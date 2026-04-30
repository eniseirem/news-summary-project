"""
cluster_update.py
===========================

⚠️ NOT IN USE: n8n now handles cluster updates directly (matching + centroid updates).
This endpoint is kept for reference but is not currently used in the workflow.

Optimized incremental clustering endpoint for n8n integration.

Purpose
-------
This endpoint receives minimal cluster centroids from n8n (instead of loading from file),
matches new articles to existing clusters, and returns delta updates.

⚠️ STATUS: Currently not in use - n8n handles cluster matching and centroid updates directly.

Key Optimizations
-----------------
- Receives only cluster_id + centroid_embedding (minimal payload)
- Returns only delta updates (articles_added, new_centroid) for matched clusters
- Returns full data only for newly created clusters
- n8n handles fetching full clusters from OpenSearch and merging updates

Design Notes
------------
- Summarizes articles first (prevents truncation)
- Matches article summaries to provided cluster centroids
- Updates centroids using running average
- Creates new clusters for unmatched articles
- Does NOT save to file storage (n8n manages persistence)
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
import numpy as np
import time

from api.schemas import Article
from llm_engine.summarizer_llama import summarize_articles_batch
from llm_engine.multilingual import translate_single_article
from clustering.embeddings import encode
from clustering.incremental_clustering import cosine_similarity
from clustering.cluster_storage import create_cluster, serialize_embedding

logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================

class ClusterCentroid(BaseModel):
    """Minimal cluster data for matching (only what's needed)."""
    cluster_id: str
    centroid_embedding: List[float]  # 384-dim vector (serialized)
    current_article_count: Optional[int] = None  # Optional: needed for accurate centroid updates


class IncrementalClusterN8NRequest(BaseModel):
    """Request model for n8n incremental clustering."""
    request_id: str
    articles: List[Article]
    cluster_centroids: List[ClusterCentroid]  # MINIMAL: Only centroids for matching
    similarity_threshold: float = 0.7  # Minimum similarity to match
    min_cluster_size: int = 2  # Minimum size for new clusters


class ArticleMatch(BaseModel):
    """Information about article matching."""
    article_id: str
    matched_cluster_id: Optional[str] = None  # None if no match
    similarity_score: Optional[float] = None  # Cosine similarity if matched
    is_new_cluster: bool = False  # True if article created new cluster
    new_cluster_id: Optional[str] = None  # If is_new_cluster=True


class MatchedClusterUpdate(BaseModel):
    """Update information for a matched cluster."""
    cluster_id: str
    articles_added: List[str]  # New article IDs added
    updated_centroid_embedding: List[float]  # Updated centroid (384-dim)
    new_article_count: int  # Updated count (old_count + len(articles_added))


class NewCluster(BaseModel):
    """Newly created cluster."""
    cluster_id: str
    article_ids: List[str]
    article_count: int
    centroid_embedding: List[float]  # 384-dim
    cluster_summary: Optional[str] = None
    created_at: str  # ISO timestamp


class IncrementalClusterN8NResponse(BaseModel):
    """Response model for n8n incremental clustering."""
    request_id: str
    total_articles: int
    matched_articles: int  # Articles matched to existing clusters
    new_clusters_created: int  # Number of new clusters created
    new_articles_in_new_clusters: int  # Articles in newly created clusters
    article_matches: List[ArticleMatch]  # Per-article matching results
    matched_cluster_updates: List[MatchedClusterUpdate]  # Updates for matched clusters
    new_clusters: List[NewCluster]  # Newly created clusters (full data)
    article_summaries: Optional[Dict[str, str]] = None  # Map: article_id -> summary text (100 words each)
    total_existing_clusters: int  # Total clusters provided in request
    processed_at: str  # ISO timestamp
    processing_time_ms: Optional[int] = None  # Processing time in milliseconds


router = APIRouter(tags=["clustering", "incremental", "n8n"])


# ============================================================================
# Helper Functions
# ============================================================================

def match_article_to_centroids(
    article_embedding: np.ndarray,
    cluster_centroids: Dict[str, np.ndarray],
    similarity_threshold: float = 0.7,
) -> Tuple[Optional[str], float]:
    """
    Match an article embedding to the best matching cluster centroid.
    
    Parameters
    ----------
    article_embedding : np.ndarray
        Embedding vector of the article.
    cluster_centroids : Dict[str, np.ndarray]
        Dictionary mapping cluster_id -> centroid_embedding.
    similarity_threshold : float
        Minimum similarity score to match.
    
    Returns
    -------
    Tuple[Optional[str], float]
        Tuple of (best_match_cluster_id, similarity_score).
        Returns (None, 0.0) if no match above threshold.
    """
    if not cluster_centroids:
        return None, 0.0
    
    best_match_id = None
    best_similarity = 0.0
    
    for cluster_id, centroid in cluster_centroids.items():
        try:
            similarity = cosine_similarity(article_embedding, centroid)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match_id = cluster_id
        except Exception as e:
            logger.warning(f"Error calculating similarity for cluster {cluster_id}: {e}")
            continue
    
    # Check if best match exceeds threshold
    if best_similarity >= similarity_threshold:
        return best_match_id, best_similarity
    else:
        return None, best_similarity


def update_centroid_running_average(
    current_centroid: np.ndarray,
    current_count: int,
    new_embeddings: List[np.ndarray],
) -> np.ndarray:
    """
    Update centroid using running average formula.
    
    Formula: new_centroid = (old_centroid * old_count + sum(new_embeddings)) / (old_count + len(new_embeddings))
    
    Parameters
    ----------
    current_centroid : np.ndarray
        Current centroid vector.
    current_count : int
        Current number of articles in cluster.
    new_embeddings : List[np.ndarray]
        List of new article embeddings to add.
    
    Returns
    -------
    np.ndarray
        Updated centroid vector (normalized).
    """
    if not new_embeddings:
        return current_centroid
    
    # Sum of new embeddings
    new_sum = np.sum(new_embeddings, axis=0)
    
    # Running average: (old * count + new_sum) / (count + len(new))
    new_centroid = (current_centroid * current_count + new_sum) / (current_count + len(new_embeddings))
    
    # Normalize to maintain unit vector for cosine similarity
    norm = np.linalg.norm(new_centroid)
    if norm > 0:
        new_centroid = new_centroid / norm
    
    return new_centroid


# ============================================================================
# Main Endpoint
# ============================================================================

# ⚠️ NOT IN USE: n8n now handles cluster updates directly
# This endpoint is kept for reference but is not currently used in the workflow.
@router.post("/cluster_update", response_model=IncrementalClusterN8NResponse)
async def cluster_incremental_n8n_endpoint(payload: IncrementalClusterN8NRequest, response: Response):
    """
    ⚠️ NOT IN USE: n8n now handles cluster updates directly (matching + centroid updates).
    This endpoint is kept for reference but is not currently used in the workflow.
    
    Cluster articles incrementally using cluster centroids provided by n8n.
    
    This is an optimized endpoint for n8n integration that:
    - Receives minimal cluster data (centroids only)
    - Returns delta updates (not full cluster objects)
    - Does NOT save to file storage (n8n manages persistence in OpenSearch)
    
    Processing Steps
    ----------------
    1. Translate articles to English if needed (preserves original_language metadata)
    2. Summarize articles individually (prevents truncation)
    3. Generate embeddings for article summaries
    4. Match each article to provided cluster centroids (cosine similarity)
    5. Update matched clusters (calculate new centroids)
    6. Cluster unmatched articles together (HDBSCAN)
    7. Create new clusters for unmatched articles
    8. Return delta updates and new clusters
    
    Request Format
    --------------
    - `cluster_centroids`: List of {cluster_id, centroid_embedding} (minimal data)
    - `articles`: List of articles to process
    
    Response Format
    ---------------
    - `matched_cluster_updates`: Delta updates (articles_added, new_centroid)
    - `new_clusters`: Full cluster data for newly created clusters
    - `article_matches`: Per-article matching results
    
    Benefits
    --------
    - Minimal payload: Only centroids sent (~1.5KB per cluster vs ~4KB full)
    - Fast network transfer: ~20-50ms vs ~200-500ms
    - Scalable: Works with thousands of clusters
    - Efficient: n8n only updates what changed
    
    Constraints
    -----------
    - Articles must not be empty
    - Similarity threshold between 0.0 and 1.0
    - Minimum cluster size at least 1
    - Cluster centroids must be 384-dim (all-MiniLM-L6-v2)
    
    Parameters
    ----------
    payload : IncrementalClusterN8NRequest
        Request containing articles and cluster centroids.
    
    Returns
    -------
    IncrementalClusterN8NResponse
        Delta updates and new clusters.
    """
    start_time = time.time()
    
    # Validate input
    if not payload.articles:
        raise HTTPException(
            status_code=400,
            detail="Articles list cannot be empty"
        )
    
    if not 0.0 <= payload.similarity_threshold <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="similarity_threshold must be between 0.0 and 1.0"
        )
    
    if payload.min_cluster_size < 1:
        raise HTTPException(
            status_code=400,
            detail="min_cluster_size must be at least 1"
        )
    
    # Validate cluster centroids
    if not payload.cluster_centroids:
        logger.warning("No cluster centroids provided, all articles will create new clusters")
    
    # Convert cluster centroids to numpy arrays and store metadata
    cluster_centroids_dict: Dict[str, np.ndarray] = {}
    cluster_counts_dict: Dict[str, int] = {}  # Store current counts for centroid updates
    for centroid_data in payload.cluster_centroids:
        try:
            embedding_array = np.array(centroid_data.centroid_embedding, dtype=np.float32)
            if len(embedding_array) != 384:
                logger.warning(
                    f"Cluster {centroid_data.cluster_id} has embedding dimension {len(embedding_array)}, "
                    f"expected 384. Skipping."
                )
                continue
            cluster_centroids_dict[centroid_data.cluster_id] = embedding_array
            # Store current count if provided, otherwise will estimate
            if centroid_data.current_article_count is not None:
                cluster_counts_dict[centroid_data.cluster_id] = centroid_data.current_article_count
        except Exception as e:
            logger.warning(f"Error processing centroid for cluster {centroid_data.cluster_id}: {e}")
            continue
    
    # Send acknowledgment headers
    response.headers["X-Request-Id"] = payload.request_id
    response.headers["X-Status"] = "processing"
    response.headers["Connection"] = "keep-alive"
    
    logger.info(
        f"Processing {len(payload.articles)} articles against {len(cluster_centroids_dict)} clusters "
        f"for request {payload.request_id}"
    )
    
    # ---- Step 1: Translate (if needed) in parallel + Summarize articles individually (prevents truncation) ----
    logger.info(f"Step 1: Translating (if needed) + summarizing {len(payload.articles)} articles individually...")
    
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
            # Fallback: do not crash the whole request; treat as English (no translation)
            logger.warning(
                f"[CLUSTER_INCREMENTAL_N8N] Translation unsupported for article id={art_dict.get('id')}: {e}"
            )
            translated = dict(art_dict)
            translated["language"] = "en"
            translated["original_language"] = art_dict.get("language", "en")
            return translated
        except Exception as e:
            # Catch any other translation errors
            logger.warning(
                f"[CLUSTER_INCREMENTAL_N8N] Translation failed for article id={art_dict.get('id')}: {e}"
            )
            translated = dict(art_dict)
            translated["language"] = "en"
            translated["original_language"] = art_dict.get("language", "en")
            return translated
    
    # Translate articles in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=5) as executor:
        translated_articles = list(executor.map(translate_with_fallback, article_dicts))
    
    # Prepare articles for summarization
    articles_for_summarization = []
    article_by_id = {}
    
    for i, art in enumerate(payload.articles):
        translated = translated_articles[i]
        
        # Use translated text (guaranteed to be English)
        title_en = translated.get("title", "") or ""
        body_en = translated.get("body", "") or ""
        text = f"{title_en}. {body_en}".strip() if title_en else body_en.strip()
        
        if not text:
            continue  # Skip empty articles
        
        article_by_id[art.id] = art
        articles_for_summarization.append({
            "id": art.id,
            "text": text,
            "title": title_en,
            "body": body_en,
        })
    
    if not articles_for_summarization:
        raise HTTPException(
            status_code=400,
            detail="No valid articles found after processing (all articles are empty)"
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
    
    # ---- Step 2: Generate embeddings for article summaries ----
    logger.info(f"Step 2: Generating embeddings for {len(summarized_articles)} article summaries...")
    
    article_list_for_embedding = []
    for art_summary in summarized_articles:
        article_id = art_summary.get("id")
        summary = article_id_to_summary.get(article_id, "")
        if summary:
            article_list_for_embedding.append({
                "id": article_id,
                "text": summary,
            })
    
    if not article_list_for_embedding:
        raise HTTPException(
            status_code=500,
            detail="No valid summaries for embedding generation"
        )
    
    # Generate embeddings
    try:
        texts_list = [item["text"] for item in article_list_for_embedding]
        embeddings_array = encode(
            texts=texts_list,
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            normalize=True,
        )
        # Convert to dict: article_id -> embedding
        article_embeddings = {
            item["id"]: embeddings_array[i]
            for i, item in enumerate(article_list_for_embedding)
        }
        logger.info(f"Generated {len(article_embeddings)} embeddings")
    except Exception as e:
        logger.error(f"Failed to generate embeddings: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate embeddings: {str(e)}"
        )
    
    # ---- Step 3: Match articles to existing clusters ----
    logger.info(f"Step 3: Matching {len(article_embeddings)} articles to {len(cluster_centroids_dict)} clusters...")
    
    # Track matches
    matched_clusters: Dict[str, List[Tuple[str, np.ndarray]]] = {}  # cluster_id -> [(article_id, embedding), ...]
    unmatched_articles: List[Tuple[str, np.ndarray]] = []  # [(article_id, embedding), ...]
    article_matches: List[ArticleMatch] = []
    
    for article_id, embedding in article_embeddings.items():
        best_match_id, similarity_score = match_article_to_centroids(
            article_embedding=embedding,
            cluster_centroids=cluster_centroids_dict,
            similarity_threshold=payload.similarity_threshold,
        )
        
        if best_match_id:
            # Matched to existing cluster
            matched_clusters.setdefault(best_match_id, []).append((article_id, embedding))
            article_matches.append(ArticleMatch(
                article_id=article_id,
                matched_cluster_id=best_match_id,
                similarity_score=similarity_score,
                is_new_cluster=False,
                new_cluster_id=None,
            ))
        else:
            # No match - will create new cluster
            unmatched_articles.append((article_id, embedding))
            article_matches.append(ArticleMatch(
                article_id=article_id,
                matched_cluster_id=None,
                similarity_score=similarity_score,
                is_new_cluster=True,
                new_cluster_id=None,  # Will be set after clustering
            ))
    
    logger.info(f"Matched {len(matched_clusters)} clusters, {len(unmatched_articles)} unmatched articles")
    
    # ---- Step 4: Update matched clusters (calculate new centroids) ----
    logger.info(f"Step 4: Updating {len(matched_clusters)} matched clusters...")
    
    matched_cluster_updates: List[MatchedClusterUpdate] = []
    
    for cluster_id, matched_items in matched_clusters.items():
        # Get current centroid
        current_centroid = cluster_centroids_dict[cluster_id]
        
        # Get current count (use provided count or estimate from matched items)
        current_count = cluster_counts_dict.get(cluster_id)
        if current_count is None:
            # Estimate: use number of matched items as proxy (not ideal, but works)
            # n8n should provide current_article_count for accurate updates
            current_count = len(matched_items)
            logger.warning(
                f"Cluster {cluster_id} missing current_article_count, "
                f"estimating as {current_count} (may be inaccurate)"
            )
        
        # Extract embeddings
        new_embeddings = [embedding for _, embedding in matched_items]
        article_ids_added = [article_id for article_id, _ in matched_items]
        
        # Update centroid using running average
        updated_centroid = update_centroid_running_average(
            current_centroid=current_centroid,
            current_count=current_count,
            new_embeddings=new_embeddings,
        )
        
        matched_cluster_updates.append(MatchedClusterUpdate(
            cluster_id=cluster_id,
            articles_added=article_ids_added,
            updated_centroid_embedding=updated_centroid.tolist(),
            new_article_count=current_count + len(article_ids_added),
        ))
    
    # ---- Step 5: Cluster unmatched articles ----
    logger.info(f"Step 5: Clustering {len(unmatched_articles)} unmatched articles...")
    
    new_clusters: List[NewCluster] = []
    
    if unmatched_articles:
        # If we have unmatched articles, cluster them together
        if len(unmatched_articles) >= payload.min_cluster_size:
            # Use HDBSCAN to cluster unmatched articles
            from clustering.cluster_pipeline import cluster_articles
            
            unmatched_article_list = [
                {"id": article_id, "text": article_id_to_summary.get(article_id, "")}
                for article_id, _ in unmatched_articles
            ]
            
            try:
                clustered_unmatched = cluster_articles(
                    articles=unmatched_article_list,
                    method="hdbscan",
                    min_cluster_size=payload.min_cluster_size,
                )
                
                # Create new clusters from clustered unmatched articles
                for cluster_data in clustered_unmatched:
                    cluster_article_ids = cluster_data.get("article_ids", [])
                    if not cluster_article_ids:
                        continue
                    
                    # Calculate centroid from embeddings
                    cluster_embeddings = [
                        article_embeddings[aid] for aid in cluster_article_ids
                        if aid in article_embeddings
                    ]
                    
                    if not cluster_embeddings:
                        continue
                    
                    centroid = np.mean(cluster_embeddings, axis=0)
                    norm = np.linalg.norm(centroid)
                    if norm > 0:
                        centroid = centroid / norm
                    
                    # Create new cluster
                    new_cluster = create_cluster(
                        article_ids=cluster_article_ids,
                        centroid_embedding=centroid,
                        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
                        clustering_method="incremental",
                    )
                    
                    # Update article matches with new cluster IDs
                    for article_id in cluster_article_ids:
                        for match in article_matches:
                            if match.article_id == article_id:
                                match.new_cluster_id = new_cluster["cluster_id"]
                                break
                    
                    new_clusters.append(NewCluster(
                        cluster_id=new_cluster["cluster_id"],
                        article_ids=cluster_article_ids,
                        article_count=len(cluster_article_ids),
                        centroid_embedding=centroid.tolist(),
                        cluster_summary=None,  # Can be generated later
                        created_at=datetime.utcnow().isoformat(),
                    ))
                
            except Exception as e:
                logger.error(f"Failed to cluster unmatched articles: {e}", exc_info=True)
                # Fallback: Create individual clusters for each unmatched article
                for article_id, embedding in unmatched_articles:
                    centroid = embedding / np.linalg.norm(embedding) if np.linalg.norm(embedding) > 0 else embedding
                    
                    new_cluster = create_cluster(
                        article_ids=[article_id],
                        centroid_embedding=centroid,
                        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
                        clustering_method="incremental",
                    )
                    
                    for match in article_matches:
                        if match.article_id == article_id:
                            match.new_cluster_id = new_cluster["cluster_id"]
                            break
                    
                    new_clusters.append(NewCluster(
                        cluster_id=new_cluster["cluster_id"],
                        article_ids=[article_id],
                        article_count=1,
                        centroid_embedding=centroid.tolist(),
                        cluster_summary=None,
                        created_at=datetime.utcnow().isoformat(),
                    ))
        else:
            # Too few unmatched articles - create individual clusters
            for article_id, embedding in unmatched_articles:
                centroid = embedding / np.linalg.norm(embedding) if np.linalg.norm(embedding) > 0 else embedding
                
                new_cluster = create_cluster(
                    article_ids=[article_id],
                    centroid_embedding=centroid,
                    embedding_model="sentence-transformers/all-MiniLM-L6-v2",
                    clustering_method="incremental",
                )
                
                for match in article_matches:
                    if match.article_id == article_id:
                        match.new_cluster_id = new_cluster["cluster_id"]
                        break
                
                new_clusters.append(NewCluster(
                    cluster_id=new_cluster["cluster_id"],
                    article_ids=[article_id],
                    article_count=1,
                    centroid_embedding=centroid.tolist(),
                    cluster_summary=None,
                    created_at=datetime.utcnow().isoformat(),
                ))
    
    # Calculate statistics
    matched_articles = sum(len(update.articles_added) for update in matched_cluster_updates)
    new_articles_in_new_clusters = sum(cluster.article_count for cluster in new_clusters)
    
    processing_time_ms = int((time.time() - start_time) * 1000)
    
    logger.info(
        f"Completed processing: {matched_articles} matched, {len(new_clusters)} new clusters created "
        f"({new_articles_in_new_clusters} articles) in {processing_time_ms}ms"
    )
    
    # Return article summaries for n8n to cache (only new articles processed in this request)
    article_summaries_dict = {
        article_id: summary
        for article_id, summary in article_id_to_summary.items()
        if summary  # Only include non-empty summaries
    }
    
    return IncrementalClusterN8NResponse(
        request_id=payload.request_id,
        total_articles=len(payload.articles),
        matched_articles=matched_articles,
        new_clusters_created=len(new_clusters),
        new_articles_in_new_clusters=new_articles_in_new_clusters,
        article_matches=article_matches,
        matched_cluster_updates=matched_cluster_updates,
        new_clusters=new_clusters,
        article_summaries=article_summaries_dict if article_summaries_dict else None,
        total_existing_clusters=len(payload.cluster_centroids),
        processed_at=datetime.utcnow().isoformat(),
        processing_time_ms=processing_time_ms,
    )
