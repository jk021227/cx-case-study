"""
llm_client.py — LLM plug-in module for Assignment 2.

NO-KEY MODE (default):
    If neither OPENAI_API_KEY nor ANTHROPIC_API_KEY is set, the client
    returns deterministic rule-based answers. No external calls are made.

To enable a real LLM, export one of:
    export OPENAI_API_KEY="sk-..."        # uses gpt-3.5-turbo
    export ANTHROPIC_API_KEY="sk-ant-..." # uses claude-3-haiku

Public API:
    response, mode = complete(prompt)
    # mode ∈ {"no-key", "openai", "anthropic", "openai-error", "anthropic-error"}
"""

from __future__ import annotations

import os

# ── Environment detection ──────────────────────────────────────────────────────
_OPENAI_KEY: str = os.environ.get("OPENAI_API_KEY", "")
_ANTHROPIC_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")


def complete(
    prompt: str,
    *,
    system: str = "You are a concise, data-driven customer experience analyst.",
    max_tokens: int = 400,
    temperature: float = 0.3,
) -> tuple[str, str]:
    """Send *prompt* and return ``(response_text, mode)``.

    Priority: Anthropic → OpenAI → no-key rule-based fallback.
    """
    if _ANTHROPIC_KEY:
        return _anthropic(prompt, system=system, max_tokens=max_tokens,
                          temperature=temperature)
    if _OPENAI_KEY:
        return _openai(prompt, system=system, max_tokens=max_tokens,
                       temperature=temperature)
    return _no_key(prompt), "no-key"


# ── Provider implementations ───────────────────────────────────────────────────

def _anthropic(
    prompt: str,
    *,
    system: str,
    max_tokens: int,
    temperature: float,
) -> tuple[str, str]:
    """Call Anthropic Claude."""
    try:
        import anthropic  # type: ignore
        client = anthropic.Anthropic(api_key=_ANTHROPIC_KEY)
        msg = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip(), "anthropic"
    except Exception as exc:
        return f"[Anthropic error — {exc}]", "anthropic-error"


def _openai(
    prompt: str,
    *,
    system: str,
    max_tokens: int,
    temperature: float,
) -> tuple[str, str]:
    """Call OpenAI ChatCompletion."""
    try:
        import openai  # type: ignore
        client = openai.OpenAI(api_key=_OPENAI_KEY)
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content.strip(), "openai"
    except Exception as exc:
        return f"[OpenAI error — {exc}]", "openai-error"


# ── NO-KEY rule-based fallback ─────────────────────────────────────────────────

def _no_key(prompt: str) -> str:
    """Deterministic rule-based summary used when no API key is present.

    Extracts quoted example lines from the prompt and wraps them in a
    templated analytical response. This avoids hallucination entirely.
    """
    # Pull out bullet-pointed example lines embedded in the prompt
    examples = [
        line.strip().lstrip("-").strip().strip('"').strip()
        for line in prompt.splitlines()
        if line.strip().startswith("-") or line.strip().startswith('"')
    ]
    examples = [e for e in examples if len(e) > 15][:4]

    if examples:
        bullets = "\n".join(f"  • {e[:120]}" for e in examples)
        return (
            "Based on the retrieved complaint examples, customers are "
            "experiencing the following issues:\n"
            f"{bullets}\n\n"
            "Recommendation: Prioritise root-cause investigation for the "
            "most-frequent pain point and set up a dedicated fast-resolution "
            "queue with a 24-hour SLA target.\n\n"
            "_(NO-KEY MODE — set OPENAI_API_KEY or ANTHROPIC_API_KEY for "
            "AI-generated analysis)_"
        )

    return (
        "The selected complaints share themes around service quality, "
        "technical reliability, and billing transparency. "
        "Recommend monitoring complaint volume weekly and escalating any "
        "theme that grows more than 20% week-over-week.\n\n"
        "_(NO-KEY MODE — set OPENAI_API_KEY or ANTHROPIC_API_KEY for "
        "AI-generated analysis)_"
    )
