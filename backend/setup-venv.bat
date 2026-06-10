@echo off
cd /d "%~dp0"
echo ============================================
echo  Fix venv for: FYP-Smart-Learning (6)
echo ============================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo Python not found. Install Python 3.11+ first.
  pause
  exit /b 1
)

if exist venv (
  echo Removing old venv (broken copy from another folder)...
  rmdir /s /q venv
)

echo Creating fresh venv in THIS folder...
python -m venv venv

echo Installing packages...
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install flask flask-cors python-dotenv requests sqlalchemy
echo Optional for Grammar page only:
echo   venv\Scripts\python.exe -m pip install language-tool-python

echo.
echo Testing sqlalchemy...
venv\Scripts\python.exe -c "import sqlalchemy; print('sqlalchemy OK:', sqlalchemy.__version__)"
if errorlevel 1 (
  echo INSTALL FAILED
  pause
  exit /b 1
)

echo.
echo ============================================
echo  Done! Start server with:
echo  venv\Scripts\python.exe app.py
echo ============================================
pause
