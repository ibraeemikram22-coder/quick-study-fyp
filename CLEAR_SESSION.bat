@echo off
title Clear Login Session
echo.
echo Clearing saved login from this browser...
echo Opening clear-session page...
echo.
start "" "%~dp0frontend\clear-session.html"
echo Done. Browser mein session clear ho jayega, phir Sign up page khulega.
echo.
pause
