#!/bin/bash

# Configuration file for SWP News Summary project
# Edit this file to change the base directory or project paths

# Base directory - change this if your project is in a different location
BASE_DIR="$HOME/Desktop/SWP-News-Summary"

# Project subdirectories
CRAWLER_PATH="${BASE_DIR}/cswspws25-WebCrawlerMain"
LLM_PATH="${BASE_DIR}/cswspws25-llm-pipeline"
DASH_PATH="${BASE_DIR}/dashboard"

# Container names
N8N_CONTAINER="n8n"
LLM_CONTAINER="llm-service"

# Network name
DOCKER_NETWORK="n8n-network"

# Ports
N8N_PORT="5678"
LLM_PORT="8001"

# Timezone
TIMEZONE="Europe/Berlin"

# Export all variables so they can be used by other scripts
export BASE_DIR
export CRAWLER_PATH
export LLM_PATH
export DASH_PATH
export N8N_CONTAINER
export LLM_CONTAINER
export DOCKER_NETWORK
export N8N_PORT
export LLM_PORT
export TIMEZONE
