@echo off
cd /d "%~dp0"

echo ========================================================
echo Dedicated Ubuntu AI Server Scoring (Ollama qwen2.5:3b)
echo Server: http://192.168.0.133:11434
echo ========================================================

echo.
echo Checking connection to AI Server at 192.168.0.133:11434...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $tcp = New-Object System.Net.Sockets.TcpClient('192.168.0.133', 11434); $tcp.Close(); exit 0 } catch { exit 1 }"
if errorlevel 1 goto :server_offline

echo [SUCCESS] AI Server is online and reachable!
goto :ask_limit

:server_offline
echo.
echo [ERROR] Could not connect to AI Server at 192.168.0.133:11434!
echo Please check:
echo   1. The Ubuntu AI server is powered on and connected to your network.
echo   2. If a VPN like Proton VPN is active, make sure Allow LAN traffic is enabled.
echo.
pause
exit /b 1

:ask_limit
echo.
set /p LIMIT="Enter the number of jobs to score (default 200): "
if "%LIMIT%"=="" set LIMIT=200

echo.
echo ========================================================
echo Pulling latest code from GitHub...
echo ========================================================
git pull --rebase

echo.
echo ========================================================
echo Running Triage Agent via AI Server (qwen2.5:3b)...
echo ========================================================
python triage_agent.py --limit %LIMIT% --ai-server --ai-server-model qwen2.5:3b

echo.
echo ========================================================
echo Pushing updated scores to GitHub...
echo ========================================================
git add scores.json
git commit -m "chore: sync latest AI server job scores"
git push

echo.
echo ========================================================
echo Done! The dashboard is updated.
echo ========================================================
pause
