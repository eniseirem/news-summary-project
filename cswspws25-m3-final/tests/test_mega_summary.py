import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

print("TEST FILE STARTED")

from api.endpoints.mega_summarize import (
    mega_summary_from_clusters_endpoint,
    MegaSummaryFromClustersRequest,
)

# --- Files ---
INPUT_CLUSTER_SUMMARIES = ROOT / "data" / "output" / "cluster_summaries.json"
OUTPUT_MEGA_SUMMARY = ROOT / "data" / "output" / "mega_summary.json"


def test_mega_summary():
    # 1) Load cluster summaries
    if not INPUT_CLUSTER_SUMMARIES.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT_CLUSTER_SUMMARIES}")

    with open(INPUT_CLUSTER_SUMMARIES, "r", encoding="utf-8") as f:
        cluster_summary_data = json.load(f)

    # Expected structure:
    # {
    #   "request_id": "...",
    #   "cluster_count": N,
    #   "clusters": [
    #       { "cluster_id": "...", "summary": "...", ... }
    #   ]
    # }

    clusters = cluster_summary_data.get("clusters", [])
    if not clusters:
        raise ValueError("No clusters found in cluster_summaries.json")

    # 2) Build cluster_summaries dict for mega summary
    cluster_summaries = {}
    for c in clusters:
        cid = str(c.get("cluster_id"))
        summary = c.get("summary", "").strip()
        if cid and summary:
            cluster_summaries[cid] = summary

    if not cluster_summaries:
        raise ValueError("No valid cluster summaries found")

    # 3) Build typed request object
    request = MegaSummaryFromClustersRequest(
        request_id="test-mega-summary",
        cluster_summaries=cluster_summaries,
    )

    # 4) Call endpoint directly
    response = mega_summary_from_clusters_endpoint(request)

    # 5) Write output
    OUTPUT_MEGA_SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_MEGA_SUMMARY, "w", encoding="utf-8") as f:
        json.dump(response.model_dump(), f, indent=2, ensure_ascii=False)

    # 6) Console feedback
    print("Mega summary successfully generated")
    print(f"Output written to: {OUTPUT_MEGA_SUMMARY}")
    print(f"Clusters used: {response.cluster_ids}")
    print(f"Cluster count: {response.cluster_count}")


if __name__ == "__main__":
    test_mega_summary()
