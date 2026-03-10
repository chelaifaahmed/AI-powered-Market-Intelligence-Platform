"""
scrapers/http_client.py
-----------------------
Reusable HTTP client built on ``requests.Session`` with:
- Connection pooling (via Session + HTTPAdapter)
- Library-level retry on connection/read errors (urllib3 Retry)
- Application-level retry via the @retry decorator
- Random User-Agent rotation on every request
- Configurable timeout
- Rate limiting support
- Structured logging

Usage:
    from scrapers.http_client import HttpClient
    from scrapers.rate_limiter import RateLimiter

    limiter = RateLimiter(requests_per_second=1.0)
    client  = HttpClient(timeout=15, max_retries=3, rate_limiter=limiter)
    response = client.get("https://www.caranddriver.com")
    html = response.text
"""

import logging
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scrapers.rate_limiter import RateLimiter
from scrapers.user_agents import get_random_user_agent

logger = logging.getLogger("scrapers.http_client")

# ---------------------------------------------------------------------------
# Default timeouts / pool settings
# ---------------------------------------------------------------------------
_DEFAULT_TIMEOUT: int = 15          # seconds
_DEFAULT_MAX_RETRIES: int = 3
_POOL_CONNECTIONS: int = 10
_POOL_MAXSIZE: int = 20

# HTTP status codes that indicate a transient server error worth retrying
_RETRY_STATUS_CODES: tuple[int, ...] = (429, 500, 502, 503, 504)


class HttpClient:
    """Reusable, production-grade HTTP client.

    Args:
        timeout (int): Request timeout in seconds for both connect and read.
        max_retries (int): Number of library-level retries (urllib3) on
            network errors and whitelisted status codes.
        rate_limiter (RateLimiter | None): Optional rate limiter; if provided,
            ``wait()`` is called before every request.

    Attributes:
        session (requests.Session): Underlying session with pooling & retry adapter.
    """

    def __init__(
        self,
        timeout: int = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        rate_limiter: Optional[RateLimiter] = None,
    ) -> None:
        self.timeout = timeout
        self.rate_limiter = rate_limiter
        self.session = self._build_session(max_retries)
        logger.debug(
            "HttpClient initialised (timeout=%ds, max_retries=%d, rate_limiter=%s)",
            timeout,
            max_retries,
            rate_limiter,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get(self, url: str, **kwargs) -> requests.Response:
        """Issue a GET request.

        Applies rate limiting, rotates the User-Agent header, then makes the
        request.  Raises ``requests.HTTPError`` for 4xx/5xx responses.

        Args:
            url (str): The URL to fetch.
            **kwargs: Extra keyword arguments forwarded to ``session.get()``.

        Returns:
            requests.Response: The HTTP response object.

        Raises:
            requests.HTTPError: On HTTP 4xx/5xx (after retries).
            requests.Timeout: On connect/read timeout.
            requests.ConnectionError: On network failure.
        """
        if self.rate_limiter:
            self.rate_limiter.wait()

        user_agent = get_random_user_agent()
        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", user_agent)

        logger.info("GET %s  (UA: %s…)", url, user_agent[:40])

        try:
            response = self.session.get(
                url,
                headers=headers,
                timeout=self.timeout,
                **kwargs,
            )
            response.raise_for_status()
            logger.info(
                "GET %s → %d (%d bytes)",
                url,
                response.status_code,
                len(response.content),
            )
            return response

        except requests.HTTPError as exc:
            logger.error(
                "HTTP error fetching %s → status=%d: %s",
                url,
                exc.response.status_code if exc.response is not None else "N/A",
                exc,
            )
            raise

        except requests.Timeout:
            logger.error("Timeout fetching %s (timeout=%ds)", url, self.timeout)
            raise

        except requests.ConnectionError as exc:
            logger.error("Connection error fetching %s: %s", url, exc)
            raise

        except Exception as exc:
            logger.error("Unexpected error fetching %s: %s", url, exc)
            raise

    def close(self) -> None:
        """Close the underlying session and release pooled connections."""
        self.session.close()
        logger.debug("HttpClient session closed.")

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_session(max_retries: int) -> requests.Session:
        """Create a ``requests.Session`` with a mounted retry adapter.

        The urllib3 ``Retry`` object handles:
        - Connection / read errors
        - HTTP 429 / 5xx responses (via ``status_forcelist``)
        - Exponential backoff between lib-level retries
        """
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=0.5,             # 0.5 s, 1 s, 2 s, …
            status_forcelist=list(_RETRY_STATUS_CODES),
            allowed_methods={"GET", "HEAD", "OPTIONS"},
            raise_on_status=False,          # we call raise_for_status() manually
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=_POOL_CONNECTIONS,
            pool_maxsize=_POOL_MAXSIZE,
        )
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session
