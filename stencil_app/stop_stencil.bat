@echo off
REM ===========================
REM Stop Stencil Manager App
REM ===========================

echo Stopping Waitress server...

:: Kill all Python processes that are running waitress
taskkill /F /IM python.exe /FI "WINDOWTITLE eq cmd*" >nul 2>&1
taskkill /F /IM python.exe /FI "MODULES eq waitress" >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

echo Done.
pause
