"""
cluster_summary.py
==================

Cluster-based article summarization endpoint (orchestration layer).

Purpose
-------
This endpoint orchestrates the full clustering and summarization pipeline:
1. Summarizes articles individually (prevents truncation)
2. Clusters article summaries using SBERT embeddings + HDBSCAN
3. Generates cluster summaries
4. Extracts keywords (LDA + TF-IDF) using /keywords logic
5. Generates topic labels using /topic_label logic
6. Assigns categories using /category_label logic

This endpoint operates at the **article → cluster → summary** level and
does NOT generate a global or category-level mega summary.

Design Notes
------------
- This is an orchestration endpoint that combines multiple operations
- Uses underlying functions from separated endpoints (not HTTP calls)
- Articles are assumed to be pre-filtered upstream (frontend / n8n)
- Clustering is performed using SBERT embeddings + HDBSCAN
- Each cluster is summarized independently
- Cluster summaries are used to assign one of five fixed categories:
    * Global Politics
    * Economics
    * Sports
    * Events
    * General News
- No tone, style, or format rewriting is applied
- Output language is always English

Related Endpoints
-----------------
- /topic_label - Standalone topic labeling
- /keywords - Standalone keyword extraction (LDA/TFIDF)
- /category_label - Standalone category labeling

This endpoint is primarily used for:
- Topic grouping views
- Category pages that need per-topic sections
- Inspection and debugging of clustering quality
- Full pipeline processing (all-in-one)
"""

from datetime import datetime
from typing import List, Optional, Dict
from fastapi import APIRouter, Response, HTTPException
from pydantic import BaseModel
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import sys
from copy import deepcopy

from api.schemas import Article
from llm_engine.summarizer_llama import summarize_cluster_with_llama, summarize_articles_batch
from clustering.cluster_pipeline import cluster_articles

# Import from separated endpoint modules (using underlying functions)
from topic_labeling.llama_lda_pipeline import generate_cluster_label_with_llama
from topic_labeling.llama_topic_labeler import generate_cluster_topic_label
from topic_labeling.lda_pipeline import generate_lda_labels_for_cluster
from topic_labeling.tfidf_pipeline import extract_tfidf_keywords

from llm_engine.multilingual import translate_single_article

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class ClusterSummaryRequest(BaseModel):
    request_id: str
    filters_used: dict = {}
    articles: List[Article]


class ClusterInfo(BaseModel):
    cluster_id: int
    category: str
    subcategory: str
    topic_summary: str
    articles: List[Article]
    article_ids: List[str]  # Explicit list of article IDs for easier access
    article_count: int
    keywords: Optional[Dict[str, List[str]]] = None


class ClusterSummaryResponse(BaseModel):
    request_id: str
    summary_type: str = "cluster_summary"
    cluster_count: int
    clusters: List[ClusterInfo]
    processed_at: str


router = APIRouter(tags=["clustering"])


def _process_single_cluster_with_keywords(
    cluster: dict,
    article_list_for_clustering: List[dict],
    article_map: dict,
) -> Optional[ClusterInfo]:
    """
    Process a single cluster: summarize, extract keywords, label topic and category.
    """
    cluster_id = cluster["cluster_id"]
    # Support both 'article_ids' and 'article_urls' for backward compatibility
    article_ids = cluster.get("article_ids") or cluster.get("article_urls", [])
    print(f"[CLUSTER_{cluster_id}] Starting processing with {len(article_ids)} articles")

    if not article_ids:
        return None

    # Combine article summaries for this cluster
    cluster_texts = [
        a["text"]
        for a in article_list_for_clustering
        if (a.get("id") or a.get("url")) in article_ids
    ]
    combined_text = " ".join(cluster_texts).strip()

    if not combined_text:
        return None

    # Get articles for this cluster (these are already translated to English upstream)
    articles_in_cluster = [article_map[aid] for aid in article_ids if aid in article_map]
    if not articles_in_cluster:
        return None

    # Prepare data for parallel keyword extraction
    articles_as_dicts = [{"id": art.id, "title": art.title, "body": art.body} for art in articles_in_cluster]
    article_texts = [f"{a.title}. {a.body}" for a in articles_in_cluster]

    # Generate cluster summary (blocking - needed for subsequent steps)
    cluster_summary = summarize_cluster_with_llama(
        text=str(combined_text),
        language="en",
    )

    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        print(f"[CLUSTER_{cluster_id}] Extracting keywords (LDA + TF-IDF)...")
        lda_future = executor.submit(
            lambda: generate_lda_labels_for_cluster(
                cluster={"cluster_id": cluster_id, "articles": articles_as_dicts},
                num_topics=3,
            )
        )
        tfidf_future = executor.submit(lambda: extract_tfidf_keywords(texts=article_texts, top_k=5))

        print(f"[CLUSTER_{cluster_id}] Generating topic label...")
        topic_future = executor.submit(
            lambda: generate_cluster_topic_label(
                cluster_summary=cluster_summary,
                max_words=4,
            )
        )

        # Wait for LDA first (needed for category labeling)
        try:
            lda_result = lda_future.result(timeout=60)
            if lda_result:
                lda_keywords = lda_result.get("lda_labels", [])
                print(f"[CLUSTER_{cluster_id}] ✓ LDA keywords extracted: {len(lda_keywords)} topics")
            else:
                print(f"[CLUSTER_{cluster_id}] ⚠️  WARNING: LDA returned None!")
                lda_keywords = []
        except Exception as e:
            print(f"[CLUSTER_{cluster_id}] ❌ LDA extraction failed: {e}")
            import traceback

            traceback.print_exc()
            lda_keywords = []

        print(f"[CLUSTER_{cluster_id}] Generating category label...")
        category_future = executor.submit(
            lambda: generate_cluster_label_with_llama(
                cluster_summary=cluster_summary,
                article_count=len(articles_in_cluster),
                lda_keywords=lda_keywords,
                use_lda=True,
                is_noise_cluster=cluster_id == -1,
            )
        )

        try:
            tfidf_keywords = tfidf_future.result()
            print(f"[CLUSTER_{cluster_id}] ✓ TF-IDF keywords extracted: {len(tfidf_keywords)} keywords")
        except Exception as e:
            print(f"[CLUSTER_{cluster_id}] ❌ TF-IDF extraction failed: {e}")
            tfidf_keywords = []

        try:
            subcategory = topic_future.result()
            print(f"[CLUSTER_{cluster_id}] ✓ Topic label generated: '{subcategory}'")
        except Exception as e:
            print(f"[CLUSTER_{cluster_id}] ❌ Topic labeling failed: {e}")
            subcategory = ""

        try:
            category = category_future.result()
            print(f"[CLUSTER_{cluster_id}] ✓ Category label generated: '{category}'")
        except Exception as e:
            print(f"[CLUSTER_{cluster_id}] ❌ Category labeling failed: {e}")
            category = "General News"

    print(
        f"[CLUSTER_{cluster_id}] Completed: category={category}, subcategory={subcategory}, "
        f"lda_keywords={len(lda_keywords)}, tfidf_keywords={len(tfidf_keywords)}"
    )

    return ClusterInfo(
        cluster_id=cluster_id,
        category=category,
        subcategory=subcategory,
        topic_summary=cluster_summary,
        articles=articles_in_cluster,
        article_ids=[art.id for art in articles_in_cluster],
        article_count=len(articles_in_cluster),
        keywords={"lda": lda_keywords, "tfidf": tfidf_keywords},
    )


@router.post("/cluster_summary", response_model=ClusterSummaryResponse)
async def cluster_summary_endpoint(payload: ClusterSummaryRequest, response: Response):
    """
    Cluster articles and generate one summary per cluster (orchestration endpoint).
    """

    # Validate input
    if not payload.articles:
        raise HTTPException(status_code=400, detail="No articles provided in request")

    if len(payload.articles) > 100:
        raise HTTPException(
            status_code=400,
            detail=f"Too many articles ({len(payload.articles)}). Maximum is 100.",
        )

    # ---- Step 1: Translate (if needed) + Summarize articles individually ----
    print(f"[CLUSTER_SUMMARY] Step 1: Translating (if needed) + summarizing {len(payload.articles)} articles...")
    logger.info(f"Translating (if needed) + summarizing {len(payload.articles)} articles...")

    article_map: Dict[str, Article] = {}
    articles_for_summarization: List[dict] = []

    for art in payload.articles:
        # Translate to English if needed (keeps payload light; only stores original_language)
        art_dict = art.model_dump() if hasattr(art, "model_dump") else art.dict()

        try:
            translated = translate_single_article(art_dict)
        except ValueError as e:
            # Fallback: do not crash the whole request; treat as English (no translation)
            logger.warning(f"[CLUSTER_SUMMARY] Translation unsupported for article id={getattr(art, 'id', None)}: {e}")
            translated = dict(art_dict)
            translated["language"] = "en"
            translated["original_language"] = (art_dict.get("language") or "en")

        title_en = translated.get("title", "") or ""
        body_en = translated.get("body", "") or ""
        lang_en = translated.get("language", "en") or "en"

        text = f"{title_en}. {body_en}".strip() if title_en else body_en.strip()
        if not text:
            continue  # Skip empty articles

        # Create an in-memory Article object with EN fields for downstream usage
        art_en = deepcopy(art)
        art_en.title = title_en
        art_en.body = body_en
        art_en.language = lang_en  # should be "en"

        # If Article schema supports original_language, set it for frontend/reference
        if hasattr(art_en, "original_language"):
            setattr(art_en, "original_language", translated.get("original_language", "en"))

        article_map[art_en.id] = art_en

        articles_for_summarization.append(
            {
                "id": art_en.id,
                "text": text,
                "title": art_en.title,
                "body": art_en.body,
            }
        )

    # ✅ Important: avoid calling summarizer on empty inputs
    if not articles_for_summarization:
        raise HTTPException(
            status_code=400,
            detail="No valid articles found after processing (all articles are empty)",
        )

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

    print(f"[CLUSTER_SUMMARY] Summarized {len(summarized_articles)} articles")
    logger.info(f"Summarized {len(summarized_articles)} articles")

    # Create mapping from article ID to summary
    article_id_to_summary: Dict[str, str] = {}
    for art_summary in summarized_articles:
        article_id = art_summary.get("id")
        summary = art_summary.get("summary", "") or ""
        if not summary:
            # Fallback to original text if summary failed
            for orig in articles_for_summarization:
                if orig.get("id") == article_id:
                    summary = orig.get("text", "") or ""
                    break
        if article_id:
            article_id_to_summary[article_id] = summary

    # ---- Step 2: Prepare summarized articles for clustering ----
    article_list_for_clustering: List[dict] = []
    for art_summary in summarized_articles:
        article_id = art_summary.get("id")
        if not article_id:
            continue
        summary = article_id_to_summary.get(article_id, "")
        if summary:
            # ✅ Force language="en" so clustering pipeline won't try to translate again
            article_list_for_clustering.append(
                {
                    "id": article_id,
                    "text": summary,
                    "language": "en",
                }
            )

    # ---- Step 3: Cluster article summaries ----
    try:
        print(f"[CLUSTER_SUMMARY] Step 2: Clustering {len(article_list_for_clustering)} article summaries...")
        logger.info(f"Clustering {len(article_list_for_clustering)} article summaries...")
        clusters = cluster_articles(article_list_for_clustering, method="hdbscan")
        print(f"[CLUSTER_SUMMARY] Found {len(clusters)} clusters")
        logger.info(f"Found {len(clusters)} clusters")
    except Exception as e:
        logger.error(f"Clustering failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")

    if not clusters:
        return ClusterSummaryResponse(
            request_id=payload.request_id,
            summary_type="cluster_summary",
            cluster_count=0,
            clusters=[],
            processed_at=datetime.utcnow().isoformat(),
        )

    # ---- Process clusters in parallel for better performance ----
    loop = asyncio.get_event_loop()

    with ThreadPoolExecutor(max_workers=min(5, len(clusters))) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                _process_single_cluster_with_keywords,
                cluster,
                article_list_for_clustering,
                article_map,
            )
            for cluster in clusters
        ]

        print(f"[CLUSTER_SUMMARY] Processing {len(tasks)} clusters in parallel...")
        logger.info(f"Processing {len(tasks)} clusters in parallel...")

        try:
            cluster_results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Cluster processing failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Cluster processing failed: {str(e)}")

        valid_results = []
        for i, result in enumerate(cluster_results):
            if isinstance(result, Exception):
                logger.error(f"Cluster {i} processing failed: {result}", exc_info=True)
                continue
            if result is not None:
                valid_results.append(result)

        print(f"[CLUSTER_SUMMARY] All clusters processed. Returning {len(valid_results)} results")
        logger.info(f"All clusters processed. {len(valid_results)}/{len(cluster_results)} succeeded")

    # Add keep-alive headers for long-running requests
    response.headers["Connection"] = "keep-alive"
    response.headers["Keep-Alive"] = "timeout=1800, max=1000"

    return ClusterSummaryResponse(
        request_id=payload.request_id,
        summary_type="cluster_summary",
        cluster_count=len(valid_results),
        clusters=valid_results,
        processed_at=datetime.utcnow().isoformat(),
    )
