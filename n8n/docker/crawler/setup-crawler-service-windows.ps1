<#
    Windows Crawler API setup script

    PowerShell counterpart of `docker/crawler/setup-crawler-service.sh`.

    Responsibilities:
    - Verify crawler source directory exists
    - Create/replace `crawler-api` container on `n8n-network`
    - Install required Python dependencies inside the container
    - Run the FastAPI app with uvicorn

    Assumptions:
    - Project root:  $Env:USERPROFILE\SWP-News-Summary
    - Crawler path:  $Env:USERPROFILE\SWP-News-Summary\cswspws25-WebCrawlerMain
#>

param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Load shared Windows config
$configPath = Join-Path (Split-Path $PSScriptRoot -Parent) "windows_config.ps1"
. $configPath

$BaseDir          = $SWP_BaseDir
$CrawlerPath      = $SWP_CrawlerPath
$CrawlerContainer = $SWP_CrawlerContainer
$CrawlerPort      = $SWP_CrawlerExternalPort
$InternalPort     = $SWP_CrawlerInternalPort
$DockerNetwork    = $SWP_DockerNetwork

Write-Host ""
Write-Host "Setting up crawler-api (Windows)..."
Write-Host ""

docker info *>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host " Docker daemon is not running" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $CrawlerPath)) {
    Write-Host "✗ Crawler directory not found: $CrawlerPath" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $CrawlerPath "main.py"))) {
    Write-Host "✗ main.py not found in $CrawlerPath" -ForegroundColor Red
    exit 1
}

Write-Host " Ensuring Docker network exists..."
docker network inspect $DockerNetwork *>$null
if ($LASTEXITCODE -ne 0) { docker network create $DockerNetwork *>$null }

Write-Host " Stopping old container..."
docker stop $CrawlerContainer 2>$null || true
docker rm   $CrawlerContainer 2>$null || true

Write-Host " Creating crawler-api container..."
# Use 'cd /crawler && ...' inside container (no -w) so path is not rewritten by some shells
docker run -d `
  --name $CrawlerContainer `
  --network $DockerNetwork `
  -p "${CrawlerPort}:${InternalPort}" `
  -v "$CrawlerPath:/crawler" `
  --restart unless-stopped `
  python:3.11-slim `
  bash -c "cd /crawler && apt-get update > /dev/null 2>&1 && apt-get install -y gcc python3-dev > /dev/null 2>&1 && pip install --no-cache-dir --quiet fastapi 'uvicorn[standard]' requests beautifulsoup4 feedparser newspaper3k lxml lxml_html_clean && sleep 3 && uvicorn main:app --host 0.0.0.0 --port $InternalPort"

Write-Host " Waiting for crawler to start..."
Start-Sleep -Seconds 12

if (docker ps | Select-String -SimpleMatch $CrawlerContainer) {
    Write-Host "✓ Crawler running on n8n-network" -ForegroundColor Green
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Write-Host " Crawler API (Windows) setup summary"
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    Write-Host "   Container : $CrawlerContainer"
    Write-Host "   Network   : $DockerNetwork"
    Write-Host "   Code path : $CrawlerPath -> /crawler"
    Write-Host "   Host URL  : http://localhost:$CrawlerPort/docs"
    Write-Host "   n8n URL   : http://$CrawlerContainer`:$InternalPort"
    Write-Host ""
} else {
    Write-Host "✗ Failed to start crawler-api" -ForegroundColor Red
    docker logs $CrawlerContainer --tail 30
    exit 1
}

Write-Host ""
Write-Host "Done!"
Write-Host ""

