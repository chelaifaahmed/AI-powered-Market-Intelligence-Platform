"""
scrapers/retry_handler.py
--------------------------
Generic retry decorator for network calls with exponential back-off + jitter.

Usage:
    from scrapers.retry_handler import retry

    @retry(max_retries=3, delay=1.0, backoff=2.0)
    def fetch(url: str) -> str:
        ...
"""

import functools
import logging
import random
import time
from typing import Any, Callable, Tuple, Type, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger("scrapers.retry")


def retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    jitter: float = 0.3,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable[..., Any]:
    """Decorator factory — retries the wrapped function on failure.

    Args:
        max_retries (int): Maximum number of retry attempts (not counting the
            first call). Total attempts = max_retries + 1.
        delay (float): Initial sleep duration in seconds before the first retry.
        backoff (float): Multiplier applied to ``delay`` after each failure.
            ``backoff=2`` → exponential back-off (1 s, 2 s, 4 s, …).
        jitter (float): Maximum seconds of random jitter added to each sleep,
            preventing thundering-herd issues.
        exceptions (tuple): Exception types that trigger a retry. All others
            propagate immediately.

    Returns:
        Callable: The decorated function.

    Example:
        @retry(max_retries=3, delay=2.0, backoff=2.0,
               exceptions=(requests.Timeout, requests.ConnectionError))
        def fetch_page(url):
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:  # cast to F at return
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc

                    if attempt == max_retries:
                        # All retries exhausted — re-raise
                        logger.error(
                            "[retry] %s — all %d attempt(s) failed. "
                            "Final error: %s",
                            func.__qualname__,
                            max_retries + 1,
                            exc,
                        )
                        raise

                    sleep_time = current_delay + random.uniform(0, jitter)
                    logger.warning(
                        "[retry] %s — attempt %d/%d failed: %s. "
                        "Retrying in %.2f s …",
                        func.__qualname__,
                        attempt + 1,
                        max_retries + 1,
                        exc,
                        sleep_time,
                    )
                    time.sleep(sleep_time)
                    current_delay *= backoff

            # Should never be reached, but satisfies type checkers.
            raise last_exception  # type: ignore[misc]

        return cast(F, wrapper)  # type: ignore[return-value]

    return decorator  # type: ignore[return-value]
