# HMV-Viewer – Hilfsmittelverzeichnis (GKV-SV)

Python-Projekt mit GUI (tkinter) zum Einsehen des Hilfsmittelverzeichnisses aus der `*_HMV.xml`,
mit **10-stelliger Hilfsmittelnummer**, **Versionshistorie** und **Excel-Export**.

## Start – nur eine Python-Datei, keine Installation, keine Admin-Rechte

Die Datei **`hmv_viewer_app.py`** enthält die komplette Anwendung. Sie braucht nur Python 3.9+
(tkinter ist bei den Python-Installern für Windows/macOS dabei; Linux: `sudo apt install python3-tk`) –
**kein `pip`, keine zusätzlichen Pakete**. Python selbst lässt sich ohne Admin-Rechte installieren
(python.org → „Install for current user“ bzw. Haken bei „Use admin privileges“ entfernen).

```
python hmv_viewer_app.py          # Windows auch: Doppelklick auf die Datei oder start.bat
```

Beim ersten Start fragt das Programm nach der XML. Die Datei `20260831_HMV.xml` oder direkt die ZIP-Datei
(`..._HMV.zip`) auswählen. Die Daten werden im Ordner `data` **neben der Datei** gespeichert
(anderer Ort: Umgebungsvariable `HMV_DB`). Zum Weitergeben genügt es, `hmv_viewer_app.py` zu kopieren.

`hmv_viewer_app.py` wird aus dem Quellcode erzeugt (nicht von Hand bearbeiten):

```
python tools/build_single_file.py   # nach Änderungen an hmv_viewer/*.py
```

Alternativ direkt aus dem Quellordner: `python -m hmv_viewer` bzw. `python run_hmv.py`.

## Als .exe weitergeben (ohne Installation, ohne Admin-Rechte)

Auf einem Windows-Rechner mit Python: **`build_exe.bat` doppelklicken** → `dist\HMV-Viewer.exe`.
Diese einzelne Datei kann an Endnutzer weitergegeben werden (kein Python, keine Installation, keine Admin-Rechte):

* Die Datenbank wird im Ordner `data` **neben der .exe** angelegt (portabel, z. B. auf einem Netzlaufwerk oder
  USB-Stick). Ist der Ordner nicht beschreibbar, wird `%LOCALAPPDATA%\HMV-Viewer` verwendet.
* Beim Start entpackt sich die .exe kurz in den Temp-Ordner des Benutzers (erster Start ca. 3–10 s).
* Die .exe ist nicht signiert: Windows SmartScreen kann „Weitere Informationen → Trotzdem ausführen“ anzeigen,
  Virenscanner melden bei PyInstaller-Dateien gelegentlich Fehlalarme. Abhilfe: Code-Signing-Zertifikat
  oder Freigabe durch die IT.
* Bei einem unerwarteten Fehler erscheint ein Dialog und `data\fehler.log` wird geschrieben.

## Die 10-stellige Hilfsmittelnummer

| Stellen | Bedeutung        | Beispiel |
|---------|------------------|----------|
| 1–2     | Produktgruppe    | 01       |
| 3–4     | Anwendungsort    | 24       |
| 5–6     | Untergruppe      | 01       |
| 7       | Produktart       | 0        |
| 8–10    | Produkt          | 002      |

→ `0124010002`, angezeigt als **01.24.01.0002**. Die ersten 7 Stellen (`01.24.01.0`) sind die Produktart.
Die Suche versteht beide Schreibweisen; `01.24.01` (mit Punkten) sucht als Präfix.

## Versionshistorie

Jeder Import einer XML ist eine **Version** (V1, V2, …). Beim Import wird der neue Stand mit dem
bisherigen verglichen, jede Abweichung wird dauerhaft gespeichert:

| Typ | Bedeutung |
|-----|-----------|
| Neu | Produkt war bisher nicht im Bestand |
| Geändert | Feld(er) geändert – alter und neuer Wert je Feld werden gespeichert |
| Entfernt | Produkt fehlt in der neuen XML (bleibt als „entfernt“ im Bestand) |
| Wieder aufgenommen | zuvor entferntes Produkt ist wieder enthalten |

Dasselbe gilt für Gruppen, Anwendungsorte, Untergruppen und Produktarten (Reiter *Versionen*).
Der **erste Import ist die Ausgangsbasis** (alles „Neu“, aber nicht farbig markiert).

In der GUI:
* **Produkte**: Hierarchiebaum links, Suche (Bezeichnung, Hersteller, Nummer, optional Merkmale),
  Filter *Status* und *Änderung in Version/Typ*. Zeilen der letzten Version sind farbig markiert
  (grün = neu, gelb = geändert, blau = wieder aufgenommen, rot = entfernt).
  Unten: **Details** und **Historie** des gewählten Produkts mit Diff (alt/neu) je Feld.
* **Versionen & Änderungen**: alle Importe mit Zählern; Auswahl zeigt die Änderungen der Version,
  Doppelklick springt zum Produkt.
* **Favoriten**: Produkte per Klick in die ★-Spalte, Strg+D, Rechtsklick oder Button im Detailbereich merken;
  Gruppen/Orte/Untergruppen/Arten per Rechtsklick im Baum. Alles erscheint oben im Baum unter „★ Favoriten“
  (Strg+B). Favoriten liegen in der Datenbank und bleiben bei neuen Importen erhalten.
* **Schnellzugriff**: Filterfeld über dem Baum (Name oder Nummer, z. B. „10.50“), Gruppe/Art in den Details
  anklicken springt dorthin, ↓ aus der Suche in die Trefferliste. Alle Tastenkürzel: Button *Tastenkürzel*.

Importiert man dieselbe Datei zweimal, erkennt das Programm das (SHA-256) und fragt nach.
Enthält eine neue XML weniger als 50 % der bisherigen Produkte, wird vor dem Import gewarnt
(Schutz vor unvollständigen Dateien).

## Excel-Export

Button *Nach Excel exportieren …*: aktuelle Auswahl / alle aktiven / alle inkl. entfernter Produkte.
Blätter: **Produkte** (10-Steller als Text mit führender Null, formatierte Nummer, Hierarchie, Merkmale,
Datumsfelder als echte Daten, Version/Typ der letzten Änderung, farbig), **Änderungshistorie**
(Feld, alter Wert, neuer Wert je Version) und **Versionen**. Die .xlsx wird ohne Zusatzpakete selbst geschrieben.

## Kommandozeile

```
python -m hmv_viewer import 20260831_HMV.zip            # neue Version importieren
python -m hmv_viewer versionen
python -m hmv_viewer export out.xlsx --scope alle --suche rollator
python -m hmv_viewer export aenderungen_v3.xlsx --version 3
```

## Aufbau

```
hmv_viewer/model.py      Datenmodell, 10-Steller-Logik
hmv_viewer/parser.py     Streaming-Parser (XML oder ZIP)
hmv_viewer/importer.py   Import + Diff + Versionierung
hmv_viewer/queries.py    Filter, Suche, Historie, Hierarchie
hmv_viewer/exporter.py   Excel-Export (Inhalt)
hmv_viewer/xlsx.py       XLSX-Schreiber ohne Fremdpakete
hmv_viewer/launcher.py   gemeinsamer Start (Fehlerdialog, DPI)
tools/build_single_file.py  erzeugt hmv_viewer_app.py
hmv_viewer_app.py        fertige Einzeldatei
hmv_viewer/gui.py        tkinter-Oberfläche
tests/                   python -m unittest discover -s tests
```
