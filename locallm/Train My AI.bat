@echo off
title Train My AI
cd /d "%~dp0"

rem Find the Python that has torch installed. INSTALL.bat builds .venv next to
rem this file; setup_training.py builds .venv-train next to it instead; a
rem development checkout of the full repository may have one a level up.
rem None of the three is assumed -- if there is no usable Python this stops
rem and says what to run. The previous version pointed at a fixed path and,
rem when that path was missing, printed "The system cannot find the path
rem specified" and STILL EXITED 0.
set "PY="
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"
if not defined PY if exist "%~dp0.venv-train\Scripts\python.exe" set "PY=%~dp0.venv-train\Scripts\python.exe"
if not defined PY if exist "%~dp0..\.venv-train\Scripts\python.exe" set "PY=%~dp0..\.venv-train\Scripts\python.exe"

if not defined PY (
    echo.
    echo   This app is not set up on this computer yet.
    echo.
    echo   Run INSTALL.bat in this folder first. It installs what is needed
    echo   and picks the right version for your graphics card. Or, from a
    echo   command prompt: python setup_training.py
    echo.
    pause
    exit /b 1
)

"%PY%" "%~dp0start_studio.py"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo   Train My AI stopped with an error ^(code %RC%^).
    pause
)
exit /b %RC%
