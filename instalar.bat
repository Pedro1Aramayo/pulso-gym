@echo off
cd /d "%~dp0"
py -3.12 -m venv .venv
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto error
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
if not exist .env copy .env.example .env
echo Instalacion terminada. Edite .env, abra Docker Desktop y ejecute iniciar.bat.
pause
exit /b 0
:error
echo No se pudo instalar. Revise el error mostrado arriba. Se requiere Python 3.12.
pause
exit /b 1
