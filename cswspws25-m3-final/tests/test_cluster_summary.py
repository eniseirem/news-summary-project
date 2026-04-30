import sys
import json
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from api.endpoints.cluster_summarize import (
    cluster_summary_from_clusters_endpoint,
    ClusterSummaryFromClustersRequest,
)
from api.schemas import Article

INPUT_TRANSLATIONS = ROOT / "data" / "output" / "translation" / "translation_roundtrip_results.json"
INPUT_CLUSTERS = ROOT / "data" / "output" / "translation" / "topic_clustering_results.json"
OUTPUT_CLUSTER_SUMMARIES = ROOT / "data" / "output" / "cluster_summaries.json"


def load_articles():
    with open(INPUT_TRANSLATIONS, "r", encoding="utf-8") as f:
        data = json.load(f)

    articles = []
    for art in data:
        articles.append(
            Article(
                id=art["id"],
                title=art["translated_en"].get("title", ""),
                body=art["translated_en"].get("body", ""),
                language="en",
                original_language="de",
            )
        )
    return articles


async def run_test():
    with open(INPUT_CLUSTERS, "r", encoding="utf-8") as f:
        clusters_raw = json.load(f)

    # cluster_id muss string sein
    for c in clusters_raw:
        c["cluster_id"] = str(c["cluster_id"])

    req = ClusterSummaryFromClustersRequest(
        request_id="test-cluster-summary",
        clusters=clusters_raw,
        articles=load_articles(),
        article_summaries=None,
    )

    response = await cluster_summary_from_clusters_endpoint(req)

    OUTPUT_CLUSTER_SUMMARIES.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_CLUSTER_SUMMARIES, "w", encoding="utf-8") as f:
        json.dump(response.model_dump(), f, indent=2, ensure_ascii=False)

    print(f"Generated {response.cluster_count} cluster summaries")


if __name__ == "__main__":
    asyncio.run(run_test())
