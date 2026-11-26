# Runs the retained upstream unit tests (changedetectionio/tests/unit) and compares the failures with the
# known native-Windows failures recorded on the UNMODIFIED upstream code (e2e/known_windows_unit_failures.txt):
# symlink creation needs admin rights on Windows, one SSRF test assumes Linux, two upstream tests are outdated, one
# needs fork() (details in that file). Any failure NOT in that list is a regression and makes this script exit 1.
param([string]$Python = '')   # default: <project>\.venv, then %USERPROFILE%\venvs\cdio-simplified
$ErrorActionPreference = 'Continue'
if (-not $Python) {
    $Python = @((Join-Path (Split-Path -Parent $PSScriptRoot) '.venv\Scripts\python.exe'), (Join-Path $env:USERPROFILE 'venvs\cdio-simplified\Scripts\python.exe')) |
        Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $Python) { throw 'Python virtual environment not found - see docs\INSTALLATION_GUIDE.md, or pass -Python' }
}
$pkg = Join-Path (Split-Path -Parent $PSScriptRoot) 'changedetectionio'
$env:PYTHONIOENCODING = 'utf-8'
Push-Location $pkg
$out = & $Python -m pytest tests/unit -q -p no:cacheprovider -rfE 2>&1 | Out-String
Pop-Location
& $Python -I (Join-Path $PSScriptRoot 'check_templates.py') (Split-Path -Parent $PSScriptRoot)
$templatesOk = ($LASTEXITCODE -eq 0)
# Every third-party module the app imports must be installed (catches lost transitive dependencies)
& $Python -W ignore -I (Join-Path $PSScriptRoot 'check_imports.py') (Split-Path -Parent $PSScriptRoot)
$importsOk = ($LASTEXITCODE -eq 0)
$known = Get-Content (Join-Path $PSScriptRoot 'known_windows_unit_failures.txt') | Where-Object { $_ -and -not $_.StartsWith('#') }
$failed = [regex]::Matches($out, '(?m)^(?:FAILED|ERROR) (\S+)') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
$new = $failed | Where-Object { $_ -notin $known }
$m = [regex]::Matches($out, '(?m)^=+ (.*?\d+ passed.*?) =+\s*$')
$summaryLine = if ($m.Count) { $m[$m.Count - 1].Groups[1].Value } else { '(no pytest summary line found - the run did NOT complete, result invalid)' }
Write-Host "UNIT: $summaryLine"
if (-not $m.Count) { Write-Host "Last pytest output:"; ($out -split "`n" | Select-Object -Last 15) | ForEach-Object { Write-Host "  $_" } }
Write-Host ("UNIT: known Windows-only failures: {0}, NEW failures: {1}" -f ($failed.Count - @($new).Count), @($new).Count)
$new | ForEach-Object { Write-Host "  NEW FAILURE: $_" }
if (@($new).Count -gt 0 -or -not $m.Count -or -not $templatesOk -or -not $importsOk) { exit 1 }
exit 0
