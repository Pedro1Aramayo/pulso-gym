@echo off
cd /d "%~dp0"
if not exist .env (
  echo Primero ejecute instalar.bat y configure .env.
  pause
  exit /b 1
)
docker compose up -d --wait
if errorlevel 1 (
  echo Abra Docker Desktop y revise su configuracion.
  pause
  exit /b 1
)
.venv\Scripts\python.exe main.py
pause
