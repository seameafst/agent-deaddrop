@echo off
rem Daily observatory report (manual run helper).
rem Scheduled generation is handled by the watchdog task after 09:00.
cd /d "%~dp0.."
if not exist "data\reports" mkdir "data\reports"
".venv\Scripts\python.exe" "tools\daily_report.py" >> "data\reports\scheduler.log" 2>&1
exit /b %errorlevel%
