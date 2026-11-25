# End-to-end regression harness for the simplified changedetection.io fork (native Windows, no Docker/WSL).
#
#   1. core      fixture site + app instance with ALLOW_IANA_RESTRICTED_ADDRESSES=true (fixture is on 127.0.0.1)
#   2. persist   same datastore, app restarted -> data must survive
#   3. security  fresh instance WITHOUT the SSRF bypass and WITH a password (SALTED_PASS)
#
# The SSRF bypass is only ever set on the throw-away test instance in step 1; it is never set by run.ps1.
#
# Usage:  .\e2e\run_e2e.ps1 [-Python <path to python.exe>] [-Label name] [-ExpectRemoved "/a,/b"]
param(
    [string]$Python = "C:\Users\adity\venvs\cdio\Scripts\python.exe",
    [string]$Label = "run",
    [string]$ExpectRemoved = "",
    [string]$ExpectNoUi = "",
    [int]$AppPort = 5055,
    [int]$SecPort = 5056,
    [int]$FixturePort = 8099
)
$ErrorActionPreference = 'Stop'
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
    $base = @{ LISTEN_HOST = '127.0.0.1'; DISABLE_VERSION_CHECK = 'true'; FETCH_WORKERS = '3'; PYTHONIOENCODING = 'utf-8';
               LLM_FEATURES_DISABLED = 'true'; DISABLE_MCP = 'true'; DISABLED_PROCESSORS = 'image_ssim_diff' }
    if ($env:E2E_PLAYWRIGHT_DRIVER_URL) { $base.PLAYWRIGHT_DRIVER_URL = $env:E2E_PLAYWRIGHT_DRIVER_URL }
    $all = $base + $extraEnv
    $saved = @{}
    foreach ($k in $all.Keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k); [Environment]::SetEnvironmentVariable($k, $all[$k]) }
    $p = Start-Process -FilePath $Python -ArgumentList @('changedetection.py', '-d', $datastore, '-p', $port) -WorkingDirectory $repo `
        -RedirectStandardOutput (Join-Path $work "$logName.out.log") -RedirectStandardError (Join-Path $work "$logName.err.log") -PassThru -WindowStyle Hidden
    foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k]) }
    return $p
}
function Run-Test([string]$mode, [string]$datastore, [string]$base, [string[]]$extra) {
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
    $rc1 = Run-Test 'core' $ds "http://127.0.0.1:$AppPort" $extra
    $summary.ram_mb_after_core = [math]::Round((Get-RamMB $AppPort), 1)
    Stop-ByCmd "*changedetection.py*-p $AppPort*"; Start-Sleep 3

    # ---- 2. persist (restart on same datastore) ----
    Start-App $ds $AppPort @{ ALLOW_IANA_RESTRICTED_ADDRESSES = 'true' } 'persist' | Out-Null
    $rc2 = Run-Test 'persist' $ds "http://127.0.0.1:$AppPort" @()
    Stop-ByCmd "*changedetection.py*-p $AppPort*"

    # ---- 3. security (SSRF protection ON, password ON) ----
    $pw = 'e2e-' + [guid]::NewGuid().ToString('N').Substring(0, 12)
    $salted = & $Python -I -c "import base64,hashlib,os,sys;s=os.urandom(32);print(base64.b64encode(s+hashlib.pbkdf2_hmac('sha256',sys.argv[1].encode(),s,100000)).decode())" $pw
    Start-App $dsSec $SecPort @{ SALTED_PASS = $salted } 'security' | Out-Null
    $rc3 = Run-Test 'security' $dsSec "http://127.0.0.1:$SecPort" @("--password=$pw")
    $summary.ram_mb_idle_security_instance = [math]::Round((Get-RamMB $SecPort), 1)
    Stop-ByCmd "*changedetection.py*-p $SecPort*"
}
finally {
    Stop-ByCmd "*changedetection.py*-p $AppPort*"; Stop-ByCmd "*changedetection.py*-p $SecPort*"
    Stop-Process -Id $fixture.Id -Force -ErrorAction SilentlyContinue; Stop-ByCmd "*fixture_server.py*$FixturePort*"
}
$tot = 0; $pass = 0
foreach ($m in 'core', 'persist', 'security') {
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
