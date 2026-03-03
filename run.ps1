# Start The Oracle — backend + frontend
# Usage: .\run.ps1       (starts both)
#        .\run.ps1 stop  (kills both)

$projectDir = $PSScriptRoot

if ($args[0] -eq "stop") {
    Write-Host "Stopping The Oracle..." -ForegroundColor Yellow
    Get-Process -Name python, node -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "Done." -ForegroundColor Cyan
    exit
}

# Kill any leftover processes first
Get-Process -Name python, node -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

Write-Host "Starting The Oracle..." -ForegroundColor Cyan

# Start backend in a new window
$backendCmd = "Set-Location '$projectDir\backend'; uv run --project '$projectDir' uvicorn main:app --reload --port 8050; Read-Host 'Press Enter to close'"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd

# Start frontend in a new window
$frontendCmd = "Set-Location '$projectDir\frontend'; npm run dev; Read-Host 'Press Enter to close'"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd

Write-Host ""
Write-Host "Backend:  http://localhost:8050" -ForegroundColor Green
Write-Host "Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host ""
Write-Host "To stop both: .\run.ps1 stop" -ForegroundColor Yellow
