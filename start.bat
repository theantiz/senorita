@echo off
title Senorita Launcher

echo Starting Senorita Backend...
start "Senorita Backend" cmd /k "cd backend && call .venv\Scripts\activate.bat && python run.py"

echo Starting Senorita Frontend (Next.js)...
start "Senorita Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo Development servers have been launched in separate windows!
echo - Backend will run on http://localhost:8000
echo - Frontend will run on http://localhost:3000
echo.
pause
