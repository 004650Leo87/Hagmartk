$ErrorActionPreference = 'Stop'
$root = 'C:\Hagmartk Labs\Projeto\Hagmartk'
$backendPort = 8010
$frontendPort = 5180
$apiUrl = "http://127.0.0.1:$backendPort"

$telegramEnvFile = Join-Path $root 'secrets\telegram.env'
if (Test-Path $telegramEnvFile) {
    Get-Content $telegramEnvFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
            $parts = $line.Split('=', 2)
            [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), 'Process')
        }
    }
    Write-Host 'Telegram config local carregada (segredos ocultos).' -ForegroundColor DarkGreen
}

Write-Host 'HAGMARTK MF - ponte dedicada' -ForegroundColor Cyan
Write-Host "Backend:  $apiUrl"
Write-Host "Frontend: http://127.0.0.1:$frontendPort"

$busy = @()
foreach ($port in @($backendPort, $frontendPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        $busy += $port
    }
}
if ($busy.Count -gt 0) {
    throw "Porta(s) HAGMARTK ocupada(s): $($busy -join ', '). Nada foi iniciado."
}

$backendCommand = "Set-Location '$root'; `$env:HAGMARTK_AUTOSTART='1'; `$env:HAGMARTK_MARKET_ADAPTER='mt5'; `$env:HAGMARTK_CORS_ORIGINS='http://127.0.0.1:$frontendPort,http://localhost:$frontendPort'; python -m uvicorn backend.api.app:app --host 127.0.0.1 --port $backendPort"
$frontendCommand = "Set-Location '$root\frontend'; `$env:VITE_API_URL='$apiUrl'; npm run dev -- --host 127.0.0.1 --port $frontendPort --strictPort"

Start-Process powershell -ArgumentList '-NoExit','-NoProfile','-Command',$backendCommand -WindowStyle Normal
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList '-NoExit','-NoProfile','-Command',$frontendCommand -WindowStyle Normal

Write-Host 'Ponte HAGMARTK MF iniciada em janelas independentes.' -ForegroundColor Green
