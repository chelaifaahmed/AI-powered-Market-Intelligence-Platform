"""
parsers/html_cleaner.py
-----------------------
STEP 2 — HTML Cleaning

Strips boilerplate (navigation, ads, headers, footers, scripts, styles, tracking
elements, cookie banners) and returns:
    - clean_text  : readable plain text for LLM / regex passes
    - clean_html  : lightly stripped HTML for DOM heuristic pass

Priority:
    1. trafilatura  (best boilerplate removal)
    2. BeautifulSoup tag stripping (fallback if trafilatura unavailable)
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Tuple

from bs4 import BeautifulSoup

logger = logging.getLogger("parsers.html_cleaner")

# Tags whose entire subtree should be removed before any text extraction
_STRIP_TAGS = {
    "script", "style", "noscript", "iframe", "svg", "canvas",
    "header", "footer", "nav", "aside", "form",
}

# CSS class / id substrings associated with noise — matched case-insensitively
_NOISE_PATTERNS = re.compile(
    r"(cookie|consent|gdpr|popup|modal|banner|ad[-_]|advertisement|"
    r"tracking|analytics|sidebar|nav(igation)?|breadcrumb|social|"
    r"share|comment|footer|header|related|recommended)",
    re.IGNORECASE,
)


def _bs4_clean(html: str) -> Tuple[str, str]:
    """
    Fallback cleaner: uses BeautifulSoup to strip boilerplate tags and
    noise-labelled elements.

    Returns (clean_text, clean_html).
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove structural noise tags
    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    # Remove elements whose class/id suggests noise
    for element in soup.find_all(True):
        # If element is already removed from tree by a collapsed parent, skip it
        if element.parent is None:
            continue
        
        c = element.get("class")
        if not c:
            classes = ""
        elif isinstance(c, list):
            classes = " ".join(str(x) for x in c)
        else:
            classes = str(c)
            
        el_id = str(element.get("id") or "")
        
        if _NOISE_PATTERNS.search(classes) or _NOISE_PATTERNS.search(el_id):
            element.decompose()

    clean_html = str(soup)
    clean_text = soup.get_text(separator="\n", strip=True)
    # Collapse excessive blank lines
    clean_text = re.sub(r"\n{3,}", "\n\n", clean_text)
    return clean_text, clean_html


def clean_html(raw_html: str) -> Tuple[str, str]:
    """
    Clean raw HTML and return (clean_text, clean_html).

    Tries trafilatura first; falls back to BS4 stripping.

    Args:
        raw_html: Full HTML string from the database.

    Returns:
        (clean_text, clean_html): Tuple of plain text and stripped HTML.
    """
    if not raw_html:
        return "", ""

    # --- Primary: trafilatura ---
    try:
        import trafilatura  # type: ignore

        clean_text: Optional[str] = trafilatura.extract(
            raw_html,
            include_tables=False,
            include_comments=False,
            include_formatting=False,
            no_fallback=False,
            output_format="txt",
        )
        if clean_text and len(clean_text.strip()) > 100:
            # Also produce a BS4-cleaned HTML for the DOM pass
            _, clean_html_str = _bs4_clean(raw_html)
            logger.debug(
                "trafilatura extracted %d chars of clean text", len(clean_text)
            )
            return clean_text.strip(), clean_html_str
    except Exception as exc:
        logger.debug("trafilatura failed (%s) — falling back to BS4", exc)

    # --- Fallback: BS4 ---
    try:
        clean_text_bs4, clean_html_bs4 = _bs4_clean(raw_html)
        logger.debug(
            "BS4 extracted %d chars of clean text", len(clean_text_bs4)
        )
        return clean_text_bs4, clean_html_bs4
    except Exception as exc:
        logger.error("BS4 cleaning failed: %s", exc)
        return "", raw_html
