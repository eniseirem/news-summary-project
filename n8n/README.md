# SWP News Summary – n8n & Bundle Setup

Automated news aggregation, clustering, summarization, categorization, and visualization system using **n8n**, **OpenSearch**, a **crawler API**, **LLM service**, and a **Streamlit dashboard**.

This README reflects the **final setup** and the **bundle-based data restore** flow. A **PDF version** can be generated with `./make_readme_pdf.sh` (requires [pandoc](https://pandoc.org/) or Node.js for `npx md-to-pdf`).

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Installation & Base Layout](#installation--base-layout)
- [Bundle-Based Setup (`bundle_data_setup.sh`)](#bundle-based-setup)
  - [First run and folder layout](#first-run-and-folder-layout)
  - [If bundle data is missing or data loading fails](#if-bundle-data-is-missing-or-data-loading-fails)
- [Services & Ports](#services--ports)
- [Workflows & Documentation](#workflows--documentation)
  - [When workflows run](#when-workflows-run)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Additional Information](#additional-information)
  - [Backups & recovery (Google Drive)](#backups--recovery-google-drive)

---

## Overview

The current system (Milestone 3) provides an end‑to‑end pipeline that:

1. **Crawls** news articles from many sources via a Python **crawler API**.
2. **Indexes** them into OpenSearch (`articles` index).
3. **Clusters** articles incrementally using an LLM + **KNN-based** merge/create logic.
4. **Generates** per‑cluster summaries, topic labels, and keywords.
5. **Categorizes** clusters into semantic categories (e.g. Politics, Tech).
6. **Builds** **mega summaries** per category.
7. **Serves** summaries via:
   - Webhook endpoints (cluster summaries, styling),
   - A Streamlit dashboard on top of OpenSearch.

Most of this logic lives in **n8n M3 workflows** (see [Workflows & Documentation](#workflows--documentation)).

---

## Architecture

```
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
- **OpenSearch**: main data store (`articles`, `clusters`, `cluster_summaries`,
  `article_summaries`, `mega_summaries`, `llm_batch`, …).
- **n8n**: orchestrates the **M3 workflows** (crawler, clustering, categorization, mega summaries, webhooks).  
  All data from crawler and LLM is **written to OpenSearch by n8n** – those services never talk to OpenSearch directly.
- **crawler‑api**: Python service providing per‑source endpoints (CNN, Guardian, FAZ, NTV, …), called **only by n8n**.
- **llm‑service**: FastAPI server exposing endpoints like `/cluster_create`, `/cluster_summarize`, `/topic_label`, `/keyword_extract`, `/mega_summarize`, `/summary_style`, `/translate_cluster_summary`.  
  It is called **only by n8n**, and it is the only component that talks to Ollama.
- **Ollama**: separate container hosting models (e.g. `llama3.2:3b`); **llm‑service⇄Ollama** communication only.
- **dashboard**: Streamlit frontend that **only talks to n8n and OpenSearch** (for data and actions), never directly to crawler or LLM/Ollama.

---

## Prerequisites

### Required Software

- **Docker Desktop** (or Docker Engine + Docker Compose)
  - Version 20.10 or higher
- **Git**
  - For cloning this repository

### Recommended System

- **RAM**: 16GB recommended (12GB minimum)
- **Disk**: 10GB+ free (OpenSearch, images, models)
- **OS**: macOS, Linux, or Windows with WSL2
- Terminal with `bash` support

The current LLM stack runs via **Ollama**, with the active model configured by `OLLAMA_MODEL` in `docker/llm-service/config.sh` and pulled by `setup-llm-service.sh` (see `n8n/docs/ollama-optimization-trials.md` for tuning details and recommended model settings).

---

## Installation & Base Layout

The GitHub repository is the project source. Cloning it gives you the n8n code and scripts at the **root** of the clone, not inside a folder named `n8n`. The stack and **`bundle_data_setup.sh`** expect the n8n-pipeline to live at **`~/SWP-News-Summary/n8n`**.

**Option A – Clone the n8n-pipeline branch, then let the setup script fix the layout (recommended)**

```bash
cd "${HOME}"
git clone --branch main https://github.com/eniseirem/news-summary-project.git cswspws25
# Old GitLab URL: https://gitlab.fokus.fraunhofer.de/dana/cswspws25.git
cd cswspws25
./bundle_data_setup.sh
```

When the script finds the n8n-pipeline clone as a **sibling** of `SWP-News-Summary`, it will ask: **"Move under SWP-News-Summary and rename as n8n?"** Answer **y**; the script will move the folder and exit. Then re-run from the new location:

```bash
cd ~/SWP-News-Summary/n8n
./bundle_data_setup.sh
```

**Option B – Clone the n8n-pipeline branch directly into the expected path**

```bash
mkdir -p "${HOME}/SWP-News-Summary"
cd "${HOME}/SWP-News-Summary"
git clone --branch main https://github.com/eniseirem/news-summary-project.git n8n
# Old GitLab URL: https://gitlab.fokus.fraunhofer.de/dana/cswspws25.git
cd n8n
./bundle_data_setup.sh
```

**Expected layout (after layout is correct)**

- Project root: `~/SWP-News-Summary`
- n8n code and scripts: `~/SWP-News-Summary/n8n` (this repo = n8n-pipeline)
- OpenSearch stack: `~/SWP-News-Summary/opensearch`
- Frontend dashboard: `~/SWP-News-Summary/frontend`
- LLM stack: `~/SWP-News-Summary/cswspws25-m3-final`
- Crawler: `~/SWP-News-Summary/cswspws25-WebCrawlerMain`

`bundle_data_setup.sh` clones missing service repos (opensearch, crawler, LLM, dashboard) when you confirm; the n8n-pipeline itself is this repository and must be at **`~/SWP-News-Summary/n8n`**.

The easiest way to bring up a full stack from prepared backups is **`n8n/bundle_data_setup.sh`** (see next section). Legacy scripts like `setup_n8n_ultimate.sh` and the old Milestone 1/2 workflows are kept for reference but are **not the primary entry point** for the current pipeline.

---

## Bundle-Based Setup

**Script:** `n8n/bundle_data_setup.sh`  
**Purpose:** Set up networks/volumes, restore n8n/OpenSearch data from backups, and start all containers  
**Safety:** backs up **existing** n8n data and asks before overwriting OpenSearch volume.

**If data loading or restore fails** (missing bundle files, restore errors, or services not seeing data): run **`./bundle_fetch_backups.sh`** from `n8n/` to fetch backups from Google Drive, or [manually download](#if-bundle-data-is-missing-or-data-loading-fails) both archives and place them in **`n8n/bundle/`**, then re-run **`bundle_data_setup.sh`**. On **first run**, ensure you run from the correct folder and [fix folder layout](#first-run-and-folder-layout) if the script offers to move the clone (e.g. under `SWP-News-Summary` as `n8n`).

### What It Does

In order:

1. **Checks Docker**
   - Fails fast if the Docker daemon is not running.

2. **Ensures infrastructure**
   - Creates Docker networks:
     - `opensearch_internal_net`
     - `n8n-network`
   - Ensures OpenSearch volume:
     - `opensearch-data`

3. **Restores n8n data**
   - If `n8n/n8n-backup/` exists:
     - Backs up current `~/.n8n` as `~/.n8n_backup_YYYYMMDD-HHMMSS`
     - Copies `n8n-backup/` into `~/.n8n`
   - Else if `n8n/bundle/n8n-data.tar.gz` exists:
     - Backs up current `~/.n8n` as above
     - Extracts the tarball into `~/.n8n` with `--strip-components=1`
   - Else:
     - Skips n8n restore and leaves current data in place.

4. **Optionally restores OpenSearch volume**
   - If `n8n/bundle/opensearch-data.tar.gz` exists:
     - Prompts: **“Restore OpenSearch data from bundle into opensearch-data volume?”**
     - On **yes**: wipes the volume and untars into `/data` (busybox container).
     - On **no**: keeps existing OpenSearch data.

5. **Optionally starts all services**
   - Prompts: **“Start containers (OpenSearch, n8n, LLM, crawler, dashboard) now?”**
   - On **yes**, it:
     - Starts the **OpenSearch** stack via `opensearch/docker-compose.yml`.
     - Runs `opensearch/scripts/restore_indices.sh` to ensure indices (e.g. `clusters`, `articles`, etc.) exist.
     - Runs `n8n/docker/n8n/setup_n8n.sh`.
     - Runs `n8n/docker/llm-service/setup-llm-service.sh`.
     - Runs `n8n/docker/crawler/setup-crawler-service.sh`.
     - Runs `n8n/docker/streamlit-frontend/setup-frontend-service.sh`.

### First run and folder layout

- **First run:** Run the script from **`~/SWP-News-Summary/n8n`** so bundle paths resolve (e.g. `n8n/bundle/n8n-data.tar.gz`). If you don’t have `n8n` there yet, see below.
- If you cloned the n8n pipeline repo as a **sibling** of `SWP-News-Summary` (e.g. as `cswspws25`), the script will detect it and ask: **"Move under SWP-News-Summary and rename as n8n?"**  
  - Answer **y** to move the folder; the script then **exits**.  
  - **Re-run** from the new location so the rest of the setup (bundle fetch/restore, containers) runs from the correct place:
  ```bash
  cd ~/SWP-News-Summary/n8n
  ./bundle_data_setup.sh
  ```
- After moving (or if you already have `SWP-News-Summary/n8n`), put bundle files in **`n8n/bundle/`** (see [If bundle data is missing or data loading fails](#if-bundle-data-is-missing-or-data-loading-fails)). Then run `bundle_data_setup.sh` again to restore and start containers.

### If bundle data is missing or data loading fails

The script needs **`n8n-data.tar.gz`** and **`opensearch-data.tar.gz`** in **`n8n/bundle/`**. If they are missing, a restore step fails, or data doesn’t load correctly after running `bundle_data_setup.sh`:

1. **Fetch from Google Drive (recommended)**  
   From the **`n8n`** directory, run:
   ```bash
   cd ~/SWP-News-Summary/n8n
   ./bundle_fetch_backups.sh
   ```
   This downloads both archives into **`n8n/bundle/`**. If you already ran `bundle_data_setup.sh` and it offered **"Fetch n8n + OpenSearch backups from Google Drive now?"**, you can answer **y** there instead of running `bundle_fetch_backups.sh` manually.

2. **Manual download**  
   If the fetch fails (e.g. Google Drive returns HTML or a large-file confirmation page), use the same archives that **`bundle_fetch_backups.sh`** and **`bundle_data_setup.sh`** use (these are **not** the macOS recovery backups—see [Backups & recovery (Google Drive)](#backups--recovery-google-drive) for that):
   - **n8n data** → save as **`n8n-data.tar.gz`**:  
     [https://drive.usercontent.google.com/download?id=15jpeU-q4TmAT6QJkGxd75uNrp9vktkim&export=download&authuser=0](https://drive.usercontent.google.com/download?id=15jpeU-q4TmAT6QJkGxd75uNrp9vktkim&export=download&authuser=0)
   - **OpenSearch data** → save as **`opensearch-data.tar.gz`**:  
     [https://drive.google.com/uc?export=download&id=1VVVi7rvpqzDWAkHmybXmMJM2lRjhlaJd](https://drive.google.com/uc?export=download&id=1VVVi7rvpqzDWAkHmybXmMJM2lRjhlaJd)
   - **Move** (or copy) both files into the bundle folder so the script can find them:
     ```text
     ~/SWP-News-Summary/n8n/bundle/n8n-data.tar.gz
     ~/SWP-News-Summary/n8n/bundle/opensearch-data.tar.gz
     ```
   - Ensure you run from **`~/SWP-News-Summary/n8n`**; on first run, if the script asked to move the clone under `SWP-News-Summary` as `n8n`, do that first and re-run from the new location (see [First run and folder layout](#first-run-and-folder-layout)).

3. **Re-run setup**  
   After the files are in **`n8n/bundle/`**, run **`bundle_data_setup.sh`** again. It will prompt to restore n8n data and OpenSearch data, then to start containers. Once containers are up, the **Streamlit dashboard** (`http://localhost:8501`) may need a **browser refresh** (F5 or reload) or a **dashboard container restart** (`docker restart dashboard`) to show the newly loaded data.

**Alternative backup folder (macOS-created):** A separate Google Drive folder contains **macOS-created images and additional data files** (different filenames and full-system/ollama options). See [Backups & recovery (Google Drive)](#backups--recovery-google-drive) below.

### DRY-RUN Mode

You can preview everything **without making changes**:

```bash
cd ~/SWP-News-Summary/n8n
DRY_RUN=true ./bundle_data_setup.sh
```

Real run:

```bash
./bundle_data_setup.sh
```

### After a Successful Run

- OpenSearch containers running and reachable on `opensearch_internal_net`.
- n8n container running with M3 workflows already present in `~/.n8n`.
- llm‑service container running with its API exposed.
- crawler‑api and Streamlit dashboard containers running and on the right networks.

If you just restored data from the bundle (e.g. after `bundle_fetch_backups.sh` and re-running setup), the **dashboard** at `http://localhost:8501` may still show old or empty data until you **refresh the page** (F5 or reload) or **restart the dashboard container** (`docker restart dashboard`) so it picks up the reloaded OpenSearch data.

---

## Services & Ports

After `bundle_data_setup.sh` (or the individual setup scripts), you typically have:

- **n8n**: `http://localhost:5678` (require user account)
- **llm‑service**: `http://localhost:8001`
- **OpenSearch HTTP**: `https://localhost:9200` (may require auth)
- **Dashboard (Streamlit)**: `http://localhost:8501`

> Inside Docker networks, containers talk to each other via hostnames like
> `opensearch:9200`, `llm-service:8001`, `crawler-api:8000`, `n8n:5678`.

---

## Workflows & Documentation

Detailed n8n workflow docs live under:

- `n8n/workflows/docs/`

Start with:

- `M3_Workflows_Overview.md` – high-level overview of all M3 workflows.

Then dive into the specific pieces:

- `M3_News_Crawler.md` – news ingestion into `articles`.
- `M3_Incremental_Clustering_KNN.md` – incremental clustering with KNN. (legacy)
- `M3_Clustering_Summary_Label.md` – clustering + summary + label pipeline. (extended version -Incremental)
- `M3_Cluster_Summary_And_Label.md` – sub-workflow for cluster summaries + labels + keywords.
- `M3_Category_Mapping_For_Clusters.md` – per-cluster category assignment.
- `M3_Categorize_Clusters_Workflow_Technical_Overview.md` – full categorization + mega summaries.
- `M3_Mega_Summary_Workflow.md` / `M3_Mega_Summary_Sub_Workflow.md` – category-level mega summaries.
- `M3_Webhook_Cluster_Summary.md` – public cluster summary webhook.
- `M3_Summary_Style_Workflow.md` – styling endpoint for summaries.
- `M3_Translation_Workflow.md` – translation of summaries and labels.

Because the `.n8n` directory is restored from backup, all these workflows should already
exist in the n8n UI – **no manual import necessary** in the typical bundle-based setup. If not workflows can be found under n8n/workflows/n8n json

### When workflows run

The **News Crawler** workflow is scheduled to run automatically **every 6 hours** at **00:00, 06:00, 12:00, and 18:00** (server time). Downstream pipelines (clustering, summary, label, etc.) are typically triggered by that crawl.

You can also **start a run manually** at any time: open the n8n UI (`http://localhost:5678`), open the **News Crawler** workflow, and click **Execute Workflow** (or the play button) to run the crawler once on demand.

---

## Project Structure

Simplified layout for the current M3 setup:

```text
SWP-News-Summary/
│
├── n8n/
│   ├── bundle/
│   │   ├── n8n-data.tar.gz # could be also downloaded directly from drive
│   │   └── opensearch-data.tar.gz
│   ├── bundle_data_setup.sh
│   ├── complete_setup.sh                 # Legacy setup
│   ├── docker/
│   │   ├── n8n/setup_n8n.sh
│   │   ├── llm-service/setup-llm-service.sh
│   │   ├── crawler/setup-crawler-service.sh
│   │   └── streamlit-frontend/setup-frontend-service.sh
│   ├── docs/
│   │   ├── ollama-optimization-trials.md         # Test Results
│   ├── workflows/
│   │   ├── n8n json/                     # Exported workflows
│   │   └── docs/                         # M3_* docs
│   └── README.md                         # This file
│
├── opensearch/
│   ├── docker-compose.yml
│   └── scripts/restore_indices.sh
│
├── frontend/                             # Streamlit dashboard
│   └── ...
├── cswspws25-WebCrawlerMain/         # Web crawler (separate branch)
│   ├── main.py                       # Main crawler script
│   ├── NBC
│   └── ...
│
└── cswspws25-m3-final/           # LLM service (separate branch)
    ├── src/
    │   └── api/
    │       └── main.py               # FastAPI server
    └── ...
```

---

## Troubleshooting

### Common Issues

#### 1. "Cannot connect to Docker daemon"

**Problem:** Docker is not running

**Solution:**
```bash
# Start Docker Desktop
# Or on Linux:
sudo systemctl start docker
```

#### 2. "Port 5678 already in use"

**Problem:** Another service is using n8n's port

**Solution:**
```bash
# Stop conflicting service or change port in config.sh
# Then re-run setup
```

#### 3. "LLM API returns 502 Bad Gateway"

**Problem:** LLM service is still downloading models

**Solution:**
```bash
# Check if download is complete
docker logs -f llm-service

# Wait for "Application startup complete"
```

#### 4. "Crawler workflow fails"

**Problem:** Python dependencies not installed

**Solution:**
```bash
# Reinstall crawler dependencies
docker exec n8n /home/node/crawler-venv/bin/pip install \
  requests beautifulsoup4 feedparser newspaper4k lxml lxml-html-clean
```

#### 5. "No articles found"

**Problem:** News sources may be blocking requests

**Solution:**
- Check crawler logs in n8n execution
- Verify internet connection
- Some sources may require headers/user agents (check crawler config)

#### 6. "Dashboard shows empty"

**Problem:** No summary files generated yet, or dashboard still shows old/empty data after restoring from the bundle.

**Solution:**
- If you **just reloaded data** via `bundle_fetch_backups.sh` and re-ran setup: **refresh the dashboard page** (F5 or reload) at `http://localhost:8501`, or **restart the dashboard container** (`docker restart dashboard`), so it picks up the new OpenSearch data.
- Otherwise: run the pipeline manually first and verify LLM service is running.

#### 7. Linux (server): n8n permission errors after restoring from bundle

**Problem:** After restoring n8n data from a bundle into `~/.n8n`, the n8n container cannot read or write files (permission denied). This often happens on **servers where you cannot use sudo**; local setups usually do not hit this.

**Solution:** After any n8n data restore, fix ownership/permissions so the container can access the data:

```bash
chmod 644 ~/.n8n/config 2>/dev/null || true
chmod -R a+rwX ~/.n8n 2>/dev/null || true
```

If n8n is already running, restart it so it picks up the restored data:

```bash
docker restart n8n
```

The bundle setup script (`bundle_data_setup.sh`) applies these `chmod` steps automatically when you choose to restore n8n data.

#### 8. macOS: n8n login or user reset required

**Problem:** n8n UI asks for a user that doesn’t exist, or you need to reset the owner account (e.g. after restoring data from another machine).

**Solution:** Reset the n8n user inside the container:

```bash
docker exec -it n8n n8n user-management:reset
```

Follow the prompts to set a new owner email and password, then log in at `http://localhost:5678`.

#### 9. Bundle data missing or data loading / restore fails

**Problem:** `bundle_data_setup.sh` can't find `n8n-data.tar.gz` or `opensearch-data.tar.gz`, or restore fails (e.g. corrupt file or wrong path).

**Solution:** See [If bundle data is missing or data loading fails](#if-bundle-data-is-missing-or-data-loading-fails): run `./bundle_fetch_backups.sh` from `n8n/` to fetch from Google Drive, or manually download both files and place them in `n8n/bundle/`, then re-run `bundle_data_setup.sh`. For first-run folder layout (e.g. moving the clone under SWP-News-Summary as `n8n`), see [First run and folder layout](#first-run-and-folder-layout).

#### 10. Ollama shuts down or times out on first run (e.g. 8 GB RAM)

**Problem:** With limited RAM (e.g. **8 GB**), Ollama can shut down during the first run. You may see **timeout errors** in `docker logs ollama` and failures in workflows that use the LLM (e.g. **Clustering Summary Label** or similar clustering/summary/label workflows).

**Solution:**
- **Increase RAM** if possible: the stack is more stable with **16 GB** (see [Prerequisites](#-prerequisites)).
- Check Ollama is running and responsive: `docker logs ollama` (look for timeouts or OOM).
- Restart Ollama and retry the workflow: `docker restart ollama` (and `llm-service` if needed).
- Consider a smaller model or fewer concurrent requests; see `n8n/docs/ollama-optimization-trials.md` for tuning.

### Viewing Logs

```bash
# n8n logs
docker logs -f n8n

# LLM service logs
docker logs -f llm-service

# Ollama (if timeouts or clustering/summary workflow errors)
docker logs -f ollama

# Both n8n and LLM
docker logs -f n8n & docker logs -f llm-service
```

### Restart Services

```bash
# Restart n8n
docker restart n8n

# Restart LLM
docker restart llm-service

# Restart both
docker restart n8n llm-service
```

### Complete Reset

```bash
# Stop and remove containers
docker stop n8n llm-service
docker rm n8n llm-service

# Remove pipeline output data (WARNING: Deletes generated output)
rm -rf cswspws25-llm-pipeline/data/errors/*

# Re-run setup
./setup_n8n_ultimate.sh
```

---

## Additional Information

### News Sources

The crawler collects articles from:
- 📰 BBC
- 📰 New York Times  
- 📰 Fox News
- 📰 The Guardian
- 📰 NBC News
- 📰 Yahoo Finance
                   ... 
(full list can be found in the cswspws25-WebCrawlerMain branch readme)

### LLM Model

- **Runtime**: Ollama (running in a dedicated container)
- **Model selection**: Controlled via `OLLAMA_MODEL` in `docker/llm-service/config.sh` (default is currently `llama3.2:3b`, see `n8n/docs/ollama-optimization-trials.md` for tuning history)
- **Purpose**: Extractive + abstractive summarization, translation, labeling, and keyword extraction
- **Performance**: CPU‑only in Docker on macOS (no GPU/Neural Engine access), so throughput depends heavily on your CPU cores and the chosen model size

### Ports

- **5678**: n8n web interface
- **8501**: frontend interface
- **8001**: LLM API service
- **8002**: opensearch dashboard


### Docker Volumes

- `~/.n8n`: n8n data persistence
- `CRAWLER_PATH:/crawler`: Crawler code
- `LLM_PATH:/llm`: LLM service code
- `DASH_PATH:/dashboard`: Dashboard files

### Backups & recovery (Google Drive)

An alternative set of **macOS-created images and additional data files** is available in this Google Drive folder:

**[SWP - Images](https://drive.google.com/drive/folders/1_YE_e5iXd0Bv6euLocuVg_n8p8PfBney)**

Contents (names and sizes may vary):

| File | Description |
|------|-------------|
| `DOCKER_FULL_SYSTEM_RECOVERY_README.md` | Full recovery instructions |
| `full-system-snapshot.tar` | Full system snapshot (~6 GB) |
| `n8n-home.tar.gz` | n8n home data (~184 MB); equivalent to `n8n-data.tar.gz` for restore into `~/.n8n` |
| `ollama-home.tar.gz` | Ollama models/data (~6 GB) |
| `opensearch_opensearch-data.tar.gz` | OpenSearch volume backup (~8 MB); equivalent to `opensearch-data.tar.gz` |
| `swp-project-binds.tar.gz` | Project bind mounts (~427 MB) |

For use with `bundle_data_setup.sh`, rename/copy as needed so that `n8n/bundle/` contains `n8n-data.tar.gz` and `opensearch-data.tar.gz` (e.g. copy `n8n-home.tar.gz` → `n8n/bundle/n8n-data.tar.gz` and `opensearch_opensearch-data.tar.gz` → `n8n/bundle/opensearch-data.tar.gz`). For full-system recovery, follow `DOCKER_FULL_SYSTEM_RECOVERY_README.md` in the folder.

---

## 🔗 Useful Commands

### Container Management

```bash
# Start services
docker start n8n
docker start llm-service

# Stop services
docker stop n8n
docker stop llm-service

# View running containers
docker ps

# View all containers
docker ps -a
```

### Accessing Containers

```bash
# Access n8n shell
docker exec -it n8n /bin/sh

# Access LLM shell
docker exec -it llm-service /bin/bash

# Run crawler manually
docker exec n8n /home/node/crawler-venv/bin/python /crawler/main.py
```

### Testing APIs

```bash
# Test LLM health
curl http://localhost:8001/docs

# Test n8n
curl http://localhost:5678

# Test dashboard
curl http://localhost:5678/webhook/json-view
```

---

## 📧 Support

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Review Docker logs
3. Verify configuration in `config.sh`
4. Ensure all prerequisites are met

---

## 📄 License


---

## 👥 Contributors


---

**Last Updated**: February 2025

**Version**: 1.0.0