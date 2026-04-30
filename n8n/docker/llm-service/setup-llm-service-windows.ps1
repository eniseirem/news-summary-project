<#
    Windows LLM service + Ollama setup script

    PowerShell counterpart of `docker/llm-service/setup-llm-service.sh`.

    Responsibilities:
    - Ensure the LLM repo (m3-final branch) is present under cswspws25-m3-final
    - Ensure required data directories exist
    - Start the Ollama container (with configured OLLAMA_NUM_PARALLEL, OLLAMA_CONTEXT_LENGTH)
    - Pull the configured OLLAMA_MODEL
    - Start the llm-service FastAPI container and attach it to n8n-network

    Assumptions:
    - Project root:  $Env:USERPROFILE\SWP-News-Summary
    - LLM_PATH:      $Env:USERPROFILE\SWP-News-Summary\cswspws25-m3-final
    - Docker Desktop is installed and on PATH
#>

param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Load shared Windows config
$configPath = Join-Path (Split-Path $PSScriptRoot -Parent) "windows_config.ps1"
. $configPath

$BaseDir = $SWP_BaseDir
$LlmPath = $SWP_LlmPath

$OllamaContainer = $SWP_OllamaContainer
$LlmContainer    = $SWP_LlmContainer
$DockerNetwork   = $SWP_DockerNetwork

$OllamaPort   = $SWP_OllamaPort
$LlmPort      = $SWP_LlmPort

# These should match docker/llm-service/config.sh
$OllamaModel          = $SWP_OllamaModel
$OllamaNumParallel    = $SWP_OllamaNumParallel
$OllamaContextLength  = $SWP_OllamaContextLength

$GitRepo   = $SWP_LlmGitRepo
$GitBranch = $SWP_LlmGitBranch

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗"
Write-Host "║        LLM SERVICE + OLLAMA SETUP (Windows)               ║"
Write-Host "╚════════════════════════════════════════════════════════════╝"
Write-Host ""

# Ensure LLM repo
if (Test-Path $LlmPath) {
    Write-Host "⚠ LLM directory already exists: $LlmPath"
} else {
    Write-Host "→ Cloning LLM service from Git..."
    Write-Host "  Repository: $GitRepo"
    Write-Host "  Branch:     $GitBranch"
    $parent = Split-Path -Parent $LlmPath
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Force -Path $parent *>$null
    }
    Push-Location $parent
    try {
        git clone -b $GitBranch $GitRepo (Split-Path -Leaf $LlmPath)
    } finally {
        Pop-Location
    }
}

if (-not (Test-Path $LlmPath)) {
    Write-Host "✗ LLM directory not found after clone: $LlmPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $LlmPath "requirements.txt"))) {
    Write-Host "✗ requirements.txt not found in $LlmPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $LlmPath "src\api\main.py"))) {
    Write-Host "✗ src/api/main.py not found in $LlmPath" -ForegroundColor Red
    exit 1
}

Write-Host "→ Creating data directories..."
New-Item -ItemType Directory -Force -Path (Join-Path $LlmPath "data\successes") *>$null
New-Item -ItemType Directory -Force -Path (Join-Path $LlmPath "data\errors")    *>$null
New-Item -ItemType Directory -Force -Path (Join-Path $LlmPath "data\nltk_data") *>$null

Write-Host "→ Ensuring Docker network exists..."
docker network create $DockerNetwork 2>$null || Write-Host "  (network already exists)"

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗"
Write-Host "║                    SETTING UP OLLAMA                      ║"
Write-Host "╚════════════════════════════════════════════════════════════╝"
Write-Host ""

Write-Host "→ Cleaning up old Ollama container..."
docker stop $OllamaContainer 2>$null || true
docker rm   $OllamaContainer 2>$null || true

Write-Host "→ Pulling Ollama image..."
docker pull ollama/ollama:latest

Write-Host "→ Creating Ollama container..."
docker run -d --name $OllamaContainer `
    --network $DockerNetwork `
    -p ${OllamaPort}:11434 `
    -v "$Env:USERPROFILE\.ollama:/root/.ollama" `
    --restart unless-stopped `
    -e OLLAMA_NUM_PARALLEL=$OllamaNumParallel `
    -e OLLAMA_CONTEXT_LENGTH=$OllamaContextLength `
    ollama/ollama:latest

Write-Host "→ Waiting for Ollama..."
Start-Sleep -Seconds 5

if (-not (docker ps | Select-String -SimpleMatch $OllamaContainer)) {
    Write-Host "✗ Ollama failed to start" -ForegroundColor Red
    docker logs $OllamaContainer --tail 50
    exit 1
}

Write-Host "✓ Ollama running" -ForegroundColor Green
Write-Host ""

Write-Host "→ Pulling model: $OllamaModel"
docker exec $OllamaContainer ollama pull $OllamaModel || true
Write-Host "✓ Model ready" -ForegroundColor Green
Write-Host ""

Write-Host "╔════════════════════════════════════════════════════════════╗"
Write-Host "║                   SETTING UP LLM BACKEND                   ║"
Write-Host "╚════════════════════════════════════════════════════════════╝"
Write-Host ""

Write-Host "→ Cleaning up old LLM container..."
docker stop $LlmContainer 2>$null || true
docker rm   $LlmContainer 2>$null || true

Write-Host "→ Creating LLM service container..."
Write-Host "  - Using python:3.10-slim image"
Write-Host "  - Installing build dependencies (gcc, g++)"
Write-Host "  - Connecting to Ollama via container name: http://$OllamaContainer`:$OllamaPort"

docker run -d --name $LlmContainer `
    --network $DockerNetwork `
    -p ${LlmPort}:${LlmPort} `
    -v "$LlmPath:/app" `
    -w /app `
    --restart unless-stopped `
    -e OLLAMA_BASE_URL="http://$OllamaContainer`:$OllamaPort" `
    -e OLLAMA_MODEL=$OllamaModel `
    python:3.10-slim `
    bash -c "
      apt-get update > /dev/null 2>&1 && \
      apt-get install -y gcc g++ build-essential > /dev/null 2>&1 && \
      pip install --no-cache-dir -r requirements.txt > /dev/null 2>&1 && \
      uvicorn src.api.main:app --host 0.0.0.0 --port ${LlmPort}
    "

Write-Host "→ Waiting for LLM service..."
Start-Sleep -Seconds 10

if (-not (docker ps | Select-String -SimpleMatch $LlmContainer)) {
    Write-Host "✗ LLM service failed to start" -ForegroundColor Red
    docker logs $LlmContainer --tail 50
    exit 1
}

Write-Host "✓ LLM service running" -ForegroundColor Green
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host " LLM service (Windows) setup summary"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host "   LLM repo   : $LlmPath  (branch: $GitBranch)"
Write-Host "   Data dirs  : data\successes, data\errors, data\nltk_data"
Write-Host "   Ollama     : container '$OllamaContainer' on $DockerNetwork"
Write-Host "   Model      : $OllamaModel (parallel=$OllamaNumParallel, ctx=$OllamaContextLength)"
Write-Host "   LLM API    : container '$LlmContainer' on $DockerNetwork"
Write-Host "   LLM URL    : http://localhost:$LlmPort/docs"
Write-Host ""

