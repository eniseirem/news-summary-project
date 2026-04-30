#!/usr/bin/env bash

# SWP News Summary - Bundle / Infra Setup
#
# Purpose:
# - Make Docker Desktop bundles and manual restores reproducible by:
#   - Ensuring all required Docker networks and volumes exist
#   - Leaving container creation to your bundle files (this script
#     does NOT run complete_setup.sh or workflow_setup.sh)
#
# Safety:
# - Does NOT stop/remove containers, networks, or volumes.
# - Only creates networks/volumes if they don't already exist.
# - Supports DRY-RUN mode via DRY_RUN=true

set -euo pipefail

DRY_RUN="${DRY_RUN:-false}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

BASE_DIR="${HOME}/SWP-News-Summary"
N8N_DIR="${BASE_DIR}/n8n"

# Directory containing bundle artifacts:
# - images.tar
# - n8n-data/           (bind mount contents for n8n)
# - opensearch-data/    (filesystem snapshot for opensearch-data volume)
BUNDLE_DIR="${BUNDLE_DIR:-${N8N_DIR}/bundle}"

# Shared networks across the stack
OPENSEARCH_NETWORK="opensearch_internal_net"
N8N_NETWORK="n8n-network"

# Volumes referenced by the stack
VOLUMES=(
  "opensearch-data"
)

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

restore_images_from_bundle() {
  local images_tar="${BUNDLE_DIR}/images.tar"
  if [ ! -f "${images_tar}" ]; then
    log_info "No images.tar found in ${BUNDLE_DIR} – skipping image load."
    return 0
  fi

  log_step "Loading Docker images from ${images_tar}..."

  # Show basic info so it doesn't look stuck
  if command -v stat >/dev/null 2>&1; then
    local size_bytes
    size_bytes=$(stat -f '%z' "${images_tar}" 2>/dev/null || stat -c '%s' "${images_tar}" 2>/dev/null || echo "?")
    log_info "Bundle size: ${size_bytes} bytes"
  fi

  local start_ts
  start_ts=$(date +"%Y-%m-%d %H:%M:%S")
  log_info "Start time: ${start_ts}"
  log_info "This can take several minutes on first run. Command:"
  echo "  docker load -i '${images_tar}'"
  echo ""

  local start_secs=$SECONDS
  run "docker load -i '${images_tar}'"
  local end_secs=$SECONDS
  local end_ts
  end_ts=$(date +"%Y-%m-%d %H:%M:%S")
  local elapsed=$((end_secs - start_secs))

  log_ok "Images from bundle loaded (or simulated in DRY-RUN)."
  log_info "End time:   ${end_ts} (elapsed ~${elapsed}s)"
}

restore_n8n_data_from_bundle() {
  local backup_dir="${N8N_DIR}/n8n-backup"
  local tar_src="${BUNDLE_DIR}/n8n-data.tar.gz"
  local target="${HOME}/.n8n"

  if [ -d "${backup_dir}" ]; then
    log_step "Restoring n8n data from directory backup: ${backup_dir} -> ${target}"
    
    # Backup existing n8n data if present
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
    # Tar has paths like '.n8n/database.sqlite', so strip the first component
    # so files end up directly under ~/.n8n instead of ~/.n8n/.n8n/...
    run "tar xzf '${tar_src}' -C '${target}' --strip-components=1"
    log_ok "n8n data restored from n8n-data.tar.gz (or simulated in DRY-RUN)."
    return 0
  fi

  log_info "No n8n-backup directory or n8n-data.tar.gz found – skipping n8n data restore."
}

restore_opensearch_data_from_bundle() {
  local tar_src="${BUNDLE_DIR}/opensearch-data.tar.gz"

  if [ ! -f "${tar_src}" ]; then
    log_info "No opensearch-data.tar.gz found in ${BUNDLE_DIR} – skipping OpenSearch data restore."
    return 0
  fi

  log_step "Restoring OpenSearch data from ${tar_src} into opensearch-data volume..."

  # This overwrites current contents of the opensearch-data volume.
  # Caller should have created a backup already (which you did earlier).
  local cmd="
    rm -rf /data/* && \
    tar xzf /backup/opensearch-data.tar.gz -C /data
  "

  if ! run "docker run --rm \
    -v opensearch-data:/data \
    -v '${BUNDLE_DIR}':/backup:ro \
    busybox sh -c \"${cmd}\""; then
    log_err "OpenSearch data read was unsuccessful (e.g. tar: invalid magic / short read)."
    log_info "The bundle file may be corrupted or an HTML page from Google Drive. Replace ${tar_src} with a valid opensearch-data.tar.gz and re-run this script to restore."
    return 0
  fi

  log_ok "OpenSearch data restored from bundle (or simulated in DRY-RUN)."
}

create_opensearch_containers() {
  local compose_dir="${BASE_DIR}/opensearch"
  local compose_file="${compose_dir}/docker-compose.yml"

  if [ ! -f "${compose_file}" ]; then
    log_info "No opensearch/docker-compose.yml found – skipping OpenSearch containers."
    return 0
  fi

  log_step "Starting OpenSearch stack from docker-compose.yml..."
  (
    cd "${compose_dir}"
    if command -v docker-compose >/dev/null 2>&1; then
      run "docker-compose up -d"
    else
      run "docker compose up -d"
    fi
  )

  log_ok "OpenSearch containers started (or simulated in DRY-RUN)."
}

create_n8n_container() {
  # Use existing config_m2.sh for paths and network config
  local cfg="${N8N_DIR}/docker/n8n/config_m2.sh"
  if [ ! -f "${cfg}" ]; then
    log_info "No config_m2.sh found at ${cfg} – skipping n8n container."
    return 0
  fi

  # shellcheck source=/dev/null
  source "${cfg}"

  local container_name="${N8N_CONTAINER:-n8n}"
  local image="n8nio/n8n:latest"

  if docker ps -a --format '{{.Names}}' | grep -qx "${container_name}"; then
    log_info "n8n container '${container_name}' already exists – not recreating."
    return 0
  fi

  log_step "Creating n8n container '${container_name}' using image ${image}..."

  run "docker run -d --name ${container_name} \
    --network ${DOCKER_NETWORK} \
    -p ${N8N_PORT:-5678}:5678 \
    -v ${HOME}/.n8n:/home/node/.n8n \
    -v \"${CRAWLER_PATH}:/crawler:rw\" \
    -v \"${LLM_PATH}:/llm:rw\" \
    -v \"${DASH_PATH}:/dashboard:rw\" \
    -e GENERIC_TIMEZONE=${TIMEZONE:-Europe/Berlin} \
    -e OLLAMA_BASE_URL=\"${OLLAMA_BASE_URL:-http://ollama:11434}\" \
    -e OLLAMA_MODEL=\"${OLLAMA_MODEL:-llama3.2:3b}\" \
    -e NODES_EXCLUDE='[]' \
    --restart unless-stopped \
    ${image}"

  # Also connect n8n to OpenSearch network (like setup_n8n.sh)
  run "docker network connect ${OPENSEARCH_NETWORK} ${container_name} 2>/dev/null || true"

  log_ok "n8n container '${container_name}' created (or simulated in DRY-RUN)."
}

run_llm_and_ollama() {
  local script="${N8N_DIR}/docker/llm-service/setup-llm-service.sh"
  if [ ! -f "${script}" ]; then
    log_info "No LLM/Ollama setup script found at ${script} – skipping."
    return 0
  fi

  log_step "Running LLM + Ollama setup script..."
  run "bash '${script}'"
  log_ok "LLM + Ollama setup script finished (or simulated in DRY-RUN)."
}

run_crawler_api() {
  local script="${N8N_DIR}/docker/crawler/setup-crawler-service.sh"
  if [ ! -f "${script}" ]; then
    log_info "No crawler setup script found at ${script} – skipping."
    return 0
  fi

  log_step "Running crawler-api setup script..."
  run "bash '${script}'"
  log_ok "crawler-api setup script finished (or simulated in DRY-RUN)."
}

run_dashboard() {
  local script="${N8N_DIR}/docker/streamlit-frontend/setup-frontend-service.sh"
  if [ ! -f "${script}" ]; then
    log_info "No dashboard setup script found at ${script} – skipping."
    return 0
  fi

  log_step "Running dashboard setup script..."
  run "bash '${script}'"
  log_ok "dashboard setup script finished (or simulated in DRY-RUN)."
}

connect_service_to_opensearch_network() {
  local service_name="$1"

  # Only attempt if both containers exist
  if ! docker ps -a --format '{{.Names}}' | grep -qx "${service_name}"; then
    log_info "Container '${service_name}' not found – skipping OpenSearch network connect."
    return 0
  fi
  if ! docker ps -a --format '{{.Names}}' | grep -qx "opensearch"; then
    log_info "OpenSearch container not found – skipping OpenSearch network connect for '${service_name}'."
    return 0
  fi

  log_step "Connecting '${service_name}' to the same network(s) as OpenSearch (like complete_setup)..."

  # Detect which networks OpenSearch is on
  local opensearch_networks
  opensearch_networks=$(docker inspect "opensearch" --format '{{range $key, $value := .NetworkSettings.Networks}}{{$key}} {{end}}')

  if [ -z "${opensearch_networks}" ]; then
    log_info "OpenSearch is not attached to any user-defined network – skipping."
    return 0
  fi

  log_info "OpenSearch is on networks: ${opensearch_networks}"

  # Prefer opensearch_internal_net or opensearch_default if present
  local target_network=""
  for network in ${opensearch_networks}; do
    if [ "${network}" = "${OPENSEARCH_NETWORK}" ] || [ "${network}" = "opensearch_default" ] || [ "${network}" = "opensearch_internal_net" ]; then
      target_network="${network}"
      break
    fi
  done

  # If no preferred network found, just take the first one
  if [ -z "${target_network}" ]; then
    target_network=$(echo "${opensearch_networks}" | awk '{print $1}')
  fi

  if [ -z "${target_network}" ]; then
    log_info "Could not determine a target OpenSearch network – skipping."
    return 0
  fi

  log_step "Connecting '${service_name}' to OpenSearch network: ${target_network}"
  run "docker network connect '${target_network}' '${service_name}' 2>/dev/null || true"
  log_ok "'${service_name}' connected to ${target_network} (or already connected)."
}

main() {
  echo ""
  echo "╔════════════════════════════════════════════════════════════╗"
  echo "║           SWP NEWS SUMMARY - BUNDLE/INFRA SETUP            ║"
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

  # 1) Ensure infra needed by bundles and setup scripts
  log_step "Preparing base Docker infrastructure (networks & volumes)..."
  ensure_network "${OPENSEARCH_NETWORK}"
  ensure_network "${N8N_NETWORK}"

  for vol in "${VOLUMES[@]}"; do
    ensure_volume "${vol}"
  done

  log_ok "Base Docker infrastructure ready."
  echo ""

  # 2) Restore from bundle artifacts (images + data)
  restore_images_from_bundle

  if [ "${DRY_RUN}" = "true" ]; then
    log_info "DRY-RUN: n8n-data and opensearch-data restores simulated only."
    echo ""
    log_ok "bundle_setup.sh finished (infra + bundle load simulated)."
    return 0
  fi

  # n8n data
  if [ -d "${N8N_DIR}/n8n-backup" ] || [ -f "${BUNDLE_DIR}/n8n-data.tar.gz" ]; then
    echo ""
    echo "Restore n8n data from bundle (overwrites current ~/.n8n after backup)? [y/N]"
    read -r REPLY
    if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
      restore_n8n_data_from_bundle
    else
      log_info "Skipping n8n data restore."
    fi
  fi

  # OpenSearch data
  if [ -f "${BUNDLE_DIR}/opensearch-data.tar.gz" ]; then
    echo ""
    echo "Restore OpenSearch data from bundle into opensearch-data volume (overwrites current contents)? [y/N]"
    read -r REPLY
    if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
      restore_opensearch_data_from_bundle
    else
      log_info "Skipping OpenSearch data restore."
    fi
  fi

  echo ""
  echo "Create containers (OpenSearch + n8n) using the restored bundle data now? [y/N]"
  read -r REPLY
  if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
    create_opensearch_containers
    create_n8n_container
    run_llm_and_ollama
    run_crawler_api
    run_dashboard
    # Ensure n8n and dashboard can reach OpenSearch by its container name,
    # using the same logic as complete_setup's connect_n8n_to_opensearch.
    connect_service_to_opensearch_network "n8n"
    connect_service_to_opensearch_network "dashboard"
  else
    log_info "Skipping container creation. You can start them manually later."
  fi

  echo ""
  log_ok "bundle_setup.sh finished: infra prepared, bundle data restored, container creation handled."
  echo ""
  echo "Next steps:"
  echo "  - If you skipped container creation, start them via:"
  echo "      - OpenSearch:  cd opensearch && docker compose up -d"
  echo "      - n8n:        docker start n8n   (or rerun this script and answer Y)"
  echo ""
  echo "Usage examples:"
  echo "  DRY_RUN=true ./bundle_setup.sh      # Show what would happen, no changes"
  echo "  ./bundle_setup.sh                   # Real run (restore bundle data)"
  echo ""
}

main "$@"

