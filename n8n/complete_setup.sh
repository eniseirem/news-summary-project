#!/bin/bash

# SWP News Summary - Master Setup Script (Fixed)
# Compatible with bash 3.x and above

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# =============================================================================
# CONFIGURATION
# =============================================================================

REPO_URL="https://gitlab.fokus.fraunhofer.de/dana/cswspws25.git"
BASE_DIR="$HOME/SWP-News-Summary"

# Branch configuration
BRANCH_OPENSEARCH="Opensearch"
BRANCH_N8N="n8n-pipeline"
BRANCH_CRAWLER="WebCrawlerMain"
BRANCH_LLM="m3-final"
BRANCH_DASHBOARD="frontend/dashboard-ui"

# Directory configuration
DIR_OPENSEARCH="$BASE_DIR/opensearch"
DIR_N8N="$BASE_DIR/n8n"
DIR_CRAWLER="$BASE_DIR/cswspws25-WebCrawlerMain"
DIR_LLM="$BASE_DIR/cswspws25-m3-final"
DIR_DASHBOARD="$BASE_DIR/frontend"

# Setup script locations (ALL in n8n/docker/)
SETUP_N8N="$DIR_N8N/docker/n8n/setup_n8n.sh"
SETUP_LLM="$DIR_N8N/docker/llm-service/setup-llm-service.sh"
SETUP_CRAWLER="$DIR_N8N/docker/crawler/setup-crawler-service.sh"
SETUP_DASHBOARD="$DIR_N8N/docker/streamlit-frontend/setup-frontend-service.sh"

# Docker networks
OPENSEARCH_NETWORK="opensearch_internal_net"
N8N_NETWORK="n8n-network"

# Container names
OPENSEARCH_CONTAINER="opensearch"
OPENSEARCH_DASHBOARD_CONTAINER="opensearch-dashboards"
OPENSEARCH_API_CONTAINER="opensearch-python-api"
N8N_CONTAINER="n8n"
OLLAMA_CONTAINER="ollama"
LLM_CONTAINER="llm-service"
CRAWLER_CONTAINER="crawler-api"
DASHBOARD_CONTAINER="dashboard"

# Ports
OPENSEARCH_PORT="9200"
OPENSEARCH_DASHBOARD_PORT="5601"
OPENSEARCH_API_PORT="8002"
N8N_PORT="5678"
OLLAMA_PORT="11434"
LLM_PORT="8001"
CRAWLER_PORT="8003"
DASHBOARD_PORT="8501"

# Other settings
TIMEZONE="Europe/Berlin"
OLLAMA_MODEL="llama3.2:3b"
OLLAMA_NUM_PARALLEL="2"
OLLAMA_CONTEXT_LENGTH="8192"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

print_header() {
    clear
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║       SWP NEWS SUMMARY - COMPLETE SYSTEM SETUP               ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    echo -e "${CYAN}Repository:${NC} ${REPO_URL}"
    echo -e "${CYAN}Base Directory:${NC} ${BASE_DIR}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}${CYAN}  $1${NC}"
    echo -e "${BOLD}${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_step() {
    echo -e "${BLUE}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${CYAN}ℹ${NC} $1"
}

# =============================================================================
# PREREQUISITE CHECKS
# =============================================================================

check_prerequisites() {
    print_section "CHECKING PREREQUISITES"
    
    local all_good=true
    
    # Check bash version
    print_step "Checking bash version..."
    bash_version=$(bash --version | head -n1 | grep -oE '[0-9]+\.[0-9]+' | head -n1)
    print_success "Bash version: $bash_version"
    
    # Check Docker
    print_step "Checking Docker..."
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        echo "       Install from: https://docs.docker.com/get-docker/"
        all_good=false
    else
        docker_version=$(docker --version | cut -d' ' -f3 | tr -d ',')
        print_success "Docker installed ($docker_version)"
    fi
    
    # Check Docker daemon
    if command -v docker &> /dev/null; then
        print_step "Checking Docker daemon..."
        if ! docker info &> /dev/null; then
            print_error "Docker daemon is not running"
            echo "       Please start Docker Desktop or Docker service"
            all_good=false
        else
            print_success "Docker daemon is running"
        fi
    fi
    
    # Check Docker Compose
    print_step "Checking Docker Compose..."
    if command -v docker-compose &> /dev/null; then
        compose_version=$(docker-compose --version | cut -d' ' -f3 | tr -d ',')
        print_success "Docker Compose installed ($compose_version)"
    elif docker compose version &> /dev/null 2>&1; then
        print_success "Docker Compose (plugin) installed"
    else
        print_error "Docker Compose is not installed"
        echo "       Required for OpenSearch and Dashboard setup"
        all_good=false
    fi
    
    # Check Git
    print_step "Checking Git..."
    if ! command -v git &> /dev/null; then
        print_error "Git is not installed"
        all_good=false
    else
        git_version=$(git --version | cut -d' ' -f3)
        print_success "Git installed ($git_version)"
    fi
    
    echo ""
    
    if [ "$all_good" = false ]; then
        print_error "Prerequisites check failed. Please install missing components."
        exit 1
    fi
    
    print_success "All prerequisites satisfied!"
    echo ""
}

# =============================================================================
# CONFIG FILE GENERATION
# =============================================================================

create_config_files() {
    print_section "CREATING CONFIGURATION FILES"
    
    # Create config.sh for LLM service
    local llm_config_dir="$DIR_N8N/docker/llm-service"
    
    if [ ! -d "$llm_config_dir" ]; then
        mkdir -p "$llm_config_dir"
    fi
    
    print_step "Creating LLM config: $llm_config_dir/config.sh"
    cat > "$llm_config_dir/config.sh" << 'EOF'
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
EOF
    chmod +x "$llm_config_dir/config.sh"
    print_success "LLM config created"
    
    # Create config_m2.sh for n8n
    local n8n_config_dir="$DIR_N8N/docker/n8n"
    
    if [ ! -d "$n8n_config_dir" ]; then
        mkdir -p "$n8n_config_dir"
    fi
    
    print_step "Creating n8n config: $n8n_config_dir/config_m2.sh"
    cat > "$n8n_config_dir/config_m2.sh" << 'EOF'
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
EOF
    chmod +x "$n8n_config_dir/config_m2.sh"
    print_success "n8n config created"
    
    echo ""
}
# =============================================================================
# CREATE RESTORE INDICES SCRIPT
# =============================================================================

create_restore_indices_script() {
    local opensearch_scripts_dir="$DIR_OPENSEARCH/scripts"
    
    if [ ! -d "$opensearch_scripts_dir" ]; then
        mkdir -p "$opensearch_scripts_dir"
    fi
    
    print_step "Creating restore_indices.sh script..."
    
    cat > "$opensearch_scripts_dir/restore_indices.sh" << 'EOF'
#!/bin/bash

set -e

OPENSEARCH_URL="https://localhost:9200"
OPENSEARCH_USER="admin"
OPENSEARCH_PASS="admin"

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Indices directory is one level up from scripts, then into indices
INDICES_DIR="$SCRIPT_DIR/../indices"

echo "Waiting for OpenSearch..."

# Wait for OpenSearch
while ! curl -k -s -u ${OPENSEARCH_USER}:${OPENSEARCH_PASS} ${OPENSEARCH_URL} >/dev/null 2>&1; do
    sleep 2
done

echo "OpenSearch is up."
echo ""

# Check if indices directory exists
if [ ! -d "$INDICES_DIR" ]; then
    echo "Error: Indices directory not found: $INDICES_DIR"
    echo "Expected path: $INDICES_DIR"
    exit 1
fi

echo "Using indices directory: $INDICES_DIR"
echo ""

# Process each JSON file
for json_file in "$INDICES_DIR"/*.json; do
    if [ -f "$json_file" ]; then
        # Extract index name from filename (without .json extension)
        index_name=$(basename "$json_file" .json)
        
        echo "Creating index: $index_name"
        
        # Read the JSON file
        index_def=$(cat "$json_file")
        
        # Check if it has the wrapper format: { "index_name": { "mappings": ... } }
        # or direct format: { "mappings": ... }
        if echo "$index_def" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if 'mappings' in data else 1)" 2>/dev/null; then
            # Direct format - use as is
            echo "  → Using direct format"
        else
            # Wrapper format - extract inner content
            echo "  → Extracting from wrapper format"
            index_def=$(echo "$index_def" | python3 -c "import sys, json; data=json.load(sys.stdin); print(json.dumps(list(data.values())[0]))" 2>/dev/null)
            
            if [ -z "$index_def" ]; then
                # If python extraction fails, try jq
                index_def=$(cat "$json_file" | jq -c '.[]' 2>/dev/null)
            fi
        fi
        
        if [ -z "$index_def" ]; then
            echo "  ✗ Could not extract index definition"
            continue
        fi
        
        # Create the index
        response=$(curl -k -s -w "\n%{http_code}" -u ${OPENSEARCH_USER}:${OPENSEARCH_PASS} \
            -X PUT "${OPENSEARCH_URL}/${index_name}" \
            -H "Content-Type: application/json" \
            -d "$index_def")
        
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | sed '$d')
        
        if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then
            echo "  ✓ Created successfully"
        elif [ "$http_code" = "400" ]; then
            if echo "$body" | grep -q "resource_already_exists_exception"; then
                echo "  ⚠ Already exists"
            else
                echo "  ✗ Error creating index"
                echo "  Response: $body" | head -c 200
            fi
        else
            echo "  ✗ HTTP $http_code"
            echo "  Response: $body" | head -c 200
        fi
        
        echo ""
    fi
done

echo "All indices processed."
echo ""
echo "Current indices:"
curl -k -s -u ${OPENSEARCH_USER}:${OPENSEARCH_PASS} "${OPENSEARCH_URL}/_cat/indices?v" | grep -v "^\."
EOF

    chmod +x "$opensearch_scripts_dir/restore_indices.sh"
    print_success "restore_indices.sh created"
}

# =============================================================================
# UPDATE EXISTING REPOSITORY
# =============================================================================

update_repository() {
    local service_name=$1
    local service_dir=$2
    local branch=$3
    
    print_section "UPDATING $service_name"
    
    if [ ! -d "$service_dir" ]; then
        print_warning "Directory not found: $service_dir"
        return 1
    fi
    
    cd "$service_dir" || return 1
    
    # Check if it's a git repository
    if [ ! -d ".git" ]; then
        print_warning "Not a git repository: $service_dir"
        print_info "Skipping update"
        return 0
    fi
    
    print_info "Repository: $service_dir"
    
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null || [ -n "$(git ls-files --others --exclude-standard)" ]; then
        echo ""
        print_warning "Git repository has local changes or untracked files"
        echo ""
        echo -e "${YELLOW}Options:${NC}"
        echo -e "  ${CYAN}1)${NC} Discard all changes and pull latest (RECOMMENDED)"
        echo -e "  ${CYAN}2)${NC} Stash changes and pull latest"
        echo -e "  ${CYAN}3)${NC} Keep current files and skip git update"
        echo -e "  ${CYAN}4)${NC} Exit and handle manually"
        echo ""
        read -p "Choose option [1-4]: " -n 1 -r
        echo
        
        case $REPLY in
            1)
                print_step "Discarding all local changes..."
                git reset --hard
                git clean -fd
                
                local current_branch=$(git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD)
                if [ "$current_branch" != "$branch" ]; then
                    print_step "Switching to $branch branch..."
                    git fetch origin
                    git checkout "$branch"
                    git reset --hard origin/"$branch"
                else
                    print_step "Pulling latest changes..."
                    git fetch origin
                    git reset --hard origin/"$branch"
                fi
                print_success "Repository updated"
                ;;
            2)
                print_step "Stashing local changes..."
                git stash save "Auto-stash by setup script $(date)"
                
                local current_branch=$(git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD)
                if [ "$current_branch" != "$branch" ]; then
                    print_step "Switching to $branch branch..."
                    git fetch origin
                    git checkout "$branch"
                    git pull origin "$branch"
                else
                    print_step "Pulling latest changes..."
                    git pull origin "$branch"
                fi
                print_success "Repository updated (changes stashed)"
                print_info "To restore stashed changes: git stash pop"
                ;;
            3)
                print_info "Using existing files without git update"
                ;;
            4)
                print_info "Exiting. You can manually handle git changes with:"
                echo "  cd $service_dir"
                echo "  git stash  # or git reset --hard"
                echo "  git checkout $branch"
                echo "  git pull"
                exit 0
                ;;
            *)
                print_error "Invalid option"
                exit 1
                ;;
        esac
    else
        # No local changes
        print_step "No local changes detected"
        echo ""
        read -p "Pull latest changes from git? [Y/n]: " -n 1 -r
        echo
        
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            local current_branch=$(git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD)
            if [ "$current_branch" != "$branch" ]; then
                print_step "Switching to $branch branch..."
                git fetch origin
                git checkout "$branch"
                git pull origin "$branch"
            else
                print_step "Pulling latest changes..."
                git pull origin "$branch"
            fi
            print_success "Repository updated"
        else
            print_info "Using existing directory without updates"
        fi
    fi
    
    echo ""
    cd "$BASE_DIR"
    return 0
}

# =============================================================================
# REPOSITORY SETUP
# =============================================================================

clone_branch() {
    local service=$1
    local branch=$2
    local target_dir=$3
    
    print_step "Cloning ${service} (branch: ${branch})..."
    
    if [ -d "$target_dir" ]; then
        print_warning "Directory exists: ${target_dir}"
        return 0
    fi
    
    # Clone
    if git clone --single-branch --branch "$branch" "$REPO_URL" "$target_dir" 2>&1 | tail -n 2; then
        print_success "${service} cloned successfully"
        return 0
    else
        print_error "Failed to clone ${service}"
        return 1
    fi
}

setup_repositories() {
    print_section "STEP 1: REPOSITORY SETUP"
    
    # Check if base directory exists
    if [ -d "$BASE_DIR" ]; then
        print_warning "Base directory already exists: ${BASE_DIR}"
        echo ""
        echo -e "${YELLOW}Choose an option:${NC}"
        echo -e "  ${CYAN}1)${NC} Delete and re-clone everything (fresh start)"
        echo -e "  ${CYAN}2)${NC} Update existing repositories (pull latest)"
        echo -e "  ${CYAN}3)${NC} Use existing without updates"
        echo -e "  ${CYAN}4)${NC} Exit setup"
        echo ""
        read -p "Enter choice [1-4]: " choice
        
        case $choice in
            1)
                print_step "Removing existing directory..."
                rm -rf "$BASE_DIR"
                print_success "Directory removed"
                # Will proceed to clone below
                ;;
            2)
                print_info "Updating existing repositories..."
                echo ""
                
                # Update each repository
                update_repository "OpenSearch" "$DIR_OPENSEARCH" "$BRANCH_OPENSEARCH"
                update_repository "n8n" "$DIR_N8N" "$BRANCH_N8N"
                update_repository "Crawler" "$DIR_CRAWLER" "$BRANCH_CRAWLER"
                update_repository "LLM" "$DIR_LLM" "$BRANCH_LLM"
                update_repository "Dashboard" "$DIR_DASHBOARD" "$BRANCH_DASHBOARD"
                
                # Create config files
                create_config_files
                
                # Create restore indices script
                create_restore_indices_script
                
                return 0
                ;;
            3)
                print_info "Using existing directories without updates"
                echo ""
                # Still create config files
                create_config_files
                
                # Create restore indices script
                create_restore_indices_script
                
                return 0
                ;;
            4)
                print_info "Setup cancelled by user"
                exit 0
                ;;
            *)
                print_error "Invalid choice"
                exit 1
                ;;
        esac
    fi
    
    # Create base directory
    mkdir -p "$BASE_DIR"
    print_success "Created base directory: ${BASE_DIR}"
    echo ""
    
    # Clone all branches
    local failed=0
    
    clone_branch "opensearch" "$BRANCH_OPENSEARCH" "$DIR_OPENSEARCH" || failed=1
    clone_branch "n8n" "$BRANCH_N8N" "$DIR_N8N" || failed=1
    clone_branch "crawler" "$BRANCH_CRAWLER" "$DIR_CRAWLER" || failed=1
    clone_branch "llm" "$BRANCH_LLM" "$DIR_LLM" || failed=1
    clone_branch "dashboard" "$BRANCH_DASHBOARD" "$DIR_DASHBOARD" || failed=1
    
    echo ""
    
    if [ $failed -eq 1 ]; then
        print_error "Some repositories failed to clone"
        exit 1
    fi
    
    print_success "All branches cloned successfully!"
    echo ""
    
    # Create config files after cloning
    create_config_files
    
    # Create restore indices script
    create_restore_indices_script
    
    # Show directory structure
    print_info "Directory structure:"
    echo ""
    ls -la "$BASE_DIR"
    echo ""
}

# =============================================================================
# NETWORK SETUP
# =============================================================================

setup_networks() {
    print_section "DOCKER NETWORK SETUP"
    
    # Create OpenSearch network
    print_step "Creating network: ${OPENSEARCH_NETWORK}"
    if docker network inspect "$OPENSEARCH_NETWORK" >/dev/null 2>&1; then
        print_warning "Network already exists"
    else
        docker network create "$OPENSEARCH_NETWORK" >/dev/null
        print_success "Network created"
    fi
    
    # Create n8n network
    print_step "Creating network: ${N8N_NETWORK}"
    if docker network inspect "$N8N_NETWORK" >/dev/null 2>&1; then
        print_warning "Network already exists"
    else
        docker network create "$N8N_NETWORK" >/dev/null
        print_success "Network created"
    fi
    
    echo ""
    print_success "Network setup complete!"
    echo ""
}

# =============================================================================
# OPENSEARCH SETUP
# =============================================================================

setup_opensearch() {
    print_section "SETTING UP OPENSEARCH"
    
    # Check if already running
    if docker ps | grep -q "$OPENSEARCH_CONTAINER"; then
        print_success "OpenSearch is already running"
        
        # Check if indices exist, if not create them
        print_step "Checking for OpenSearch indices..."
        if curl -k -s -u admin:admin https://localhost:$OPENSEARCH_PORT/_cat/indices 2>/dev/null | grep -q "articles\|clusters"; then
            print_success "OpenSearch indices already exist"
        else
            print_warning "Indices not found, running restoration script..."
            cd "$DIR_OPENSEARCH"
            if [ -d "scripts" ]; then
                cd scripts
                if [ -f "restore_indices.sh" ]; then
                    print_step "Running restore_indices.sh..."
                    chmod +x restore_indices.sh
                    bash restore_indices.sh || print_warning "Index restoration had issues"
                elif [ -f "restore_indices.cmd" ]; then
                    print_step "Running restore_indices.cmd..."
                    bash restore_indices.cmd 2>/dev/null || sh restore_indices.cmd 2>/dev/null || print_warning "Could not run script automatically"
                else
                    print_warning "No restore script found in scripts/"
                fi
                cd "$BASE_DIR"
            else
                print_warning "No scripts/ directory found"
            fi
        fi
        
        echo ""
        print_info "Access points:"
        echo "  • OpenSearch: https://localhost:$OPENSEARCH_PORT"
        echo "  • Dashboards: http://localhost:$OPENSEARCH_DASHBOARD_PORT"
        echo "  • API Docs: http://localhost:$OPENSEARCH_API_PORT/docs"
        echo ""
        return 0
    fi
    
    if [ ! -d "$DIR_OPENSEARCH" ]; then
        print_error "OpenSearch directory not found: $DIR_OPENSEARCH"
        return 1
    fi
    
    cd "$DIR_OPENSEARCH" || return 1
    print_info "Working directory: $(pwd)"
    echo ""
    
    # Clean start
    print_step "Cleaning up any stopped containers..."
    if command -v docker-compose &> /dev/null; then
        docker-compose down -v --remove-orphans 2>/dev/null || true
    else
        docker compose down -v --remove-orphans 2>/dev/null || true
    fi
    
    # Check for docker-compose.yml
    if [ ! -f "docker-compose.yml" ]; then
        print_error "docker-compose.yml not found in $DIR_OPENSEARCH"
        return 1
    fi
    
    print_step "Starting OpenSearch services with docker-compose..."
    print_info "This may take 1-3 minutes..."
    echo ""
    
    # Start services
    if command -v docker-compose &> /dev/null; then
        docker-compose up -d
    else
        docker compose up -d
    fi
    
    echo ""
    print_success "Docker Compose started"
    echo ""
    
    # Wait for OpenSearch to be ready
    print_step "Waiting for OpenSearch to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -k -s -u admin:admin https://localhost:$OPENSEARCH_PORT >/dev/null 2>&1; then
            echo ""
            print_success "OpenSearch is ready!"
            break
        fi
        attempt=$((attempt + 1))
        echo -n "."
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        echo ""
        print_warning "OpenSearch health check timed out, but continuing..."
    fi
    
    echo ""
    
    # NEW: Create indices after OpenSearch is ready
    print_step "Setting up OpenSearch indices..."
    if [ -d "scripts" ]; then
        cd scripts
        if [ -f "restore_indices.sh" ]; then
            print_info "Running restore_indices.sh..."
            chmod +x restore_indices.sh
            bash restore_indices.sh || print_warning "Index restoration had issues"
        elif [ -f "restore_indices.cmd" ]; then
            print_info "Running restore_indices.cmd..."
            bash restore_indices.cmd 2>/dev/null || sh restore_indices.cmd 2>/dev/null || print_warning "Could not run script automatically"
        else
            print_warning "No index restoration script found in scripts/"
            print_info "You may need to manually create indices"
        fi
        cd "$DIR_OPENSEARCH"
    else
        print_warning "No scripts/ directory found"
    fi
    
    echo ""
    print_info "Verifying indices..."
    curl -k -s -u admin:admin https://localhost:$OPENSEARCH_PORT/_cat/indices?v 2>/dev/null | grep -v "^\." || print_warning "Could not retrieve indices"
    echo ""
    
    print_info "Access points:"
    echo "  • OpenSearch: https://localhost:$OPENSEARCH_PORT"
    echo "  • Dashboards: http://localhost:$OPENSEARCH_DASHBOARD_PORT"
    echo "  • API Docs: http://localhost:$OPENSEARCH_API_PORT/docs"
    echo ""
    
    # Return to base directory
    cd "$BASE_DIR"
    
    return 0
}

# =============================================================================
# N8N SETUP
# =============================================================================

setup_n8n() {
    print_section "SETTING UP N8N"
    
    # Check if already running
    if docker ps | grep -q "$N8N_CONTAINER"; then
        print_success "n8n is already running"
        print_info "Access n8n at: http://localhost:$N8N_PORT"
        echo ""
        return 0
    fi
    
    if [ ! -f "$SETUP_N8N" ]; then
        print_error "n8n setup script not found: $SETUP_N8N"
        return 1
    fi
    
    local script_dir=$(dirname "$SETUP_N8N")
    local script_name=$(basename "$SETUP_N8N")
    
    print_step "Running setup from: $script_dir"
    cd "$script_dir" || return 1
    chmod +x "$script_name"
    
    echo ""
    if bash "./$script_name"; then
        print_success "n8n setup completed!"
        print_info "Access n8n at: http://localhost:$N8N_PORT"
    else
        print_error "n8n setup failed!"
        return 1
    fi
    
    echo ""
    cd "$BASE_DIR"
    return 0
}

# =============================================================================
# CONNECT N8N TO OPENSEARCH NETWORK
# =============================================================================

connect_n8n_to_opensearch() {
    print_section "CONNECTING N8N TO OPENSEARCH"
    
    # Check if n8n is running
    if ! docker ps | grep -q "$N8N_CONTAINER"; then
        print_warning "n8n container is not running, skipping network connection"
        return 0
    fi
    
    # Check if OpenSearch is running
    if ! docker ps | grep -q "$OPENSEARCH_CONTAINER"; then
        print_warning "OpenSearch container is not running, skipping network connection"
        return 0
    fi
    
    # Detect which network OpenSearch is actually on
    print_step "Detecting OpenSearch network..."
    local opensearch_networks=$(docker inspect "$OPENSEARCH_CONTAINER" --format '{{range $key, $value := .NetworkSettings.Networks}}{{$key}} {{end}}')
    
    print_info "OpenSearch is on networks: $opensearch_networks"
    
    # Find a common network or connect to the first OpenSearch network
    local target_network=""
    for network in $opensearch_networks; do
        # Prefer opensearch_internal_net or opensearch_default
        if [ "$network" = "$OPENSEARCH_NETWORK" ] || [ "$network" = "opensearch_default" ] || [ "$network" = "opensearch_internal_net" ]; then
            target_network="$network"
            break
        fi
    done
    
    # If no preferred network found, use the first one
    if [ -z "$target_network" ]; then
        target_network=$(echo $opensearch_networks | awk '{print $1}')
    fi
    
    if [ -z "$target_network" ]; then
        print_error "Could not determine OpenSearch network"
        return 1
    fi
    
    print_step "Connecting n8n to OpenSearch network: $target_network"
    
    # Check if n8n is already on this network
    if docker network inspect "$target_network" 2>/dev/null | grep -q "$N8N_CONTAINER"; then
        print_info "n8n is already connected to $target_network"
    else
        if docker network connect "$target_network" "$N8N_CONTAINER" 2>/dev/null; then
            print_success "n8n connected to $target_network"
        else
            print_warning "Could not connect n8n to $target_network"
            return 1
        fi
    fi
    
    # Restart n8n to refresh DNS
    print_step "Restarting n8n to refresh network settings..."
    docker restart "$N8N_CONTAINER" >/dev/null 2>&1
    sleep 5
    print_success "n8n restarted"
    
    # Test connectivity
    print_step "Testing OpenSearch connectivity from n8n..."
    sleep 2
    
    if docker exec "$N8N_CONTAINER" sh -c "timeout 2 cat < /dev/tcp/opensearch/9200" >/dev/null 2>&1; then
        print_success "n8n can reach OpenSearch at opensearch:9200"
    else
        print_warning "Could not verify connectivity (this may be normal)"
        print_info "If workflows fail, try using: https://host.docker.internal:9200"
    fi
    
    echo ""
    
    print_info "Network configuration:"
    echo "  • n8n can access OpenSearch at: https://opensearch:9200"
    echo "  • Alternative URL: https://host.docker.internal:9200"
    echo "  • Credentials: admin / admin"
    echo ""
}

# =============================================================================
# LLM SERVICE SETUP
# =============================================================================

setup_llm() {
    print_section "SETTING UP LLM SERVICE"
    
    if [ ! -f "$SETUP_LLM" ]; then
        print_error "LLM setup script not found: $SETUP_LLM"
        echo ""
        print_info "Expected location: $SETUP_LLM"
        print_info "Please ensure n8n repository is cloned properly"
        return 1
    fi
    
    local script_dir=$(dirname "$SETUP_LLM")
    local script_name=$(basename "$SETUP_LLM")
    
    print_step "Running setup from: $script_dir"
    print_info "Script: $script_name"
    
    cd "$script_dir" || return 1
    chmod +x "$script_name"
    
    echo ""
    if bash "./$script_name"; then
        print_success "LLM service setup completed!"
    else
        print_error "LLM service setup failed"
        return 1
    fi
    
    echo ""
    cd "$BASE_DIR"
    return 0
}

# =============================================================================
# CRAWLER SETUP
# =============================================================================

setup_crawler() {
    print_section "SETTING UP CRAWLER"
    
    if [ ! -f "$SETUP_CRAWLER" ]; then
        print_error "Crawler setup script not found: $SETUP_CRAWLER"
        echo ""
        print_info "Expected location: $SETUP_CRAWLER"
        print_info "Please ensure n8n repository is cloned properly"
        return 1
    fi
    
    local script_dir=$(dirname "$SETUP_CRAWLER")
    local script_name=$(basename "$SETUP_CRAWLER")
    
    print_step "Running setup from: $script_dir"
    print_info "Script: $script_name"
    
    cd "$script_dir" || return 1
    chmod +x "$script_name"
    
    echo ""
    if bash "./$script_name"; then
        print_success "Crawler setup completed!"
    else
        print_error "Crawler setup failed"
        return 1
    fi
    
    echo ""
    cd "$BASE_DIR"
    return 0
}

# =============================================================================
# DASHBOARD SETUP
# =============================================================================

setup_dashboard() {
    print_section "SETTING UP DASHBOARD"
    
    if [ ! -f "$SETUP_DASHBOARD" ]; then
        print_error "Dashboard setup script not found: $SETUP_DASHBOARD"
        echo ""
        print_info "Expected location: $SETUP_DASHBOARD"
        print_info "Please ensure n8n repository is cloned properly"
        return 1
    fi
    
    local script_dir=$(dirname "$SETUP_DASHBOARD")
    local script_name=$(basename "$SETUP_DASHBOARD")
    
    print_step "Running setup from: $script_dir"
    print_info "Script: $script_name"
    
    cd "$script_dir" || return 1
    chmod +x "$script_name"
    
    echo ""
    if bash "./$script_name"; then
        print_success "Dashboard setup completed!"
    else
        print_error "Dashboard setup failed"
        return 1
    fi
    
    echo ""
    cd "$BASE_DIR"
    return 0
}

# =============================================================================
# SERVICE ORCHESTRATION
# =============================================================================

setup_all_services() {
    print_section "SERVICE SETUP ORCHESTRATION"
    
    print_info "Setup order: OpenSearch → n8n → LLM → Crawler → Dashboard"
    print_info "All setup scripts are in: $DIR_N8N/docker/"
    echo ""
    
    # OpenSearch (required)
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    read -p "Setup OpenSearch? [Y/n]: " -n 1 -r
    echo
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        setup_opensearch || print_warning "OpenSearch setup had issues"
        sleep 2
    else
        print_info "Skipping OpenSearch"
    fi
    
    # n8n (required)
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    read -p "Setup n8n? [Y/n]: " -n 1 -r
    echo
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        setup_n8n || print_warning "n8n setup had issues"
        
        # Connect n8n to OpenSearch network for workflow communication
        connect_n8n_to_opensearch || print_warning "Network connection had issues"
        
        sleep 2
    else
        print_info "Skipping n8n"
    fi
    
    # LLM
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    read -p "Setup LLM service? [Y/n]: " -n 1 -r
    echo
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        setup_llm || print_warning "LLM setup had issues"
        sleep 2
    else
        print_info "Skipping LLM"
    fi
    
    # Crawler
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    read -p "Setup Crawler API? [Y/n]: " -n 1 -r
    echo
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        setup_crawler || print_warning "Crawler setup had issues"
        sleep 2
    else
        print_info "Skipping Crawler"
    fi
    
    # Dashboard
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    read -p "Setup Dashboard? [Y/n]: " -n 1 -r
    echo
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        setup_dashboard || print_warning "Dashboard setup had issues"
    else
        print_info "Skipping Dashboard"
    fi
    
    echo ""
    print_success "Service setup orchestration complete!"
}

# =============================================================================
# FINAL SUMMARY
# =============================================================================

print_summary() {
    clear
    print_section "🎉 SETUP COMPLETE!"
    
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    CURRENTLY RUNNING                         ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""
    
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    SERVICE URLS                              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo -e "${BOLD}${CYAN}OpenSearch Stack:${NC}"
    echo "  • OpenSearch API:    https://localhost:$OPENSEARCH_PORT"
    echo "  • OpenSearch UI:     http://localhost:$OPENSEARCH_DASHBOARD_PORT"
    echo "  • SoPro API:         http://localhost:$OPENSEARCH_API_PORT"
    echo "  • API Docs:          http://localhost:$OPENSEARCH_API_PORT/docs"
    echo "  • Credentials:       admin / admin"
    echo ""
    
    echo -e "${BOLD}${CYAN}n8n Workflow Automation:${NC}"
    echo "  • n8n UI:            http://localhost:$N8N_PORT"
    echo "  • OpenSearch URL:    https://opensearch:9200"
    echo ""
    
    # Check if services are running
    if docker ps | grep -q "$OLLAMA_CONTAINER\|$LLM_CONTAINER"; then
        echo -e "${BOLD}${CYAN}LLM Services:${NC}"
        echo "  • LLM API:           http://localhost:$LLM_PORT"
        echo "  • LLM Docs:          http://localhost:$LLM_PORT/docs"
        echo "  • Ollama:            http://localhost:$OLLAMA_PORT"
        echo "  • Model:             $OLLAMA_MODEL"
        echo ""
    fi
    
    if docker ps | grep -q "$CRAWLER_CONTAINER"; then
        echo -e "${BOLD}${CYAN}Crawler API:${NC}"
        echo "  • Crawler API:       http://localhost:$CRAWLER_PORT"
        echo "  • Crawler Docs:      http://localhost:$CRAWLER_PORT/docs"
        echo ""
    fi
    
    if docker ps | grep -q "$DASHBOARD_CONTAINER"; then
        echo -e "${BOLD}${CYAN}Dashboard:${NC}"
        echo "  • Dashboard UI:      http://localhost:$DASHBOARD_PORT"
        echo ""
    fi
    
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                    USEFUL COMMANDS                           ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    echo "View all containers:  docker ps"
    echo "View logs:            docker logs -f <container-name>"
    echo "Stop all services:    docker stop \$(docker ps -q)"
    echo "Test OpenSearch:      curl -k -u admin:admin https://localhost:9200"
    echo ""
    
    print_success "System is ready to use!"
    print_info "Project directory: $BASE_DIR"
    echo ""
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    print_header
    check_prerequisites
    setup_repositories
    setup_networks
    setup_all_services
    print_summary
}

# Run main function
main "$@"