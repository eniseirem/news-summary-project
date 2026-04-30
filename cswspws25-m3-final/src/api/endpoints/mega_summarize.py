"""
mega_summarize.py
=================

Generate a mega summary from existing cluster summaries.

Purpose
-------
This endpoint generates a mega summary by combining multiple cluster summaries.
It is designed to work with pre-generated cluster summaries from /cluster_summarize.

Key Features
-----------
- Fast processing (just combines existing summaries)
- No article processing needed
- Lightweight endpoint optimized for n8n integration
"""

from datetime import datetime
from typing import Dict, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

from llm_engine.summarizer_llama import summarize_mega_with_llama

logger = logging.getLogger(__name__)

router = APIRouter(tags=["clustering", "n8n"])


class MegaSummaryFromClustersRequest(BaseModel):
    """Request model for mega summary generation."""
    request_id: str
    cluster_summaries: Dict[str, str]  # Map: cluster_id -> summary text


class MegaSummaryFromClustersResponse(BaseModel):
    """Response model for mega summary generation."""
    request_id: str
    mega_summary: str
    cluster_count: int
    cluster_ids: List[str]
    processed_at: str


@router.post("/mega_summarize", response_model=MegaSummaryFromClustersResponse)
def mega_summary_from_clusters_endpoint(payload: MegaSummaryFromClustersRequest):
    """
    Generate a mega summary from existing cluster summaries.
    
    Processing Steps
    ----------------
    1. Combine all cluster summaries into one text
    2. Generate mega summary from combined summaries
    3. Return mega summary with metadata
    
    Key Features
    ------------
    - Fast processing (just combines existing summaries)
    - No article processing needed
    - Only generates mega summary (no per-cluster breakdowns)
    
    Parameters
    ----------
    payload : MegaSummaryFromClustersRequest
        Request containing cluster summaries (cluster_id -> summary text).
    
    Returns
    -------
    MegaSummaryFromClustersResponse
        Generated mega summary combining all cluster summaries.
    """
    logger.info(f"[MEGA_SUMMARY_FROM_CLUSTERS] Processing {len(payload.cluster_summaries)} cluster summaries")
    
    if not payload.cluster_summaries:
        raise HTTPException(
            status_code=400,
            detail="At least one cluster summary is required"
        )
    
    # Validate summaries are not empty
    valid_summaries = {
        cluster_id: summary
        for cluster_id, summary in payload.cluster_summaries.items()
        if summary and summary.strip()
    }
    
    if not valid_summaries:
        raise HTTPException(
            status_code=400,
            detail="All cluster summaries are empty"
        )
    
    # Combine all cluster summaries
    cluster_ids = list(valid_summaries.keys())
    combined_text = "\n\n".join(valid_summaries.values())
    
    if not combined_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Combined cluster summaries are empty"
        )
    
    # Generate mega summary
    logger.info(f"[MEGA_SUMMARY_FROM_CLUSTERS] Generating mega summary from {len(valid_summaries)} clusters...")
    try:
        mega_summary = summarize_mega_with_llama(
            text=combined_text,
            total_clusters=len(valid_summaries),
            language="en",
        )
    except Exception as e:
        logger.error(f"[MEGA_SUMMARY_FROM_CLUSTERS] Failed to generate mega summary: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate mega summary: {str(e)}"
        )
    
    logger.info(f"[MEGA_SUMMARY_FROM_CLUSTERS] Generated mega summary ({len(mega_summary.split())} words)")
    
    return MegaSummaryFromClustersResponse(
        request_id=payload.request_id,
        mega_summary=mega_summary,
        cluster_count=len(valid_summaries),
        cluster_ids=cluster_ids,
        processed_at=datetime.utcnow().isoformat(),
    )
