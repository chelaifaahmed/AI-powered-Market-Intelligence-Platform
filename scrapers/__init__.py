"""
scrapers/__init__.py
--------------------
Public API for the Phase 3A scraping infrastructure package.
"""

from scrapers.base_scraper import BaseScraper
from scrapers.http_client import HttpClient
from scrapers.rate_limiter import RateLimiter
from scrapers.retry_handler import retry
from scrapers.user_agents import get_random_user_agent

__all__ = [
    "BaseScraper",
    "HttpClient",
    "RateLimiter",
    "retry",
    "get_random_user_agent",
]
