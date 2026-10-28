$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root "backend\.venv\Scripts\python.exe"
$Frontend = Join-Path $Root "frontend"
$LogDir = Join-Path $Root "backend\data"

if (-not (Test-Path $Python)) {
    Write-Error "Backend virtual environment not found. Follow the setup steps in README.md."
}
if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
    Write-Error "Frontend dependencies not found. Run npm install in frontend\ first."
}
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Wait-Http {
    param([string]$Url, [System.Diagnostics.Process]$Process, [string]$ErrorLog)
    foreach ($attempt in 1..30) {
        if ($Process.HasExited) {
            Write-Host "Process exited early. Log: $ErrorLog"
            if (Test-Path $ErrorLog) { Get-Content $ErrorLog -Tail 40 }
            return $false
        }
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return $true }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    Write-Host "Timed out waiting for $Url"
    if (Test-Path $ErrorLog) { Get-Content $ErrorLog -Tail 40 }
    return $false
}

$backendOut = Join-Path $LogDir "backend.out.log"
$backendErr = Join-Path $LogDir "backend.err.log"
$frontendOut = Join-Path $LogDir "frontend.out.log"
$frontendErr = Join-Path $LogDir "frontend.err.log"

$backend = Start-Process -FilePath $Python -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") -WorkingDirectory (Join-Path $Root "backend") -PassThru -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr
if (-not (Wait-Http -Url "http://127.0.0.1:8000/health" -Process $backend -ErrorLog $backendErr)) {
    if (-not $backend.HasExited) { Stop-Process -Id $backend.Id -Force }
    exit 1
}

$frontendProcess = Start-Process -FilePath "npm.cmd" -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173") -WorkingDirectory $Frontend -PassThru -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr
if (-not (Wait-Http -Url "http://127.0.0.1:5173" -Process $frontendProcess -ErrorLog $frontendErr)) {
    if (-not $frontendProcess.HasExited) { Stop-Process -Id $frontendProcess.Id -Force }
    if (-not $backend.HasExited) { Stop-Process -Id $backend.Id -Force }
    exit 1
}

Write-Host "RecallFlow is running."
Write-Host "Dashboard: http://127.0.0.1:5173"
Write-Host "API docs:  http://127.0.0.1:8000/docs"
Write-Host "Backend PID $($backend.Id), frontend PID $($frontendProcess.Id)."
Write-Host "Logs: $LogDir"
