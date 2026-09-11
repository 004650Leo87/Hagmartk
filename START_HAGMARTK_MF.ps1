$ErrorActionPreference = 'Stop'
$root = 'C:\Hagmartk Labs\Projeto\Hagmartk'
$backendPort = 8010
$frontendPort = 5180
$apiUrl = "http://127.0.0.1:$backendPort"
$frontendUrl = "http://127.0.0.1:$frontendPort"
$backendScript = Join-Path $root 'START_HAGMARTK_BACKEND.ps1'

function Test-HagmartkBackend {
    try {
        $response = Invoke-RestMethod "$apiUrl/health" -TimeoutSec 3
        return $response.status -eq 'ok'
    } catch {
        return $false
    }
}

function Test-HagmartkFrontend {
    try {
        $response = Invoke-WebRequest $frontendUrl -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

Write-Host 'HAGMARTK MF - ponte dedicada' -ForegroundColor Cyan
Write-Host "Backend:  $apiUrl"
Write-Host "Frontend: $frontendUrl"
if (Test-HagmartkBackend) {
    Write-Host 'Backend ja esta online; mantendo processo atual.' -ForegroundColor DarkGreen
} else {
    $occupied = Get-NetTCPConnection -LocalPort $backendPort -State Listen -ErrorAction SilentlyContinue
    if ($occupied) {
        throw "Porta $backendPort ocupada por outro processo; backend HAGMARTK nao foi iniciado."
    }
    Start-Process powershell -ArgumentList '-NoProfile','-WindowStyle','Hidden','-ExecutionPolicy','Bypass','-File',$backendScript -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds(20)
    do {
        Start-Sleep -Milliseconds 500
        $healthy = Test-HagmartkBackend
    } until ($healthy -or (Get-Date) -ge $deadline)
    if (-not $healthy) { throw 'Backend HAGMARTK nao ficou saudavel dentro de 20 segundos.' }
    Write-Host 'Backend iniciado e saudavel.' -ForegroundColor Green
}

if (Test-HagmartkFrontend) {
    Write-Host 'Frontend ja esta online; mantendo processo atual.' -ForegroundColor DarkGreen
} else {
    $occupied = Get-NetTCPConnection -LocalPort $frontendPort -State Listen -ErrorAction SilentlyContinue
    if ($occupied) {
        throw "Porta $frontendPort ocupada por outro processo; frontend HAGMARTK nao foi iniciado."
    }
    $frontendCommand = "Set-Location '$root\frontend'; `$env:VITE_API_URL='$apiUrl'; npm run dev -- --host 127.0.0.1 --port $frontendPort --strictPort"
    Start-Process powershell -ArgumentList '-NoExit','-NoProfile','-Command',$frontendCommand -WindowStyle Minimized
    Start-Sleep -Seconds 2
    if (-not (Test-HagmartkFrontend)) { throw 'Frontend HAGMARTK nao respondeu em 5180.' }
    Write-Host 'Frontend iniciado e respondendo.' -ForegroundColor Green
}

Write-Host 'HAGMARTK MF operacional. Telegram depende do backend, nao do frontend.' -ForegroundColor Green
