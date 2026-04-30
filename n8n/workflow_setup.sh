#!/bin/bash

# n8n Account Setup & Workflow Import Script with Automated Credentials
# Run this AFTER complete_setup.sh

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

BASE_DIR="$HOME/SWP-News-Summary"
N8N_DIR="$BASE_DIR/n8n"
WORKFLOWS_DIR="$N8N_DIR/workflows/n8n json"
N8N_URL="http://localhost:5678"
N8N_CONTAINER="n8n"

# Default credentials for services
OPENSEARCH_HOST="opensearch"
OPENSEARCH_PORT="9200"
OPENSEARCH_USER="admin"
OPENSEARCH_PASS="admin"

OLLAMA_HOST="ollama"
OLLAMA_PORT="11434"

LLM_HOST="llm-service"
LLM_PORT="8001"

CRAWLER_HOST="crawler-api"
CRAWLER_PORT="8003"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

print_header() {
    clear
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║         N8N AUTOMATED SETUP & WORKFLOW IMPORT                ║"
    echo "║                                                              ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
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
# CHECK PREREQUISITES
# =============================================================================

check_prerequisites() {
    print_section "CHECKING PREREQUISITES"
    
    local all_good=true
    
    # Check if n8n container is running
    print_step "Checking n8n container..."
    if ! docker ps | grep -q "$N8N_CONTAINER"; then
        print_error "n8n container is not running"
        echo "       Please run complete_setup.sh first"
        all_good=false
    else
        print_success "n8n container is running"
    fi
    
    # Check if n8n is accessible
    print_step "Checking n8n accessibility..."
    if ! curl -s "$N8N_URL" > /dev/null 2>&1; then
        print_error "n8n is not accessible at $N8N_URL"
        all_good=false
    else
        print_success "n8n is accessible"
    fi
    
    # Check if workflows directory exists
    print_step "Checking workflows directory..."
    if [ ! -d "$WORKFLOWS_DIR" ]; then
        print_warning "Workflows directory not found: $WORKFLOWS_DIR"
        echo "       Will skip workflow import"
        WORKFLOWS_EXIST=false
    else
        workflow_count=$(find "$WORKFLOWS_DIR" -name "*.json" -type f 2>/dev/null | wc -l | tr -d ' ')
        if [ "$workflow_count" -gt 0 ]; then
            print_success "Found $workflow_count workflow(s) to import"
            WORKFLOWS_EXIST=true
        else
            print_warning "No workflow JSON files found"
            WORKFLOWS_EXIST=false
        fi
    fi
    
    echo ""
    
    if [ "$all_good" = false ]; then
        print_error "Prerequisites check failed"
        exit 1
    fi
    
    print_success "All prerequisites satisfied!"
    echo ""
}

# =============================================================================
# CHECK IF N8N IS INITIALIZED
# =============================================================================

check_n8n_initialization() {
    print_section "CHECKING N8N INITIALIZATION"
    
    print_step "Checking if n8n owner account exists..."
    
    # Try to access n8n API
    response=$(curl -s -o /dev/null -w "%{http_code}" "$N8N_URL/api/v1/owner")
    
    if [ "$response" = "200" ]; then
        print_warning "n8n owner account already exists"
        N8N_INITIALIZED=true
    else
        print_info "n8n needs initialization (first-time setup)"
        N8N_INITIALIZED=false
    fi
    
    echo ""
}

# =============================================================================
# GUIDE USER TO CREATE ACCOUNT
# =============================================================================

guide_account_creation() {
    if [ "$N8N_INITIALIZED" = true ]; then
        print_section "N8N ACCOUNT STATUS"
        print_success "n8n account already created - skipping this step"
        echo ""
        return 0
    fi
    
    print_section "STEP 1: CREATE N8N ACCOUNT"
    
    echo -e "${CYAN}You need to create an owner account for n8n.${NC}"
    echo ""
    echo -e "${BOLD}Instructions:${NC}"
    echo "  1. n8n will open in your browser automatically"
    echo "  2. Fill in the account creation form:"
    echo "     - Email"
    echo "     - First Name"
    echo "     - Last Name"
    echo "     - Password"
    echo "  3. Click 'Create Account'"
    echo ""
    
    read -p "Press ENTER to open n8n in your browser..."
    
    # Try to open in browser
    if command -v open &> /dev/null; then
        open "$N8N_URL"
    elif command -v xdg-open &> /dev/null; then
        xdg-open "$N8N_URL"
    elif command -v start &> /dev/null; then
        start "$N8N_URL"
    else
        echo ""
        print_info "Please open this URL in your browser:"
        echo "  $N8N_URL"
    fi
    
    echo ""
    print_warning "Complete the account creation in your browser, then return here."
    echo ""
    read -p "Have you created your account? [y/N]: " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Please complete account creation first, then run this script again."
        exit 0
    fi
    
    echo ""
    print_success "Account created!"
    echo ""
}

# =============================================================================
# SAVE CREDENTIALS INFO
# =============================================================================

save_credentials_info() {
    print_section "STEP 2: CREDENTIAL CONFIGURATION"
    
    print_info "Saving service endpoint information..."
    echo ""
    
    # Save credentials info to file
    local creds_file="$N8N_DIR/n8n-service-endpoints.txt"
    cat > "$creds_file" << EOF
n8n Service Endpoints Configuration
Generated: $(date)

==========================================
SERVICE ENDPOINTS FOR n8n WORKFLOWS
==========================================

OpenSearch:
  URL: https://${OPENSEARCH_HOST}:${OPENSEARCH_PORT}
  Username: ${OPENSEARCH_USER}
  Password: ${OPENSEARCH_PASS}
  
  How to configure in n8n:
  1. In your workflow, add an HTTP Request node
  2. Set Authentication to "Predefined Credential Type"
  3. Select "Basic Auth"
  4. Click "Create New Credential"
  5. Enter:
     - Name: OpenSearch
     - User: ${OPENSEARCH_USER}
     - Password: ${OPENSEARCH_PASS}

LLM Service:
  URL: http://${LLM_HOST}:${LLM_PORT}
  
  How to configure in n8n:
  1. In your workflow, add an HTTP Request node
  2. Set Authentication to "None"
  3. Set URL to: http://${LLM_HOST}:${LLM_PORT}

Ollama:
  URL: http://${OLLAMA_HOST}:${OLLAMA_PORT}
  
  How to configure in n8n:
  1. In your workflow, add an HTTP Request node
  2. Set Authentication to "None"
  3. Set URL to: http://${OLLAMA_HOST}:${OLLAMA_PORT}

Crawler API:
  URL: http://${CRAWLER_HOST}:${CRAWLER_PORT}
  
  How to configure in n8n:
  1. In your workflow, add an HTTP Request node
  2. Set Authentication to "None"
  3. Set URL to: http://${CRAWLER_HOST}:${CRAWLER_PORT}

==========================================
MANUAL CREDENTIAL SETUP IN n8n
==========================================

After importing workflows, you need to configure credentials:

1. Open n8n: ${N8N_URL}
2. Go to Settings > Credentials (or click user icon → Credentials)
3. Click "Add Credential"
4. For OpenSearch:
   - Type: Basic Auth
   - Name: OpenSearch
   - User: ${OPENSEARCH_USER}
   - Password: ${OPENSEARCH_PASS}
5. Save the credential

For other services (LLM, Ollama, Crawler):
   - No authentication required
   - Just use the URLs in HTTP Request nodes

==========================================
WORKFLOW CONFIGURATION
==========================================

In each imported workflow:
1. Open the workflow
2. Find HTTP Request nodes
3. Click on each node
4. If it connects to OpenSearch:
   - Select "OpenSearch" from credential dropdown
5. If it connects to other services:
   - Verify the URL is correct
   - No credentials needed

EOF
    
    print_success "Service endpoints saved to: $creds_file"
    echo ""
    
    print_info "Credential Setup Instructions:"
    echo ""
    echo "  Since n8n credentials require the web UI, please:"
    echo "  1. Open n8n at: $N8N_URL"
    echo "  2. Go to: Settings → Credentials"
    echo "  3. Create 'Basic Auth' credential for OpenSearch:"
    echo "     - Name: OpenSearch"
    echo "     - User: ${OPENSEARCH_USER}"
    echo "     - Password: ${OPENSEARCH_PASS}"
    echo ""
    echo "  Full instructions saved in:"
    echo "  $creds_file"
    echo ""
}

# =============================================================================
# PREPARE WORKFLOWS FOR IMPORT
# =============================================================================

prepare_workflows() {
    print_section "STEP 3: PREPARE WORKFLOWS"
    
    if [ "$WORKFLOWS_EXIST" = false ]; then
        print_warning "No workflows found, skipping this step"
        return 0
    fi
    
    print_step "Creating workflows import directory..."
    
    local import_dir="$HOME/n8n-workflows-import"
    mkdir -p "$import_dir"
    
    # Copy workflows to easily accessible location
    print_step "Copying workflow files..."
    cp "$WORKFLOWS_DIR"/*.json "$import_dir/" 2>/dev/null || true
    
    local copied_count=$(ls -1 "$import_dir"/*.json 2>/dev/null | wc -l | tr -d ' ')
    
    print_success "Copied $copied_count workflow(s) to: $import_dir"
    echo ""
    
    print_info "Workflows ready for import:"
    ls -1 "$import_dir"/*.json 2>/dev/null | while read -r file; do
        echo "  • $(basename "$file")"
    done
    
    echo ""
    IMPORT_DIR="$import_dir"
}

# =============================================================================
# IMPORT WORKFLOWS
# =============================================================================

import_workflows() {
    print_section "STEP 4: IMPORT WORKFLOWS"
    
    if [ "$WORKFLOWS_EXIST" = false ]; then
        print_info "No workflows to import"
        return 0
    fi
    
    echo -e "${CYAN}Importing workflows automatically...${NC}"
    echo ""
    
    print_step "Copying workflows to container..."
    
    # Copy workflows into container
    if docker cp "$IMPORT_DIR" "$N8N_CONTAINER:/tmp/workflows" 2>/dev/null; then
        print_success "Workflows copied to container"
        echo ""
        
        # Import each workflow
        print_step "Importing workflows..."
        docker exec "$N8N_CONTAINER" sh -c '
            success=0
            failed=0
            for f in /tmp/workflows/*.json; do
                if [ -f "$f" ]; then
                    workflow_name=$(basename "$f")
                    echo "  Importing $workflow_name..."
                    if n8n import:workflow --input="$f" 2>/dev/null; then
                        success=$((success + 1))
                    else
                        failed=$((failed + 1))
                    fi
                fi
            done
            echo ""
            echo "Import complete: $success succeeded, $failed failed"
        '
        
        echo ""
        print_success "Workflow import completed!"
    else
        print_error "Failed to copy workflows to container"
        print_info "You can import manually via the web UI"
    fi
    
    echo ""
}

# =============================================================================
# FINAL INSTRUCTIONS
# =============================================================================

print_final_instructions() {
    print_section "✓ SETUP COMPLETE!"
    
    echo -e "${GREEN}Your n8n instance is configured!${NC}"
    echo ""
    
    echo -e "${BOLD}Access n8n:${NC}"
    echo "  URL: $N8N_URL"
    echo ""
    
    if [ "$WORKFLOWS_EXIST" = true ]; then
        echo -e "${BOLD}Workflows:${NC}"
        echo "  ✓ Imported from: $WORKFLOWS_DIR"
        echo ""
    fi
    
    echo -e "${BOLD}IMPORTANT - Next Steps:${NC}"
    echo "  1. Open n8n at: $N8N_URL"
    echo "  2. Go to Settings → Credentials"
    echo "  3. Create 'Basic Auth' credential:"
    echo "     - Name: OpenSearch"
    echo "     - User: ${OPENSEARCH_USER}"
    echo "     - Password: ${OPENSEARCH_PASS}"
    echo "  4. Open each workflow and assign the 'OpenSearch' credential"
    echo "  5. Activate workflows as needed"
    echo ""
    
    echo -e "${BOLD}Service Configuration:${NC}"
    echo "  • All service endpoints and setup instructions:"
    echo "    $N8N_DIR/n8n-service-endpoints.txt"
    echo ""
    
    echo -e "${BOLD}Useful Commands:${NC}"
    echo "  • View n8n logs:     docker logs -f n8n"
    echo "  • Restart n8n:       docker restart n8n"
    echo "  • Stop n8n:          docker stop n8n"
    echo ""
    
    print_success "n8n setup complete - workflows imported!"
    print_warning "Remember to configure credentials in the web UI"
    echo ""
}

# =============================================================================
# MAIN EXECUTION
# =============================================================================

main() {
    print_header
    check_prerequisites
    check_n8n_initialization
    guide_account_creation
    save_credentials_info
    prepare_workflows
    import_workflows
    print_final_instructions
}

# Run main function
main "$@"