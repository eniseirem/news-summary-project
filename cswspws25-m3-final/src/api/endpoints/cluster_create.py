"""
cluster_create.py
========================

Lightweight clustering endpoint.

Purpose
-------
This endpoint performs clustering on articles and returns cluster assignments.
Designed to be lightweight and fast for n8n workflows.

Design Notes
------------
- Translates articles to English if needed
- Summarizes articles individually (prevents truncation)
- Clusters article summaries using SBERT embeddings + HDBSCAN
- Returns minimal cluster data (cluster_id, article_ids, centroid)
- No summarization, keywords, or labels (use other endpoints for that)
- Optimized for n8n integration with minimal payload
"""

from datetime import datetime
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
import numpy as np
import asyncio
from concurrent.futures import ThreadPoolExecutor

from api.schemas import Article
from llm_engine.summarizer_llama import summarize_articles_batch
from llm_engine.multilingual import translate_single_article
from clustering.cluster_pipeline import cluster_articles
from clustering.embeddings import encode
from clustering.cluster_storage import serialize_embedding

logger = logging.getLogger(__name__)

router = APIRouter(tags=["clustering", "n8n"])


class ClusterArticlesN8NRequest(BaseModel):
    """Request model for lightweight clustering."""
    request_id: str
    articles: List[Article]
    min_cluster_size: int = 2  # Minimum cluster size for HDBSCAN
    method: str = "hdbscan"  # "hdbscan" or "kmeans"


class ClusterN8N(BaseModel):
    """Minimal cluster information."""
    cluster_id: int
    article_ids: List[str]
    article_count: int
    centroid_embedding: List[float]  # 384-dim vector


class ClusterArticlesN8NResponse(BaseModel):
    """Response model for lightweight clustering."""
    request_id: str
    total_articles: int
    total_clusters: int
    clusters: List[ClusterN8N]
    article_summaries: Optional[Dict[str, str]] = None  # Map: article_id -> summary text
    processed_at: str


@router.post("/cluster_create", response_model=ClusterArticlesN8NResponse)
async def cluster_articles_n8n_endpoint(payload: ClusterArticlesN8NRequest):
    """
    Cluster articles using SBERT embeddings and HDBSCAN/KMeans.
    
    Processing Steps
    ----------------
    1. Translate articles to English if needed
    2. Summarize articles individually (prevents truncation)
    3. Generate embeddings for article summaries
    4. Cluster articles using HDBSCAN or KMeans
    5. Calculate centroids for each cluster
    6. Return cluster assignments with centroids
    
    Benefits
    --------
    - Lightweight: Only clustering, no summarization/labeling
    - Fast: Optimized for n8n workflows
    - Minimal payload: Only essential cluster data
    
    Constraints
    -----------
    - Articles must not be empty
    - Minimum cluster size at least 1
    - Method must be "hdbscan" or "kmeans"
    
    Parameters
    ----------
    payload : ClusterArticlesN8NRequest
        Request containing articles and clustering parameters.
    
    Returns
    -------
    ClusterArticlesN8NResponse
        Cluster assignments with centroids.
    """
    
    # Validate input
    if not payload.articles:
        raise HTTPException(
            status_code=400,
            detail="Articles list cannot be empty"
        )
    
    if payload.min_cluster_size < 1:
        raise HTTPException(
            status_code=400,
            detail="min_cluster_size must be at least 1"
        )
    
    if payload.method not in ["hdbscan", "kmeans"]:
        raise HTTPException(
            status_code=400,
            detail="method must be 'hdbscan' or 'kmeans'"
        )
    
    # Step 1: Translate articles in parallel (with early exit for English)
    logger.info(f"[CLUSTER_ARTICLES_N8N] Processing {len(payload.articles)} articles...")
    
    # Prepare article dicts for parallel translation
    article_dicts = []
    for art in payload.articles:
        art_dict = art.model_dump() if hasattr(art, "model_dump") else art.dict()
        article_dicts.append(art_dict)
    
    # Translate articles in parallel (5 workers)
    def translate_with_fallback(art_dict: dict) -> dict:
        """Translate article with error handling."""
        try:
            return translate_single_article(art_dict)
        except ValueError as e:
            logger.warning(f"[CLUSTER_ARTICLES_N8N] Translation unsupported for article id={art_dict.get('id')}: {e}")
            translated = dict(art_dict)
            translated["language"] = "en"
            translated["original_language"] = art_dict.get("language", "en")
            return translated
        except Exception as e:
            logger.warning(f"[CLUSTER_ARTICLES_N8N] Translation failed for article id={art_dict.get('id')}: {e}")
            translated = dict(art_dict)
            translated["language"] = "en"
            translated["original_language"] = art_dict.get("language", "en")
            return translated
    
    # Translate articles in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=5) as executor:
        translated_articles = list(executor.map(translate_with_fallback, article_dicts))
    
    # Prepare articles for summarization
    articles_for_clustering = []
    article_map = {}
    
    for i, art in enumerate(payload.articles):
        translated = translated_articles[i]
        
        # Prepare text for summarization
        title_en = translated.get("title", "") or ""
        body_en = translated.get("body", "") or ""
        text = f"{title_en}. {body_en}".strip() if title_en else body_en.strip()
        
        if text:
            articles_for_clustering.append({
                "id": art.id,
                "text": text,
            })
            article_map[art.id] = art
    
    if not articles_for_clustering:
        raise HTTPException(
            status_code=400,
            detail="No valid articles after processing"
        )
    
    # Step 2: Summarize articles in parallel
    logger.info(f"[CLUSTER_ARTICLES_N8N] Summarizing {len(articles_for_clustering)} articles...")
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=5) as executor:
        summarized_articles = await loop.run_in_executor(
            executor,
            summarize_articles_batch,
            [{"id": a["id"], "text": a["text"]} for a in articles_for_clustering],
            100,  # target_words_per_article
            "en",  # language
            5,     # max_workers
        )
    
    # Create mapping from article ID to summary
    article_id_to_summary = {}
    for art_summary in summarized_articles:
        article_id = art_summary.get("id")
        summary = art_summary.get("summary", "")
        if not summary:
            # Fallback to original text if summary failed
            for orig in articles_for_clustering:
                if orig.get("id") == article_id:
                    summary = orig.get("text", "")
                    break
        article_id_to_summary[article_id] = summary
    
    # Step 3: Prepare articles for clustering (use summaries)
    article_list_for_clustering = []
    for art_summary in summarized_articles:
        article_id = art_summary.get("id")
        summary = article_id_to_summary.get(article_id, "")
        if summary:
            article_list_for_clustering.append({
                "id": article_id,
                "text": summary,
            })
    
    if not article_list_for_clustering:
        raise HTTPException(
            status_code=500,
            detail="No articles with valid summaries for clustering"
        )
    
    # Step 4: Cluster articles
    logger.info(f"[CLUSTER_ARTICLES_N8N] Clustering {len(article_list_for_clustering)} articles...")
    clusters = cluster_articles(
        articles=article_list_for_clustering,
        method=payload.method,
        min_cluster_size=payload.min_cluster_size,
    )
    
    # Step 5: Calculate centroids for each cluster
    logger.info(f"[CLUSTER_ARTICLES_N8N] Calculating centroids for {len(clusters)} clusters...")
    
    cluster_results = []
    for cluster in clusters:
        cluster_id = cluster["cluster_id"]
        article_ids = cluster["article_ids"]
        
        # Get summaries for articles in this cluster
        cluster_texts = [
            article_id_to_summary.get(aid, "")
            for aid in article_ids
            if article_id_to_summary.get(aid, "")
        ]
        
        if not cluster_texts:
            continue
        
        # Generate embeddings for cluster articles
        embeddings = encode(cluster_texts)
        
        if len(embeddings) == 0:
            continue
        
        # Calculate centroid (mean of embeddings)
        centroid = np.mean(embeddings, axis=0)
        
        # Normalize centroid
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm
        
        # Serialize centroid
        centroid_serialized = serialize_embedding(centroid)
        
        cluster_results.append(
            ClusterN8N(
                cluster_id=cluster_id,
                article_ids=article_ids,
                article_count=len(article_ids),
                centroid_embedding=centroid_serialized,
            )
        )
    
    logger.info(f"[CLUSTER_ARTICLES_N8N] Returning {len(cluster_results)} clusters")
    
    # Return article summaries for n8n to cache
    article_summaries_dict = {
        article_id: summary
        for article_id, summary in article_id_to_summary.items()
        if summary  # Only include non-empty summaries
    }
    
    return ClusterArticlesN8NResponse(
        request_id=payload.request_id,
        total_articles=len(payload.articles),
        total_clusters=len(cluster_results),
        clusters=cluster_results,
        article_summaries=article_summaries_dict if article_summaries_dict else None,
        processed_at=datetime.utcnow().isoformat(),
    )
