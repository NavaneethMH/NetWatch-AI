@echo off
cd /d "%~dp0"
title NetWatch AI - Backend
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
) else (
    python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --workers 1
)
if errorlevel 1 pause
