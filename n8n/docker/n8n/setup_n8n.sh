#!/bin/bash

# n8n + LLM Setup - FIXED VERSION with OPTIONS
# Choose what to setup: n8n only, LLM only, or both

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config_m2.sh"
SETUP_N8N=true

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

clear
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║       N8N                                                  ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo " Base directory: ${BASE_DIR}"
echo ""

CONTAINER_NAME="${N8N_CONTAINER}"

# =============================================================================
# N8N SETUP
# =============================================================================
if [ "$SETUP_N8N" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║                 SETTING UP N8N                             ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # Clean up n8n
    echo " Cleaning up old n8n container..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
    echo ""

    echo " Pulling n8n image..."
    IMAGE="n8nio/n8n:latest"
    docker pull $IMAGE

    echo ""
    echo " Creating n8n container..."
    docker run -d --name $CONTAINER_NAME \
        --network ${DOCKER_NETWORK} \
        -p ${N8N_PORT}:5678 \
        -v ~/.n8n:/home/node/.n8n \
        -v "${CRAWLER_PATH}:/crawler:rw" \
        -v "${LLM_PATH}:/llm:rw" \
        -v "${DASH_PATH}:/dashboard:rw" \
        -e GENERIC_TIMEZONE=${TIMEZONE} \
        -e OLLAMA_BASE_URL="${OLLAMA_BASE_URL}" \
        -e OLLAMA_MODEL="${OLLAMA_MODEL}" \
        -e NODES_EXCLUDE='[]' \
        --restart unless-stopped \
        $IMAGE

    echo " Waiting for n8n..."
    sleep 8

    if ! docker ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${RED} n8n container failed to start${NC}"
        docker logs $CONTAINER_NAME --tail 30
        exit 1
    fi

    echo -e "${GREEN} n8n running${NC}"
    echo ""
    echo " Connecting n8n to opensearch_internal_net..."
    if docker network inspect opensearch_internal_net >/dev/null 2>&1; then
       docker network connect opensearch_internal_net $CONTAINER_NAME 2>/dev/null || true
    else
       echo "Network opensearch_internal_net not found, skipping"
    fi
    echo " Testing OpenSearch DNS from n8n..."
    docker exec -it "$CONTAINER_NAME" sh -lc 'getent hosts opensearch && echo " opensearch resolvable" || echo " opensearch not resolvable"'

    # Connect to network
    echo " Connecting n8n to network..."
    docker network connect ${DOCKER_NETWORK} ${N8N_CONTAINER} 2>/dev/null || echo "  (already connected)"
    echo ""
fi

# =============================================================================
# COMPLETION SUMMARY
# =============================================================================

clear
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                   SETUP COMPLETE!                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if [ "$SETUP_N8N" = true ]; then
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}   N8N SETUP${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "   Container: ${N8N_CONTAINER}"
    echo "   n8n UI: http://localhost:${N8N_PORT}"
    echo ""
fi

echo -e "${GREEN} Setup complete! ${NC}"
echo ""
