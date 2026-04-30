#!/bin/bash

# LLM Service Configuration

# Base directory
BASE_DIR="$HOME/SWP-News-Summary"

# Paths
LLM_PATH="${BASE_DIR}/cswspws25-m3-final"

# Container names
OLLAMA_CONTAINER="ollama"
LLM_CONTAINER="llm-service"

# Docker network
DOCKER_NETWORK="n8n-network"

# Ports
OLLAMA_PORT="11434"
LLM_PORT="8001"

# Ollama settings
OLLAMA_MODEL="llama3.2:3b"
OLLAMA_NUM_PARALLEL="2"
OLLAMA_CONTEXT_LENGTH="8192"
OLLAMA_BASE_URL="http://${OLLAMA_CONTAINER}:${OLLAMA_PORT}"
