@echo off
REM Daily batter quality refresh — registered as Windows scheduled task `mlb-batter-quality-daily`
cd /d "C:\Users\johnny\Desktop\mlb_model"
"C:\Users\johnny\AppData\Local\Python\pythoncore-3.14-64\python.exe" scripts\refresh_batter_quality_daily.py >> logs\cron.log 2>&1
exit /b %ERRORLEVEL%
