"""
incremental_clustering.py
==========================

Incremental clustering functions for matching new articles to existing clusters.

Purpose
-------
This module provides functions to match new articles to existing clusters,
enabling incremental clustering instead of re-clustering from scratch.

Design Notes
------------
- Uses cosine similarity for matching
- Supports threshold-based assignment
- Returns top-k candidates for review
- Handles centroid updates when articles are added
"""

import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from clustering.cluster_storage import (
    load_clusters,
    get_cluster_centroids,
    get_active_clusters,
    update_cluster,
    save_clusters,
)


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Parameters
    ----------
    vec1 : np.ndarray
        First vector.
    vec2 : np.ndarray
        Second vector.
    
    Returns
    -------
    float
        Cosine similarity score between -1 and 1.
    """
    if vec1.shape != vec2.shape:
        raise ValueError(f"Vectors must have same shape: {vec1.shape} vs {vec2.shape}")
    
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))


def match_to_existing_clusters(
    article_embedding: np.ndarray,
    similarity_threshold: float = 0.7,
    top_k: int = 5,
    clusters_file: Optional[Path] = None,
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """
    Match a new article embedding to existing clusters from local JSON file storage.
    
    ⚠️ MAINTENANCE ONLY: This function operates on local JSON file storage
    (data/clusters/clusters.json) and is NOT part of the n8n/OpenSearch workflow.
    n8n handles article-to-cluster matching directly in OpenSearch using k-NN queries
    with status-based filtering. This function is only used by cluster_articles_incremental(),
    which itself is not called by the active n8n workflow.
    
    Used by:
    - cluster_articles_incremental() (legacy function, not used in n8n workflow)
    
    Parameters
    ----------
    article_embedding : np.ndarray
        Embedding vector of the new article.
    similarity_threshold : float, default 0.7
        Minimum similarity score to assign article to cluster.
    top_k : int, default 5
        Number of top candidates to return.
    clusters_file : Optional[Path]
        Path to clusters file (uses default if None).
    
    Returns
    -------
    Tuple[Optional[str], List[Dict[str, Any]]]
        Tuple of:
        - Best matching cluster_id (None if no match above threshold)
        - List of top-k candidates with similarity scores
    """
    from clustering.cluster_storage import DEFAULT_CLUSTERS_FILE
    
    # Load clusters
    if clusters_file:
        clusters = load_clusters(clusters_file)
    else:
        clusters = load_clusters()
    
    # Get only active clusters
    active_clusters = get_active_clusters(clusters)
    
    if not active_clusters:
        return None, []
    
    # Get centroids
    centroids = get_cluster_centroids(active_clusters, active_only=True)
    
    if not centroids:
        return None, []
    
    # Calculate similarities
    similarities = []
    for cluster_id, centroid in centroids.items():
        try:
            similarity = cosine_similarity(article_embedding, centroid)
            similarities.append({
                "cluster_id": cluster_id,
                "similarity": similarity,
                "cluster": active_clusters[cluster_id],
            })
        except Exception as e:
            print(f"[INCREMENTAL_CLUSTERING] Error calculating similarity for cluster {cluster_id}: {e}")
            continue
    
    # Sort by similarity (descending)
    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    
    # Get top-k candidates
    candidates = similarities[:top_k]
    
    # Check if best match exceeds threshold
    best_match_id = None
    if candidates and candidates[0]["similarity"] >= similarity_threshold:
        best_match_id = candidates[0]["cluster_id"]
    
    return best_match_id, candidates


def add_article_to_cluster(
    cluster_id: str,
    article_id: str,
    article_embedding: np.ndarray,
    clusters_file: Optional[Path] = None,
    update_summary: bool = False,
) -> Dict[str, Any]:
    """
    Add an article to an existing cluster and update the centroid.
    
    Parameters
    ----------
    cluster_id : str
        ID of the cluster to add article to.
    article_id : str
        ID of the article to add.
    article_embedding : np.ndarray
        Embedding vector of the article.
    clusters_file : Optional[Path]
        Path to clusters file (uses default if None).
    update_summary : bool
        Whether to trigger summary update (requires external call).
    
    Returns
    -------
    Dict[str, Any]
        Updated cluster document.
    """
    from clustering.cluster_storage import DEFAULT_CLUSTERS_FILE
    
    # Load clusters
    if clusters_file:
        clusters = load_clusters(clusters_file)
    else:
        clusters = load_clusters()
    
    if cluster_id not in clusters:
        raise ValueError(f"Cluster {cluster_id} not found")
    
    cluster = clusters[cluster_id]
    
    # Check if article already in cluster
    if article_id in cluster["article_ids"]:
        print(f"[INCREMENTAL_CLUSTERING] Article {article_id} already in cluster {cluster_id}")
        return cluster
    
    # Calculate new centroid (running average)
    current_centroid = np.array(cluster["centroid_embedding"], dtype=np.float32)
    current_count = cluster["article_count"]
    
    # New centroid = (old_centroid * old_count + new_embedding) / (old_count + 1)
    new_centroid = (current_centroid * current_count + article_embedding) / (current_count + 1)
    
    # Normalize the centroid (maintain unit vector for cosine similarity)
    norm = np.linalg.norm(new_centroid)
    if norm > 0:
        new_centroid = new_centroid / norm
    
    # Update cluster
    updated_cluster = update_cluster(
        cluster,
        new_article_ids=[article_id],
        new_centroid_embedding=new_centroid,
    )
    
    # Increment match count
    updated_cluster["match_count"] = updated_cluster.get("match_count", 0) + 1
    
    # Save updated clusters
    clusters[cluster_id] = updated_cluster
    save_clusters(clusters, clusters_file)
    
    return updated_cluster


def create_new_cluster_from_articles(
    article_ids: List[str],
    article_embeddings: Dict[str, np.ndarray],
    cluster_summary: Optional[str] = None,
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    topic_label: Optional[str] = None,
    category: Optional[str] = None,
    keywords: Optional[Dict[str, List[str]]] = None,
    clusters_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Create a new cluster from a list of articles.
    
    Parameters
    ----------
    article_ids : List[str]
        Article IDs to include in the cluster.
    article_embeddings : Dict[str, np.ndarray]
        Dictionary mapping article_id -> embedding.
    cluster_summary : Optional[str]
        Cluster summary (if available).
    embedding_model : str
        Name of embedding model used.
    topic_label : Optional[str]
        Topic label for the cluster.
    category : Optional[str]
        Category label for the cluster.
    keywords : Optional[Dict[str, List[str]]]
        Keywords for the cluster.
    clusters_file : Optional[Path]
        Path to clusters file (uses default if None).
    
    Returns
    -------
    Dict[str, Any]
        Created cluster document.
    """
    from clustering.cluster_storage import (
        create_cluster,
        save_clusters,
        load_clusters,
        DEFAULT_CLUSTERS_FILE,
    )
    
    # Calculate centroid (average of all article embeddings)
    embeddings_list = [article_embeddings[aid] for aid in article_ids if aid in article_embeddings]
    
    if not embeddings_list:
        raise ValueError("No valid embeddings provided for articles")
    
    centroid = np.mean(embeddings_list, axis=0)
    
    # Normalize centroid
    norm = np.linalg.norm(centroid)
    if norm > 0:
        centroid = centroid / norm
    
    # Create cluster
    cluster = create_cluster(
        article_ids=article_ids,
        centroid_embedding=centroid,
        cluster_summary=cluster_summary,
        embedding_model=embedding_model,
        representative_article_ids=article_ids[:min(5, len(article_ids))],
        topic_label=topic_label,
        category=category,
        keywords=keywords,
        clustering_method="incremental",
    )
    
    # Save cluster
    if clusters_file:
        clusters = load_clusters(clusters_file)
    else:
        clusters = load_clusters()
    
    clusters[cluster["cluster_id"]] = cluster
    save_clusters(clusters, clusters_file)
    
    return cluster
