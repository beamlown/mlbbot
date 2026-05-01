@echo off
REM One-shot installer for the 3 daily mlb_model scheduled tasks.
REM Double-click or run from Command Prompt. Re-runnable (uses /F to overwrite).

echo Installing mlb-elo-daily (06:00 daily)...
schtasks /Create /SC DAILY /TN mlb-elo-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_update_elo_daily.bat" /ST 06:00 /F
if errorlevel 1 goto :err

echo Installing mlb-pitcher-quality-daily (08:00 daily)...
schtasks /Create /SC DAILY /TN mlb-pitcher-quality-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_pitcher_quality_daily.bat" /ST 08:00 /F
if errorlevel 1 goto :err

echo Installing mlb-batter-quality-daily (08:30 daily)...
schtasks /Create /SC DAILY /TN mlb-batter-quality-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_batter_quality_daily.bat" /ST 08:30 /F
if errorlevel 1 goto :err

echo Installing mlb-reliever-quality-daily (08:15 daily)...
schtasks /Create /SC DAILY /TN mlb-reliever-quality-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_reliever_quality_daily.bat" /ST 08:15 /F
if errorlevel 1 goto :err

echo Installing mlb-bullpen-quality-daily (08:45 daily)...
schtasks /Create /SC DAILY /TN mlb-bullpen-quality-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_bullpen_quality_daily.bat" /ST 08:45 /F
if errorlevel 1 goto :err

echo Installing mlb-weather-daily (09:15 daily)...
schtasks /Create /SC DAILY /TN mlb-weather-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_refresh_weather_daily.bat" /ST 09:15 /F
if errorlevel 1 goto :err

echo Installing mlb-sharp-odds-daily (09:00 daily)...
schtasks /Create /SC DAILY /TN mlb-sharp-odds-daily /TR "C:\Users\johnny\Desktop\mlb_model\scripts\cron\run_update_sharp_odds_daily.bat" /ST 09:00 /F
if errorlevel 1 goto :err

echo.
echo All 7 tasks installed. Verify with: schtasks /Query /TN mlb-elo-daily
echo Logs go to: C:\Users\johnny\Desktop\mlb_model\logs\cron.log
exit /b 0

:err
echo.
echo ERROR installing tasks. Run as Administrator if you see access denied.
exit /b 1
