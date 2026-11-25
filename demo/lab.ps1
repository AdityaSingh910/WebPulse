# WebPulse LAB - an isolated, controlled demonstration environment (demo tooling, not part of the app).
#
#   .\demo\lab.ps1            start the local fixture site (port 8199) + a separate LAB WebPulse instance (port 5001)
#
# Isolation:
#   - The LAB instance has its OWN datastore (C:\Users\adity\cdio-data\webpulse-lab) and port (5001).
#   - Only this LAB process gets ALLOW_IANA_RESTRICTED_ADDRESSES=true, so it may fetch the fixture site on
#     127.0.0.1. Your normal WebPulse (run.ps1, port 5000) keeps full SSRF protection and is not affected.
#   - Both instances listen on 127.0.0.1 only.
#   - The LAB reuses the headless Edge that run.ps1 -Browser starts (CDP on 127.0.0.1:9222) for JavaScript pages.
#
# Change the fixture site with .\demo\lab_control.ps1 (price, stock, page text, view received notifications).
param(
    [int]$Port = 5001,
    [int]$FixturePort = 8199,
    [string]$Datastore = "C:\Users\adity\cdio-data\webpulse-lab",
    [string]$FixtureDir = "C:\Users\adity\cdio-data\webpulse-lab-fixture",
    [string]$Python = "C:\Users\adity\venvs\cdio-simplified\Scripts\python.exe",
    [int]$CdpPort = 9222
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Force $Datastore, $FixtureDir | Out-Null

# 1. Fixture site (reused from e2e/fixture_server.py, unmodified)
$running = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*fixture_server.py*$FixturePort*" }
if (-not $running) {
    Start-Process -FilePath $Python -ArgumentList @('-I', (Join-Path $repo 'e2e\fixture_server.py'), $FixturePort, $FixtureDir) -WindowStyle Hidden
    Write-Host "Fixture site: http://127.0.0.1:$FixturePort  (state + notifications.log in $FixtureDir)"
}

# 2. LAB instance - environment set for this process only
$env:LISTEN_HOST = '127.0.0.1'
$env:DISABLE_VERSION_CHECK = 'true'
$env:FETCH_WORKERS = '3'
$env:PYTHONIOENCODING = 'utf-8'
$env:ALLOW_IANA_RESTRICTED_ADDRESSES = 'true'     # LAB ONLY - lets this instance reach the 127.0.0.1 fixture
$env:PLAYWRIGHT_DRIVER_URL = "http://127.0.0.1:$CdpPort"
Write-Host "WebPulse LAB: http://127.0.0.1:$Port  (datastore $Datastore)"
Set-Location $repo
& $Python changedetection.py -d $Datastore -p $Port
