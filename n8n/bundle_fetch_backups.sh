#!/usr/bin/env bash

# Fetch n8n and OpenSearch backup archives into the local bundle directory.
# This is intended to be run from the n8n repo root:
#   cd ~/SWP-News-Summary/n8n
#   ./bundle_fetch_backups.sh
#
# NOTE: Filenames are aligned with bundle_data_setup.sh expectations:
#   - bundle/n8n-data.tar.gz
#   - bundle/opensearch-data.tar.gz
# On download failure (e.g. HTML instead of file) the script does not exit;
# it continues and prints a manual download guide at the end.

mkdir -p bundle

FETCH_FAILED=0

download_from_gdrive () {
  FILE_ID="$1"
  OUTPUT="$2"

  if [ -f "$OUTPUT" ]; then
    echo "✔ $OUTPUT already exists — skipping download"
    return 0
  fi

  echo "⬇ Downloading $OUTPUT from Google Drive..."

  TMP_PAGE=$(mktemp)
  TMP_COOKIE=$(mktemp)

  # First request (may include confirm token)
  curl -s -L -c "$TMP_COOKIE" \
    "https://drive.google.com/uc?export=download&id=${FILE_ID}" \
    -o "$TMP_PAGE"

  CONFIRM=$(grep -o 'confirm=[^&]*' "$TMP_PAGE" | head -n1 | cut -d= -f2)

  if [ -n "$CONFIRM" ]; then
    curl -L -b "$TMP_COOKIE" \
      "https://drive.google.com/uc?export=download&confirm=${CONFIRM}&id=${FILE_ID}" \
      -o "$OUTPUT"
  else
    # If no confirm token, file was small and already downloaded
    mv "$TMP_PAGE" "$OUTPUT"
  fi

  rm -f "$TMP_PAGE" "$TMP_COOKIE"

  # Verify file is not HTML
  if file "$OUTPUT" | grep -q "HTML"; then
    echo "❌ Download failed — got HTML instead of file. Removing invalid file."
    rm -f "$OUTPUT"
    FETCH_FAILED=1
    return 1
  fi

  echo "✔ Downloaded $OUTPUT"
  return 0
}

# -----------------------------------------
# Download n8n backup (to bundle/n8n-data.tar.gz) — Drive id 15jpeU... = n8n-data.tar.gz
# -----------------------------------------
download_from_gdrive \
  "15jpeU-q4TmAT6QJkGxd75uNrp9vktkim" \
  "bundle/n8n-data.tar.gz" || true

# -----------------------------------------
# Download OpenSearch backup (to bundle/opensearch-data.tar.gz) — Drive id 1VVVi7... = opensearch-data.tar.gz
# -----------------------------------------
download_from_gdrive \
  "1VVVi7rvpqzDWAkHmybXmMJM2lRjhlaJd" \
  "bundle/opensearch-data.tar.gz" || true

if [ "$FETCH_FAILED" -eq 1 ]; then
  echo ""
  echo "⚠ Some downloads failed. Opening Google Drive so you can download manually."
  N8N_DRIVE_URL="https://drive.google.com/file/d/15jpeU-q4TmAT6QJkGxd75uNrp9vktkim/view"
  OPENSEARCH_DRIVE_URL="https://drive.google.com/file/d/1VVVi7rvpqzDWAkHmybXmMJM2lRjhlaJd/view"
  if command -v open >/dev/null 2>&1; then
    open "$N8N_DRIVE_URL" 2>/dev/null || true
    sleep 1
    open "$OPENSEARCH_DRIVE_URL" 2>/dev/null || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$N8N_DRIVE_URL" 2>/dev/null || true
    sleep 1
    xdg-open "$OPENSEARCH_DRIVE_URL" 2>/dev/null || true
  fi
  echo ""
  echo "Manual steps:"
  echo "  1. In the opened Drive tabs, download n8n-data.tar.gz and opensearch-data.tar.gz."
  echo "  2. Place both files inside the 'bundle' folder: $(pwd)/bundle/"
  echo "  3. Re-run bundle_data_setup to continue with restore and container startup."
  echo ""
else
  echo "✅ All bundle files ready."
  echo ""
  # Last step: load the data into existing n8n dir and OpenSearch volume
  N8N_TAR="bundle/n8n-data.tar.gz"
  OS_TAR="bundle/opensearch-data.tar.gz"
  TARGET_N8N="${HOME}/.n8n"
  OPENSEARCH_VOLUME="${OPENSEARCH_VOLUME:-opensearch-data}"
  if [ -f "$N8N_TAR" ] && [ -f "$OS_TAR" ]; then
    echo "Load fetched data into existing ~/.n8n and OpenSearch volume now? [y/N]"
    read -r REPLY
    if [[ "${REPLY}" =~ ^[Yy]$ ]]; then
      # n8n: backup existing then extract
      if [ -d "$TARGET_N8N" ]; then
        BACKUP="${HOME}/.n8n_backup_$(date +%Y%m%d-%H%M%S)"
        echo "▶ Backing up existing ~/.n8n to $BACKUP..."
        mv "$TARGET_N8N" "$BACKUP"
      fi
      mkdir -p "$TARGET_N8N"
      echo "▶ Loading n8n data from $N8N_TAR into ~/.n8n..."
      tar xzf "$N8N_TAR" -C "$TARGET_N8N" --strip-components=1
      echo "✔ n8n data loaded. Restart the n8n container to see workflows."
      echo ""
      # OpenSearch: extract into volume via busybox
      echo "▶ Loading OpenSearch data from $OS_TAR into volume $OPENSEARCH_VOLUME..."
      if docker run --rm \
        -v "${OPENSEARCH_VOLUME}:/data" \
        -v "$(pwd)/bundle:/backup:ro" \
        busybox sh -c "rm -rf /data/* && tar xzf /backup/opensearch-data.tar.gz -C /data" 2>/dev/null; then
        echo "✔ OpenSearch data loaded."
      else
        echo "⚠ OpenSearch load failed (e.g. invalid tar or volume). Creating indices from JSON so UI can load."
      fi
      # Ensure indices (e.g. clusters) exist — required if tar load failed or data dir had no index state
      OPENSEARCH_SCRIPTS="$(cd "$(dirname "$0")" && pwd)/../opensearch/scripts"
      if [ -f "${OPENSEARCH_SCRIPTS}/restore_indices.sh" ]; then
        echo "▶ Ensuring OpenSearch indices exist (clusters, articles, etc.)..."
        ( cd "${OPENSEARCH_SCRIPTS}" && chmod +x restore_indices.sh 2>/dev/null; ./restore_indices.sh ) && echo "✔ Indices ready." || echo "⚠ restore_indices had issues (indices may already exist)."
      fi
      # Restart containers so they use the loaded data
      echo ""
      echo "▶ Restarting containers to pick up loaded data..."
      docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "n8n"       && { docker restart n8n 2>/dev/null       && echo "✔ n8n restarted."       || true; } || true
      docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "opensearch" && { docker restart opensearch 2>/dev/null && echo "✔ OpenSearch restarted." || true; } || true
      # Ensure n8n can resolve hostname "opensearch" (fix getaddrinfo ENOTFOUND opensearch).
      # Attach both opensearch and n8n to the same network so they can reach each other.
      OPENSEARCH_NET="${OPENSEARCH_NET:-opensearch_internal_net}"
      docker network create "$OPENSEARCH_NET" 2>/dev/null || true
      docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "opensearch" && { docker network connect "$OPENSEARCH_NET" opensearch 2>/dev/null && echo "✔ opensearch attached to $OPENSEARCH_NET." || true; }
      docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "n8n"       && { docker network connect "$OPENSEARCH_NET" n8n 2>/dev/null       && echo "✔ n8n connected to $OPENSEARCH_NET (opensearch hostname will resolve)." || true; }
      docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "dashboard" && { docker network connect "$OPENSEARCH_NET" dashboard 2>/dev/null && echo "✔ dashboard connected to $OPENSEARCH_NET." || true; }
      echo ""
      echo "✅ Fetch and load finished."
    else
      echo "Skipping load. Run bundle_data_setup to load data and start containers later."
    fi
  fi
fi
exit 0

