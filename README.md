# SWP News Summary Monorepo

SWP News Summary is an end-to-end news processing platform that crawls articles, clusters related stories, generates summaries and labels, categorizes topics, and serves results via webhooks and a dashboard.

This repository is a **monorepo** composed of multiple previously separate project branches, now kept together in one place for easier setup and collaboration.

## Project Purpose

The project is designed to turn large streams of raw news into structured, readable intelligence.
The pipeline continuously gathers articles and produces:

- grouped stories (clusters of related articles),
- concise summaries and labels,
- category-level overviews ("mega summaries"),
- dashboard-ready and webhook-accessible outputs.

This is especially useful for monitoring topics over time and quickly spotting major developments across multiple publishers.

## Core Capabilities

- **Automated ingestion** from multiple news sources via crawler endpoints.
- **Incremental clustering** so newly crawled articles can be attached to existing story groups.
- **LLM-powered enrichment** for summarization, topic labeling, keyword extraction, and translation.
- **Category mapping and mega summaries** to provide higher-level views beyond single clusters.
- **Operational delivery** through n8n workflows, webhooks, and a Streamlit dashboard.

## Monorepo Structure

- `n8n/` - Orchestration layer and main setup entrypoint.
- `opensearch/` - OpenSearch stack and index restore scripts.
- `cswspws25-WebCrawlerMain/` - Crawler service source.
- `cswspws25-m3-final/` - LLM service source.
- `frontend/` - Dashboard/frontend source.

For detailed branch/import mapping, see `README-repo-layout.md`.

## Architecture Overview

At a high level:

1. Crawler fetches articles.
2. n8n workflows orchestrate processing and trigger services.
3. LLM service generates clustering, summaries, labels, and related outputs.
4. OpenSearch stores articles, clusters, and summary artifacts.
5. Frontend/dashboard reads data and displays results.

Most pipeline logic is orchestrated by n8n workflows.

### Architecture Diagram

```text
+------------------------------------------------------------------+
|                       Docker Network                             |
|------------------------------------------------------------------|
|                                                                  |
|  [Crawler] ─────▶ [n8n] ─────▶ [llm-service] ─────▶ [Ollama]   |
|                     │                                            |
|                     │                                            |
|                     ├────────────▶ [Dashboard]                   |
|                     │                 │                          |
|                     │                 ▼                          |
|                     └────────────▶ [OpenSearch]                  |
|                                                                  |
+------------------------------------------------------------------+
```

## End-to-End Processing Flow

1. **Collect**: crawler service fetches fresh articles.
2. **Store raw articles**: n8n writes ingested data into OpenSearch (`articles` and related indices).
3. **Cluster and enrich**: n8n calls LLM-service endpoints for cluster creation/merging, summaries, labels, and keywords.
4. **Categorize**: clusters are mapped into semantic categories.
5. **Aggregate**: mega summaries are generated per category.
6. **Serve results**: outputs are exposed to the dashboard and webhook endpoints.

For workflow-level technical behavior, use `n8n/workflows/docs/` as the canonical reference.

## Project Structure Design

```text
SWP-News-Summary/
│
├── n8n/
│   ├── bundle/
│   │   ├── n8n-data.tar.gz
│   │   └── opensearch-data.tar.gz
│   ├── bundle_data_setup.sh
│   ├── complete_setup.sh
│   ├── docker/
│   │   ├── n8n/setup_n8n.sh
│   │   ├── llm-service/setup-llm-service.sh
│   │   ├── crawler/setup-crawler-service.sh
│   │   └── streamlit-frontend/setup-frontend-service.sh
│   ├── docs/
│   ├── workflows/
│   │   ├── n8n json/
│   │   └── docs/
│   └── README.md
│
├── opensearch/
│   ├── docker-compose.yml
│   └── scripts/restore_indices.sh
│
├── frontend/
├── cswspws25-WebCrawlerMain/
└── cswspws25-m3-final/
```

## Where To Start

Use the n8n documentation as the primary operational guide:

- Main setup and runtime guide: `n8n/README.md`
- Bundle-focused setup details: `n8n/README-bundle-data-setup.md`

Recommended first run path:

1. Read prerequisites and layout expectations in `n8n/README.md`.
2. Run setup from `n8n/` using `bundle_data_setup.sh`.
3. Verify services and ports as documented in `n8n/README.md`.

## Implementation References

If you want to understand or modify implementation details, start in `n8n/`:

- Workflow technical docs: `n8n/workflows/docs/`
- Exported n8n workflow JSONs: `n8n/workflows/n8n json/`
- Service setup scripts:
  - `n8n/docker/n8n/setup_n8n.sh`
  - `n8n/docker/llm-service/setup-llm-service.sh`
  - `n8n/docker/crawler/setup-crawler-service.sh`
  - `n8n/docker/streamlit-frontend/setup-frontend-service.sh`

Component-specific implementation also lives in:

- `cswspws25-WebCrawlerMain/` for crawler internals.
- `cswspws25-m3-final/` for LLM API/service internals.
- `frontend/` for dashboard behavior.
- `opensearch/` for OpenSearch stack configuration.

## Contributors

- **eniseirem** (N8N Lead, Integration)
- **Lennyad** (collaborator invited)

Add future contributors in GitHub repository settings:
`Settings -> Collaborators and teams`.

