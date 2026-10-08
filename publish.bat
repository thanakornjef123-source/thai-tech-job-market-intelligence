@echo off
rem Commit the refreshed online-dashboard data (data/snapshot, data/eval, results.md) and push it to GitHub.
rem   publish.bat        -> run by hand (first time: a GitHub sign-in window may appear once)
rem   publish.bat auto   -> called by run_daily.bat (never waits for a sign-in window)
rem Exit codes: 0 = done, 1 = failed, 2 = skipped (Git not installed / not a repository)
setlocal
cd /d "%~dp0"
set "GIT="
where git >NUL 2>&1 && set "GIT=git"
if not defined GIT if exist "%ProgramFiles%\Git\cmd\git.exe" set "GIT=%ProgramFiles%\Git\cmd\git.exe"
rem fall back to the Git bundled with GitHub Desktop (includes Git Credential Manager)
if not defined GIT for /d %%D in ("%LOCALAPPDATA%\GitHubDesktop\app-*") do if exist "%%D\resources\app\git\cmd\git.exe" set "GIT=%%D\resources\app\git\cmd\git.exe"
if not defined GIT goto :nogit
if not exist .git goto :norepo
if /i "%~1"=="auto" set "GCM_INTERACTIVE=never"
if /i "%~1"=="auto" set "GIT_TERMINAL_PROMPT=0"
for /f %%D in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set "TODAY=%%D"

"%GIT%" -c safe.directory=* add -- data/snapshot data/eval results.md
if errorlevel 1 goto :failed
"%GIT%" -c safe.directory=* diff --cached --quiet
if errorlevel 1 "%GIT%" -c safe.directory=* commit -q -m "Update data %TODAY%"
if errorlevel 1 goto :failed
"%GIT%" -c safe.directory=* push -q origin main
if errorlevel 1 goto :failed
echo [publish] done - online dashboard data pushed (%TODAY%)
if /i not "%~1"=="auto" pause
exit /b 0

:nogit
echo [publish] skipped: Git was not found (install GitHub Desktop or Git for Windows)
if /i not "%~1"=="auto" pause
exit /b 2

:norepo
echo [publish] skipped: this folder is not a git repository
if /i not "%~1"=="auto" pause
exit /b 2

:failed
echo [publish] FAILED - run publish.bat by hand to see the error or sign in to GitHub
if /i not "%~1"=="auto" pause
exit /b 1
