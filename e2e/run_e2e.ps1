# End-to-end regression harness for the simplified changedetection.io fork (native Windows, no Docker/WSL).
#
#   1. core      fixture site + app instance with ALLOW_IANA_RESTRICTED_ADDRESSES=true (fixture is on 127.0.0.1)
#   2. persist   same datastore, app restarted -> data must survive
#   3. security  fresh instance WITHOUT the SSRF bypass and WITH a password (SALTED_PASS)
#   4. browser   (-Browser) Playwright fetcher driving the Microsoft Edge that ships with Windows, over CDP
#
# The SSRF bypass is only ever set on the throw-away test instance in step 1; it is never set by run.ps1.
#
# Usage:  .\e2e\run_e2e.ps1 [-Python <path to python.exe>] [-Label name] [-ExpectRemoved "/a,/b"]
param(
    [string]$Python = '',                 # default: <project>\.venv, then %USERPROFILE%\venvs\cdio-simplified
    [string]$Label = "run",
    [string]$ExpectRemoved = "",
    [string]$ExpectNoUi = "",
    [int]$AppPort = 5055,
    [int]$SecPort = 5056,
    [int]$FixturePort = 8099,
    [switch]$Browser,              # also run the Playwright/Edge browser checks (B..)
    [int]$BrowserAppPort = 5057,
    [int]$CdpPort = 9223,
    [switch]$UI,                   # also run the browser UI tests (U..) in Microsoft Edge
    [int]$UiAppPort = 5058
)
$ErrorActionPreference = 'Stop'
if (-not $Python) {
    $Python = @((Join-Path (Split-Path -Parent $PSScriptRoot) '.venv\Scripts\python.exe'), (Join-Path $env:USERPROFILE 'venvs\cdio-simplified\Scripts\python.exe')) |
        Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $Python) { throw 'Python virtual environment not found - see docs\INSTALLATION_GUIDE.md, or pass -Python' }
}
# Defaults for E19/E20: URLs of removed upstream features (must be 404) and markers of removed UI (must be absent)
if (-not $ExpectRemoved) {
    $ExpectRemoved = '/rss,/mcp/v1,/site.webmanifest,/sw.js,/pwa/install-qrcode.svg,/check_proxy/00000000-0000-0000-0000-000000000000/status,/settings/llm,/settings/mcp'
}
if (-not $ExpectNoUi) {
    $ExpectNoUi = 'llm-summary,ai-mode,mcp-token,site.webmanifest,serviceWorker,install-qrcode,rss-token,recheck-proxy,html2canvas,snippet-to-image,chromewebstore,brightdata,oxylabs,language-selector,flag-icons,selenium,puppeteer,ns-quick'
}
$repo = Split-Path -Parent $PSScriptRoot
$work = Join-Path $env:TEMP ("cdio-e2e\{0}-{1}" -f $Label, (Get-Date -Format 'yyyyMMdd-HHmmss'))
$ds = Join-Path $work 'datastore'
$dsSec = Join-Path $work 'datastore-security'
New-Item -ItemType Directory -Force $ds, $dsSec | Out-Null
$fix = "http://127.0.0.1:$FixturePort"

function Stop-ByCmd([string]$pattern) {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like $pattern } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
function Get-RamMB([int]$port) {
    # A venv python.exe launcher spawns the real interpreter as a child; report the largest process.
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*changedetection.py*-p $port*" }
    ($procs | ForEach-Object { (Get-Process -Id $_.ProcessId).WorkingSet64 } | Measure-Object -Maximum).Maximum / 1MB
}
function Start-App([string]$datastore, [int]$port, [hashtable]$extraEnv, [string]$logName) {
    $base = @{ LISTEN_HOST = '127.0.0.1'; DISABLE_VERSION_CHECK = 'true'; FETCH_WORKERS = '3'; PYTHONIOENCODING = 'utf-8'; REQUESTS_RETRY_MAX_COUNT = '2' }  # same as run.ps1
    $all = $base + $extraEnv
    $saved = @{}
    foreach ($k in $all.Keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k); [Environment]::SetEnvironmentVariable($k, $all[$k]) }
    $p = Start-Process -FilePath $Python -ArgumentList @('changedetection.py', '-d', $datastore, '-p', $port) -WorkingDirectory $repo `
        -RedirectStandardOutput (Join-Path $work "$logName.out.log") -RedirectStandardError (Join-Path $work "$logName.err.log") -PassThru -WindowStyle Hidden
    foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k]) }
    return $p
}
function Invoke-E2ETest([string]$mode, [string]$datastore, [string]$base, [string[]]$extra) {
    & $Python -I (Join-Path $PSScriptRoot 'test_e2e.py') $mode $datastore $base $fix $work @extra
    return $LASTEXITCODE
}

Stop-ByCmd "*fixture_server.py*$FixturePort*"; Stop-ByCmd "*-p $AppPort*"; Stop-ByCmd "*-p $SecPort*"
$fixture = Start-Process -FilePath $Python -ArgumentList @('-I', (Join-Path $PSScriptRoot 'fixture_server.py'), $FixturePort, $work) -PassThru -WindowStyle Hidden
$summary = [ordered]@{ label = $Label; work_dir = $work }
try {
    # ---- 1. core ----
    Start-App $ds $AppPort @{ ALLOW_IANA_RESTRICTED_ADDRESSES = 'true' } 'core' | Out-Null
    $extra = @(); if ($ExpectRemoved) { $extra += "--expect-removed=$ExpectRemoved" }
    if ($ExpectNoUi) { $extra += "--expect-no-ui=$ExpectNoUi" }
    $null = Invoke-E2ETest 'core' $ds "http://127.0.0.1:$AppPort" $extra
    $summary.ram_mb_after_core = [math]::Round((Get-RamMB $AppPort), 1)
    Stop-ByCmd "*changedetection.py*-p $AppPort*"; Start-Sleep 3

    # ---- 2. persist (restart on same datastore) ----
    Start-App $ds $AppPort @{ ALLOW_IANA_RESTRICTED_ADDRESSES = 'true' } 'persist' | Out-Null
    $null = Invoke-E2ETest 'persist' $ds "http://127.0.0.1:$AppPort" @()
    Stop-ByCmd "*changedetection.py*-p $AppPort*"

    # ---- 3. security (SSRF protection ON, password ON) ----
    $pw = 'e2e-' + [guid]::NewGuid().ToString('N').Substring(0, 12)
    $salted = & $Python -I -c "import base64,hashlib,os,sys;s=os.urandom(32);print(base64.b64encode(s+hashlib.pbkdf2_hmac('sha256',sys.argv[1].encode(),s,100000)).decode())" $pw
    Start-App $dsSec $SecPort @{ SALTED_PASS = $salted } 'security' | Out-Null
    $null = Invoke-E2ETest 'security' $dsSec "http://127.0.0.1:$SecPort" @("--password=$pw")
    $summary.ram_mb_idle_security_instance = [math]::Round((Get-RamMB $SecPort), 1)
    Stop-ByCmd "*changedetection.py*-p $SecPort*"

    # ---- 4. browser (optional): Playwright fetcher via headless Microsoft Edge over CDP ----
    if ($Browser) {
        $edge = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe") |
            Where-Object { Test-Path $_ } | Select-Object -First 1
        $edgeProfile = Join-Path $work 'edge-profile'
        Start-Process $edge -ArgumentList @('--headless=new', "--remote-debugging-port=$CdpPort", '--remote-debugging-address=127.0.0.1',
            "--user-data-dir=$edgeProfile", '--no-first-run', '--disable-gpu', 'about:blank') -WindowStyle Hidden
        $dsBrowser = Join-Path $work 'datastore-browser'; New-Item -ItemType Directory -Force $dsBrowser | Out-Null
        for ($i = 0; $i -lt 20; $i++) { try { Invoke-RestMethod "http://127.0.0.1:$CdpPort/json/version" -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep 1 } }
        Start-App $dsBrowser $BrowserAppPort @{ ALLOW_IANA_RESTRICTED_ADDRESSES = 'true'; PLAYWRIGHT_DRIVER_URL = "http://127.0.0.1:$CdpPort" } 'browser' | Out-Null
        $null = Invoke-E2ETest 'browser' $dsBrowser "http://127.0.0.1:$BrowserAppPort" @()
        # SSRF through redirects / page JavaScript, both fetchers (Phase 15) - uses the same headless Edge
        & $Python (Join-Path $PSScriptRoot 'ssrf_redirect_test.py') $work "http://127.0.0.1:$CdpPort" | Out-Host
        $summary.ram_mb_browser_instance_app_only = [math]::Round((Get-RamMB $BrowserAppPort), 1)
        Stop-ByCmd "*changedetection.py*-p $BrowserAppPort*"
    }

    # ---- 5. ui (optional): click through the real interface in Microsoft Edge (Playwright) ----
    if ($UI) {
        $dsUi = Join-Path $work 'datastore-ui'; New-Item -ItemType Directory -Force $dsUi | Out-Null
        # The fixture doubles as the controlled-demo site, reached through the named demo proxy exactly as run.ps1 sets it up
        Set-Content (Join-Path $dsUi 'proxies.json') ('{"webpulse-demo-site": {"label": "WebPulse demo site (simulated)", "url": "' + $fix + '"}}')
        Start-App $dsUi $UiAppPort @{ ALLOW_IANA_RESTRICTED_ADDRESSES = 'true'; WEBPULSE_DEMO_SITE = $fix } 'ui' | Out-Null
        & $Python -I (Join-Path $PSScriptRoot 'ui_test.py') $dsUi "http://127.0.0.1:$UiAppPort" $fix $work
        Stop-ByCmd "*changedetection.py*-p $UiAppPort*"
    }
}
finally {
    Stop-ByCmd "*changedetection.py*-p $UiAppPort*"
    Stop-ByCmd "*changedetection.py*-p $AppPort*"; Stop-ByCmd "*changedetection.py*-p $SecPort*"
    Stop-Process -Id $fixture.Id -Force -ErrorAction SilentlyContinue; Stop-ByCmd "*fixture_server.py*$FixturePort*"
    Stop-ByCmd "*changedetection.py*-p $BrowserAppPort*"
    Get-CimInstance Win32_Process -Filter "Name='msedge.exe'" | Where-Object { $_.CommandLine -like "*$work*edge-profile*" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
}
$tot = 0; $pass = 0
$modes = @('core', 'persist', 'security'); if ($Browser) { $modes += 'browser'; $modes += 'ssrf' }; if ($UI) { $modes += 'ui' }
foreach ($m in $modes) {
    $f = Join-Path $work "results_$m.json"
    if (Test-Path $f) { $j = Get-Content $f -Raw | ConvertFrom-Json; $summary["$m"] = "$($j.passed)/$($j.total)"; $tot += $j.total; $pass += $j.passed }
    else { $summary["$m"] = 'DID NOT RUN' }
}
$summary.total = "$pass/$tot"
# The security instance logs a traceback for every SSRF-blocked fetch (expected), so only core/persist logs count
$summary.unexpected_errors_in_app_logs = (Get-ChildItem $work -Filter '*.log' | Where-Object { $_.Name -notlike 'security*' } |
    Select-String -Pattern 'Traceback|CRITICAL' | Measure-Object).Count
$summary | ConvertTo-Json | Tee-Object -FilePath (Join-Path $work 'summary.json')
if ($pass -ne $tot -or $tot -eq 0) { exit 1 }
