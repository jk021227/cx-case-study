"""
quant_handler.py — Answers quantitative questions from aggregated data.

Handles questions like:
  "How many complaints do we have?"
  "What are the top themes?"
  "Show me complaints by channel / product / severity"
  "Show me the monthly trend"
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd


class QuantHandler:
    """Answer quantitative questions from pre-loaded DataFrames."""

    def __init__(self, cleaned_df: pd.DataFrame, themes_df: pd.DataFrame) -> None:
        self.df = cleaned_df.copy()
        self.themes = themes_df.copy()
        self._prepare()

    def _prepare(self) -> None:
        """Pre-compute derived columns used by multiple methods."""
        if "date" in self.df.columns:
            self.df["_date"] = pd.to_datetime(self.df["date"], errors="coerce")
            self.df["_month"] = self.df["_date"].dt.to_period("M").astype(str)
            self.df["_week"] = self.df["_date"].dt.to_period("W").astype(str)

    # ── Public API ─────────────────────────────────────────────────────────────

    def handle(self, query: str) -> dict[str, Any]:
        """Route a quantitative query and return a result dict."""
        q = query.lower()

        if re.search(r"\bhow many\b|\btotal\b|\bcount\b|\bnumber of\b", q):
            return self._count_query(q)
        if re.search(r"\btop theme|\bbiggest theme|\bmost common theme|\blargest theme\b", q):
            return self._top_themes_query()
        if re.search(r"\btheme|\bcluster|\btopic|\bsegment\b", q):
            return self._all_themes_query()
        if re.search(r"\bchannel|\bemail|\bphone|\bchat|\bsocial\b", q):
            return self._channel_query()
        if re.search(r"\btrend|\bmonth|\bweek|\bover time|\btime series\b", q):
            return self._trend_query(q)
        if re.search(r"\bseverity|\bhigh|\bcritical|\burgent|\blow\b", q):
            return self._severity_query()
        if re.search(r"\bproduct|\bcategory|\bmortgage|\bloan|\bcredit card\b", q):
            return self._product_query()

        return self._general_stats()

    # ── Query implementations ──────────────────────────────────────────────────

    def _count_query(self, q: str) -> dict[str, Any]:
        total = len(self.df)
        extras: list[str] = []

        if "theme" in q and len(self.themes) > 0:
            top = self.themes.iloc[0]
            extras.append(
                f"The largest theme is **{top['label']}** "
                f"({int(top['count']):,} complaints, "
                f"{int(top['count'])/total*100:.1f}% of total)."
            )
        if "channel" in self.df.columns:
            top_ch = self.df["channel"].value_counts()
            extras.append(
                f"Top channel: **{top_ch.index[0]}** ({top_ch.iloc[0]:,} complaints)."
            )

        answer = f"There are **{total:,}** complaints in the dataset."
        if extras:
            answer += "\n\n" + "\n".join(extras)

        return {
            "answer": answer,
            "data": {"total_complaints": total},
            "confidence": f"Based on all {total:,} rows",
        }

    def _top_themes_query(self) -> dict[str, Any]:
        rows = [
            f"  {rank}. **{row['label']}** — {int(row['count']):,} complaints "
            f"({int(row['count'])/len(self.df)*100:.1f}%)"
            for rank, row in enumerate(self.themes.itertuples(), 1)
        ]
        return {
            "answer": "**Top complaint themes (by volume):**\n" + "\n".join(rows),
            "data": self.themes[["theme_id", "label", "count"]].to_dict(orient="records"),
            "confidence": f"Based on {len(self.df):,} complaints across {len(self.themes)} themes",
        }

    def _all_themes_query(self) -> dict[str, Any]:
        return self._top_themes_query()

    def _channel_query(self) -> dict[str, Any]:
        if "channel" not in self.df.columns:
            return {
                "answer": "No `channel` column found in the dataset.",
                "data": {},
                "confidence": "N/A",
            }
        ch = self.df["channel"].value_counts()
        rows = [
            f"  - **{k}**: {v:,} ({v/len(self.df)*100:.1f}%)"
            for k, v in ch.items()
        ]
        return {
            "answer": "**Complaints by channel:**\n" + "\n".join(rows),
            "data": ch.to_dict(),
            "confidence": f"Based on {len(self.df):,} complaints",
        }

    def _trend_query(self, q: str) -> dict[str, Any]:
        if "_month" not in self.df.columns:
            return {
                "answer": "No `date` column found — trend analysis unavailable.",
                "data": {},
                "confidence": "N/A",
            }
        period_col = "_week" if "week" in q else "_month"
        trend = (
            self.df.groupby(period_col)
            .size()
            .reset_index(name="count")
            .rename(columns={period_col: "period"})
        )
        rows = [
            f"  - **{row['period']}**: {row['count']:,}"
            for _, row in trend.iterrows()
        ]
        label = "weekly" if period_col == "_week" else "monthly"
        return {
            "answer": f"**Complaint trend ({label}):**\n" + "\n".join(rows),
            "data": trend.to_dict(orient="records"),
            "confidence": (
                f"Based on {len(self.df):,} complaints "
                f"across {len(trend)} {label} periods"
            ),
        }

    def _severity_query(self) -> dict[str, Any]:
        if "severity" not in self.df.columns:
            return {
                "answer": "No `severity` column found in the dataset.",
                "data": {},
                "confidence": "N/A",
            }
        sv = self.df["severity"].value_counts()
        rows = [
            f"  - **{k}**: {v:,} ({v/len(self.df)*100:.1f}%)"
            for k, v in sv.items()
        ]
        return {
            "answer": "**Complaints by severity:**\n" + "\n".join(rows),
            "data": sv.to_dict(),
            "confidence": f"Based on {len(self.df):,} complaints",
        }

    def _product_query(self) -> dict[str, Any]:
        col = next(
            (c for c in ["product_category", "product", "category"]
             if c in self.df.columns),
            None,
        )
        if col is None:
            return {
                "answer": "No product/category column found in the dataset.",
                "data": {},
                "confidence": "N/A",
            }
        pc = self.df[col].value_counts()
        rows = [
            f"  - **{k}**: {v:,} ({v/len(self.df)*100:.1f}%)"
            for k, v in pc.items()
        ]
        return {
            "answer": f"**Complaints by {col.replace('_', ' ')}:**\n" + "\n".join(rows),
            "data": pc.to_dict(),
            "confidence": f"Based on {len(self.df):,} complaints",
        }

    def _general_stats(self) -> dict[str, Any]:
        total = len(self.df)
        lines = [f"**Dataset summary:** {total:,} complaints loaded."]

        if len(self.themes) > 0:
            top = self.themes.iloc[0]
            lines.append(
                f"Top theme: **{top['label']}** ({int(top['count']):,} complaints)."
            )
        if "channel" in self.df.columns:
            top_ch = self.df["channel"].value_counts()
            lines.append(f"Top channel: **{top_ch.index[0]}** ({top_ch.iloc[0]:,}).")
        if "severity" in self.df.columns:
            high = int((self.df["severity"] == "high").sum())
            lines.append(
                f"High-severity complaints: **{high:,}** ({high/total*100:.1f}%)."
            )

        return {
            "answer": "\n".join(lines),
            "data": {"total": total},
            "confidence": f"Based on {total:,} rows",
        }
