@echo off
rem Schneller Start: kopiert das Programm (nur Geändertes) nach %LOCALAPPDATA%\HMV-Viewer-Programm und startet es dort.
rem Die gemeinsame Datenbank bleibt auf dem Netzlaufwerk (data\hmv.db neben dieser Datei). Keine Adminrechte nötig.
rem Eigener Zielordner: /MIR löscht dort alles, was nicht zum Programm gehört.
set "QUELLE=%~dp0HMV-Viewer"
set "ZIEL=%LOCALAPPDATA%\HMV-Viewer-Programm"
set "HMV_DB=%~dp0data\hmv.db"
robocopy "%QUELLE%" "%ZIEL%" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  rem Kopieren nicht möglich (z. B. Programm läuft noch) -> direkt vom Netzlaufwerk starten
  start "" "%QUELLE%\HMV-Viewer.exe"
) else (
  start "" "%ZIEL%\HMV-Viewer.exe"
)
