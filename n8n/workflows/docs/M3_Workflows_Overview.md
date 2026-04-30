# M3 Workflows Overview

## Goal of the M3 Pipeline

The M3 workflows together implement a full news understanding pipeline:

- Ingest raw articles from many news sources
- Cluster them incrementally using KNN
- Generate per-cluster summaries and semantic labels
- Categorize clusters into higher-level categories
- Generate mega summaries per category
- Expose the results via webhook / styling / translation endpoints

This document is a **map of all M3 workflows**. For each one, there is a dedicated technical doc with full details.

---

## 1. M3 – News Crawler

- **Workflow:** `M3 - News Crawler` (`AtP3zRYU32PlpvMW0UdNn.json`)
- **Doc:** `M3_News_Crawler.md`

**What it does:**  
Master crawler that calls the crawler API for multiple sources (CNN, Guardian, FAZ, NTV, etc.), normalizes the articles, and writes them into the `articles` index in OpenSearch, with detailed logging into `articles_request`.

**Key outputs:**

- `articles` – canonical raw articles
- `articles_request` – crawl/index logs and run summaries

---

## 2. M3 – Incremental Clustering with KNN Similarity

- **Workflow:** `M3 - Incremental Clustering with KNN Similarity` (`k7AKZ33FOgLggBAo.json`)
- **Doc:** `M3_Incremental_Clustering_KNN.md`

**What it does:**  
Incrementally clusters unclustered articles using an LLM and a KNN-based merge/create decision.

**Highlights:**

- Reads **unclustered** articles from `articles`.
- Calls LLM `/cluster_create` to get proposed clusters and article summaries.
- For each proposed cluster:
  - Runs KNN against `clusters.centroid_embedding` (k=20, threshold=0.75, 384‑dim).
  - Merges into an existing cluster if similarity ≥ 0.75, otherwise creates a new one.
- Writes:
  - `clusters`
  - `article_summaries`
  - `llm_batch` (batch tracking)

**Related workflows:**  
Also see `M3_Clustering_Summary_Label.md` for an extended version with integrated summaries and labels.

---

## 3. M3 – Clustering + Summary + Label (Extended Incremental)

- **Workflow:** `M3 - Clustering + Summary + Label` (`F1V4epzdPhq4fb3Y.json`)
- **Doc:** `M3_Clustering_Summary_Label.md`

**What it does:**  
Extends the incremental KNN clustering to also generate cluster summaries, topic labels, and keywords in a single pipeline.

**Highlights:**

- Reuses the **same KNN logic** as the incremental workflow (k=20, threshold=0.75, 384‑dim embeddings).
- Writes to:
  - `clusters`
  - `article_summaries`
  - `cluster_summaries` (via sub-workflow)
  - `llm_batch`
- Calls sub-workflow **`cluster summary and label`** for each cluster to enrich clusters with:
  - Human-readable cluster summaries
  - Topic labels
  - Keywords

**Related workflows:**  
Also see `M3_Cluster_Summary_And_Label.md` for sub-workflow details.

---

## 4. M3 – Cluster Summary and Label (Sub-workflow)

- **Workflow:** `cluster summary and label` (`t0axUOUgpQYcZyXC.json`)
- **Doc:** `M3_Cluster_Summary_And_Label.md`

**What it does:**  
Given a cluster (and its articles), creates a cluster summary, a topic label, and keywords, and writes them to OpenSearch.

**Highlights:**

- LLM calls:
  - `/cluster_summarize` → main cluster summary
  - `/topic_label` → topic label
  - `/keyword_extract` → keyword list
- Writes:
  - `cluster_summaries`
  - updates `clusters` with `topic_label`
  - `keywords` index with extracted keywords
- Optionally triggers the **categorization** workflow for further processing.

---

## 5. M3 – Category Mapping for Clusters (Sub-workflow)

- **Workflow:** `category mapping for clusters` (`KYAJn4vJ1sQr8zrP.json`)
- **Doc:** `M3_Category_Mapping_For_Clusters.md`

**What it does:**  
Takes a single cluster’s summary and metadata, calls LLM to decide its **semantic category**, and writes that category back into the `clusters` index.

**Highlights:**

- LLM endpoint: `/category_label`.
- Input: `_cluster_doc_id`, `cluster_id`, `summary`, `article_count`, `article_ids`.
- Output: `clusters/{_cluster_doc_id}` with `category` and `updated_at`.

**Usage:**  
Used inside **M3 Categorize Clusters Workflow** as the per-cluster categorization step.

---

## 6. M3 – Categorize Clusters Workflow (Main categorization)

- **Workflow:** `M3 - Categorize Clusters Workflow`
- **Doc:** `M3_Categorize_Clusters_Workflow_Technical_Overview.md`

**What it does:**  
Finds clusters that have **no category** yet, ensures they have summaries, assigns categories to them, and then generates **mega summaries per category**.

**Highlights:**

- Stage 1 – Categorization:
  - Finds clusters without `category` in `clusters`.
  - Ensures each has a summary (calls `cluster summary and label` when needed).
  - Calls `category mapping for clusters` to set `category`.
- Stage 2 – Mega summaries:
  - Groups categorized clusters by category.
  - Builds `cluster_summaries` maps per category.
  - Calls backend `/mega_summary_from_clusters` and writes to `mega_summaries`.

**Related workflows:**  
Also see:

- `M3_Category_Mapping_For_Clusters.md`
- `M3_Cluster_Summary_And_Label.md`
- `M3_Mega_Summary_Workflow.md`
- `M3_Mega_Summary_Sub_Workflow.md`

---

## 7. M3 – Mega Summary Workflow (Orchestrator)

- **Workflow:** `M3 - Mega Summary Workflow` (`xprLf76Ve2AbQ5eH7-CLU.json`)
- **Doc:** `M3_Mega_Summary_Workflow.md`

**What it does:**  
Orchestrates mega summary generation for **all categories** that already have clusters.

**Highlights:**

- Reads clusters with `category` from `clusters`.
- Groups them by category.
- For each category:
  - Fetches cluster summaries from `cluster_summaries`.
  - Builds a `cluster_summaries` map and `request_id` (`mega_{category}_{ts}`).
  - Calls the **`mega summary`** sub-workflow.

**Related workflows:**  
Also see `M3_Mega_Summary_Sub_Workflow.md` for the per-category LLM call.

---

## 8. M3 – Mega Summary (Sub-workflow)

- **Workflow:** `mega summary` (`ncmTMNFvPv5Jt8Sj.json`)
- **Doc:** `M3_Mega_Summary_Sub_Workflow.md`

**What it does:**  
Given all cluster summaries for a single category, creates one **mega summary document** in `mega_summaries`.

**Highlights:**

- LLM endpoint: `/mega_summarize`.
- Uses `request_id` naming convention to embed the category name.
- Writes one document per category into `mega_summaries` with counts and IDs.

---

## 9. M3 – Webhook Cluster Summary

- **Workflow:** `Milestone 3 - Webhook` (`7PCQD8l17QBqNg0mmrtRP.json`)
- **Doc:** `M3_Webhook_Cluster_Summary.md`

**What it does:**  
Public webhook endpoint that, given filters (timewindow, category, keywords), returns a **clustered summary response** using existing cluster and article summaries.

**Highlights:**

- Path: `/webhook/cluster-summary`.
- Can either:
  - Use `cluster_summaries` to get article IDs by cluster, then fetch `article_summaries`; or
  - Directly query `article_summaries` (no cluster filter).
- Calls LLM `/cluster_summary` to produce a rich “batch summary” response.
- If the request body includes `"language": "de"`, the workflow calls the **`translation for webhook`** sub‑workflow, translates the `final_summary` via `/translate_cluster_summary`, and returns the translated German summary in the webhook response.
- Stores:
  - `batch_summaries`
  - `llm_batch` tracking docs.

**Related workflows:**  
Also see:

- `M3_Incremental_Clustering_KNN.md`
- `M3_Clustering_Summary_Label.md`

for how clusters and summaries are produced upstream.

---

## 10. M3 – Summary Style Workflow

- **Workflow:** `m3 - summary_style` (`854Jg3_83NQdqeiToIatJ.json`)
- **Doc:** `M3_Summary_Style_Workflow.md`

**What it does:**  
Webhook that takes a **category + style options** and returns a **styled version** of a summary (e.g. academic vs journalistic, bullets vs paragraphs).

**Highlights:**

- Normalizes:
  - `writing_style` (Journalistic, Academic, Executive, LinkedIn)
  - `output_format` (Paragraph, Bullet Points, TL;DR, Sections)
  - `editorial_tone` (Institutional / Neutral / Default).
- Fetches the latest summary for a category from `cluster_summaries`.
- Calls LLM `/summary_style` and returns just the styled text + metadata.

---

## 11. M3 – Translation Workflow

- **Workflow:** `M3 - translation` (`4-1lq2GOUd_Tzxgw85mrb.json`)
- **Doc:** `M3_Translation_Workflow.md`

**What it does:**  
Bulk‑translates summaries, mega summaries, and categories from several indices into **German**, and writes the translated fields back.

**Highlights:**

- Operates on:
  - `cluster_summaries`
  - `mega_summaries`
  - `news_cluster_summaries`
  - `category_label`
- LLM endpoint: `/translate_cluster_summary`.
- Adds fields such as:
  - `summary_translated`, `summary_translated_language`
  - `mega_summary_translated`, `mega_summary_translated_language`
  - `category_translated`, `category_translated_language`

---

## 12. How It All Fits Together

High-level data flow:

1. **Ingest raw articles**
   - `M3 - News Crawler` → `articles`, `articles_request`

2. **Cluster & summarize**
   - `M3 Incremental Clustering with KNN` **or** `M3 - Clustering + Summary + Label`
   - `cluster summary and label` (sub-workflow)
   - → `clusters`, `article_summaries`, `cluster_summaries`, `keywords`, `llm_batch`

3. **Categorize clusters & build category views**
   - `M3 - Categorize Clusters Workflow`
   - `category mapping for clusters` (sub-workflow)
   - `M3 - Mega Summary Workflow` + `mega summary` (sub-workflow)
   - → `clusters` with `category`, `mega_summaries`

4. **Serve & adapt content**
   - `Milestone 3 - Webhook` → cluster summaries API
   - `m3 - summary_style` → styled summaries API
   - `M3 - translation` → translated summaries/categories in OpenSearch

With this overview, you can open any of the `M3_*.md` docs to dive into the detailed node-by-node behavior of a specific workflow.

