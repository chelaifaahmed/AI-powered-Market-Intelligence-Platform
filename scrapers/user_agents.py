"""
scrapers/user_agents.py
-----------------------
Rotating pool of realistic modern browser User-Agent strings.

Usage:
    from scrapers.user_agents import get_random_user_agent
    ua = get_random_user_agent()
"""

import random

# ---------------------------------------------------------------------------
# Modern browser User-Agent strings (updated 2025-Q1)
# Mix of Chrome, Firefox, Edge, and Safari across Windows / macOS / Linux.
# ---------------------------------------------------------------------------
USER_AGENTS: list[str] = [
    # Chrome 122 — Windows 10
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",

    # Chrome 121 — Windows 11
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",

    # Chrome 120 — macOS Sonoma
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

    # Chrome 119 — Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",

    # Firefox 123 — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) "
    "Gecko/20100101 Firefox/123.0",

    # Firefox 122 — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.3; rv:122.0) "
    "Gecko/20100101 Firefox/122.0",

    # Firefox 121 — Linux
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) "
    "Gecko/20100101 Firefox/121.0",

    # Edge 122 — Windows 10
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",

    # Edge 121 — Windows 11
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",

    # Safari 17 — macOS Sonoma
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",

    # Safari 16 — macOS Ventura
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_4) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.6.1 Safari/605.1.15",

    # Chrome 122 — Android 14
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.6261.90 Mobile Safari/537.36",

    # Chrome 121 — Android 13
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",

    # Firefox 122 — Android
    "Mozilla/5.0 (Android 13; Mobile; rv:122.0) "
    "Gecko/122.0 Firefox/122.0",

    # Opera 106 — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0",

    # Brave-based Chrome 122 — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Brave/1.63",
]


def get_random_user_agent() -> str:
    """Return a random User-Agent string from the pool.

    Returns:
        str: A modern browser UA string chosen at random.
    """
    return random.choice(USER_AGENTS)
