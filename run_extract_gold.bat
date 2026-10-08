@echo off
setlocal
chcp 65001 >NUL
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
set PY=python
where py >NUL 2>&1 && set PY=py -3
if not exist logs mkdir logs

%PY% -c "import duckdb, streamlit, altair, pandas" >NUL 2>&1 || %PY% -m pip install -q -r requirements.txt

if not exist .env echo No .env file - copy .env.example to .env and put your Gemini key in it first.& pause& exit /b 1
%PY% -u -m src.extract --gold
%PY% -u -m src.baseline --gold
%PY% -u -m src.evaluate --split test --once
pause
