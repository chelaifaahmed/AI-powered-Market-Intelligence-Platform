"""
parsers/__init__.py
-------------------
Automotive Parser package.
"""

from parsers.automotive_pipeline import AutomotivePipeline, ParserPipeline  # noqa: F401

__all__ = ["AutomotivePipeline", "ParserPipeline"]
