#!/bin/bash

# Dashboard Setup Script - Fixed for actual directory structure

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              DASHBOARD SETUP (FIXED)                       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Configuration
BASE_DIR="$HOME/SWP-News-Summary"
FRONTEND_DIR="$BASE_DIR/frontend/frontend"  # Note: nested frontend/frontend
DASHBOARD_DIR="$FRONTEND_DIR/dashboard"
DASHBOARD_PORT="8501"
CONTAINER_NAME="dashboard"
OLD_CONTAINER_NAME="streamlit-frontend"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running${NC}"
    echo "  Please start Docker Desktop and try again"
    exit 1
fi

echo -e "${GREEN}✓ Docker is running${NC}"
echo ""

# Check for old containers
echo -e "${YELLOW}→ Checking for existing containers...${NC}"
OLD_CONTAINERS=$(docker ps -a --filter "publish=${DASHBOARD_PORT}" --format "{{.Names}}")

if [ ! -z "$OLD_CONTAINERS" ]; then
    echo -e "${YELLOW}⚠ Found containers using port ${DASHBOARD_PORT}:${NC}"
    echo "$OLD_CONTAINERS"
    echo ""
    echo "Stopping and removing old containers..."
    for container in $OLD_CONTAINERS; do
        docker stop "$container" 2>/dev/null || true
        docker rm "$container" 2>/dev/null || true
    done
    echo -e "${GREEN}✓ Old containers removed${NC}"
fi

echo ""

# Verify directory structure
if [ ! -d "$FRONTEND_DIR" ]; then
    echo -e "${RED}✗ Frontend directory not found: $FRONTEND_DIR${NC}"
    exit 1
fi

if [ ! -d "$DASHBOARD_DIR" ]; then
    echo -e "${RED}✗ Dashboard directory not found: $DASHBOARD_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found dashboard directory${NC}"
echo -e "${CYAN}ℹ Dashboard path: $DASHBOARD_DIR${NC}"
echo ""

# Check for app.py
if [ ! -f "$DASHBOARD_DIR/app.py" ]; then
    echo -e "${RED}✗ app.py not found in dashboard directory${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Found app.py${NC}"
echo ""

# Create Dockerfile if it doesn't exist
echo -e "${YELLOW}→ Creating Dockerfile...${NC}"
cat > "$DASHBOARD_DIR/Dockerfile" << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run Streamlit
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
EOF

echo -e "${GREEN}✓ Dockerfile created${NC}"
echo ""

# Create requirements.txt if it doesn't exist
if [ ! -f "$DASHBOARD_DIR/requirements.txt" ]; then
    echo -e "${YELLOW}→ Creating requirements.txt...${NC}"
    cat > "$DASHBOARD_DIR/requirements.txt" << 'EOF'
streamlit>=1.28.0
opensearch-py>=2.3.0
pandas>=2.0.0
plotly>=5.17.0
python-dotenv>=1.0.0
requests>=2.31.0
EOF
    echo -e "${GREEN}✓ requirements.txt created${NC}"
else
    echo -e "${GREEN}✓ requirements.txt already exists${NC}"
fi

echo ""

# Create docker-compose.yml (FIXED - removed depends_on)
echo -e "${YELLOW}→ Creating docker-compose.yml...${NC}"
cat > "$FRONTEND_DIR/docker-compose.yml" << EOF
services:
  dashboard:
    build:
      context: ./dashboard
      dockerfile: Dockerfile
    container_name: ${CONTAINER_NAME}
    ports:
      - "${DASHBOARD_PORT}:8501"
    volumes:
      - ./dashboard:/app
    environment:
      - OPENSEARCH_USER=admin
      - OPENSEARCH_PASS=admin
      - OPENSEARCH_HOST=opensearch
      - OPENSEARCH_PORT=9200
    networks:
      - opensearch_internal_net
      - n8n-network
    restart: unless-stopped

networks:
  opensearch_internal_net:
    external: true
  n8n-network:
    external: true
EOF

echo -e "${GREEN}✓ docker-compose.yml created${NC}"
echo ""

# Check if required networks exist
echo -e "${YELLOW}→ Checking for required Docker networks...${NC}"
MISSING_NETWORKS=()

if ! docker network ls | grep -q "opensearch_internal_net"; then
    MISSING_NETWORKS+=("opensearch_internal_net")
fi

if ! docker network ls | grep -q "n8n-network"; then
    MISSING_NETWORKS+=("n8n-network")
fi

if [ ${#MISSING_NETWORKS[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠ Missing required networks:${NC}"
    for network in "${MISSING_NETWORKS[@]}"; do
        echo "  - $network"
    done
    echo ""
    echo "Creating missing networks..."
    for network in "${MISSING_NETWORKS[@]}"; do
        docker network create "$network"
    done
    echo -e "${GREEN}✓ Networks created${NC}"
fi

echo -e "${GREEN}✓ All required networks exist${NC}"
echo ""

# Clean up existing containers
cd "$FRONTEND_DIR"
echo -e "${YELLOW}→ Cleaning up existing containers...${NC}"
if command -v docker-compose &> /dev/null; then
    docker-compose down --remove-orphans 2>/dev/null || true
else
    docker compose down --remove-orphans 2>/dev/null || true
fi

echo ""
echo -e "${YELLOW}→ Building and starting dashboard...${NC}"
echo "  This may take 2-5 minutes on first run..."
echo ""

# Build and start
if command -v docker-compose &> /dev/null; then
    docker-compose build --no-cache 2>&1 | grep -v "WARN"
    docker-compose up -d 2>&1 | grep -v "WARN"
else
    docker compose build --no-cache 2>&1 | grep -v "WARN"
    docker compose up -d 2>&1 | grep -v "WARN"
fi

if [ $? -ne 0 ]; then
    echo -e "${RED}✗ Docker compose failed${NC}"
    echo ""
    echo -e "${YELLOW}→ Checking logs...${NC}"
    if command -v docker-compose &> /dev/null; then
        docker-compose logs
    else
        docker compose logs
    fi
    exit 1
fi

echo -e "${GREEN}✓ Dashboard container started${NC}"
echo ""

# Wait for service
echo -e "${YELLOW}→ Waiting for dashboard to initialize...${NC}"
sleep 10

# Check container status
echo ""
echo -e "${YELLOW}→ Container status:${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "NAME|${CONTAINER_NAME}"
echo ""

# Check Dashboard
echo -e "${YELLOW}→ Verifying Dashboard...${NC}"
for i in {1..20}; do
    if curl -s http://localhost:${DASHBOARD_PORT}/_stcore/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Dashboard is ready!${NC}"
        break
    fi
    if [ $i -eq 20 ]; then
        echo -e "${YELLOW}⚠ Dashboard health check timed out${NC}"
        echo ""
        echo -e "${YELLOW}→ Recent logs:${NC}"
        if command -v docker-compose &> /dev/null; then
            docker-compose logs --tail 50 dashboard
        else
            docker compose logs --tail 50 dashboard
        fi
        echo ""
        echo -e "${CYAN}You can still try accessing: http://localhost:${DASHBOARD_PORT}${NC}"
    fi
    echo -n "."
    sleep 3
done

echo ""
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                    SETUP COMPLETE                          ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}Dashboard URL:  http://localhost:${DASHBOARD_PORT}${NC}"
echo ""
echo "Project paths:"
echo "  Frontend:   $FRONTEND_DIR"
echo "  Dashboard:  $DASHBOARD_DIR"
echo ""
echo "Useful commands:"
echo "  cd $FRONTEND_DIR"
if command -v docker-compose &> /dev/null; then
    echo "  docker-compose logs -f dashboard    # View logs"
    echo "  docker-compose restart dashboard    # Restart"
    echo "  docker-compose down                 # Stop"
    echo "  docker-compose up -d --build        # Rebuild"
else
    echo "  docker compose logs -f dashboard    # View logs"
    echo "  docker compose restart dashboard    # Restart"
    echo "  docker compose down                 # Stop"
    echo "  docker compose up -d --build        # Rebuild"
fi
echo ""