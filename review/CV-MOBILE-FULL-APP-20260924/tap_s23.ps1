param([Parameter(Mandatory=$true)][string]$Text,[string]$Serial='R3CW40FY82W')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
& adb -s $Serial shell uiautomator dump /sdcard/cv_mobile_tap.xml | Out-Null
& adb -s $Serial pull /sdcard/cv_mobile_tap.xml (Join-Path $root 'tap_current.xml') | Out-Null
$doc=[xml][System.IO.File]::ReadAllText((Join-Path $root 'tap_current.xml'))
$node=@($doc.SelectNodes('//node') | Where-Object { $_.GetAttribute('text') -eq $Text -or $_.GetAttribute('content-desc') -eq $Text } | Select-Object -First 1)
if($node.Count -eq 0){throw "No visible UI target matched."}
$bounds=$node[0].GetAttribute('bounds')
$m=[regex]::Matches($bounds,'\d+')
$x=[int](([int]$m[0].Value+[int]$m[2].Value)/2)
$y=[int](([int]$m[1].Value+[int]$m[3].Value)/2)
& adb -s $Serial shell input tap $x $y
Start-Sleep -Milliseconds 900
Write-Output "Tapped visible target at $x,$y"
