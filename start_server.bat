@echo off
title Rail-BDMS Server
echo ===================================================
echo Starting Rail-BDMS Application (Indian Railways DSS)
echo ===================================================
echo.
py -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
pause
