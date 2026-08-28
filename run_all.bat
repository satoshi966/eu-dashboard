@echo off
setlocal

rem ==========================================================================
rem  EU Dashboard - daily data update
rem
rem  This file only starts run_all.py. All of the real work, and the
rem  Japanese log messages, live in run_all.py.
rem  (A .bat file cannot safely contain Japanese text, so it is kept ASCII.)
rem
rem  Log files:  logs\run_YYYYMMDD_HHMMSS.log  and  logs\latest.log
rem ==========================================================================

rem --- Path to Python. Edit this line if Python is installed elsewhere. ---
rem     %LOCALAPPDATA% expands to C:\Users\<your name>\AppData\Local
set "PYTHON=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"

rem     If that exact path is missing, fall back to "python" from PATH.
if not exist "%PYTHON%" set "PYTHON=python"

rem --- Move to the folder that contains this .bat file. ---
rem     Task Scheduler starts in C:\Windows\System32, so this is required.
cd /d "%~dp0"

rem --- Make Python print UTF-8 so Japanese text is written correctly. ---
set "PYTHONIOENCODING=utf-8"
set "PYTHONUNBUFFERED=1"

rem --- Make sure Python actually runs. ---
rem     "if not exist" cannot be used here, because PYTHON may be the bare
rem     command name "python" rather than a full file path.
"%PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python could not be started: %PYTHON%
    exit /b 1
)

"%PYTHON%" "%~dp0run_all.py"
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo [ERROR] Update finished with errors. See logs\latest.log
)

exit /b %RC%
