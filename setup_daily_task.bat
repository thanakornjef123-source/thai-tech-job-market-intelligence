@echo off
setlocal
chcp 65001 >NUL
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"
set PY=python
where py >NUL 2>&1 && set PY=py -3
if not exist logs mkdir logs

set LOG=logs\setup_task_log.txt
echo setup at %date% %time% > %LOG%
schtasks /create /tn ThaiTechJobsDaily /tr "\"%~dp0run_daily.bat\" auto" /sc daily /st 09:07 /f >> %LOG% 2>&1

rem Task Scheduler defaults would skip the run on battery power and never catch up after a missed 09:07.
rem This makes it start on battery, run as soon as possible after a missed start, never run two copies, and stop after 3 hours.
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 3); Set-ScheduledTask -TaskName ThaiTechJobsDaily -Settings $s | Out-Null; Write-Output 'settings updated'" >> %LOG% 2>&1

schtasks /query /tn ThaiTechJobsDaily /fo LIST >> %LOG% 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "(Get-ScheduledTask -TaskName ThaiTechJobsDaily).Settings | Format-List StartWhenAvailable,DisallowStartIfOnBatteries,StopIfGoingOnBatteries,ExecutionTimeLimit,MultipleInstances" >> %LOG% 2>&1
type %LOG%
echo.
echo Done. The task runs only while you are logged in to Windows (the PC must be on).
timeout /t 25
