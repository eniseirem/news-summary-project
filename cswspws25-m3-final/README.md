# LLM News Summarization Pipeline

**Milestone 3 — Optimized n8n Integration, Incremental Clustering, OpenSearch Workflow**
**Branch:** `m3-final`

This repository contains the LLM-pipeline/backend service for a modular news summarization system.
It powers topic clustering, multi-article summarization, mega summaries, tone rewriting, and evaluation using **LLaMA 3** and **SBERT**, and integrates with a crawler, n8n workflows, OpenSearch, and a frontend application.

This README provides a **high-level technical overview** so engineers can understand the system end-to-end and continue building new features confidently.

---

## **System Overview**

The system is composed of five major parts:

```
Crawler → Database → n8n → LLM-Pipeline/Backend (this repo) → Frontend
                                  ↓                    ↓
                            OpenSearch            LLaMA 3 (Ollama)
```

### Component Responsibilities

| Component                            | Responsibility                                                    |
| -----------------------              | ----------------------------------------------------------------- |
| **Crawler**                          | Collects raw news articles and metadata                           |
| **Database**                         | Stores cleaned articles and metadata                              |
| **n8n**                              | Orchestrates workflow, applies filters, handles article-to-cluster matching via OpenSearch k-NN, manages cluster centroids |
| **OpenSearch**                       | Stores clusters, article summaries, centroids; provides k-NN similarity search |
| **LLM-Pipeline/Backend (this repo)** | Clustering, summarization, tone rewriting, translation, evaluation, LLaMA orchestration |
| **Frontend**                         | UI, filtering controls, translation, presentation                 |
| **Ollama**                           | Hosts LLaMA 3 for inference                                       |

---

## **Pipeline Flow (n8n Workflow)**

### Initial Clustering (`/cluster_create`)

1. **n8n** sends articles to `/cluster_create`
2. **Backend**:
   * Translates articles to English (parallel, 5 workers, cached)
   * Skips translation for English articles
   * Summarizes articles individually to 100 words (parallel, 5 workers)
   * Generates SBERT embeddings from article summaries
   * Clusters articles using HDBSCAN
   * Calculates cluster centroids
   * Returns clusters + article summaries (for caching)
3. **n8n** stores clusters and article summaries in OpenSearch

### Incremental Clustering (`/cluster_update`) ⚠️ Currently Not in Use

**Note:** n8n now handles cluster matching directly, so `/cluster_update` is currently skipped.

**Intended workflow (when enabled):**
1. **n8n** receives new articles
2. **n8n** uses OpenSearch k-NN search to find relevant cluster centroids
3. **n8n** matches articles to clusters (using similarity threshold)
4. **n8n** updates matched cluster centroids (weighted average)
5. **n8n** sends unmatched articles to `/cluster_update`
6. **Backend**:
   * Translates unmatched articles (parallel, cached)
   * Summarizes to 100 words (parallel)
   * Clusters unmatched articles using HDBSCAN
   * Returns new clusters + article summaries
7. **n8n** stores new clusters and summaries in OpenSearch

### Cluster Summarization (`/cluster_summarize`)

1. **n8n** sends clusters + cached article summaries to `/cluster_summarize`
2. **Backend**:
   * Uses cached summaries (if provided) or generates new ones
   * Generates cluster summaries from article summaries
   * Returns cluster summaries
3. **n8n** stores cluster summaries in OpenSearch

### Mega Summarization (`/mega_summarize`)

1. **n8n** sends cluster summaries to `/mega_summarize`
2. **Backend**:
   * Combines cluster summaries into mega summary
   * Returns mega summary
3. **n8n** stores mega summary

### Post-Processing

- **Styling** (`/summary_style`): Rewrites summaries with tone/style/format
- **Translation** (`/translate_cluster_summary`, `/translate_mega_summary`): English → German
- **Topic Labeling** (`/topic_label`): Generates short topic labels
- **Category Labeling** (`/category_label`): Assigns predefined categories
- **Keyword Extraction** (`/keyword_extract`): LDA + TF-IDF keywords
- **Evaluation** (`/evaluate_cluster`, `/evaluate_mega`): LLM-as-judge evaluation

---

## **Core Features**

### Clustering & Summarization
* **Initial Clustering**: HDBSCAN clustering with SBERT embeddings
* **Incremental Clustering**: ⚠️ Currently handled by n8n (matching + centroid updates); `/cluster_update` endpoint skipped
* **Article Summarization**: 100-word summaries (prevents truncation)
* **Cluster Summarization**: Length-controlled summaries (200 + 150×num_clusters, max 1000 words)
* **Mega Summarization**: Global summaries across all clusters

### Performance Optimizations
* **Parallel Translation**: 5 workers, cached results (LRU cache, 1000 entries)
* **Parallel Summarization**: 5 workers for batch processing
* **Translation Caching**: MD5-based cache key (language + title + body)
* **Skip English Translation**: Early exit for English articles
* **Cached Summaries**: n8n provides cached article summaries to avoid regeneration

### LLM Integration
* **LLaMA 3** via Ollama for summarization, topic labeling, category labeling, styling
* **MarianMT** for translation (multi-language → English, English → German)
* **SBERT** (sentence-transformers) for 384-dimensional embeddings

### Evaluation
* **LLM-as-Judge**: Multiple judges (qwen, mistral, gemma) with fallback
* **Metrics**: Coherence, consistency, relevance, fluency
* **Fallback Handling**: Configurable drop_fallbacks flag

---

## **API Endpoints**

### n8n Workflow Endpoints

#### `POST /cluster_create`
Initial clustering of articles. Returns clusters and article summaries for caching.

**Processing:**
1. Translate articles to English (parallel, 5 workers, cached)
2. Summarize articles to 100 words (parallel, 5 workers)
3. Generate SBERT embeddings
4. Cluster using HDBSCAN
5. Calculate centroids
6. Return clusters + article summaries

**Response includes:** `clusters[]`, `article_summaries{}`

---

#### `POST /cluster_update` ⚠️ Currently Not in Use

**Note:** n8n now handles cluster matching directly, so this endpoint is currently skipped.

**Intended purpose:** Cluster unmatched articles using HDBSCAN when n8n cannot match them to existing clusters.

**Processing (when enabled):**
1. Translate unmatched articles (parallel, cached)
2. Summarize to 100 words (parallel)
3. Cluster unmatched articles using HDBSCAN
4. Return new clusters + article summaries

**Request:** `unmatched_articles[]`, `min_cluster_size`

**Response includes:** `new_clusters[]`, `article_summaries{}`

---

#### `POST /cluster_summarize`
Generate cluster summaries from pre-clustered data using cached article summaries.

**Processing:**
1. Use cached article summaries (if provided) or generate new ones
2. Generate cluster summaries from article summaries
3. Return cluster summaries

**Request:** `clusters[]`, `articles[]`, `article_summaries{}` (optional)

**Response includes:** `clusters[]` with `summary` field

---

#### `POST /mega_summarize`
Generate mega summary from existing cluster summaries.

**Processing:**
1. Combine cluster summaries into mega summary
2. Return mega summary

**Request:** `cluster_summaries{}`

**Response includes:** `mega_summary`

---

### Post-Processing Endpoints

#### `POST /summary_style`
Rewrites summaries with writing style, output format, and institutional tone.

**Options:**
- **Writing Style**: journalistic, academic, executive
- **Output Format**: paragraph, bullet_points, tldr, sections
- **Institutional Tone**: boolean flag

---

#### `POST /translate_cluster_summary`
Translates cluster summary from English to German.

**Response adds:** `summary_de` field

---

#### `POST /translate_mega_summary`
Translates mega summary and cluster summaries from English to German.

**Response adds:** `summary_de` fields

---

#### `POST /topic_label`
Generates short topic labels (max 4 words) for summaries.

---

#### `POST /category_label`
Assigns summaries to predefined categories:
- Global Politics
- Economics
- Sports
- Events
- General News

---

#### `POST /keyword_extract`
Extracts keywords using LDA and/or TF-IDF.

**Options:**
- `extract_lda`: boolean (default: true)
- `extract_tfidf`: boolean (default: true)
- `num_topics`: int (default: 3)
- `top_k`: int (default: 5)

---

### Evaluation Endpoints

#### `POST /evaluate_cluster`
Evaluates cluster summaries using LLM-as-judge.

**Judges:** qwen, mistral, gemma (with fallback)

**Metrics:** coherence, consistency, relevance, fluency

**Options:**
- `drop_fallbacks`: boolean (default: true)

---

#### `POST /evaluate_mega`
Evaluates mega summaries using LLM-as-judge.

**Same as `/evaluate_cluster` but for mega summaries.**

---

### Legacy Endpoints

#### `POST /summarize_batch`
Simple multi-article summary (no clustering). Used for small article sets.

---

#### `POST /cluster_summary`
Full pipeline: cluster → cluster summaries → keywords → topic labels → category labels.

**Note:** Legacy endpoint, kept for compatibility. New n8n workflow uses `/cluster_create` + `/cluster_summarize`.

---

#### `POST /summarize_clustered`
Full pipeline: cluster → cluster summaries → mega summary.

**Note:** Legacy endpoint, kept for compatibility. New n8n workflow uses `/cluster_create` + `/cluster_summarize` + `/mega_summarize`.

---

#### `POST /cluster_maintenance`
Maintenance operations for clusters (merging, splitting, cleanup).

---

#### `GET /cluster_stats`
Statistics about clusters (counts, sizes, distributions).

---

## **Performance Optimizations**

### Translation Optimizations
- **Parallel Processing**: 5 workers for concurrent translation
- **Caching**: LRU cache (1000 entries) with MD5 keys (language + title + body)
- **Skip English**: Early exit for English articles (no translation needed)
- **Lazy Model Loading**: MarianMT models loaded on first use

### Summarization Optimizations
- **Parallel Processing**: 5 workers for batch summarization
- **100-Word Summaries**: Prevents truncation in downstream processing
- **Cached Summaries**: n8n provides cached summaries to avoid regeneration

### Clustering Optimizations
- **SBERT Embeddings**: Fast 384-dimensional embeddings
- **HDBSCAN**: Efficient density-based clustering
- **Centroid Caching**: n8n stores centroids in OpenSearch for fast k-NN search

---

## **Frontend Integration Notes**

* Frontend **defines the 5 canonical categories** (product taxonomy)
* Backend does not invent categories
* LLaMA classifies summaries into one of the 5 categories
* Cluster labels are **not categories** — they are section headers
* Translation can happen on backend (`/translate_cluster_summary`, `/translate_mega_summary`) or frontend
* Backend returns English output by default

---

## **Evaluation**

Evaluation uses **LLM-as-Judge** with multiple judges and fallback:

* **Judges**: qwen, mistral, gemma
* **Metrics**: coherence, consistency, relevance, fluency
* **Fallback**: If one judge fails, others continue; `drop_fallbacks` controls aggregation
* **Scoring**: 1.0-5.0 scale, aggregated across judges

Evaluation operates on:
* Generated summaries (cluster or mega)
* Reference summaries (optional)
* Stored results for reporting

Evaluation does **not** affect runtime summarization.

---

## **Project Structure**

```
src/
  api/
    endpoints/
      # n8n Workflow Endpoints
      cluster_create.py          # Initial clustering
      cluster_update.py          # Incremental clustering (unmatched articles) ⚠️ Currently not in use
      cluster_summarize.py      # Cluster summaries from pre-clustered data
      mega_summarize.py         # Mega summaries from cluster summaries
      
      # Post-Processing Endpoints
      summary_style.py          # Styling (tone/style/format)
      translate_cluster_summary.py  # English → German (cluster)
      translate_mega_summary.py     # English → German (mega)
      topic_label.py            # Topic labeling
      category_label.py         # Category labeling
      keyword_extract.py        # LDA + TF-IDF keywords
      
      # Evaluation Endpoints
      evaluate_cluster.py       # LLM-as-judge (cluster)
      evaluate_mega.py          # LLM-as-judge (mega)
      
      # Legacy Endpoints
      summarize_batch.py        # Simple batch summarization
      cluster_maintenance.py    # Cluster maintenance operations
      cluster_stats.py         # Cluster statistics
      other_endpoints/         # Legacy M2 endpoints
        cluster_summary_m2.py
        summarize_clustered_m2.py
        summarize_with_style_warnings.py
    
    schemas.py                  # Pydantic models
    main.py                     # FastAPI app initialization
    
  llm_engine/
    # Summarization
    model_loader.py            # Backend selector (BART/LLaMA)
    summarizer_bart.py         # BART summarization (legacy)
    summarizer_llama.py        # LLaMA summarization (primary)
    llama_client.py            # Ollama client
    
    # Translation
    multilingual.py            # Multi-language → English (with caching)
    translate_en_to_de.py      # English → German
    
    # Styling
    tone_rewriter_llama.py     # Tone/style rewriter (with warnings)
    tone_rewriter_llama_plain.py  # Plain tone/style rewriter
    
  clustering/
    cluster_pipeline.py        # HDBSCAN clustering logic
    embeddings.py              # SBERT embedding generation
    
  topic_labeling/
    llama_topic_labeler.py     # LLaMA-based topic labeling
    llama_lda_pipeline.py      # LLaMA + LDA category labeling
    lda_pipeline.py            # LDA keyword extraction
    tfidf_pipeline.py          # TF-IDF keyword extraction
    label_comparison_runner.py # Offline comparison (M2)
    label_comparison_runner1.py # Enhanced comparison (M2)
    
  evaluation/
    evaluation_runner.py       # Evaluation orchestration
    llm_judge.py              # LLM-as-judge implementation
    metrics.py                # ROUGE, BERTScore, etc.
    pipeline_benchmarks.py    # Benchmarking utilities
    
  tests/
  results/
  
docs/
  m3_endpoints_format.md       # Endpoint request/response formats
  endpoint_examples_screenshots.md  # Example requests/responses
  
requirements.txt              # Python dependencies
docker-compose.yaml          # Docker orchestration
Dockerfile                   # API container build
```

---

## **Installation & Local Development**

### Requirements

* Python 3.10+
* Ollama (for LLaMA 3 inference)
* PyTorch (for MarianMT translation models)
* Docker (optional, for containerized deployment)

### Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd cswspws25
   ```

2. **Create virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install and run Ollama**
   ```bash
   # macOS
   brew install ollama
   
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Pull LLaMA 3 model
   ollama pull llama3
   
   # Run Ollama (in separate terminal)
   ollama serve
   ```

5. **Set environment variables** (optional)
   ```bash
   # Create .env file
   LLM_BACKEND=llama  # or "bart" for legacy
   OLLAMA_BASE_URL=http://localhost:11434
   ```

6. **Run the backend**
   ```bash
   # From project root
   cd src
   uvicorn api.main:app --reload --port 8000
   
   # Or use the start script
   ./start_server.sh
   ```

7. **Access API documentation**
   ```
   http://localhost:8000/docs
   ```

### Development Scripts

- `start_server.sh`: Start the FastAPI server
- `restart_ollama.sh`: Restart Ollama service

---

## **Docker Deployment**

### Build and run API container

```bash
docker build -t news-llm-backend .
docker run -p 8000:8000 news-llm-backend
```

### Docker Compose (with Ollama)

```bash
docker-compose up -d
```

This starts:
- **API service** (port 8000)
- **Ollama service** (port 11434)

Access:
- API: `http://localhost:8000/docs`
- Ollama: `http://localhost:11434`

---

## **Technical Details**

### Translation Caching

Translation results are cached using an LRU cache (max 1000 entries):
- **Cache Key**: MD5 hash of `language:title:body`
- **Cache Hit**: Returns cached translation immediately
- **Cache Miss**: Translates and stores result
- **English Articles**: Skipped entirely (no translation needed)

### Summarization

- **Article Summaries**: 100 words (prevents truncation in downstream processing)
- **Cluster Summaries**: Dynamic length (200 + 150×num_clusters, max 1000 words)
- **Mega Summaries**: Combines all cluster summaries

### Clustering

- **Algorithm**: HDBSCAN (density-based clustering)
- **Embeddings**: SBERT (sentence-transformers, 384 dimensions)
- **Centroids**: Average of article embeddings in cluster
- **Matching**: Cosine similarity (n8n handles via OpenSearch k-NN)

### LLM Backend

- **Primary**: LLaMA 3 via Ollama (deterministic, temperature=0.0)
- **Legacy**: BART (facebook/bart-large-cnn) for backward compatibility
- **Selection**: Controlled via `LLM_BACKEND` environment variable

---

## **Roadmap**

* n8n workflow integration with OpenSearch
* Parallel translation and summarization
* Translation caching
* n8n cluster matching (incremental clustering handled by n8n)
* LLM-as-judge evaluation with fallback
* Full frontend integration with new endpoints
* Performance benchmarking and optimization
* Cluster maintenance automation

---

## **Contributing**

* Create feature branches for new modules
* Maintain consistent style and naming
* Document new endpoints in `/docs`
* Add tests where applicable to `/tests`
* Add results of tests to `/results`
* Run locally before submitting merge requests


---

## Authors and Acknowledgment
LLM-Processing-Pipeline/Backend Group
Part of the Semantic Technologies Project - LLM News-Based Agent

## Team Members
- Abisola Ajuwon
- Zhixin Mao
- Theresia Palser

---

## **License**

This project is licensed under the **MIT License** unless otherwise specified.

## Project Status
Active Development. Core modules are functional. Integration testing in progress.
