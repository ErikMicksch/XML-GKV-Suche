@echo off
cd /d "%~dp0"
where py >nul 2>nul && (py -3 hmv_viewer_app.py) || (python hmv_viewer_app.py)
if errorlevel 1 pause
