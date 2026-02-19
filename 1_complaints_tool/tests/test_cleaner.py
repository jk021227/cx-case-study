"""
Tests for cleaner.py — run with:  pytest 1_complaints_tool/tests/ -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

# Make sure the package is importable when running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from cleaner import clean, detect_text_column, normalize_text


# ── normalize_text ────────────────────────────────────────────────────────────

class TestNormalizeText:
    def test_lowercase(self):
        assert normalize_text("Hello WORLD") == "hello world"

    def test_strips_url(self):
        result = normalize_text("Visit https://example.com for help")
        assert "https" not in result
        assert "example.com" not in result

    def test_strips_email(self):
        result = normalize_text("Contact support@bank.com today")
        assert "support@bank.com" not in result

    def test_collapses_whitespace(self):
        assert normalize_text("too   many    spaces") == "too many spaces"

    def test_strips_leading_trailing(self):
        assert normalize_text("  hello  ") == "hello"

    def test_non_string_returns_empty(self):
        assert normalize_text(None) == ""   # type: ignore[arg-type]
        assert normalize_text(42) == ""     # type: ignore[arg-type]

    def test_empty_string_returns_empty(self):
        assert normalize_text("") == ""


# ── detect_text_column ────────────────────────────────────────────────────────

class TestDetectTextColumn:
    def test_finds_complaint_text_column(self):
        df = pd.DataFrame({"complaint_text": ["abc"], "date": ["2024-01-01"]})
        assert detect_text_column(df) == "complaint_text"

    def test_case_insensitive(self):
        df = pd.DataFrame({"Complaint_Text": ["abc"], "id": [1]})
        assert detect_text_column(df) == "Complaint_Text"

    def test_fallback_to_longest_string_col(self):
        df = pd.DataFrame({
            "short": ["hi"],
            "longer_text": ["this is a much longer string that should win"],
        })
        col = detect_text_column(df)
        assert col == "longer_text"

    def test_raises_when_no_string_col(self):
        df = pd.DataFrame({"a": [1, 2], "b": [3.0, 4.0]})
        with pytest.raises(ValueError, match="No string"):
            detect_text_column(df)


# ── clean ─────────────────────────────────────────────────────────────────────

class TestClean:
    def _make_df(self, texts: list, **kwargs) -> pd.DataFrame:
        data = {"complaint_text": texts}
        data.update(kwargs)
        return pd.DataFrame(data)

    def test_adds_text_clean_column(self):
        df = self._make_df(["My card was declined today at the store."])
        cleaned, _ = clean(df)
        assert "text_clean" in cleaned.columns

    def test_removes_nulls(self):
        df = self._make_df(["Valid complaint text here.", None, ""])
        cleaned, metrics = clean(df)
        assert len(cleaned) == 1
        assert metrics["dropped_null_text"] >= 1

    def test_deduplication(self):
        df = self._make_df(["Duplicate complaint text", "Duplicate complaint text",
                            "A different complaint text"])
        cleaned, metrics = clean(df)
        assert metrics["dropped_duplicates"] == 1
        assert len(cleaned) == 2

    def test_short_text_removed(self):
        df = self._make_df(["ok", "This is a sufficiently long complaint text."])
        cleaned, metrics = clean(df)
        assert metrics["dropped_short_text"] == 1
        assert len(cleaned) == 1

    def test_metrics_rows_in_out(self):
        df = self._make_df([
            "First valid complaint about the service quality.",
            "Second valid complaint about billing fees charged.",
        ])
        cleaned, metrics = clean(df)
        assert metrics["rows_in"] == 2
        assert metrics["rows_out"] == 2
        assert metrics["rows_retained_pct"] == 100.0

    def test_text_normalised_in_output(self):
        df = self._make_df(["MY CARD WAS DECLINED  TODAY"])
        cleaned, _ = clean(df)
        assert cleaned["text_clean"].iloc[0] == "my card was declined today"

    def test_no_dedup_when_disabled(self):
        df = self._make_df(["Same text here for testing.", "Same text here for testing."])
        cleaned, metrics = clean(df, drop_duplicates=False)
        assert metrics["dropped_duplicates"] == 0
        assert len(cleaned) == 2

    def test_returns_reset_index(self):
        df = self._make_df(["Valid complaint text alpha.", None,
                            "Valid complaint text beta."])
        cleaned, _ = clean(df)
        assert list(cleaned.index) == list(range(len(cleaned)))
