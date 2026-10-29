$ErrorActionPreference='Stop'
$qaRoot='C:\Cloud\CloudEngine\build\setup-fix-verification'
$installDir=Join-Path $qaRoot 'Проверка установки\Cloud Engine'
New-Item -ItemType Directory -Force -Path $qaRoot | Out-Null
$blockedTemp=Join-Path $qaRoot 'blocked-temp'
Set-Content -LiteralPath $blockedTemp -Value 'This is a file, not a writable temporary directory.'
$env:TEMP=$blockedTemp
$env:TMP=$env:TEMP
$env:LOCALAPPDATA=Join-Path $qaRoot 'Runtime'
$env:QT_QPA_PLATFORM='offscreen'
$env:SDL_VIDEODRIVER='dummy'
$env:SDL_AUDIODRIVER='dummy'
New-Item -ItemType Directory -Force -Path $installDir | Out-Null
$userProject=Join-Path $installDir 'Моя игра.scene'
Set-Content -LiteralPath $userProject -Value 'User project must survive uninstall' -Encoding utf8
$setup=Join-Path $qaRoot 'CloudEngine-Installer-Verification.exe'
$argsList='/SP- /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LANG=russian /TASKS=desktopicon /DIR="'+$installDir+'" /LOG="'+$qaRoot+'\installation.log"'
$process=Start-Process -FilePath $setup -ArgumentList $argsList -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(45000)) { throw 'Setup timed out' }
if ($process.ExitCode -ne 0) { throw "Setup exit code $($process.ExitCode)" }
$engine=Join-Path $installDir 'CloudEngine.exe'
$source='C:\Cloud\CloudEngine\releases\Current\CloudEngine.exe'
$result=@{installation=$true; invalid_temp_regression=$true; file_integrity=((Get-FileHash -LiteralPath $engine).Hash -eq (Get-FileHash -LiteralPath $source).Hash)}
$shell=New-Object -ComObject WScript.Shell
foreach ($kind in @('Desktop','Start Menu')) {
    $shortcut=Join-Path $installDir ('Verification '+$kind+'\Cloud Engine 1.2.0-beta.6.lnk')
    $result['shortcut_'+$kind.Replace(' ','_')]=(Test-Path -LiteralPath $shortcut) -and ($shell.CreateShortcut($shortcut).TargetPath -eq $engine)
}
$report=Join-Path $qaRoot 'installed-engine.json'
$process=Start-Process -FilePath $engine -ArgumentList ('--smoke-test "'+$report+'"') -WorkingDirectory $installDir -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(90000)) { throw 'Installed engine test timed out' }
$checks=Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
$result.installed_engine_checks=(@($checks.PSObject.Properties | Where-Object { $_.Value -ne $true }).Count -eq 0)
$uninstaller=Join-Path $installDir 'unins000.exe'
$process=Start-Process -FilePath $uninstaller -ArgumentList ('/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG="'+$qaRoot+'\uninstall.log"') -WindowStyle Hidden -PassThru
if (-not $process.WaitForExit(45000)) { throw 'Uninstall timed out' }
for ($attempt=0; $attempt -lt 30 -and (Test-Path -LiteralPath $engine); $attempt++) { Start-Sleep -Milliseconds 200 }
$result.uninstall_removed_engine= -not (Test-Path -LiteralPath $engine)
$result.uninstall_kept_user_project=Test-Path -LiteralPath $userProject
$result.uninstall_removed_shortcuts= -not (Test-Path -LiteralPath (Join-Path $installDir 'Verification Desktop\Cloud Engine 1.2.0-beta.6.lnk'))
$result.registry_and_system_shortcuts='Not exercised: isolated verification build uses workspace shortcuts and no uninstall registry key.'
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $qaRoot 'installer-report.json') -Encoding utf8
$result | ConvertTo-Json
if (@($result.Values | Where-Object { $_ -is [bool] -and -not $_ }).Count) { throw 'An installer verification check failed' }
