"""
label_comparison_runner.py
==========================

Offline comparison runner for topic categorization.

Compares:
1) LLaMA category assignment using cluster summary only
2) LLaMA category assignment using cluster summary + LDA keywords

Adds:
- Timing metrics
- Text size statistics
- LDA topic probabilities
- Label agreement metrics
- Category distribution summary

NOT part of the API.
"""

from pathlib import Path
import json
import time
from collections import Counter

from clustering.cluster_pipeline import cluster_articles, attach_articles_to_clusters
from llm_engine.summarizer_llama import summarize_cluster_with_llama
from topic_labeling.lda_pipeline import generate_lda_labels_for_cluster
from topic_labeling.llama_lda_pipeline import generate_cluster_label_with_llama


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_FILE = BASE_DIR / "data" / "input" / "m2_articles_1.json"
OUTPUT_FILE = BASE_DIR / "data" / "output" / "m2_articles_label_comparison_3.json"

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_comparison():
    start_total = time.perf_counter()

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    articles = data["articles"] if isinstance(data, dict) else data

    article_payloads = [
        {
            "id": str(a.get("id")),
            "title": a.get("title", ""),
            "body": a.get("body", ""),
            "language": a.get("language", "en"),
        }
        for a in articles
        if a.get("language", "en") == "en"
    ]

    # ---------------- Clustering ----------------
    t0 = time.perf_counter()
    clusters = cluster_articles(article_payloads, method="hdbscan")
    clusters_for_summarization = attach_articles_to_clusters(
        clusters=clusters,
        articles=article_payloads,
    )
    clustering_time = time.perf_counter() - t0

    results = []
    category_llama_only = []
    category_llama_with_lda = []

    for cluster in clusters_for_summarization:
        cluster_id = cluster["cluster_id"]
        cluster_articles_list = cluster["articles"]

        combined_text = " ".join(
            f"{a['title']}. {a['body']}".strip()
            for a in cluster_articles_list
        )

        combined_word_count = len(combined_text.split())

        # ---------------- Summarization ----------------
        t1 = time.perf_counter()
        cluster_summary = summarize_cluster_with_llama(
            text=combined_text,
            language="en",
        )
        summarization_time = time.perf_counter() - t1

        summary_word_count = len(cluster_summary.split())

        # ---------------- LDA ----------------
        t2 = time.perf_counter()
        lda_result = generate_lda_labels_for_cluster(
            cluster={
                "cluster_id": cluster_id,
                "articles": cluster_articles_list,
            },
            num_topics=3,
        )
        lda_time = time.perf_counter() - t2

        lda_keywords = lda_result.get("lda_labels", [])
        lda_topics = lda_result.get("topics", [])  # probabilities if exposed

        # ---------------- Categorization ----------------
       # -------- LLaMA labeling (no LDA) --------
        t_label_no_lda = time.perf_counter()
        label_no_lda = generate_cluster_label_with_llama(
            cluster_summary=cluster_summary,
            article_count=len(cluster_articles_list),
            use_lda=False,
            is_noise_cluster=cluster_id == -1,
        )
        label_no_lda_time = time.perf_counter() - t_label_no_lda

        # -------- LLaMA labeling (with LDA) --------
        t_label_with_lda = time.perf_counter()
        label_with_lda = generate_cluster_label_with_llama(
            cluster_summary=cluster_summary,
            article_count=len(cluster_articles_list),
            lda_keywords=lda_keywords,
            use_lda=True,
            is_noise_cluster=cluster_id == -1,
        )
        label_with_lda_time = time.perf_counter() - t_label_with_lda

        category_llama_only.append(label_no_lda)
        category_llama_with_lda.append(label_with_lda)

        results.append(
            {
                "cluster_id": cluster_id,
                "article_count": len(cluster_articles_list),
                "article_ids": [a["id"] for a in cluster_articles_list],
                "combined_text_word_count": combined_word_count,
                "cluster_summary_word_count": summary_word_count,
                "cluster_summary": cluster_summary,
                "lda_keywords": lda_keywords,
                "lda_topics": lda_topics,
                "category_llama_only": label_no_lda,
                "category_llama_with_lda": label_with_lda,
                "label_agreement": label_no_lda == label_with_lda,
                "timing_seconds": {
                    "summarization": round(summarization_time, 3),
                    "lda": round(lda_time, 3),
                    "label_no_lda": round(label_no_lda_time, 3),
                    "label_with_lda": round(label_with_lda_time, 3),
                },
            }
        )

    total_time = time.perf_counter() - start_total

    output = {
        "input_file": INPUT_FILE.name,
        "total_articles": len(article_payloads),
        "cluster_count": len(results),
        "timing_seconds": {
            "total": round(total_time, 3),
            "clustering": round(clustering_time, 3),
        },
        "category_distribution": {
            "llama_only": dict(Counter(category_llama_only)),
            "llama_with_lda": dict(Counter(category_llama_with_lda)),
        },
        "label_agreement_rate": round(
            sum(r["label_agreement"] for r in results) / max(len(results), 1), 3
        ),
        "results": results,
    }

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Comparison complete → {OUTPUT_FILE}")


if __name__ == "__main__":
    run_comparison()