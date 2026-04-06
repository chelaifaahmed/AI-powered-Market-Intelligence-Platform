@echo off
echo Starting the AI-Powered Automotive & Insurance Market Intelligence Platform...

echo Starting API Server...
start "API Server" cmd /k ".venv\Scripts\uvicorn.exe api.main:app --host 0.0.0.0 --port 8099"

echo Starting Dashboard...
start "Dashboard" cmd /k "cd dashboard && npm run dev"

echo Both systems have been started in separate windows!
pause
