#!/bin/bash

# Simple Crawler API Setup
# Creates crawler-api and connects to existing n8n-network

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
BASE_DIR="$HOME/SWP-News-Summary"
CRAWLER_PATH="${BASE_DIR}/cswspws25-WebCrawlerMain"
CRAWLER_CONTAINER="crawler-api"
CRAWLER_PORT="8003"
INTERNAL_PORT="8000"
DOCKER_NETWORK="n8n-network"

echo ""
echo "Setting up crawler-api..."
echo ""

# Verify crawler directory exists
if [ ! -d "${CRAWLER_PATH}" ]; then
    echo -e "${RED}✗ Crawler directory not found: ${CRAWLER_PATH}${NC}"
    exit 1
fi

if [ ! -f "${CRAWLER_PATH}/main.py" ]; then
    echo -e "${RED}✗ main.py not found in ${CRAWLER_PATH}${NC}"
    exit 1
fi

# Clean up old container
echo " Stopping old container..."
docker stop ${CRAWLER_CONTAINER} 2>/dev/null || true
docker rm ${CRAWLER_CONTAINER} 2>/dev/null || true

# Create crawler-api on n8n-network
echo " Creating crawler-api container..."
docker run -d \
  --name ${CRAWLER_CONTAINER} \
  --network ${DOCKER_NETWORK} \
  -p ${CRAWLER_PORT}:${INTERNAL_PORT} \
  -v "${CRAWLER_PATH}:/crawler" \
  -w /crawler \
  --restart unless-stopped \
  python:3.11-slim \
  bash -c "
    apt-get update > /dev/null 2>&1 && \
    apt-get install -y gcc python3-dev > /dev/null 2>&1 && \
    pip install --no-cache-dir --quiet \
      fastapi \
      'uvicorn[standard]' \
      requests \
      beautifulsoup4 \
      feedparser \
      newspaper3k \
      lxml \
      lxml_html_clean && \
    sleep 3 && \
    uvicorn main:app --host 0.0.0.0 --port ${INTERNAL_PORT}
  "

echo " Waiting for crawler to start..."
sleep 10

# Verify
if docker ps | grep -q "${CRAWLER_CONTAINER}"; then
    echo -e "${GREEN}✓ Crawler running on n8n-network${NC}"
    echo ""
    echo "  Container: ${CRAWLER_CONTAINER}"
    echo "  Network:   ${DOCKER_NETWORK}"
    echo "  Host URL:  http://localhost:${CRAWLER_PORT}/docs"
    echo "  n8n URL:   http://${CRAWLER_CONTAINER}:${INTERNAL_PORT}"
    echo ""
    
    # Test from n8n
    if docker exec n8n curl -s http://${CRAWLER_CONTAINER}:${INTERNAL_PORT} > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Accessible from n8n${NC}"
    else
        echo -e "${YELLOW}⚠ Not yet accessible from n8n (may need a few more seconds)${NC}"
    fi
else
    echo -e "${RED}✗ Failed to start${NC}"
    docker logs ${CRAWLER_CONTAINER} --tail 30
    exit 1
fi

echo ""
echo "Done!"
