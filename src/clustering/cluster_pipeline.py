"""
cluster_pipeline.py
===================
End-to-end clustering pipeline that groups articles by topic similarity.

Design contract (post-translation strategy)
------------------------------------------
This module is language-agnostic and does NOT perform translation.
Upstream orchestration (e.g. /cluster_summary) must ensure texts are in English.

This module:
- Builds embeddings from article texts
- Clusters embeddings (HDBSCAN default, KMeans optional)
- Returns cluster structures only (cluster_id, article_ids, label=None)

Incremental Clustering Support
-------------------------------
Supports incremental clustering mode, where new articles can be matched to existing
clusters instead of re-clustering from scratch. Use cluster_articles_incremental() for this mode.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.cluster import KMeans
from hdbscan import HDBSCAN

from clustering.embeddings import encode
from clustering.incremental_clustering import (
    match_to_existing_clusters,
    add_article_to_cluster,
    create_new_cluster_from_articles,
)


def _extract_article_id(article: Dict[str, Any]) -> Optional[str]:
    """Support both 'id' and 'url' during migration."""
    article_id = article.get("id") or article.get("url")
    return str(article_id) if article_id is not None else None


def _extract_article_text(article: Dict[str, Any]) -> str:
    """
    Extract best-effort text from an article dict.

    Priority:
    1) 'text' (already prepared text, often a summary)
    2) 'body' (+ optional title emphasis)
    3) fallback empty
    """
    text = (article.get("text") or "").strip()
    if text:
        return text

    body = (article.get("body") or "").strip()
    title = (article.get("title") or "").strip()

    if title and body:
        # keep your original heuristic: repeat title twice to weight it a bit
        return ((title + ". ") * 2 + body).strip()
    if body:
        return body
    if title:
        return title

    return ""


def cluster_articles(
    articles: List[Dict[str, Any]],
    method: str = "hdbscan",
    n_clusters: Optional[int] = None,
    min_cluster_size: int = 2,
) -> List[Dict[str, Any]]:
    """
    Cluster articles by topic similarity using embeddings.

    Parameters
    ----------
    articles : List[Dict[str, Any]]
        List of article dicts with at least 'id'/'url' and some text field.
        Expected minimal format: [{"id": "art1", "text": "..."}, ...]
    method : str, default "hdbscan"
        Clustering method: "kmeans" or "hdbscan"
    n_clusters : Optional[int], default None
        For KMeans: number of clusters. If None, auto-determines based on article count.
    min_cluster_size : int, default 2
        For HDBSCAN: minimum cluster size.

    Returns
    -------
    List[Dict[str, Any]]
        [{
            "cluster_id": int,
            "article_ids": List[str],
            "label": None
        }, ...]
    """
    if not articles:
        return []

    texts: List[str] = []
    article_ids: List[str] = []

    for article in articles:
        article_id = _extract_article_id(article)
        if article_id is None:
            continue

        text = _extract_article_text(article)
        if not text:
            continue

        texts.append(text)
        article_ids.append(article_id)

    if not texts:
        return []

    embeddings = encode(texts)

    # Handle edge case: not enough articles to cluster
    if len(embeddings) < 2:
        if len(embeddings) == 1:
            return [{"cluster_id": 0, "article_ids": article_ids, "label": None}]
        return []

    # Perform clustering
    if method == "kmeans":
        if n_clusters is None:
            n_clusters = max(2, min(10, int(np.sqrt(len(texts)))))

        clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)  # type: ignore[arg-type]
        cluster_labels = clusterer.fit_predict(embeddings)

    elif method == "hdbscan":
        num_points = len(embeddings)

        if num_points > 100:
            adjusted_min_samples = min(5, num_points - 1)
        elif num_points > 50:
            adjusted_min_samples = min(3, num_points - 1)
        else:
            adjusted_min_samples = min(1, num_points - 1) if num_points > 1 else 1

        adjusted_min_cluster_size = min(min_cluster_size, num_points)

        clusterer = HDBSCAN(
            min_cluster_size=adjusted_min_cluster_size,
            min_samples=adjusted_min_samples,
            metric="euclidean",
            cluster_selection_method="eom",
        )
        cluster_labels = clusterer.fit_predict(embeddings)

    else:
        raise ValueError(f"Unknown clustering method: {method}")

    # Group articles by cluster
    clusters_dict: Dict[int, List[str]] = {}
    noise_article_ids: List[str] = []

    for idx, cluster_id in enumerate(cluster_labels):
        aid = article_ids[idx]

        if int(cluster_id) == -1:
            noise_article_ids.append(aid)
            continue

        cid = int(cluster_id)
        clusters_dict.setdefault(cid, []).append(aid)

    result: List[Dict[str, Any]] = []
    for cid, aids in clusters_dict.items():
        result.append({"cluster_id": cid, "article_ids": aids, "label": None})

    if noise_article_ids:
        misc_cluster_id = max(clusters_dict.keys(), default=-1) + 1
        result.append({"cluster_id": misc_cluster_id, "article_ids": noise_article_ids, "label": None})

    return result


def attach_articles_to_clusters(
    clusters: List[Dict[str, Any]],
    articles: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Attach full article objects (id, title, body) to each cluster.
    Note: This is only used in some pipelines; /cluster_summary uses its own article_map.
    """
    article_by_id: Dict[str, Dict[str, Any]] = {}
    for a in articles:
        article_id = _extract_article_id(a)
        if article_id is None:
            continue
        article_by_id[article_id] = {
            "id": article_id,
            "title": a.get("title", ""),
            "body": a.get("body", ""),
        }

    clusters_for_summarization: List[Dict[str, Any]] = []
    for cluster in clusters:
        article_ids = cluster.get("article_ids") or cluster.get("article_urls", [])
        clusters_for_summarization.append(
            {
                "cluster_id": cluster["cluster_id"],
                "articles": [article_by_id[aid] for aid in article_ids if aid in article_by_id],
            }
        )
    return clusters_for_summarization


def cluster_articles_incremental(
    articles: List[Dict[str, Any]],
    similarity_threshold: float = 0.7,
    min_cluster_size: int = 2,
    method: str = "hdbscan",
    use_existing_clusters: bool = True,
) -> List[Dict[str, Any]]:
    """
    Cluster articles incrementally, matching to existing clusters when possible.
    Expects input texts already in English (handled upstream).
    """
    if not articles:
        return []

    texts: List[str] = []
    article_ids: List[str] = []

    for article in articles:
        article_id = _extract_article_id(article)
        if article_id is None:
            continue

        text = _extract_article_text(article)
        if not text:
            continue

        texts.append(text)
        article_ids.append(article_id)

    if not texts:
        return []

    embeddings = encode(texts)
    if len(embeddings) == 0:
        return []

    if not use_existing_clusters:
        return cluster_articles(articles, method=method, min_cluster_size=min_cluster_size)

    matched_articles: Dict[str, str] = {}
    unmatched_indices: List[int] = []
    unmatched_articles: List[Dict[str, Any]] = []
    unmatched_embeddings: List[np.ndarray] = []

    for idx, (article_id, embedding) in enumerate(zip(article_ids, embeddings)):
        best_match_id, _candidates = match_to_existing_clusters(
            article_embedding=embedding,
            similarity_threshold=similarity_threshold,
            top_k=3,
        )

        if best_match_id:
            matched_articles[article_id] = best_match_id
            try:
                add_article_to_cluster(
                    cluster_id=best_match_id,
                    article_id=article_id,
                    article_embedding=embedding,
                )
            except Exception as e:
                print(f"[INCREMENTAL_CLUSTERING] Error adding article {article_id} to cluster {best_match_id}: {e}")
                unmatched_indices.append(idx)
                unmatched_articles.append({"id": article_id, "text": texts[idx], "language": "en"})
                unmatched_embeddings.append(embedding)
        else:
            unmatched_indices.append(idx)
            unmatched_articles.append({"id": article_id, "text": texts[idx], "language": "en"})
            unmatched_embeddings.append(embedding)

    matched_clusters: Dict[str, List[str]] = {}
    for article_id, cluster_id in matched_articles.items():
        matched_clusters.setdefault(cluster_id, []).append(article_id)

    result: List[Dict[str, Any]] = []
    for cluster_id, matched_article_ids in matched_clusters.items():
        result.append(
            {
                "cluster_id": cluster_id,
                "article_ids": matched_article_ids,
                "label": None,
                "is_new": False,
                "matched_from": cluster_id,
            }
        )

    if unmatched_articles:
        print(f"[INCREMENTAL_CLUSTERING] {len(unmatched_articles)} articles unmatched, clustering them...")

        unmatched_clusters = cluster_articles(unmatched_articles, method=method, min_cluster_size=min_cluster_size)

        for cluster in unmatched_clusters:
            cluster_article_ids = cluster.get("article_ids", [])
            if not cluster_article_ids:
                continue

            cluster_embeddings: Dict[str, np.ndarray] = {}
            for i, aid in enumerate(article_ids):
                if aid in cluster_article_ids and i in unmatched_indices:
                    idx_in_unmatched = unmatched_indices.index(i)
                    cluster_embeddings[aid] = unmatched_embeddings[idx_in_unmatched]

            try:
                new_cluster = create_new_cluster_from_articles(
                    article_ids=cluster_article_ids,
                    article_embeddings=cluster_embeddings,
                    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
                )
                result.append(
                    {
                        "cluster_id": new_cluster["cluster_id"],
                        "article_ids": cluster_article_ids,
                        "label": None,
                        "is_new": True,
                        "matched_from": None,
                    }
                )
            except Exception as e:
                print(f"[INCREMENTAL_CLUSTERING] Error creating new cluster: {e}")
                result.append(
                    {
                        "cluster_id": f"temp_{len(result)}",
                        "article_ids": cluster_article_ids,
                        "label": None,
                        "is_new": True,
                        "matched_from": None,
                    }
                )

    return result
