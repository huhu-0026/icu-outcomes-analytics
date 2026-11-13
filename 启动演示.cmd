@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "ICU_PYTHON=python"
if exist "D:\anaconda3\python.exe" set "ICU_PYTHON=D:\anaconda3\python.exe"
"%ICU_PYTHON%" app.py serve --mode demo --open
if errorlevel 1 pause