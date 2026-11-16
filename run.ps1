# AI Code Reviewer - Launch Script
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Starting AI Code Reviewer Platform     " -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# Check if PostgreSQL is running
$pgService = Get-Service -Name "*postgres*" -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Running" }
if (-not $pgService) {
    Write-Warning "PostgreSQL service is not running. Please ensure PostgreSQL is active."
}

# Start Backend in a dedicated window
Write-Host "Starting Backend API on http://localhost:8000..." -ForegroundColor Green
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\backend'; & '$PSScriptRoot\backend\.venv\Scripts\python.exe' -m uvicorn app.main:app --reload --port 8000"

# Start Frontend in a dedicated window
Write-Host "Starting Frontend UI on http://localhost:3000..." -ForegroundColor Green
Start-Process -FilePath "powershell.exe" -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot\frontend'; npm run dev"

Write-Host ""
Write-Host "Platform services launched:" -ForegroundColor Yellow
Write-Host "  - Frontend:  http://localhost:3000" -ForegroundColor Cyan
Write-Host "  - Backend:   http://localhost:8000" -ForegroundColor Cyan
Write-Host "  - API Docs:  http://localhost:8000/api/docs" -ForegroundColor Cyan

