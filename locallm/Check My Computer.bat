@echo off
title Check My Computer
cd /d "%~dp0"

rem This one deliberately falls back further than Train My AI does. The whole
rem point of check_my_computer.py is that it runs BEFORE anything is set up and
rem says "PyTorch is not installed, here is the command" instead of dying, so it
rem must work with whatever Python the computer already has. It is stdlib-only
rem until it tries to import torch, and it handles that import failing.
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0.venv-train\Scripts\python.exe" set "PY=%~dp0.venv-train\Scripts\python.exe"
if not defined PY if exist "%~dp0..\.venv-train\Scripts\python.exe" set "PY=%~dp0..\.venv-train\Scripts\python.exe"
if not defined PY where py >nul 2>nul && set "PY=py"
if not defined PY where python >nul 2>nul && set "PY=python"

if not defined PY (
    echo.
    echo   Python is not installed on this computer.
    echo.
    echo   Get it from https://www.python.org/downloads/ ^(version 3.10 or
    echo   newer^), tick "Add python.exe to PATH" during setup, then run this
    echo   again.
    echo.
    pause
    exit /b 1
)

"%PY%" "%~dp0check_my_computer.py"
set "RC=%ERRORLEVEL%"
pause
exit /b %RC%
