@echo off
rem Cetakan - jalankan dengan klik dua kali
cd /d "%~dp0"
where python >nul 2>nul || (echo Python belum terpasang. Unduh dari https://www.python.org/downloads/ lalu centang "Add python.exe to PATH". & pause & exit /b 1)
if not exist .venv (
  echo Menyiapkan Cetakan untuk pertama kali, mohon tunggu...
  python -m venv .venv || (pause & exit /b 1)
  .venv\Scripts\python -m pip install --disable-pip-version-check -q -r requirements.txt || (pause & exit /b 1)
)
.venv\Scripts\python -m cetakan --port 8000 --buka
pause
