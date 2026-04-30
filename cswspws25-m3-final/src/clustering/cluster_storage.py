"""
cluster_storage.py
==================

Cluster storage layer for persistent cluster management.

Purpose
-------
This module provides functions to store, load, and manage clusters persistently.
Enables incremental clustering by allowing new articles to be matched to existing clusters.

Storage Format
--------------
- JSON-based storage (can be migrated to database later)
- Stores clusters with centroids, metadata, and article assignments
- Supports versioning and archiving

Design Notes
------------
- Uses UUIDs for cluster IDs to avoid conflicts
- Stores centroid embeddings for fast similarity matching
- Tracks metadata (created_at, last_updated, etc.)
- Supports archiving stale clusters
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from threading import Lock

# Thread-safe file operations
_file_lock = Lock()

# Default storage paths
DEFAULT_STORAGE_DIR = Path(__file__).parent.parent.parent / "data" / "clusters"
DEFAULT_CLUSTERS_FILE = DEFAULT_STORAGE_DIR / "clusters.json"
DEFAULT_ARCHIVE_FILE = DEFAULT_STORAGE_DIR / "clusters_archive.json"
DEFAULT_INDEX_FILE = DEFAULT_STORAGE_DIR / "index.json"


def ensure_storage_dir(storage_dir: Path = DEFAULT_STORAGE_DIR) -> None:
    """Ensure storage directory exists."""
    storage_dir.mkdir(parents=True, exist_ok=True)


def generate_cluster_id() -> str:
    """Generate a unique cluster ID (UUID v4)."""
    return str(uuid.uuid4())


def serialize_embedding(embedding: np.ndarray) -> List[float]:
    """Convert numpy array to list for JSON serialization."""
    if isinstance(embedding, np.ndarray):
        return embedding.tolist()
    return list(embedding)


def deserialize_embedding(embedding_list: List[float]) -> np.ndarray:
    """Convert list to numpy array."""
    return np.array(embedding_list, dtype=np.float32)


def load_clusters(
    clusters_file: Path = DEFAULT_CLUSTERS_FILE,
) -> Dict[str, Dict[str, Any]]:
    """
    Load all clusters from storage.
    
    Parameters
    ----------
    clusters_file : Path
        Path to clusters JSON file.
    
    Returns
    -------
    Dict[str, Dict[str, Any]]
        Dictionary mapping cluster_id -> cluster data.
    """
    ensure_storage_dir(clusters_file.parent)
    
    if not clusters_file.exists():
        return {}
    
    with _file_lock:
        try:
            with open(clusters_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Handle both list and dict formats
                if isinstance(data, list):
                    return {cluster["cluster_id"]: cluster for cluster in data}
                return data
        except (json.JSONDecodeError, IOError) as e:
            print(f"[CLUSTER_STORAGE] Error loading clusters: {e}")
            return {}


def save_clusters(
    clusters: Dict[str, Dict[str, Any]],
    clusters_file: Optional[Path] = None,
    backup: bool = True,
) -> None:
    """
    Save clusters to storage.
    
    Parameters
    ----------
    clusters : Dict[str, Dict[str, Any]]
        Dictionary mapping cluster_id -> cluster data.
    clusters_file : Optional[Path]
        Path to clusters JSON file. Uses default if None.
    backup : bool
        Whether to create a backup before saving.
    """
    if clusters_file is None:
        clusters_file = DEFAULT_CLUSTERS_FILE
    ensure_storage_dir(clusters_file.parent)
    
    # Create backup if requested
    if backup and clusters_file.exists():
        backup_file = clusters_file.parent / f"{clusters_file.stem}_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            import shutil
            shutil.copy2(clusters_file, backup_file)
            # Keep only last 5 backups
            backups = sorted(clusters_file.parent.glob(f"{clusters_file.stem}_backup_*.json"))
            for old_backup in backups[:-5]:
                try:
                    old_backup.unlink()
                except (OSError, PermissionError) as unlink_error:
                    print(f"[CLUSTER_STORAGE] Warning: Could not delete backup {old_backup}: {unlink_error}")
        except Exception as e:
            print(f"[CLUSTER_STORAGE] Warning: Could not create backup: {e}")
    
    with _file_lock:
        try:
            # Convert to list format for easier reading
            clusters_list = list(clusters.values())
            with open(clusters_file, "w", encoding="utf-8") as f:
                json.dump(clusters_list, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[CLUSTER_STORAGE] Error saving clusters: {e}")
            raise


def create_cluster(
    article_ids: List[str],
    centroid_embedding: np.ndarray,
    cluster_summary: Optional[str] = None,
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    representative_article_ids: Optional[List[str]] = None,
    topic_label: Optional[str] = None,
    category: Optional[str] = None,
    keywords: Optional[Dict[str, List[str]]] = None,
    is_noise: bool = False,
    clustering_method: str = "incremental",
) -> Dict[str, Any]:
    """
    Create a new cluster document.
    
    Parameters
    ----------
    article_ids : List[str]
        Article IDs in this cluster.
    centroid_embedding : np.ndarray
        Cluster centroid embedding (average of article embeddings).
    cluster_summary : Optional[str]
        Cluster summary text.
    embedding_model : str
        Name of embedding model used.
    representative_article_ids : Optional[List[str]]
        Top representative article IDs.
    topic_label : Optional[str]
        Topic label for the cluster.
    category : Optional[str]
        Category label for the cluster.
    keywords : Optional[Dict[str, List[str]]]
        Keywords (LDA and/or TF-IDF).
    is_noise : bool
        Whether this is a noise cluster.
    clustering_method : str
        Clustering method used.
    
    Returns
    -------
    Dict[str, Any]
        Cluster document.
    """
    cluster_id = generate_cluster_id()
    now = datetime.utcnow().isoformat()
    
    # Determine representative articles
    if representative_article_ids is None:
        representative_article_ids = article_ids[:min(5, len(article_ids))]
    
    cluster = {
        "cluster_id": cluster_id,
        "centroid_embedding": serialize_embedding(centroid_embedding),
        "embedding_model": embedding_model,
        "embedding_dim": len(centroid_embedding),
        "article_ids": article_ids,
        "article_count": len(article_ids),
        "representative_article_ids": representative_article_ids,
        "cluster_summary": cluster_summary or "",
        "topic_label": topic_label,
        "category": category,
        "subcategory": topic_label,  # Use topic_label as subcategory
        "keywords": keywords or {"lda": [], "tfidf": []},
        "created_at": now,
        "last_updated": now,
        "last_article_added_at": now,
        "status": "active",
        "is_noise": is_noise,
        "clustering_method": clustering_method,
        "min_cluster_size": 2,
        "version": 1,
        "parent_cluster_ids": None,
        "total_articles_ever": len(article_ids),
        "match_count": 0,
    }
    
    return cluster


def update_cluster(
    cluster: Dict[str, Any],
    new_article_ids: Optional[List[str]] = None,
    new_centroid_embedding: Optional[np.ndarray] = None,
    cluster_summary: Optional[str] = None,
    topic_label: Optional[str] = None,
    category: Optional[str] = None,
    keywords: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """
    Update an existing cluster.
    
    Parameters
    ----------
    cluster : Dict[str, Any]
        Existing cluster document.
    new_article_ids : Optional[List[str]]
        New article IDs to add (will be merged with existing).
    new_centroid_embedding : Optional[np.ndarray]
        Updated centroid embedding.
    cluster_summary : Optional[str]
        Updated cluster summary.
    topic_label : Optional[str]
        Updated topic label.
    category : Optional[str]
        Updated category.
    keywords : Optional[Dict[str, List[str]]]
        Updated keywords.
    
    Returns
    -------
    Dict[str, Any]
        Updated cluster document.
    """
    cluster = cluster.copy()
    cluster["version"] += 1
    cluster["last_updated"] = datetime.utcnow().isoformat()
    
    # Update article IDs
    if new_article_ids:
        existing_ids = set(cluster["article_ids"])
        new_ids = [aid for aid in new_article_ids if aid not in existing_ids]
        cluster["article_ids"].extend(new_ids)
        cluster["article_count"] = len(cluster["article_ids"])
        cluster["total_articles_ever"] += len(new_ids)
        cluster["last_article_added_at"] = datetime.utcnow().isoformat()
        
        # Update representative articles if needed
        if len(new_ids) > 0:
            # Keep top 5 most representative (simple: first 5)
            cluster["representative_article_ids"] = cluster["article_ids"][:5]
    
    # Update centroid
    if new_centroid_embedding is not None:
        cluster["centroid_embedding"] = serialize_embedding(new_centroid_embedding)
    
    # Update summary and labels
    if cluster_summary is not None:
        cluster["cluster_summary"] = cluster_summary
    if topic_label is not None:
        cluster["topic_label"] = topic_label
        cluster["subcategory"] = topic_label
    if category is not None:
        cluster["category"] = category
    if keywords is not None:
        cluster["keywords"] = keywords
    
    return cluster


def get_active_clusters(
    clusters: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Get only active clusters from local JSON file storage.
    
    ⚠️ MAINTENANCE ONLY: This function is used for backend maintenance operations
    on local JSON file storage (data/clusters/clusters.json). It is NOT part of the
    n8n/OpenSearch workflow, which handles cluster filtering directly in OpenSearch
    queries using status-based filters.
    
    Used by:
    - /cluster_stats endpoint for reporting statistics
    - /cluster_maintenance endpoint for finding/merging/archiving clusters
    - scheduled_maintenance.py for maintenance scripts
    
    Returns
    -------
    Dict[str, Dict[str, Any]]
        Dictionary of active clusters filtered by status == "active"
    """
    return {
        cluster_id: cluster
        for cluster_id, cluster in clusters.items()
        if cluster.get("status") == "active"
    }


def archive_cluster(
    cluster: Dict[str, Any],
    archive_file: Path = DEFAULT_ARCHIVE_FILE,
) -> None:
    """
    Archive a cluster (move to archive file).
    
    Parameters
    ----------
    cluster : Dict[str, Any]
        Cluster to archive.
    archive_file : Path
        Path to archive file.
    """
    ensure_storage_dir(archive_file.parent)
    
    # Load existing archive
    archived_clusters = []
    if archive_file.exists():
        try:
            with open(archive_file, "r", encoding="utf-8") as f:
                archived_clusters = json.load(f)
                if not isinstance(archived_clusters, list):
                    archived_clusters = []
        except (json.JSONDecodeError, IOError):
            archived_clusters = []
    
    # Update cluster status
    cluster = cluster.copy()
    cluster["status"] = "archived"
    cluster["last_updated"] = datetime.utcnow().isoformat()
    
    # Add to archive
    archived_clusters.append(cluster)
    
    # Save archive
    with _file_lock:
        try:
            with open(archive_file, "w", encoding="utf-8") as f:
                json.dump(archived_clusters, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[CLUSTER_STORAGE] Error archiving cluster: {e}")
            raise


def get_cluster_centroids(
    clusters: Dict[str, Dict[str, Any]],
    active_only: bool = True,
) -> Dict[str, np.ndarray]:
    """
    Extract cluster centroids for matching.
    
    Parameters
    ----------
    clusters : Dict[str, Dict[str, Any]]
        All clusters.
    active_only : bool
        Whether to include only active clusters.
    
    Returns
    -------
    Dict[str, np.ndarray]
        Dictionary mapping cluster_id -> centroid embedding.
    """
    target_clusters = get_active_clusters(clusters) if active_only else clusters
    
    centroids = {}
    for cluster_id, cluster in target_clusters.items():
        centroid_list = cluster.get("centroid_embedding")
        if centroid_list:
            centroids[cluster_id] = deserialize_embedding(centroid_list)
    
    return centroids


def update_index(
    clusters: Dict[str, Dict[str, Any]],
    index_file: Path = DEFAULT_INDEX_FILE,
) -> None:
    """
    Update the cluster index for fast lookups.
    
    Parameters
    ----------
    clusters : Dict[str, Dict[str, Any]]
        All clusters.
    index_file : Path
        Path to index file.
    """
    ensure_storage_dir(index_file.parent)
    
    active_clusters = get_active_clusters(clusters)
    
    # Build index by status
    clusters_by_status = {
        "active": [cid for cid, c in clusters.items() if c.get("status") == "active"],
        "archived": [cid for cid, c in clusters.items() if c.get("status") == "archived"],
    }
    
    # Build index by category
    clusters_by_category: Dict[str, List[str]] = {}
    for cluster_id, cluster in active_clusters.items():
        category = cluster.get("category")
        if category:
            clusters_by_category.setdefault(category, []).append(cluster_id)
    
    index = {
        "clusters_by_status": clusters_by_status,
        "clusters_by_category": clusters_by_category,
        "last_updated": datetime.utcnow().isoformat(),
        "total_clusters": len(clusters),
        "active_clusters": len(active_clusters),
        "archived_clusters": len(clusters_by_status.get("archived", [])),
    }
    
    with _file_lock:
        try:
            with open(index_file, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[CLUSTER_STORAGE] Error updating index: {e}")
