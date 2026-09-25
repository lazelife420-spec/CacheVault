param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Marker,
    [string]$Serial = 'R3CW40FY82W'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$devicePng = '/sdcard/cv_mobile_capture.png'
$deviceXml = '/sdcard/cv_mobile_capture.xml'
& adb -s $Serial shell screencap -p $devicePng | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'S23 screenshot capture failed.' }
& adb -s $Serial pull $devicePng (Join-Path $root "$Name.png") | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'S23 screenshot transfer failed.' }
& adb -s $Serial shell uiautomator dump $deviceXml | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'S23 UI marker dump failed.' }
& adb -s $Serial pull $deviceXml (Join-Path $root "$Name.xml") | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'S23 marker transfer failed.' }
$doc = [xml][System.IO.File]::ReadAllText((Join-Path $root "$Name.xml"))
$visibleText = @($doc.SelectNodes('//node[@text!=""]') | ForEach-Object { $_.GetAttribute('text') })
if ($visibleText -notcontains $Marker) { throw "Marker verification failed for $Name." }
Write-Output "PASS $Name — marker verified"
