# Cluster LLM Judge Evaluation Script (`cluster_llm_judge.py`)

## Overview

The `cluster_llm_judge.py` script processes batches of articles, clusters them by topic similarity, and extracts a single representative cluster summary with its associated source articles based on a specified category. This is designed for LLM judge evaluation workflows where you need to compare cluster summaries against their original articles.

## Purpose

- Generate cluster summaries from article batches
- Select a representative cluster by category
- Extract source articles associated with the selected cluster
- Enable evaluation of cluster summary quality against original articles

## Key Features

1. **Category-based cluster selection**: Filters clusters by category and selects the largest/most representative one
2. **Parallel processing**: Processes multiple clusters concurrently for improved performance
3. **Batch processing**: Supports single files or batch ranges
4. **Category listing**: Lists all available categories in a batch before selection
5. **Structured output**: Returns cluster summary with associated articles in a standardized format

## Usage Examples

### Extract a specific cluster by category
```bash
python -m evaluation.cluster_llm_judge \
    --input_file data/input/llm_judge_eval/batch_001.json \
    --batch_id 001 \
    --category "Global Politics"
```

### List available categories
```bash
python -m evaluation.cluster_llm_judge \
    --input_file data/input/llm_judge_eval/batch_001.json \
    --batch_id 001 \
    --list_categories
```

### Process multiple batches
```bash
python -m evaluation.cluster_llm_judge \
    --input_dir data/input/llm_judge_eval \
    --batch_range 1 10 \
    --category "Global Politics" \
    --parallel
```

## Command-Line Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `--input_file` | Path to input JSON file with articles | Yes (single file mode) |
| `--input_dir` | Directory containing input files | Yes (batch mode) |
| `--batch_id` | Batch identifier (e.g., "001") | Yes (single file mode) |
| `--batch_range` | Process batches from START to END | Yes (batch mode) |
| `--category` | Category to filter clusters (e.g., "Global Politics") | Optional |
| `--list_categories` | List all available categories | Optional |
| `--output_dir` | Output directory (default: `data/output/llm_judge_eval`) | Optional |
| `--parallel` | Process multiple batches in parallel | Optional |

## Input Format

The script accepts JSON files with articles in one of these formats:

### Format 1: List of articles
```json
[
  {
    "id": "article_1",
    "url": "https://example.com/article1",
    "title": "Article Title",
    "body": "Article content...",
    "language": "en",
    "source": "SourceName",
    "published_at": "2025-01-01T00:00:00Z",
    "category": "politics"
  }
]
```

### Format 2: Dictionary with articles key
```json
{
  "articles": [
    {
      "id": "article_1",
      "url": "https://example.com/article1",
      "title": "Article Title",
      "body": "Article content...",
      ...
    }
  ]
}
```

## Output Format

When a category is specified, the output is a single cluster with its summary and source articles:

```json
{
  "article_batch_id": "batch_001",
  "cluster_id": "cluster_2",
  "category": "Global Politics",
  "topic_label": "Debt Ceiling Crisis Looms",
  "article_count": 5,
  "clustering_quality": "good",
  "cluster_summary": {
    "summary": "A comprehensive summary of all articles in this cluster..."
  },
  "source_articles": [
    {
      "article_id": "a_0001",
      "title": "Article Title 1",
      "text": "Full article text content..."
    },
    {
      "article_id": "a_0002",
      "title": "Article Title 2",
      "text": "Full article text content..."
    }
  ]
}
```

### Output File Naming

- **Single cluster**: `{batch_id}_cluster_{cluster_id}_{category}.json`
  - Example: `001_cluster_cluster_2_global_politics.json`
- **All clusters** (no category): `{batch_id}_all_clusters.json`

## Processing Pipeline

1. **Article Loading**: Loads and validates articles from JSON input
2. **Clustering**: Uses HDBSCAN clustering with SBERT embeddings to group articles by topic similarity
3. **Cluster Processing**: For each cluster:
   - Generates cluster summary using LLaMA
   - Assigns category label using LLaMA-based classification
   - Generates topic label
   - Extracts associated articles
4. **Selection**: If category is specified:
   - Filters clusters matching the category
   - Selects the largest cluster (most articles) as the representative
5. **Output**: Formats and saves the selected cluster with its summary and source articles

## Technical Details

- **Clustering Method**: HDBSCAN with SBERT embeddings (`all-MiniLM-L6-v2`)
- **Minimum Cluster Size**: 2 articles (HDBSCAN requirement)
- **Parallel Processing**: Uses `ThreadPoolExecutor` for concurrent cluster processing
- **LLM Engine**: Uses Ollama with LLaMA models for summarization and categorization
- **Category Matching**: Case-insensitive category matching

## Use Cases

1. **LLM Judge Evaluation**: Compare cluster summaries against original articles for quality assessment
2. **Category-Specific Analysis**: Extract representative clusters for specific news categories
3. **Batch Processing**: Process multiple article batches and extract clusters by category
4. **Quality Control**: Verify that cluster summaries accurately represent their source articles

## Related Scripts

- `mega_llm_judge.py`: Generates mega summaries from all clusters (comprehensive overview)
- `cluster_llm_judge.py`: Extracts single representative clusters by category (focused analysis)

## Output Fields

- **`article_batch_id`**: Identifier for the batch being processed
- **`cluster_id`**: Identifier for the selected cluster
- **`category`**: News category assigned to the cluster (e.g., "Global Politics", "Economics")
- **`topic_label`**: Specific topic label for the cluster (e.g., "Debt Ceiling Crisis Looms")
- **`article_count`**: Number of articles in the selected cluster
- **`clustering_quality`**: Indicates clustering quality - "good" if expected number of clusters found, "limited" otherwise
- **`cluster_summary`**: Object containing the summary text
- **`source_articles`**: Array of source articles with `article_id`, `title`, and `text` fields

## Notes

- The script selects the **largest cluster** when multiple clusters match the specified category
- **`clustering_quality`** field indicates whether clustering found the expected number of clusters based on article count (at least 3, or ~1 cluster per 50 articles)
- Articles not assigned to any cluster are logged as warnings
- Output files are saved to `data/output/llm_judge_eval/` by default
- Requires Ollama to be running for LLaMA-based summarization and categorization
- Topic and category labels are generated in parallel for efficiency
