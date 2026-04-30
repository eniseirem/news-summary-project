"""
cluster_maintenance.py
======================

Cluster maintenance functions for merging and archiving clusters.

Purpose
-------
This module provides functions to maintain clusters over time:
- Merge similar clusters
- Archive stale clusters
- Clean up duplicate clusters

Design Notes
------------
- Uses cosine similarity to find similar clusters
- Archives clusters that haven't been updated recently
- Merges clusters with high similarity
"""

import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from clustering.cluster_storage import (
    load_clusters,
    save_clusters,
    get_active_clusters,
    archive_cluster,
    update_cluster,
    get_cluster_centroids,
    DEFAULT_CLUSTERS_FILE,
    DEFAULT_ARCHIVE_FILE,
)
from clustering.incremental_clustering import cosine_similarity


def find_similar_clusters(
    similarity_threshold: float = 0.85,
    clusters_file: Optional[Path] = None,
) -> List[Tuple[str, str, float]]:
    """
    Find pairs of similar clusters that could be merged.
    
    Parameters
    ----------
    similarity_threshold : float, default 0.85
        Minimum similarity to consider clusters similar.
    clusters_file : Optional[Path]
        Path to clusters file (uses default if None).
    
    Returns
    -------
    List[Tuple[str, str, float]]
        List of tuples: (cluster_id_1, cluster_id_2, similarity_score)
    """
    if clusters_file:
        clusters = load_clusters(clusters_file)
    else:
        clusters = load_clusters()
    
    active_clusters = get_active_clusters(clusters)
    centroids = get_cluster_centroids(active_clusters, active_only=True)
    
    similar_pairs = []
    cluster_ids = list(centroids.keys())
    
    # Compare all pairs
    for i, cluster_id1 in enumerate(cluster_ids):
        for cluster_id2 in cluster_ids[i+1:]:
            try:
                similarity = cosine_similarity(
                    centroids[cluster_id1],
                    centroids[cluster_id2]
                )
                if similarity >= similarity_threshold:
                    similar_pairs.append((cluster_id1, cluster_id2, similarity))
            except Exception as e:
                print(f"[CLUSTER_MAINTENANCE] Error comparing clusters {cluster_id1} and {cluster_id2}: {e}")
                continue
    
    # Sort by similarity (descending)
    similar_pairs.sort(key=lambda x: x[2], reverse=True)
    
    return similar_pairs


def merge_clusters(
    cluster_id_1: str,
    cluster_id_2: str,
    clusters_file: Optional[Path] = None,
    keep_cluster_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Merge two clusters into one.
    
    Parameters
    ----------
    cluster_id_1 : str
        ID of first cluster to merge.
    cluster_id_2 : str
        ID of second cluster to merge.
    clusters_file : Optional[Path]
        Path to clusters file (uses default if None).
    keep_cluster_id : Optional[str]
        Which cluster ID to keep (defaults to cluster_id_1).
    
    Returns
    -------
    Dict[str, Any]
        Merged cluster document.
    """
    if clusters_file:
        clusters = load_clusters(clusters_file)
    else:
        clusters = load_clusters()
    
    if cluster_id_1 not in clusters or cluster_id_2 not in clusters:
        raise ValueError(f"One or both clusters not found: {cluster_id_1}, {cluster_id_2}")
    
    cluster1 = clusters[cluster_id_1]
    cluster2 = clusters[cluster_id_2]
    
    # Determine which cluster to keep
    if keep_cluster_id is None:
        keep_cluster_id = cluster_id_1
    
    if keep_cluster_id == cluster_id_1:
        base_cluster = cluster1
        merge_cluster = cluster2
    else:
        base_cluster = cluster2
        merge_cluster = cluster1
    
    # Merge article IDs (avoid duplicates)
    merged_article_ids = list(set(base_cluster["article_ids"] + merge_cluster["article_ids"]))
    
    # Calculate merged centroid (weighted average)
    centroid1 = np.array(base_cluster["centroid_embedding"], dtype=np.float32)
    centroid2 = np.array(merge_cluster["centroid_embedding"], dtype=np.float32)
    count1 = base_cluster["article_count"]
    count2 = merge_cluster["article_count"]
    total_count = count1 + count2
    
    merged_centroid = (centroid1 * count1 + centroid2 * count2) / total_count
    
    # Normalize
    norm = np.linalg.norm(merged_centroid)
    if norm > 0:
        merged_centroid = merged_centroid / norm
    
    # Merge metadata (prefer non-empty values)
    merged_summary = base_cluster.get("cluster_summary") or merge_cluster.get("cluster_summary") or ""
    merged_topic_label = base_cluster.get("topic_label") or merge_cluster.get("topic_label")
    merged_category = base_cluster.get("category") or merge_cluster.get("category")
    
    # Merge keywords (combine lists, remove duplicates)
    keywords1 = base_cluster.get("keywords", {})
    keywords2 = merge_cluster.get("keywords", {})
    merged_keywords = {
        "lda": list(set(keywords1.get("lda", []) + keywords2.get("lda", []))),
        "tfidf": list(set(keywords1.get("tfidf", []) + keywords2.get("tfidf", []))),
    }
    
    # Update base cluster
    updated_cluster = update_cluster(
        base_cluster,
        new_article_ids=merged_article_ids,
        new_centroid_embedding=merged_centroid,
        cluster_summary=merged_summary,
        topic_label=merged_topic_label,
        category=merged_category,
        keywords=merged_keywords,
    )
    
    # Track parent clusters
    parent_ids = []
    if base_cluster.get("parent_cluster_ids"):
        parent_ids.extend(base_cluster["parent_cluster_ids"])
    else:
        parent_ids.append(cluster_id_1)
    
    if merge_cluster.get("parent_cluster_ids"):
        parent_ids.extend(merge_cluster["parent_cluster_ids"])
    else:
        parent_ids.append(cluster_id_2)
    
    updated_cluster["parent_cluster_ids"] = list(set(parent_ids))
    
    # Archive the merged cluster
    if keep_cluster_id == cluster_id_1:
        archive_cluster(cluster2)
        clusters.pop(cluster_id_2)
    else:
        archive_cluster(cluster1)
        clusters.pop(cluster_id_1)
    
    # Save updated clusters
    clusters[keep_cluster_id] = updated_cluster
    save_clusters(clusters, clusters_file)
    
    return updated_cluster


def archive_stale_clusters(
    days_inactive: int = 30,
    clusters_file: Optional[Path] = None,
) -> List[str]:
    """
    Archive clusters that haven't been updated in N days.
    
    Parameters
    ----------
    days_inactive : int, default 30
        Number of days of inactivity before archiving.
    clusters_file : Optional[Path]
        Path to clusters file (uses default if None).
    
    Returns
    -------
    List[str]
        List of archived cluster IDs.
    """
    if clusters_file:
        clusters = load_clusters(clusters_file)
    else:
        clusters = load_clusters()
    
    active_clusters = get_active_clusters(clusters)
    cutoff_date = datetime.utcnow() - timedelta(days=days_inactive)
    
    archived_ids = []
    
    for cluster_id, cluster in active_clusters.items():
        last_updated_str = cluster.get("last_updated") or cluster.get("created_at")
        if not last_updated_str:
            continue
        
        try:
            last_updated = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
            if last_updated.replace(tzinfo=None) < cutoff_date:
                archive_cluster(cluster)
                clusters.pop(cluster_id)
                archived_ids.append(cluster_id)
        except Exception as e:
            print(f"[CLUSTER_MAINTENANCE] Error parsing date for cluster {cluster_id}: {e}")
            continue
    
    # Save updated clusters
    if archived_ids:
        save_clusters(clusters, clusters_file)
    
    return archived_ids


def cleanup_duplicate_clusters(
    similarity_threshold: float = 0.95,
    clusters_file: Optional[Path] = None,
) -> List[Tuple[str, str]]:
    """
    Find and optionally merge duplicate clusters (very high similarity).
    
    Parameters
    ----------
    similarity_threshold : float, default 0.95
        Very high similarity threshold for duplicates.
    clusters_file : Optional[Path]
        Path to clusters file (uses default if None).
    
    Returns
    -------
    List[Tuple[str, str]]
        List of duplicate pairs found (cluster_id_1, cluster_id_2).
    """
    similar_pairs = find_similar_clusters(
        similarity_threshold=similarity_threshold,
        clusters_file=clusters_file,
    )
    
    # Merge duplicates (keep the one with more articles)
    merged_pairs = []
    
    for cluster_id_1, cluster_id_2, similarity in similar_pairs:
        try:
            if clusters_file:
                clusters = load_clusters(clusters_file)
            else:
                clusters = load_clusters()
            
            cluster1 = clusters[cluster_id_1]
            cluster2 = clusters[cluster_id_2]
            
            # Keep the cluster with more articles
            keep_id = cluster_id_1 if cluster1["article_count"] >= cluster2["article_count"] else cluster_id_2
            
            merge_clusters(cluster_id_1, cluster_id_2, clusters_file=clusters_file, keep_cluster_id=keep_id)
            merged_pairs.append((cluster_id_1, cluster_id_2))
        except Exception as e:
            print(f"[CLUSTER_MAINTENANCE] Error merging duplicates {cluster_id_1} and {cluster_id_2}: {e}")
            continue
    
    return merged_pairs
