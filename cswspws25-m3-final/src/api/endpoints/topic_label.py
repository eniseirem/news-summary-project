"""
topic_label.py
==============

Topic labeling endpoint for generating short topic labels from summaries.

Purpose
-------
This endpoint generates concise topic labels (max 4 words) from cluster summaries
or article summaries using LLaMA. It's designed to be called independently
or as part of a larger pipeline.

Design Notes
------------
- Accepts cluster summaries or article summaries
- Returns topic label along with article IDs and metadata
- Can be used standalone or integrated into other endpoints
- Uses LLaMA for label generation with retry logic
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from topic_labeling.llama_topic_labeler import generate_cluster_topic_label


class TopicLabelRequest(BaseModel):
    """Request model for topic labeling."""
    request_id: str
    summary: str  # Cluster summary or article summary
    article_ids: Optional[List[str]] = None  # Optional: article IDs associated with this summary
    max_words: int = 4  # Maximum words in topic label (default 4)


class TopicLabelResponse(BaseModel):
    """Response model for topic labeling."""
    request_id: str
    topic_label: str
    article_ids: Optional[List[str]] = None  # Article IDs if provided
    summary_length: int  # Length of input summary in characters
    max_words: int  # Maximum words used for label
    processed_at: str


router = APIRouter(tags=["topic_labeling"])


@router.post("/topic_label", response_model=TopicLabelResponse)
def topic_label_endpoint(payload: TopicLabelRequest):
    """
    Generate a topic label from a summary.

    Processing Steps
    ----------------
    1. Validate input summary (must not be empty)
    2. Generate topic label using LLaMA
    3. Return label with metadata

    Constraints
    -----------
    - Summary must not be empty
    - Label is limited to max_words (default 4)
    - Uses LLaMA with retry logic (up to 3 attempts)

    Intended Usage
    --------------
    - Standalone topic labeling for clusters or articles
    - Integration into clustering pipelines
    - Re-labeling existing clusters
    - Batch processing of summaries

    Parameters
    ----------
    payload : TopicLabelRequest
        Request containing summary and optional article IDs.

    Returns
    -------
    TopicLabelResponse
        Topic label with metadata.
    """
    
    # Validate input
    if not payload.summary or not payload.summary.strip():
        raise HTTPException(
            status_code=400,
            detail="Summary cannot be empty"
        )
    
    if payload.max_words < 1 or payload.max_words > 10:
        raise HTTPException(
            status_code=400,
            detail="max_words must be between 1 and 10"
        )
    
    # Generate topic label
    try:
        topic_label = generate_cluster_topic_label(
            cluster_summary=payload.summary,
            max_words=payload.max_words,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Topic label generation failed: {str(e)}"
        )
    
    return TopicLabelResponse(
        request_id=payload.request_id,
        topic_label=topic_label,
        article_ids=payload.article_ids,
        summary_length=len(payload.summary),
        max_words=payload.max_words,
        processed_at=datetime.utcnow().isoformat(),
    )
