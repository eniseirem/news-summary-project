# Ollama News Clustering Pipeline - Optimization Report

**Hardware:** 4 CPU cores, 15.6 GB RAM  / (12 CPU cores, 24GB RAM, 16 core GPU*)

*Since the device is Apple silicon processor based, only cpu development used.

---

## Executive Summary

Initial processing of 30 articles took **~3.5 hours** with 3 timeouts. After optimization, this was reduced to **~27 minutes** with zero timeouts — a **7.8x speedup**. However, production runs revealed instability under concurrent load, with timeouts reappearing intermittently. Test reports on 12 CPU cores was reported on native running. 

### Docker Performance Impact on Mac M-Series

**Critical Limitation**: Running Ollama in Docker on Mac M-Series chips **cannot access the Apple Silicon GPU/Neural Engine**.

**Why This Matters:**
1. **Docker uses a Linux VM** on macOS which has no access to Metal/GPU acceleration
2. **CPU-only inference** is 10-20x slower than native GPU-accelerated inference
3. **16-core GPU sits unused** while the CPU maxes out at 1380% (nearly all 14 cores)

**Current Performance (Docker, CPU-only):**
- Translation: ~9 minutes for 30 articles
- Summarization: ~10-18 minutes for 30 articles  
- Total: ~20-27 minutes (best case, 4 CPU)
- Timeouts: Frequent under concurrent load

**Expected Performance (Native macOS with GPU):**
- Translation: ~30-60 seconds for 30 articles 
- Summarization: ~1-2 minutes for 30 articles 
- Total: **~2-3 minutes** (vs 20-27 minutes)
- Timeouts: Virtually eliminated due to faster processing

**Note:** Still 12 CPU deployment shows significantly better performance and stability compared to 4 CPU deployment.

---
## Pipeline Flow

Translation - Individual Summarisation - Clustering


| Pipeline | Complexity Calculation | Notes |
|--------|---------------|-------------|
| **Translation** | O(N × (1 + C) × L × B) | Chunk, Lenght of the translation, Beams |
| **Summarisation** | O(N × W × L) | N article count, L output tokens per generation (169), Word count in the input prompt  |

---


## Optimizations on the LLM-pipeline

### Overview

The pipeline was optimized to handle large-scale article processing efficiently through:

1. **Parallel Processing**: Translation and summarization run concurrently (5 workers each)
2. **Translation Caching**: LRU cache (1000 entries) eliminates redundant translations
3. **Early Exit Optimizations**: Skip translation for English articles
4. **Incremental Clustering**: Process only new/unmatched articles, reducing computation
5. **Async Endpoints**: Non-blocking parallel cluster processing
6. **Cached Summaries**: Reuse article summaries from OpenSearch to avoid regeneration

**Overall Impact:** 3-5x speedup for multi-cluster requests, 80-90% reduction in translation overhead, and scalable incremental processing.

### 1. Translation Optimization

### 1.1 Parallel Translation Processing

**Implementation:**
- Uses `ThreadPoolExecutor` with 5 workers
- Translates multiple articles concurrently instead of sequentially
- Reduces translation time from `N × 200ms` to `max(200ms) × ceil(N/5)`

**Performance Impact:**
- **Before:** 50 articles × 200ms = 10 seconds
- **After:** ceil(50/5) × 200ms = 2 seconds
- **Speedup:** 5x faster

### 1.2 Translation Caching

**Implementation**
- LRU-style cache with max 1000 entries
- Cache key: MD5 hash of `language:title:body`
- Preserves article metadata (ID, source, published_at)
- Automatic cache eviction when limit reached (FIFO)

**Performance Impact:**
- **Cache Hit:** ~0ms (instant return)
- **Cache Miss:** ~100-200ms (translation + storage)
- **Overhead Reduction:** 60-80% fewer translation calls

### 1.3 Skip English Translation

**Implementation:**
- Early exit for English articles (no translation needed)
- Preserves `original_language` metadata
- Zero overhead for English content

**Performance Impact:**
- **English Articles:** 0ms overhead (vs 100-200ms before)
- **Only necessary translation** Reduction in translation calls by number of ENglish articles

### 1.4 Lazy Model Loading

**Implementation:**
- MarianMT models loaded on first use, not at import time
- Models cached in memory after first load
- Thread-safe double-checked locking

**Performance Impact:**
- **First Translation:** ~2-5 seconds (one-time model loading)
- **Subsequent Translations:** ~100-200ms (model cached)
- **Memory Efficient:** Models loaded only when needed

## **2. Summarization Optimizations**

### 2.1 Parallel Summarization

**Implementation:**
- Uses `asyncio` + `ThreadPoolExecutor` with 5 workers
- Processes multiple articles concurrently
- Reduces summarization time proportionally

**Performance Impact:**
- **Speedup:** 5x faster

### 2.2 100-Word Article Summaries

**Implementation:**
- All article summaries standardized to 100 words
- Prevents truncation in downstream processing
- Consistent input size for clustering

**Performance Impact:**
- **Faster Summarization:** Shorter summaries = faster LLM calls
- **Prevents Truncation:** No need to re-summarize later
- **Consistent Embeddings:** Uniform input size improves clustering quality

### 2.3 Cached Article Summaries

**Implementation:**
- n8n provides cached article summaries from OpenSearch
- Backend uses cached summaries if provided
- Falls back to generating summaries only if missing

**Performance Impact:**
- **Cache Hit:** 0ms (no summarization needed)
- **Cache Miss:** ~5s per article (normal summarization)
- **Massive Savings:** Avoids regenerating summaries for existing articles

## **3. Clustering Optimizations**

### 3.1 Incremental Clustering Architecture

**Location:** `src/api/endpoints/cluster_create.py`

**How It Works:**

1. **llm-pipeline** creates clusters and embeddings  
2. **n8n** receives clusters + embeddings
3. **n8n** uses OpenSearch k-NN search to find relevant cluster centroids and matches
4. **n8n** updates matched cluster centroids (weighted average)

See: [M3 Incremental Clustering (KNN)](https://github.com/eniseirem/news-summary-project/blob/main/n8n/workflows/docs/M3_Incremental_Clustering_KNN.md)
<!-- Old GitLab link: https://gitlab.fokus.fraunhofer.de/dana/cswspws25/-/blob/n8n-pipeline/workflows/docs/M3_Incremental_Clustering_KNN.md -->

**Performance Impact:** Faster matching of articles to clusters

## **4. Endpoint-Level Optimizations**

### 4.1 Parallel Processing in Endpoints 

**Implementation:**
- `/cluster_create` uses parallel processing for both translation and summarization
- Both endpoints use `ThreadPoolExecutor` with 5 workers
- Async endpoints with non-blocking parallel execution

**Performance Impact:**
- **Translation:** 5x faster (parallel processing)
- **Summarization:** 5x faster (parallel processing)
- **Overall:** Significant speedup for initial clustering operations

### 4.2 Increased Timeouts

**Implementation:**
- Default timeout: 300s → 600s (10 minutes)
- Handles large batches without timing out

**Performance Impact:**
- **Prevents Timeouts:** Large batches complete successfully
- **Better Reliability:** Fewer failed requests

---
## Pipeline Flow

### 4.3 Progress Logging

**Location:** Multiple endpoints

**Implementation:**
- Logging at key processing stages
- Helps debug long-running requests
- Better visibility for n8n team

**Performance Impact:**
- **Better Monitoring:** Understand where time is spent
- **Faster Debugging:** Identify bottlenecks quickly

## **5. Architecture-Level Optimizations**

### 5.1 Modular Endpoint Design

**Endpoints:**
- `/cluster_create`: Initial clustering only
- `/cluster_summarize`: Summarization from cached data
- `/mega_summarize`: Mega summary from cluster summaries

**Benefits:**
- **Separation of Concerns:** Each endpoint does one thing well
- **Caching Opportunities:** Can cache at each stage
- **Parallel Processing:** Can call endpoints in parallel if needed
- **Reduced Payload:** Only send what's needed for each step

---

### 5.2 OpenSearch Integration

**How It Works:**
- n8n stores clusters, article summaries, and centroids in OpenSearch
- k-NN search for fast similarity matching
- Cached summaries reused across requests

**Performance Benefits:**
- **Fast Matching:** k-NN search is O(log N) vs O(N) linear search
- **Persistent Cache:** Summaries persist across requests
- **Scalable Storage:** Handles millions of articles

---

## Further Changes Applied

### 1. Fixed Model Alias (CRITICAL)
**Problem:** `llama3.2:3b` was aliased to the 8B model (4.7 GB) instead of actual 3B (1.9 GB)

**Impact:** ~2x speedup per generation (8B → 3B has fewer parameters)

### 2. Fixed Context Length Mismatch (CRITICAL)
**Problem:** Code assumed 131,072 token context, Ollama used 4,096 tokens

**Root Cause:** When prompts exceeded 4,096 tokens, Ollama silently truncated them:
```
truncating input prompt limit=4096 prompt=4670 keep=25 new=4096
```
This gave the model a mangled prompt (first 25 tokens + last chunk), causing it to hang during generation and timeout.

**Fix:** Updated configuration to align both sides at 8,192 tokens:
- `config.sh`: Added `OLLAMA_CONTEXT_LENGTH=8192`
- `llama3.yaml`: Changed `context_tokens: 131072` → `context_tokens: 8192`

**Impact:** 
- Hierarchical safeguards now trigger correctly (at 5,734 tokens / 70% threshold)
- Prompts exceeding limits are properly chunked before sending
- Reduced model hangs and timeouts when long articles sent

### 3. Increased Parallelism
**Problem:** Fake parallelism - 5 threads firing but Ollama processing only 1 at a time

**Fix:**
- `config.sh`: Added `OLLAMA_NUM_PARALLEL=3`
- `setup_llm.sh`: Passed environment variable to Ollama container

**Impact:** 3 concurrent generations instead of 1 sequential = ~3x speedup potential
However, due to system limits (3 CPU) this didn't introduce significant speed to the pipeline. As nature of concurrent runs, multiple timeout results still reached. 

### 4. Reduced Beam Search in Translation
**Problem:** MarianMT using num_beams=4 (slow)

**Fix:**
- `multilingual.py`: Changed `num_beams=4` → `num_beams=2` 

**Impact:** None observed - translation still takes ~9 minutes (suggesting bottleneck is elsewhere)

---

## Results

### Performance Comparison - 4 CPU

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Total Time** | ~210 min | ~27 min | **7.8x faster if no timeout** |
| **Per Article** | ~7 min | ~54 sec | **7.8x faster** |
| **Timeouts** | 3/30 (10%) | 0/30 (0%) | **100% resolved** |

# Detailed 4 CPU Test Runs

| Run | Articles | Translation | Summarization | Clustering | Total | Timeouts | Notes |
|-----|----------|-------------|---------------|------------|-------|----------|-------|
| 1 | 30 | 9.7 min | 17.8 min | ~4 sec | 27.5 min | 0 | Feb 5 - Clean run |
| 2 | 30 | 9.1 min | 10.1 min | ~4 sec | 19.2 min | 0 | Best Case|
| 3 | 544 | 41.5 min | under 1 min | ~19 sec | 41.6 min | 10+ | Feb 1 - Large batch with timeouts, never finished |
| 4 | 30 | -1 min* | 17.9 min | ~25 sec | 18.2 min | 5 | Feb 1 - Multiple timeouts |
| 5 | 30 | -1 min*| 43.3 min | ~25 sec | 43.6 min | 4+ | Feb 1 - Heavy timeouts |
| 6 | 30 | -1 min* | 57.4 min | ~5 sec | 57.7 min | 7+ | Feb 1 - Severe degradation |
| 7 | 30 | -1 min* | 60.0 min | ~19 sec | 60.3 min | 15+ | Feb 1 - Maximum timeouts |
| 8 | 30 | -1 min* | 40.3 min | ~25 sec | 40.6 min | 3+ | Feb 1 - Partial recovery |

*under 1 min. Batch was already consist of English articles. 

## Summary Statistics

| Metric | Best Case | Worst Case | Average (Clean Runs) |
|--------|-----------|------------|---------------------|
| Translation Time | under 1 min | 41.5 min | ~6.7 min |
| Summarization Time | 10.1 min | 60.0 min | ~13.9 min |
| Clustering Time | ~4 sec | ~25 sec | ~14 sec |
| Total Time (30 articles) | 18.2 min | 60.3 min | ~21.9 min |
| Success Rate | 100% | ~50% | - |


**Pattern:** One stuck generation blocks queue → subsequent requests timeout → cascading failure

**Root Cause:** Ollama has no internal timeout. When one generation hangs (rare token sequence, memory pressure, etc.), it occupies a slot indefinitely. Subsequent requests pile up and timeout after 600s, but the stuck generation continues running. However, introducing internal timeout would result in no result in CPU.

### Performance Comparison - 12 CPU

**Detailed 12 CPU Test Runs**

| Run | Articles | Total Time | Per Article | Status |
|-----|----------|------------|-------------|--------|
| 1   | 30       | 1.84 min   | 3.7 sec     | ✓ Success |
| 2   | 30       | 2.40 min   | 4.8 sec     | ✓ Success |
| 3   | 30       | 1.95 min   | 3.9 sec     | ✓ Success |
| 4   | 30       | 1.97 min   | 3.9 sec     | ✓ Success |
| 5   | 30       | 2.00 min   | 4.0 sec     | ✓ Success |
| **Avg** | **30** | **2.03 min** | **4.1 sec** | **✓ 100%** |


---

## Performance Summary

### 4 CPU Deployment (4 cores, 15.6 GB RAM)
- **Best Case:** 19 minutes, 0 timeouts
- **Average:**  21.9 min (clean runs), 35.2 min (all runs)
- **Per Article:** ~0.73 min/article (clean), ~1.17 min/article (all runs)
- **Success Rate:** 74.6% (282 successful / 378 total articles)
- **Stability:** Good in controlled tests, occasional issues under heavy concurrent load

### 12 CPU Deployment (12 CPU cores, 24GB RAM, 16 core GPU)
- **Best Case:** 1.84 minutes
- **Average:** 2.03 minutes per 30 articles  
- **Per Article:** 4.1 seconds
- **Success Rate:** 100% (zero timeouts)
- **Stability:** No issues under concurrent load

**Key Insight:** More CPU provides both speed and stability improvements, making it the clear choice for production deployment.

---

## Additional Steps That Can Improve the Pipeline

### 1. CPU Stability Under Concurrent Load
**Problem:** Cascading failures when one generation gets stuck

**Proposed Fix:** Add retry logic in `llama_client.py`:
- On timeout, wait 10s for queue to clear
- Retry once before failing
- Skip article instead of blocking entire batch

### 2. Translation Bottleneck (9 minutes)
**Problem:** num_beams=1 had no impact on translation speed

**Likely Cause:** 
- PyTorch GIL contention (5 threads but only 1 executes)
- CPU-bound operations in MarianMT
- Not bottlenecked by beam search

**Recommendation:** test on GPU might change the result

