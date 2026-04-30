### `bundle_data_setup.sh` – Bundle-Based Setup (No `images.tar`)

This script helps you recreate the full SWP News Summary stack (OpenSearch, n8n, LLM, crawler, dashboard) **using your bundle data**, without loading images from `images.tar`. Images are pulled/built as in `complete_setup.sh`; data comes from your bundle.

---

### What it does

- **Infra**
  - Ensures Docker networks:
    - `opensearch_internal_net`
    - `n8n-network`
  - Ensures Docker volume:
    - `opensearch-data`

- **n8n data**
  - Preferred source: `~/SWP-News-Summary/n8n/n8n-backup/`
    - Backs up current `~/.n8n` to `~/.n8n_backup_...`
    - Copies `n8n-backup` → `~/.n8n`
  - Fallback: `~/SWP-News-Summary/n8n/bundle/n8n-data.tar.gz`
    - Backs up `~/.n8n`
    - Extracts tar into `~/.n8n` (stripping leading `.n8n/`)

- **OpenSearch data**
  - Optional restore from `~/SWP-News-Summary/n8n/bundle/opensearch-data.tar.gz` into `opensearch-data` volume (after confirmation).
  - Always runs `~/SWP-News-Summary/opensearch/scripts/restore_indices.sh` after starting OpenSearch, so indices like `clusters` are created from JSON if needed.

- **Containers (like `complete_setup.sh`)**
  - OpenSearch stack via `opensearch/docker-compose.yml`.
  - `n8n` via `n8n/docker/n8n/setup_n8n.sh`.
  - LLM + Ollama via `n8n/docker/llm-service/setup-llm-service.sh`.
  - `crawler-api` via `n8n/docker/crawler/setup-crawler-service.sh`.
  - `dashboard` via `n8n/docker/streamlit-frontend/setup-frontend-service.sh`.

- **n8n owner account reset**
  - Runs:

    ```bash
    docker run --rm \
      -v ~/.n8n:/home/node/.n8n \
      n8nio/n8n:latest \
      user-management:reset
    ```

  - Opens your browser to `http://localhost:5678` so you can create a fresh owner account.

- **Activate all n8n workflows**
  - After n8n is up, runs:

    ```bash
    docker exec n8n n8n update:workflow --all --active=true
    ```

    so all imported workflows are activated automatically.

---

### Prerequisites

- Docker Desktop running.
- `~/SWP-News-Summary` checked out with:
  - `n8n/`
  - `opensearch/`
  - `cswspws25-m3-final/`
  - `cswspws25-WebCrawlerMain/`
  - `frontend/frontend/`
- Optional bundle data:
  - `~/SWP-News-Summary/n8n/n8n-backup/` and/or
  - `~/SWP-News-Summary/n8n/bundle/n8n-data.tar.gz`
  - `~/SWP-News-Summary/n8n/bundle/opensearch-data.tar.gz`

---

### Usage

From the `n8n` directory:

```bash
cd ~/SWP-News-Summary/n8n
chmod +x bundle_data_setup.sh   # first time only
```

- **Dry run (see what it would do, no changes):**

```bash
DRY_RUN=true ./bundle_data_setup.sh
```

- **Real run:**

```bash
./bundle_data_setup.sh
```

You’ll be prompted to:

1. Optionally restore OpenSearch data from `opensearch-data.tar.gz`.
2. Start all containers (OpenSearch, n8n, LLM, crawler, dashboard).
3. After startup:
   - All n8n workflows are activated.
   - n8n user management is reset and your browser opens at `http://localhost:5678` to create the owner account.

---

### After running

- **n8n UI:** `http://localhost:5678`
- **Dashboard:** `http://localhost:8501`
- **OpenSearch:** `https://localhost:9200` (user: `admin` / pass: `admin`)
- **OpenSearch Dashboards:** `http://localhost:5601`
- **LLM service:** `http://localhost:8001`
- **Crawler API:** `http://localhost:8003/docs`

### `bundle_data_setup.sh` – Bundle-Based Setup (No `images.tar`)

This script helps you recreate the full SWP News Summary stack (OpenSearch, n8n, LLM, crawler, dashboard) **using your bundle data**, without loading images from `images.tar`. Images are pulled/built as in `complete_setup.sh`; data comes from your bundle.

---

### What it does

- **Infra**
  - Ensures Docker networks:
    - `opensearch_internal_net`
    - `n8n-network`
  - Ensures Docker volume:
    - `opensearch-data`

- **n8n data**
  - Preferred source: `~/SWP-News-Summary/n8n/n8n-backup/`
    - Backs up current `~/.n8n` to `~/.n8n_backup_...`
    - Copies `n8n-backup` → `~/.n8n`
  - Fallback: `~/SWP-News-Summary/n8n/bundle/n8n-data.tar.gz`
    - Backs up `~/.n8n`
    - Extracts tar into `~/.n8n` (stripping leading `.n8n/`)

- **OpenSearch data**
  - Optional restore from `~/SWP-News-Summary/n8n/bundle/opensearch-data.tar.gz` into `opensearch-data` volume (after confirmation).
  - Always runs `~/SWP-News-Summary/opensearch/scripts/restore_indices.sh` after starting OpenSearch, so indices like `clusters` are created from JSON if needed.

- **Containers (like `complete_setup.sh`)**
  - OpenSearch stack via `opensearch/docker-compose.yml`.
  - `n8n` via `n8n/docker/n8n/setup_n8n.sh`.
  - LLM + Ollama via `n8n/docker/llm-service/setup-llm-service.sh`.
  - `crawler-api` via `n8n/docker/crawler/setup-crawler-service.sh`.
  - `dashboard` via `n8n/docker/streamlit-frontend/setup-frontend-service.sh`.

- **n8n owner account reset**
  - Runs:

    ```bash
    docker run --rm \
      -v ~/.n8n:/home/node/.n8n \
      n8nio/n8n:latest \
      user-management:reset
    ```

  - Opens your browser to `http://localhost:5678` so you can create a fresh owner account.

---

### Prerequisites

- Docker Desktop running.
- `~/SWP-News-Summary` checked out with:
  - `n8n/`
  - `opensearch/`
  - `cswspws25-m3-final/`
  - `cswspws25-WebCrawlerMain/`
  - `frontend/frontend/`
- Optional bundle data:
  - `~/SWP-News-Summary/n8n/n8n-backup/` and/or
  - `~/SWP-News-Summary/n8n/bundle/n8n-data.tar.gz`
  - `~/SWP-News-Summary/n8n/bundle/opensearch-data.tar.gz`

---

### Usage

From the `n8n` directory:

```bash
cd ~/SWP-News-Summary/n8n
chmod +x bundle_data_setup.sh   # first time only
```

- **Dry run (see what it would do, no changes):**

```bash
DRY_RUN=true ./bundle_data_setup.sh
```

- **Real run:**

```bash
./bundle_data_setup.sh
```

You’ll be prompted to:

1. Optionally restore OpenSearch data from `opensearch-data.tar.gz`.
2. Start all containers (OpenSearch, n8n, LLM, crawler, dashboard).
3. After startup, n8n user management is reset and your browser opens at `http://localhost:5678` to create the owner account.

---

### After running

- **n8n UI:** `http://localhost:5678`
- **Dashboard:** `http://localhost:8501`
- **OpenSearch:** `https://localhost:9200` (user: `admin` / pass: `admin`)
- **OpenSearch Dashboards:** `http://localhost:5601`
- **LLM service:** `http://localhost:8001`
- **Crawler API:** `http://localhost:8003/docs`

