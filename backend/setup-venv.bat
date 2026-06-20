@echo off
cd /d "%~dp0"
echo ============================================
echo  Fix venv for this project folder
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Python not found. Install Python 3.11+ first.
  pause
  exit /b 1
)

if exist venv (
  echo Removing old venv...
  rmdir /s /q venv
)

echo Creating fresh venv...
python -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
if exist requirements-deploy.txt (
  venv\Scripts\python.exe -m pip install -r requirements-deploy.txt
) else if exist requirements.txt (
  venv\Scripts\python.exe -m pip install -r requirements.txt
)
venv\Scripts\python.exe -m pip install flask flask-cors python-dotenv requests sqlalchemy pymysql pypdf python-docx google-generativeai gunicorn

powershell -NoProfile -Command "Set-Content -LiteralPath 'venv\.install_root' -Value '%CD%' -NoNewline"
echo ok>.deps_ok

echo.
echo Testing backend...
venv\Scripts\python.exe -c "from app import app; print('Backend OK')"
if errorlevel 1 (
  echo INSTALL FAILED — read error above
  pause
  exit /b 1
)

echo.
echo Done! Use START_PROJECT.bat in project root.
pause
