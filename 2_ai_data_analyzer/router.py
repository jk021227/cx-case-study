"""
router.py — Query classification and dispatch for Assignment 2.

Classifies incoming questions as 'quant' or 'qual' and routes them
to the appropriate handler.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from quant_handler import QuantHandler
from qual_handler import QualHandler

# Keywords that signal a quantitative query
_QUANT_PATTERNS: list[str] = [
    r"\bhow many\b", r"\bhow much\b", r"\btotal\b", r"\bcount\b",
    r"\bnumber of\b", r"\bpercentage\b", r"\bpercent\b", r"\brate\b",
    r"\bfrequency\b", r"\bdistribution\b", r"\bbreakdown\b", r"\btrend\b",
    r"\btop \d*\s*theme", r"\bmost common\b", r"\blargest\b", r"\bhighest\b",
    r"\blowest\b", r"\baverage\b", r"\bmean\b", r"\bmedian\b",
    r"\bby channel\b", r"\bby month\b", r"\bby week\b",
    r"\bby product\b", r"\bby severity\b", r"\bwhich channel\b",
    r"\bwhich product\b", r"\bover time\b", r"\btime series\b",
]

# Keywords that signal a qualitative query
_QUAL_PATTERNS: list[str] = [
    r"\bwhy\b", r"\bwhat are customers saying\b", r"\bdescribe\b",
    r"\bsummarise\b", r"\bsummarize\b", r"\bexamples\b",
    r"\bshow me examples\b", r"\bwhat kind of\b", r"\bexplain\b",
    r"\bissues with\b", r"\bcomplaints about\b", r"\bfeelings\b",
    r"\bsentiment\b", r"\bpain point\b", r"\bwhat is wrong\b",
    r"\bwhat do customers\b", r"\bwhat are the main\b",
]

_QUANT_RE = re.compile("|".join(_QUANT_PATTERNS), re.IGNORECASE)
_QUAL_RE = re.compile("|".join(_QUAL_PATTERNS), re.IGNORECASE)


def classify(query: str) -> str:
    """Return ``'quant'``, ``'qual'``, or ``'ambiguous'``.

    Uses regex pattern matching and falls back to 'qual' for ambiguous
    open-ended questions.
    """
    quant_hits = len(_QUANT_RE.findall(query))
    qual_hits = len(_QUAL_RE.findall(query))

    if quant_hits > qual_hits:
        return "quant"
    if qual_hits > quant_hits:
        return "qual"
    # Tie-break: short numeric-style questions -> quant; else qual
    if re.search(r"\b(how|many|count|total|top|which|show)\b", query, re.I):
        return "quant"
    return "qual"


class Router:
    """Dispatch user queries to QuantHandler or QualHandler."""

    def __init__(self, cleaned_df: pd.DataFrame, themes_df: pd.DataFrame) -> None:
        self.quant = QuantHandler(cleaned_df, themes_df)
        self.qual = QualHandler(cleaned_df, themes_df)

    def answer(self, query: str) -> dict[str, Any]:
        """Route *query* and return a result dict with ``query_type`` added."""
        qtype = classify(query)
        if qtype == "quant":
            result = self.quant.handle(query)
            result["query_type"] = "quantitative"
        else:
            result = self.qual.handle(query)
            result["query_type"] = "qualitative"
        return result
