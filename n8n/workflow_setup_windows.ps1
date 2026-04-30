<#
    n8n Account Setup & Workflow Import Script (Windows / PowerShell)

    PowerShell adaptation of `workflow_setup.sh`.

    Responsibilities:
      - Verify n8n container is running and reachable
      - Check workflows directory inside the cloned n8n repo
      - Guide user through initial n8n owner account creation (in browser)
      - Write a service-endpoints info file for configuring credentials
      - Copy workflow JSONs into an import folder
      - Copy that folder into the n8n container and run `n8n import:workflow`

    Run AFTER the main setup (bash or Windows version) has started n8n:

        ./workflow_setup_windows.ps1
#>

param(
    [switch]$NonInteractive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section([string]$Title) {
    Write-Host ""
    Write-Host "=============================================================="
    Write-Host "  $Title"
    Write-Host "=============================================================="
    Write-Host ""
}

function Write-Step([string]$Text) { Write-Host "  [>] $Text" }
function Write-Ok([string]$Text)   { Write-Host "  [+] $Text" -ForegroundColor Green }
function Write-Warn([string]$Text) { Write-Host "  [!] $Text" -ForegroundColor Yellow }
function Write-Err([string]$Text)  { Write-Host "  [x] $Text" -ForegroundColor Red }
function Write-Info([string]$Text) { Write-Host "  [i] $Text" -ForegroundColor Cyan }

function Write-Header {
    Clear-Host
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════╗"
    Write-Host "║                                                              ║"
    Write-Host "║         N8N AUTOMATED SETUP & WORKFLOW IMPORT (WINDOWS)      ║"
    Write-Host "║                                                              ║"
    Write-Host "╚══════════════════════════════════════════════════════════════╝"
    Write-Host ""
}

# -----------------------------------------------------------------------------
# CONFIGURATION (mirrors workflow_setup.sh)
# -----------------------------------------------------------------------------

$BASE_DIR     = Join-Path $env:USERPROFILE "SWP-News-Summary"
$N8N_DIR      = Join-Path $BASE_DIR "n8n"
$WORKFLOWS_DIR = Join-Path $N8N_DIR "workflows/n8n json"
$N8N_URL      = "http://localhost:5678"
$N8N_CONTAINER = "n8n"

# Default service endpoints
$OPENSEARCH_HOST = "opensearch"
$OPENSEARCH_PORT = 9200
$OPENSEARCH_USER = "admin"
$OPENSEARCH_PASS = "admin"

$OLLAMA_HOST     = "ollama"
$OLLAMA_PORT     = 11434

$LLM_HOST        = "llm-service"
$LLM_PORT        = 8001

$CRAWLER_HOST    = "crawler-api"
$CRAWLER_PORT    = 8003

$script:WORKFLOWS_EXIST = $false
$script:IMPORT_DIR = ""
$script:N8N_INITIALIZED = $false

function Ask-YesNo([string]$Prompt, [bool]$DefaultYes = $true) {
    if ($NonInteractive) { return $DefaultYes }
    $suffix = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
    $answer = Read-Host "$Prompt $suffix"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $DefaultYes }
    return $answer.ToLower().StartsWith("y")
}

# -----------------------------------------------------------------------------
# PREREQUISITES
# -----------------------------------------------------------------------------

function Check-Prerequisites {
    Write-Section "CHECKING PREREQUISITES"
    $allGood = $true

    Write-Step "Checking n8n container..."
    $running = docker ps --format "{{.Names}}" | Select-String -SimpleMatch $N8N_CONTAINER
    if (-not $running) {
        Write-Err "n8n container is not running."
        Write-Info "Please run the complete setup first and ensure n8n is up."
        $allGood = $false
    }
    else {
        Write-Ok "n8n container is running."
    }

    Write-Step "Checking n8n accessibility at $N8N_URL ..."
    try {
        Invoke-WebRequest -Uri $N8N_URL -UseBasicParsing -TimeoutSec 5 >$null 2>&1
        Write-Ok "n8n is accessible."
    }
    catch {
        Write-Err "n8n is not accessible at $N8N_URL"
        $allGood = $false
    }

    Write-Step "Checking workflows directory..."
    if (-not (Test-Path $WORKFLOWS_DIR)) {
        Write-Warn "Workflows directory not found: $WORKFLOWS_DIR"
        Write-Info "Workflow import will be skipped."
        $script:WORKFLOWS_EXIST = $false
    }
    else {
        $count = Get-ChildItem -Path $WORKFLOWS_DIR -Filter *.json -ErrorAction SilentlyContinue | Measure-Object | Select-Object -ExpandProperty Count
        if ($count -gt 0) {
            Write-Ok "Found $count workflow JSON file(s)."
            $script:WORKFLOWS_EXIST = $true
        }
        else {
            Write-Warn "No workflow JSON files found in $WORKFLOWS_DIR"
            $script:WORKFLOWS_EXIST = $false
        }
    }

    if (-not $allGood) {
        Write-Err "Prerequisite check failed."
        exit 1
    }

    Write-Ok "All prerequisites satisfied."
    Write-Host ""
}

# -----------------------------------------------------------------------------
# N8N INITIALIZATION CHECK
# -----------------------------------------------------------------------------

function Check-N8nInitialization {
    Write-Section "CHECKING N8N INITIALIZATION"

    Write-Step "Checking if n8n owner account exists..."
    try {
        $response = Invoke-WebRequest -Uri "$N8N_URL/api/v1/owner" -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Warn "n8n owner account already exists."
            $script:N8N_INITIALIZED = $true
        }
        else {
            $script:N8N_INITIALIZED = $false
        }
    }
    catch {
        Write-Info "n8n needs initialization (first-time setup)."
        $script:N8N_INITIALIZED = $false
    }

    Write-Host ""
}

# -----------------------------------------------------------------------------
# ACCOUNT CREATION GUIDE
# -----------------------------------------------------------------------------

function Guide-AccountCreation {
    if ($script:N8N_INITIALIZED) {
        Write-Section "N8N ACCOUNT STATUS"
        Write-Ok "n8n account already created - skipping account creation step."
        Write-Host ""
        return
    }

    Write-Section "STEP 1: CREATE N8N ACCOUNT"
    Write-Info "You need to create the initial n8n owner account in the browser."
    Write-Host ""
    Write-Host "Instructions:"
    Write-Host "  1. The script will open n8n in your browser."
    Write-Host "  2. Fill in the account creation form (email, name, password)."
    Write-Host "  3. Click 'Create Account'."
    Write-Host ""

    if (-not $NonInteractive) {
        Read-Host "Press ENTER to open n8n in your default browser"
    }

    try {
        Start-Process $N8N_URL | Out-Null
    }
    catch {
        Write-Info "Could not launch browser automatically. Please open:"
        Write-Host "  $N8N_URL"
    }

    if ($NonInteractive) {
        Write-Warn "NonInteractive mode: skipping wait for manual confirmation."
        return
    }

    Write-Host ""
    Write-Warn "Complete account creation in your browser, then return to this window."
    $done = Ask-YesNo "Have you created your account?" $false
    if (-not $done) {
        Write-Warn "Please complete account creation first, then run this script again."
        exit 0
    }

    Write-Ok "Account creation acknowledged."
    Write-Host ""
}

# -----------------------------------------------------------------------------
# SERVICE ENDPOINT / CREDENTIAL INFO
# -----------------------------------------------------------------------------

function Save-CredentialsInfo {
    Write-Section "STEP 2: CREDENTIAL CONFIGURATION"
    Write-Info "Saving service endpoint information for n8n workflows."
    Write-Host ""

    if (-not (Test-Path $N8N_DIR)) {
        New-Item -ItemType Directory -Path $N8N_DIR -Force | Out-Null
    }

    $credsFile = Join-Path $N8N_DIR "n8n-service-endpoints.txt"
    @"
n8n Service Endpoints Configuration
Generated: $(Get-Date)

==========================================
SERVICE ENDPOINTS FOR n8n WORKFLOWS
==========================================

OpenSearch:
  URL: https://$OPENSEARCH_HOST`:$OPENSEARCH_PORT
  Username: $OPENSEARCH_USER
  Password: $OPENSEARCH_PASS
  
  How to configure in n8n:
  1. In your workflow, add an HTTP Request node
  2. Set Authentication to "Predefined Credential Type"
  3. Select "Basic Auth"
  4. Click "Create New Credential"
  5. Enter:
     - Name: OpenSearch
     - User: $OPENSEARCH_USER
     - Password: $OPENSEARCH_PASS

LLM Service:
  URL: http://$LLM_HOST`:$LLM_PORT
  
  How to configure in n8n:
  1. In your workflow, add an HTTP Request node
  2. Set Authentication to "None"
  3. Set URL to: http://$LLM_HOST`:$LLM_PORT

Ollama:
  URL: http://$OLLAMA_HOST`:$OLLAMA_PORT
  
  How to configure in n8n:
  1. In your workflow, add an HTTP Request node
  2. Set Authentication to "None"
  3. Set URL to: http://$OLLAMA_HOST`:$OLLAMA_PORT

Crawler API:
  URL: http://$CRAWLER_HOST`:$CRAWLER_PORT
  
  How to configure in n8n:
  1. In your workflow, add an HTTP Request node
  2. Set Authentication to "None"
  3. Set URL to: http://$CRAWLER_HOST`:$CRAWLER_PORT

==========================================
MANUAL CREDENTIAL SETUP IN n8n
==========================================

After importing workflows, you need to configure credentials:

1. Open n8n: $N8N_URL
2. Go to Settings > Credentials
3. Click "Add Credential"
4. For OpenSearch:
   - Type: Basic Auth
   - Name: OpenSearch
   - User: $OPENSEARCH_USER
   - Password: $OPENSEARCH_PASS

For LLM, Ollama, and Crawler:
   - No authentication required
   - Just use the URLs above in HTTP Request nodes

==========================================
WORKFLOW CONFIGURATION
==========================================

In each imported workflow:
1. Open the workflow
2. Find HTTP Request nodes
3. Click on each node
4. If it connects to OpenSearch:
   - Select "OpenSearch" from the credential dropdown
5. If it connects to other services:
   - Verify the URL is correct
   - No credentials needed

"@ | Set-Content -Path $credsFile -NoNewline

    Write-Ok "Service endpoints saved to: $credsFile"
    Write-Host ""
}

# -----------------------------------------------------------------------------
# PREPARE WORKFLOWS
# -----------------------------------------------------------------------------

function Prepare-Workflows {
    Write-Section "STEP 3: PREPARE WORKFLOWS"

    if (-not $script:WORKFLOWS_EXIST) {
        Write-Warn "No workflows found. Skipping preparation."
        return
    }

    $importDir = Join-Path $env:USERPROFILE "n8n-workflows-import"
    Write-Step "Creating import directory: $importDir"
    New-Item -ItemType Directory -Path $importDir -Force | Out-Null

    Write-Step "Copying workflow JSON files..."
    Get-ChildItem -Path $WORKFLOWS_DIR -Filter *.json -ErrorAction SilentlyContinue | `
        Copy-Item -Destination $importDir -Force

    $count = Get-ChildItem -Path $importDir -Filter *.json -ErrorAction SilentlyContinue | Measure-Object | Select-Object -ExpandProperty Count
    Write-Ok "Copied $count workflow(s) to: $importDir"

    if ($count -gt 0) {
        Write-Info "Workflows ready for import:"
        Get-ChildItem -Path $importDir -Filter *.json | ForEach-Object {
            Write-Host "  • $($_.Name)"
        }
    }

    Write-Host ""
    $script:IMPORT_DIR = $importDir
}

# -----------------------------------------------------------------------------
# IMPORT WORKFLOWS INTO CONTAINER
# -----------------------------------------------------------------------------

function Import-Workflows {
    Write-Section "STEP 4: IMPORT WORKFLOWS"

    if (-not $script:WORKFLOWS_EXIST) {
        Write-Info "No workflows to import."
        return
    }

    if (-not (Test-Path $script:IMPORT_DIR)) {
        Write-Warn "Import directory not found; skipping automated import."
        return
    }

    Write-Step "Copying workflows into n8n container..."

    try {
        docker cp $script:IMPORT_DIR "$N8N_CONTAINER:/tmp/workflows" 2>$null
        Write-Ok "Workflows copied into container."
    }
    catch {
        Write-Err "Failed to copy workflows into container: $($_.Exception.Message)"
        Write-Info "You can import workflows manually via the n8n web UI."
        return
    }

    Write-Step "Importing workflows using n8n CLI inside container..."
    try {
        docker exec $N8N_CONTAINER sh -c '
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
        ' | Write-Host

        Write-Ok "Workflow import completed."
    }
    catch {
        Write-Err "Error during workflow import: $($_.Exception.Message)"
        Write-Info "You can still import JSON workflows manually in the n8n UI."
    }

    Write-Host ""
}

# -----------------------------------------------------------------------------
# FINAL INSTRUCTIONS
# -----------------------------------------------------------------------------

function Print-FinalInstructions {
    Write-Section "SETUP COMPLETE"

    Write-Ok "Your n8n instance is configured (account and workflows)."
    Write-Host ""
    Write-Host "Access n8n:"
    Write-Host "  URL: $N8N_URL"
    Write-Host ""

    if ($script:WORKFLOWS_EXIST) {
        Write-Host "Workflows:"
        Write-Host "  ✓ Imported from: $WORKFLOWS_DIR"
        Write-Host ""
    }

    Write-Host "IMPORTANT - Next Steps:"
    Write-Host "  1. Open n8n: $N8N_URL"
    Write-Host "  2. Go to Settings → Credentials"
    Write-Host "  3. Create a 'Basic Auth' credential for OpenSearch:"
    Write-Host "       - Name: OpenSearch"
    Write-Host "       - User: $OPENSEARCH_USER"
    Write-Host "       - Password: $OPENSEARCH_PASS"
    Write-Host "  4. Open each workflow and assign the 'OpenSearch' credential where needed."
    Write-Host "  5. Activate workflows as required."
    Write-Host ""

    Write-Host "Service configuration details file:"
    Write-Host "  $(Join-Path $N8N_DIR "n8n-service-endpoints.txt")"
    Write-Host ""

    Write-Host "Useful commands:"
    Write-Host "  • View n8n logs:  docker logs -f $N8N_CONTAINER"
    Write-Host "  • Restart n8n:    docker restart $N8N_CONTAINER"
    Write-Host "  • Stop n8n:       docker stop $N8N_CONTAINER"
    Write-Host ""

    Write-Warn "Remember to configure credentials in the n8n web UI."
}

# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

Write-Header
Check-Prerequisites
Check-N8nInitialization
Guide-AccountCreation
Save-CredentialsInfo
Prepare-Workflows
Import-Workflows
Print-FinalInstructions

