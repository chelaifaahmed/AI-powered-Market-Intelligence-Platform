"""
parsers/automotive_pipeline.py
------------------------------
Unified orchestrator for processing scraped automotive and insurance pages.
"""

from __future__ import annotations

import logging
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from parsers.html_cleaner import clean_html
from parsers.dom_extractor import extract_from_dom
from parsers.schema_extractor import extract_from_schema
from parsers.llm_extractor import extract_with_llm
from parsers.normalizer import merge_extractions, normalise_results
from parsers.validator import validate

logger = logging.getLogger("parsers.automotive_pipeline")

class AutomotivePipeline:
    def __init__(self, session: Session):
        self.session = session

    def process_page(self, raw_html: str, source_url: str) -> Dict[str, Any]:
        """
        Processes a single raw page into structured automotive intelligence.
        """
        # 1. Clean HTML
        clean_text, stripped_html = clean_html(raw_html)
        if not clean_text:
            return {"status": "error", "reason": "empty_text"}

        # 2. Extract
        dom_data = extract_from_dom(stripped_html, source_url)
        schema_data = extract_from_schema(raw_html)
        llm_data = extract_with_llm(clean_text)

        # 3. Merge & Normalise
        raw_merged = merge_extractions(schema_data, dom_data, llm_data)
        normalised = normalise_results(raw_merged, source_url)

        # 4. Validate
        is_valid, reason = validate(normalised)
        if not is_valid:
            return {"status": "invalid", "reason": reason}

        return {"status": "success", "data": normalised}
