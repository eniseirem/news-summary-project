"""
LLaMA-based topic categorization pipeline for clustered news summaries.

Purpose
-------
This module assigns each news cluster to ONE of a fixed set of
predefined categories using LLaMA.

Categories
----------
- Global Politics
- Economics
- Sports
- Events
- General News

Design Principles
-----------------
- Categories are fixed and hard-coded.
- LLaMA selects the best category; it does NOT invent new ones.
- LDA keywords are optional supporting signals.
- Operates strictly on cluster summaries (not raw articles).
- No clustering or summarization happens here.
- Weak or noisy clusters always resolve to General News.
- Safe for UI and analytics usage.

Supported Modes
---------------
1. Summary-only classification
2. Summary + LDA-assisted classification

The `use_lda` flag enables A/B comparison.
"""

from __future__ import annotations

from typing import List, Optional

from llm_engine import llama_client


# ---------------------------------------------------------------------------
# Fixed category set
# ---------------------------------------------------------------------------

CATEGORIES = [
    "Global Politics",
    "Economics",
    "Sports",
    "Events",
    "General News",
]

# ---------------------------------------------------------------------------
# Weak cluster detection (helper function)
# ---------------------------------------------------------------------------
def _is_weak_cluster(
    cluster_summary: str,
    article_count: int,
    min_articles: int = 2,
    min_summary_words: int = 60,
    
) -> bool:
    """
    Determine whether a cluster is too weak or incoherent
    to assign a meaningful category.
    """
    if article_count < min_articles:
        return True

    if not cluster_summary.strip():
        return True

    if len(cluster_summary.split()) < min_summary_words:
        return True

    # Catch safety refusals or generic failures
    lowered = cluster_summary.lower()
    if "can't help" in lowered or "cannot help" in lowered:
        return True

    return False


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_category_prompt(
    summary: str,
    lda_keywords: Optional[List[str]] = None,
    language: str = "en",
) -> str:
    """
    Build a prompt that forces LLaMA to choose exactly one category
    from a predefined list.
    """
    lda_section = ""
    if lda_keywords:
        lda_section = (
            "\nLDA KEYWORDS:\n"
            + ", ".join(lda_keywords)
            + "\n"
        )

    categories_str = "\n".join(f"- {c}" for c in CATEGORIES)

    return (
        "You are a news editor categorizing a news topic.\n"
        "Choose the SINGLE best category from the list below.\n"
        "Do NOT create new categories.\n"
        "Return ONLY the category name, exactly as written.\n\n"
        "CATEGORIES:\n"
        f"{categories_str}\n\n"
        "CLUSTER SUMMARY:\n"
        f"{summary}\n"
        f"{lda_section}\n"
        "CATEGORY:"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_cluster_label_with_llama(
    cluster_summary: str,
    article_count: int, 
    lda_keywords: Optional[List[str]] = None,
    use_lda: bool = True,
    language: str = "en",
    is_noise_cluster: bool = False,
) -> str:
    """
    Assign a cluster to exactly one predefined news category.

    Parameters
    ----------
    cluster_summary : str
        Clean, human-readable summary of the cluster.
    lda_keywords : Optional[List[str]]
        Optional LDA keyword phrases for the cluster.
    use_lda : bool
        Whether to include LDA keywords as supporting context.
    language : str
        Output language (default: English).
    is_noise_cluster : bool
        Whether this cluster originated from HDBSCAN noise or fallback logic.

    Returns
    -------
    str
        One of the predefined category names.
    """
    
    # Hard rule: noise or weak clusters → General News
    if is_noise_cluster or _is_weak_cluster(
        cluster_summary=cluster_summary,
        article_count=article_count,
    ):
        return "General News"

    prompt = _build_category_prompt(
        summary=cluster_summary,
        lda_keywords=lda_keywords if use_lda else None,
        language=language,
    )

    raw_output = llama_client.generate_raw(
        prompt=prompt,
        max_tokens=16,
    )

    # Normalize output
    label = raw_output.strip().split("\n")[0]
    label = label.replace('"', "").replace("'", "").strip()

    # Hard safety: enforce category set
    for category in CATEGORIES:
        if label.lower() == category.lower():
            return category

    # Fallback if model outputs something unexpected
    return "General News"
