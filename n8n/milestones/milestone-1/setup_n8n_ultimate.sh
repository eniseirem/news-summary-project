#!/bin/bash

# n8n + LLM Setup - FIXED VERSION with OPTIONS
# Choose what to setup: n8n only, LLM only, or both

set -e

# Load configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/config.sh"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

clear
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║     🚀 N8N + PYTORCH - SETUP WITH OPTIONS 🚀              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "📂 Base directory: ${BASE_DIR}"
echo ""

CONTAINER_NAME="${N8N_CONTAINER}"

# Ask what to setup
echo "What would you like to setup?"
echo ""
echo "  1) n8n only (with crawler)"
echo "  2) LLM service only"
echo "  3) Both n8n and LLM (full setup)"
echo ""
read -p "Choose option (1-3) [default: 3]: " SETUP_CHOICE
SETUP_CHOICE=${SETUP_CHOICE:-3}
echo ""

case $SETUP_CHOICE in
    1)
        SETUP_N8N=true
        SETUP_LLM=false
        echo "📋 Will setup: n8n + crawler only"
        ;;
    2)
        SETUP_N8N=false
        SETUP_LLM=true
        echo "📋 Will setup: LLM service only"
        ;;
    3)
        SETUP_N8N=true
        SETUP_LLM=true
        echo "📋 Will setup: Both n8n and LLM"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
read -p "Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 0
fi
echo ""

# =============================================================================
# N8N SETUP
# =============================================================================

if [ "$SETUP_N8N" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║              📦 SETTING UP N8N                             ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # Clean up n8n
    echo "🧹 Cleaning up old n8n container..."
    docker stop $CONTAINER_NAME 2>/dev/null || true
    docker rm $CONTAINER_NAME 2>/dev/null || true
    echo ""

    echo "📥 Pulling n8n image..."
    IMAGE="n8nio/n8n:latest"
    docker pull $IMAGE

    echo ""
    echo "🐳 Creating n8n container..."
    docker run -d --name $CONTAINER_NAME \
        -p 5678:5678 \
        -v ~/.n8n:/home/node/.n8n \
        -v "${CRAWLER_PATH}:/crawler:rw" \
        -v "${LLM_PATH}:/llm:rw" \
        -v "${DASH_PATH}:/dashboard:rw" \
        -e GENERIC_TIMEZONE=Europe/Berlin \
        --restart unless-stopped \
        $IMAGE

    echo "⏳ Waiting for n8n..."
    sleep 8

    if ! docker ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${RED}✗ n8n container failed to start${NC}"
        docker logs $CONTAINER_NAME --tail 30
        exit 1
    fi

    echo -e "${GREEN}✓ n8n running${NC}"
    echo ""

    # Setup crawler in n8n
    echo "📦 Setting up crawler in n8n container..."
    docker exec -u root $CONTAINER_NAME apk update > /dev/null
    docker exec -u root $CONTAINER_NAME apk add --no-cache python3 py3-pip py3-virtualenv gcc musl-dev python3-dev > /dev/null
    docker exec $CONTAINER_NAME python3 -m virtualenv /home/node/crawler-venv
    docker exec $CONTAINER_NAME /home/node/crawler-venv/bin/pip install --quiet \
        requests beautifulsoup4 feedparser newspaper4k lxml lxml-html-clean
    echo -e "${GREEN}✓ Crawler setup complete${NC}"
    echo ""

    # Connect to network if exists
    if docker network inspect n8n-network > /dev/null 2>&1; then
        echo "🔗 Connecting n8n to network..."
        docker network connect n8n-network n8n 2>/dev/null || echo "  (already connected)"
    fi
fi

# =============================================================================
# LLM SETUP
# =============================================================================

if [ "$SETUP_LLM" = true ]; then
    echo ""
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║              🤖 SETTING UP LLM SERVICE                     ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo ""

    # Clean up LLM
    echo "🧹 Cleaning up old LLM container..."
    docker stop llm-service 2>/dev/null || true
    docker rm llm-service 2>/dev/null || true
    echo ""

    # Create data directories in LLM project
    echo "📁 Creating LLM data directories..."
    mkdir -p "${LLM_PATH}/data/successes"
    mkdir -p "${LLM_PATH}/data/errors"
    echo -e "${GREEN}✓ Data directories created${NC}"
    echo ""

    echo "🤖 Creating separate LLM container..."
    echo "⏳ This will take 5-10 minutes (downloading PyTorch ~2GB + BART model ~1.6GB)..."
    echo ""

    docker run -d --name llm-service \
        -p 8001:8001 \
        -v "${LLM_PATH}:/app" \
        --restart unless-stopped \
        -e PYTHONPATH=/app/src:/app \
        -e CUDA_VISIBLE_DEVICES="" \
        python:3.10-slim \
        bash -c "
            cd /app
            echo 'Installing packages...'
            pip install --quiet torch transformers==4.35.0 fastapi uvicorn requests pydantic python-dotenv beautifulsoup4 langdetect regex sentencepiece protobuf
            echo 'Pre-downloading BART model (1.6GB)...'
            python -c 'from transformers import pipeline; pipeline(\"summarization\", model=\"facebook/bart-large-cnn\", device=-1)'
            echo 'Model downloaded! Starting server...'
            exec uvicorn src.api.main:app --host 0.0.0.0 --port 8001 --log-level info
        "

    echo -e "${GREEN}✓ LLM container created (downloading in background)${NC}"
    echo "⏳ Model download will take 5-10 minutes..."
    echo "   Watch progress: docker logs -f llm-service"
    echo ""
fi

# =============================================================================
# NETWORK SETUP
# =============================================================================

if [ "$SETUP_N8N" = true ] && [ "$SETUP_LLM" = true ]; then
    echo "🔗 Creating Docker network..."
    docker network create n8n-network 2>/dev/null || echo "  (network already exists)"
    docker network connect n8n-network n8n 2>/dev/null || echo "  (n8n already connected)"
    docker network connect n8n-network llm-service 2>/dev/null || echo "  (llm-service already connected)"
    echo -e "${GREEN}✓ Network configured${NC}"
    echo ""
fi

# =============================================================================
# COMPLETION SUMMARY
# =============================================================================

clear
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              ✅ SETUP COMPLETE! ✅                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

if [ "$SETUP_N8N" = true ]; then
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  📦 N8N SETUP${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "  🐳 Container: $CONTAINER_NAME"
    echo "  🌐 n8n UI: http://localhost:5678"
    echo ""
    echo "  🕷️  Crawler Command in n8n:"
    echo "    Command: /home/node/crawler-venv/bin/python"
    echo "    Arguments: /crawler/main.py"
    echo "    OR: sh -c \"export PYTHONPATH=/crawler && /home/node/crawler-venv/bin/python /crawler/main.py\""
    echo ""
fi

if [ "$SETUP_LLM" = true ]; then
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  🤖 LLM SERVICE SETUP${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "  🐳 Container: llm-service"
    echo "  📡 LLM API: http://localhost:8001"
    echo ""
    echo "  In n8n HTTP Request node:"
    echo "    URL: http://host.docker.internal:8001/summarize_batch"
    if [ "$SETUP_N8N" = true ]; then
        echo "    OR:  http://llm-service:8001/summarize_batch (via network)"
    fi
    echo "    Method: POST"
    echo "    Body: See documentation"
    echo ""
    echo "  Test LLM:"
    echo "    curl http://localhost:8001/docs"
    echo ""
    echo "  📁 Data directories:"
    echo "    Success logs: ${LLM_PATH}/data/successes/"
    echo "    Error logs:   ${LLM_PATH}/data/errors/"
    echo ""
    echo "  💡 LLM service is still downloading packages and model."
    echo "     Wait 5-10 minutes, then check: docker logs -f llm-service"
    echo ""
fi

echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${CYAN}  📋 USEFUL COMMANDS${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
if [ "$SETUP_N8N" = true ]; then
    echo "  Start n8n:     docker start n8n"
    echo "  Stop n8n:      docker stop n8n"
    echo "  n8n logs:      docker logs -f n8n"
    echo ""
fi
if [ "$SETUP_LLM" = true ]; then
    echo "  Start LLM:     docker start llm-service"
    echo "  Stop LLM:      docker stop llm-service"
    echo "  LLM logs:      docker logs -f llm-service"
    echo ""
fi
if [ "$SETUP_N8N" = true ] && [ "$SETUP_LLM" = true ]; then
    echo "  Start both:    ./start_all.sh"
    echo "  Stop both:     ./stop_all.sh"
    echo ""
fi
echo -e "${GREEN}✨ Setup complete! ✨${NC}"
echo ""