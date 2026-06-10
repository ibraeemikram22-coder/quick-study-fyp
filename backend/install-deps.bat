@echo off
cd /d "%~dp0"
echo Installing packages into venv...
.\venv\Scripts\pip install -r requirements.txt
echo.
echo Done. Start server with: .\venv\Scripts\python app.py
pause
