#!/usr/bin/env python3
"""
Assignment 1: Customer Complaints CLI Tool
==========================================

Reads a complaints CSV, cleans it, extracts recurring themes via
TF-IDF + KMeans, and writes four output files.

Usage
-----
  python main.py --input ../data/sample_complaints.csv --output-dir ../out

Options
-------
  --input PATH        Path to input complaints CSV (required)
  --output-dir PATH   Output directory (default: ../out)
  --n-themes INT      Number of themes to extract (default: 5)
  --text-col NAME     Text column name (auto-detected if omitted)
  --seed INT          Random seed for reproducibility (default: 42)
  --verbose           Enable DEBUG-level logging
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running as a script from any working directory
sys.path.insert(0, str(Path(__file__).parent))

from cleaner import clean
from theme_extractor import extract_themes
from reporter import save_outputs


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Customer Complaints Analysis Tool — Assignment 1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--input", required=True, metavar="PATH",
                   help="Input complaints CSV path")
    p.add_argument("--output-dir", default="../out", metavar="PATH",
                   help="Directory for output files (default: ../out)")
    p.add_argument("--n-themes", type=int, default=5, metavar="INT",
                   help="Number of themes to extract (default: 5)")
    p.add_argument("--text-col", default=None, metavar="NAME",
                   help="Text column name (auto-detected if omitted)")
    p.add_argument("--seed", type=int, default=42,
                   help="Random seed (default: 42)")
    p.add_argument("--verbose", action="store_true",
                   help="Enable DEBUG-level logging")
    return p.parse_args(argv)


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        level=logging.DEBUG if verbose else logging.INFO,
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns 0 on success, 1 on error."""
    args = _parse_args(argv)
    _setup_logging(args.verbose)
    log = logging.getLogger(__name__)

    input_path = Path(args.input)
    if not input_path.exists():
        log.error("Input file not found: %s", input_path)
        return 1

    # ── Step 1: Load ──────────────────────────────────────────────────────────
    log.info("Loading %s …", input_path)
    try:
        import pandas as pd
        df_raw = pd.read_csv(input_path)
    except Exception as exc:
        log.error("Failed to read CSV: %s", exc)
        return 1
    log.info("Loaded %d rows × %d columns", *df_raw.shape)

    # ── Step 2: Clean ─────────────────────────────────────────────────────────
    log.info("Cleaning data …")
    df_clean, cleaning_metrics = clean(df_raw, text_col=args.text_col)

    # ── Step 3: Extract themes ────────────────────────────────────────────────
    log.info("Extracting %d themes …", args.n_themes)
    themes_df = extract_themes(
        df_clean,
        n_themes=args.n_themes,
        seed=args.seed,
    )

    # ── Step 4: Save outputs ──────────────────────────────────────────────────
    log.info("Writing outputs to %s …", args.output_dir)
    paths = save_outputs(df_clean, themes_df, cleaning_metrics, args.output_dir)

    # ── Print summary ─────────────────────────────────────────────────────────
    divider = "=" * 62
    print(f"\n{divider}")
    print("  Assignment 1 — Complete")
    print(divider)
    print(f"  Input rows      : {cleaning_metrics['rows_in']:>6,}")
    print(f"  After cleaning  : {cleaning_metrics['rows_out']:>6,}  "
          f"({cleaning_metrics['rows_retained_pct']}% retained)")
    print(f"  Themes found    : {args.n_themes:>6}")
    print()
    print("  Top themes:")
    for _, row in themes_df.head(5).iterrows():
        print(f"    [{int(row['theme_id'])}] {row['label']:35s}  n={row['count']}")
    print()
    print("  Output files:")
    for name, path in paths.items():
        print(f"    {name:<20} -> {path}")
    print(f"{divider}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
