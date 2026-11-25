# Change the LAB fixture site, then recheck the LAB watches in WebPulse (demo tooling, not part of the app).
#
#   .\demo\lab_control.ps1 -Price 2499                    product price (INR)
#   .\demo\lab_control.ps1 -Stock OutOfStock              OutOfStock | InStock
#   .\demo\lab_control.ps1 -Text "Line one<br>Line two"   news page body (<br> separates lines)
#   .\demo\lab_control.ps1 -Show                          current fixture state
#   .\demo\lab_control.ps1 -Notifications                 notifications the fixture has received
#
# After a change, click "Recheck" on the [LAB] watch in http://127.0.0.1:5001 (or add -Recheck here).
param(
    [string]$Price,
    [ValidateSet('InStock', 'OutOfStock')][string]$Stock,
    [string]$Text,
    [switch]$Show,
    [switch]$Notifications,
    [switch]$Recheck,
    [int]$FixturePort = 8199,
    [int]$LabPort = 5001,
    [string]$FixtureDir = "C:\Users\adity\cdio-data\webpulse-lab-fixture",
    [string]$LabDatastore = "C:\Users\adity\cdio-data\webpulse-lab"
)
$fix = "http://127.0.0.1:$FixturePort"
$q = @()
if ($Price) { $q += "price=$([uri]::EscapeDataString($Price))" }
if ($Stock) { $q += "stock=$Stock" }
if ($Text) { $q += "text=$([uri]::EscapeDataString($Text))" }
if ($q.Count) {
    $state = Invoke-RestMethod -Method Post "$fix/set?$($q -join '&')"
    Write-Host "Fixture updated:" ($state | ConvertTo-Json -Compress)
}
if ($Show) { Get-Content (Join-Path $FixtureDir 'state.json') -ErrorAction SilentlyContinue }
if ($Notifications) {
    $log = Join-Path $FixtureDir 'notifications.log'
    if (Test-Path $log) {
        Get-Content $log | ForEach-Object { try { $_ | ConvertFrom-Json | Select-Object title, message | Format-List } catch { $_ } }
    } else { Write-Host 'No notifications received yet.' }
}
if ($Recheck) {
    $key = (Get-Content (Join-Path $LabDatastore 'changedetection.json') -Raw | ConvertFrom-Json).settings.application.api_access_token
    $h = @{ 'x-api-key' = $key }
    $watches = Invoke-RestMethod -Headers $h "http://127.0.0.1:$LabPort/api/v1/watch"
    foreach ($p in $watches.PSObject.Properties) {
        if ($p.Value.url -like "*127.0.0.1:$FixturePort/page.html*" -or $p.Value.url -like "*127.0.0.1:$FixturePort/product.html*") {
            Invoke-RestMethod -Headers $h "http://127.0.0.1:$LabPort/api/v1/watch/$($p.Name)?recheck=1" | Out-Null
            Write-Host "Recheck queued: $($p.Value.title)"
        }
    }
}
