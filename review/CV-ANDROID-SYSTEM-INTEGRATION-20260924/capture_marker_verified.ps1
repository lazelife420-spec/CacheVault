param(
    [Parameter(Mandatory = $true)][string]$Serial,
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Marker
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$devicePng = '/sdcard/cv_system_integration_capture.png'
$deviceXml = '/sdcard/cv_system_integration_capture.xml'

& adb -s $Serial shell screencap -p $devicePng | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Screenshot failed for $Serial." }
& adb -s $Serial pull $devicePng (Join-Path $root "$Name.png") | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Screenshot transfer failed for $Serial." }
& adb -s $Serial shell uiautomator dump $deviceXml | Out-Null
if ($LASTEXITCODE -ne 0) { throw "UI marker dump failed for $Serial." }
& adb -s $Serial pull $deviceXml (Join-Path $root "$Name.xml") | Out-Null
if ($LASTEXITCODE -ne 0) { throw "UI marker transfer failed for $Serial." }

$doc = [xml][System.IO.File]::ReadAllText((Join-Path $root "$Name.xml"))
$visibleText = @($doc.SelectNodes('//node[@text!=""]') | ForEach-Object { $_.GetAttribute('text') })
if ($visibleText -notcontains $Marker) { throw "Marker verification failed for $Name on $Serial." }
Write-Output "PASS $Name on $Serial — marker verified"
