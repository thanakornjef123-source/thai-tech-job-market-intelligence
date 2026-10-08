@echo off
setlocal
chcp 65001 >NUL
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
set PY=python
where py >NUL 2>&1 && set PY=py -3
if not exist logs mkdir logs

set LOG=logs\discover_log.txt
echo run at %date% %time% > %LOG%
%PY% -u -m src.discover >> %LOG% 2>&1
type %LOG%
if "%1"=="" pause
