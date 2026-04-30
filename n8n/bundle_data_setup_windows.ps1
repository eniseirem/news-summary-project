<#
    SWP News Summary - Complete Setup (Windows) — single entry point

    This is the only script you need for a full setup. Do not run complete_setup
    or bundle_setup separately; this script handles everything.

    What it does:
    - Moves n8n-pipeline clone under SWP-News-Summary as n8n if needed (auto-detects folder name)
    - Clones missing service repos (opensearch, crawler, LLM, dashboard)
    - Fetches n8n + OpenSearch bundle archives from Google Drive (or prompts manual)
    - Restores n8n data into .n8n and OpenSearch data into opensearch-data volume
    - Ensures OpenSearch indices (e.g. clusters) exist via restore_indices fallback
    - Creates Docker networks/volumes and starts all containers

    Assumptions:
    - Project root:  $Env:USERPROFILE\SWP-News-Summary
    - n8n dir:       ...\SWP-News-Summary\n8n
    - Bundle dir:    n8n\bundle
    - Docker Desktop installed, `docker` on PATH

    Usage:  .\bundle_data_setup_windows.ps1
    Dry run:  .\bundle_data_setup_windows.ps1 -DryRun
#>

param(
    [switch] $DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Load shared Windows configuration (paths, ports, container names, etc.)
$windowsConfigPath = Join-Path $PSScriptRoot "docker\windows_config.ps1"
if (Test-Path $windowsConfigPath) {
    . $windowsConfigPath
}

function Write-Step { param([string]$Msg) Write-Host "▶ $Msg" -ForegroundColor Yellow }
function Write-Ok   { param([string]$Msg) Write-Host "✓ $Msg" -ForegroundColor Green }
function Write-Err  { param([string]$Msg) Write-Host "✗ $Msg" -ForegroundColor Red }
function Write-Info { param([string]$Msg) Write-Host "ℹ $Msg" -ForegroundColor Cyan }

function Run-Cmd {
    param(
        [Parameter(Mandatory=$true)][string] $Command
    )
    if ($DryRun) {
        Write-Host "[DRY RUN] $Command" -ForegroundColor Yellow
    } else {
        & powershell -NoProfile -Command $Command
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed: $Command"
        }
    }
}

$BaseDir  = if ($SWP_BaseDir) { $SWP_BaseDir } else { Join-Path $Env:USERPROFILE "SWP-News-Summary" }
$N8nDir   = if ($SWP_N8nDir)  { $SWP_N8nDir  } else { Join-Path $BaseDir "n8n" }
$BundleDir = if ($Env:BUNDLE_DIR -and $Env:BUNDLE_DIR.Trim()) { $Env:BUNDLE_DIR } else { Join-Path $N8nDir "bundle" }
$CloneDirName = "cswspws25"

$OpenSearchNetwork = if ($SWP_OpenSearchNetwork) { $SWP_OpenSearchNetwork } else { "opensearch_internal_net" }
$N8nNetwork        = if ($SWP_DockerNetwork)     { $SWP_DockerNetwork     } else { "n8n-network" }
$OpenSearchVolume  = if ($SWP_OpenSearchVolume)  { $SWP_OpenSearchVolume  } else { "opensearch-data" }

function Move-CloneUnderSwp {
    # If this script runs from a folder that looks like the n8n-pipeline clone (has this script or docker\n8n),
    # and it sits as a sibling of SWP-News-Summary, offer to move it under SWP-News-Summary and rename as n8n.
    # Auto-detects the folder name (no need for it to be "cswspws25").
    $dirScript = $PSScriptRoot
    $scriptDirName = Split-Path -Leaf $dirScript
    $parent = Split-Path -Parent $dirScript
    $swpDir = Join-Path $parent "SWP-News-Summary"
    $targetN8n = Join-Path $swpDir "n8n"

    if ($dirScript -ceq $targetN8n) { return }

    # Must look like the n8n-pipeline repo (any folder name)
    $hasSetup = Test-Path (Join-Path $dirScript "bundle_data_setup_windows.ps1")
    $hasDockerN8n = Test-Path (Join-Path $dirScript "docker\n8n")
    if (-not $hasSetup -and -not $hasDockerN8n) { return }

    # Only offer move if SWP-News-Summary exists as sibling and n8n doesn't exist there yet
    if (-not (Test-Path $swpDir)) { return }
    if (Test-Path $targetN8n) {
        Write-Info "SWP-News-Summary\n8n already exists; not moving $scriptDirName."
        return
    }

    Write-Host ""
    Write-Info "Found n8n-pipeline clone '$scriptDirName' at same level as SWP-News-Summary."
    Write-Host "  Current location: $dirScript"
    Write-Host "  Target location:  $targetN8n"
    Write-Host ""
    $ans = Read-Host "Move '$scriptDirName' under SWP-News-Summary and rename as n8n? [y/N]"
    if ($ans -notmatch '^[Yy]$') {
        Write-Info "Skipping move. Run this script from SWP-News-Summary\n8n for normal setup."
        return
    }

    if ($DryRun) {
        Write-Host "[DRY RUN] New-Item -ItemType Directory -Force -Path `"$swpDir`"; Move-Item `"$dirScript`" `"$targetN8n`"" -ForegroundColor Yellow
        Write-Host "[DRY RUN] Then re-run: cd `"$targetN8n`"; .\bundle_data_setup_windows.ps1" -ForegroundColor Yellow
        return
    }

    Write-Step "Creating $swpDir..."
    New-Item -ItemType Directory -Force -Path $swpDir *>$null
    Write-Step "Moving $dirScript -> $targetN8n..."
    Move-Item -LiteralPath $dirScript -Destination $targetN8n
    Write-Ok "Done. Re-run the setup from the new location:"
    Write-Host ""
    Write-Host "  cd `"$targetN8n`""
    Write-Host "  .\bundle_data_setup_windows.ps1"
    Write-Host ""
    exit 0
}

function Check-Docker {
    Write-Step "Checking Docker daemon..."
    try {
        docker info *>$null
    } catch {
        Write-Err "Docker is not running. Start Docker Desktop and re-run this script."
        exit 1
    }
    Write-Ok "Docker is running."
}

function Ensure-Network {
    param([string]$Name)
    Write-Step "Ensuring Docker network '$Name' exists..."
    $exists = docker network ls --format "{{.Name}}" | Where-Object { $_ -eq $Name }
    if ($exists) {
        Write-Ok "Network '$Name' already exists."
    } else {
        if ($DryRun) {
            Write-Host "[DRY RUN] docker network create `"$Name`"" -ForegroundColor Yellow
        } else {
            docker network create "$Name" *>$null
        }
        Write-Ok "Network '$Name' created."
    }
}

function Ensure-Volume {
    param([string]$Name)
    Write-Step "Ensuring Docker volume '$Name' exists..."
    $exists = docker volume ls --format "{{.Name}}" | Where-Object { $_ -eq $Name }
    if ($exists) {
        Write-Ok "Volume '$Name' already exists."
    } else {
        if ($DryRun) {
            Write-Host "[DRY RUN] docker volume create `"$Name`"" -ForegroundColor Yellow
        } else {
            docker volume create "$Name" *>$null
        }
        Write-Ok "Volume '$Name' created."
    }
}

function Restore-N8nData {
    $backupDir = Join-Path $N8nDir "n8n-backup"
    $tarSrc    = Join-Path $BundleDir "n8n-data.tar.gz"
    $target    = Join-Path $Env:USERPROFILE ".n8n"

    if (Test-Path $backupDir) {
        Write-Step "Restoring n8n data from directory backup: $backupDir -> $target"
        if (Test-Path $target) {
            $backupName = ".n8n_backup_{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
            $backupPath = Join-Path $Env:USERPROFILE $backupName
            Write-Step "Backing up existing .n8n to $backupPath..."
            if ($DryRun) {
                Write-Host "[DRY RUN] Move-Item '$target' '$backupPath'" -ForegroundColor Yellow
            } else {
                Move-Item -LiteralPath $target -Destination $backupPath
            }
        }
        if (-not $DryRun) {
            New-Item -ItemType Directory -Force -Path $target *>$null
            Copy-Item -Path (Join-Path $backupDir "*") -Destination $target -Recurse -Force
        } else {
            Write-Host "[DRY RUN] Copy-Item '$backupDir\*' '$target'" -ForegroundColor Yellow
        }
        Write-Ok "n8n data restored from n8n-backup directory (or simulated in DRY-RUN)."
        return
    }

    if (Test-Path $tarSrc) {
        Write-Step "Restoring n8n data from tarball: $tarSrc -> $target"
        if (Test-Path $target) {
            $backupName = ".n8n_backup_{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss")
            $backupPath = Join-Path $Env:USERPROFILE $backupName
            Write-Step "Backing up existing .n8n to $backupPath..."
            if ($DryRun) {
                Write-Host "[DRY RUN] Move-Item '$target' '$backupPath'" -ForegroundColor Yellow
            } else {
                Move-Item -LiteralPath $target -Destination $backupPath
            }
        }
        if ($DryRun) {
            Write-Host "[DRY RUN] Extract $tarSrc into $target (strip leading .n8n/)" -ForegroundColor Yellow
        } else {
            New-Item -ItemType Directory -Force -Path $target *>$null
            # Use a temporary busybox container to extract tar into a mounted folder
            docker run --rm `
                -v "$target:/data" `
                -v "$BundleDir:/backup:ro" `
                busybox sh -c "tar xzf /backup/n8n-data.tar.gz -C /data --strip-components=1"
        }
        Write-Ok "n8n data restored from n8n-data.tar.gz (or simulated in DRY-RUN)."
        return
    }

    Write-Info "No n8n-backup directory or n8n-data.tar.gz found – skipping n8n data restore."
}

function Restore-OpenSearchData {
    $tarSrc = Join-Path $BundleDir "opensearch-data.tar.gz"
    if (-not (Test-Path $tarSrc)) {
        Write-Info "No opensearch-data.tar.gz found in $BundleDir – skipping OpenSearch data restore."
        return
    }

    Write-Step "Restoring OpenSearch data from $tarSrc into $OpenSearchVolume volume..."

    if ($DryRun) {
        Write-Host "[DRY RUN] docker run --rm -v $OpenSearchVolume:/data -v '$BundleDir':/backup:ro busybox sh -c 'rm -rf /data/* && tar xzf /backup/opensearch-data.tar.gz -C /data'" -ForegroundColor Yellow
        Write-Ok "OpenSearch data restored from tar (or simulated in DRY-RUN)."
        return
    }

    try {
        $cmd = "rm -rf /data/* && tar xzf /backup/opensearch-data.tar.gz -C /data"
        & docker run --rm `
            -v "$OpenSearchVolume:/data" `
            -v "$BundleDir:/backup:ro" `
            busybox sh -c "$cmd"
        if ($LASTEXITCODE -ne 0) { throw "Docker/tar exited with code $LASTEXITCODE" }
        Write-Ok "OpenSearch data restored from tar."
    } catch {
        Write-Host ""
        Write-Host "✗ OpenSearch data read was unsuccessful (e.g. tar: invalid magic / short read)." -ForegroundColor Red
        Write-Info "The bundle file may be corrupted or an HTML page from Google Drive. Replace $tarSrc with a valid opensearch-data.tar.gz and re-run this script to restore."
        Write-Host ""
    }
}

function Start-OpenSearchStack {
    $composeDir  = Join-Path $BaseDir "opensearch"
    $composeFile = Join-Path $composeDir "docker-compose.yml"

    if (-not (Test-Path $composeFile)) {
        Write-Info "No opensearch/docker-compose.yml found – skipping OpenSearch stack."
        return
    }

    Write-Step "Starting OpenSearch stack via docker compose..."
    if ($DryRun) {
        Write-Host "[DRY RUN] cd `"$composeDir`"; docker compose up -d" -ForegroundColor Yellow
    } else {
        Push-Location $composeDir
        try {
            docker compose up -d
        } finally {
            Pop-Location
        }
    }
    Write-Ok "OpenSearch stack started (or simulated in DRY-RUN)."
}

function Ensure-ServiceRepos {
    # opensearch, crawler, LLM, dashboard (n8n is the tree containing this script – not cloned)
    $missing = @()
    if (-not (Test-Path $SWP_OpensearchPath)) { $missing += "opensearch" }
    if (-not (Test-Path $SWP_CrawlerPath))   { $missing += "crawler" }
    if (-not (Test-Path $SWP_LlmPath))       { $missing += "llm" }
    if (-not (Test-Path $SWP_FrontendRoot))  { $missing += "dashboard" }

    if ($missing.Count -eq 0) {
        Write-Info "All service directories already exist (opensearch/crawler/llm/dashboard). No cloning needed."
        return
    }

    Write-Host ""
    Write-Info "The following directories are missing and can be cloned from $SWP_RepoUrl:"
    foreach ($svc in $missing) {
        switch ($svc) {
            "opensearch" { Write-Host "  - opensearch -> $SWP_OpensearchPath (branch: $SWP_BranchOpensearch)" }
            "crawler"    { Write-Host "  - crawler    -> $SWP_CrawlerPath   (branch: $SWP_BranchCrawler)" }
            "llm"        { Write-Host "  - llm        -> $SWP_LlmPath       (branch: $SWP_LlmGitBranch)" }
            "dashboard"  { Write-Host "  - dashboard  -> $SWP_FrontendRoot  (branch: $SWP_BranchDashboard)" }
        }
    }
    Write-Host ""
    $ans = Read-Host "Clone missing repositories now? [y/N]"
    if ($ans -notmatch '^[Yy]$') {
        Write-Info "Skipping cloning of service repositories."
        return
    }

    foreach ($svc in $missing) {
        switch ($svc) {
            "opensearch" {
                Write-Step "Cloning opensearch (branch: $SWP_BranchOpensearch) into $SWP_OpensearchPath"
                if (-not $DryRun) {
                    $parent = Split-Path -Parent $SWP_OpensearchPath
                    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent *>$null }
                    Push-Location $parent
                    try {
                        git clone --single-branch --branch $SWP_BranchOpensearch $SWP_RepoUrl (Split-Path -Leaf $SWP_OpensearchPath)
                    } finally {
                        Pop-Location
                    }
                } else {
                    Write-Host "[DRY RUN] git clone --single-branch --branch $SWP_BranchOpensearch $SWP_RepoUrl $SWP_OpensearchPath" -ForegroundColor Yellow
                }
            }
            "crawler" {
                Write-Step "Cloning crawler (branch: $SWP_BranchCrawler) into $SWP_CrawlerPath"
                if (-not $DryRun) {
                    $parent = Split-Path -Parent $SWP_CrawlerPath
                    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent *>$null }
                    Push-Location $parent
                    try {
                        git clone --single-branch --branch $SWP_BranchCrawler $SWP_RepoUrl (Split-Path -Leaf $SWP_CrawlerPath)
                    } finally {
                        Pop-Location
                    }
                } else {
                    Write-Host "[DRY RUN] git clone --single-branch --branch $SWP_BranchCrawler $SWP_RepoUrl $SWP_CrawlerPath" -ForegroundColor Yellow
                }
            }
            "llm" {
                Write-Step "Cloning llm (branch: $SWP_LlmGitBranch) into $SWP_LlmPath"
                if (-not $DryRun) {
                    $parent = Split-Path -Parent $SWP_LlmPath
                    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent *>$null }
                    Push-Location $parent
                    try {
                        git clone --single-branch --branch $SWP_LlmGitBranch $SWP_LlmGitRepo (Split-Path -Leaf $SWP_LlmPath)
                    } finally {
                        Pop-Location
                    }
                } else {
                    Write-Host "[DRY RUN] git clone --single-branch --branch $SWP_LlmGitBranch $SWP_LlmGitRepo $SWP_LlmPath" -ForegroundColor Yellow
                }
            }
            "dashboard" {
                Write-Step "Cloning dashboard (branch: $SWP_BranchDashboard) into $SWP_FrontendRoot"
                if (-not $DryRun) {
                    $parent = Split-Path -Parent $SWP_FrontendRoot
                    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent *>$null }
                    Push-Location $parent
                    try {
                        git clone --single-branch --branch $SWP_BranchDashboard $SWP_RepoUrl (Split-Path -Leaf $SWP_FrontendRoot)
                    } finally {
                        Pop-Location
                    }
                } else {
                    Write-Host "[DRY RUN] git clone --single-branch --branch $SWP_BranchDashboard $SWP_RepoUrl $SWP_FrontendRoot" -ForegroundColor Yellow
                }
            }
        }
    }
}

function Ensure-RestoreIndicesScript {
    $scriptDir = Join-Path $BaseDir "opensearch\scripts"
    if (-not (Test-Path $scriptDir)) { return }
    $psPath  = Join-Path $scriptDir "restore_indices.ps1"
    $shPath  = Join-Path $scriptDir "restore_indices.sh"
    $cmdPath = Join-Path $scriptDir "restore_indices.cmd"
    $created = $false

    if (-not (Test-Path $psPath)) {
        Write-Step "Creating restore_indices.ps1 so OpenSearch indices can be created..."
        $psContent = @'
# Restore OpenSearch indices from JSON files (Windows).
$ErrorActionPreference = "Stop"
$OPENSEARCH_URL = if ($env:OPENSEARCH_URL) { $env:OPENSEARCH_URL } else { "https://localhost:9200" }
$OPENSEARCH_USER = if ($env:OPENSEARCH_USER) { $env:OPENSEARCH_USER } else { "admin" }
$OPENSEARCH_PASS = if ($env:OPENSEARCH_PASS) { $env:OPENSEARCH_PASS } else { "admin" }
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$INDICES_DIR = Join-Path (Split-Path -Parent $ScriptDir) "indices"
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
[System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
$pair = "${OPENSEARCH_USER}:${OPENSEARCH_PASS}"
$bytes = [System.Text.Encoding]::ASCII.GetBytes($pair)
$base64 = [System.Convert]::ToBase64String($bytes)
$headers = @{ Authorization = "Basic $base64"; "Content-Type" = "application/json" }
Write-Host "Waiting for OpenSearch at $OPENSEARCH_URL..."
while ($true) {
    try {
        $r = Invoke-WebRequest -Uri $OPENSEARCH_URL -Headers @{ Authorization = "Basic $base64" } -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300) { break }
    } catch { Start-Sleep -Seconds 2 }
}
Write-Host "OpenSearch is up."; Write-Host ""; Write-Host "Using indices directory: $INDICES_DIR"; Write-Host ""
if (-not (Test-Path -LiteralPath $INDICES_DIR -PathType Container)) { Write-Host "Error: Indices directory not found: $INDICES_DIR" -ForegroundColor Red; exit 1 }
Get-ChildItem -Path $INDICES_DIR -Filter "*.json" -File | ForEach-Object {
    $indexName = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
    Write-Host "Creating index: $indexName"
    $body = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8
    $uri = "$OPENSEARCH_URL/$indexName"
    try {
        $response = Invoke-WebRequest -Uri $uri -Method Put -Headers $headers -Body $body -UseBasicParsing -TimeoutSec 30
        if ([int]$response.StatusCode -eq 200 -or [int]$response.StatusCode -eq 201) { Write-Host "  [OK] Created successfully" -ForegroundColor Green }
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $reader.BaseStream.Position = 0
        $responseBody = $reader.ReadToEnd()
        if ($code -eq 400 -and $responseBody -match "resource_already_exists_exception") { Write-Host "  [OK] Already exists" -ForegroundColor Yellow }
        else { Write-Host "  [FAIL] HTTP $code" -ForegroundColor Red }
    }
    Write-Host ""
}
Write-Host "All indices processed."
'@
        Set-Content -LiteralPath $psPath -Value $psContent -Encoding UTF8
        $created = $true
    }

    if (-not (Test-Path $shPath)) {
        Write-Step "Creating restore_indices.sh so OpenSearch indices can be created..."
        $shContent = @'
#!/bin/bash
set -e
OPENSEARCH_URL="${OPENSEARCH_URL:-https://localhost:9200}"
OPENSEARCH_USER="${OPENSEARCH_USER:-admin}"
OPENSEARCH_PASS="${OPENSEARCH_PASS:-admin}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INDICES_DIR="${SCRIPT_DIR}/../indices"
echo "Waiting for OpenSearch at $OPENSEARCH_URL..."
while ! curl -k -s -u "${OPENSEARCH_USER}:${OPENSEARCH_PASS}" "${OPENSEARCH_URL}" >/dev/null 2>&1; do sleep 2; done
echo "OpenSearch is up."; echo ""
[ -d "$INDICES_DIR" ] || { echo "Error: Indices dir not found: $INDICES_DIR"; exit 1; }
for json_file in "$INDICES_DIR"/*.json; do
  [ -f "$json_file" ] || continue
  index_name=$(basename "$json_file" .json)
  echo "Creating index: $index_name"
  index_def=$(cat "$json_file")
  echo "$index_def" | python3 -c "import sys, json; data=json.load(sys.stdin); exit(0 if 'mappings' in data else 1)" 2>/dev/null || index_def=$(echo "$index_def" | python3 -c "import sys, json; data=json.load(sys.stdin); print(json.dumps(list(data.values())[0]))" 2>/dev/null)
  [ -n "$index_def" ] || index_def=$(jq -c '.[]' "$json_file" 2>/dev/null || true)
  [ -n "$index_def" ] || { echo "  ✗ Could not extract"; continue; }
  response=$(curl -k -s -w "\n%{http_code}" -u "${OPENSEARCH_USER}:${OPENSEARCH_PASS}" -X PUT "${OPENSEARCH_URL}/${index_name}" -H "Content-Type: application/json" -d "$index_def")
  http_code=$(echo "$response" | tail -n1)
  body=$(echo "$response" | sed '$d')
  if [ "$http_code" = "200" ] || [ "$http_code" = "201" ]; then echo "  ✓ Created"; elif [ "$http_code" = "400" ] && echo "$body" | grep -q "resource_already_exists_exception"; then echo "  ⚠ Already exists"; else echo "  ✗ HTTP $http_code"; fi
  echo ""
done
echo "Indices processed."
curl -k -s -u "${OPENSEARCH_USER}:${OPENSEARCH_PASS}" "${OPENSEARCH_URL}/_cat/indices?v" | grep -v "^\." || true
'@
        Set-Content -LiteralPath $shPath -Value $shContent -Encoding UTF8 -NoNewline:$false
        $created = $true
    }

    if (-not (Test-Path $cmdPath)) {
        Write-Step "Creating restore_indices.cmd so OpenSearch indices can be created..."
        $cmdContent = @'
@echo off
setlocal
REM Restore OpenSearch indices from opensearch/indices/*.json (Windows).
REM For better error handling use: powershell -ExecutionPolicy Bypass -File "%~dp0restore_indices.ps1"
if not defined OPENSEARCH_URL set OPENSEARCH_URL=https://localhost:9200
if not defined OPENSEARCH_USER set OPENSEARCH_USER=admin
if not defined OPENSEARCH_PASS set OPENSEARCH_PASS=admin
set INDICES_DIR=%~dp0..\indices
if not exist "%INDICES_DIR%" ( echo Error: Indices directory not found: %INDICES_DIR%; exit /b 1 )
echo Waiting for OpenSearch at %OPENSEARCH_URL%...
:wait
curl -k -s -u %OPENSEARCH_USER%:%OPENSEARCH_PASS% %OPENSEARCH_URL% >nul 2>&1
if errorlevel 1 ( timeout /t 2 >nul; goto wait )
echo OpenSearch is up. & echo. & echo Using indices directory: %INDICES_DIR% & echo.
for %%f in ("%INDICES_DIR%\*.json") do ( echo Creating index: %%~nf & curl -k -s -u %OPENSEARCH_USER%:%OPENSEARCH_PASS% -X PUT "%OPENSEARCH_URL%/%%~nf" -H "Content-Type: application/json" --data-binary "@%%f" & echo. )
echo All indices processed.
'@
        Set-Content -LiteralPath $cmdPath -Value $cmdContent -Encoding ASCII
        $created = $true
    }

    if ($created) { Write-Ok "restore_indices.ps1 / .sh / .cmd created." }
}

function Run-RestoreIndices {
    $scriptDir  = Join-Path $BaseDir "opensearch\scripts"
    $psPath     = Join-Path $scriptDir "restore_indices.ps1"
    $cmdPath    = Join-Path $scriptDir "restore_indices.cmd"
    Ensure-RestoreIndicesScript
    if (-not (Test-Path $psPath) -and -not (Test-Path $cmdPath)) {
        Write-Info "No restore_indices.ps1/cmd found – skipping index creation."
        return
    }
    Write-Step "Running restore_indices (Windows) to create OpenSearch indices from JSON files..."
    if ($DryRun) {
        Write-Host "[DRY RUN] restore_indices.ps1 or .cmd" -ForegroundColor Yellow
    } else {
        if (Test-Path $psPath) {
            powershell -NoProfile -ExecutionPolicy Bypass -File $psPath
        } else {
            & $cmdPath
        }
    }
    Write-Ok "restore_indices (Windows) completed (or simulated in DRY-RUN)."
}

function Start-N8n {
    $script = Join-Path $N8nDir "docker\n8n\setup_n8n_windows.ps1"
    if (-not (Test-Path $script)) {
        Write-Info "No setup_n8n_windows.ps1 found at $script – skipping n8n."
        return
    }
    Write-Step "Running n8n Windows setup script..."
    if ($DryRun) {
        Write-Host "[DRY RUN] powershell -ExecutionPolicy Bypass -File `"$script`"" -ForegroundColor Yellow
    } else {
        powershell -ExecutionPolicy Bypass -File $script
    }
    Write-Ok "n8n Windows setup script finished (or simulated in DRY-RUN)."
}

function Start-LLMAndOllama {
    $script = Join-Path $N8nDir "docker\llm-service\setup-llm-service-windows.ps1"
    if (-not (Test-Path $script)) {
        Write-Info "No LLM/Ollama Windows setup script found at $script – skipping."
        return
    }
    Write-Step "Running LLM + Ollama Windows setup script..."
    if ($DryRun) {
        Write-Host "[DRY RUN] powershell -ExecutionPolicy Bypass -File `"$script`"" -ForegroundColor Yellow
    } else {
        powershell -ExecutionPolicy Bypass -File $script
    }
    Write-Ok "LLM + Ollama Windows setup script finished (or simulated in DRY-RUN)."
}

function Start-CrawlerApi {
    $script = Join-Path $N8nDir "docker\crawler\setup-crawler-service-windows.ps1"
    if (-not (Test-Path $script)) {
        Write-Info "No crawler Windows setup script found at $script – skipping."
        return
    }
    Write-Step "Running crawler-api Windows setup script..."
    if ($DryRun) {
        Write-Host "[DRY RUN] powershell -ExecutionPolicy Bypass -File `"$script`"" -ForegroundColor Yellow
    } else {
        powershell -ExecutionPolicy Bypass -File $script
    }
    Write-Ok "crawler-api Windows setup script finished (or simulated in DRY-RUN)."
}

function Start-Dashboard {
    $script = Join-Path $N8nDir "docker\streamlit-frontend\setup-frontend-service-windows.ps1"
    if (-not (Test-Path $script)) {
        Write-Info "No dashboard Windows setup script found at $script – skipping."
        return
    }
    Write-Step "Running dashboard Windows setup script..."
    if ($DryRun) {
        Write-Host "[DRY RUN] powershell -ExecutionPolicy Bypass -File `"$script`"" -ForegroundColor Yellow
    } else {
        powershell -ExecutionPolicy Bypass -File $script
    }
    Write-Ok "dashboard Windows setup script finished (or simulated in DRY-RUN)."
}

Write-Host ""
Write-Host "╔════════════════════════════════════════════════════════════╗"
Write-Host "║     SWP NEWS SUMMARY - COMPLETE SETUP (SINGLE ENTRY)        ║"
Write-Host "╚════════════════════════════════════════════════════════════╝"
Write-Host ""
Write-Host "  Base directory: $BaseDir"
Write-Host "  n8n directory : $N8nDir"
Write-Host "  Bundle dir    : $BundleDir"
Write-Host ""

if ($DryRun) {
    Write-Info "Running in DRY-RUN mode (no changes will be applied)."
    Write-Host ""
}

Check-Docker

# ---------------------------------------------------------------------------
# Step: Move n8n-pipeline clone under SWP-News-Summary as n8n
# ---------------------------------------------------------------------------
# When the project is cloned, it may sit at the same level as SWP-News-Summary
# (folder name is auto-detected, e.g. cswspws25 or any other name). We move it
# under SWP-News-Summary and rename to n8n *before* fetching or restoring, so
# bundle paths resolve correctly (e.g. n8n\bundle\n8n-data.tar.gz). If we move, we exit and ask
# the user to re-run from the new location.
Move-CloneUnderSwp

Ensure-ServiceRepos

# ---------------------------------------------------------------------------
# Optionally fetch bundle archives from Google Drive if missing
# ---------------------------------------------------------------------------
$n8nTar = Join-Path $BundleDir "n8n-data.tar.gz"
$osTar  = Join-Path $BundleDir "opensearch-data.tar.gz"
$fetchScriptWin = Join-Path $N8nDir "bundle_fetch_backups_windows.ps1"
if ((-not (Test-Path $n8nTar) -or -not (Test-Path $osTar)) -and (Test-Path $fetchScriptWin)) {
    Write-Host ""
    Write-Info "Bundle archives (n8n-data/opensearch-data) not found in $BundleDir."
    $ans = Read-Host "Fetch n8n + OpenSearch backups from Google Drive now? [y/N]"
    if ($ans -match '^[Yy]$') {
        if ($DryRun) {
            Write-Host "[DRY RUN] Would run: powershell -ExecutionPolicy Bypass -File `"$fetchScriptWin`"" -ForegroundColor Yellow
        } else {
            Write-Step "Fetching bundle archives via bundle_fetch_backups_windows.ps1..."
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $fetchScriptWin
        }
    } else {
        Write-Info "Skipping Google Drive fetch for bundle archives."
    }
}

# If bundle files are still missing after fetch, show manual guide, open Drive, and continue (do not exit)
if (-not (Test-Path $n8nTar) -or -not (Test-Path $osTar)) {
    Write-Host ""
    Write-Info "Bundle archives still missing. Opening Google Drive for manual download."
    $n8nDriveUrl   = "https://drive.google.com/file/d/15jpeU-q4TmAT6QJkGxd75uNrp9vktkim/view"
    $osDriveUrl    = "https://drive.google.com/file/d/1VVVi7rvpqzDWAkHmybXmMJM2lRjhlaJd/view"
    try {
        Start-Process $n8nDriveUrl
        Start-Sleep -Seconds 1
        Start-Process $osDriveUrl
    } catch { Write-Host "  (Could not open browser: $_)" }
    Write-Host ""
    Write-Host "Instructions (bundle_data_setup):"
    Write-Host "  1. In the opened tabs, download n8n-data.tar.gz and opensearch-data.tar.gz from Google Drive."
    Write-Host "  2. Place both files inside the bundle folder: $BundleDir"
    Write-Host "  3. For n8n: run this script again and choose to restore n8n data when prompted (or copy into $Env:USERPROFILE\.n8n)."
    Write-Host "  4. For OpenSearch: run this script again and choose to restore OpenSearch when prompted."
    Write-Host "  5. Then start containers when prompted."
    Write-Host ""
    Write-Info "Continuing with networks/volumes and container startup (restore will be skipped if files absent)."
    Write-Host ""
}

Ensure-Network $OpenSearchNetwork
Ensure-Network $N8nNetwork
Ensure-Volume  $OpenSearchVolume
Write-Host ""

# Restore n8n and OpenSearch from bundle when present (same flow for both)
# Note: The n8n container uses a bind mount of .n8n (host) -> /home/node/.n8n (container).
# So the image is not the reason data might not show — we restore into the same path the
# container reads. If n8n is already running, we must restart it so it picks up the new data.
$n8nBackupDir = Join-Path $N8nDir "n8n-backup"
$n8nContainerName = "n8n"
if (Test-Path $n8nTar) -or (Test-Path $n8nBackupDir) {
    Write-Host ""
    $n8nAnswer = Read-Host "Restore n8n data from bundle into .n8n (overwrites current after backup)? [y/N]"
    if ($n8nAnswer -match '^[Yy]$') {
        Restore-N8nData
        if (-not $DryRun) {
            $running = docker ps --format "{{.Names}}" | Where-Object { $_ -eq $n8nContainerName }
            if ($running) {
                Write-Step "Restarting n8n container so it picks up the restored data..."
                docker restart $n8nContainerName
                Write-Ok "n8n restarted. Open the UI to see restored workflows."
            }
        }
    } else {
        Write-Info "Skipping n8n data restore."
    }
}

$openSearchTar = Join-Path $BundleDir "opensearch-data.tar.gz"
if (Test-Path $openSearchTar) {
    Write-Host ""
    $answer = Read-Host "Restore OpenSearch data from bundle into $OpenSearchVolume volume (overwrites current contents)? [y/N]"
    if ($answer -match '^[Yy]$') {
        Restore-OpenSearchData
    } else {
        Write-Info "Skipping OpenSearch data restore."
    }
}

# Fallback: ensure OpenSearch indices (e.g. clusters) exist when tar restore was skipped/failed
Ensure-RestoreIndicesScript
$osContainer = "opensearch"
$restoreIndicesPs1 = Join-Path $BaseDir "opensearch\scripts\restore_indices.ps1"
$restoreIndicesCmd = Join-Path $BaseDir "opensearch\scripts\restore_indices.cmd"
$osRunning = docker ps --format "{{.Names}}" | Where-Object { $_ -eq $osContainer }
if (-not $DryRun -and $osRunning -and (Test-Path $restoreIndicesPs1 -or Test-Path $restoreIndicesCmd)) {
    Write-Step "Ensuring OpenSearch indices exist (fallback for missing/failed data restore)..."
    try {
        if (Test-Path $restoreIndicesPs1) {
            powershell -NoProfile -ExecutionPolicy Bypass -File $restoreIndicesPs1
        } else {
            & $restoreIndicesCmd
        }
        Write-Ok "Indices (e.g. clusters) created or already exist."
    } catch {
        Write-Info "restore_indices had issues (indices may already exist)."
    }
}

Write-Host ""
$startAnswer = Read-Host "Start containers (OpenSearch, n8n, LLM, crawler, dashboard) now? [y/N]"
if ($startAnswer -match '^[Yy]$') {
    Start-OpenSearchStack
    Run-RestoreIndices
    Start-N8n
    # Ensure n8n can resolve "opensearch" (fix getaddrinfo ENOTFOUND in workflows)
    $n8nRunning = docker ps --format "{{.Names}}" | Where-Object { $_ -eq "n8n" }
    if (-not $DryRun -and $n8nRunning) {
        docker network create $OpenSearchNetwork 2>$null
        docker network connect $OpenSearchNetwork n8n 2>$null
        if ($LASTEXITCODE -eq 0) { Write-Ok "n8n connected to $OpenSearchNetwork (opensearch hostname will resolve)." }
    }
    Start-LLMAndOllama
    Start-CrawlerApi
    Start-Dashboard
} else {
    Write-Info "Skipping container startup. You can run setup scripts manually later."
}

Write-Host ""
Write-Ok "Complete setup finished. This is the only script you need; no need to run complete_setup or bundle_setup."
Write-Host ""
Write-Host "Usage:"
Write-Host "  .\bundle_data_setup_windows.ps1            # Full setup (recommended)"
Write-Host "  .\bundle_data_setup_windows.ps1 -DryRun   # Preview only, no changes"
Write-Host ""

