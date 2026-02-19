"""
reporter.py — Output generation for Assignment 1.

Writes four files to the output directory:
  cleaned_complaints.csv  — deduplicated, normalised complaints
  themes.csv              — theme_id, label, count, top_keywords, example_texts
  summary.md              — human-readable Markdown report
  metrics.json            — machine-readable cleaning + theme metadata
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def save_outputs(
    cleaned_df: pd.DataFrame,
    themes_df: pd.DataFrame,
    cleaning_metrics: dict,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Persist all Assignment 1 outputs.

    Returns a mapping of ``{name: path}`` for every file written.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}

    # ── 1. Cleaned CSV ────────────────────────────────────────────────────────
    p = out / "cleaned_complaints.csv"
    cleaned_df.to_csv(p, index=False)
    paths["cleaned_csv"] = p
    logger.info("Saved: %s", p)

    # ── 2. Themes CSV ─────────────────────────────────────────────────────────
    p = out / "themes.csv"
    themes_df.to_csv(p, index=False)
    paths["themes_csv"] = p
    logger.info("Saved: %s", p)

    # ── 3. Summary Markdown ───────────────────────────────────────────────────
    p = out / "summary.md"
    _write_summary(cleaned_df, themes_df, cleaning_metrics, p)
    paths["summary_md"] = p
    logger.info("Saved: %s", p)

    # ── 4. Metrics JSON ───────────────────────────────────────────────────────
    p = out / "metrics.json"
    full_metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cleaning": cleaning_metrics,
        "themes": themes_df[["theme_id", "label", "count"]].to_dict(orient="records"),
    }
    p.write_text(json.dumps(full_metrics, indent=2))
    paths["metrics_json"] = p
    logger.info("Saved: %s", p)

    return paths


# ── Private helpers ────────────────────────────────────────────────────────────

def _write_summary(
    cleaned_df: pd.DataFrame,
    themes_df: pd.DataFrame,
    cleaning_metrics: dict,
    path: Path,
) -> None:
    """Generate the Markdown summary report."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# Customer Complaints Analysis — Summary Report",
        f"\n_Generated: {ts}_\n",
        "---\n",
        "## Dataset Overview\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Raw rows ingested | {cleaning_metrics['rows_in']:,} |",
        f"| Rows after cleaning | {cleaning_metrics['rows_out']:,} |",
        f"| Retention rate | {cleaning_metrics['rows_retained_pct']}% |",
        f"| Duplicates removed | {cleaning_metrics.get('dropped_duplicates', 0):,} |",
        f"| Null / empty text removed | {cleaning_metrics.get('dropped_null_text', 0):,} |",
        f"| Too-short text removed | {cleaning_metrics.get('dropped_short_text', 0):,} |",
        f"| Text column used | `{cleaning_metrics.get('text_col', 'unknown')}` |",
        "",
    ]

    # Optional date range
    if "date" in cleaned_df.columns:
        try:
            dates = pd.to_datetime(cleaned_df["date"], errors="coerce").dropna()
            if len(dates) > 0:
                lines += [
                    f"| Date range | {dates.min().date()} -> {dates.max().date()} |",
                    "",
                ]
        except Exception:
            pass

    # Channel breakdown (if column exists)
    if "channel" in cleaned_df.columns:
        ch = cleaned_df["channel"].value_counts()
        lines += [
            "### Complaints by Channel\n",
            "| Channel | Count | Share |",
            "|---------|-------|-------|",
        ]
        for ch_name, cnt in ch.items():
            pct = cnt / len(cleaned_df) * 100
            lines.append(f"| {ch_name} | {cnt} | {pct:.1f}% |")
        lines.append("")

    # Product breakdown (if column exists)
    for col in ["product_category", "product", "category"]:
        if col in cleaned_df.columns:
            pc = cleaned_df[col].value_counts()
            lines += [
                f"### Complaints by {col.replace('_', ' ').title()}\n",
                "| Category | Count | Share |",
                "|----------|-------|-------|",
            ]
            for cat, cnt in pc.items():
                pct = cnt / len(cleaned_df) * 100
                lines.append(f"| {cat} | {cnt} | {pct:.1f}% |")
            lines.append("")
            break

    # Theme summary table
    lines += [
        "---\n",
        "## Top Recurring Themes\n",
        "| Rank | Theme | Complaints | Top Keywords |",
        "|------|-------|-----------|--------------|",
    ]
    for rank, row in enumerate(themes_df.itertuples(), 1):
        kw_preview = ", ".join(str(row.top_keywords).split(", ")[:5])
        lines.append(
            f"| {rank} | **{row.label}** | {row.count} | {kw_preview} |"
        )

    # Theme detail sections
    lines += ["", "---\n", "## Theme Details\n"]
    for row in themes_df.itertuples():
        lines += [
            f"### Theme {row.theme_id}: {row.label} ({row.count} complaints)\n",
            f"**Keywords:** {row.top_keywords}\n",
            "**Example complaints:**\n",
        ]
        for i, ex in enumerate(str(row.example_texts).split(" | "), 1):
            lines.append(f"> {i}. {ex}")
        lines.append("")

    lines += [
        "---\n",
        "_Report generated by `1_complaints_tool/main.py` — CX Case Study, Assignment 1_",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
