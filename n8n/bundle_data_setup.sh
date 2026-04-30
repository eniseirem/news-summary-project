#!/usr/bin/env bash

# SWP News Summary - Complete Setup (single entry point)
#
# This is the only script you need for a full setup. Do not run complete_setup
# or bundle_setup separately; this script handles everything.
#
# What it does:
# - Moves n8n-pipeline clone (cswspws25) under SWP-News-Summary as n8n if needed
# - Clones missing service repos (opensearch, crawler, llM, dashboard)
# - Fetches n8n + OpenSearch bundle archives from Google Drive (or prompts manual)
# - Restores n8n data into ~/.n8n and OpenSearch data into opensearch-data volume
# - Ensures OpenSearch indices (e.g. clusters) exist via restore_indices fallback
# - Creates Docker networks/volumes and starts all containers (OpenSearch, n8n, LLM, crawler, dashboard)
# - Does not use images.tar; images are pulled when containers start
#
# Safety:
# - Backs up existing ~/.n8n before overwriting
# - Overwrites opensearch-data volume only after confirmation

set -euo pipefail

DRY_RUN="${DRY_RUN:-false}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

BASE_DIR="${HOME}/SWP-News-Summary"
# Resolve script location: may be SWP-News-Summary/n8n or a sibling cswspws25 (n8n-pipeline clone)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" && pwd)"
N8N_DIR="${BASE_DIR}/n8n"
BUNDLE_DIR="${BUNDLE_DIR:-${N8N_DIR}/bundle}"
# Name of the repo when cloned (sibling folder that we may move under SWP-News-Summary as n8n)
CLONE_DIR_NAME="cswspws25"

# Networks / volume (same as complete_setup)
OPENSEARCH_NETWORK="opensearch_internal_net"
N8N_NETWORK="n8n-network"
OPENSEARCH_VOLUME="opensearch-data"

# Optional repository cloning (mirrors branches from complete_setup.sh)
# NOTE: n8n is NOT cloned here – it is the tree that contains this script (N8N_DIR = BASE_DIR/n8n).
REPO_URL="https://github.com/eniseirem/news-summary-project.git"
# Old GitLab URL: https://gitlab.fokus.fraunhofer.de/dana/cswspws25.git
BRANCH_OPENSEARCH="Opensearch"
BRANCH_CRAWLER="WebCrawlerMain"
BRANCH_LLM="m3-final"
BRANCH_DASHBOARD="frontend/dashboard-ui"

DIR_OPENSEARCH="${BASE_DIR}/opensearch"
DIR_CRAWLER="${BASE_DIR}/cswspws25-WebCrawlerMain"
DIR_LLM="${BASE_DIR}/cswspws25-m3-final"
DIR_DASHBOARD="${BASE_DIR}/frontend"

run() {
  if [ "${DRY_RUN}" = "true" ]; then
    echo -e "${YELLOW}[DRY RUN]${NC} $*"
  else
    eval "$@"
  fi
}

log_step()  { echo -e "${YELLOW}▶${NC} $*"; }
log_ok()    { echo -e "${GREEN}✓${NC} $*"; }
log_err()   { echo -e "${RED}✗${NC} $*"; }
log_info()  { echo -e "${CYAN}ℹ${NC} $*"; }

# If this script is running from a folder that looks like the n8n-pipeline clone (has bundle_data_setup.sh
# or docker/n8n) and sits as a sibling of SWP-News-Summary, offer to move it under SWP-News-Summary and
# rename as n8n. Auto-detects the folder name (no need for it to be "cswspws25").
maybe_move_clone_under_swp() {
  local dir_script="${SCRIPT_DIR}"
  local parent="${SCRIPT_DIR%/*}"
  local basename_script="${SCRIPT_DIR##*/}"

  # Already under SWP-News-Summary/n8n
  if [[ "${dir_script}" == "${BASE_DIR}/n8n" ]]; then
    return 0
  fi

  # Must look like the n8n-pipeline repo (any folder name)
  if [ ! -f "${dir_script}/bundle_data_setup.sh" ] && [ ! -d "${dir_script}/docker/n8n" ]; then
    return 0
  fi

  local swp_dir="${parent}/SWP-News-Summary"
  local target_n8n="${swp_dir}/n8n"

  # Skip only if n8n already exists under SWP-News-Summary (we can create SWP-News-Summary if missing)
  if [ -d "${target_n8n}" ]; then
    log_info "SWP-News-Summary/n8n already exists; not moving ${basename_script}."
    return 0
  fi

  echo ""
  log_info "Found n8n-pipeline clone '${basename_script}' at same level as SWP-News-Summary."
  echo "  Current location: ${dir_script}"
  echo "  Target location:  ${target_n8n}"
  echo ""
  echo "Move '${basename_script}' under SWP-News-Summary and rename as n8n? [y/N]"
  read -r REPLY
  if [[ ! "${REPLY}" =~ ^[Yy]$ ]]; then
    log_info "Skipping move. Run this script from SWP-News-Summary/n8n for normal setup."
    return 0
  fi

  if [ "${DRY_RUN}" = "true" ]; then
    echo -e "${YELLOW}[DRY RUN]${NC} mkdir -p '${swp_dir}' && mv '${dir_script}' '${target_n8n}'"
    echo -e "${YELLOW}[DRY RUN]${NC} Then re-run: cd ${target_n8n} && ./bundle_data_setup.sh"
    return 0
  fi

  log_step "Creating ${swp_dir}..."
  mkdir -p "${swp_dir}"
  log_step "Moving ${dir_script} -> ${target_n8n}..."
  mv "${dir_script}" "${target_n8n}"
  log_ok "Done. Re-run the setup from the new location:"
  echo ""
  echo "  cd ${target_n8n}"
  echo "  ./bundle_data_setup.sh"
  echo ""
  exit 0
}

clone_service_repo_if_missing() {
  local service="$1"
  local branch="$2"
  local target_dir="$3"

  if [ -d "${target_dir}" ]; then
    log_info "Directory for ${service} already exists: ${target_dir} (skipping clone)."
    return 0
  fi

  log_step "Cloning ${service} (branch: ${branch}) into ${target_dir}..."
  if [ "${DRY_RUN}" = "true" ]; then
    echo -e "${YELLOW}[DRY RUN]${NC} git clone --single-branch --branch '${branch}' '${REPO_URL}' '${target_dir}'"
    return 0
  fi

  if git clone --single-branch --branch "${branch}" "${REPO_URL}" "${target_dir}"; then
    log_ok "${service} cloned successfully."
    return 0
  else
    log_err "Failed to clone ${service}."
    return 1
  fi
}

maybe_clone_service_repos() {
  local missing=()

  [ ! -d "${DIR_OPENSEARCH}" ] && missing+=("opensearch")
  [ ! -d "${DIR_CRAWLER}" ]   && missing+=("crawler")
  [ ! -d "${DIR_LLM}" ]       && missing+=("llm")
  [ ! -d "${DIR_DASHBOARD}" ] && missing+=("dashboard")

  if [ ${#missing[@]} -eq 0 ]; then
    log_info "All service directories already exist (opensearch/crawler/llm/dashboard). No cloning needed."
    return 0
  fi

  echo ""
  log_info "The following directories are missing and can be cloned from ${REPO_URL}:"
  for svc in "${missing[@]}"; do
    case "${svc}" in
      "opensearch") echo "  - opensearch -> ${DIR_OPENSEARCH} (branch: ${BRANCH_OPENSEARCH})" ;;
      "crawler")   echo "  - crawler    -> ${DIR_CRAWLER}   (branch: ${BRANCH_CRAWLER})" ;;
      "llm")       echo "  - llm        -> ${DIR_LLM}       (branch: ${BRANCH_LLM})" ;;
      "dashboard") echo "  - dashboard  -> ${DIR_DASHBOARD} (branch: ${BRANCH_DASHBOARD})" ;;
    esac
  done
  echo ""
  echo "Clone missing repositories now? [y/N]"
  read -r REPLY
  if [[ ! "${REPLY}" =~ ^[Yy]$ ]]; then
    log_info "Skipping cloning of service repositories."
    return 0
  fi

  for svc in "${missing[@]}"; do
    case "${svc}" in
      "opensearch")
        clone_service_repo_if_missing "opensearch" "${BRANCH_OPENSEARCH}" "${DIR_OPENSEARCH}" || return 1
        ;;
      "crawler")
        clone_service_repo_if_missing "crawler" "${BRANCH_CRAWLER}" "${DIR_CRAWLER}" || return 1
        ;;
      "llm")
        clone_service_repo_if_missing "llm" "${BRANCH_LLM}" "${DIR_LLM}" || return 1
        ;;
      "dashboard")
        clone_service_repo_if_missing "dashboard" "${BRANCH_DASHBOARD}" "${DIR_DASHBOARD}" || return 1
        ;;
    esac
  done
}

check_docker() {
  log_step "Checking Docker daemon..."
  if ! run "docker info >/dev/null 2>&1"; then
    log_err "Docker is not running. Start Docker Desktop and re-run this script."
    exit 1
  fi
  log_ok "Docker is running."
}

ensure_network() {
  local name="$1"
  log_step "Ensuring Docker network '${name}' exists..."
  if docker network ls --format '{{.Name}}' | grep -qx "${name}"; then
    log_ok "Network '${name}' already exists."
  else
    run "docker network create '${name}' >/dev/null"
    log_ok "Network '${name}' created."
  fi
}

ensure_volume() {
  local name="$1"
  log_step "Ensuring Docker volume '${name}' exists..."
  if docker volume ls --format '{{.Name}}' | grep -qx "${name}"; then
    log_ok "Volume '${name}' already exists."
  else
    run "docker volume create '${name}' >/dev/null"
    log_ok "Volume '${name}' created."
  fi
}

restore_n8n_data() {
  local backup_dir="${N8N_DIR}/n8n-backup"
  local tar_src="${BUNDLE_DIR}/n8n-data.tar.gz"
  local target="${HOME}/.n8n"

  if [ -d "${backup_dir}" ]; then
    log_step "Restoring n8n data from directory backup: ${backup_dir} -> ${target}"
    if [ -d "${target}" ]; then
      local backup="${HOME}/.n8n_backup_$(date +%Y%m%d-%H%M%S)"
      log_step "Backing up existing ~/.n8n to ${backup}..."
      run "mv '${target}' '${backup}'"
    fi
    run "mkdir -p '${target}'"
    run "cp -a '${backup_dir}/.' '${target}/'"
    log_ok "n8n data restored from n8n-backup directory (or simulated in DRY-RUN)."
    return 0
  fi

  if [ -f "${tar_src}" ]; then
    log_step "Restoring n8n data from tarball: ${tar_src} -> ${target}"
    if [ -d "${target}" ]; then
      local backup="${HOME}/.n8n_backup_$(date +%Y%m%d-%H%M%S)"
      log_step "Backing up existing ~/.n8n to ${backup}..."
      run "mv '${target}' '${backup}'"
    fi
    run "mkdir -p '${target}'"
    # Tar has leading .n8n/, strip it so files land directly in ~/.n8n
    run "tar xzf '${tar_src}' -C '${target}' --strip-components=1"
    log_ok "n8n data restored from n8n-data.tar.gz (or simulated in DRY-RUN)."
    return 0
  fi

  log_info "No n8n-backup directory or n8n-data.tar.gz found – skipping n8n data restore."
}

restore_opensearch_data() {
  local tar_src="${BUNDLE_DIR}/opensearch-data.tar.gz"

  if [ ! -f "${tar_src}" ]; then
    log_info "No opensearch-data.tar.gz found in ${BUNDLE_DIR} – skipping OpenSearch data restore."
    return 0
  fi

  log_step "Restoring OpenSearch data from ${tar_src} into ${OPENSEARCH_VOLUME} volume..."

  local cmd="
    rm -rf /data/* && \
    tar xzf /backup/opensearch-data.tar.gz -C /data
  "

  if ! run "docker run --rm \
    -v ${OPENSEARCH_VOLUME}:/data \
    -v '${BUNDLE_DIR}':/backup:ro \
    busybox sh -c \"${cmd}\""; then
    log_err "OpenSearch data read was unsuccessful (e.g. tar: invalid magic / short read)."
    log_info "The bundle file may be corrupted or an HTML page from Google Drive. Replace ${tar_src} with a valid opensearch-data.tar.gz and re-run this script to restore."
    return 0
  fi

  log_ok "OpenSearch data restored from tar (or simulated in DRY-RUN)."
}

start_opensearch_stack() {
  local compose_dir="${BASE_DIR}/opensearch"
  local compose_file="${compose_dir}/docker-compose.yml"

  if [ ! -f "${compose_file}" ]; then
    log_info "No opensearch/docker-compose.yml found – skipping OpenSearch stack."
    return 0
  fi

  log_step "Starting OpenSearch stack via docker-compose..."
  (
    cd "${compose_dir}"
    if command -v docker-compose >/dev/null 2>&1; then
      run "docker-compose up -d"
    else
      run "docker compose up -d"
    fi
  )
  log_ok "OpenSearch stack started (or simulated in DRY-RUN)."
}

# Ensure opensearch/scripts/restore_indices.sh exists so we can create indices (clusters, etc.) when needed
ensure_restore_indices_script() {
  local script_dir="${BASE_DIR}/opensearch/scripts"
  local script_path="${script_dir}/restore_indices.sh"
  [ -d "${script_dir}" ] || return 0
  [ -f "${script_path}" ] && return 0
  log_step "Creating restore_indices.sh so OpenSearch indices can be created..."
  cat > "${script_path}" << 'RESTORE_EOF'
#!/bin/bash
set -e
OPENSEARCH_URL="${OPENSEARCH_URL:-https://localhost:9200}"
OPENSEARCH_USER="${OPENSEARCH_USER:-admin}"
OPENSEARCH_PASS="${OPENSEARCH_PASS:-admin}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INDICES_DIR="${SCRIPT_DIR}/../indices"
echo "Waiting for OpenSearch at $OPENSEARCH_URL..."
while ! curl -k -s -u "${OPENSEARCH_USER}:${OPENSEARCH_PASS}" "${OPENSEARCH_URL}" >/dev/null 2>&1; do sleep 2; done
echo "OpenSearch is up."; echo ""
[ -d "$INDICES_DIR" ] || { echo "Error: Indices dir not found: $INDICES_DIR"; exit 1; }
for json_file in "$INDICES_DIR"/*.json; do
  [ -f "$json_file" ] || continue
  index_name=$(basename "$json_file" .json)
  echo "Creating index: $index_name"
  index_def=$(cat "$json_file")
  echo "$index_def" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if 'mappings' in data else 1)" 2>/dev/null || index_def=$(echo "$index_def" | python3 -c "import sys, json; data=json.load(sys.stdin); print(json.dumps(list(data.values())[0]))" 2>/dev/null)
  [ -n "$index_def" ] || index_def=$(jq -c '.[]' "$json_file" 2>/dev/null || true)
  [ -n "$index_def" ] || { echo "  ✗ Could not extract"; continue; }
  response=$(curl -k -s -w "\n%{http_code}" -u "${OPENSEARCH_USER}:${OPENSEARCH_PASS}" -X PUT "${OPENSEARCH_URL}/${index_name}" -H "Content-Type: application/json" -d "$index_def")
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | sed '$d')
  if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then echo "  ✓ Created"; elif [ "$http_code" = "400" ] && echo "$body" | grep -q "resource_already_exists_exception"; then echo "  ⚠ Already exists"; else echo "  ✗ HTTP $http_code"; fi
  echo ""
done
echo "Indices processed."
curl -k -s -u "${OPENSEARCH_USER}:${OPENSEARCH_PASS}" "${OPENSEARCH_URL}/_cat/indices?v" | grep -v "^\." || true
RESTORE_EOF
  chmod +x "${script_path}"
  log_ok "restore_indices.sh created."
}

run_restore_indices() {
  local script_dir="${BASE_DIR}/opensearch/scripts"
  local script_path="${script_dir}/restore_indices.sh"
  ensure_restore_indices_script
  if [ ! -f "${script_path}" ]; then
    log_info "No restore_indices.sh – skipping index creation."
    return 0
  fi
  log_step "Running restore_indices.sh to create OpenSearch indices from JSON files..."
  ( cd "${script_dir}" && run "./restore_indices.sh" )
  log_ok "restore_indices.sh completed (or simulated in DRY-RUN)."
}

start_n8n() {
  local script="${N8N_DIR}/docker/n8n/setup_n8n.sh"
  if [ ! -f "${script}" ]; then
    log_info "No setup_n8n.sh found at ${script} – skipping n8n."
    return 0
  fi

  log_step "Running n8n setup script (will pull image if needed)..."
  run "bash '${script}'"
  log_ok "n8n setup script finished (or simulated in DRY-RUN)."
}

start_llm_and_ollama() {
  local script="${N8N_DIR}/docker/llm-service/setup-llm-service.sh"
  if [ ! -f "${script}" ]; then
    log_info "No LLM/Ollama setup script found at ${script} – skipping."
    return 0
  fi

  log_step "Running LLM + Ollama setup script..."
  run "bash '${script}'"
  log_ok "LLM + Ollama setup script finished (or simulated in DRY-RUN)."
}

start_crawler_api() {
  local script="${N8N_DIR}/docker/crawler/setup-crawler-service.sh"
  if [ ! -f "${script}" ]; then
    log_info "No crawler setup script found at ${script} – skipping."
    return 0
  fi

  log_step "Running crawler-api setup script..."
  run "bash '${script}'"
  log_ok "crawler-api setup script finished (or simulated in DRY-RUN)."
}

start_dashboard() {
  local script="${N8N_DIR}/docker/streamlit-frontend/setup-frontend-service.sh"
  if [ ! -f "${script}" ]; then
    log_info "No dashboard setup script found at ${script} – skipping."
    return 0
  fi

  log_step "Running dashboard setup script..."
  run "bash '${script}'"
  log_ok "dashboard setup script finished (or simulated in DRY-RUN)."
}

main() {
  echo ""
  echo "╔════════════════════════════════════════════════════════════╗"
  echo "║     SWP NEWS SUMMARY - COMPLETE SETUP (SINGLE ENTRY)        ║"
  echo "╚════════════════════════════════════════════════════════════╝"
  echo ""
  echo "  Base directory: ${BASE_DIR}"
  echo "  n8n directory : ${N8N_DIR}"
  echo "  Bundle dir    : ${BUNDLE_DIR}"
  echo ""

  if [ "${DRY_RUN}" = "true" ]; then
    log_info "Running in DRY-RUN mode (no changes will be applied)."
    echo ""
  fi

  check_docker

  # -------------------------------------------------------------------------
  # Step: Move n8n-pipeline clone (cswspws25) under SWP-News-Summary as n8n
  # -------------------------------------------------------------------------
  # When the project is cloned, the repo name is cswspws25 and it sits at the
  # same level as SWP-News-Summary. We must move it under SWP-News-Summary and
  # rename it to n8n *before* fetching or restoring, so bundle paths resolve
  # correctly (e.g. n8n/bundle/n8n-data.tar.gz). If we move, we exit and ask
  # the user to re-run from the new location.
  maybe_move_clone_under_swp

  # Optionally clone missing service repositories (opensearch, crawler, llm, dashboard)
  maybe_clone_service_repos

  # -------------------------------------------------------------------------
  # Optionally fetch bundle archives from Google Drive if missing
  # -------------------------------------------------------------------------
  local fetch_script="${N8N_DIR}/bundle_fetch_backups.sh"
  if { [ ! -f "${BUNDLE_DIR}/n8n-data.tar.gz" ] || [ ! -f "${BUNDLE_DIR}/opensearch-data.tar.gz" ]; } \
     && [ -f "${fetch_script}" ]; then
    echo ""
    log_info "Bundle archives not found in ${BUNDLE_DIR}."
    echo "Fetch n8n + OpenSearch backups from Google Drive now? [y/N]"
    read -r REPLY
    if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
      if [ "${DRY_RUN}" = "true" ]; then
        echo -e "${YELLOW}[DRY RUN]${NC} Would run: bash '${fetch_script}'"
      else
        log_step "Fetching bundle archives via bundle_fetch_backups.sh..."
        ( cd "${N8N_DIR}" && bash "${fetch_script}" ) || true
      fi
    else
      log_info "Skipping Google Drive fetch for bundle archives."
    fi
  fi

  # If bundle files are still missing after fetch, show manual guide, open Drive, and continue (do not exit)
  if [ ! -f "${BUNDLE_DIR}/n8n-data.tar.gz" ] || [ ! -f "${BUNDLE_DIR}/opensearch-data.tar.gz" ]; then
    echo ""
    log_info "Bundle archives still missing. Opening Google Drive for manual download."
    n8n_drive_url="https://drive.google.com/file/d/15jpeU-q4TmAT6QJkGxd75uNrp9vktkim/view"
    os_drive_url="https://drive.google.com/file/d/1VVVi7rvpqzDWAkHmybXmMJM2lRjhlaJd/view"
    if command -v open >/dev/null 2>&1; then
      open "$n8n_drive_url" 2>/dev/null || true
      sleep 1
      open "$os_drive_url" 2>/dev/null || true
    elif command -v xdg-open >/dev/null 2>&1; then
      xdg-open "$n8n_drive_url" 2>/dev/null || true
      sleep 1
      xdg-open "$os_drive_url" 2>/dev/null || true
    fi
    echo ""
    echo "Instructions (bundle_data_setup):"
    echo "  1. In the opened tabs, download n8n-data.tar.gz and opensearch-data.tar.gz from Google Drive."
    echo "  2. Place both files inside the bundle folder: ${BUNDLE_DIR}"
    echo "  3. For n8n: run this script again and choose to restore n8n data when prompted (or copy into ~/.n8n)."
    echo "  4. For OpenSearch: run this script again and choose to restore OpenSearch when prompted."
    echo "  5. Then start containers when prompted."
    echo ""
    log_info "Continuing with networks/volumes and container startup (restore will be skipped if files absent)."
    echo ""
  fi

  # 1) Networks & volume
  ensure_network "${OPENSEARCH_NETWORK}"
  ensure_network "${N8N_NETWORK}"
  ensure_volume "${OPENSEARCH_VOLUME}"
  echo ""

  # 2) Restore data from bundle/backups (prompt for each when bundle exists, like OpenSearch)
  # Note: The n8n container bind-mounts ~/.n8n -> /home/node/.n8n, so we restore into the
  # same path the container reads. If n8n is already running, we restart it so it sees the new data.
  if [ -d "${N8N_DIR}/n8n-backup" ] || [ -f "${BUNDLE_DIR}/n8n-data.tar.gz" ]; then
    echo ""
    echo "Restore n8n data from bundle into ~/.n8n (overwrites current after backup)? [y/N]"
    read -r REPLY
    if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
      restore_n8n_data
      if [ "${DRY_RUN}" != "true" ]; then
        if docker ps --format '{{.Names}}' | grep -qx "n8n"; then
          log_step "Restarting n8n container so it picks up the restored data..."
          docker restart n8n
          log_ok "n8n restarted. Open the UI to see restored workflows."
        fi
      fi
    else
      log_info "Skipping n8n data restore."
    fi
  fi

  if [ -f "${BUNDLE_DIR}/opensearch-data.tar.gz" ]; then
    echo ""
    echo "Restore OpenSearch data from bundle into ${OPENSEARCH_VOLUME} volume (overwrites current contents)? [y/N]"
    read -r REPLY
    if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
      restore_opensearch_data
    else
      log_info "Skipping OpenSearch data restore."
    fi
  fi

  # Fallback: ensure OpenSearch indices (e.g. clusters) exist when tar restore was skipped/failed
  ensure_restore_indices_script
  if [ "${DRY_RUN}" != "true" ] && docker ps --format '{{.Names}}' | grep -qx "opensearch"; then
    if [ -f "${BASE_DIR}/opensearch/scripts/restore_indices.sh" ]; then
      log_step "Ensuring OpenSearch indices exist (fallback for missing/failed data restore)..."
      ( cd "${BASE_DIR}/opensearch/scripts" && chmod +x restore_indices.sh && ./restore_indices.sh ) || log_info "restore_indices.sh had issues (indices may already exist)."
    fi
  fi

  echo ""
  echo "Start containers (OpenSearch, n8n, LLM, crawler, dashboard) now? [y/N]"
  read -r REPLY
  if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
    start_opensearch_stack
    # Always ensure indices exist as in complete_setup
    run_restore_indices
    start_n8n
    # Ensure n8n can resolve "opensearch" (fix getaddrinfo ENOTFOUND in workflows).
    # OpenSearch is started via opensearch/docker-compose and is on its default network;
    # we attach both opensearch and n8n to opensearch_internal_net so they can reach each other.
    if [ "${DRY_RUN}" != "true" ]; then
      docker network create "${OPENSEARCH_NETWORK}" 2>/dev/null || true
      if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "opensearch"; then
        docker network connect "${OPENSEARCH_NETWORK}" opensearch 2>/dev/null && log_ok "opensearch attached to ${OPENSEARCH_NETWORK}." || true
      fi
      if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "n8n"; then
        docker network connect "${OPENSEARCH_NETWORK}" n8n 2>/dev/null && log_ok "n8n connected to ${OPENSEARCH_NETWORK} (opensearch hostname will resolve)." || true
      fi
    fi
    start_llm_and_ollama
    start_crawler_api
    start_dashboard
    # So the dashboard can reach OpenSearch at opensearch:9200
    if [ "${DRY_RUN}" != "true" ] && docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "dashboard"; then
      docker network connect "${OPENSEARCH_NETWORK}" dashboard 2>/dev/null && log_ok "dashboard connected to ${OPENSEARCH_NETWORK}." || true
    fi
  else
    log_info "Skipping container startup. You can run setup scripts manually later."
  fi

  echo ""
  log_ok "Complete setup finished. This is the only script you need; no need to run complete_setup or bundle_setup."
  echo ""
  echo "Usage:"
  echo "  ./bundle_data_setup.sh                 # Full setup (recommended)"
  echo "  DRY_RUN=true ./bundle_data_setup.sh    # Preview only, no changes"
  echo ""
}

main "$@"

