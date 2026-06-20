@echo off
setlocal EnableExtensions
title Quick Study Builder - START
color 0A

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "PY=%BACKEND%\venv\Scripts\python.exe"
set "DEPS_OK=%BACKEND%\.deps_ok"
set "VENV_MARKER=%BACKEND%\venv\.install_root"

echo ============================================
echo   Quick Study Builder
echo ============================================
echo   Folder: %ROOT%
echo.

net start MySQL80 >nul 2>&1
net start MySQL >nul 2>&1

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Python not installed. Install Python 3.11+ from python.org
  pause
  exit /b 1
)

call :EnsureVenv
if errorlevel 1 (
  echo ERROR: Could not create Python venv.
  pause
  exit /b 1
)

if exist "%DEPS_OK%" goto skip_pip
echo Installing packages (first run or after update)...
"%PY%" -m pip install --upgrade pip >nul 2>&1
"%PY%" -m pip install flask flask-cors python-dotenv requests sqlalchemy pymysql pypdf python-docx -q
if errorlevel 1 (
  echo ERROR: pip install failed.
  pause
  exit /b 1
)
echo ok>"%DEPS_OK%"
echo Packages ready.
goto after_pip

:skip_pip
echo Packages already installed — skipping pip (fast start).

:after_pip
echo Testing backend import...
"%PY%" -c "from app import app" 2>"%TEMP%\qsb_start_err.txt"
if errorlevel 1 (
  echo.
  echo ERROR: Backend cannot start. Details:
  type "%TEMP%\qsb_start_err.txt"
  echo.
  echo Fix: double-click backend\setup-venv.bat then run this file again.
  pause
  exit /b 1
)

echo Starting backend on port 3000...
start "QSB Backend - DO NOT CLOSE" cmd /k "cd /d ""%BACKEND%"" && ""%PY%"" app.py"

echo Starting frontend on port 5500...
start "QSB Frontend" cmd /k "cd /d ""%FRONTEND%"" && python -m http.server 5500"

echo Waiting for backend health check...
set /a WAIT=0
:wait_health
timeout /t 2 /nobreak >nul
set /a WAIT+=2
powershell -NoProfile -Command "try { (Invoke-WebRequest -Uri 'http://localhost:3000/api/health' -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200 } catch { $false }" | findstr /I "True" >nul
if not errorlevel 1 goto health_ok
if %WAIT% LSS 24 goto wait_health

echo.
echo WARNING: Backend slow to start. Check the "QSB Backend" window for errors.
goto open_browser

:health_ok
echo Backend is online.

:open_browser
start "" http://localhost:5500
echo.
echo Backend:  http://localhost:3000/api/health
echo Frontend: http://localhost:5500
echo.
echo *** Keep the "QSB Backend" window open ***
echo.
pause
exit /b 0

:EnsureVenv
if not exist "%PY%" goto build_venv
if not exist "%VENV_MARKER%" goto build_venv
powershell -NoProfile -Command "$m=Get-Content -LiteralPath '%VENV_MARKER%' -Raw -ErrorAction SilentlyContinue; if ($m -eq '%BACKEND%') { exit 0 } else { exit 1 }"
if not errorlevel 1 exit /b 0

:build_venv
echo.
echo Creating fresh virtual environment...
if exist "%BACKEND%\venv" rmdir /s /q "%BACKEND%\venv"
python -m venv "%BACKEND%\venv"
if not exist "%PY%" exit /b 1
powershell -NoProfile -Command "Set-Content -LiteralPath '%VENV_MARKER%' -Value '%BACKEND%' -NoNewline"
if exist "%DEPS_OK%" del /q "%DEPS_OK%"
exit /b 0
