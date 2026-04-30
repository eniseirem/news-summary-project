<#
    Windows Dashboard (Streamlit) setup script

    PowerShell counterpart of `docker/streamlit-frontend/setup-frontend-service.sh`.

    Responsibilities:
    - Verify frontend/dashboard directory exists
    - Ensure Dockerfile and requirements.txt are present (create if needed)
    - Ensure required Docker networks exist
    - Build and run the dashboard container via docker compose

    Assumptions:
    - Project root:       $Env:USERPROFILE\SWP-News-Summary
    - Frontend directory: $Env:USERPROFILE\SWP-News-Summary\frontend\frontend
#>

param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Load shared Windows config
$configPath = Join-Path (Split-Path $PSScriptRoot -Parent) "windows_config.ps1"
. $configPath

$BaseDir       = $SWP_BaseDir
$FrontendDir   = $SWP_FrontendRoot
$DashboardDir  = $SWP_DashboardDir
$DashboardPort = $SWP_DashboardPort
$ContainerName = $SWP_DashboardContainer

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗"
Write-Host "║              DASHBOARD SETUP (Windows)                    ║"
Write-Host "╚════════════════════════════════════════════════════════════╝"
Write-Host ""

if (-not (docker info > $null 2>&1)) {
    Write-Host "✗ Docker is not running" -ForegroundColor Red
    Write-Host "  Please start Docker Desktop and try again"
    exit 1
}

Write-Host "✓ Docker is running" -ForegroundColor Green
Write-Host ""

if (-not (Test-Path $FrontendDir)) {
    Write-Host "✗ Frontend directory not found: $FrontendDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $DashboardDir)) {
    Write-Host "✗ Dashboard directory not found: $DashboardDir" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $DashboardDir "app.py"))) {
    Write-Host "✗ app.py not found in $DashboardDir" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Found dashboard directory and app.py" -ForegroundColor Green
Write-Host ""

# Dockerfile
$dockerfilePath = Join-Path $DashboardDir "Dockerfile"
if (-not (Test-Path $dockerfilePath)) {
@"
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
"@ | Set-Content -LiteralPath $dockerfilePath -Encoding UTF8
    Write-Host "✓ Dockerfile created" -ForegroundColor Green
}

# requirements.txt
$reqPath = Join-Path $DashboardDir "requirements.txt"
if (-not (Test-Path $reqPath)) {
@"
streamlit>=1.28.0
opensearch-py>=2.3.0
pandas>=2.0.0
plotly>=5.17.0
python-dotenv>=1.0.0
requests>=2.31.0
"@ | Set-Content -LiteralPath $reqPath -Encoding UTF8
    Write-Host "✓ requirements.txt created" -ForegroundColor Green
}

# docker-compose.yml
$composePath = Join-Path $FrontendDir "docker-compose.yml"
@"
services:
  dashboard:
    build:
      context: ./dashboard
      dockerfile: Dockerfile
    container_name: ${ContainerName}
    ports:
      - "${DashboardPort}:8501"
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
"@ | Set-Content -LiteralPath $composePath -Encoding UTF8

Write-Host "✓ docker-compose.yml written" -ForegroundColor Green
Write-Host ""

Write-Host "→ Checking required networks..." -ForegroundColor Yellow
if (-not (docker network ls | Select-String -SimpleMatch "opensearch_internal_net")) {
    docker network create opensearch_internal_net
}
if (-not (docker network ls | Select-String -SimpleMatch "n8n-network")) {
    docker network create n8n-network
}

Write-Host "✓ Required networks are present" -ForegroundColor Green
Write-Host ""

Set-Location $FrontendDir

Write-Host "→ Cleaning up existing containers..." -ForegroundColor Yellow
docker compose down --remove-orphans 2>$null || true

Write-Host ""
Write-Host "→ Building and starting dashboard..." -ForegroundColor Yellow
Write-Host "  This may take a few minutes on first run..."
Write-Host ""

docker compose build --no-cache
docker compose up -d

Write-Host "→ Waiting for dashboard to initialize..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

Write-Host "→ Container status:" -ForegroundColor Yellow
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | Select-String -Pattern "NAME|$ContainerName"
Write-Host ""

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host " Dashboard (Windows) setup summary"
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
Write-Host "   Container : $ContainerName"
Write-Host "   Frontend  : $FrontendDir"
Write-Host "   Dashboard : $DashboardDir"
Write-Host "   Compose   : $composePath"
Write-Host "   Networks  : opensearch_internal_net, n8n-network"
Write-Host "   URL       : http://localhost:$DashboardPort"
Write-Host ""

