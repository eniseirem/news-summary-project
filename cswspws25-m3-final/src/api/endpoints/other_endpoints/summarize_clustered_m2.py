"""
summarize_clustered.py
=====================

Cluster-based summarization endpoint with mega summary (orchestration layer).

Purpose
-------
This endpoint orchestrates a full clustering and summarization pipeline:
1. Summarizes articles individually (prevents truncation)
2. Clusters article summaries using SBERT embeddings + HDBSCAN
3. Generates cluster summaries
4. Generates topic labels using /topic_label logic
5. Assigns categories using /category_label logic
6. Generates a global mega summary from all cluster summaries

This endpoint generates:
- Per-cluster summaries (one summary per topic cluster)
- A global mega summary (combining all cluster summaries)

Design Notes
------------
- This is an orchestration endpoint that combines multiple operations
- Uses underlying functions from separated endpoints (not HTTP calls)
- Simpler than /cluster_summary (no keyword extraction)
- Focuses on summaries and labels, not detailed keyword analysis

Related Endpoints
-----------------
- /cluster_summary - Full pipeline with keywords (LDA/TF-IDF)
- /topic_label - Standalone topic labeling
- /category_label - Standalone category labeling

It is primarily intended for:
- Topic grouping views with global overview
- Debugging clustering + summarization quality
- Frontend layouts that display both topic sections and a global digest
"""

from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

from api.schemas import Article
from llm_engine.summarizer_llama import summarize_cluster_with_llama, summarize_mega_with_llama, summarize_articles_batch
from clustering.cluster_pipeline import cluster_articles
from topic_labeling.llama_lda_pipeline import generate_cluster_label_with_llama
from topic_labeling.llama_topic_labeler import generate_cluster_topic_label

logger = logging.getLogger(__name__)

# Maximum articles per request to prevent timeouts
MAX_ARTICLES_PER_REQUEST = 100


class SummarizeClusteredRequest(BaseModel):
    request_id: str
    filters_used: dict = {}
    articles: List[Article]


class SummarizeClusteredResponse(BaseModel):
    request_id: str
    summary_type: str = "clustered_summary"
    cluster_count: int
    clusters: List[dict]
    mega_summary: str = ""  # Global summary combining all cluster summaries
    processed_at: str


router = APIRouter(tags=["summarization", "clustering"])


def _process_single_cluster(
    cluster: dict,
    article_list_for_clustering: List[dict],
    article_by_id: dict,
) -> dict:
    """
    Process a single cluster: summarize, label topic and category.
    
    This function orchestrates:
    - Cluster summarization
    - Topic labeling - uses /topic_label logic
    - Category labeling - uses /category_label logic
    
    Note: This is simpler than cluster_summary's processing (no keyword extraction).
    
    Parameters
    ----------
    cluster : dict
        Cluster dict with cluster_id and article_ids
    article_list_for_clustering : List[dict]
        List of article dicts with summaries (from article-level summarization)
    article_by_id : dict
        Mapping of article_id -> Article object
    
    Returns
    -------
    dict
        Cluster dict with summary, topic_label, category, and articles
    """
    cluster_id = cluster["cluster_id"]
    # Support both 'article_ids' and 'article_urls' for backward compatibility
    article_ids = cluster.get("article_ids") or cluster.get("article_urls", [])
    
    print(f"[CLUSTER_{cluster_id}] Starting processing with {len(article_ids)} articles")

    # Combine article summaries for this cluster (article_list_for_clustering now contains summaries)
    cluster_texts = [
        a["text"]
        for a in article_list_for_clustering
        if (a.get("id") or a.get("url")) in article_ids
    ]
    combined_text = " ".join(cluster_texts)
    print(f"[CLUSTER_{cluster_id}] Combined text length: {len(combined_text)} characters")

    # Generate cluster summary (must complete first)
    print(f"[CLUSTER_{cluster_id}] Calling summarize_cluster_with_llama...")
    try:
        cluster_summary = summarize_cluster_with_llama(
            text=str(combined_text),
            language="en",
        )
        print(f"[CLUSTER_{cluster_id}] Summary generated ({len(cluster_summary)} chars)")
    except Exception as e:
        print(f"[CLUSTER_{cluster_id}] ERROR in summarize_cluster_with_llama: {e}")
        raise

    # Orchestrate parallel operations: topic labeling and category labeling
    # Note: Uses the same underlying functions as /topic_label and /category_label endpoints
    print(f"[CLUSTER_{cluster_id}] Generating topic and category labels in parallel...")
    import concurrent.futures
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        # Step 1: Generate topic label - uses /topic_label endpoint logic
        topic_future = executor.submit(
            lambda: generate_cluster_topic_label(cluster_summary=cluster_summary)
        )
        
        # Step 2: Generate category label - uses /category_label endpoint logic
        category_future = executor.submit(
            lambda: generate_cluster_label_with_llama(
                cluster_summary=cluster_summary,
                article_count=len(article_list_for_clustering),
                use_lda=True,
                is_noise_cluster=(cluster_id == -1),
            )
        )
        
        try:
            topic_label = topic_future.result()
            print(f"[CLUSTER_{cluster_id}] ✓ Topic label generated: '{topic_label}'")
        except Exception as e:
            print(f"[CLUSTER_{cluster_id}] ❌ Topic labeling failed: {e}")
            topic_label = ""
        
        try:
            category_label = category_future.result()
            print(f"[CLUSTER_{cluster_id}] ✓ Category label generated: '{category_label}'")
        except Exception as e:
            print(f"[CLUSTER_{cluster_id}] ❌ Category labeling failed: {e}")
            category_label = "General News"
    
    print(f"[CLUSTER_{cluster_id}] Completed processing")

    return {
        "cluster_id": cluster_id,
        "topic_label": topic_label,
        "category": category_label,
        "topic_summary": cluster_summary,
        "article_ids": article_ids,  # Explicit article_ids list
        "articles": [
            {
                "id": article_by_id[aid].id,
                "title": article_by_id[aid].title,
            }
            for aid in article_ids
            if aid in article_by_id
        ],
    }


@router.post("/summarize_clustered", response_model=SummarizeClusteredResponse)
async def summarize_clustered_endpoint(payload: SummarizeClusteredRequest, response: Response):
    """
    Cluster articles and generate summaries with mega summary (orchestration endpoint).

    Processing Steps
    ----------------
    1. Summarize articles individually (prevents truncation)
    2. Cluster article summaries using SBERT embeddings + HDBSCAN
    3. For each cluster (processed in parallel):
        - Generate cluster summary from article summaries
        - Generate topic label - uses /topic_label logic
        - Generate category label - uses /category_label logic
    4. Generate a global mega summary from all cluster summaries
    5. Return per-cluster summaries, mega summary, and metadata

    This endpoint orchestrates multiple operations:
    - Article-level summarization
    - Clustering
    - Cluster summarization
    - Topic labeling (via /topic_label functions)
    - Category labeling (via /category_label functions)
    - Mega summary generation

    Differences from /cluster_summary
    ----------------------------------
    - Simpler: No keyword extraction (LDA/TF-IDF)
    - Includes: Global mega summary
    - Focus: Summaries and labels, not detailed keyword analysis

    Constraints
    -----------
    - No category-level summarization
    - No tone, style, or format rewriting
    - Input articles must already be filtered upstream
    - Maximum 100 articles per request (to prevent timeouts)

    Related Endpoints
    ----------------
    - /cluster_summary - Full pipeline with keywords (LDA/TF-IDF)
    - /topic_label - Standalone topic labeling
    - /category_label - Standalone category labeling

    Intended Usage
    --------------
    - Topic-based article groupings with global overview
    - Frontend sectioned views with mega summary
    - Internal inspection of clustering behavior
    - Full pipeline with mega summary (all-in-one)

    Parameters
    ----------
    payload : SummarizeClusteredRequest
        Request containing article list and metadata.

    Returns
    -------
    SummarizeClusteredResponse
        Cluster summaries with topic labels, category labels, and global mega summary.
    """
    
    # Validate request size immediately
    if len(payload.articles) > MAX_ARTICLES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Too many articles. Maximum {MAX_ARTICLES_PER_REQUEST} articles per request. "
                   f"Received {len(payload.articles)} articles. "
                   f"Please split into smaller batches."
        )
    
    # Send immediate acknowledgment headers to keep connection alive
    response.headers["X-Request-Id"] = payload.request_id
    response.headers["X-Status"] = "processing"
    response.headers["Connection"] = "keep-alive"
    
    logger.info(f"Processing {len(payload.articles)} articles for request {payload.request_id}")

    # ---- Step 1: Summarize articles individually first (prevents truncation) ----
    logger.info(f"Step 1: Summarizing {len(payload.articles)} articles individually...")
    
    article_by_id = {}
    articles_for_summarization = []

    for art in payload.articles:
        text = f"{art.title}. {art.body}".strip() if art.title else art.body.strip()
        if not text:
            continue
        article_by_id[art.id] = art
        articles_for_summarization.append({
            "id": art.id,
                "text": text,
            "title": art.title,
            "body": art.body,
        })
    
    # Summarize articles in parallel
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=5) as executor:
        summarized_articles = await loop.run_in_executor(
            executor,
            summarize_articles_batch,
            articles_for_summarization,
            100,  # target_words_per_article
            "en",  # language
            5,     # max_workers
        )
    
    logger.info(f"Summarized {len(summarized_articles)} articles")
    
    # Create mapping from article ID to summary
    article_id_to_summary = {}
    for art_summary in summarized_articles:
        article_id = art_summary.get("id")
        summary = art_summary.get("summary", "")
        if not summary:
            # Fallback to original text if summary failed
            for orig in articles_for_summarization:
                if orig.get("id") == article_id:
                    summary = orig.get("text", "")
                    break
        article_id_to_summary[article_id] = summary
    
    # ---- Step 2: Prepare summarized articles for clustering ----
    article_list_for_clustering = []
    for art_summary in summarized_articles:
        article_id = art_summary.get("id")
        summary = article_id_to_summary.get(article_id, "")
        if summary:  # Only include articles with valid summaries
            article_list_for_clustering.append({
                "id": article_id,
                "text": summary,  # Use summary instead of full text
            })

    # ---- Step 3: Cluster article summaries ----
    logger.info(f"Step 2: Clustering {len(article_list_for_clustering)} article summaries...")
    clusters = cluster_articles(article_list_for_clustering, method="hdbscan")
    logger.info(f"Found {len(clusters)} clusters")

    # ---- Process clusters in parallel for better performance ----
    loop = asyncio.get_event_loop()
    
    # Use ThreadPoolExecutor to run blocking LLaMA calls in parallel
    with ThreadPoolExecutor(max_workers=min(5, len(clusters))) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                _process_single_cluster,
                cluster,
                article_list_for_clustering,
                article_by_id,
            )
            for cluster in clusters
        ]
        
        # Wait for all clusters to be processed
        logger.info(f"Processing {len(tasks)} clusters in parallel...")
        cluster_payloads = await asyncio.gather(*tasks)
        logger.info("All clusters processed")

    # ---- Generate global mega summary from all cluster summaries ----
    mega_summary = ""
    if cluster_payloads:
        logger.info("Generating mega summary...")
        # Combine all cluster summaries into one text
        all_cluster_summaries = "\n\n".join([
            cluster["topic_summary"]
            for cluster in cluster_payloads
        ])
        
        # Generate mega summary from all cluster summaries (run in thread pool)
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            mega_summary = await loop.run_in_executor(
                executor,
                summarize_mega_with_llama,
                all_cluster_summaries,
                int(len(cluster_payloads)),
                "en",
            )
        logger.info("Mega summary generated")

    return SummarizeClusteredResponse(
        request_id=payload.request_id,
        summary_type="clustered_summary",
        cluster_count=int(len(cluster_payloads)),
        clusters=cluster_payloads,
        mega_summary=mega_summary,
        processed_at=datetime.utcnow().isoformat(),
    )
