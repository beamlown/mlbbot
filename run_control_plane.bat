@echo off
REM =====================================================================
REM  Control Plane launcher — pulls latest code on the feature branch
REM  and starts the Flask server at http://127.0.0.1:8787
REM
REM  Just double-click this file.
REM
REM  It does NOT overwrite your local changes. If `git pull` can't
REM  fast-forward (e.g. you have uncommitted edits), it stops and tells
REM  you what to do instead of stomping on your work.
REM =====================================================================

setlocal EnableExtensions EnableDelayedExpansion
title Control Plane
cd /d "%~dp0"

set "BRANCH=claude/bot-bridge-dashboard-yv9by"
set "PORT=8787"
set "HOST=127.0.0.1"
set "URL=http://%HOST%:%PORT%/"

echo.
echo =========================================================
echo  Control Plane launcher
echo  repo   : %CD%
echo  branch : %BRANCH%
echo  url    : %URL%
echo =========================================================
echo.

REM --- Sanity: are we inside a git checkout? --------------------------------
git rev-parse --git-dir >nul 2>&1
if errorlevel 1 (
  echo [!] This folder is not a git checkout. Aborting.
  goto :fail
)

REM --- Warn if there are uncommitted changes --------------------------------
for /f "delims=" %%D in ('git status --porcelain') do (
  echo [!] You have uncommitted local changes:
  git status --short
  echo.
  echo     The launcher will NOT touch them. Commit or stash first if
  echo     you want the very latest code from the remote.
  echo.
  goto :after_pull
)

REM --- Fetch + fast-forward pull --------------------------------------------
echo [*] Fetching origin/%BRANCH% ...
git fetch origin %BRANCH%
if errorlevel 1 (
  echo [!] git fetch failed. Network / auth issue? Continuing with local copy.
  goto :after_pull
)

for /f "delims=" %%B in ('git rev-parse --abbrev-ref HEAD') do set "CURRENT=%%B"
if /i not "!CURRENT!"=="%BRANCH%" (
  echo [*] Switching from !CURRENT! to %BRANCH% ...
  git switch %BRANCH%
  if errorlevel 1 (
    echo [!] Could not switch branches. Aborting.
    goto :fail
  )
)

echo [*] Pulling (fast-forward only) ...
git pull --ff-only origin %BRANCH%
if errorlevel 1 (
  echo [!] git pull failed (maybe diverged history). Leaving local copy untouched.
)

:after_pull

REM --- Kill anything already bound to the port ------------------------------
echo [*] Checking for an existing server on port %PORT% ...
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
  echo     killing pid %%P
  taskkill /F /PID %%P >nul 2>&1
)

REM --- Pick a python interpreter --------------------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if "!PY!"=="" where python >nul 2>&1 && set "PY=python"
if "!PY!"=="" (
  echo [!] No python found on PATH. Install Python 3.10+ and re-run.
  goto :fail
)
echo [*] Using interpreter: !PY!

REM --- Confirm Flask is importable ------------------------------------------
!PY! -c "import flask" >nul 2>&1
if errorlevel 1 (
  echo [*] Flask not installed. Running: !PY! -m pip install flask
  !PY! -m pip install --quiet flask
  if errorlevel 1 (
    echo [!] pip install flask failed. Aborting.
    goto :fail
  )
)

REM --- Launch + open browser ------------------------------------------------
echo.
echo [*] Starting control plane on %URL%
echo     (press Ctrl+C in this window to stop)
echo.
start "" "%URL%"
!PY! -m flask --app control_plane.app run --host %HOST% --port %PORT%
goto :end

:fail
echo.
pause
exit /b 1

:end
endlocal
pause
