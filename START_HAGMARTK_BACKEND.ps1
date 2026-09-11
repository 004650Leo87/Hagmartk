$ErrorActionPreference = 'Stop'
$root = 'C:\Hagmartk Labs\Projeto\Hagmartk'
$backendPort = 8010
$frontendPort = 5180
$healthUrl = "http://127.0.0.1:$backendPort/health"
$logDir = Join-Path $root 'logs'
$controlLog = Join-Path $logDir 'hagmartk_backend_autostart.log'
$stdoutLog = Join-Path $logDir 'hagmartk_backend_stdout.log'
$stderrLog = Join-Path $logDir 'hagmartk_backend_stderr.log'

New-Item -ItemType Directory -Force -Path $logDir | Out-Null
foreach ($logFile in @($controlLog, $stdoutLog, $stderrLog)) {
    if ((Test-Path $logFile) -and ((Get-Item $logFile).Length -gt 5MB)) {
        Move-Item $logFile ($logFile + '.1') -Force
    }
}

function Test-HagmartkBackend {
    try {
        $response = Invoke-RestMethod $healthUrl -TimeoutSec 3
        return $response.status -eq 'ok'
    } catch {
        return $false
    }
}

if (Test-HagmartkBackend) {
    Add-Content $controlLog "$(Get-Date -Format o) backend already healthy; nothing to start"
    exit 0
}
$telegramEnvFile = Join-Path $root 'secrets\telegram.env'
if (Test-Path $telegramEnvFile) {
    Get-Content $telegramEnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
            $parts = $line.Split('=', 2)
            [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), 'Process')
        }
    }
}

$env:HAGMARTK_AUTOSTART = '1'
$env:HAGMARTK_MARKET_ADAPTER = 'unified'
$env:HAGMARTK_CYCLE_THEORY_SHADOW = '1'
$env:HAGMARTK_ORB_SHADOW = '1'
$env:HAGMARTK_CORS_ORIGINS = "http://127.0.0.1:$frontendPort,http://localhost:$frontendPort"

$pythonExe = (Get-Command python -ErrorAction Stop).Source
Set-Location $root

while ($true) {
    if (Test-HagmartkBackend) { exit 0 }
    $portOwner = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue
    if ($portOwner) {
        Add-Content $controlLog "$(Get-Date -Format o) port $backendPort occupied by PID $($portOwner.OwningProcess); retrying"
        Start-Sleep -Seconds 30
        continue
    }
    Add-Content $controlLog "$(Get-Date -Format o) starting backend"
    try {
        $cmdLine = "`"$pythonExe`" -m uvicorn backend.api.app:app --host 127.0.0.1 --port $backendPort 1>>`"$stdoutLog`" 2>>`"$stderrLog`""
        & $env:ComSpec /d /s /c $cmdLine
        $exitCode = $LASTEXITCODE
    } catch {
        $exitCode = 1
        Add-Content $controlLog "$(Get-Date -Format o) backend start exception: $($_.Exception.GetType().Name)"
    }

    Add-Content $controlLog "$(Get-Date -Format o) backend exited code=$exitCode; restarting in 10s"
    Start-Sleep -Seconds 10
}
