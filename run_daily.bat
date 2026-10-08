@echo off
setlocal
chcp 65001 >NUL
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
set PY=python
where py >NUL 2>&1 && set PY=py -3
if not exist logs mkdir logs

set LOG=logs\daily_log.txt
set FAILED=
if exist %LOG% for %%F in (%LOG%) do if %%~zF gtr 1000000 move /y %LOG% logs\daily_log.old.txt >NUL
echo ===== run at %date% %time% >> %LOG%
%PY% -c "import duckdb, streamlit, altair, pandas, google.genai" >NUL 2>&1 || %PY% -m pip install -q -r requirements.txt >> %LOG% 2>&1

rem --- collect -> stage -> dedupe: if any of these fail there is nothing new to process, stop here
%PY% -u -m src.collect >> %LOG% 2>&1
if errorlevel 1 set FAILED=%FAILED% collect& goto :fail
%PY% -u -m src.stage >> %LOG% 2>&1
if errorlevel 1 set FAILED=%FAILED% stage& goto :fail
%PY% -u -m src.dedupe >> %LOG% 2>&1
if errorlevel 1 set FAILED=%FAILED% dedupe& goto :fail

rem --- the remaining steps are independent: run all of them, remember which failed
%PY% -u -m src.check >> %LOG% 2>&1
if errorlevel 1 set FAILED=%FAILED% check
%PY% -u -m src.baseline >> %LOG% 2>&1
if errorlevel 1 set FAILED=%FAILED% baseline
if not exist .env goto :after_llm
%PY% -u -m src.extract --gold >> %LOG% 2>&1
if errorlevel 1 set FAILED=%FAILED% extract-gold
%PY% -u -m src.extract >> %LOG% 2>&1
if errorlevel 1 set FAILED=%FAILED% extract
%PY% -u -m src.evaluate --split test --once >> %LOG% 2>&1
if errorlevel 1 set FAILED=%FAILED% evaluate
:after_llm
%PY% -u -m src.stats >> %LOG% 2>&1
if errorlevel 1 set FAILED=%FAILED% stats
%PY% -u -m src.marts >> %LOG% 2>&1
if errorlevel 1 set FAILED=%FAILED% marts
%PY% -u -m src.snapshot >> %LOG% 2>&1
if errorlevel 1 set FAILED=%FAILED% snapshot
rem --- push the refreshed snapshot to GitHub (skipped quietly if Git for Windows is not installed)
call publish.bat auto >> %LOG% 2>&1
set PUBRC=%errorlevel%
if "%PUBRC%"=="1" set FAILED=%FAILED% publish

if defined FAILED goto :fail
echo OK >> %LOG%
if exist logs\LAST_FAILED.txt del logs\LAST_FAILED.txt
set RC=0
goto :end

:fail
echo FAILED:%FAILED% >> %LOG%
echo %date% %time% failed steps:%FAILED% - see logs\daily_log.txt > logs\LAST_FAILED.txt
msg "%USERNAME%" "Thai tech jobs: daily run failed (%FAILED% ) - see logs\daily_log.txt" 2>NUL
set RC=1

:end
if "%1"=="" pause
exit /b %RC%
