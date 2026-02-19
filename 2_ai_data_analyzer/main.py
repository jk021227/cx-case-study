#!/usr/bin/env python3
"""
Assignment 2: AI + Data Analyzer — Interactive Chat Interface
=============================================================

Loads cleaned complaint data and themes from Assignment 1 outputs
(auto-runs Assignment 1 if outputs are missing), then starts an
interactive CLI chat session.

Usage
-----
  python main.py
  python main.py --cleaned ../out/cleaned_complaints.csv --themes ../out/themes.csv

LLM Modes
---------
  NO-KEY MODE (default):   Rule-based answers. Set one of:
  OPENAI_API_KEY           → enables OpenAI GPT summarisation
  ANTHROPIC_API_KEY        → enables Anthropic Claude summarisation

Type :help inside the chat for example questions.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Allow running as a script from any directory
sys.path.insert(0, str(Path(__file__).parent))

from router import Router
import llm_client

_WELCOME = """\
╔══════════════════════════════════════════════════════════════╗
║    CX Case Study — AI + Data Analyzer  (Assignment 2)       ║
╚══════════════════════════════════════════════════════════════╝

Ask any question about customer complaints and press Enter.
Commands: :quit  :help  :examples  :mode
"""

_HELP = """\
─────────────────────────────────────────────────────────────
EXAMPLE QUESTIONS
─────────────────────────────────────────────────────────────
Quantitative (counts, distributions, trends):
  1.  How many complaints are there in total?
  2.  What are the top complaint themes?
  3.  How many complaints came through the phone channel?
  4.  Show me the monthly complaint trend
  5.  What percentage of complaints are high severity?
  6.  Which product category has the most complaints?

Qualitative (analysis of content and root causes):
  7.  Why are customers frustrated with the mobile app?
  8.  Summarise complaints about billing and fees
  9.  What are customers saying about customer service?
  10. Describe the main issues with account access
  11. Show me examples of transaction problems
  12. What is wrong with the loan application process?
─────────────────────────────────────────────────────────────
"""


# ── Data loading ───────────────────────────────────────────────────────────────

def _load_data(cleaned_path: Path, themes_path: Path):
    import pandas as pd
    cleaned_df = pd.read_csv(cleaned_path)
    themes_df = pd.read_csv(themes_path)
    return cleaned_df, themes_df


def _run_assignment1(output_dir: Path) -> bool:
    """Auto-run Assignment 1 to generate required output files."""
    repo_root = Path(__file__).parent.parent
    data_path = repo_root / "data" / "sample_complaints.csv"
    script = repo_root / "1_complaints_tool" / "main.py"

    if not data_path.exists():
        print(f"[error] Sample data not found: {data_path}")
        return False
    if not script.exists():
        print(f"[error] Assignment 1 script not found: {script}")
        return False

    print("[auto] Running Assignment 1 to generate output files …")
    result = subprocess.run(
        [sys.executable, str(script),
         "--input", str(data_path),
         "--output-dir", str(output_dir)],
        capture_output=False,
        text=True,
    )
    return result.returncode == 0


# ── Formatting ─────────────────────────────────────────────────────────────────

def _fmt(result: dict) -> str:
    """Format a result dict for terminal display."""
    qtype = result.get("query_type", "?").upper()
    lines = [f"\n[{qtype}]", result.get("answer", "")]

    if result.get("examples"):
        lines.append("\nTop retrieved examples:")
        for ex in result["examples"][:2]:
            truncated = ex[:130] + "…" if len(ex) > 130 else ex
            lines.append(f"  • {truncated}")

    footer_parts: list[str] = []
    if conf := result.get("confidence"):
        footer_parts.append(f"Confidence: {conf}")
    if mode := result.get("llm_mode"):
        footer_parts.append(f"Mode: {mode}")
    if footer_parts:
        lines.append("\n" + " | ".join(footer_parts))

    lines.append("")
    return "\n".join(lines)


# ── Chat loop ──────────────────────────────────────────────────────────────────

def _run_chat(router: Router) -> None:
    print(_WELCOME)

    # Detect and announce LLM mode
    _, mode = llm_client.complete("ping", max_tokens=1)
    if mode == "no-key":
        print(
            "  ⚠  NO-KEY MODE  —  No API key found. Answers use rule-based summaries.\n"
            "     To enable AI analysis: export OPENAI_API_KEY=... "
            "or ANTHROPIC_API_KEY=...\n"
        )
    else:
        print(f"  ✓  LLM mode: {mode}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input in (":quit", ":exit", "quit", "exit"):
            print("Goodbye!")
            break
        if user_input in (":help", "help", ":examples", "examples"):
            print(_HELP)
            continue
        if user_input == ":mode":
            _, m = llm_client.complete("ping", max_tokens=1)
            print(f"  Current mode: {m}\n")
            continue

        result = router.answer(user_input)
        print(_fmt(result))


# ── Entry point ────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="CX AI + Data Analyzer — Assignment 2",
    )
    p.add_argument("--cleaned", default="../out/cleaned_complaints.csv",
                   metavar="PATH", help="Cleaned complaints CSV")
    p.add_argument("--themes", default="../out/themes.csv",
                   metavar="PATH", help="Themes CSV")
    p.add_argument("--run-assignment1", action="store_true",
                   help="Force-run Assignment 1 before starting")
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    cleaned_path = Path(args.cleaned)
    themes_path = Path(args.themes)
    out_dir = cleaned_path.parent

    # Auto-generate outputs if missing
    if args.run_assignment1 or not cleaned_path.exists() or not themes_path.exists():
        if not _run_assignment1(out_dir):
            sys.exit(1)

    if not cleaned_path.exists() or not themes_path.exists():
        print("[error] Required files still missing after running Assignment 1.")
        print(f"  {cleaned_path}")
        print(f"  {themes_path}")
        sys.exit(1)

    print(f"[info] Loading data from {out_dir} …")
    cleaned_df, themes_df = _load_data(cleaned_path, themes_path)
    print(f"[info] Loaded {len(cleaned_df):,} complaints, {len(themes_df)} themes.\n")

    router = Router(cleaned_df, themes_df)
    _run_chat(router)


if __name__ == "__main__":
    main()
