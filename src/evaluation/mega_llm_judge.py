"""
llm_judge.py
============

Script to generate cluster summaries and mega summaries for LLM judge evaluation.

Usage:
    python -m evaluation.llm_judge --input_file data/input/llm_judge_eval/batch_001.json --batch_id 001
    python -m evaluation.llm_judge --input_dir data/input/llm_judge_eval --batch_range 001 010
"""

import json
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, cast
from datetime import datetime
import sys
import os

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.schemas import Article
from llm_engine.summarizer_llama import summarize_cluster_with_llama, summarize_mega_with_llama
from clustering.cluster_pipeline import cluster_articles
from topic_labeling.llama_lda_pipeline import generate_cluster_label_with_llama
from topic_labeling.llama_topic_labeler import generate_cluster_topic_label
from concurrent.futures import ThreadPoolExecutor


def _process_single_cluster(
    cluster: dict,
    article_list_for_clustering: List[dict],
    article_by_id: dict,
    cluster_index: Optional[int] = None,
    total_clusters: Optional[int] = None,
    skip_topic_labels: bool = False,
    skip_category_labels: bool = False,
    max_cluster_articles: Optional[int] = None,
) -> Optional[dict]:
    """Process a single cluster synchronously (for use in thread pool)."""
    import time
    start_time = time.time()
    
    cluster_id = cluster["cluster_id"]
    # Support both 'article_ids' and 'article_urls' for backward compatibility
    article_ids = cluster.get("article_ids") or cluster.get("article_urls", [])
    
    progress_str = f"[{cluster_index}/{total_clusters}]" if cluster_index is not None else ""
    print(f"📦 {progress_str} CLUSTER_{cluster_id}: Starting ({len(article_ids)} articles)")

    # Skip clusters that exceed the article limit (don't process or include in output)
    if max_cluster_articles and len(article_ids) > max_cluster_articles:
        print(f"   └─ ⚠️ Skipping cluster (too large: {len(article_ids)} articles > {max_cluster_articles} limit)")
        return None  # Return None to indicate this cluster should be excluded

    # Combine article texts for this cluster
    print(f"   └─ Combining texts from {len(article_ids)} articles...")
    cluster_texts = [
        a["text"]
        for a in article_list_for_clustering
        if (a.get("id") or a.get("url")) in article_ids
    ]
    combined_text = " ".join(cluster_texts)
    text_length = len(combined_text)
    print(f"   └─ Combined text length: {text_length:,} characters")

    # Generate cluster summary (must complete first)
    print(f"   └─ Generating cluster summary with LLaMA...")
    summary_start = time.time()
    try:
        cluster_summary = summarize_cluster_with_llama(
            text=str(combined_text),
            language="en",
        )
        summary_time = time.time() - summary_start
        print(f"   └─ ✓ Summary generated ({summary_time:.1f}s, {len(cluster_summary):,} chars)")
        
        # Check if summary generation failed (returned error message)
        if cluster_summary.startswith("[") and ("failed" in cluster_summary.lower() or "error" in cluster_summary.lower()):
            print(f"   └─ ⚠️ Summary generation returned error, using fallback...")
            cluster_summary = f"[Cluster summary generation failed for cluster {cluster_id} - content may be too large]"
    except Exception as e:
        summary_time = time.time() - summary_start
        print(f"   └─ ⚠️ Summary generation failed after {summary_time:.1f}s: {e}")
        print(f"   └─ ⚠️ Using fallback summary for cluster {cluster_id}...")
        # Create a minimal fallback summary
        cluster_summary = f"[Cluster summary generation failed for cluster {cluster_id} - {len(article_ids)} articles, content may be too large for processing]"

    # Run topic label and category label in parallel (both depend on summary)
    import concurrent.futures
    
    label_start = time.time()
    
    # Skip label generation if summary failed
    if cluster_summary.startswith("[") and ("failed" in cluster_summary.lower()):
        topic_label = ""
        category_label = "General News"
        label_time = 0
        print(f"   └─ ⚠️ Skipping label generation (summary generation failed)")
    elif skip_category_labels and skip_topic_labels:
        # Skip all labels
        topic_label = ""
        category_label = "General News"
        label_time = 0
        print(f"   └─ ⚠️ Skipping all label generation (topic and category labels skipped)")
    elif skip_category_labels:
        # Skip category labels, only generate topic label
        category_label = "General News"
        print(f"   └─ Generating topic label only (category labels skipped)...")
        try:
            topic_label = generate_cluster_topic_label(cluster_summary=cluster_summary)
            if not topic_label:
                raise ValueError("Topic label generation returned empty result")
        except Exception as e:
            error_msg = str(e) if e else "Unknown error"
            error_type = type(e).__name__
            print(f"   └─ ⚠️ Topic label generation failed ({error_type}): {error_msg}")
            # Re-raise to ensure the error is visible and not silently ignored
            raise RuntimeError(f"Failed to generate topic label: {error_msg}") from e
        label_time = time.time() - label_start
    elif skip_topic_labels:
        # Skip topic labels, only generate category label
        topic_label = ""
        print(f"   └─ Generating category label only (topic labels skipped)...")
        try:
            category_label = generate_cluster_label_with_llama(
                cluster_summary=cluster_summary,
                article_count=len(article_list_for_clustering),
                use_lda=True,
                is_noise_cluster=(cluster_id == -1),
            )
        except Exception as e:
            print(f"   └─ ⚠️ Category label generation failed: {e}")
            category_label = "General News"
        label_time = time.time() - label_start
    else:
        # Generate both labels in parallel
        print(f"   └─ Generating topic and category labels in parallel...")
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                topic_future = executor.submit(
                    lambda: generate_cluster_topic_label(cluster_summary=cluster_summary)
                )
                category_future = executor.submit(
                    lambda: generate_cluster_label_with_llama(
                        cluster_summary=cluster_summary,
                        article_count=len(article_list_for_clustering),
                        use_lda=True,
                        is_noise_cluster=(cluster_id == -1),
                    )
                )
                
                try:
                    # Timeout accounts for retries: 30s per attempt * 3 attempts + buffer = 120s
                    topic_label = topic_future.result(timeout=120)
                    if not topic_label or topic_label == "Miscellaneous":
                        print(f"   └─ ⚠️ Topic label generation returned empty/invalid result")
                        topic_label = ""
                except Exception as e:
                    error_msg = str(e) if e else "Unknown error"
                    error_type = type(e).__name__
                    print(f"   └─ ⚠️ Topic label generation failed ({error_type}): {error_msg}")
                    topic_label = ""
                
                try:
                    category_label = category_future.result(timeout=60)  # 1 min timeout (reduced from 5 min)
                except Exception as e:
                    print(f"   └─ ⚠️ Category label generation failed: {e}")
                    category_label = "General News"
        except Exception as e:
            print(f"   └─ ⚠️ Label generation failed: {e}")
            topic_label = ""
            category_label = "General News"
        label_time = time.time() - label_start
    total_time = time.time() - start_time
    topic_display = f" - Topic: {topic_label}" if topic_label else ""
    print(f"   └─ ✓ Labels generated ({label_time:.1f}s) - Category: {category_label}{topic_display}")
    print(f"   └─ ✓ CLUSTER_{cluster_id} completed in {total_time:.1f}s\n")

    return {
        "cluster_id": cluster_id,
        "category": category_label,
        "summary": cluster_summary,
        "topic_label": topic_label,
        "article_count": len(article_ids),
    }


async def process_articles(
    articles: List[Article],
    article_batch_id: str,
    output_path: Optional[Path] = None,  # Optional: for saving partial results
    skip_topic_labels: bool = False,
    skip_category_labels: bool = False,
    max_workers: int = 5,
    max_cluster_articles: Optional[int] = 50,  # Skip clusters with more than this many articles (default: 50)
) -> Dict[str, Any]:
    """
    Process articles to generate cluster summaries and mega summary.
    
    Returns:
        Dictionary with cluster_summaries and mega_summary in the format:
        {
            "article_batch_id": "...",
            "cluster_summaries": {
                "cluster_1": {"category": "...", "summary": "..."},
                "cluster_2": {"category": "...", "summary": "..."},
                ...
            },
            "mega_summary": {"summary": "..."}
        }
    """
    import time
    pipeline_start = time.time()
    
    print(f"\n{'='*60}")
    print(f"🚀 Processing batch: {article_batch_id}")
    print(f"📄 Total articles: {len(articles)}")
    print(f"{'='*60}\n")

    # Stage 1: Prepare articles for clustering
    print(f"📋 Stage 1/4: Preparing articles for clustering...")
    prep_start = time.time()
    article_by_id = {}
    article_list_for_clustering = []

    for i, art in enumerate(articles, 1):
        text = f"{art.title}. {art.body}".strip() if art.title else art.body.strip()
        article_by_id[art.id] = art
        article_list_for_clustering.append({
            "id": art.id,
            "text": text,
        })
        if i % 50 == 0 or i == len(articles):
            print(f"   └─ Prepared {i}/{len(articles)} articles...")
    
    prep_time = time.time() - prep_start
    print(f"   └─ ✓ Preparation complete ({prep_time:.1f}s)\n")

    # Stage 2: Cluster articles
    print(f"🔗 Stage 2/4: Clustering articles...")
    cluster_start = time.time()
    print(f"   └─ Generating embeddings and clustering {len(article_list_for_clustering)} articles...")
    
    # Try HDBSCAN first
    min_cluster_size = 2
    clusters = cluster_articles(
        article_list_for_clustering, 
        method="hdbscan",
        min_cluster_size=min_cluster_size
    )
    
    cluster_time = time.time() - cluster_start
    total_clustered = sum(len(c.get("article_ids") or c.get("article_urls", [])) for c in clusters)
    
    # If HDBSCAN produces too few clusters (1 or 2), fallback to KMeans
    num_articles = len(article_list_for_clustering)
    min_expected_clusters = max(3, int(num_articles / 50))  # At least 3, or ~1 cluster per 50 articles
    
    if len(clusters) < min_expected_clusters and num_articles >= 10:
        print(f"   └─ ⚠️  HDBSCAN found only {len(clusters)} cluster(s), expected at least {min_expected_clusters}")
        print(f"   └─ Switching to KMeans for better cluster granularity...")
        
        # Use KMeans with a reasonable number of clusters
        # Heuristic: sqrt of article count, but between 5 and 20
        import math
        n_clusters = max(5, min(20, int(math.sqrt(num_articles))))
        print(f"   └─ Using KMeans with {n_clusters} clusters...")
        
        clusters = cluster_articles(
            article_list_for_clustering,
            method="kmeans",
            n_clusters=n_clusters
        )
        
        cluster_time = time.time() - cluster_start
        total_clustered = sum(len(c.get("article_ids") or c.get("article_urls", [])) for c in clusters)
        
        # If KMeans also produces too few clusters, document it for evaluation
        if len(clusters) < min_expected_clusters:
            print(f"   └─ ⚠️  KMeans also found only {len(clusters)} cluster(s)")
            print(f"   └─ ⚠️  Articles appear to be semantically very similar or duplicate")
            print(f"   └─ ⚠️  This is valuable evaluation data - clustering quality may be limited")
            print(f"   └─ ✓ Using {len(clusters)} cluster(s) as found by clustering algorithms")
            print(f"   └─ Found {len(clusters)} clusters ({total_clustered}/{len(article_list_for_clustering)} articles clustered)\n")
        else:
            print(f"   └─ ✓ KMeans clustering complete ({cluster_time:.1f}s)")
            print(f"   └─ Found {len(clusters)} clusters ({total_clustered}/{len(article_list_for_clustering)} articles clustered)\n")
    else:
        print(f"   └─ ✓ Clustering complete ({cluster_time:.1f}s)")
        print(f"   └─ Found {len(clusters)} clusters ({total_clustered}/{len(article_list_for_clustering)} articles clustered)\n")
    
    if total_clustered != len(article_list_for_clustering):
        print(f"⚠️  Warning: {len(article_list_for_clustering) - total_clustered} articles not assigned to clusters!\n")

    if not clusters:
        return {
            "article_batch_id": article_batch_id,
            "cluster_summaries": {},
            "mega_summary": {"summary": ""},
        }

    # Stage 3: Process clusters in parallel
    print(f"📝 Stage 3/4: Processing {len(clusters)} clusters...")
    process_start = time.time()
    loop = asyncio.get_event_loop()
    
    # Use configurable max_workers (default 5 to balance speed and Ollama load)
    actual_workers = min(max_workers, len(clusters))
    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                _process_single_cluster,
                cluster,
                article_list_for_clustering,
                article_by_id,
                i + 1,  # cluster_index
                len(clusters),  # total_clusters
                skip_topic_labels,  # skip_topic_labels flag
                skip_category_labels,  # skip_category_labels flag
                max_cluster_articles,  # max_cluster_articles limit
            )
            for i, cluster in enumerate(clusters)
        ]
        
        print(f"   └─ Processing {len(tasks)} clusters in parallel (max {actual_workers} concurrent)...")
        # Use return_exceptions=True to catch exceptions and continue processing
        cluster_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    process_time = time.time() - process_start
    print(f"   └─ ✓ All clusters processed ({process_time:.1f}s)\n")

    # Save partial results after clustering (in case we crash later)
    if output_path:
        try:
            partial_results = {
                "article_batch_id": article_batch_id,
                "total_articles": len(articles),
                "cluster_count": len(clusters),
                "status": "processing",
                "cluster_summaries": {},
                "mega_summary": {"summary": "[Processing in progress...]"},
            }
            save_results(partial_results, output_path)
        except Exception:
            pass  # Don't fail if we can't save partial results

    # Format cluster summaries
    print(f"📊 Formatting cluster summaries...")
    cluster_summaries = {}
    all_cluster_summaries_text = []
    total_articles_in_clusters = 0
    failed_clusters = 0
    skipped_clusters = 0
    
    # Filter out None results (skipped clusters) and track cluster numbering
    valid_results = []
    cluster_number = 1
    for result in cluster_results:
        if result is None:
            skipped_clusters += 1
            continue  # Skip None results (clusters that exceeded article limit)
        valid_results.append((cluster_number, result))
        cluster_number += 1
    
    if skipped_clusters > 0:
        print(f"   └─ ⚠️ Skipped {skipped_clusters} cluster(s) that exceeded article limit")
    
    for cluster_num, result in valid_results:
        # Handle exceptions from async gather
        if isinstance(result, Exception):
            print(f"   └─ ⚠️ Cluster {cluster_num} raised exception: {result}")
            failed_clusters += 1
            cluster_key = f"cluster_{cluster_num}"
            cluster_summaries[cluster_key] = {
                "category": "General News",
                "topic_label": "",
                "summary": f"[Cluster processing failed with exception: {str(result)[:100]}]",
                "article_count": 0,
                "status": "failed",
            }
            continue
        
        # Type assertion: after exception check, result is guaranteed to be a dict
        cluster_data = cast(Dict[str, Any], result)
        cluster_key = f"cluster_{cluster_num}"
        summary = cluster_data["summary"]
        
        # Skip clusters with failed summaries for mega summary (but keep them in output)
        is_failed = summary.startswith("[") and ("failed" in summary.lower() or "error" in summary.lower())
        if is_failed:
            failed_clusters += 1
        
        cluster_summaries[cluster_key] = {
            "category": cluster_data["category"],
            "topic_label": cluster_data.get("topic_label", ""),
            "summary": summary,
            "article_count": cluster_data["article_count"],
            "status": "failed" if is_failed else "success",
        }
        
        # Only include successful summaries in mega summary
        if not is_failed:
            all_cluster_summaries_text.append(summary)
        
        total_articles_in_clusters += cluster_data["article_count"]
        topic_display = f" - {cluster_data.get('topic_label', '')}" if cluster_data.get("topic_label") else ""
        status_indicator = " ⚠️" if is_failed else ""
        print(f"   └─ {'⚠️' if is_failed else '✓'} {cluster_key}: {cluster_data['category']}{topic_display} ({cluster_data['article_count']} articles){status_indicator}")
    
    if failed_clusters > 0:
        print(f"\n   ⚠️ Warning: {failed_clusters} cluster(s) failed to generate summaries (likely due to timeout)")
        print(f"   └─ These clusters will be excluded from mega summary but included in output")
    
    if skipped_clusters > 0:
        print(f"\n   ⚠️ Info: {skipped_clusters} cluster(s) skipped (exceeded {max_cluster_articles if max_cluster_articles else 'N/A'} article limit)")
        print(f"   └─ Skipped clusters are excluded from output and mega summary")
    
    print(f"\n📊 Summary: {len(articles)} input articles → {len(cluster_summaries)} clusters ({total_articles_in_clusters} articles in clusters)")
    if total_articles_in_clusters != len(articles):
        print(f"⚠️  Warning: {len(articles) - total_articles_in_clusters} articles not assigned to any cluster!")

    # Stage 4: Generate mega summary
    print(f"\n🎯 Stage 4/4: Generating mega summary...")
    mega_start = time.time()
    mega_summary_text = ""
    mega_summary_error = None
    mega_time = 0  # Initialize in case mega summary is skipped
    
    if all_cluster_summaries_text:
        combined_length = sum(len(s) for s in all_cluster_summaries_text)
        print(f"   └─ Combining {len(cluster_summaries)} cluster summaries ({combined_length:,} total chars)...")
        combined_summaries = "\n\n".join(all_cluster_summaries_text)
        
        print(f"   └─ Generating mega summary with LLaMA...")
        try:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                mega_summary_text = await loop.run_in_executor(
                    executor,
                    summarize_mega_with_llama,
                    combined_summaries,
                    len(cluster_summaries),
                    "en",
                )
            
            mega_time = time.time() - mega_start
            print(f"   └─ ✓ Mega summary generated ({mega_time:.1f}s, {len(mega_summary_text):,} chars)\n")
        except Exception as e:
            mega_time = time.time() - mega_start
            mega_summary_error = str(e)
            print(f"   └─ ⚠️ Mega summary generation failed after {mega_time:.1f}s: {e}")
            print(f"   └─ ⚠️ Saving partial results with cluster summaries only...")
            # Use a fallback: combine first few cluster summaries as placeholder
            if len(all_cluster_summaries_text) > 0:
                # Take first 3 cluster summaries and combine them as fallback
                fallback_text = "\n\n".join(all_cluster_summaries_text[:min(3, len(all_cluster_summaries_text))])
                mega_summary_text = f"[Mega summary generation failed - using partial cluster summaries]\n\n{fallback_text[:500]}..."
            else:
                mega_summary_text = "[Mega summary generation failed - no cluster summaries available]"
            print(f"   └─ ⚠️ Using fallback summary ({len(mega_summary_text):,} chars)\n")
    
    total_time = time.time() - pipeline_start
    print(f"{'='*60}")
    print(f"✅ Pipeline complete in {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"{'='*60}\n")

    # Add metadata about clustering quality
    clustering_quality = "good" if len(cluster_summaries) >= min_expected_clusters else "limited"
    
    # Calculate stage times
    stage_times = {
        "preparation": prep_time,
        "clustering": cluster_time,
        "cluster_processing": process_time,
        "mega_summary": mega_time,
    }
    
    result = {
        "article_batch_id": article_batch_id,
        "total_articles": len(articles),  # Total articles in the batch
        "cluster_count": len(cluster_summaries),
        "clustering_quality": clustering_quality,  # "good" or "limited" - indicates if clustering found expected number of clusters
        "cluster_summaries": cluster_summaries,
        "mega_summary": {
            "summary": mega_summary_text,
        },
        "stage_times": stage_times,  # Add stage timing information
    }
    
    # Add error information if mega summary failed
    if mega_summary_error:
        result["mega_summary"]["error"] = mega_summary_error
        result["mega_summary"]["status"] = "partial"
    else:
        result["mega_summary"]["status"] = "complete"
    
    return result


def load_articles_from_json(file_path: Path) -> List[Article]:
    """Load articles from JSON file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle different input formats
    if isinstance(data, list):
        articles = data
    elif isinstance(data, dict) and "articles" in data:
        articles = data["articles"]
    else:
        raise ValueError(f"Unexpected JSON format in {file_path}")
    
    print(f"📄 Loaded {len(articles)} articles from {file_path.name}")
    
    # Validate articles
    valid_articles = []
    for i, article in enumerate(articles):
        try:
            art = Article(**article)
            valid_articles.append(art)
        except Exception as e:
            print(f"⚠️  Skipping invalid article {i+1}: {e}")
    
    print(f"✓ {len(valid_articles)} valid articles ready for processing\n")
    return valid_articles


def save_results(results: Dict[str, Any], output_path: Path):
    """Save results to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Results saved to: {output_path}")


async def process_single_file(
    input_file: Path, 
    batch_id: str, 
    output_dir: Path, 
    skip_topic_labels: bool = False,
    skip_category_labels: bool = False,
    max_workers: int = 5,
    max_cluster_articles: Optional[int] = 50,
):
    """Process a single input file."""
    output_filename = f"{batch_id}_mega_summary.json"
    output_path = output_dir / output_filename
    
    try:
        # Load articles
        articles = load_articles_from_json(input_file)
        
        # Process
        results = await process_articles(
            articles, 
            batch_id, 
            output_path=output_path, 
            skip_topic_labels=skip_topic_labels,
            skip_category_labels=skip_category_labels,
            max_workers=max_workers,
        )
        
        # Save results
        save_results(results, output_path)
        
        return results
    except Exception as e:
        print(f"\n❌ Fatal error during processing: {e}")
        print(f"⚠️ Attempting to save partial results...")
        
        # Try to save whatever we have
        try:
            # Create a minimal result structure with error info
            partial_results = {
                "article_batch_id": batch_id,
                "error": str(e),
                "status": "failed",
                "cluster_summaries": {},
                "mega_summary": {
                    "summary": f"[Processing failed with error: {str(e)[:200]}]",
                    "status": "failed"
                },
            }
            save_results(partial_results, output_path)
            print(f"✓ Partial results saved to: {output_path}")
        except Exception as save_error:
            print(f"❌ Failed to save partial results: {save_error}")
        
        # Re-raise to show the error, but at least we tried to save
        raise


async def process_batch_range(
    input_dir: Path, 
    output_dir: Path, 
    start_batch: int, 
    end_batch: int, 
    parallel: bool = False, 
    skip_topic_labels: bool = False,
    skip_category_labels: bool = False,
    max_workers: int = 5,
    max_cluster_articles: Optional[int] = 50,
):
    """
    Process multiple batches.
    
    Args:
        parallel: If True, process batches in parallel (faster but may overwhelm Ollama).
                 If False, process sequentially (safer, default).
        skip_topic_labels: If True, skip topic label generation (faster processing).
        skip_category_labels: If True, skip category label generation (faster processing).
        max_workers: Maximum number of clusters to process in parallel (default: 5).
    """
    import time
    
    # Collect all batch files first
    batch_files = []
    for batch_num in range(start_batch, end_batch + 1):
        batch_id = f"{batch_num:03d}"
        
        possible_names = [
            f"batch_{batch_id}.json",
            f"{batch_id}.json",
            f"input_{batch_id}.json",
        ]
        
        input_file = None
        for name in possible_names:
            candidate = input_dir / name
            if candidate.exists():
                input_file = candidate
                break
        
        if input_file:
            batch_files.append((batch_id, input_file))
        else:
            print(f"⚠️  Skipping batch {batch_id}: No input file found")
    
    if not batch_files:
        print("❌ No batch files found to process")
        return
    
    print(f"\n📊 Found {len(batch_files)} batches to process")
    print(f"⚡ Parallel mode: {'ON' if parallel else 'OFF (sequential)'}\n")
    
    start_time = time.time()
    
    if parallel:
        # Process batches in parallel (2 at a time to avoid overwhelming Ollama)
        semaphore = asyncio.Semaphore(2)  # Limit to 2 concurrent batches
        
        async def process_with_limit(batch_id: str, input_file: Path):
            async with semaphore:
                return await process_single_file(
                    input_file, 
                    batch_id, 
                    output_dir, 
                    skip_topic_labels=skip_topic_labels,
                    skip_category_labels=skip_category_labels,
                    max_workers=max_workers,
                    max_cluster_articles=max_cluster_articles,
                )
        
        tasks = [process_with_limit(batch_id, input_file) for batch_id, input_file in batch_files]
        await asyncio.gather(*tasks, return_exceptions=True)
    else:
        # Process batches sequentially
        for batch_id, input_file in batch_files:
            try:
                await process_single_file(
                    input_file, 
                    batch_id, 
                    output_dir, 
                    skip_topic_labels=skip_topic_labels,
                    skip_category_labels=skip_category_labels,
                    max_workers=max_workers,
                    max_cluster_articles=max_cluster_articles,
                )
            except Exception as e:
                print(f"❌ Error processing batch {batch_id}: {e}")
                continue
    
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"✅ Processed {len(batch_files)} batches in {elapsed/60:.1f} minutes")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate cluster summaries and mega summaries for LLM judge evaluation"
    )
    parser.add_argument(
        "--input_file",
        type=str,
        help="Path to input JSON file with articles",
    )
    parser.add_argument(
        "--input_dir",
        type=str,
        help="Path to directory containing input files",
    )
    parser.add_argument(
        "--batch_id",
        type=str,
        help="Batch ID (e.g., '001') for single file processing",
    )
    parser.add_argument(
        "--batch_range",
        nargs=2,
        metavar=("START", "END"),
        type=int,
        help="Process batches from START to END (e.g., --batch_range 001 010)",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="data/output/llm_judge_eval",
        help="Output directory (default: data/output/llm_judge_eval)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Process multiple batches in parallel (faster but may overwhelm Ollama)",
    )
    parser.add_argument(
        "--skip_mega",
        action="store_true",
        help="Skip mega summary generation (faster, only cluster summaries)",
    )
    parser.add_argument(
        "--skip_topic_labels",
        action="store_true",
        help="Skip topic label generation (faster processing, only category labels)",
    )
    parser.add_argument(
        "--skip_category_labels",
        action="store_true",
        help="Skip category label generation (faster processing, saves 1 LLaMA call per cluster)",
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=5,
        help="Maximum number of clusters to process in parallel (default: 5, increase for faster processing if Ollama can handle it)",
    )
    parser.add_argument(
        "--max_cluster_articles",
        type=int,
        default=50,
        help="Skip clusters with more than this many articles (default: 50, set to 0 to disable limit)",
    )
    
    args = parser.parse_args()
    
    # Determine input directory
    if args.input_dir:
        input_dir = Path(args.input_dir)
    elif args.input_file:
        input_dir = Path(args.input_file).parent
    else:
        input_dir = Path("data/input/llm_judge_eval")
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process based on arguments
    if args.input_file and args.batch_id:
        # Single file processing
        input_file = Path(args.input_file)
        if not input_file.exists():
            print(f"❌ Input file not found: {input_file}")
            return
        
        max_cluster_articles = args.max_cluster_articles if args.max_cluster_articles > 0 else None
        asyncio.run(process_single_file(
            input_file, 
            args.batch_id, 
            output_dir, 
            skip_topic_labels=args.skip_topic_labels,
            skip_category_labels=args.skip_category_labels,
            max_workers=args.max_workers,
            max_cluster_articles=max_cluster_articles,
        ))
    
    elif args.batch_range:
        # Batch range processing
        start, end = args.batch_range
        max_cluster_articles = args.max_cluster_articles if args.max_cluster_articles > 0 else None
        asyncio.run(process_batch_range(
            input_dir, 
            output_dir, 
            start, 
            end, 
            parallel=args.parallel, 
            skip_topic_labels=args.skip_topic_labels,
            skip_category_labels=args.skip_category_labels,
            max_workers=args.max_workers,
            max_cluster_articles=max_cluster_articles,
        ))
    
    else:
        print("❌ Please provide either:")
        print("   --input_file <path> --batch_id <id>  (for single file)")
        print("   --input_dir <path> --batch_range <start> <end>  (for multiple files)")
        parser.print_help()


if __name__ == "__main__":
    main()
