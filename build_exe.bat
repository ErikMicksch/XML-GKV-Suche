@echo off
rem ============================================================
rem  Baut dist\HMV-Viewer\HMV-Viewer.exe  (Programmordner, portabel)
rem  Voraussetzung: Python 3.9+ ist auf DIESEM Rechner installiert.
rem  Beim Endnutzer wird weder Python noch eine Installation benötigt.
rem  Ordner statt Einzeldatei: keine Entpackung bei jedem Start -> deutlich schneller, besonders vom Netzlaufwerk.
rem  Verteilen: dist\HMV-Viewer\ und dist\start_lokal.bat neben den Ordner "data" auf das Netzlaufwerk kopieren.
rem ============================================================
cd /d "%~dp0"
where py >nul 2>nul && (set PY=py -3) || (set PY=python)
%PY% -m pip install --upgrade pip
%PY% -m pip install pyinstaller PySide6 || goto :fail
%PY% -m unittest discover -s tests || goto :fail
rem Kein --uac-admin: die .exe läuft immer mit normalen Benutzerrechten (Manifest "asInvoker").
%PY% -m PyInstaller --noconfirm --clean --onedir --windowed ^
    --name HMV-Viewer ^
    --add-data "hmv_viewer\ui\qml;hmv_viewer\ui\qml" ^
    --collect-submodules hmv_viewer ^
    --exclude-module pytest --exclude-module numpy --exclude-module pandas --exclude-module tkinter ^
    run_hmv.py || goto :fail
copy /y start_lokal.bat dist\ >nul
echo.
echo Fertig: %~dp0dist\HMV-Viewer\HMV-Viewer.exe  und  %~dp0dist\start_lokal.bat
pause
exit /b 0
:fail
echo.
echo FEHLER beim Bauen - siehe Meldungen oben.
pause
exit /b 1
