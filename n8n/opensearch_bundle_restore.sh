#!/usr/bin/env bash

# Restore OpenSearch data from bundle tar, or (fallback) create indices via restore_indices.sh.
#
# - Looks for opensearch-data.tar.gz under the n8n bundle directory
#   (by default: $HOME/SWP-News-Summary/n8n/bundle/opensearch-data.tar.gz).
# - If present, replaces the contents of the opensearch-data volume with the tar contents.
# - If not present, falls back to running opensearch/scripts/restore_indices.sh
#   to create indices from JSON files.
# - Does NOT touch n8n; it only affects OpenSearch data/indices.

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

BASE_DIR="${HOME}/SWP-News-Summary"
N8N_DIR="${BASE_DIR}/n8n"
N8N_BUNDLE_DIR="${N8N_BUNDLE_DIR:-${N8N_DIR}/bundle}"
OPENSEARCH_DIR="${BASE_DIR}/opensearch"
OPENSEARCH_VOLUME="opensearch-data"
TARBALL="${N8N_BUNDLE_DIR}/opensearch-data.tar.gz"

log_step()  { echo -e "${YELLOW}▶${NC} $*"; }
log_ok()    { echo -e "${GREEN}✓${NC} $*"; }
log_err()   { echo -e "${RED}✗${NC} $*"; }
log_info()  { echo -e "${CYAN}ℹ${NC} $*"; }

check_docker() {
  log_step "Checking Docker daemon..."
  if ! docker info >/dev/null 2>&1; then
    log_err "Docker is not running. Please start Docker Desktop and try again."
    exit 1
  fi
  log_ok "Docker is running."
}

ensure_volume() {
  local name="$1"
  log_step "Ensuring Docker volume '${name}' exists..."
  if docker volume ls --format '{{.Name}}' | grep -qx "${name}"; then
    log_ok "Volume '${name}' already exists."
  else
    docker volume create "${name}" >/dev/null
    log_ok "Volume '${name}' created."
  fi
}

restore_from_tar() {
  if [ ! -f "${TARBALL}" ]; then
    log_info "No opensearch-data.tar.gz found at ${TARBALL} – cannot restore volume from tar."
    return 1
  fi

  log_step "Restoring OpenSearch data from bundle tar:"
  log_info "  Tarball : ${TARBALL}"
  log_info "  Volume  : ${OPENSEARCH_VOLUME}"
  echo ""
  echo -e "${YELLOW}⚠ This will ERASE current contents of the '${OPENSEARCH_VOLUME}' volume and replace them with the tar data.${NC}"
  read -r -p "Proceed with volume restore? [y/N] " REPLY
  echo ""
  if [[ ! "${REPLY}" =~ ^[Yy]$ ]]; then
    log_info "User chose not to restore from tar. Skipping volume restore."
    return 1
  fi

  ensure_volume "${OPENSEARCH_VOLUME}"

  log_step "Running busybox helper to clear volume and extract tar..."
  if ! docker run --rm \
    -v "${OPENSEARCH_VOLUME}":/data \
    -v "${N8N_BUNDLE_DIR}":/backup:ro \
    busybox sh -c "rm -rf /data/* && tar xzf /backup/opensearch-data.tar.gz -C /data"; then
    log_err "OpenSearch data read was unsuccessful (e.g. tar: invalid magic / short read)."
    log_info "The bundle file may be corrupted or an HTML page from Google Drive. Replace ${TARBALL} with a valid opensearch-data.tar.gz and re-run."
    return 1
  fi

  log_ok "OpenSearch data restored from opensearch-data.tar.gz."
  return 0
}

run_restore_indices_script() {
  local script_dir="${OPENSEARCH_DIR}/scripts"
  local script_path="${script_dir}/restore_indices.sh"

  if [ ! -f "${script_path}" ]; then
    log_info "No restore_indices.sh found at ${script_path} – skipping index creation."
    return 1
  fi

  log_step "Running restore_indices.sh to create indices from JSON files..."
  chmod +x "${script_path}"
  ( cd "${script_dir}" && ./restore_indices.sh )
  log_ok "restore_indices.sh completed."
  return 0
}

main() {
  echo ""
  echo "╔════════════════════════════════════════════════════════════╗"
  echo "║    OPENSEARCH BUNDLE DATA / INDICES RESTORE (NO N8N)       ║"
  echo "╚════════════════════════════════════════════════════════════╝"
  echo ""
  echo "  Base directory : ${BASE_DIR}"
  echo "  Bundle dir     : ${N8N_BUNDLE_DIR}"
  echo "  Volume         : ${OPENSEARCH_VOLUME}"
  echo ""

  check_docker

  # 1) Try to restore from opensearch-data.tar.gz if available
  if restore_from_tar; then
    echo ""
    log_ok "OpenSearch volume restored from bundle tar."
  else
    echo ""
    log_info "Falling back to index creation via restore_indices.sh (if available)..."
    if ! run_restore_indices_script; then
      log_info "No restore_indices.sh run. You may need to create indices manually."
    fi
  fi

  echo ""
  log_ok "opensearch_bundle_restore.sh finished."
  echo ""
}

main "$@"

