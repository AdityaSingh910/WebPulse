# WebPulse - one command starts everything (native Windows, no Docker / WSL):
#
#   .\run.ps1
#
#   1. headless Microsoft Edge (already installed on Windows) for JavaScript pages      127.0.0.1:9222
#   2. the internal demo site (controlled shop / careers / news pages)                 127.0.0.1:8199
#   3. WebPulse itself - the only page you open in your browser                         http://127.0.0.1:5000
#
#   Ctrl+C stops WebPulse and the helpers it started.
#   Options: -NoBrowser  -NoDemoSite  -Port 5001  -Datastore D:\data\webpulse  -Workers 3
#
# Security defaults (do not change for normal use):
#   - everything binds to 127.0.0.1 only
#   - SSRF protection stays ON: ALLOW_IANA_RESTRICTED_ADDRESSES is never set here. The demo site is reached
#     only through its own named proxy by the [Demo] watches (see demo/setup_presentation.py); it never forwards.
#     The Controlled demo page (/demo/) talks only to http://127.0.0.1:<DemoSitePort>.
param(
    [int]$Port = 5000,
    [string]$Datastore = "C:\Users\adity\cdio-data\webpulse-demo",
    [string]$Python = "C:\Users\adity\venvs\cdio-simplified\Scripts\python.exe",
    [int]$Workers = 3,
    [switch]$NoBrowser,
    [switch]$NoDemoSite,
    [int]$CdpPort = 9222,
    [int]$DemoSitePort = 8199,
    [string]$DemoSiteDir = "C:\Users\adity\cdio-data\webpulse-demo-site"
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
New-Item -ItemType Directory -Force $Datastore | Out-Null
$started = @()

# 1. Headless Edge (CDP) for the browser fetcher
if (-not $NoBrowser) {
    $cdpUp = $false
    try { Invoke-RestMethod "http://127.0.0.1:$CdpPort/json/version" -TimeoutSec 2 | Out-Null; $cdpUp = $true } catch {}
    if (-not $cdpUp) {
        $edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") |
            Where-Object { Test-Path $_ } | Select-Object -First 1
        if (-not $edge) { throw "Microsoft Edge not found (use -NoBrowser)" }
        $started += Start-Process $edge -PassThru -WindowStyle Hidden -ArgumentList @('--headless=new', "--remote-debugging-port=$CdpPort",
            '--remote-debugging-address=127.0.0.1', "--user-data-dir=$(Join-Path $env:TEMP 'cdio-edge-profile')", '--no-first-run', '--disable-gpu', 'about:blank')
        Start-Sleep 3
    }
    $env:PLAYWRIGHT_DRIVER_URL = "http://127.0.0.1:$CdpPort"
    Write-Host "Browser (headless Edge):  127.0.0.1:$CdpPort"
}

# 2. Internal demo site (serves only its own canned pages; never forwards)
if (-not $NoDemoSite) {
    New-Item -ItemType Directory -Force $DemoSiteDir | Out-Null
    # A demo site left over from an earlier run is replaced, so the current version always runs
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*fixture_server.py*$DemoSitePort*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    $started += Start-Process -FilePath $Python -PassThru -WindowStyle Hidden -ArgumentList @('-I', (Join-Path $PSScriptRoot 'e2e\fixture_server.py'), $DemoSitePort, $DemoSiteDir)
    # Turns on the "Controlled demo" page; WebPulse accepts only http://127.0.0.1:<port> here
    $env:WEBPULSE_DEMO_SITE = "http://127.0.0.1:$DemoSitePort"
    Write-Host "Demo site (internal):     127.0.0.1:$DemoSitePort   (Controlled demo page: http://127.0.0.1:$Port/demo/)"
}
else {
    Remove-Item Env:WEBPULSE_DEMO_SITE -ErrorAction SilentlyContinue
}

# 3. WebPulse
$env:LISTEN_HOST = '127.0.0.1'
$env:DISABLE_VERSION_CHECK = 'true'   # no daily "phone home"
$env:FETCH_WORKERS = "$Workers"       # concurrent fetch workers
$env:PYTHONIOENCODING = 'utf-8'
# Network-error retries of the plain-HTTP fetcher (upstream default 6, with ~31 s of back-off). Measured on this
# laptop: a dead site held a worker for 31-67 s with 6 retries versus 2-16 s with 2 (see CHANGES.md, Phase 12).
# A failed check is tried again at the next scheduled interval anyway.
if (-not $env:REQUESTS_RETRY_MAX_COUNT) { $env:REQUESTS_RETRY_MAX_COUNT = '2' }
Remove-Item Env:ALLOW_IANA_RESTRICTED_ADDRESSES -ErrorAction SilentlyContinue
Remove-Item Env:ALLOW_FILE_URI -ErrorAction SilentlyContinue

Write-Host "WebPulse:                 http://127.0.0.1:$Port   (Ctrl+C to stop)"
try {
    & $Python changedetection.py -d $Datastore -p $Port
}
finally {
    foreach ($p in $started) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
}
