@echo off
rem ============================================================
rem  Baut dist\HMV-Viewer.exe  (eine einzelne, portable Datei)
rem  Voraussetzung: Python 3.9+ ist auf DIESEM Rechner installiert.
rem  Beim Endnutzer wird weder Python noch eine Installation benötigt.
rem ============================================================
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -m pip install --upgrade pip
%PY% -m pip install pyinstaller PySide6 || goto :fail
%PY% -m unittest discover -s tests || goto :fail
rem Kein --uac-admin: die .exe läuft immer mit normalen Benutzerrechten (Manifest "asInvoker").
rem Beim Start entpackt sie sich in den Temp-Ordner des jeweiligen Benutzers -> mehrere Benutzer gleichzeitig möglich.
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
    --name HMV-Viewer ^
    --exclude-module pytest --exclude-module numpy --exclude-module pandas --exclude-module tkinter ^
    run_hmv.py || goto :fail
echo.
echo Fertig: %~dp0dist\HMV-Viewer.exe
pause
exit /b 0
:fail
echo.
echo FEHLER beim Bauen - siehe Meldungen oben.
pause
exit /b 1
