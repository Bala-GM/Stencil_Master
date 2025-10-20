@echo off
REM ===========================
REM Start Stencil Manager App
REM ===========================

cd /d "D:\VS Code\Pyweb"
echo Starting Stencil Manager...
python -m waitress --listen=0.0.0.0:5005 stencil_app.app:app

pause
