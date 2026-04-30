"""
scheduled_maintenance.py
========================

Scheduled maintenance script for cluster maintenance operations.

Purpose
-------
This script can be run as a cron job to automatically:
- Merge similar clusters
- Archive stale clusters
- Cleanup duplicate clusters

Usage
-----
Run manually:
    python -m clustering.scheduled_maintenance

Or add to crontab (daily at 2 AM):
    0 2 * * * cd /path/to/project && python -m clustering.scheduled_maintenance

Design Notes
------------
- Safe operations (creates backups)
- Logs all operations
- Can be called from cron or scheduled task runner
"""

import sys
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from clustering.cluster_maintenance import (
    find_similar_clusters,
    merge_clusters,
    archive_stale_clusters,
    cleanup_duplicate_clusters,
)
from clustering.cluster_storage import load_clusters, update_index

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('cluster_maintenance.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def run_maintenance(
    merge_threshold: float = 0.85,
    archive_days: int = 30,
    cleanup_threshold: float = 0.95,
    dry_run: bool = False,
) -> dict:
    """
    Run all maintenance operations.
    
    Parameters
    ----------
    merge_threshold : float
        Similarity threshold for merging clusters.
    archive_days : int
        Days of inactivity before archiving.
    cleanup_threshold : float
        Similarity threshold for duplicate cleanup.
    dry_run : bool
        If True, only report what would be done without making changes.
    
    Returns
    -------
    dict
        Summary of operations performed.
    """
    logger.info("=" * 60)
    logger.info("Starting cluster maintenance")
    logger.info(f"Dry run: {dry_run}")
    logger.info("=" * 60)
    
    results = {
        "started_at": datetime.utcnow().isoformat(),
        "dry_run": dry_run,
        "merges": [],
        "archived": [],
        "duplicates_merged": [],
    }
    
    # Load clusters
    clusters = load_clusters()
    active_before = len([c for c in clusters.values() if c.get("status") == "active"])
    logger.info(f"Active clusters before maintenance: {active_before}")
    
    # 1. Merge similar clusters
    logger.info("\n--- Step 1: Merging similar clusters ---")
    try:
        similar_pairs = find_similar_clusters(similarity_threshold=merge_threshold)
        logger.info(f"Found {len(similar_pairs)} similar cluster pairs")
        
        for cluster_id_1, cluster_id_2, similarity in similar_pairs:
            try:
                cluster1 = clusters.get(cluster_id_1, {})
                cluster2 = clusters.get(cluster_id_2, {})
                
                # Keep cluster with more articles
                keep_id = cluster_id_1 if cluster1.get("article_count", 0) >= cluster2.get("article_count", 0) else cluster_id_2
                
                if not dry_run:
                    merged_cluster = merge_clusters(
                        cluster_id_1,
                        cluster_id_2,
                        keep_cluster_id=keep_id,
                    )
                    logger.info(f"✓ Merged clusters {cluster_id_1} and {cluster_id_2} (similarity: {similarity:.3f}) -> {keep_id}")
                    results["merges"].append({
                        "cluster_1": cluster_id_1,
                        "cluster_2": cluster_id_2,
                        "similarity": similarity,
                        "kept": keep_id,
                    })
                else:
                    logger.info(f"[DRY RUN] Would merge clusters {cluster_id_1} and {cluster_id_2} (similarity: {similarity:.3f})")
                    results["merges"].append({
                        "cluster_1": cluster_id_1,
                        "cluster_2": cluster_id_2,
                        "similarity": similarity,
                    })
            except Exception as e:
                logger.error(f"Error merging clusters {cluster_id_1} and {cluster_id_2}: {e}")
                continue
        
        # Reload clusters after merges
        if not dry_run:
            clusters = load_clusters()
    except Exception as e:
        logger.error(f"Merge operation failed: {e}", exc_info=True)
    
    # 2. Archive stale clusters
    logger.info("\n--- Step 2: Archiving stale clusters ---")
    try:
        if not dry_run:
            archived_ids = archive_stale_clusters(days_inactive=archive_days)
            logger.info(f"✓ Archived {len(archived_ids)} stale clusters")
            results["archived"] = archived_ids
        else:
            # Count what would be archived
            cutoff_date = datetime.utcnow() - timedelta(days=archive_days)
            would_archive = []
            for cluster_id, cluster in clusters.items():
                if cluster.get("status") != "active":
                    continue
                last_updated_str = cluster.get("last_updated") or cluster.get("created_at")
                if last_updated_str:
                    try:
                        last_updated = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
                        if last_updated.replace(tzinfo=None) < cutoff_date:
                            would_archive.append(cluster_id)
                    except Exception:
                        continue
            logger.info(f"[DRY RUN] Would archive {len(would_archive)} stale clusters")
            results["archived"] = would_archive
    except Exception as e:
        logger.error(f"Archive operation failed: {e}", exc_info=True)
    
    # 3. Cleanup duplicates
    logger.info("\n--- Step 3: Cleaning up duplicate clusters ---")
    try:
        if not dry_run:
            merged_pairs = cleanup_duplicate_clusters(similarity_threshold=cleanup_threshold)
            logger.info(f"✓ Merged {len(merged_pairs)} duplicate cluster pairs")
            results["duplicates_merged"] = [(p[0], p[1]) for p in merged_pairs]
        else:
            duplicate_pairs = find_similar_clusters(similarity_threshold=cleanup_threshold)
            logger.info(f"[DRY RUN] Would merge {len(duplicate_pairs)} duplicate cluster pairs")
            results["duplicates_merged"] = [(p[0], p[1]) for p in duplicate_pairs]
    except Exception as e:
        logger.error(f"Cleanup operation failed: {e}", exc_info=True)
    
    # Update index
    if not dry_run:
        try:
            update_index(load_clusters())
            logger.info("✓ Updated cluster index")
        except Exception as e:
            logger.warning(f"Failed to update index: {e}")
    
    # Final statistics
    clusters_after = load_clusters()
    active_after = len([c for c in clusters_after.values() if c.get("status") == "active"])
    
    results["finished_at"] = datetime.utcnow().isoformat()
    results["active_clusters_before"] = active_before
    results["active_clusters_after"] = active_after
    results["total_merges"] = len(results["merges"])
    results["total_archived"] = len(results["archived"])
    results["total_duplicates"] = len(results["duplicates_merged"])
    
    logger.info("\n" + "=" * 60)
    logger.info("Maintenance Summary")
    logger.info("=" * 60)
    logger.info(f"Active clusters before: {active_before}")
    logger.info(f"Active clusters after: {active_after}")
    logger.info(f"Clusters merged: {len(results['merges'])}")
    logger.info(f"Clusters archived: {len(results['archived'])}")
    logger.info(f"Duplicates merged: {len(results['duplicates_merged'])}")
    logger.info("=" * 60)
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run cluster maintenance operations")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--merge-threshold",
        type=float,
        default=0.85,
        help="Similarity threshold for merging clusters (default: 0.85)"
    )
    parser.add_argument(
        "--archive-days",
        type=int,
        default=30,
        help="Days of inactivity before archiving (default: 30)"
    )
    parser.add_argument(
        "--cleanup-threshold",
        type=float,
        default=0.95,
        help="Similarity threshold for duplicate cleanup (default: 0.95)"
    )
    
    args = parser.parse_args()
    
    run_maintenance(
        merge_threshold=args.merge_threshold,
        archive_days=args.archive_days,
        cleanup_threshold=args.cleanup_threshold,
        dry_run=args.dry_run,
    )
