import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clustering.cluster_pipeline import cluster_articles

INPUT_FILE = ROOT / "data" / "output" / "translation" / "translation_roundtrip_results.json"
OUTPUT_FILE = ROOT / "data" / "output" / "translation" / "topic_clustering_results.json"


def test_topic_clustering_on_translated_articles():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        translated_articles = json.load(f)

    articles_for_clustering = []
    for art in translated_articles:
        articles_for_clustering.append(
            {
                "id": art["id"],
                "title": art["translated_en"].get("title", ""),
                "body": art["translated_en"].get("body", ""),
            }
        )

    clusters = cluster_articles(
        articles_for_clustering,
        method="hdbscan",
        min_cluster_size=2,
    )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(clusters, f, indent=2)

    print(f"Generated {len(clusters)} clusters")
    for c in clusters:
        print(f"Cluster {c['cluster_id']}: {len(c['article_ids'])} articles")


if __name__ == "__main__":
    test_topic_clustering_on_translated_articles()
