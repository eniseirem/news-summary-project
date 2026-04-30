<#
    Shared Windows configuration for SWP News Summary stack.

    This file centralizes paths, container names, ports, and credentials
    used by the Windows PowerShell setup scripts, so changes can be made
    in one place.

    Usage (from any Windows setup script):

        $configPath = Join-Path (Split-Path $PSScriptRoot -Parent) "windows_config.ps1"
        . $configPath

    After dot-sourcing, all `$SWP_*` variables below are available.
#>

Set-StrictMode -Version Latest

# --- Base paths ---

$Global:SWP_BaseDir        = Join-Path $Env:USERPROFILE "SWP-News-Summary"
$Global:SWP_N8nDir         = Join-Path $SWP_BaseDir "n8n"
$Global:SWP_CrawlerPath    = Join-Path $SWP_BaseDir "cswspws25-WebCrawlerMain"
$Global:SWP_LlmPath        = Join-Path $SWP_BaseDir "cswspws25-m3-final"
$Global:SWP_FrontendRoot   = Join-Path $SWP_BaseDir "frontend\frontend"   # contains dashboard/
$Global:SWP_DashboardDir   = Join-Path $SWP_FrontendRoot "dashboard"

# --- Docker networks & volumes ---

$Global:SWP_OpenSearchNetwork = "opensearch_internal_net"
$Global:SWP_DockerNetwork     = "n8n-network"
$Global:SWP_OpenSearchVolume  = "opensearch-data"

# --- Container names ---

$Global:SWP_N8nContainer      = "n8n"
$Global:SWP_OllamaContainer   = "ollama"
$Global:SWP_LlmContainer      = "llm-service"
$Global:SWP_CrawlerContainer  = "crawler-api"
$Global:SWP_DashboardContainer = "dashboard"

# --- Ports (host side) ---

$Global:SWP_N8nPort              = 5678
$Global:SWP_OllamaPort           = 11434
$Global:SWP_LlmPort              = 8001
$Global:SWP_CrawlerExternalPort  = 8003
$Global:SWP_CrawlerInternalPort  = 8000
$Global:SWP_DashboardPort        = 8501

# --- Ollama / LLM configuration ---

$Global:SWP_OllamaModel         = "llama3.2:3b"
$Global:SWP_OllamaNumParallel   = 2
$Global:SWP_OllamaContextLength = 8192
$Global:SWP_LlmGitRepo          = "https://gitlab.fokus.fraunhofer.de/dana/cswspws25.git"
$Global:SWP_LlmGitBranch        = "m3-final"

# --- Git branches for other services (same repo) ---
# NOTE: n8n is not cloned – it is the tree that contains bundle_data_setup_windows.ps1 (SWP_N8nDir).

$Global:SWP_RepoUrl             = "https://gitlab.fokus.fraunhofer.de/dana/cswspws25.git"
$Global:SWP_OpensearchPath      = Join-Path $SWP_BaseDir "opensearch"
$Global:SWP_BranchOpensearch    = "Opensearch"
$Global:SWP_BranchCrawler       = "WebCrawlerMain"
$Global:SWP_BranchDashboard     = "frontend/dashboard-ui"

# --- Timezone / misc ---

$Global:SWP_TimeZone            = "Europe/Berlin"

# --- OpenSearch connection (for restore scripts, dashboard, etc.) ---

$Global:SWP_OpenSearchUrl       = "https://localhost:9200"
$Global:SWP_OpenSearchUser      = "admin"
$Global:SWP_OpenSearchPass      = "admin"

