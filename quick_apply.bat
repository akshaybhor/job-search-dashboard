@echo off
cd /d "%~dp0\auto_apply"
title Quick Apply - Multi-ATS One-Click Runner

echo ========================================================
echo        ⚡ QUICK APPLY - ONE-CLICK RUNNER
echo ========================================================
echo.

python -u "quick_apply.py" %*

echo.
echo ========================================================
echo   Finished! Press any key to close this window.
echo ========================================================
pause >nul
