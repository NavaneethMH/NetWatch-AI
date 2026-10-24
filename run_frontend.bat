@echo off
cd /d "%~dp0frontend"
title NetWatch AI - Frontend
if not exist "node_modules\" (
    echo Installing node dependencies...
    call npm.cmd install
)
call npm.cmd run dev
if errorlevel 1 pause
