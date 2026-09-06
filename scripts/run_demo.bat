@echo off
REM B-SHIELD (IBVAP) — One-Command Windows Batch Launcher
echo ============================================================
echo  B-SHIELD (IBVAP)
echo  AI-Powered Intelligent Border Surveillance Command Center
echo ============================================================
echo MODE: DEMO / EVALUATION ONLY
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_demo.ps1"
pause
