<#
    Windows n8n setup script

    PowerShell counterpart of `docker/n8n/setup_n8n.sh`.

    Responsibilities:
    - Clean up any existing n8n container
    - Pull the n8n image
    - Run the n8n container on the correct network with the same volumes/env vars
    - Connect n8n to `opensearch_internal_net` and `n8n-network`

    Assumptions:
    - Project root:  $Env:USERPROFILE\SWP-News-Summary
    - n8n data dir: $Env:USERPROFILE\.n8n
    - `config_m2.sh` values are mirrored here in PowerShell-friendly form
#>

param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Load shared Windows config
$configPath = Join-Path (Split-Path $PSScriptRoot -Parent) "windows_config.ps1"
. $configPath

$BaseDir      = $SWP_BaseDir
$CrawlerPath  = $SWP_CrawlerPath
$LlmPath      = $SWP_LlmPath
$DashPath     = Join-Path $SWP_BaseDir "frontend"

$N8nContainer = $SWP_N8nContainer
$DockerNetwork = $SWP_DockerNetwork
$N8nPort      = $SWP_N8nPort
$TimeZone     = $SWP_TimeZone   # adjust in windows_config.ps1 if needed

# These should match docker/llm-service/config.sh
$OllamaContainer = $SWP_OllamaContainer
$OllamaPort      = $SWP_OllamaPort
$OllamaModel     = $SWP_OllamaModel
$OllamaBaseUrl   = "http://$OllamaContainer`:$OllamaPort"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗"
Write-Host "║                       N8N (Windows)                       ║"
Write-Host "╚════════════════════════════════════════════════════════════╝"
Write-Host ""
Write-Host " Base directory: $BaseDir"
Write-Host ""

# Clean up existing container
Write-Host " Cleaning up old n8n container..."
docker stop $N8nContainer 2>$null || true
docker rm   $N8nContainer 2>$null || true
Write-Host ""

Write-Host " Pulling n8n image..."
$image = "n8nio/n8n:latest"
docker pull $image

Write-Host ""
Write-Host " Creating n8n container..."

docker run -d --name $N8nContainer `
    --network $DockerNetwork `
    -p ${N8nPort}:5678 `
    -v "$Env:USERPROFILE\.n8n:/home/node/.n8n" `
    -v "$CrawlerPath:/crawler:rw" `
    -v "$LlmPath:/llm:rw" `
    -v "$DashPath:/dashboard:rw" `
    -e GENERIC_TIMEZONE=$TimeZone `
    -e OLLAMA_BASE_URL=$OllamaBaseUrl `
    -e OLLAMA_MODEL=$OllamaModel `
    -e NODES_EXCLUDE='[]' `
    --restart unless-stopped `
    $image

Write-Host " Waiting for n8n..."
Start-Sleep -Seconds 8

if (-not (docker ps | Select-String -SimpleMatch $N8nContainer)) {
    Write-Host " n8n container failed to start" -ForegroundColor Red
    docker logs $N8nContainer --tail 30
    exit 1
}

Write-Host " n8n running" -ForegroundColor Green
Write-Host ""

Write-Host " Connecting n8n to opensearch_internal_net..."
if (docker network inspect opensearch_internal_net > $null 2>&1) {
    docker network connect opensearch_internal_net $N8nContainer 2>$null || true
} else {
    Write-Host "Network opensearch_internal_net not found, skipping"
}

Write-Host " Connecting n8n to n8n-network..."
docker network connect $DockerNetwork $N8nContainer 2>$null || Write-Host "  (already connected)"

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host " N8N (Windows) setup summary"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host "   Container : $N8nContainer"
Write-Host "   Image     : $image"
Write-Host "   UI URL    : http://localhost:$N8nPort"
Write-Host "   Networks  : n8n-network, opensearch_internal_net (if present)"
Write-Host "   Volumes   : $Env:USERPROFILE\.n8n  -> /home/node/.n8n"
Write-Host "               $CrawlerPath          -> /crawler"
Write-Host "               $LlmPath              -> /llm"
Write-Host "               $DashPath             -> /dashboard"
Write-Host ""

