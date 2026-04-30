<#
    Fetch n8n and OpenSearch backup archives from Google Drive into the local
    bundle directory (Windows / PowerShell version).

    Intended usage:
        cd $Env:USERPROFILE\SWP-News-Summary\n8n
        .\bundle_fetch_backups_windows.ps1

    Output filenames are aligned with bundle_data_setup_windows.ps1:
        - bundle\n8n-data.tar.gz
        - bundle\opensearch-data.tar.gz
#>

param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:FetchFailed = 0

$bundleDir = Join-Path $PSScriptRoot "bundle"
if (-not (Test-Path $bundleDir)) {
    New-Item -ItemType Directory -Force -Path $bundleDir *>$null
}

function Download-FromGDrive {
    param(
        [Parameter(Mandatory=$true)][string] $FileId,
        [Parameter(Mandatory=$true)][string] $OutputPath
    )

    if (Test-Path $OutputPath) {
        Write-Host "✔ $OutputPath already exists — skipping download"
        return $true
    }

    Write-Host "⬇ Downloading $OutputPath from Google Drive..."

    $tmpPage   = New-TemporaryFile
    $tmpCookie = New-TemporaryFile

    try {
        # First request
        & curl.exe -s -L -c $tmpCookie.FullName `
            "https://drive.google.com/uc?export=download&id=$FileId" `
            -o $tmpPage.FullName

        $content = Get-Content -Raw -LiteralPath $tmpPage.FullName
        $confirm = ($content -match "confirm=([^&\"]+)" | Out-Null; $Matches[1])

        if ($confirm) {
            & curl.exe -L -b $tmpCookie.FullName `
                "https://drive.google.com/uc?export=download&confirm=$confirm&id=$FileId" `
                -o $OutputPath
        } else {
            # No confirm token -> file likely already downloaded
            Move-Item -LiteralPath $tmpPage.FullName -Destination $OutputPath
        }

        # Basic HTML check
        $outHead = Get-Content -LiteralPath $OutputPath -TotalCount 5 -ErrorAction SilentlyContinue
        if ($outHead -and ($outHead -join "`n") -like "*<html*") {
            Write-Host "❌ Download failed — got HTML instead of file. Removing invalid file." -ForegroundColor Red
            Remove-Item -Force -LiteralPath $OutputPath -ErrorAction SilentlyContinue
            $script:FetchFailed = 1
            return $false
        }

        Write-Host "✔ Downloaded $OutputPath"
        return $true
    } catch {
        Write-Host "❌ Download failed: $_" -ForegroundColor Red
        $script:FetchFailed = 1
        return $false
    } finally {
        Remove-Item -Force -ErrorAction SilentlyContinue $tmpPage.FullName,$tmpCookie.FullName
    }
}

# n8n backup -> bundle\n8n-data.tar.gz (Drive id 15jpeU... = n8n-data.tar.gz)
Download-FromGDrive -FileId "15jpeU-q4TmAT6QJkGxd75uNrp9vktkim" -OutputPath (Join-Path $bundleDir "n8n-data.tar.gz") | Out-Null

# OpenSearch backup -> bundle\opensearch-data.tar.gz (Drive id 1VVVi7... = opensearch-data.tar.gz)
Download-FromGDrive -FileId "1VVVi7rvpqzDWAkHmybXmMJM2lRjhlaJd" -OutputPath (Join-Path $bundleDir "opensearch-data.tar.gz") | Out-Null

if ($script:FetchFailed -ne 0) {
    Write-Host ""
    Write-Host "⚠ Some downloads failed. Opening Google Drive so you can download manually." -ForegroundColor Yellow
    $n8nDriveUrl    = "https://drive.google.com/file/d/15jpeU-q4TmAT6QJkGxd75uNrp9vktkim/view"
    $opensearchUrl  = "https://drive.google.com/file/d/1VVVi7rvpqzDWAkHmybXmMJM2lRjhlaJd/view"
    try {
        Start-Process $n8nDriveUrl
        Start-Sleep -Seconds 1
        Start-Process $opensearchUrl
    } catch { Write-Host "  (Could not open browser: $_)" }
    Write-Host ""
    Write-Host "Manual steps:"
    Write-Host "  1. In the opened Drive tabs, download n8n-data.tar.gz and opensearch-data.tar.gz."
    Write-Host "  2. Place both files inside the 'bundle' folder: $bundleDir"
    Write-Host "  3. Re-run bundle_data_setup_windows.ps1 to continue with restore and container startup."
    Write-Host ""
} else {
    Write-Host "✅ All bundle files ready."
    Write-Host ""
    # Last step: load the data into existing .n8n and OpenSearch volume
    $n8nTar   = Join-Path $bundleDir "n8n-data.tar.gz"
    $osTar    = Join-Path $bundleDir "opensearch-data.tar.gz"
    $targetN8n = Join-Path $Env:USERPROFILE ".n8n"
    $osVolume  = if ($Env:OPENSEARCH_VOLUME) { $Env:OPENSEARCH_VOLUME } else { "opensearch-data" }
    if ((Test-Path $n8nTar) -and (Test-Path $osTar)) {
        $ans = Read-Host "Load fetched data into existing .n8n and OpenSearch volume now? [y/N]"
        if ($ans -match '^[Yy]$') {
            if (Test-Path $targetN8n) {
                $backup = Join-Path $Env:USERPROFILE (".n8n_backup_{0}" -f (Get-Date -Format "yyyyMMdd-HHmmss"))
                Write-Host "▶ Backing up existing .n8n to $backup..."
                Move-Item -LiteralPath $targetN8n -Destination $backup
            }
            New-Item -ItemType Directory -Force -Path $targetN8n *>$null
            Write-Host "▶ Loading n8n data from bundle into .n8n..."
            docker run --rm -v "${targetN8n}:/data" -v "${bundleDir}:/backup:ro" busybox sh -c "tar xzf /backup/n8n-data.tar.gz -C /data --strip-components=1"
            Write-Host "✔ n8n data loaded. Restart the n8n container to see workflows."
            Write-Host ""
            Write-Host "▶ Loading OpenSearch data from bundle into volume $osVolume..."
            & docker run --rm -v "${osVolume}:/data" -v "${bundleDir}:/backup:ro" busybox sh -c "rm -rf /data/* && tar xzf /backup/opensearch-data.tar.gz -C /data"
            if ($LASTEXITCODE -eq 0) {
                Write-Host "✔ OpenSearch data loaded."
            } else {
                Write-Host "⚠ OpenSearch load failed (e.g. invalid tar or volume). Creating indices from JSON so UI can load." -ForegroundColor Yellow
            }
            # Ensure restore_indices.ps1 and .sh exist (create if missing), then run restore indices
            $baseDir   = Split-Path -Parent $PSScriptRoot
            $osScripts = Join-Path $baseDir "opensearch\scripts"
            $restorePs1 = Join-Path $osScripts "restore_indices.ps1"
            $restoreSh  = Join-Path $osScripts "restore_indices.sh"
            $restoreCmd = Join-Path $osScripts "restore_indices.cmd"
            if (Test-Path $osScripts) {
                # Create restore_indices.ps1 if missing
                if (-not (Test-Path $restorePs1)) {
                    Write-Host "▶ Creating restore_indices.ps1..."
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
while ($true) { try { $r = Invoke-WebRequest -Uri $OPENSEARCH_URL -Headers @{ Authorization = "Basic $base64" } -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop; if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300) { break } } catch { Start-Sleep -Seconds 2 } }
Write-Host "OpenSearch is up."; Write-Host ""; Write-Host "Using indices directory: $INDICES_DIR"; Write-Host ""
if (-not (Test-Path -LiteralPath $INDICES_DIR -PathType Container)) { Write-Host "Error: Indices directory not found: $INDICES_DIR" -ForegroundColor Red; exit 1 }
Get-ChildItem -Path $INDICES_DIR -Filter "*.json" -File | ForEach-Object { $indexName = [System.IO.Path]::GetFileNameWithoutExtension($_.Name); Write-Host "Creating index: $indexName"; $body = Get-Content -LiteralPath $_.FullName -Raw -Encoding UTF8; $uri = "$OPENSEARCH_URL/$indexName"; try { $response = Invoke-WebRequest -Uri $uri -Method Put -Headers $headers -Body $body -UseBasicParsing -TimeoutSec 30; if ([int]$response.StatusCode -eq 200 -or [int]$response.StatusCode -eq 201) { Write-Host "  [OK] Created successfully" -ForegroundColor Green } } catch { $code = $_.Exception.Response.StatusCode.value__; $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream()); $reader.BaseStream.Position = 0; $responseBody = $reader.ReadToEnd(); if ($code -eq 400 -and $responseBody -match "resource_already_exists_exception") { Write-Host "  [OK] Already exists" -ForegroundColor Yellow } else { Write-Host "  [FAIL] HTTP $code" -ForegroundColor Red } }; Write-Host "" }
Write-Host "All indices processed."
'@
                    Set-Content -LiteralPath $restorePs1 -Value $psContent -Encoding UTF8
                }
                # Create restore_indices.sh if missing
                if (-not (Test-Path $restoreSh)) {
                    Write-Host "▶ Creating restore_indices.sh..."
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
                    Set-Content -LiteralPath $restoreSh -Value $shContent -Encoding UTF8 -NoNewline:$false
                }
            }
            if (Test-Path $restorePs1) {
                Write-Host "▶ Ensuring OpenSearch indices exist (clusters, articles, etc.)..."
                & powershell -NoProfile -ExecutionPolicy Bypass -File $restorePs1
                Write-Host "✔ Indices ready."
            } elseif (Test-Path $restoreCmd) {
                Write-Host "▶ Ensuring OpenSearch indices exist (clusters, articles, etc.)..."
                & $restoreCmd
                Write-Host "✔ Indices ready."
            }
            # Restart containers so they use the loaded data
            Write-Host ""
            Write-Host "▶ Restarting containers to pick up loaded data..."
            $running = @(docker ps --format "{{.Names}}" 2>$null)
            if ($running -contains "n8n") { docker restart n8n 2>$null; Write-Host "✔ n8n restarted." }
            if ($running -contains "opensearch") { docker restart opensearch 2>$null; Write-Host "✔ OpenSearch restarted." }
            # Ensure n8n can resolve hostname "opensearch" (fix getaddrinfo ENOTFOUND opensearch).
            # Attach both opensearch and n8n to the same network so they can reach each other.
            $osNet = if ($Env:OPENSEARCH_NET) { $Env:OPENSEARCH_NET } else { "opensearch_internal_net" }
            docker network create $osNet 2>$null
            if ($running -contains "opensearch") { docker network connect $osNet opensearch 2>$null; if ($LASTEXITCODE -eq 0) { Write-Host "✔ opensearch attached to $osNet." } }
            if ($running -contains "n8n")       { docker network connect $osNet n8n 2>$null;       if ($LASTEXITCODE -eq 0) { Write-Host "✔ n8n connected to $osNet (opensearch hostname will resolve)." } }
            if ($running -contains "dashboard") { docker network connect $osNet dashboard 2>$null; if ($LASTEXITCODE -eq 0) { Write-Host "✔ dashboard connected to $osNet." } }
            Write-Host ""
            Write-Host "✅ Fetch and load finished."
        } else {
            Write-Host "Skipping load. Run bundle_data_setup_windows.ps1 to load data and start containers later."
        }
    }
}
exit 0

