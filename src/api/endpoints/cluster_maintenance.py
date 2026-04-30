"""
cluster_maintenance.py
======================

Cluster maintenance endpoint for merging and archiving clusters.

Purpose
-------
This endpoint provides cluster maintenance operations:
- Merge similar clusters
- Archive stale clusters
- Cleanup duplicate clusters

Design Notes
------------
- Can be called manually or scheduled (cron job)
- Safe operations (creates backups before major changes)
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from clustering.cluster_maintenance import (
    find_similar_clusters,
    merge_clusters,
    archive_stale_clusters,
    cleanup_duplicate_clusters,
)


class MaintenanceRequest(BaseModel):
    """Request model for cluster maintenance."""
    request_id: str
    operation: str  # "merge", "archive", "cleanup", or "all"
    similarity_threshold: float = 0.85  # For merge/cleanup operations
    days_inactive: int = 30  # For archive operation


class MergeResult(BaseModel):
    """Result of merge operation."""
    cluster_id_1: str
    cluster_id_2: str
    similarity: float
    merged_cluster_id: str
    merged_article_count: int


class ArchiveResult(BaseModel):
    """Result of archive operation."""
    archived_cluster_ids: List[str]
    total_archived: int


class MaintenanceResponse(BaseModel):
    """Response model for maintenance operations."""
    request_id: str
    operation: str
    merges: Optional[List[MergeResult]] = None
    archived: Optional[ArchiveResult] = None
    duplicates_merged: Optional[List[tuple]] = None
    processed_at: str


router = APIRouter(tags=["clustering", "maintenance"])


@router.post("/cluster_maintenance", response_model=MaintenanceResponse)
def cluster_maintenance_endpoint(payload: MaintenanceRequest):
    """
    Perform cluster maintenance operations.

    Operations
    ----------
    - "merge": Merge similar clusters (similarity >= threshold)
    - "archive": Archive clusters inactive for N days
    - "cleanup": Merge duplicate clusters (very high similarity)
    - "all": Perform all operations

    Processing Steps
    ----------------
    1. Find similar/duplicate clusters (if merge/cleanup)
    2. Merge clusters (if merge/cleanup)
    3. Archive stale clusters (if archive)
    4. Return results

    Safety
    ------
    - Creates backups before major changes
    - Archives clusters instead of deleting
    - Tracks parent clusters for merged clusters

    Constraints
    -----------
    - Similarity threshold between 0.0 and 1.0
    - Days inactive must be positive
    - Operation must be one of: merge, archive, cleanup, all

    Parameters
    ----------
    payload : MaintenanceRequest
        Request containing operation type and parameters.

    Returns
    -------
    MaintenanceResponse
        Results of maintenance operations.
    """
    
    # Validate input
    valid_operations = ["merge", "archive", "cleanup", "all"]
    if payload.operation not in valid_operations:
        raise HTTPException(
            status_code=400,
            detail=f"operation must be one of: {', '.join(valid_operations)}"
        )
    
    if not 0.0 <= payload.similarity_threshold <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="similarity_threshold must be between 0.0 and 1.0"
        )
    
    if payload.days_inactive < 1:
        raise HTTPException(
            status_code=400,
            detail="days_inactive must be at least 1"
        )
    
    merges = None
    archived = None
    duplicates_merged = None
    
    # Perform merge operation
    if payload.operation in ["merge", "all"]:
        try:
            similar_pairs = find_similar_clusters(
                similarity_threshold=payload.similarity_threshold,
            )
            
            merge_results = []
            for cluster_id_1, cluster_id_2, similarity in similar_pairs:
                try:
                    # Load clusters to get article counts
                    from clustering.cluster_storage import load_clusters
                    clusters = load_clusters()
                    cluster1 = clusters.get(cluster_id_1, {})
                    cluster2 = clusters.get(cluster_id_2, {})
                    
                    # Merge (keep cluster with more articles)
                    keep_id = cluster_id_1 if cluster1.get("article_count", 0) >= cluster2.get("article_count", 0) else cluster_id_2
                    merged_cluster = merge_clusters(
                        cluster_id_1,
                        cluster_id_2,
                        keep_cluster_id=keep_id,
                    )
                    
                    merge_results.append(MergeResult(
                        cluster_id_1=cluster_id_1,
                        cluster_id_2=cluster_id_2,
                        similarity=similarity,
                        merged_cluster_id=keep_id,
                        merged_article_count=merged_cluster.get("article_count", 0),
                    ))
                except Exception as e:
                    print(f"[MAINTENANCE] Error merging clusters {cluster_id_1} and {cluster_id_2}: {e}")
                    continue
            
            merges = merge_results
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Merge operation failed: {str(e)}"
            )
    
    # Perform archive operation
    if payload.operation in ["archive", "all"]:
        try:
            archived_ids = archive_stale_clusters(
                days_inactive=payload.days_inactive,
            )
            archived = ArchiveResult(
                archived_cluster_ids=archived_ids,
                total_archived=len(archived_ids),
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Archive operation failed: {str(e)}"
            )
    
    # Perform cleanup operation
    if payload.operation in ["cleanup", "all"]:
        try:
            # Use very high threshold for duplicates
            duplicate_threshold = max(payload.similarity_threshold, 0.95)
            merged_pairs = cleanup_duplicate_clusters(
                similarity_threshold=duplicate_threshold,
            )
            duplicates_merged = [(pair[0], pair[1]) for pair in merged_pairs]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Cleanup operation failed: {str(e)}"
            )
    
    return MaintenanceResponse(
        request_id=payload.request_id,
        operation=payload.operation,
        merges=merges,
        archived=archived,
        duplicates_merged=duplicates_merged,
        processed_at=datetime.utcnow().isoformat(),
    )
