"""
scrapers/rate_limiter.py
------------------------
Thread-safe request throttler that enforces a maximum requests-per-second rate.

Usage:
    limiter = RateLimiter(requests_per_second=0.5)   # 1 req every 2 s
    limiter.wait()   # call before every HTTP request
"""

import logging
import threading
import time

logger = logging.getLogger("scrapers.rate_limiter")


class RateLimiter:
    """Throttles outbound HTTP requests to a configurable rate.

    Args:
        requests_per_second (float): Maximum allowed request rate.
            E.g. ``1.0`` = one request per second,
                 ``0.5`` = one request every 2 seconds.

    Thread safety:
        A ``threading.Lock`` serialises ``wait()`` calls so multiple
        threads sharing one ``RateLimiter`` instance do not race.
    """

    def __init__(self, requests_per_second: float = 1.0) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be a positive number.")
        self.requests_per_second: float = requests_per_second
        self._min_interval: float = 1.0 / requests_per_second
        self._last_called: float = 0.0
        self._lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def wait(self) -> None:
        """Block the caller until the rate limit interval has elapsed.

        Call this immediately before issuing an HTTP request.
        """
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_called
            sleep_for = self._min_interval - elapsed

            if sleep_for > 0:
                logger.debug(
                    "Rate limiter sleeping %.3f s (interval=%.3f s, "
                    "elapsed=%.3f s)",
                    sleep_for,
                    self._min_interval,
                    elapsed,
                )
                time.sleep(sleep_for)

            self._last_called = time.monotonic()

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"RateLimiter("
            f"requests_per_second={self.requests_per_second}, "
            f"min_interval={self._min_interval:.3f}s)"
        )
