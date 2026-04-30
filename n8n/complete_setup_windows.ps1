<# 
    SWP News Summary - Complete System Setup (Windows / PowerShell)

    This script is a PowerShell adaptation of `complete_setup.sh` for Windows hosts.
    It assumes:
      - Docker Desktop is installed and running
      - Git is installed and available in PATH
      - PowerShell 5.1+ (or PowerShell 7+) is available

    It performs the same high-level actions as the bash script:
      1. Check prerequisites (Docker, Docker Compose, Git)
      2. Clone or update all required repositories
      3. Generate configuration files (`config.sh`, `config_m2.sh`)
      4. Generate `restore_indices.sh` for OpenSearch
      5. Create Docker networks
      6. Optionally set up:
         - OpenSearch stack
         - n8n
         - LLM service
         - Crawler API
         - Dashboard
      7. Print a final summary with container status and URLs

    Run from PowerShell:
        ./complete_setup_windows.ps1
#>

param(
    [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Header {
    Clear-Host
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗"
    Write-Host "║                                                              ║"
    Write-Host "║       SWP NEWS SUMMARY - COMPLETE SYSTEM SETUP (WINDOWS)     ║"
    Write-Host "║                                                              ║"
    Write-Host "╚══════════════════════════════════════════════════════════════╝"
    Write-Host ""
    Write-Host "Repository:      $REPO_URL"
    Write-Host "Base Directory:  $BASE_DIR"
    Write-Host ""
}

function Write-Section([string]$Title) {
    Write-Host ""
    Write-Host "=============================================================="
    Write-Host "  $Title"
    Write-Host "=============================================================="
    Write-Host ""
}

function Write-Step([string]$Text)    { Write-Host "  [>] $Text" }
function Write-Ok([string]$Text)      { Write-Host "  [+] $Text" -ForegroundColor Green }
function Write-Warn([string]$Text)    { Write-Host "  [!] $Text" -ForegroundColor Yellow }
function Write-Err([string]$Text)     { Write-Host "  [x] $Text" -ForegroundColor Red }
function Write-Info([string]$Text)    { Write-Host "  [i] $Text" -ForegroundColor Cyan }

# -----------------------------------------------------------------------------
# CONFIGURATION (mirrors complete_setup.sh)
# -----------------------------------------------------------------------------

$REPO_URL          = "https://github.com/eniseirem/news-summary-project.git"
# Old GitLab URL: https://gitlab.fokus.fraunhofer.de/dana/cswspws25.git
$BASE_DIR          = Join-Path $env:USERPROFILE "SWP-News-Summary"

$BRANCH_OPENSEARCH = "Opensearch"
$BRANCH_N8N        = "n8n-pipeline"
$BRANCH_CRAWLER    = "WebCrawlerMain"
$BRANCH_LLM        = "m3-final"
$BRANCH_DASHBOARD  = "frontend/dashboard-ui"

$DIR_OPENSEARCH    = Join-Path $BASE_DIR "opensearch"
$DIR_N8N           = Join-Path $BASE_DIR "n8n"
$DIR_CRAWLER       = Join-Path $BASE_DIR "cswspws25-WebCrawlerMain"
$DIR_LLM           = Join-Path $BASE_DIR "cswspws25-m3-final"
$DIR_DASHBOARD     = Join-Path $BASE_DIR "frontend"

# Setup script locations (inside n8n repo)
$SETUP_N8N         = Join-Path $DIR_N8N "docker/n8n/setup_n8n.sh"
$SETUP_LLM         = Join-Path $DIR_N8N "docker/llm-service/setup-llm-service.sh"
$SETUP_CRAWLER     = Join-Path $DIR_N8N "docker/crawler/setup-crawler-service.sh"
$SETUP_CRAWLER_WIN = Join-Path $DIR_N8N "docker/crawler/setup-crawler-service-windows.sh"
$SETUP_DASHBOARD   = Join-Path $DIR_N8N "docker/streamlit-frontend/setup-frontend-service.sh"

# Docker networks
$OPENSEARCH_NETWORK = "opensearch_internal_net"
$N8N_NETWORK        = "n8n-network"

# Container names
$OPENSEARCH_CONTAINER         = "opensearch"
$OPENSEARCH_DASHBOARD_CONTAINER = "opensearch-dashboards"
$OPENSEARCH_API_CONTAINER     = "opensearch-python-api"
$N8N_CONTAINER                = "n8n"
$OLLAMA_CONTAINER             = "ollama"
$LLM_CONTAINER                = "llm-service"
$CRAWLER_CONTAINER            = "crawler-api"
$DASHBOARD_CONTAINER          = "dashboard"

# Ports
$OPENSEARCH_PORT              = 9200
$OPENSEARCH_DASHBOARD_PORT    = 5601
$OPENSEARCH_API_PORT          = 8002
$N8N_PORT                     = 5678
$OLLAMA_PORT                  = 11434
$LLM_PORT                     = 8001
$CRAWLER_PORT                 = 8003
$DASHBOARD_PORT               = 8501

$TIMEZONE                     = "Europe/Berlin"
$OLLAMA_MODEL                 = "llama3.2:3b"
$OLLAMA_NUM_PARALLEL          = 2
$OLLAMA_CONTEXT_LENGTH        = 8192

# -----------------------------------------------------------------------------
# PREREQUISITES
# -----------------------------------------------------------------------------

function Test-CommandExists([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Check-Prerequisites {
    Write-Section "CHECKING PREREQUISITES"
    $allGood = $true

    Write-Step "Checking Docker..."
    if (-not (Test-CommandExists "docker")) {
        Write-Err "Docker is not installed or not in PATH."
        Write-Info "Install Docker Desktop from: https://docs.docker.com/desktop/"
        $allGood = $false
    }
    else {
        $dockerVersion = docker --version 2>$null
        Write-Ok "Docker available ($dockerVersion)"

        Write-Step "Checking Docker daemon..."
        try {
            docker info >$null 2>&1
            Write-Ok "Docker daemon is running."
        }
        catch {
            Write-Err "Docker daemon is not running. Please start Docker Desktop."
            $allGood = $false
        }
    }

    Write-Step "Checking Docker Compose..."
    $composeOk = $false
    if (Test-CommandExists "docker-compose") {
        $composeVersion = docker-compose --version 2>$null
        Write-Ok "docker-compose installed ($composeVersion)"
        $composeOk = $true
    }
    else {
        try {
            docker compose version >$null 2>&1
            Write-Ok "Docker Compose plugin available (docker compose)."
            $composeOk = $true
        }
        catch {
            Write-Err "Docker Compose is not installed."
        }
    }
    if (-not $composeOk) { $allGood = $false }

    Write-Step "Checking Git..."
    if (-not (Test-CommandExists "git")) {
        Write-Err "Git is not installed or not in PATH."
        $allGood = $false
    }
    else {
        $gitVersion = git --version 2>$null
        Write-Ok "Git available ($gitVersion)"
    }

    if (-not $allGood) {
        Write-Err "Prerequisite check failed. Please install the missing tools and retry."
        exit 1
    }

    Write-Ok "All prerequisites satisfied."
    Write-Host ""
}

# -----------------------------------------------------------------------------
# CONFIG FILE GENERATION
# -----------------------------------------------------------------------------

function New-LlmConfig {
    $llmConfigDir = Join-Path $DIR_N8N "docker/llm-service"
    if (-not (Test-Path $llmConfigDir)) {
        New-Item -ItemType Directory -Path $llmConfigDir -Force | Out-Null
    }

    $configPath = Join-Path $llmConfigDir "config.sh"
    Write-Step "Creating LLM config: $configPath"
    @'
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
'@ | Set-Content -Path $configPath -NoNewline
    Write-Ok "LLM config created."
}

function New-N8nConfig {
    $n8nConfigDir = Join-Path $DIR_N8N "docker/n8n"
    if (-not (Test-Path $n8nConfigDir)) {
        New-Item -ItemType Directory -Path $n8nConfigDir -Force | Out-Null
    }

    $configPath = Join-Path $n8nConfigDir "config_m2.sh"
    Write-Step "Creating n8n config: $configPath"
    @'
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
'@ | Set-Content -Path $configPath -NoNewline
    Write-Ok "n8n config created."
}

function New-RestoreIndicesScript {
    $scriptsDir = Join-Path $DIR_OPENSEARCH "scripts"
    if (-not (Test-Path $scriptsDir)) {
        New-Item -ItemType Directory -Path $scriptsDir -Force | Out-Null
    }

    $scriptPath = Join-Path $scriptsDir "restore_indices.sh"
    Write-Step "Creating restore_indices.sh: $scriptPath"
    @'
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
'@ | Set-Content -Path $scriptPath -NoNewline
    Write-Ok "restore_indices.sh created."
}

function New-ConfigFiles {
    Write-Section "CREATING CONFIGURATION FILES"
    New-LlmConfig
    New-N8nConfig
    New-RestoreIndicesScript
    Write-Host ""
}

# -----------------------------------------------------------------------------
# GIT / REPOSITORY SETUP
# -----------------------------------------------------------------------------

function Invoke-Git {
    param(
        [string]$WorkingDir,
        [string]$Arguments
    )
    Push-Location $WorkingDir
    try {
        git $Arguments
    }
    finally {
        Pop-Location
    }
}

function Clone-Branch {
    param(
        [string]$Service,
        [string]$Branch,
        [string]$TargetDir
    )

    Write-Step "Cloning $Service (branch: $Branch) into $TargetDir"
    if (Test-Path $TargetDir) {
        Write-Warn "Directory already exists, skipping clone."
        return
    }

    git clone --single-branch --branch $Branch $REPO_URL $TargetDir
    Write-Ok "$Service cloned successfully."
}

function Update-Repository {
    param(
        [string]$ServiceName,
        [string]$ServiceDir,
        [string]$Branch
    )

    Write-Section "UPDATING $ServiceName"

    if (-not (Test-Path $ServiceDir)) {
        Write-Warn "Directory not found: $ServiceDir (skipping)."
        return
    }

    if (-not (Test-Path (Join-Path $ServiceDir ".git"))) {
        Write-Warn "Not a git repository: $ServiceDir (skipping)."
        return
    }

    $hasChanges = $false
    $status = Invoke-Git -WorkingDir $ServiceDir -Arguments "status --porcelain"
    if ($status) { $hasChanges = $true }

    if ($hasChanges) {
        Write-Warn "Repository has local changes or untracked files."
        if ($NonInteractive) {
            Write-Warn "NonInteractive mode: keeping existing files, skipping update."
            return
        }

        Write-Host ""
        Write-Host "Options:"
        Write-Host "  1) Discard all changes and pull latest (recommended)"
        Write-Host "  2) Stash changes and pull latest"
        Write-Host "  3) Keep current files and skip git update"
        Write-Host "  4) Exit and handle manually"
        $choice = Read-Host "Choose option [1-4]"

        switch ($choice) {
            "1" {
                Write-Step "Discarding all local changes..."
                Invoke-Git -WorkingDir $ServiceDir -Arguments "reset --hard"
                Invoke-Git -WorkingDir $ServiceDir -Arguments "clean -fd"
            }
            "2" {
                Write-Step "Stashing local changes..."
                Invoke-Git -WorkingDir $ServiceDir -Arguments "stash save `"Auto-stash by setup script $(Get-Date)`""
            }
            "3" {
                Write-Info "Using existing files without git update."
                return
            }
            "4" {
                Write-Info "Exiting as requested. You can update $ServiceDir manually."
                exit 0
            }
            default {
                Write-Err "Invalid choice."
                exit 1
            }
        }
    }

    # Pull latest
    Write-Step "Ensuring branch '$Branch' and pulling latest..."
    Invoke-Git -WorkingDir $ServiceDir -Arguments "fetch origin"
    Invoke-Git -WorkingDir $ServiceDir -Arguments "checkout $Branch"
    Invoke-Git -WorkingDir $ServiceDir -Arguments "pull origin $Branch"
    Write-Ok "$ServiceName repository updated."
}

function Setup-Repositories {
    Write-Section "STEP 1: REPOSITORY SETUP"

    if (Test-Path $BASE_DIR) {
        Write-Warn "Base directory already exists: $BASE_DIR"

        if ($NonInteractive) {
            Write-Info "NonInteractive mode: updating existing repositories."
            Update-Repository -ServiceName "OpenSearch" -ServiceDir $DIR_OPENSEARCH -Branch $BRANCH_OPENSEARCH
            Update-Repository -ServiceName "n8n"        -ServiceDir $DIR_N8N        -Branch $BRANCH_N8N
            Update-Repository -ServiceName "Crawler"    -ServiceDir $DIR_CRAWLER    -Branch $BRANCH_CRAWLER
            Update-Repository -ServiceName "LLM"        -ServiceDir $DIR_LLM        -Branch $BRANCH_LLM
            Update-Repository -ServiceName "Dashboard"  -ServiceDir $DIR_DASHBOARD  -Branch $BRANCH_DASHBOARD
            New-ConfigFiles
            return
        }

        Write-Host ""
        Write-Host "Choose an option:"
        Write-Host "  1) Delete and re-clone everything (fresh start)"
        Write-Host "  2) Update existing repositories (pull latest)"
        Write-Host "  3) Use existing without updates"
        Write-Host "  4) Exit setup"
        $choice = Read-Host "Enter choice [1-4]"

        switch ($choice) {
            "1" {
                Write-Step "Removing existing directory..."
                Remove-Item -Recurse -Force $BASE_DIR
                Write-Ok "Directory removed."
            }
            "2" {
                Write-Info "Updating existing repositories..."
                Update-Repository -ServiceName "OpenSearch" -ServiceDir $DIR_OPENSEARCH -Branch $BRANCH_OPENSEARCH
                Update-Repository -ServiceName "n8n"        -ServiceDir $DIR_N8N        -Branch $BRANCH_N8N
                Update-Repository -ServiceName "Crawler"    -ServiceDir $DIR_CRAWLER    -Branch $BRANCH_CRAWLER
                Update-Repository -ServiceName "LLM"        -ServiceDir $DIR_LLM        -Branch $BRANCH_LLM
                Update-Repository -ServiceName "Dashboard"  -ServiceDir $DIR_DASHBOARD  -Branch $BRANCH_DASHBOARD
                New-ConfigFiles
                return
            }
            "3" {
                Write-Info "Using existing directories without updates."
                New-ConfigFiles
                return
            }
            "4" {
                Write-Info "Setup cancelled by user."
                exit 0
            }
            default {
                Write-Err "Invalid choice."
                exit 1
            }
        }
    }

    if (-not (Test-Path $BASE_DIR)) {
        New-Item -ItemType Directory -Path $BASE_DIR -Force | Out-Null
        Write-Ok "Created base directory: $BASE_DIR"
        Write-Host ""
    }

    Clone-Branch -Service "opensearch" -Branch $BRANCH_OPENSEARCH -TargetDir $DIR_OPENSEARCH
    Clone-Branch -Service "n8n"        -Branch $BRANCH_N8N        -TargetDir $DIR_N8N
    Clone-Branch -Service "crawler"    -Branch $BRANCH_CRAWLER    -TargetDir $DIR_CRAWLER
    Clone-Branch -Service "llm"        -Branch $BRANCH_LLM        -TargetDir $DIR_LLM
    Clone-Branch -Service "dashboard"  -Branch $BRANCH_DASHBOARD  -TargetDir $DIR_DASHBOARD

    New-ConfigFiles
}

# -----------------------------------------------------------------------------
# DOCKER NETWORKS
# -----------------------------------------------------------------------------

function Ensure-DockerNetwork {
    param(
        [string]$Name
    )
    Write-Step "Ensuring network: $Name"
    $exists = docker network ls --format "{{.Name}}" | Select-String -SimpleMatch $Name
    if ($exists) {
        Write-Warn "Network already exists."
    }
    else {
        docker network create $Name | Out-Null
        Write-Ok "Network created."
    }
}

function Setup-Networks {
    Write-Section "DOCKER NETWORK SETUP"
    Ensure-DockerNetwork -Name $OPENSEARCH_NETWORK
    Ensure-DockerNetwork -Name $N8N_NETWORK
    Write-Ok "Network setup complete."
    Write-Host ""
}

# -----------------------------------------------------------------------------
# SERVICE SETUP HELPERS (invoke bash scripts inside repo)
# -----------------------------------------------------------------------------

function Invoke-BashScript {
    param(
        [string]$ScriptPath,
        [string]$WorkingDir
    )

    if (-not (Test-Path $ScriptPath)) {
        Write-Err "Script not found: $ScriptPath"
        return $false
    }

    if (-not (Test-CommandExists "bash")) {
        Write-Err "bash is not available on this system."
        Write-Info "Install Git for Windows and ensure 'Git Bash' is in PATH, or use WSL."
        return $false
    }

    Push-Location $WorkingDir
    try {
        Write-Step "Running bash script: $ScriptPath"
        bash $ScriptPath
        return $true
    }
    catch {
        Write-Err "Script failed: $($_.Exception.Message)"
        return $false
    }
    finally {
        Pop-Location
    }
}

function Setup-OpenSearch {
    Write-Section "SETTING UP OPENSEARCH"

    $running = docker ps --format "{{.Names}}" | Select-String -SimpleMatch $OPENSEARCH_CONTAINER
    if ($running) {
        Write-Ok "OpenSearch is already running."
        Write-Info "If indices are missing, you can run 'restore_indices.sh' manually in the opensearch repo."
        return
    }

    if (-not (Test-Path $DIR_OPENSEARCH)) {
        Write-Err "OpenSearch directory not found: $DIR_OPENSEARCH"
        return
    }

    Push-Location $DIR_OPENSEARCH
    try {
        Write-Step "Stopping any existing OpenSearch stack (docker-compose down)..."
        try {
            if (Test-CommandExists "docker-compose") {
                docker-compose down -v --remove-orphans 2>$null
            }
            else {
                docker compose down -v --remove-orphans 2>$null
            }
        }
        catch { }

        if (-not (Test-Path "docker-compose.yml")) {
            Write-Err "docker-compose.yml not found in $DIR_OPENSEARCH"
            return
        }

        Write-Step "Starting OpenSearch services with docker-compose..."
        if (Test-CommandExists "docker-compose") {
            docker-compose up -d
        }
        else {
            docker compose up -d
        }

        Write-Ok "Docker Compose started."
        Write-Step "Waiting for OpenSearch to be ready..."

        $maxAttempts = 30
        for ($i = 0; $i -lt $maxAttempts; $i++) {
            try {
                Invoke-WebRequest -Uri "https://localhost:$OPENSEARCH_PORT" -UseBasicParsing -Headers @{ Authorization = ("Basic " + [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("admin:admin"))) } -SkipCertificateCheck -TimeoutSec 5 >$null 2>&1
                Write-Ok "OpenSearch is ready."
                break
            }
            catch {
                Start-Sleep -Seconds 2
            }
        }

        # Run restore_indices.sh if present
        $scriptsDir = Join-Path $DIR_OPENSEARCH "scripts"
        $restoreScript = Join-Path $scriptsDir "restore_indices.sh"
        if (Test-Path $restoreScript) {
            Write-Step "Running restore_indices.sh..."
            if (Test-CommandExists "bash") {
                bash $restoreScript
            }
            else {
                Write-Warn "bash not available. Please run restore_indices.sh from a Unix-like shell."
            }
        }

        Write-Info "OpenSearch URLs:"
        Write-Host "  • OpenSearch API:    https://localhost:$OPENSEARCH_PORT"
        Write-Host "  • OpenSearch UI:     http://localhost:$OPENSEARCH_DASHBOARD_PORT"
        Write-Host "  • SoPro API Docs:    http://localhost:$OPENSEARCH_API_PORT/docs"
    }
    finally {
        Pop-Location
    }
}

function Setup-N8N {
    Write-Section "SETTING UP N8N"
    if (-not (Test-Path $SETUP_N8N)) {
        Write-Err "n8n setup script not found: $SETUP_N8N"
        return
    }
    $dir = Split-Path $SETUP_N8N -Parent
    if (Invoke-BashScript -ScriptPath $SETUP_N8N -WorkingDir $dir) {
        Write-Ok "n8n setup completed. URL: http://localhost:$N8N_PORT"
    }
}

function Setup-LLM {
    Write-Section "SETTING UP LLM SERVICE"
    if (-not (Test-Path $SETUP_LLM)) {
        Write-Err "LLM setup script not found: $SETUP_LLM"
        return
    }
    $dir = Split-Path $SETUP_LLM -Parent
    if (Invoke-BashScript -ScriptPath $SETUP_LLM -WorkingDir $dir) {
        Write-Ok "LLM service setup completed."
    }
}

function Setup-Crawler {
    Write-Section "SETTING UP CRAWLER"
    # Prefer the Windows-friendly crawler script if it exists
    $scriptPath = if (Test-Path $SETUP_CRAWLER_WIN) { $SETUP_CRAWLER_WIN } else { $SETUP_CRAWLER }

    if (-not (Test-Path $scriptPath)) {
        Write-Err "Crawler setup script not found: $scriptPath"
        return
    }

    $dir = Split-Path $scriptPath -Parent
    if (Invoke-BashScript -ScriptPath $scriptPath -WorkingDir $dir) {
        Write-Ok "Crawler setup completed."
    }
}

function Setup-Dashboard {
    Write-Section "SETTING UP DASHBOARD"
    if (-not (Test-Path $SETUP_DASHBOARD)) {
        Write-Err "Dashboard setup script not found: $SETUP_DASHBOARD"
        return
    }
    $dir = Split-Path $SETUP_DASHBOARD -Parent
    if (Invoke-BashScript -ScriptPath $SETUP_DASHBOARD -WorkingDir $dir) {
        Write-Ok "Dashboard setup completed."
    }
}

function Ask-YesNo([string]$Prompt, [bool]$DefaultYes = $true) {
    if ($NonInteractive) {
        return $DefaultYes
    }
    $suffix = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
    $answer = Read-Host "$Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $DefaultYes }
    return $answer.ToLower().StartsWith("y")
}

function Setup-AllServices {
    Write-Section "SERVICE SETUP ORCHESTRATION"
    Write-Info "Setup order: OpenSearch → n8n → LLM → Crawler → Dashboard"
    Write-Host ""

    if (Ask-YesNo "Setup OpenSearch?" $true) { Setup-OpenSearch }
    if (Ask-YesNo "Setup n8n?" $true)       { Setup-N8N }
    if (Ask-YesNo "Setup LLM service?" $false) { Setup-LLM }
    if (Ask-YesNo "Setup Crawler API?" $false) { Setup-Crawler }
    if (Ask-YesNo "Setup Dashboard?" $false)   { Setup-Dashboard }
}

# -----------------------------------------------------------------------------
# FINAL SUMMARY
# -----------------------------------------------------------------------------

function Print-Summary {
    Write-Section "SETUP COMPLETE"
    Write-Info "Currently running containers:"
    docker ps
    Write-Host ""

    Write-Info "Service URLs (if containers are running):"
    Write-Host "  • OpenSearch API:    https://localhost:$OPENSEARCH_PORT"
    Write-Host "  • OpenSearch UI:     http://localhost:$OPENSEARCH_DASHBOARD_PORT"
    Write-Host "  • SoPro API Docs:    http://localhost:$OPENSEARCH_API_PORT/docs"
    Write-Host "  • n8n UI:            http://localhost:$N8N_PORT"
    Write-Host "  • LLM API:           http://localhost:$LLM_PORT"
    Write-Host "  • Ollama:            http://localhost:$OLLAMA_PORT"
    Write-Host "  • Crawler API:       http://localhost:$CRAWLER_PORT"
    Write-Host "  • Dashboard UI:      http://localhost:$DASHBOARD_PORT"
    Write-Host ""

    Write-Ok "System is ready to use (subject to which services you chose to start)."
    Write-Info "Project directory: $BASE_DIR"
    Write-Host ""
}

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

Write-Header
Check-Prerequisites
Setup-Repositories
Setup-Networks
Setup-AllServices
Print-Summary

