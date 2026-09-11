$ErrorActionPreference = 'Stop'
$root = 'C:\Hagmartk Labs\Projeto\Hagmartk'
$taskName = 'HAGMARTK_MF_Backend'
$scriptPath = Join-Path $root 'START_HAGMARTK_BACKEND.ps1'

if (-not (Test-Path $scriptPath)) {
    throw "Backend launcher not found: $scriptPath"
}

$actionArgs = @{
    Execute = 'powershell.exe'
    Argument = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`""
}
$action = New-ScheduledTaskAction @actionArgs
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settingsArgs = @{
    AllowStartIfOnBatteries = $true
    DontStopIfGoingOnBatteries = $true
    StartWhenAvailable = $true
    RestartCount = 10
    RestartInterval = (New-TimeSpan -Minutes 1)
    ExecutionTimeLimit = [TimeSpan]::Zero
}
$settings = New-ScheduledTaskSettingsSet @settingsArgs
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'HAGMARTK Mercado Financeiro backend/scanners/Telegram autostart' -Force | Out-Null
Write-Host "Scheduled task installed: $taskName"
