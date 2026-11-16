@echo off
echo =========================================
echo   Starting AI Code Reviewer Platform
echo =========================================

echo Starting Backend API on http://localhost:8000...
start "AI Code Reviewer - Backend" cmd /k "cd /d "%~dp0backend" && ..\backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"

echo Starting Frontend UI on http://localhost:3000...
start "AI Code Reviewer - Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo Platform services launched:
echo   - Frontend:  http://localhost:3000
echo   - Backend:   http://localhost:8000
echo   - API Docs:  http://localhost:8000/api/docs
echo.
pause

