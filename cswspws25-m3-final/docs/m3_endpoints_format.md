# M3 Endpoints - Request & Response Formats

**Purpose:** Lightweight endpoint formats optimized for n8n integration with minimal required fields to reduce latency.

---

## 1. `/summarize_with_style_plain` --> `/summary_style`

**POST** `/summarize_with_style_plain`

Styles cluster or mega summaries with requested writing style, output format, and institutional tone.

### Request (Minimal)

```json
{
  "request_id": "req_001",
  "summary": "Cluster or mega summary text to style...",
  "writing_style": "journalistic",
  "output_format": "bullet_points",
  "institutional": false
}
```

**Required Fields:**
- `request_id` (string): Request identifier
- `summary` (string): Cluster or mega summary text to style (min 1 character)

**Optional Fields:**
- `writing_style` (string): "journalistic" | "academic" | "executive" (default: none)
- `output_format` (string): "paragraph" | "bullet_points" | "tldr" | "sections" (default: none)
- `institutional` (boolean): Use institutional tone (default: false, frontend uses as switch)
- `article_ids` (array): Article IDs associated with summary

**Note:** If no style/format/institutional=false, returns summary as-is (no rewriting).

### Response (Minimal)

```json
{
  "request_id": "req_001",
  "styled_summary": "Styled summary text...",
  "writing_style": "journalistic",
  "output_format": "bullet_points",
  "institutional": false,
  "article_ids": ["article_001", "article_002"],
  "processed_at": "2025-01-15T12:00:00Z"
}
```

**Response Fields:**
- `request_id` (string): Echo of request ID
- `styled_summary` (string): Styled summary text (or original if no styling applied)
- `writing_style` (string, optional): Writing style applied (if any)
- `output_format` (string, optional): Output format applied (if any)
- `institutional` (boolean): Whether institutional tone was applied
- `article_ids` (array, optional): Article IDs if provided
- `processed_at` (string): ISO timestamp

---

## 2. `/topic_label`

**POST** `/topic_label`

### Request (Minimal)

```json
{
  "request_id": "req_001",
  "summary": "Cluster or article summary text..."
}
```

**Required Fields:**
- `request_id` (string): Request identifier
- `summary` (string): Summary text to label (min 1 character)

**Optional Fields:**
- `article_ids` (array): Article IDs associated with summary
- `max_words` (int): Maximum words in label (default: 4, range: 1-10)

### Response (Minimal)

```json
{
  "request_id": "req_001",
  "topic_label": "Climate Change Summit",
  "processed_at": "2025-01-15T12:00:00Z"
}
```

**Response Fields:**
- `request_id` (string): Echo of request ID
- `topic_label` (string): Generated topic label (max 4 words)
- `processed_at` (string): ISO timestamp

**Optional Response Fields:**
- `article_ids` (array): Article IDs if provided
- `summary_length` (int): Length of input summary
- `max_words` (int): Maximum words used

---

## 3. `/keywords` --> `/keyword_extract`

**POST** `/keywords`

Extracts LDA and TF-IDF keywords from cluster or mega summaries.

### Request (Minimal)

```json
{
  "request_id": "req_001",
  "summary": "Cluster or mega summary text to extract keywords from..."
}
```

**Required Fields:**
- `request_id` (string): Request identifier
- `summary` (string): Cluster or mega summary text (min 1 character)

**Optional Fields:**
- `extract_lda` (boolean): Extract LDA keywords (default: true)
- `extract_tfidf` (boolean): Extract TF-IDF keywords (default: true)
- `num_topics` (int): Number of LDA topics (default: 3, range: 1-10)
- `words_per_topic` (int): Words per LDA topic (default: 3)
- `top_k` (int): Number of TF-IDF keywords (default: 5, range: 1-50)
- `article_ids` (array): Article IDs associated with summary

**Note:** At least one extraction method (LDA or TF-IDF) must be enabled.

### Response (Minimal)

```json
{
  "request_id": "req_001",
  "lda_keywords": ["climate", "change", "summit", "emissions", "agreement"],
  "tfidf_keywords": ["climate", "emissions", "summit", "agreement", "carbon"],
  "article_ids": ["article_001", "article_002"],
  "processed_at": "2025-01-15T12:00:00Z"
}
```

**Response Fields:**
- `request_id` (string): Echo of request ID
- `lda_keywords` (array, optional): LDA keywords if `extract_lda=true`
- `tfidf_keywords` (array, optional): TF-IDF keywords if `extract_tfidf=true`
- `article_ids` (array, optional): Article IDs if provided
- `processed_at` (string): ISO timestamp

---

## 4. `/category_label`

**POST** `/category_label`

### Request (Minimal)

```json
{
  "request_id": "req_001",
  "summary": "Cluster or article summary text...",
  "lda_keywords": {...},
  "use_lda": true
  "article_count": 1
}
```

**Required Fields:**
- `request_id` (string): Request identifier
- `summary` (string): Summary text to categorize (min 1 character)
- `article_count` (int): Number of articles (min 1)

**Optional Fields:**
- `article_ids` (array): Article IDs associated with summary
- `lda_keywords` (array): LDA keywords for better classification
- `use_lda` (boolean): Use LDA keywords if provided (default: true)
- `is_noise_cluster` (boolean): Whether this is a noise cluster (default: false)
- `cluster_id` (int): Cluster ID if applicable

### Response (Minimal)

```json
{
  "request_id": "req_001",
  "category": "Global Politics",
  "article_count": 1,
  "processed_at": "2025-01-15T12:00:00Z"
}
```

**Response Fields:**
- `request_id` (string): Echo of request ID
- `category` (string): One of: "Global Politics", "Economics", "Sports", "Events", "General News"
- `article_count` (int): Number of articles
- `processed_at` (string): ISO timestamp

**Optional Response Fields:**
- `article_ids` (array): Article IDs if provided
- `cluster_id` (int): Cluster ID if provided
- `summary_length` (int): Length of input summary
- `used_lda` (boolean): Whether LDA keywords were used
- `is_noise_cluster` (boolean): Whether treated as noise cluster

---

## 5. `/cluster_articles_n8n` --> `/cluster_create`

**POST** `/cluster_articles_n8n`

Initial clustering of articles. Returns clusters and article summaries for caching.

**Processing:**
1. Translate articles to English (parallel, 5 workers)
2. Summarize articles individually to 100 words (parallel, 5 workers) ← Prevents truncation
3. Generate embeddings from article summaries
4. Cluster articles using HDBSCAN
5. Calculate centroids for each cluster
6. Return clusters + article summaries (for n8n to cache)

### Request (Minimal)

```json
{
  "request_id": "req_001",
  "articles": [
    {
      "id": "article_001",
      "title": "Article Title",
      "body": "Article body text...",
      "language": "en"
    }
  ],
  "min_cluster_size": 2
}
```

**Required Fields:**
- `request_id` (string): Request identifier
- `articles` (array): List of articles (min 1)
  - `id` (string): Article ID
  - `title` (string): Article title
  - `body` (string): Article body
  - `language` (string): Language code

**Optional Fields:**
- `min_cluster_size` (int): Minimum cluster size (default: 2)

### Response (Minimal)

```json
{
  "request_id": "req_001",
  "total_articles": 5,
  "total_clusters": 2,
  "clusters": [
    {
      "cluster_id": 0,
      "article_ids": ["article_001", "article_002"],
      "article_count": 2,
      "centroid_embedding": [0.123, -0.456, 0.789, ...]
    },
    {
      "cluster_id": 1,
      "article_ids": ["article_003", "article_004", "article_005"],
      "article_count": 3,
      "centroid_embedding": [-0.345, 0.678, -0.123, ...]
    }
  ],
  "article_summaries": {
    "article_001": "Summary text (100 words)...",
    "article_002": "Summary text (100 words)...",
    "article_003": "Summary text (100 words)...",
    "article_004": "Summary text (100 words)...",
    "article_005": "Summary text (100 words)..."
  },
  "processed_at": "2025-01-15T12:00:00Z"
}
```

**Response Fields:**
- `request_id` (string): Echo of request ID
- `total_articles` (int): Total articles processed
- `total_clusters` (int): Number of clusters created
- `clusters` (array): List of clusters
  - `cluster_id` (int): Cluster ID (0-based, n8n converts to UUID in OpenSearch)
  - `article_ids` (array): Article IDs in this cluster
  - `article_count` (int): Number of articles in cluster
  - `centroid_embedding` (array): Centroid vector (384-dim) for similarity matching
- `article_summaries` (object): Map of article_id → summary text (100 words each)
  - Key: article_id (string)
  - Value: summary text (string, ~100 words)
  - n8n stores these in OpenSearch for later use
- `processed_at` (string): ISO timestamp

**Note:**
- Articles are summarized to 100 words to prevent truncation in downstream processing
- Article summaries are included for n8n to cache in OpenSearch
- Use separate endpoints for topic labels, keywords, or category labels

---

## 6. `/cluster_incremental_n8n` --> `/cluster_update` ⚠️ NOT IN USE

**POST** `/cluster_incremental_n8n`

⚠️ **STATUS: NOT IN USE** - n8n now handles cluster updates directly (matching + centroid updates). This endpoint is kept for reference but is not currently used in the workflow.

Match new articles to existing clusters (using centroids from OpenSearch) and create new clusters for unmatched articles. Returns article summaries for caching.

**Processing:**
1. Translate articles to English (parallel, 5 workers)
2. Summarize articles individually to 100 words (parallel, 5 workers) ← Prevents truncation
3. Generate embeddings from article summaries
4. Match articles to existing cluster centroids (cosine similarity)
5. Update matched clusters (calculate new centroids)
6. Cluster unmatched articles together (HDBSCAN)
7. Create new clusters for unmatched articles
8. Return delta updates + new clusters + article summaries (for n8n to cache)

### Request (Minimal)

```json
{
  "request_id": "req_002",
  "articles": [
    {
      "id": "article_007",
      "title": "New Article Title",
      "body": "New article body text...",
      "language": "en"
    },
    {
      "id": "article_008",
      "title": "Another New Article",
      "body": "Another new article body...",
      "language": "de"
    }
  ],
  "cluster_centroids": [
    {
      "cluster_id": "cluster_uuid_123",
      "centroid_embedding": [0.123, -0.456, 0.789, ...],
      "current_article_count": 5
    },
    {
      "cluster_id": "cluster_uuid_456",
      "centroid_embedding": [-0.345, 0.678, -0.123, ...],
      "current_article_count": 3
    }
  ],
  "similarity_threshold": 0.7,
  "min_cluster_size": 2
}
```

**Required Fields:**
- `request_id` (string): Request identifier
- `articles` (array): New articles to process (min 1)
  - `id` (string): Article ID
  - `title` (string): Article title
  - `body` (string): Article body
  - `language` (string): Language code
- `cluster_centroids` (array): Filtered centroids from OpenSearch (can be empty)
  - `cluster_id` (string): Cluster UUID from OpenSearch
  - `centroid_embedding` (array): 384-dim vector (384 floats)
  - `current_article_count` (int, optional): Current article count (for accurate centroid updates)

**Optional Fields:**
- `similarity_threshold` (float): Minimum similarity to match (default: 0.7, range: 0.0-1.0)
- `min_cluster_size` (int): Minimum size for new clusters (default: 2, min: 1)

**Note:**
- `cluster_centroids` is filtered by n8n using OpenSearch k-NN search
- Only relevant centroids are sent (not all clusters)
- If empty, all articles will create new clusters

### Response (Minimal)

```json
{
  "request_id": "req_002",
  "total_articles": 2,
  "matched_articles": 1,
  "new_clusters_created": 1,
  "new_articles_in_new_clusters": 1,
  "article_matches": [
    {
      "article_id": "article_007",
      "matched_cluster_id": "cluster_uuid_123",
      "similarity_score": 0.85,
      "is_new_cluster": false,
      "new_cluster_id": null
    },
    {
      "article_id": "article_008",
      "matched_cluster_id": null,
      "similarity_score": 0.45,
      "is_new_cluster": true,
      "new_cluster_id": "cluster_uuid_789"
    }
  ],
  "matched_cluster_updates": [
    {
      "cluster_id": "cluster_uuid_123",
      "articles_added": ["article_007"],
      "updated_centroid_embedding": [0.125, -0.451, 0.792, ...],
      "new_article_count": 6
    }
  ],
  "new_clusters": [
    {
      "cluster_id": "cluster_uuid_789",
      "article_ids": ["article_008"],
      "article_count": 1,
      "centroid_embedding": [0.234, -0.567, 0.890, ...],
      "created_at": "2025-01-15T12:00:00Z"
    }
  ],
  "article_summaries": {
    "article_007": "Summary text (100 words)...",
    "article_008": "Summary text (100 words)..."
  },
  "total_existing_clusters": 2,
  "processed_at": "2025-01-15T12:00:00Z",
  "processing_time_ms": 1250
}
```

**Response Fields:**
- `request_id` (string): Echo of request ID
- `total_articles` (int): Total articles processed
- `matched_articles` (int): Articles matched to existing clusters
- `new_clusters_created` (int): Number of new clusters created
- `new_articles_in_new_clusters` (int): Articles in newly created clusters
- `article_matches` (array): Per-article matching results
  - `article_id` (string): Article ID
  - `matched_cluster_id` (string, optional): Cluster UUID if matched (null if no match)
  - `similarity_score` (float, optional): Cosine similarity if matched
  - `is_new_cluster` (boolean): True if article created new cluster
  - `new_cluster_id` (string, optional): UUID of new cluster if created
- `matched_cluster_updates` (array): **Delta updates** for matched clusters
  - `cluster_id` (string): Cluster UUID
  - `articles_added` (array): New article IDs added
  - `updated_centroid_embedding` (array): Updated centroid (384-dim)
  - `new_article_count` (int): Updated count (old_count + len(articles_added))
- `new_clusters` (array): **Full data** for newly created clusters
  - `cluster_id` (string): New cluster UUID (generated by backend)
  - `article_ids` (array): Article IDs in new cluster
  - `article_count` (int): Number of articles
  - `centroid_embedding` (array): Centroid vector (384-dim)
  - `created_at` (string): ISO timestamp
- `article_summaries` (object): Map of article_id → summary text (100 words each)
  - Key: article_id (string)
  - Value: summary text (string, ~100 words)
  - Only includes NEW articles processed in this request
  - n8n stores these in OpenSearch for later use
- `total_existing_clusters` (int): Number of centroids provided in request
- `processed_at` (string): ISO timestamp
- `processing_time_ms` (int, optional): Processing time in milliseconds

**Note:**
- Articles are summarized to 100 words to prevent truncation
- Article summaries are included for n8n to cache in OpenSearch
- Use separate endpoints for cluster summaries, topic labels, keywords, or category labels

---

## 7. `/cluster_summary_from_clusters` --> `/cluster_summarize`

**POST** `/cluster_summary_from_clusters`

Generate cluster summaries from existing clusters using cached article summaries.

**Key Insight:**
- Clusters are already created (stored in OpenSearch)
- Article summaries are cached in OpenSearch (from `/cluster_articles_n8n` or `/cluster_incremental_n8n`)
- Backend can use cached summaries (no regeneration needed)
- Falls back to generating summaries if not provided

**Processing:**
1. Validate: All article_ids in clusters exist in articles/article_summaries
2. Group articles by cluster_id
3. For each cluster:
   a. Use cached article summaries (if provided) OR generate summaries (100 words)
   b. Generate cluster summary from article summaries
4. Return cluster summaries only (no labels, no keywords)

### Request (Minimal)

```json
{
  "request_id": "req_003",
  "clusters": [
    {
      "cluster_id": "cluster_uuid_123",
      "article_ids": ["article_001", "article_002"]
    },
    {
      "cluster_id": "cluster_uuid_456",
      "article_ids": ["article_003", "article_004", "article_005"]
    }
  ],
  "articles": [
    {
      "id": "article_001",
      "title": "Article Title",
      "body": "Article body text...",
      "language": "en"
    },
    {
      "id": "article_002",
      "title": "Another Title",
      "body": "Another body...",
      "language": "en"
    }
  ],
  "article_summaries": {
    "article_001": "Cached summary (100 words)...",
    "article_002": "Cached summary (100 words)...",
    "article_003": "Cached summary (100 words)...",
    "article_004": "Cached summary (100 words)...",
    "article_005": "Cached summary (100 words)..."
  }
}
```

**Required Fields:**
- `request_id` (string): Request identifier
- `clusters` (array): List of clusters to summarize
  - `cluster_id` (string): Cluster UUID from OpenSearch
  - `article_ids` (array): Article IDs in this cluster
- `articles` (array): All articles referenced in clusters
  - Must include ALL articles referenced in any cluster
  - Articles should already be translated to English (or will be translated)

**Optional Fields:**
- `article_summaries` (object): **Cached article summaries from OpenSearch**
  - Format: `{"article_id": "summary text", ...}`
  - If provided: Uses cached summaries (FAST - no regeneration)
  - If not provided: Generates summaries from articles (100 words each)
  - n8n should provide this from OpenSearch cache for efficiency

### Response (Minimal)

```json
{
  "request_id": "req_003",
  "cluster_count": 2,
  "clusters": [
    {
      "cluster_id": "cluster_uuid_123",
      "article_ids": ["article_001", "article_002"],
      "article_count": 2,
      "summary": "Cluster summary text..."
    },
    {
      "cluster_id": "cluster_uuid_456",
      "article_ids": ["article_003", "article_004", "article_005"],
      "article_count": 3,
      "summary": "Another cluster summary..."
    }
  ],
  "processed_at": "2025-01-15T12:00:00Z"
}
```

**Response Fields:**
- `request_id` (string): Echo of request ID
- `cluster_count` (int): Number of clusters processed
- `clusters` (array): List of cluster summaries
  - `cluster_id` (string): Cluster UUID (echoed from request)
  - `article_ids` (array): Article IDs (echoed from request)
  - `article_count` (int): Number of articles
  - `summary` (string): Generated cluster summary
- `processed_at` (string): ISO timestamp

**What's NOT Included:**
❌ No topic labels (use `/topic_label` endpoint)
❌ No category labels (use `/category_label` endpoint)
❌ No keywords (use `/keywords` endpoint)

**Note:**
- If `article_summaries` provided: Uses cached summaries (fast, no regeneration)
- If `article_summaries` not provided: Generates summaries from articles (100 words each)
- n8n should fetch and provide cached summaries from OpenSearch for efficiency

---

## 8. `/mega_summary_from_clusters` --> `/mega_summarize`

**POST** `/mega_summary_from_clusters`

Generate a mega summary from existing cluster summaries.

**Key Insight:**
- Cluster summaries are already generated (from `/cluster_summary_from_clusters`)
- Backend just needs to combine them into a mega summary
- No article processing needed

### Request (Minimal)

```json
{
  "request_id": "req_004",
  "cluster_summaries": {
    "cluster_uuid_123": "Cluster summary text...",
    "cluster_uuid_456": "Another cluster summary...",
    "cluster_uuid_789": "Third cluster summary..."
  }
}
```

**Required Fields:**
- `request_id` (string): Request identifier
- `cluster_summaries` (object): Map of cluster_id → summary text
  - Key: cluster_id (string UUID)
  - Value: summary text (string, min 1 character)

### Response (Minimal)

```json
{
  "request_id": "req_004",
  "mega_summary": "This briefing covers major developments in UK policy and German domestic affairs. The UK government has announced significant asylum reforms requiring refugees to wait 20 years for permanent settlement, while the economy showed strong growth. In Germany, Chancellor Merz defended pension reforms and the government introduced mandatory military screening for young men.",
  "cluster_count": 3,
  "cluster_ids": ["cluster_uuid_123", "cluster_uuid_456", "cluster_uuid_789"],
  "processed_at": "2025-01-15T12:00:00Z"
}
```

**Response Fields:**
- `request_id` (string): Echo of request ID
- `mega_summary` (string): Generated mega summary combining all cluster summaries
- `cluster_count` (int): Number of clusters included
- `cluster_ids` (array): List of cluster IDs included (for reference)
- `processed_at` (string): ISO timestamp

**Note:**
- Only generates mega summary (no per-cluster breakdowns)
- Fast processing (just combines existing summaries)

---

## 9. `/cluster_maintenance`

**POST** `/cluster_maintenance`

Performs maintenance operations on clusters: merging similar clusters, archiving inactive clusters, and cleaning up duplicates.

**Important Design Decision:**
- **Archived clusters are excluded from matching**: Once a cluster is archived, it is no longer used for article-to-cluster matching (k-NN search).
- **Reemerging topics create new clusters**: If a topic reemerges after its cluster was archived, a new cluster is created instead of reactivating the archived one.
- **Rationale**: This ensures that outdated information from archived clusters does not get included in new summaries, maintaining freshness and relevance of the clustering system.

### Request (Minimal)

```json
{
  "request_id": "req_001",
  "operation": "merge"
}
```

**Required Fields:**
- `request_id` (string): Request identifier
- `operation` (string): One of: "merge", "archive", "cleanup", "all"

**Optional Fields:**
- `similarity_threshold` (float): Similarity threshold for merge/cleanup (default: 0.85, range: 0.0-1.0)
- `days_inactive` (int): Days inactive for archive (default: 30, min: 1)
  - A cluster is considered inactive if no articles were matched to it for N days (based on `last_updated` timestamp)

### Response (Minimal)

```json
{
  "request_id": "req_001",
  "operation": "merge",
  "processed_at": "2025-01-15T12:00:00Z"
}
```

**Response Fields:**
- `request_id` (string): Echo of request ID
- `operation` (string): Operation performed
- `processed_at` (string): ISO timestamp

**Conditional Response Fields:**
- `merges` (array): Merge results if operation includes "merge"
  - `cluster_id_1` (string): First cluster ID
  - `cluster_id_2` (string): Second cluster ID
  - `similarity` (float): Similarity score
  - `merged_cluster_id` (string): ID of merged cluster
  - `merged_article_count` (int): Total articles in merged cluster
- `archived` (object): Archive results if operation includes "archive"
  - `archived_cluster_ids` (array): List of archived cluster IDs
  - `total_archived` (int): Number of clusters archived
- `duplicates_merged` (array): Duplicate merge pairs if operation includes "cleanup"
  - Array of tuples: `[cluster_id_1, cluster_id_2]`

**Notes:**
- Archived clusters are permanently excluded from article matching to prevent outdated information from appearing in summaries
- If a topic reemerges, it will create a fresh cluster with current articles only
- Archive operation checks `last_updated` timestamp: clusters with no new articles for N days are archived

---

## 10. `/cluster_stats`

**GET** `/cluster_stats`

### Request (Minimal)

```
GET /cluster_stats?request_id=req_001
```

**Query Parameters:**
- `request_id` (string, optional): Request identifier (default: "stats_request")

### Response (Minimal)

```json
{
  "request_id": "req_001",
  "total_clusters": 150,
  "active_clusters": 145,
  "archived_clusters": 5,
  "total_articles": 1250,
  "avg_cluster_size": 8.62,
  "processed_at": "2025-01-15T12:00:00Z"
}
```

**Response Fields:**
- `request_id` (string): Request identifier
- `total_clusters` (int): Total clusters (active + archived)
- `active_clusters` (int): Number of active clusters
- `archived_clusters` (int): Number of archived clusters
- `total_articles` (int): Total articles across all active clusters
- `avg_cluster_size` (float): Average articles per cluster
- `processed_at` (string): ISO timestamp

**Additional Response Fields:**
- `size_distribution` (array): Cluster size distribution
  - `size_range` (string): Size range (e.g., "1-5", "6-10", "11-20", "21+")
  - `count` (int): Number of clusters in range
  - `total_articles` (int): Total articles in range
- `category_distribution` (array): Category statistics
  - `category` (string): Category name
  - `cluster_count` (int): Number of clusters
  - `total_articles` (int): Total articles
  - `avg_cluster_size` (float): Average cluster size
- `recent_activity` (object): Activity in last 7 days
  - `clusters_created_last_7_days` (int): Clusters created
  - `clusters_updated_last_7_days` (int): Clusters updated
- `storage_info` (object): Storage metadata
  - `storage_type` (string): Storage type ("json" or "postgresql")
  - `total_clusters` (int): Total clusters
  - `index_available` (boolean): Whether index is available

---

## 11. `/evaluate/cluster` --> `/evaluate_cluster`

**POST** `/evaluate/cluster`

Evaluates cluster summaries using LLM judges. Returns 4 standard metrics on a 1-5 scale, plus 2 optional metrics (tone and style) when requested.

### Request (Minimal)

```json
{
  "request_id": "req_001",
  "cluster_summary": "Summary text of the cluster...",
  "source_articles": [
    "First article text...",
    "Second article text...",
    "Third article text..."
  ],
  "drop_fallbacks": true,
  "evaluate_tone": false,
  "evaluate_style": false
}
```

**Required Fields:**
- `request_id` (string): Request identifier
- `cluster_summary` (string): Summary text to evaluate (min 1 character)
- `source_articles` (array): List of article texts (min 1 article)

**Optional Fields:**
- `drop_fallbacks` (boolean): Exclude fallback judges from aggregation (default: true)
- `evaluate_tone` (boolean): Evaluate tone metric (5th metric, independent evaluation) (default: false)
- `evaluate_style` (boolean): Evaluate style metric (6th metric, independent evaluation) (default: false)
- `cluster_id` (string): Cluster ID for tracking
- `category` (string): Category name
- `article_ids` (array): Article IDs corresponding to source_articles

**Note:** 
- Always uses all 3 judges (qwen, mistral, gemma) automatically. Scores are aggregated across successful judges.
- Optional metrics (tone, style) are evaluated independently and do not affect the standard 4 metrics.
- When `evaluate_tone=true` or `evaluate_style=true`, additional judge calls are made for those metrics separately.

### Response (Minimal)

**Response:**
```json
{
  "request_id": "req_001",
  "status": "partial",
  "num_judges_used": 2,
  "scores": {
    "coherence": 4.25,
    "consistency": 4.5,
    "relevance": 4.0,
    "fluency": 4.75
  },
  "tone_score": null,
  "style_score": null,
  "tone_status": null,
  "style_status": null,
  "tone_num_judges_used": null,
  "style_num_judges_used": null,
  "individual_results": [
    {
      "model": "qwen",
      "status": "success",
      "scores": {
        "coherence": 4,
        "consistency": 5,
        "relevance": 4,
        "fluency": 5
      },
      "tone_score": null,
      "style_score": null,
      "error": null
    },
    {
      "model": "mistral",
      "status": "success",
      "scores": {
        "coherence": 4,
        "consistency": 4,
        "relevance": 4,
        "fluency": 4
      },
      "tone_score": null,
      "style_score": null,
      "error": null
    },
    {
      "model": "gemma",
      "status": "fallback",
      "scores": null,
      "tone_score": null,
      "style_score": null,
      "error": "Model unavailable"
    }
  ],
  "error_reasons": ["gemma: Model unavailable"],
  "article_ids": ["article_001", "article_002", "article_003"],
  "processed_at": "2025-01-15T12:00:00Z"
}
```

**Response Fields:**
- `request_id` (string): Echo of request ID
- `status` (string): "success" | "partial" | "fallback" (status for standard 4 metrics)
- `num_judges_used` (int): Number of judges used in aggregation for standard metrics (0-3, always attempts 3)
- `scores` (object): Averaged scores (float, 1-5 scale) - always present (aggregated or fallback 3.0)
  - `coherence` (float): Logical flow and structure
  - `consistency` (float): Factual consistency with source
  - `relevance` (float): Relevance to source articles
  - `fluency` (float): Language quality and readability
- `tone_score` (float, optional): Tone score (1-5 scale) - only present if `evaluate_tone=true`
- `style_score` (float, optional): Style score (1-5 scale) - only present if `evaluate_style=true`
- `tone_status` (string, optional): Status for tone evaluation ("success" | "partial" | "fallback") - only present if `evaluate_tone=true`
- `style_status` (string, optional): Status for style evaluation ("success" | "partial" | "fallback") - only present if `evaluate_style=true`
- `tone_num_judges_used` (int, optional): Number of judges used for tone aggregation (0-3) - only present if `evaluate_tone=true`
- `style_num_judges_used` (int, optional): Number of judges used for style aggregation (0-3) - only present if `evaluate_style=true`
- `individual_results` (array): Per-judge results (always present, 3 judges)
  - Each item contains: `model`, `status` ("success" | "repaired" | "fallback"), `scores`, `tone_score` (optional), `style_score` (optional), `error`
- `error_reasons` (array, optional): List of error messages from failed judges (format: `["model: error"]` or `["tone-model: error"]` or `["style-model: error"]`)
- `article_ids` (array, optional): Article IDs if provided
- `processed_at` (string): ISO timestamp

---

## 12. `/evaluate/mega` --> `/evaluate_mega`

**POST** `/evaluate/mega`

Evaluates mega summaries using LLM judges. Returns 4 standard metrics on a 1-5 scale, plus 2 optional metrics (tone and style) when requested.

### Request (Minimal)

```json
{
  "request_id": "req_001",
  "mega_summary": "Mega summary text combining all clusters...",
  "cluster_summaries": {
    "cluster_1": "First cluster summary...",
    "cluster_2": "Second cluster summary...",
    "cluster_3": "Third cluster summary..."
  },
  "drop_fallbacks": true,
  "evaluate_tone": false,
  "evaluate_style": false
}
```

**Required Fields:**
- `request_id` (string): Request identifier
- `mega_summary` (string): Mega summary text to evaluate (min 1 character)
- `cluster_summaries` (object): Dict mapping cluster_id -> summary_text (min 1 cluster)

**Optional Fields:**
- `drop_fallbacks` (boolean): Exclude fallback judges from aggregation (default: true)
- `evaluate_tone` (boolean): Evaluate tone metric (5th metric, independent evaluation) (default: false)
- `evaluate_style` (boolean): Evaluate style metric (6th metric, independent evaluation) (default: false)
- `cluster_article_ids` (object): Map cluster_id -> article_ids (e.g., `{"cluster_1": ["article_1", "article_2"]}`)

**Note:** 
- Always uses all 3 judges (qwen, mistral, gemma) automatically. Scores are aggregated across successful judges.
- Optional metrics (tone, style) are evaluated independently and do not affect the standard 4 metrics.
- When `evaluate_tone=true` or `evaluate_style=true`, additional judge calls are made for those metrics separately.

### Response (Minimal)

**Response:**
```json
{
  "request_id": "req_001",
  "status": "partial",
  "num_judges_used": 2,
  "scores": {
    "coherence": 4.25,
    "consistency": 4.5,
    "relevance": 4.0,
    "fluency": 4.75
  },
  "individual_results": [
    {
      "model": "qwen",
      "status": "success",
      "scores": {
        "coherence": 4,
        "consistency": 5,
        "relevance": 4,
        "fluency": 5
      },
      "error": null
    },
    {
      "model": "mistral",
      "status": "success",
      "scores": {
        "coherence": 4,
        "consistency": 4,
        "relevance": 4,
        "fluency": 4
      },
      "error": null
    },
    {
      "model": "gemma",
      "status": "fallback",
      "scores": null,
      "error": "Model unavailable"
    }
  ],
  "error_reasons": ["gemma: Model unavailable"],
  "article_ids": ["article_001", "article_002", "article_003"],
  "processed_at": "2025-01-15T12:00:00Z"
}
```

**Response Fields:**
- `request_id` (string): Echo of request ID
- `status` (string): "success" | "partial" | "fallback" (status for standard 4 metrics)
- `num_judges_used` (int): Number of judges used in aggregation for standard metrics (0-3, always attempts 3)
- `scores` (object): Averaged scores (float, 1-5 scale) - always present (aggregated or fallback 3.0)
  - `coherence` (float): Logical flow and structure across clusters
  - `consistency` (float): Factual consistency with cluster summaries
  - `relevance` (float): Relevance to cluster summaries
  - `fluency` (float): Language quality and readability
- `tone_score` (float, optional): Tone score (1-5 scale) - only present if `evaluate_tone=true`
- `style_score` (float, optional): Style score (1-5 scale) - only present if `evaluate_style=true`
- `tone_status` (string, optional): Status for tone evaluation ("success" | "partial" | "fallback") - only present if `evaluate_tone=true`
- `style_status` (string, optional): Status for style evaluation ("success" | "partial" | "fallback") - only present if `evaluate_style=true`
- `tone_num_judges_used` (int, optional): Number of judges used for tone aggregation (0-3) - only present if `evaluate_tone=true`
- `style_num_judges_used` (int, optional): Number of judges used for style aggregation (0-3) - only present if `evaluate_style=true`
- `individual_results` (array): Per-judge results (always present, 3 judges)
  - Each item contains: `model`, `status` ("success" | "repaired" | "fallback"), `scores`, `tone_score` (optional), `style_score` (optional), `error`
- `error_reasons` (array, optional): List of error messages from failed judges (format: `["model: error"]` or `["tone-model: error"]` or `["style-model: error"]`)
- `cluster_article_ids` (object, optional): Map cluster_id -> article_ids if provided
- `processed_at` (string): ISO timestamp

---

## 13. `/translate/cluster_summary_de` --> `/translate_cluster_summary`

**POST** `/translate/cluster_summary_de`

Translates cluster summaries from English to German. Adds `summary_de` field to the cluster summary object.

### Request (Minimal)

```json
{
  "payload": {
    "cluster_summary": {
      "summary": "English cluster summary text...",
      "cluster_id": "cluster_001",
      "article_ids": ["article_001", "article_002"]
    }
  }
}
```

**Required Fields:**
- `payload` (object): Full payload object containing cluster summary
- `payload.cluster_summary` (object): Cluster summary object
- `payload.cluster_summary.summary` (string): English summary text to translate

**Note:** If `summary` is empty, `summary_de` will be set to empty string.

### Response (Minimal)

```json
{
  "payload": {
    "cluster_summary": {
      "summary": "English cluster summary text...",
      "summary_de": "Deutsche Cluster-Zusammenfassung...",
      "cluster_id": "cluster_001",
      "article_ids": ["article_001", "article_002"]
    }
  }
}
```

**Response Fields:**
- `payload` (object): Same payload structure as request
- `payload.cluster_summary.summary_de` (string): German translation of the summary

**Note:** All other fields in the payload are preserved unchanged. Only `summary_de` is added/updated.

---

## 14. `/translate/mega_summary_de` --> `/translate_mega_summary`

**POST** `/translate/mega_summary_de`

Translates mega summaries and their constituent cluster summaries from English to German. Adds `summary_de` fields to both mega summary and all cluster summaries.

**Recommendation:**
- If the frontend already has the English summaries (e.g., from a previous endpoint call), you don't need to return them again — return only summary_de.
- If the frontend needs both languages or doesn't have English cached, return both.
- Hence, you can decide to take out "summary" and leave only "sumamry_de" or not in the request format, based on that you have.

### Request (Minimal)

```json
{
  "payload": {
    "mega_summary": {
      "summary": "English mega summary text..."
    },
    "cluster_summaries": {
      "cluster_1": {
        "summary": "First cluster summary in English..."
      },
      "cluster_2": {
        "summary": "Second cluster summary in English..."
      }
    }
  }
}
```

**Required Fields:**
- `payload` (object): Full payload object
- `payload.mega_summary` (object): Mega summary object
- `payload.mega_summary.summary` (string): English mega summary text to translate

**Optional Fields:**
- `payload.cluster_summaries` (object): Dictionary mapping cluster_id -> cluster object
- `payload.cluster_summaries[cluster_id].summary` (string): English cluster summary text to translate

**Note:** If `cluster_summaries` is not provided, only the mega summary is translated. Empty summaries result in empty `summary_de` fields.

### Response (Minimal)

```json
{
  "payload": {
    "mega_summary": {
      "summary": "English mega summary text...",
      "summary_de": "Deutsche Mega-Zusammenfassung..."
    },
    "cluster_summaries": {
      "cluster_1": {
        "summary": "First cluster summary in English...",
        "summary_de": "Erste Cluster-Zusammenfassung auf Deutsch..."
      },
      "cluster_2": {
        "summary": "Second cluster summary in English...",
        "summary_de": "Zweite Cluster-Zusammenfassung auf Deutsch..."
      }
    }
  }
}
```

**Response Fields:**
- `payload` (object): Same payload structure as request
- `payload.mega_summary.summary_de` (string): German translation of mega summary
- `payload.cluster_summaries[cluster_id].summary_de` (string): German translation of each cluster summary

**Note:** All other fields in the payload are preserved unchanged. Only `summary_de` fields are added/updated.

---

## Evaluation Metrics Explanation

### Coherence (1-5)
- **5**: Excellent logical flow, clear structure, easy to follow
- **4**: Good flow with minor gaps
- **3**: Acceptable but some structural issues
- **2**: Poor flow, hard to follow
- **1**: Very poor, incoherent

### Consistency (1-5)
- **5**: Perfectly consistent with source, no contradictions
- **4**: Mostly consistent, minor discrepancies
- **3**: Generally consistent with some issues
- **2**: Several inconsistencies
- **1**: Major contradictions with source

### Relevance (1-5)
- **5**: Highly relevant, captures all key points
- **4**: Mostly relevant, minor omissions
- **3**: Generally relevant but missing some points
- **2**: Partially relevant, missing key information
- **1**: Not relevant to source

### Fluency (1-5)
- **5**: Excellent language, natural and readable
- **4**: Good language with minor issues
- **3**: Acceptable but some awkward phrasing
- **2**: Poor language quality
- **1**: Very poor, unreadable

### Tone (1-5) - Optional 5th Metric
- **5**: Perfect tone for the content type, highly appropriate and consistent
- **4**: Good tone with minor inconsistencies
- **3**: Acceptable tone but some issues with appropriateness or consistency
- **2**: Poor tone, inappropriate or inconsistent
- **1**: Very poor tone, highly inappropriate or inconsistent

**Evaluation Criteria:**
- Neutral/Objective: Balanced, factual, no evaluative language, no editorial emphasis
- Institutional: Formal, impersonal, cautious wording, avoids ideological framing, avoids marketing language, no slang, no humor, no emotionally loaded phrasing
- Appropriate for content: The tone should match the nature of the source material and intended audience

### Style (1-5) - Optional 6th Metric
- **5**: Perfect style for the content type, highly appropriate and consistent
- **4**: Good style with minor inconsistencies
- **3**: Acceptable style but some issues with appropriateness or consistency
- **2**: Poor style, inappropriate or inconsistent
- **1**: Very poor style, highly inappropriate or inconsistent

**Evaluation Criteria:**
- Journalistic: Clear, factual, inverted pyramid structure, objective reporting
- Academic: Careful wording, hedged claims, formal structure
- Executive: High-level, decision-focused, concise, strategic perspective
- Appropriate for content: The style should match the nature of the source material and intended audience

### Judge Models
- **qwen** Qwen model
- **mistral**: Mistral model
- **gemma**: Gemma model

### Aggregation and Fallback Mode

**Multi-Judge Aggregation:**
- Always uses all 3 judges automatically: qwen, mistral, gemma
- Scores are averaged across successful judges
- Each judge returns individual status: `success`, `repaired`, or `fallback`
- Standard 4 metrics (coherence, consistency, relevance, fluency) are always evaluated
- Optional metrics (tone, style) are evaluated independently when requested via `evaluate_tone` or `evaluate_style` flags
- Optional metrics use separate judge calls and do not affect standard metric evaluation

**Fallback Handling:**
- If `drop_fallbacks=true` (default): Judges with `status="fallback"` are excluded from aggregation
- If all judges fail/fallback: Returns default scores (3.0 for each metric) with `status="fallback"`
- If some judges succeed: Returns averaged scores with `status="partial"`

**Error Reasons:**
- `error_reasons` contains list of error messages from failed judges
- Format: `["model_name: error message", ...]`
- Only present if one or more judges failed

---

## Article Schema (Shared)

All endpoints that accept articles use this minimal schema:

```json
{
  "id": "string",        // Required: Unique article ID
  "title": "string",     // Required: Article title
  "body": "string",      // Required: Article body text
  "language": "string"   // Required: Language code ("en", "de", etc.)
}
```

**Optional Fields:**
- `source` (string): Source URL/name
- `published_at` (string): ISO 8601 timestamp

---

## Notes for n8n Integration

1. **Minimal Payloads**: Only send required fields to reduce network latency
2. **Batch Processing**: Process multiple articles in single requests when possible
3. **Error Handling**: All endpoints return HTTP 400/500 with error details
4. **Timestamps**: All responses include `processed_at` ISO timestamp
5. **Request IDs**: Use unique `request_id` for tracking and debugging
6. **Optional Fields**: Omit optional fields if not needed to reduce payload size

---

## Performance Tips

- **Translation**: Articles are automatically translated to English before processing
- **Caching**: Consider caching embeddings and summaries when reprocessing
- **Parallel Processing**: Backend processes articles in parallel (5 workers)
- **Minimal Centroids**: For `/cluster_update` ⚠️ **NOT IN USE** - only send centroids (not full cluster data) - kept for reference
- **Evaluation Latency**: ~2-5 seconds per evaluation (depends on judge model)
- **Multi-Judge Aggregation**: ~2-5 seconds × number of judges (parallel execution recommended)
- **Evaluation Caching**: Consider caching evaluation results for identical inputs
- **Fallback Mode**: Automatically handles judge failures with default scores (3.0 per metric)