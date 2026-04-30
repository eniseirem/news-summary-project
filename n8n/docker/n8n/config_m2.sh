#!/bin/bash

# n8n Configuration

# Base directory
BASE_DIR="$HOME/SWP-News-Summary"

# Paths
CRAWLER_PATH="${BASE_DIR}/cswspws25-WebCrawlerMain"
LLM_PATH="${BASE_DIR}/cswspws25-m3-final"
DASH_PATH="${BASE_DIR}/frontend"

# Container names
N8N_CONTAINER="n8n"
OLLAMA_CONTAINER="ollama"

# Docker network
DOCKER_NETWORK="n8n-network"

# Ports
N8N_PORT="5678"
OLLAMA_PORT="11434"

# Timezone
TIMEZONE="Europe/Berlin"

# Ollama settings
OLLAMA_BASE_URL="http://${OLLAMA_CONTAINER}:${OLLAMA_PORT}"
OLLAMA_MODEL="llama3.2:3b"
