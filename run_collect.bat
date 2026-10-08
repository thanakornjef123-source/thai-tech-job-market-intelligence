@echo off
setlocal
chcp 65001 >NUL
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
set PY=python
where py >NUL 2>&1 && set PY=py -3
if not exist logs mkdir logs

set LOG=logs\collect_log.txt
echo run at %date% %time% using %PY% > %LOG%
%PY% --version >> %LOG% 2>&1
%PY% -u -m src.collect >> %LOG% 2>&1
if errorlevel 1 goto :end
%PY% -u -m src.stage >> %LOG% 2>&1
if errorlevel 1 goto :end
%PY% -u -m src.dedupe >> %LOG% 2>&1
:end
type %LOG%
if "%1"=="" pause
