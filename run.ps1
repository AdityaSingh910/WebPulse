# WebPulse - one command starts everything (native Windows, no Docker / WSL):
#
#   .\run.ps1
#
#   1. headless Microsoft Edge (already installed on Windows) for JavaScript pages      127.0.0.1:9222
#   2. the internal demo site (controlled shop / careers / news pages)                 127.0.0.1:8199
#   3. WebPulse itself - the only page you open in your browser                         http://127.0.0.1:5000
#
#   Ctrl+C stops WebPulse and the helpers it started.
#   Options: -NoBrowser  -NoDemoSite  -Port 5001  -Datastore D:\data\webpulse  -Workers 3  -Python C:\path\python.exe
#
# Security defaults (do not change for normal use):
#   - everything binds to 127.0.0.1 only
#   - SSRF protection stays ON: ALLOW_IANA_RESTRICTED_ADDRESSES is never set here. The demo site is reached
#     only through its own named proxy by the [Demo] watches (see demo/setup_presentation.py); it never forwards.
#     The Controlled demo page (/demo/) talks only to http://127.0.0.1:<DemoSitePort>.
#
# Safety checks before anything is started (Phase 15): the port must be free and no other WebPulse may use the same
# data folder - two instances on one data folder would both run the scheduler and could corrupt the saved data.
param(
    [int]$Port = 5000,
    [string]$Datastore = (Join-Path $env:USERPROFILE 'cdio-data\webpulse-demo'),
    [string]$Python = '',
    [int]$Workers = 3,
    [switch]$NoBrowser,
    [switch]$NoDemoSite,
    [int]$CdpPort = 9222,
    [int]$DemoSitePort = 8199,
    [string]$DemoSiteDir = (Join-Path $env:USERPROFILE 'cdio-data\webpulse-demo-site')
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Stop-WithMessage([string]$Message) {
    Write-Host ""
    Write-Host "WebPulse was NOT started: $Message" -ForegroundColor Red
    Write-Host ""
    exit 1
}

function Get-PortOwner([int]$P) {
    $c = Get-NetTCPConnection -LocalPort $P -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($c) { Get-CimInstance Win32_Process -Filter "ProcessId=$($c.OwningProcess)" -ErrorAction SilentlyContinue }
}

# ---- 0. Pre-flight checks (nothing has been started or stopped yet) ----
if (-not $Python) {
    # The project's own virtual environment first (INSTALLATION_GUIDE.md), then the original development location
    $Python = @((Join-Path $PSScriptRoot '.venv\Scripts\python.exe'), (Join-Path $env:USERPROFILE 'venvs\cdio-simplified\Scripts\python.exe')) |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $Python -or -not (Test-Path $Python)) {
    Stop-WithMessage "Python virtual environment not found. Create it as described in docs\INSTALLATION_GUIDE.md, or pass -Python C:\path\to\python.exe"
}
if (-not (Test-Path (Join-Path $PSScriptRoot 'changedetection.py'))) { Stop-WithMessage "run.ps1 must stay in the WebPulse project folder." }

$owner = Get-PortOwner $Port
if ($owner) {
    $what = if ($owner.CommandLine -like '*changedetection.py*') { 'WebPulse is already running there' } else { "it is used by $($owner.Name) (PID $($owner.ProcessId))" }
    Stop-WithMessage "port $Port is busy - $what. Open http://127.0.0.1:$Port, stop the other copy (Ctrl+C in its window), or start with -Port 5001."
}
$dsFull = [System.IO.Path]::GetFullPath($Datastore)
$sameData = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*changedetection.py*' -and $_.CommandLine -match ('-d\s+"?' + [regex]::Escape($dsFull.TrimEnd('\')) + '\\?"?(\s|$)') } |
    Select-Object -First 1
if ($sameData) {
    Stop-WithMessage "another WebPulse (PID $($sameData.ProcessId)) is already using the data folder $dsFull. Two copies on one data folder would corrupt it."
}
if (-not $NoDemoSite) {
    $demoOwner = Get-PortOwner $DemoSitePort
    if ($demoOwner -and $demoOwner.CommandLine -notlike '*fixture_server.py*') {
        Stop-WithMessage "demo-site port $DemoSitePort is used by $($demoOwner.Name) (PID $($demoOwner.ProcessId)). Start with -DemoSitePort 8299 or -NoDemoSite."
    }
}

New-Item -ItemType Directory -Force $Datastore | Out-Null
$started = @()
$edgeProfile = $null

# 1. Headless Edge (CDP) for the browser fetcher
if (-not $NoBrowser) {
    $cdpUp = $false
    try { Invoke-RestMethod "http://127.0.0.1:$CdpPort/json/version" -TimeoutSec 2 | Out-Null; $cdpUp = $true } catch {}
    if (-not $cdpUp) {
        $edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") |
            Where-Object { Test-Path $_ } | Select-Object -First 1
        if (-not $edge) { Stop-WithMessage "Microsoft Edge not found. Start with -NoBrowser (JavaScript pages will then not be readable)." }
        # A profile per port, so a second set of helpers (e.g. tests on other ports) never attaches to this Edge
        $edgeProfile = Join-Path $env:TEMP "cdio-edge-profile-$CdpPort"
        $started += Start-Process $edge -PassThru -WindowStyle Hidden -ArgumentList @('--headless=new', "--remote-debugging-port=$CdpPort",
            '--remote-debugging-address=127.0.0.1', "--user-data-dir=$edgeProfile", '--no-first-run', '--disable-gpu', 'about:blank')
        for ($i = 0; $i -lt 15 -and -not $cdpUp; $i++) {
            Start-Sleep 1
            try { Invoke-RestMethod "http://127.0.0.1:$CdpPort/json/version" -TimeoutSec 2 | Out-Null; $cdpUp = $true } catch {}
        }
        if (-not $cdpUp) { Write-Host "Warning: headless Edge did not answer on 127.0.0.1:$CdpPort - JavaScript pages will fail until it does." -ForegroundColor Yellow }
    }
    $env:PLAYWRIGHT_DRIVER_URL = "http://127.0.0.1:$CdpPort"
    Write-Host "Browser (headless Edge):  127.0.0.1:$CdpPort"
}

# 2. Internal demo site (serves only its own canned pages; never forwards)
if (-not $NoDemoSite) {
    New-Item -ItemType Directory -Force $DemoSiteDir | Out-Null
    # A demo site left over from an earlier (crashed) run is replaced, so the current version always runs.
    # Safe: the checks above guarantee that no WebPulse is running on this port / data folder.
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

Write-Host "Data folder:              $dsFull"
Write-Host "WebPulse:                 http://127.0.0.1:$Port   (Ctrl+C to stop)"
try {
    & $Python changedetection.py -d $Datastore -p $Port
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { Write-Host "WebPulse stopped with exit code $LASTEXITCODE - see the messages above." -ForegroundColor Yellow }
}
finally {
    # Stop the helpers this script started, including their child processes
    foreach ($p in $started) { & taskkill.exe /PID $p.Id /T /F 2>&1 | Out-Null }
    # msedge.exe re-launches itself, so the PID above is often already gone: also stop every Edge process that uses
    # this script's own profile folder (only the headless helper ever uses it)
    if ($edgeProfile) {
        Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*$edgeProfile*" } |
            ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
    Write-Host "WebPulse and its helpers have stopped."
}
