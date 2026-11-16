@echo off
cd /d "%~dp0"
echo UrbanOS is starting at http://127.0.0.1:5000
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "Backend\app.py"
) else (
  python "Backend\app.py"
)
