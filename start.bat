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

echo Building dashboard database...
%PY% -m src.marts
if errorlevel 1 echo [WARNING] could not rebuild the database - showing the previous one if it exists
echo Opening dashboard at http://127.0.0.1:8501  (close this window to stop)
rem open the browser a few seconds later, after the server is up (server.headless=true in .streamlit/config.toml, so Streamlit never asks for an e-mail)
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep 8; Start-Process 'http://127.0.0.1:8501'"
%PY% -m streamlit run app.py --server.address 127.0.0.1 > logs\dashboard_log.txt 2>&1
echo.
echo The dashboard has stopped. Last output (also saved in logs\dashboard_log.txt):
type logs\dashboard_log.txt
pause
