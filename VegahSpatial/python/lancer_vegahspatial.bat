@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  python -m venv .venv || (echo Python 3 est requis : https://www.python.org & pause & exit /b 1)
  .venv\Scripts\python -m pip install --upgrade pip >nul
  .venv\Scripts\pip install -r requirements.txt || (echo Echec de l installation & pause & exit /b 1)
)
.venv\Scripts\python -m vegah_spatial %*
if errorlevel 1 pause
