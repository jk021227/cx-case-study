"""
cleaner.py — Data cleaning module for Assignment 1.

Applies:
  1. Schema validation / best-text-column auto-detection
  2. Deduplication
  3. Null / empty-text handling
  4. Text normalisation (lowercase, whitespace collapse, URL/email removal)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Ranked list of column names that are likely to contain complaint text
_TEXT_COL_CANDIDATES: list[str] = [
    "complaint_text",
    "complaint",
    "text",
    "description",
    "message",
    "body",
    "content",
    "notes",
    "comments",
    "feedback",
    "issue",
    "details",
    "narrative",
]

_RE_URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_RE_EMAIL = re.compile(r"\S+@\S+\.\S+", re.IGNORECASE)
_RE_SPECIAL = re.compile(r"[^\w\s.,!?'\-]")
_RE_WHITESPACE = re.compile(r"\s+")


# ── Public helpers ─────────────────────────────────────────────────────────────

def detect_text_column(df: pd.DataFrame) -> str:
    """Auto-detect the best column for complaint text.

    Returns the first matching known candidate name (case-insensitive).
    Falls back to the string column with the longest average length.

    Raises
    ------
    ValueError
        If no string column is found at all.
    """
    cols_lower: dict[str, str] = {c.lower(): c for c in df.columns}

    for candidate in _TEXT_COL_CANDIDATES:
        if candidate in cols_lower:
            col = cols_lower[candidate]
            logger.debug("Auto-detected text column by name: %s", col)
            return col

    str_cols = df.select_dtypes(include="object").columns.tolist()
    if not str_cols:
        raise ValueError(
            "No string/text column found in the CSV. "
            "Pass --text-col <column_name> explicitly."
        )

    avg_len: dict[str, float] = {
        c: df[c].dropna().astype(str).str.len().mean() for c in str_cols
    }
    best = max(avg_len, key=avg_len.get)  # type: ignore[arg-type]
    logger.warning(
        "Text column not found by name. Falling back to longest string column: "
        "'%s' (avg %.0f chars). Pass --text-col to override.",
        best,
        avg_len[best],
    )
    return best


def normalize_text(text: str) -> str:
    """Normalise a single complaint string.

    Steps: lowercase → strip URLs → strip emails → strip special chars →
           collapse whitespace → strip leading/trailing whitespace.
    """
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = _RE_URL.sub(" ", text)
    text = _RE_EMAIL.sub(" ", text)
    text = _RE_SPECIAL.sub(" ", text)
    text = _RE_WHITESPACE.sub(" ", text)
    return text.strip()


def clean(
    df: pd.DataFrame,
    text_col: Optional[str] = None,
    *,
    drop_duplicates: bool = True,
    min_text_length: int = 10,
) -> tuple[pd.DataFrame, dict]:
    """Clean a raw complaints DataFrame.

    Parameters
    ----------
    df:
        Raw input DataFrame.
    text_col:
        Name of the complaint text column. Auto-detected when ``None``.
    drop_duplicates:
        Drop rows that are exact duplicates on the text column.
    min_text_length:
        Drop rows whose normalised text is shorter than this.

    Returns
    -------
    cleaned_df:
        Cleaned DataFrame with an added ``text_clean`` column.
    metrics:
        Dict of cleaning metrics (counts, drop reasons).
    """
    metrics: dict = {"rows_in": len(df)}

    if text_col is None:
        text_col = detect_text_column(df)
    metrics["text_col"] = text_col

    # Step 1 — Drop fully-null rows
    before = len(df)
    df = df.dropna(how="all")
    metrics["dropped_all_null_rows"] = before - len(df)

    # Step 2 — Drop rows with null/empty text column
    before = len(df)
    df = df[df[text_col].notna()]
    df = df[df[text_col].astype(str).str.strip() != ""]
    metrics["dropped_null_text"] = before - len(df)

    # Step 3 — Deduplicate on text column
    if drop_duplicates:
        before = len(df)
        df = df.drop_duplicates(subset=[text_col])
        metrics["dropped_duplicates"] = before - len(df)
    else:
        metrics["dropped_duplicates"] = 0

    # Step 4 — Normalise text into new column
    df = df.copy()
    df["text_clean"] = df[text_col].astype(str).apply(normalize_text)

    # Step 5 — Drop texts that are too short after normalisation
    before = len(df)
    df = df[df["text_clean"].str.len() >= min_text_length]
    metrics["dropped_short_text"] = before - len(df)

    metrics["rows_out"] = len(df)
    metrics["rows_retained_pct"] = (
        round(metrics["rows_out"] / metrics["rows_in"] * 100, 1)
        if metrics["rows_in"] > 0
        else 0.0
    )

    logger.info(
        "Cleaning complete: %d → %d rows (%.1f%% retained, "
        "%d dupes, %d null-text, %d too-short removed)",
        metrics["rows_in"],
        metrics["rows_out"],
        metrics["rows_retained_pct"],
        metrics["dropped_duplicates"],
        metrics["dropped_null_text"],
        metrics["dropped_short_text"],
    )

    return df.reset_index(drop=True), metrics
