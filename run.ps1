# Launcher for the simplified changedetection.io fork on native Windows (no Docker / WSL).
#
#   .\run.ps1                       # http://127.0.0.1:5000, plain HTTP fetcher
#   .\run.ps1 -Browser              # also start headless Microsoft Edge and use Playwright for JS-rendered pages
#   .\run.ps1 -Port 5001 -Datastore D:\data\cdio
#
# Security defaults (do not change for normal use):
#   - binds to 127.0.0.1 only (LISTEN_HOST)
#   - SSRF protection stays ON: ALLOW_IANA_RESTRICTED_ADDRESSES is never set here (only e2e\run_e2e.ps1
#     sets it, on a throw-away test instance, so it can reach its 127.0.0.1 fixture site)
param(
    [int]$Port = 5000,
    [string]$Datastore = "C:\Users\adity\cdio-data\simplified",
    [string]$Python = "C:\Users\adity\venvs\cdio-simplified\Scripts\python.exe",
    [int]$Workers = 3,
    [switch]$Browser,
    [int]$CdpPort = 9222
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force $Datastore | Out-Null

$env:LISTEN_HOST = '127.0.0.1'
$env:DISABLE_VERSION_CHECK = 'true'   # no daily "phone home" to changedetection.io
$env:FETCH_WORKERS = "$Workers"       # concurrent fetch workers
$env:PYTHONIOENCODING = 'utf-8'
# (Phase 1 used LLM_FEATURES_DISABLED / DISABLE_MCP / DISABLED_PROCESSORS here; those features are now
# removed from the code, so the switches are no longer needed.)
Remove-Item Env:ALLOW_IANA_RESTRICTED_ADDRESSES -ErrorAction SilentlyContinue
Remove-Item Env:ALLOW_FILE_URI -ErrorAction SilentlyContinue

if ($Browser) {
    # Free, already installed on Windows 11: Edge speaks the Chrome DevTools Protocol (CDP).
    $edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $edge) { throw "Microsoft Edge not found" }
    $profileDir = Join-Path $env:TEMP 'cdio-edge-profile'
    Start-Process $edge -ArgumentList @('--headless=new', "--remote-debugging-port=$CdpPort", '--remote-debugging-address=127.0.0.1',
        "--user-data-dir=$profileDir", '--no-first-run', '--disable-gpu', 'about:blank') -WindowStyle Hidden
    Start-Sleep 3
    $env:PLAYWRIGHT_DRIVER_URL = "http://127.0.0.1:$CdpPort"
    Write-Host "Playwright fetcher via headless Edge at $env:PLAYWRIGHT_DRIVER_URL"
}

Write-Host "Starting on http://127.0.0.1:$Port  (datastore: $Datastore)"
& $Python changedetection.py -d $Datastore -p $Port
