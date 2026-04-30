#!/bin/bash

# LLM Service Setup Script - With Git clone support

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

# Git configuration
GIT_REPO="https://gitlab.fokus.fraunhofer.de/dana/cswspws25.git"
GIT_BRANCH="m3-final"

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║         LLM SERVICE + OLLAMA SETUP                         ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Check if LLM directory exists
if [ -d "$LLM_PATH" ]; then
    echo -e "${YELLOW}⚠ LLM directory already exists: $LLM_PATH${NC}"
    echo ""
    
    # Check if it's a git repository
    if [ -d "$LLM_PATH/.git" ]; then
        cd "$LLM_PATH"
        
        # Check for uncommitted changes
        if ! git diff-index --quiet HEAD -- 2>/dev/null || [ -n "$(git ls-files --others --exclude-standard)" ]; then
            echo -e "${YELLOW}⚠ Git repository has local changes or untracked files${NC}"
            echo ""
            echo "Options:"
            echo "  1) Delete and clone fresh from Git (RECOMMENDED)"
            echo "  2) Discard changes and pull latest"
            echo "  3) Keep current files and skip Git update"
            echo "  4) Exit and handle manually"
            echo ""
            read -p "Choose option (1/2/3/4): " -n 1 -r
            echo
            
            case $REPLY in
                1)
                    echo "→ Deleting existing directory..."
                    cd ..
                    rm -rf "$LLM_PATH"
                    ;;
                2)
                    echo "→ Discarding all local changes..."
                    git reset --hard
                    git clean -fd
                    
                    CURRENT_BRANCH=$(git branch --show-current)
                    if [ "$CURRENT_BRANCH" != "$GIT_BRANCH" ]; then
                        echo "→ Switching to $GIT_BRANCH branch..."
                        git fetch origin
                        git checkout "$GIT_BRANCH"
                        git reset --hard origin/"$GIT_BRANCH"
                    else
                        echo "→ Pulling latest changes..."
                        git fetch origin
                        git reset --hard origin/"$GIT_BRANCH"
                    fi
                    echo -e "${GREEN}✓ Repository updated${NC}"
                    cd ..
                    ;;
                3)
                    echo "→ Using existing directory without Git update..."
                    cd ..
                    ;;
                4)
                    echo "Exiting. You can manually handle git changes with:"
                    echo "  cd $LLM_PATH"
                    echo "  git stash  # or git reset --hard"
                    echo "  git checkout $GIT_BRANCH"
                    echo "  git pull"
                    exit 0
                    ;;
                *)
                    echo -e "${RED}Invalid option. Exiting.${NC}"
                    exit 1
                    ;;
            esac
        else
            # No local changes, safe to update
            echo "→ No local changes detected"
            read -p "Pull latest changes from Git? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                CURRENT_BRANCH=$(git branch --show-current)
                if [ "$CURRENT_BRANCH" != "$GIT_BRANCH" ]; then
                    echo "→ Switching to $GIT_BRANCH branch..."
                    git fetch origin
                    git checkout "$GIT_BRANCH"
                    git pull origin "$GIT_BRANCH"
                else
                    echo "→ Pulling latest changes..."
                    git pull origin "$GIT_BRANCH"
                fi
                echo -e "${GREEN}✓ Repository updated${NC}"
            else
                echo "→ Using existing directory without updates..."
            fi
            cd ..
        fi
    else
        # Not a git repo
        echo "→ Directory exists but is not a Git repository"
        read -p "Delete and clone from Git? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "→ Deleting existing directory..."
            rm -rf "$LLM_PATH"
        else
            echo "→ Using existing directory..."
        fi
    fi
    echo ""
fi

# Clone repository if directory doesn't exist
if [ ! -d "$LLM_PATH" ]; then
    echo "→ Cloning LLM service from Git..."
    echo "  Repository: $GIT_REPO"
    echo "  Branch:     $GIT_BRANCH"
    echo ""
    
    BASE_DIR=$(dirname "$LLM_PATH")
    mkdir -p "$BASE_DIR"
    cd "$BASE_DIR"
    
    echo "You'll need to enter your GitLab credentials:"
    git clone -b "$GIT_BRANCH" "$GIT_REPO" "$(basename "$LLM_PATH")"
    
    if [ ! -d "$LLM_PATH" ]; then
        echo -e "${RED}✗ Failed to clone repository${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Repository cloned${NC}"
    echo ""
fi

# Verify we're in the right directory now
if [ ! -d "$LLM_PATH" ]; then
    echo -e "${RED}✗ LLM directory not found: $LLM_PATH${NC}"
    exit 1
fi

# Verify directory structure
echo "→ Checking LLM directory structure..."
if [ ! -f "$LLM_PATH/requirements.txt" ]; then
    echo -e "${RED}✗ requirements.txt not found${NC}"
    exit 1
fi

if [ ! -f "$LLM_PATH/src/api/main.py" ]; then
    echo -e "${RED}✗ src/api/main.py not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ LLM directory structure OK${NC}"
echo ""

# Create data directories
echo "→ Creating data directories..."
mkdir -p "${LLM_PATH}/data/successes"
mkdir -p "${LLM_PATH}/data/errors"
mkdir -p "${LLM_PATH}/data/nltk_data"
echo -e "${GREEN}✓ Data directories created${NC}"
echo ""

# Ensure network exists
echo "→ Ensuring Docker network exists..."
docker network create ${DOCKER_NETWORK} 2>/dev/null || echo "  (network already exists)"
echo ""
# =============================================================================
# OLLAMA SETUP
# =============================================================================

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                 SETTING UP OLLAMA                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

echo "→ Cleaning up old Ollama container..."
docker stop ${OLLAMA_CONTAINER} 2>/dev/null || true
docker rm ${OLLAMA_CONTAINER} 2>/dev/null || true
echo ""

echo "→ Pulling Ollama image..."
docker pull ollama/ollama:latest
echo ""

echo "→ Creating Ollama container..."
docker run -d --name ${OLLAMA_CONTAINER} \
    --network ${DOCKER_NETWORK} \
    -p ${OLLAMA_PORT}:11434 \
    -v ~/.ollama:/root/.ollama \
    --restart unless-stopped \
    -e OLLAMA_NUM_PARALLEL=${OLLAMA_NUM_PARALLEL} \
    -e OLLAMA_CONTEXT_LENGTH=${OLLAMA_CONTEXT_LENGTH} \
    ollama/ollama:latest

echo "→ Waiting for Ollama..."
sleep 5

if ! docker ps | grep -q "${OLLAMA_CONTAINER}"; then
    echo -e "${RED}✗ Ollama failed to start${NC}"
    docker logs ${OLLAMA_CONTAINER} --tail 50
    exit 1
fi

echo -e "${GREEN}✓ Ollama running${NC}"
echo ""

echo "→ Pulling model: llama3.2:3b"
docker exec ${OLLAMA_CONTAINER} ollama pull llama3.2:3b || true
echo -e "${GREEN}✓ Model ready${NC}"
echo ""
if ! docker ps | grep -q "${OLLAMA_CONTAINER}"; then
    echo -e "${RED}✗ Ollama failed to start${NC}"
    docker logs ${OLLAMA_CONTAINER} --tail 50
    exit 1
fi

echo -e "${GREEN}✓ Ollama running${NC}"
echo ""

echo "→ Pulling model: ${OLLAMA_MODEL}"
docker exec ${OLLAMA_CONTAINER} ollama pull ${OLLAMA_MODEL} || true
echo -e "${GREEN}✓ Model ready${NC}"
echo ""

# =============================================================================
# LLM BACKEND SETUP
# =============================================================================

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                 SETTING UP LLM BACKEND                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

echo "→ Cleaning up old LLM container..."
docker stop ${LLM_CONTAINER} 2>/dev/null || true
docker rm ${LLM_CONTAINER} 2>/dev/null || true
echo ""

echo "→ Creating LLM service container..."
echo "  - Using python:3.10-slim image"
echo "  - Installing build dependencies (gcc, g++)"
echo "  - Connecting to Ollama via container name: http://${OLLAMA_CONTAINER}:11434"
echo ""

docker run -d --name ${LLM_CONTAINER} \
    --network ${DOCKER_NETWORK} \
    -p ${LLM_PORT}:${LLM_PORT} \
    -v "${LLM_PATH}:/app" \
    --restart unless-stopped \
    -e PYTHONPATH=/app/src:/app \
    -e CUDA_VISIBLE_DEVICES="" \
    -e OLLAMA_BASE_URL="http://localhost:11434" \
    -e OLLAMA_MODEL="${OLLAMA_MODEL}" \
    -e NLTK_DATA=/app/data/nltk_data \
    python:3.10-slim \
    bash -c "
        apt-get update && apt-get install -y gcc g++ socat && \
        socat TCP-LISTEN:11434,fork,bind=127.0.0.1 TCP:${OLLAMA_CONTAINER}:11434 & \
        cd /app && \
        echo 'Installing packages...' && \
        pip install --quiet --break-system-packages -r /app/requirements.txt && \
        echo 'Downloading NLTK data...' && \
        python -c \"import nltk; nltk.download('stopwords'); nltk.download('punkt'); print('NLTK data ready')\" && \
        echo 'Starting FastAPI server...' && \
        exec python -m uvicorn src.api.main:app --host 0.0.0.0 --port ${LLM_PORT} --log-level info
    "
echo "→ Waiting for LLM service to start..."
echo "  (This may take 2-3 minutes for package installation)"
sleep 15

if ! docker ps | grep -q "${LLM_CONTAINER}"; then
    echo -e "${RED}✗ LLM service failed to start${NC}"
    echo ""
    echo "Container logs:"
    docker logs ${LLM_CONTAINER} --tail 100
    exit 1
fi

echo -e "${GREEN}✓ LLM service container running${NC}"
echo ""

# Wait for service to be fully ready
echo "→ Waiting for service to initialize..."
sleep 30

# Test services
echo "→ Testing services..."

if curl -s http://localhost:${LLM_PORT}/docs > /dev/null 2>&1; then
    echo -e "${GREEN}✓ LLM API accessible${NC}"
else
    echo -e "${YELLOW}⚠ LLM API still initializing (check logs: docker logs -f ${LLM_CONTAINER})${NC}"
fi

if curl -s http://localhost:${OLLAMA_PORT}/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ollama accessible${NC}"
else
    echo -e "${YELLOW}⚠ Ollama still initializing${NC}"
fi

# Summary
clear
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                   SETUP COMPLETE!                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}   LLM BACKEND + OLLAMA${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "   LLM Container: ${LLM_CONTAINER}"
echo "   LLM API: http://localhost:${LLM_PORT}"
echo "   Swagger: http://localhost:${LLM_PORT}/docs"
echo ""
echo "   Ollama Container: ${OLLAMA_CONTAINER}"
echo "   Ollama API: http://localhost:${OLLAMA_PORT}"
echo "   Model: ${OLLAMA_MODEL}"
echo "   Parallel: ${OLLAMA_NUM_PARALLEL}"
echo "   Context Length: ${OLLAMA_CONTEXT_LENGTH}"
echo ""
echo "   🔧 LLM connects to Ollama via Docker network:"
echo "      http://${OLLAMA_CONTAINER}:11434"
echo ""

echo "  ✓ From n8n (use container name):"
echo "    http://${LLM_CONTAINER}:${LLM_PORT}/summarize_batch"
echo ""

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}   USEFUL COMMANDS${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  LLM logs:      docker logs -f ${LLM_CONTAINER}"
echo "  Ollama logs:   docker logs -f ${OLLAMA_CONTAINER}"
echo "  Restart both:  docker restart ${OLLAMA_CONTAINER} ${LLM_CONTAINER}"
echo ""
echo "  Test LLM API:"
echo "    curl http://localhost:${LLM_PORT}/docs"
echo ""
echo "  Test Ollama:"
echo "    curl http://localhost:${OLLAMA_PORT}/api/tags"
echo ""
echo -e "${GREEN}✓ Setup complete!${NC}"
echo ""