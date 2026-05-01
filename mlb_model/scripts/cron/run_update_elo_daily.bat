@echo off
REM Daily Elo refresh — registered as Windows scheduled task `mlb-elo-daily`
cd /d "C:\Users\johnny\Desktop\mlb_model"
"C:\Users\johnny\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\update_elo_daily.py >> logs\cron.log 2>&1
exit /b %ERRORLEVEL%
