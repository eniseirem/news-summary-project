"""
category_label.py
=================

Category labeling endpoint for assigning clusters/articles to predefined news categories.

Purpose
-------
This endpoint assigns clusters or articles to one of five predefined news categories
using LLaMA. Categories are fixed and hard-coded:
- Global Politics
- Economics
- Sports
- Events
- General News

Design Notes
------------
- Accepts cluster summary or article summary
- Optionally uses LDA keywords for better classification
- Returns one of the predefined categories (never invents new ones)
- Weak/noise clusters default to "General News"
- Can be used standalone or integrated into other endpoints
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from topic_labeling.llama_lda_pipeline import generate_cluster_label_with_llama


class CategoryLabelRequest(BaseModel):
    """Request model for category labeling."""
    request_id: str
    summary: str  # Cluster summary or article summary
    article_ids: Optional[List[str]] = None  # Optional: article IDs associated with this summary
    article_count: int = 1  # Number of articles in cluster (default 1 for single article)
    lda_keywords: Optional[List[str]] = None  # Optional: LDA keywords for better classification
    use_lda: bool = True  # Whether to use LDA keywords if provided
    is_noise_cluster: bool = False  # Whether this is a noise cluster (defaults to General News)
    cluster_id: Optional[int] = None  # Optional: cluster ID if this is for a cluster


class CategoryLabelResponse(BaseModel):
    """Response model for category labeling."""
    request_id: str
    category: str  # One of: Global Politics, Economics, Sports, Events, General News
    article_ids: Optional[List[str]] = None  # Article IDs if provided
    article_count: int
    cluster_id: Optional[int] = None
    summary_length: int  # Length of input summary in characters
    used_lda: bool  # Whether LDA keywords were used
    is_noise_cluster: bool  # Whether this was treated as a noise cluster
    processed_at: str


router = APIRouter(tags=["category_labeling"])


@router.post("/category_label", response_model=CategoryLabelResponse)
def category_label_endpoint(payload: CategoryLabelRequest):
    """
    Assign a summary to one of five predefined news categories.

    Processing Steps
    ----------------
    1. Validate input summary (must not be empty)
    2. Check if cluster is weak/noise (defaults to General News)
    3. Generate category label using LLaMA
    4. Return category with metadata

    Categories
    ----------
    Fixed set of categories (LLaMA cannot invent new ones):
    - Global Politics
    - Economics
    - Sports
    - Events
    - General News

    Constraints
    -----------
    - Summary must not be empty
    - Weak clusters (< 2 articles, < 60 words) default to General News
    - Noise clusters default to General News
    - Category is always one of the five predefined categories

    Intended Usage
    --------------
    - Standalone category labeling for clusters or articles
    - Integration into clustering pipelines
    - Category-based filtering and organization
    - Analytics and reporting

    Parameters
    ----------
    payload : CategoryLabelRequest
        Request containing summary and optional metadata.

    Returns
    -------
    CategoryLabelResponse
        Category label with metadata.
    """
    
    # Validate input
    if not payload.summary or not payload.summary.strip():
        raise HTTPException(
            status_code=400,
            detail="Summary cannot be empty"
        )
    
    if payload.article_count < 1:
        raise HTTPException(
            status_code=400,
            detail="article_count must be at least 1"
        )
    
    # Generate category label
    try:
        category = generate_cluster_label_with_llama(
            cluster_summary=payload.summary,
            article_count=payload.article_count,
            lda_keywords=payload.lda_keywords if payload.use_lda else None,
            use_lda=payload.use_lda and payload.lda_keywords is not None,
            language="en",
            is_noise_cluster=payload.is_noise_cluster,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Category label generation failed: {str(e)}"
        )
    
    return CategoryLabelResponse(
        request_id=payload.request_id,
        category=category,
        article_ids=payload.article_ids,
        article_count=payload.article_count,
        cluster_id=payload.cluster_id,
        summary_length=len(payload.summary),
        used_lda=payload.use_lda and payload.lda_keywords is not None,
        is_noise_cluster=payload.is_noise_cluster,
        processed_at=datetime.utcnow().isoformat(),
    )
