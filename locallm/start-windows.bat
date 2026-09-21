@echo off
title locallm
rem Starts locallm on Windows. Double-click it, or run it from a command
rem prompt. It installs nothing and downloads nothing: it finds a Python,
rem checks the one piece that is sometimes missing, and opens the window.
rem
rem If Windows warns that it protected your PC, that is SmartScreen, and it
rem says so about every file downloaded from anywhere. Click More info, then
rem Run anyway, if you trust where you got this.

setlocal

rem WHERE THIS FILE IS, which is not where you happen to be. %0 is this file,
rem and the ~dp in front of it means "drive letter and path only", ending in a
rem backslash
rem (learn.microsoft.com/en-us/windows-server/administration/windows-commands/call).
rem So HERE below, with the name of the program stuck on the end, is the file
rem sitting next to this one however this one was started, and a shortcut that
rem starts it from somewhere else cannot send it looking in the wrong folder.
rem The quotes are what makes a stick at E:\My Stick work like any other drive.
set "HERE=%~dp0"

rem py first: the launcher that comes with the installer from python.org picks
rem the newest Python 3 rather than whatever was installed last, and system
rem installs of 3.3 and later put it on PATH
rem (docs.python.org/3/using/windows.html). python second, for a machine that
rem has Python but not the launcher. Neither name is assumed to exist.
set "PY="
set "PYOPT="
where py >nul 2>nul && set "PY=py" && set "PYOPT=-3"
if not defined PY where python >nul 2>nul && set "PY=python"

rem A candidate has to say its own version before it is accepted. On Windows
rem "python" can be the Microsoft Store stub, which exists, answers, and is not
rem a Python at all; it fails this and is put back.
if defined PY (
    "%PY%" %PYOPT% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if errorlevel 1 set "PY="
)

if not defined PY goto :no_python
if not exist "%HERE%home.py" goto :no_program

rem THE CHECK THAT TURNS A TRACEBACK INTO A SENTENCE. tkinter draws the window,
rem and Python's own documentation calls it an optional module that can be
rem missing from a working copy of Python
rem (docs.python.org/3/library/tkinter.html). The ordinary Windows installer
rem includes it, but the "embeddable" zip never does. Asking costs 13 ms,
rem measured on Linux. Not asking costs a page of traceback ending in
rem ImportError, which names nothing a stranger can act on.
"%PY%" %PYOPT% -c "import tkinter" >nul 2>nul
if errorlevel 1 goto :no_tk

"%PY%" %PYOPT% "%HERE%home.py" %*
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo   locallm stopped with an error ^(code %RC%^).
    echo.
    echo   Whatever is printed above this line is what Python said. It is the
    echo   useful part if you ask anyone about it, so copy it before closing.
    echo.
    pause
)
exit /b %RC%

:no_python
echo.
echo   No Python 3.10 or newer was found on this computer.
echo.
echo   Windows does not come with one. Get it from python.org/downloads and
echo   tick "Add python.exe to PATH" in the installer, then double-click this
echo   file again.
echo.
pause
exit /b 1

:no_program
echo.
echo   The program is not in this folder:
echo.
echo       %HERE%
echo.
echo   This file only starts locallm; it is not locallm. Keep it together with
echo   the rest of the folder it arrived in, or unzip that folder again and
echo   start from there.
echo.
pause
exit /b 1

:no_tk
echo.
echo   Python is here, but the part that draws windows is not.
echo.
echo   The ordinary installer from python.org includes it. The "embeddable"
echo   zip download deliberately does not. Install Python from
echo   python.org/downloads and double-click this file again.
echo.
echo   START-HERE.md in this folder has the rest, including what still works
echo   while you have no window.
echo.
pause
exit /b 1
