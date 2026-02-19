"""
theme_extractor.py — Offline theme extraction using TF-IDF + KMeans.

No API keys required. All computation is local.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

# Extended stop-word list (augments sklearn defaults for financial CX domain)
_STOPWORDS: set[str] = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you",
    "your", "yours", "yourself", "yourselves", "he", "him", "his",
    "himself", "she", "her", "hers", "herself", "it", "its", "itself",
    "they", "them", "their", "theirs", "themselves", "what", "which",
    "who", "whom", "this", "that", "these", "those", "am", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "having",
    "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if",
    "or", "because", "as", "until", "while", "of", "at", "by", "for",
    "with", "about", "against", "between", "into", "through", "during",
    "before", "after", "above", "below", "to", "from", "up", "down",
    "in", "out", "on", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why", "how",
    "all", "both", "each", "few", "more", "most", "other", "some",
    "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "s", "t", "can", "will", "just", "don", "should",
    "now", "ve", "ll", "re", "also", "get", "got", "would", "could",
    "please", "like", "one", "even", "still", "since", "us", "every",
    "use", "used", "using", "want", "need", "told", "said", "tell",
    "say", "know", "go", "going", "come", "back", "make", "made",
    "take", "taken", "time", "times", "day", "days", "week", "weeks",
    "month", "months", "year", "years", "two", "three", "four", "five",
    "tried", "trying", "keep", "kept",
}

# Heuristic label rules: keyword set → human-readable label
_LABEL_RULES: list[tuple[set[str], str]] = [
    ({"app", "mobile", "login", "crash", "password", "screen", "error", "loading",
      "authentication", "fingerprint", "face", "update", "ios", "android"}, "App & Login Issues"),
    ({"charge", "fee", "charged", "overdraft", "statement", "billing", "refund",
      "maintenance", "annual", "late", "penalty", "balance transfer"}, "Billing & Fee Disputes"),
    ({"transaction", "payment", "declined", "transfer", "unauthorized", "fraud",
      "purchase", "debit", "atm", "withdrawal", "deposit", "wire"}, "Transaction Problems"),
    ({"account", "locked", "access", "blocked", "frozen", "verification", "reset",
      "security", "flag", "suspended", "recover"}, "Account Access Issues"),
    ({"service", "representative", "staff", "wait", "hold", "support", "agent",
      "call", "phone", "transferred", "rude", "unhelpful", "callback"}, "Customer Service Quality"),
    ({"loan", "mortgage", "interest", "rate", "application", "approval",
      "personal", "refinance", "payoff", "equity"}, "Loan & Mortgage Issues"),
    ({"card", "chip", "tap", "contactless", "apple", "google", "pay",
      "pin", "credit", "limit"}, "Card & Payment Method Issues"),
]


def _auto_label(top_keywords: list[str]) -> str:
    """Heuristically assign a human-readable label to a cluster."""
    kw_set = set(top_keywords[:8])
    for keyword_group, label in _LABEL_RULES:
        if kw_set & keyword_group:
            return label
    # Fallback: title-case top 2 keywords
    return " & ".join(w.title() for w in top_keywords[:2])


def extract_themes(
    df: pd.DataFrame,
    text_col: str = "text_clean",
    n_themes: int = 5,
    seed: int = 42,
    n_top_keywords: int = 10,
    max_features: int = 3000,
) -> pd.DataFrame:
    """Extract complaint themes via TF-IDF vectorisation + KMeans clustering.

    Adds a ``theme_id`` column to ``df`` in-place (integer cluster label).

    Parameters
    ----------
    df:
        DataFrame containing the cleaned text column.
    text_col:
        Name of the cleaned text column.
    n_themes:
        Number of clusters to create.
    seed:
        Random seed — guarantees deterministic output.
    n_top_keywords:
        Number of top TF-IDF keywords to store per theme.
    max_features:
        TF-IDF vocabulary size cap.

    Returns
    -------
    themes_df:
        One row per theme with columns:
        theme_id, label, count, top_keywords, example_texts.
    """
    texts = df[text_col].fillna("").tolist()

    if len(texts) < n_themes:
        n_themes = max(2, len(texts) // 2)
        logger.warning(
            "Fewer documents (%d) than requested themes; reducing n_themes to %d.",
            len(texts), n_themes,
        )

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=max_features,
        stop_words=list(_STOPWORDS),
        min_df=2,
        sublinear_tf=True,
    )
    X = vectorizer.fit_transform(texts)

    km = KMeans(n_clusters=n_themes, random_state=seed, n_init=10, max_iter=300)
    labels: np.ndarray = km.fit_predict(X)
    df["theme_id"] = labels.tolist()

    feature_names = vectorizer.get_feature_names_out()
    # argsort descending → indices of highest-weight features per centroid
    order_centroids = km.cluster_centers_.argsort()[:, ::-1]

    records: list[dict] = []
    for i in range(n_themes):
        top_kw = [feature_names[idx] for idx in order_centroids[i, :n_top_keywords]]
        mask = df["theme_id"] == i
        count = int(mask.sum())
        examples = df.loc[mask, text_col].head(3).tolist()
        label = _auto_label(top_kw)

        records.append(
            {
                "theme_id": i,
                "label": label,
                "count": count,
                "top_keywords": ", ".join(top_kw),
                "example_texts": " | ".join(examples),
            }
        )

    themes_df = (
        pd.DataFrame(records)
        .sort_values("count", ascending=False)
        .reset_index(drop=True)
    )

    logger.info(
        "Extracted %d themes. Top: '%s' (%d rows).",
        n_themes,
        themes_df.iloc[0]["label"],
        themes_df.iloc[0]["count"],
    )
    return themes_df
