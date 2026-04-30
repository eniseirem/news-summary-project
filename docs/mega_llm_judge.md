# Mega LLM Judge Evaluation Script (`mega_llm_judge.py`)

## Overview

The `mega_llm_judge.py` script processes batches of articles, clusters them by topic similarity, generates individual cluster summaries, and then creates a comprehensive "mega summary" that synthesizes all cluster summaries into a single high-level overview. This is designed for LLM judge evaluation workflows where you need to evaluate both individual cluster summaries and the overall mega summary quality.

## Purpose

- Generate cluster summaries from article batches
- Create a comprehensive mega summary that synthesizes all cluster summaries
- Enable evaluation of both granular (cluster-level) and high-level (mega) summarization quality
- Process multiple batches efficiently with parallel processing support

## Key Features

1. **Two-level summarization**: Generates both cluster summaries and a mega summary
2. **Parallel cluster processing**: Processes multiple clusters concurrently for improved performance
3. **Batch processing**: Supports single files or batch ranges
4. **Adaptive clustering**: Adjusts clustering parameters based on batch size
5. **Structured output**: Returns all cluster summaries and mega summary in a standardized format

## Usage Examples

### Process a single batch
```bash
python -m evaluation.mega_llm_judge \
    --input_file data/input/llm_judge_eval/batch_001.json \
    --batch_id 001
```

### Process multiple batches sequentially
```bash
python -m evaluation.mega_llm_judge \
    --input_dir data/input/llm_judge_eval \
    --batch_range 1 10
```

### Process multiple batches in parallel
```bash
python -m evaluation.mega_llm_judge \
    --input_dir data/input/llm_judge_eval \
    --batch_range 1 10 \
    --parallel
```

## Command-Line Arguments

| Argument | Description | Required |
|----------|-------------|----------|
| `--input_file` | Path to input JSON file with articles | Yes (single file mode) |
| `--input_dir` | Directory containing input files | Yes (batch mode) |
| `--batch_id` | Batch identifier (e.g., "001") | Yes (single file mode) |
| `--batch_range` | Process batches from START to END | Yes (batch mode) |
| `--output_dir` | Output directory (default: `data/output/llm_judge_eval`) | Optional |
| `--parallel` | Process multiple batches in parallel (limited to 2 concurrent) | Optional |
| `--skip_topic_labels` | Skip topic label generation (faster processing) | Optional |
| `--skip_category_labels` | Skip category label generation (saves 1 LLaMA call per cluster) | Optional |
| `--max_workers` | Maximum clusters to process in parallel (default: 5) | Optional |
| `--max_cluster_articles` | Skip clusters with more than this many articles (default: 50, set to 0 to disable) | Optional |
| `--skip_mega` | Skip mega summary generation (faster, only cluster summaries) | Optional |

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

The output includes all cluster summaries and a mega summary:

```json
{
  "article_batch_id": "batch_001",
  "cluster_summaries": {
    "cluster_1": {
      "category": "Global Politics",
      "summary": "Summary of articles in cluster 1..."
    },
    "cluster_2": {
      "category": "Economics",
      "summary": "Summary of articles in cluster 2..."
    },
    "cluster_3": {
      "category": "Technology",
      "summary": "Summary of articles in cluster 3..."
    }
  },
  "mega_summary": {
    "summary": "A comprehensive high-level summary synthesizing all cluster summaries into a single overview..."
  }
}
```

### Output File Naming

- **Mega summary**: `{batch_id}_mega_summary.json`
  - Example: `001_mega_summary.json`

## Processing Pipeline

1. **Article Loading**: Loads and validates articles from JSON input
2. **Clustering**: Uses HDBSCAN clustering with SBERT embeddings to group articles by topic similarity
   - For batches with < 10 articles: uses `min_cluster_size=1` (adjusted to 2 due to HDBSCAN requirement)
   - For larger batches: uses `min_cluster_size=2`
3. **Cluster Processing** (Parallel): For each cluster:
   - Checks cluster size and skips if too large (configurable via `--max_cluster_articles`)
   - Combines article texts
   - Generates cluster summary using LLaMA
   - Optionally assigns category label using LLaMA-based classification (can be skipped with `--skip_category_labels`)
   - Optionally generates topic label (can be skipped with `--skip_topic_labels`)
4. **Mega Summary Generation**: 
   - Combines all cluster summaries (can be skipped with `--skip_mega`)
   - Generates a high-level mega summary using LLaMA that synthesizes all cluster summaries
5. **Output**: Formats and saves all cluster summaries and the mega summary

## Technical Details

- **Clustering Method**: HDBSCAN with SBERT embeddings (`all-MiniLM-L6-v2`)
- **Minimum Cluster Size**: 2 articles (HDBSCAN requirement)
- **Large Cluster Handling**: 
  - Clusters with more than 50 articles (configurable) are automatically skipped to avoid timeouts
  - Clusters with >500K characters are also skipped
  - Skipped clusters receive placeholder summaries indicating why they were skipped
- **Parallel Processing**: 
  - Uses `ThreadPoolExecutor` for concurrent cluster processing (default: 5 clusters, configurable via `--max_workers`)
  - Supports parallel batch processing (up to 2 batches concurrently)
- **Performance Optimizations**:
  - `--skip_topic_labels`: Skips topic label generation (saves time per cluster)
  - `--skip_category_labels`: Skips category label generation (saves 1 LLaMA call per cluster)
  - `--max_cluster_articles`: Automatically skips very large clusters that would likely timeout
- **LLM Engine**: Uses Ollama with LLaMA models for summarization and categorization
- **Two-Stage Summarization**:
  1. **Cluster summaries**: Individual summaries for each topic cluster
  2. **Mega summary**: High-level synthesis of all cluster summaries (can be skipped with `--skip_mega`)

## Use Cases

1. **LLM Judge Evaluation**: Evaluate both cluster-level and mega-level summarization quality
2. **Comprehensive Overview**: Generate a high-level summary of all topics in a batch
3. **Batch Processing**: Process multiple article batches and generate mega summaries
4. **Quality Assessment**: Compare cluster summaries against the mega summary for consistency
5. **Topic Coverage Analysis**: Understand how well the mega summary captures all cluster topics

## Comparison with `cluster_llm_judge.py`

| Feature | `mega_llm_judge.py` | `cluster_llm_judge.py` |
|---------|---------------------|------------------------|
| **Output** | All clusters + mega summary | Single representative cluster |
| **Selection** | Includes all clusters | Filters by category, selects largest |
| **Use Case** | Comprehensive evaluation | Category-specific evaluation |
| **Articles** | Cluster summaries only | Cluster summary + source articles |
| **Focus** | High-level synthesis | Detailed cluster analysis |

## Notes

- The script processes **all clusters** in a batch, not just one
- Very large clusters (>50 articles or >500K chars) are automatically skipped to prevent timeouts
- The mega summary synthesizes **all cluster summaries** into a single comprehensive overview (can be skipped with `--skip_mega`)
- Articles not assigned to any cluster are logged as warnings
- Output files are saved to `data/output/llm_judge_eval/` by default
- Requires Ollama to be running for LLaMA-based summarization and categorization
- Parallel batch processing is limited to 2 concurrent batches to avoid overwhelming Ollama
- **Performance Tips**:
  - Use `--skip_topic_labels` and `--skip_category_labels` for faster processing when labels aren't needed
  - Use `--max_cluster_articles 30` to skip very large clusters that would likely timeout
  - Increase `--max_workers` (e.g., 8-10) only if Ollama can handle the load
  - For very large batches, consider using `--skip_mega` to generate only cluster summaries

## Example Workflow

1. **Input**: Batch of 50 articles covering various topics
2. **Clustering**: Articles grouped into 5 clusters (e.g., Politics, Economics, Technology, Sports, Health)
3. **Cluster Summaries**: 5 individual summaries generated, one per cluster
4. **Mega Summary**: Single comprehensive summary synthesizing all 5 cluster summaries
5. **Output**: JSON file with all cluster summaries and the mega summary

This enables evaluation of:
- How well each cluster summary represents its articles
- How well the mega summary captures all cluster topics
- Consistency between cluster summaries and mega summary
