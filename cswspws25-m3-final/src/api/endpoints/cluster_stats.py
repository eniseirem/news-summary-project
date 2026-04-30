"""
cluster_stats.py
=================

Cluster statistics endpoint for monitoring cluster health and status.

Purpose
-------
This endpoint provides statistics and insights about stored clusters:
- Total clusters (active, archived)
- Cluster size distribution
- Category distribution
- Recent activity
- Storage metrics

Design Notes
------------
- Read-only endpoint (no modifications)
- Fast queries using index when available
"""

from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from clustering.cluster_storage import load_clusters, get_active_clusters


class ClusterSizeDistribution(BaseModel):
    """Cluster size distribution statistics."""
    size_range: str  # e.g., "1-5", "6-10", "11-20", "21+"
    count: int
    total_articles: int


class CategoryStats(BaseModel):
    """Category statistics."""
    category: str
    cluster_count: int
    total_articles: int
    avg_cluster_size: float


class ClusterStatsResponse(BaseModel):
    """Response model for cluster statistics."""
    request_id: str
    total_clusters: int
    active_clusters: int
    archived_clusters: int
    total_articles: int
    avg_cluster_size: float
    size_distribution: List[ClusterSizeDistribution]
    category_distribution: List[CategoryStats]
    recent_activity: Dict[str, Any]  # Clusters created/updated in last 7 days
    storage_info: Dict[str, Any]  # Storage metadata
    processed_at: str


router = APIRouter(tags=["clustering", "statistics"])


@router.get("/cluster_stats", response_model=ClusterStatsResponse)
def cluster_stats_endpoint(request_id: str = "stats_request"):
    """
    Get statistics about stored clusters.

    Statistics Provided
    -------------------
    - Total clusters (active, archived)
    - Total articles across all clusters
    - Average cluster size
    - Size distribution (buckets)
    - Category distribution
    - Recent activity (last 7 days)
    - Storage metadata

    Use Cases
    ---------
    - Monitoring cluster health
    - Understanding cluster distribution
    - Planning maintenance operations
    - Performance monitoring

    Parameters
    ----------
    request_id : str
        Optional request ID for tracking.

    Returns
    -------
    ClusterStatsResponse
        Comprehensive cluster statistics.
    """
    
    try:
        # Load all clusters
        all_clusters = load_clusters()
        active_clusters = get_active_clusters(all_clusters)
        
        # Basic counts
        total_clusters = len(all_clusters)
        active_count = len(active_clusters)
        archived_count = total_clusters - active_count
        
        # Calculate total articles
        total_articles = sum(
            cluster.get("article_count", 0)
            for cluster in active_clusters.values()
        )
        
        # Average cluster size
        avg_cluster_size = total_articles / active_count if active_count > 0 else 0.0
        
        # Size distribution
        size_ranges = {
            "1-5": (1, 5),
            "6-10": (6, 10),
            "11-20": (11, 20),
            "21+": (21, float('inf')),
        }
        
        size_distribution = []
        for range_name, (min_size, max_size) in size_ranges.items():
            matching_clusters = [
                c for c in active_clusters.values()
                if min_size <= c.get("article_count", 0) <= max_size
            ]
            total_in_range = sum(c.get("article_count", 0) for c in matching_clusters)
            size_distribution.append(ClusterSizeDistribution(
                size_range=range_name,
                count=len(matching_clusters),
                total_articles=total_in_range,
            ))
        
        # Category distribution
        category_stats: Dict[str, Dict[str, Any]] = {}
        for cluster in active_clusters.values():
            category = cluster.get("category") or "Uncategorized"
            if category not in category_stats:
                category_stats[category] = {
                    "cluster_count": 0,
                    "total_articles": 0,
                }
            category_stats[category]["cluster_count"] += 1
            category_stats[category]["total_articles"] += cluster.get("article_count", 0)
        
        category_distribution = [
            CategoryStats(
                category=cat,
                cluster_count=stats["cluster_count"],
                total_articles=stats["total_articles"],
                avg_cluster_size=stats["total_articles"] / stats["cluster_count"] if stats["cluster_count"] > 0 else 0.0,
            )
            for cat, stats in sorted(category_stats.items())
        ]
        
        # Recent activity (last 7 days)
        seven_days_ago = datetime.utcnow().timestamp() - (7 * 24 * 60 * 60)
        recent_created = 0
        recent_updated = 0
        
        for cluster in active_clusters.values():
            created_at = cluster.get("created_at", "")
            last_updated = cluster.get("last_updated", "")
            
            try:
                if created_at:
                    created_ts = datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
                    if created_ts >= seven_days_ago:
                        recent_created += 1
                
                if last_updated:
                    updated_ts = datetime.fromisoformat(last_updated.replace("Z", "+00:00")).timestamp()
                    if updated_ts >= seven_days_ago:
                        recent_updated += 1
            except Exception:
                continue
        
        recent_activity = {
            "clusters_created_last_7_days": recent_created,
            "clusters_updated_last_7_days": recent_updated,
        }
        
        # Storage info
        storage_info = {
            "storage_type": "json",  # Will be "postgresql" when migrated
            "total_clusters": total_clusters,
            "index_available": True,  # Index file exists
        }
        
        return ClusterStatsResponse(
            request_id=request_id,
            total_clusters=total_clusters,
            active_clusters=active_count,
            archived_clusters=archived_count,
            total_articles=total_articles,
            avg_cluster_size=round(avg_cluster_size, 2),
            size_distribution=size_distribution,
            category_distribution=category_distribution,
            recent_activity=recent_activity,
            storage_info=storage_info,
            processed_at=datetime.utcnow().isoformat(),
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate cluster statistics: {str(e)}"
        )
