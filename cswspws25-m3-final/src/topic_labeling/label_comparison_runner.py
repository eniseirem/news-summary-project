"""

How Abby currently runs this (might be different for yours):
- Terminal 1: 
OLLAMA_HOST=0.0.0.0:11435 ollama serve

- Terminal 2: 
cd ../..cswspws25
source .venv/bin/activate
export OLLAMA_HOST=http://localhost:11434
export LLM_BACKEND=llama
PYTHONPATH=/Users/ajocard/AbbyDevelopments/cswspws25/src python -m topic_labeling.label_comparison_runner

--------------------------
label_comparison_runner.py
==========================

Offline comparison runner for topic categorization.

This script compares two approaches for assigning clusters
to one of the fixed news categories:

1) LLaMA category assignment using cluster summary only
2) LLaMA category assignment using cluster summary + LDA keywords

Fixed Categories:
- Global Politics
- Economics
- Sports
- Events
- General News

Input:
- data/input/M2_articles.json

Output:
- data/output/M2_articles_label_comparison.json

This script is NOT part of the API and must not be imported
by FastAPI endpoints.
"""

from pathlib import Path
import json

from clustering.cluster_pipeline import cluster_articles, attach_articles_to_clusters
from llm_engine.summarizer_llama import summarize_cluster_with_llama
from topic_labeling.lda_pipeline import generate_lda_labels_for_cluster
from topic_labeling.llama_lda_pipeline import generate_cluster_label_with_llama


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = BASE_DIR / "data" / "input" / "m2_articles_1.json"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "m2_articles_label_comparison.json"

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Core comparison logic
# ---------------------------------------------------------------------------

def run_comparison():
    if not INPUT_FILE.exists():
        print(f"Input file not found: {INPUT_FILE}")
        return

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Support both list-only and wrapped formats
    if isinstance(data, dict) and "articles" in data:
        articles = data["articles"]
    elif isinstance(data, list):
        articles = data
    else:
        print("Unsupported input format.")
        return

    # Prepare articles for clustering (English only)
    article_payloads = [
        {
            "id": str(a.get("id")),
            "title": a.get("title", ""),
            "body": a.get("body", ""),
            "language": a.get("language", "en"),
        }
        for a in articles
        if isinstance(a, dict) and a.get("language", "en") == "en"
    ]

    if not article_payloads:
        print("No valid English articles found.")
        return

    # -------------------------------------------------------------------
    # Clustering
    # -------------------------------------------------------------------

    clusters = cluster_articles(article_payloads, method="hdbscan")  # pyright: ignore

    clusters_for_summarization = attach_articles_to_clusters(
        clusters=clusters,
        articles=article_payloads,
    )

    results = []

    for cluster in clusters_for_summarization:
        cluster_id = cluster["cluster_id"]
        cluster_articles_list = cluster["articles"]

        combined_text = " ".join(
            f"{a['title']}. {a['body']}".strip()
            for a in cluster_articles_list
        )

        # ----------------------------------------------------------------
        # Step 1: Cluster summary (LLaMA)
        # ----------------------------------------------------------------

        cluster_summary = summarize_cluster_with_llama(
            text=combined_text,
            language="en",
        )

        # ----------------------------------------------------------------
        # Step 2: LDA keyword extraction (3 topics)
        # ----------------------------------------------------------------

        lda_result = generate_lda_labels_for_cluster(
            cluster={
                "cluster_id": cluster_id,
                "articles": cluster_articles_list,
            },
            num_topics=3,
        )

        lda_keywords = lda_result.get("lda_labels", [])

        # ----------------------------------------------------------------
        # Step 3: Category assignment
        # ----------------------------------------------------------------

        category_llama_only = generate_cluster_label_with_llama(
            cluster_summary=cluster_summary,
            article_count=len(cluster_articles_list),
            use_lda=False,
            is_noise_cluster=cluster_id == -1,
        )

        category_llama_with_lda = generate_cluster_label_with_llama(
            cluster_summary=cluster_summary,
            article_count=len(cluster_articles_list),
            lda_keywords=lda_keywords,
            use_lda=True,
            is_noise_cluster=cluster_id == -1,
        )

        results.append(
            {
                "cluster_id": cluster_id,
                "article_ids": [a["id"] for a in cluster_articles_list],
                "cluster_summary": cluster_summary,
                "lda_keywords": lda_keywords,
                "category_llama_only": category_llama_only,
                "category_llama_with_lda": category_llama_with_lda,
            }
        )

    # -------------------------------------------------------------------
    # Write output
    # -------------------------------------------------------------------

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "input_file": INPUT_FILE.name,
                "cluster_count": len(results),
                "results": results,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"Comparison complete. Results written to {OUTPUT_FILE}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run_comparison()
