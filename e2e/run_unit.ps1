# Runs the retained upstream unit tests (changedetectionio/tests/unit) and compares the failures with the
# known native-Windows failures recorded on the UNMODIFIED upstream code (e2e/known_windows_unit_failures.txt):
# symlink creation needs admin rights on Windows, lxml rejects Windows file:// URIs, one test needs fork(),
# one is timing/DNS dependent. Any failure NOT in that list is a regression and makes this script exit 1.
param([string]$Python = "C:\Users\adity\venvs\cdio\Scripts\python.exe")
$ErrorActionPreference = 'Continue'
$pkg = Join-Path (Split-Path -Parent $PSScriptRoot) 'changedetectionio'
$env:PYTHONIOENCODING = 'utf-8'
Push-Location $pkg
$out = & $Python -m pytest tests/unit -q -p no:cacheprovider -rfE 2>&1 | Out-String
Pop-Location
& $Python -I (Join-Path $PSScriptRoot 'check_templates.py') (Split-Path -Parent $PSScriptRoot)
$templatesOk = ($LASTEXITCODE -eq 0)
$known = Get-Content (Join-Path $PSScriptRoot 'known_windows_unit_failures.txt') | Where-Object { $_ -and -not $_.StartsWith('#') }
$failed = [regex]::Matches($out, '(?m)^(?:FAILED|ERROR) (\S+)') | ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique
$new = $failed | Where-Object { $_ -notin $known }
$m = [regex]::Matches($out, '(?m)^=+ (.*?\d+ passed.*?) =+\s*$')
$summaryLine = if ($m.Count) { $m[$m.Count - 1].Groups[1].Value } else { '(no pytest summary line found)' }
Write-Host "UNIT: $summaryLine"
Write-Host ("UNIT: known Windows-only failures: {0}, NEW failures: {1}" -f ($failed.Count - @($new).Count), @($new).Count)
$new | ForEach-Object { Write-Host "  NEW FAILURE: $_" }
if (@($new).Count -gt 0 -or -not $m.Count -or -not $templatesOk) { exit 1 }
exit 0
