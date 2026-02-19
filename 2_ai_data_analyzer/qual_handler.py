"""
qual_handler.py — Retrieves complaint examples and summarises qualitative findings.

Uses keyword + theme matching to fetch relevant rows, then calls the LLM
client (or rule-based fallback in NO-KEY MODE) to produce a short analysis.
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

import llm_client

_MAX_EXAMPLES = 8   # Max examples sent to LLM / shown in output


class QualHandler:
    """Answer qualitative questions via retrieval + summarisation."""

    def __init__(self, cleaned_df: pd.DataFrame, themes_df: pd.DataFrame) -> None:
        self.df = cleaned_df.copy()
        self.themes = themes_df.copy()
        # Prefer original text if available; fall back to normalised
        self._text_col = (
            "complaint_text" if "complaint_text" in self.df.columns else "text_clean"
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def handle(self, query: str) -> dict[str, Any]:
        """Retrieve relevant examples and return an analysis dict."""
        examples, retrieval_info = self._retrieve(query)
        summary, mode = self._summarise(query, examples)

        return {
            "answer": summary,
            "examples": examples[:3],
            "confidence": retrieval_info,
            "llm_mode": mode,
        }

    # ── Retrieval ──────────────────────────────────────────────────────────────

    def _retrieve(self, query: str) -> tuple[list[str], str]:
        """Return matching complaint texts and a retrieval metadata string."""
        q_lower = query.lower()
        pool = self.df

        # 1. Try to match a known theme label
        for row in self.themes.itertuples():
            label_words = set(str(row.label).lower().split())
            query_words = set(q_lower.split())
            if label_words & query_words:
                pool = self.df[self.df["theme_id"] == row.theme_id]
                break

        # 2. Keyword search within the chosen pool
        keywords = [
            w for w in re.split(r"\W+", q_lower)
            if len(w) > 3 and w not in {
                "what", "show", "give", "tell", "about", "with", "from",
                "that", "have", "more", "some", "many", "which", "this",
                "they", "their", "customers", "complaints", "issues",
            }
        ]

        if keywords:
            pattern = "|".join(re.escape(k) for k in keywords)
            text_pool = pool["text_clean"] if "text_clean" in pool.columns else pool[self._text_col]
            mask = text_pool.str.contains(pattern, case=False, na=False)
            matched = pool[mask]
        else:
            matched = pool

        # Fall back to full pool if no keyword hits
        if len(matched) == 0:
            matched = pool

        examples = matched[self._text_col].dropna().head(_MAX_EXAMPLES).tolist()
        info = (
            f"{len(matched):,} matching complaints retrieved "
            f"(showing top {min(len(examples), _MAX_EXAMPLES)})"
        )
        return examples, info

    # ── Summarisation ──────────────────────────────────────────────────────────

    def _summarise(self, query: str, examples: list[str]) -> tuple[str, str]:
        """Build a prompt from the retrieved examples and call the LLM."""
        if not examples:
            return "No relevant complaints found for this query.", "no-key"

        bullets = "\n".join(f'- "{e[:200]}"' for e in examples)
        prompt = (
            f"A customer experience analyst is reviewing customer complaints.\n\n"
            f"Question: {query}\n\n"
            f"Relevant complaint examples ({len(examples)} retrieved):\n"
            f"{bullets}\n\n"
            f"Provide a concise analysis (3–5 sentences) that:\n"
            f"1. Identifies the core pain points\n"
            f"2. Notes any patterns (urgency, frequency, channel, severity)\n"
            f"3. Suggests one concrete, actionable recommendation\n"
        )
        return llm_client.complete(prompt)
