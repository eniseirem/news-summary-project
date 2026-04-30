"""
cluster_summarize.py
=====================

Generate cluster summaries from existing clusters using cached article summaries.

Purpose
-------
This endpoint generates cluster summaries from pre-clustered articles.
It can use cached article summaries (from /cluster_create)
# Note: /cluster_update is not in use - n8n handles cluster updates directly
or generate them on-the-fly if not provided.

Key Features
-----------
- Uses cached article summaries if provided (FAST - no regeneration)
- Falls back to generating summaries if not provided (100 words each)
- Generates cluster summaries only (no labels, no keywords)
- Lightweight endpoint optimized for n8n integration
"""

from datetime import datetime
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Dict, Union
from pydantic import BaseModel, field_validator


from api.schemas import Article
from llm_engine.summarizer_llama import summarize_cluster_with_llama, summarize_articles_batch
from llm_engine.multilingual import translate_single_article

logger = logging.getLogger(__name__)

router = APIRouter(tags=["clustering", "n8n"])


class ClusterInput(BaseModel):
    """Minimal cluster input.

    cluster_id can be:
    - int: local cluster index from /cluster_create (0,1,2,...)
    - str: OpenSearch UUID / external cluster identifier
    """
    cluster_id: Union[str, int]
    article_ids: List[str]

    @field_validator("cluster_id")
    @classmethod
    def coerce_cluster_id_to_str(cls, v):
        return str(v)


class ClusterSummaryOutput(BaseModel):
    """Cluster summary output."""
    cluster_id: str
    article_ids: List[str]
    article_count: int
    summary: str


class ClusterSummaryFromClustersRequest(BaseModel):
    """Request model for cluster summary generation."""
    request_id: str
    clusters: List[ClusterInput]
    articles: List[Article]
    article_summaries: Optional[Dict[str, str]] = None  # Optional: cached summaries


class ClusterSummaryFromClustersResponse(BaseModel):
    """Response model for cluster summary generation."""
    request_id: str
    cluster_count: int
    clusters: List[ClusterSummaryOutput]
    processed_at: str


@router.post("/cluster_summarize", response_model=ClusterSummaryFromClustersResponse)
async def cluster_summary_from_clusters_endpoint(payload: ClusterSummaryFromClustersRequest):
    """
    Generate cluster summaries from existing clusters using cached article summaries.
    
    Processing Steps
    ----------------
    1. Validate: All article_ids in clusters exist in articles/article_summaries
    2. Group articles by cluster_id
    3. For each cluster:
       a. Use cached article summaries (if provided) OR generate summaries (100 words)
       b. Generate cluster summary from article summaries
    4. Return cluster summaries only (no labels, no keywords)
    
    Key Features
    ------------
    - Uses cached article summaries if provided (FAST - no regeneration)
    - Falls back to generating summaries if not provided (100 words each)
    - Generates cluster summaries only (no labels, no keywords)
    
    Parameters
    ----------
    payload : ClusterSummaryFromClustersRequest
        Request containing clusters, articles, and optional cached article summaries.
    
    Returns
    -------
    ClusterSummaryFromClustersResponse
        Cluster summaries for each cluster.
    """
    logger.info(f"[CLUSTER_SUMMARY_FROM_CLUSTERS] Processing {len(payload.clusters)} clusters")
    
    # Create article lookup map
    article_map = {art.id: art for art in payload.articles}
    
    # Validate all article IDs exist
    all_article_ids = set()
    for cluster in payload.clusters:
        all_article_ids.update(cluster.article_ids)
    
    missing_articles = all_article_ids - set(article_map.keys())
    if missing_articles:
        raise HTTPException(
            status_code=400,
            detail=f"Missing articles: {list(missing_articles)}"
        )
    
    # Prepare article summaries (use cached or generate)
    article_summaries_dict = payload.article_summaries or {}
    
    # Check which articles need summaries generated
    articles_to_summarize = []
    for article_id in all_article_ids:
        if article_id not in article_summaries_dict:
            articles_to_summarize.append(article_map[article_id])
    
    # Generate missing article summaries if needed
    if articles_to_summarize:
        logger.info(f"[CLUSTER_SUMMARY_FROM_CLUSTERS] Generating {len(articles_to_summarize)} article summaries...")
        
        # Translate articles to English first
        article_dicts = []
        for art in articles_to_summarize:
            art_dict = art.model_dump() if hasattr(art, "model_dump") else art.dict()
            try:
                translated = translate_single_article(art_dict)
            except ValueError as e:
                logger.warning(f"[CLUSTER_SUMMARY_FROM_CLUSTERS] Translation unsupported for article id={art.id}: {e}")
                translated = dict(art_dict)
                translated["language"] = "en"
                translated["original_language"] = art_dict.get("language", "en")
            article_dicts.append(translated)
        
        # Summarize articles in parallel (5 workers)
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=5) as executor:
            summarized_articles = await loop.run_in_executor(
                executor,
                summarize_articles_batch,
                [{"id": a["id"], "text": f"{a.get('title', '')}. {a.get('body', '')}".strip()} for a in article_dicts],
                100,  # target_words_per_article
                "en",  # language
                5,     # max_workers
            )
        
        # Add generated summaries to dict
        for art_summary in summarized_articles:
            article_id = art_summary.get("id")
            summary = art_summary.get("summary", "")
            if article_id and summary:
                article_summaries_dict[article_id] = summary
    
    # Process each cluster
    cluster_outputs = []
    
    for cluster in payload.clusters:
        cluster_id = cluster.cluster_id
        article_ids = cluster.article_ids
        
        # Get article summaries for this cluster
        cluster_summaries = []
        for article_id in article_ids:
            if article_id in article_summaries_dict:
                cluster_summaries.append(article_summaries_dict[article_id])
            else:
                logger.warning(f"[CLUSTER_SUMMARY_FROM_CLUSTERS] No summary found for article {article_id} in cluster {cluster_id}")
        
        if not cluster_summaries:
            logger.warning(f"[CLUSTER_SUMMARY_FROM_CLUSTERS] No summaries available for cluster {cluster_id}, skipping")
            continue
        
        # Combine article summaries
        combined_text = " ".join(cluster_summaries).strip()
        
        if not combined_text:
            logger.warning(f"[CLUSTER_SUMMARY_FROM_CLUSTERS] Empty combined text for cluster {cluster_id}, skipping")
            continue
        
        # Generate cluster summary
        logger.info(f"[CLUSTER_SUMMARY_FROM_CLUSTERS] Generating summary for cluster {cluster_id} ({len(article_ids)} articles)")
        try:
            cluster_summary = summarize_cluster_with_llama(
                text=combined_text,
                language="en",
            )
        except Exception as e:
            logger.error(f"[CLUSTER_SUMMARY_FROM_CLUSTERS] Failed to generate summary for cluster {cluster_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate summary for cluster {cluster_id}: {str(e)}"
            )
        
        cluster_outputs.append(ClusterSummaryOutput(
            cluster_id=cluster_id,
            article_ids=article_ids,
            article_count=len(article_ids),
            summary=cluster_summary,
        ))
    
    logger.info(f"[CLUSTER_SUMMARY_FROM_CLUSTERS] Generated {len(cluster_outputs)} cluster summaries")
    
    return ClusterSummaryFromClustersResponse(
        request_id=payload.request_id,
        cluster_count=len(cluster_outputs),
        clusters=cluster_outputs,
        processed_at=datetime.utcnow().isoformat(),
    )
