@echo off
title Copy to Git folder
color 0B
echo.
echo ============================================
echo   COPY THIS FOLDER TO YOUR GIT FOLDER
echo ============================================
echo.
echo 1. Open TWO windows in File Explorer:
echo.
echo    SOURCE (copy FROM):
echo    %~dp0
echo.
echo    DESTINATION: your Git folder on local drive
echo.
echo 2. Select ALL inside this folder:
echo    - frontend
echo    - backend
echo    - START_PROJECT.bat
echo    - CLEAR_SESSION.bat
echo    - .gitignore
echo    - render.yaml
echo    - GIT-COPY-README.bat
echo.
echo 3. DO NOT copy if you see:
echo    - backend\venv
echo    - backend\.env  (keep your own .env locally only)
echo.
echo 4. Paste into Git folder (Replace All if asked)
echo.
echo 5. In Git folder PowerShell:
echo    git add .
echo    git commit -m "Final project"
echo    git push
echo.
echo NOTE: backend\.env stays on YOUR PC only - never on GitHub.
echo       uploads folder is EMPTY - books upload on live server later.
echo.
pause
