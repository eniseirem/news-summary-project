#!/usr/bin/env bash

# SWP News Summary - Bundle Rollback Helper
#
# Purpose:
# - Quickly undo the main changes made by bundle_setup.sh:
#   - Restore the most recent ~/.n8n_backup_* back to ~/.n8n
#   - Optionally restore opensearch-data volume from a backup tar
#
# Notes:
# - Does NOT touch containers (you can manually stop/remove new ones
#   and rename *_old containers back if you used that pattern).

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_step()  { echo -e "${YELLOW}▶${NC} $*"; }
log_ok()    { echo -e "${GREEN}✓${NC} $*"; }
log_err()   { echo -e "${RED}✗${NC} $*"; }

restore_n8n_backup() {
  local home="${HOME}"
  local latest_backup

  latest_backup=$(ls -d "${home}"/.n8n_backup_* 2>/dev/null | sort | tail -n 1 || true)

  if [ -z "${latest_backup}" ]; then
    log_step "No ~/.n8n_backup_* directories found – nothing to restore."
    return 0
  fi

  log_step "Restoring n8n config from backup: ${latest_backup}"

  if [ -d "${home}/.n8n" ]; then
    local current_backup="${home}/.n8n_bundle_$(date +%Y%m%d-%H%M%S)"
    log_step "Backing up current ~/.n8n to ${current_backup}..."
    mv "${home}/.n8n" "${current_backup}"
  fi

  mv "${latest_backup}" "${home}/.n8n"
  log_ok "Restored ~/.n8n from ${latest_backup}."
}

restore_opensearch_from_tar() {
  # BACKUP_DIR should contain opensearch-data.tgz created earlier
  local backup_dir="${BACKUP_DIR:-${HOME}/SWP-News-Summary/docker-backups}"
  local tar_path=""

  if [ -f "${backup_dir}/opensearch-data.tgz" ]; then
    tar_path="${backup_dir}/opensearch-data.tgz"
  else
    # Find most recent opensearch-data.tgz under docker-backups
    tar_path=$(find "${backup_dir}" -name "opensearch-data.tgz" 2>/dev/null | sort | tail -n 1 || true)
  fi

  if [ -z "${tar_path}" ]; then
    log_step "No opensearch-data.tgz backup found under ${backup_dir} – skipping OpenSearch restore."
    return 0
  fi

  log_step "Restoring opensearch-data volume from ${tar_path}..."

  docker run --rm \
    -v opensearch-data:/data \
    -v "$(dirname "${tar_path}")":/backup \
    busybox sh -c "cd /data && rm -rf ./* && tar xzf /backup/$(basename "${tar_path}")"

  log_ok "opensearch-data volume restored from backup."
}

main() {
  echo ""
  echo "╔════════════════════════════════════════════════════════════╗"
  echo "║       SWP NEWS SUMMARY - BUNDLE ROLLBACK HELPER            ║"
  echo "╚════════════════════════════════════════════════════════════╝"
  echo ""

  restore_n8n_backup

  echo ""
  echo "Restore OpenSearch data from backup tar? [y/N]"
  read -r REPLY
  if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
    restore_opensearch_from_tar
  else
    log_step "Skipping OpenSearch data restore."
  fi

  echo ""
  log_ok "Rollback script finished. You can now restart your old containers if needed."
  echo ""
}

main "$@"

