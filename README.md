# HMV-Viewer – Hilfsmittelverzeichnis (GKV-SV)

Python-Projekt mit moderner Oberfläche (Qt Quick/QML mit PySide6, Farbwelt angelehnt an die AOK) zum Einsehen des Hilfsmittelverzeichnisses aus der `*_HMV.xml`,
mit **10-stelliger Hilfsmittelnummer**, **Versionshistorie** und **Excel-Export**.

## Start – eine Python-Datei, keine Admin-Rechte

Die Datei **`hmv_viewer_app.py`** enthält die komplette Anwendung. Sie braucht Python 3.9+ und einmalig
das Paket **PySide6** für die Oberfläche (beides ohne Admin-Rechte installierbar; Python: python.org →
„Install for current user“):

```
python -m pip install --user PySide6
python hmv_viewer_app.py          # Windows auch: Doppelklick auf die Datei oder start.bat
```

Die Kommandozeile (siehe unten) funktioniert auch ohne PySide6. Endnutzer ohne Python bekommen die .exe.

Beim ersten Start fragt das Programm nach der XML. Die Datei `20260831_HMV.xml` oder direkt die ZIP-Datei
(`..._HMV.zip`) auswählen. Die Daten werden im Ordner `data` **neben der Datei** gespeichert
(anderer Ort: Umgebungsvariable `HMV_DB`). Zum Weitergeben genügt es, `hmv_viewer_app.py` zu kopieren.

`hmv_viewer_app.py` wird aus dem Quellcode erzeugt (nicht von Hand bearbeiten):

```
python tools/build_single_file.py   # nach Änderungen an hmv_viewer/ (auch ui/ und ui/qml/)
```

Alternativ direkt aus dem Quellordner: `python -m hmv_viewer` bzw. `python run_hmv.py`.
Die bisherige Oberfläche (Qt Widgets) startet weiterhin mit `--klassisch`, z. B. `python hmv_viewer_app.py --klassisch`.
In der Einzeldatei werden die QML-Dateien beim ersten Start je Version nach `%LOCALAPPDATA%\HMV-Viewer\qml_<version>`
entpackt (QML braucht echte Dateien; keine Adminrechte nötig).

## Speicherorte: Datenbank und Sicherungen (hmv_pfade.json)

Wo die gemeinsame Datenbank und der Sicherungsordner liegen, steht in **einer** Datei `hmv_pfade.json` neben dem
Programm (neben `hmv_viewer_app.py` bzw. im Programmordner `HMV-Viewer\`). Zieht etwas um, genügt es, diese Datei
auszutauschen. Vorlage: `hmv_pfade.beispiel.json` (umbenennen in `hmv_pfade.json`):

```
{
  "datenbank": "\\\\server\\abteilung\\HMV\\data\\hmv.db",
  "sicherungen": "\\\\server\\abteilung\\HMV\\data\\sicherungen"
}
```

* Backslashes in JSON **doppelt** schreiben (oder `/` verwenden). Relative Angaben gelten ab dem Ordner der Datei,
  `%VARIABLEN%` werden ersetzt (z. B. `"%USERPROFILE%\\HMV\\hmv.db"`). Fehlt `sicherungen`: Ordner `sicherungen`
  neben der Datenbank. Ist die Datei fehlerhaft, bricht das Programm mit einem klaren Hinweis ab (statt still eine
  falsche Datenbank zu öffnen).
* **Im Programm wählen:** *Einstellungen → Datenbank und Sicherungen*. „Datenbank wählen …“ nimmt eine vorhandene
  HMV-Datenbank oder legt eine neue an – auf Wunsch als **Kopie der aktuellen** (zum Arbeiten auf dem lokalen PC).
  Die neue Datenbank gilt nach einem Neustart (Knopf „Jetzt neu starten“), der Sicherungsordner sofort.
  Ohne Schreibrecht auf die Pfad-Datei landet ihr Inhalt in der Zwischenablage (an die IT weitergeben).
* Reihenfolge: Umgebungsvariable `HMV_DB` → `hmv_pfade.json` (anderer Ort: Umgebungsvariable `HMV_PFADE`) →
  `data\hmv.db` neben dem Programm → `%LOCALAPPDATA%\HMV-Viewer`.

### Empfohlener Betrieb: Programm auf dem Client, Datenbank auf dem Netzlaufwerk

Das Programm läuft am schnellsten **lokal auf jedem PC** (Programmordner lokal bzw. über `start_lokal.bat`), nur die
Datenbank liegt auf dem Netzlaufwerk (`hmv_pfade.json`). Damit dabei möglichst wenig über das Netz gelesen wird:

* **Kleine Indexe statt ganzer Tabelle:** Produktanzahl, Zähler im Produktgruppen-Baum und Herstellerliste kommen aus
  dem Index `ix_produkt_aktiv`, die Gruppennamen aus `ix_stamm_name`. Die Produktliste wird in zwei Schritten geladen
  (erst die passenden Nummern aus dem Index, dann nur die angezeigten 500 Produkte).
* Gemessen mit der echten Datenbank (66.024 Produkte, 119 MB), kalter Cache: Start **8,6 MB statt ~114 MB** gelesen;
  Liste/Suche/Gruppe/Hersteller je **1–7 MB statt ~70 MB**; Fensterwechsel (Abgleich mit Kollegen) liest nur wenige KB.
* Die Indexe legt der erste Start mit Schreibrecht einmalig an (Sekundenbereich); 7 gleichzeitige Clients über einen
  UNC-Pfad (6 lesend, 1 schreibend) liefen dabei ohne Fehler, Integritätsprüfung ok.
* Weiterhin über das Netz: der tägliche Sicherungslauf (kopiert die ganze Datenbank, im Hintergrund, einmal pro Tag)
  und Importe.

## Als .exe weitergeben (ohne Installation, ohne Admin-Rechte)

Auf einem Windows-Rechner mit Python: **`build_exe.bat` doppelklicken** → Programmordner `dist\HMV-Viewer\`
(mit `HMV-Viewer.exe`, enthält Qt) und `dist\start_lokal.bat`. Weitergabe an Endnutzer ohne Python, ohne Installation,
ohne Admin-Rechte:

* Die Datenbank wird im Ordner `data` **neben der .exe** angelegt (portabel, z. B. auf einem Netzlaufwerk oder
  USB-Stick). Ist der Ordner nicht beschreibbar und gibt es dort noch keine Datenbank, wird `%LOCALAPPDATA%\HMV-Viewer` verwendet.
* Ordner statt Einzeldatei: beim Start wird nichts entpackt. **`start_lokal.bat`** (neben den Ordnern `HMV-Viewer` und
  `data`) kopiert nur Geändertes nach `%LOCALAPPDATA%\HMV-Viewer-Programm` und startet von dort – schneller Start,
  die Datenbank bleibt auf dem Netzlaufwerk. Die Speicherorte kommen dabei aus `HMV-Viewer\hmv_pfade.json` auf dem
  Netzlaufwerk (fehlt sie: `data\hmv.db` neben `start_lokal.bat`).
* **Start-Protokoll:** `%TEMP%\HMV-Viewer_<Benutzer>.log` (Start, Datenbank, Grafik, Qt-Meldungen). Kann ein PC die
  Grafik nicht starten (z. B. Remote-Desktop, virtuelle Maschine), stellt das Programm einmalig auf einfache
  Software-Darstellung um (ohne Schatten) und startet neu; erzwingen mit Umgebungsvariable `HMV_GRAFIK=software`.
* `build_exe.bat` baut ohne UPX-Packer und entfernt danach ungenutzte Qt-Teile (`tools/trim_exe.py`: Web-Engine,
  3D, PDF, Diagramme …) – ca. 140 statt 410 MB. Geprüft: startet und zeigt die Oberfläche; Windows Defender
  (Signaturen vom 23.10.2026) meldet im ganzen Programmordner nichts.
* Die .exe ist nicht signiert: Windows SmartScreen kann „Weitere Informationen → Trotzdem ausführen“ anzeigen,
  Virenscanner melden bei PyInstaller-Dateien gelegentlich Fehlalarme. Abhilfe: Code-Signing-Zertifikat
  oder Freigabe durch die IT.
* Bei einem unerwarteten Fehler erscheint ein Dialog und `data\fehler_<Windows-Benutzer>.log` wird geschrieben
  (ohne Schreibrecht dort: im Temp-Ordner des Benutzers).

### Mehrere Benutzer gleichzeitig über ein Netzlaufwerk

Den Ordner `HMV-Viewer` und `start_lokal.bat` einmal auf das Netzlaufwerk legen (z. B. `\\server\abteilung\HMV\`);
alle starten **`start_lokal.bat`** (oder direkt `HMV-Viewer\HMV-Viewer.exe`).

* **Keine Adminrechte nötig – nie.** Die .exe läuft mit normalen Benutzerrechten (kein `--uac-admin`, Manifest
  „asInvoker“). Geschrieben wird nur in den `data`-Ordner neben der .exe, in den eigenen Temp-Ordner,
  in `HKCU\Software\HMV-Viewer` (Einstellungen je Windows-Benutzer) und in den selbst gewählten Favoriten-Ordner.
* **Eine gemeinsame Datenbank** `data\hmv.db` neben der .exe für alle (Verzeichnis, Versionen, gemeinsame Listen und
  Notizen, Benutzer). Sie läuft im Rollback-Journal-Modus (nicht WAL), der für Netzlaufwerke geeignet ist; ältere
  Datenbanken werden beim Start automatisch umgestellt. Getestet: 8 gleichzeitige Prozesse (Import + Schreiben + Lesen)
  über einen UNC-Pfad ohne Fehler, Integritätsprüfung ok.
* **Jeder hat seinen eigenen Benutzer** (Nachname) – einmalig beim ersten Start eingegeben und in der eigenen
  Favoriten-Datei gespeichert; oben rechts wird er nur angezeigt (kein Wechsel).
  Persönliche Favoriten, private Listen, eigene Notizen und Kategorien liegen in der eigenen Favoriten-Datei.
* Schreibt jemand gerade (z. B. ein Import), warten die anderen kurz; bei längerer Sperre erscheint ein Hinweis statt
  eines Fehlers. Neue Importe anderer werden beim Zurückkehren ins Fenster automatisch übernommen.
* Wer nur **Leserechte** auf den `data`-Ordner hat, kann alles ansehen und exportieren; die Statusleiste zeigt
  „NUR LESEN“, Änderungen an gemeinsamen Daten werden mit einer klaren Meldung abgelehnt.
* Grenzen: SQLite über Netzlaufwerk ist für eine Abteilung (einige bis ca. 20 gleichzeitige Benutzer) gedacht, nicht für
  Hunderte. Während eines Imports (je nach Größe einige Sekunden bis Minuten) sind Schreibzugriffe anderer kurz blockiert.

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
| Umgruppiert | Produkt hat eine neue 10-stellige Nummer (andere Gruppe/Untergruppe/Art bzw. anderer 7-Steller): die alte Nummer fällt weg, eine neue mit gleicher Bezeichnung und gleichem Hersteller kommt hinzu. Die Historie zeigt alte und neue Nummer. Platzhalter „Nicht besetzt“ zählen nie. Ältere Versionen werden beim ersten Start einmalig nachträglich ausgewertet. |

Dasselbe gilt für Gruppen, Anwendungsorte, Untergruppen und Produktarten (Reiter *Versionen*).
Der **erste Import ist die Ausgangsbasis** (alles „Neu“, aber nicht farbig markiert).

In der GUI:
* **Produkte** (drei Spalten): links Produktgruppen mit Filterfeld (Name oder Nummer, z. B. „10.50“),
  Mitte Trefferliste, rechts Details, Historie (Diff alt/neu je Feld) und **Meine Notiz**.
  Suche oben (Bezeichnung, Hersteller, Nummer, Notizen und – standardmäßig an, abschaltbar – Merkmale), Filter *Status*, *Änderung in Version/Typ*
  und **Hersteller** (Teiltext genügt). Zeilen der letzten Version sind farbig markiert
  (grün = neu, gelb = geändert, blau = wieder aufgenommen, rot = entfernt). Tooltip auf der Bezeichnung zeigt die Merkmale.
* **Versionen**: alle Importe mit Zählern; Auswahl zeigt die Änderungen der Version, Doppelklick springt zum Produkt.
* **Favoriten**: Produkte per Klick in die ★-Spalte, Strg+D, Rechtsklick oder Button im Detailbereich merken –
  auch mehrere markierte Zeilen auf einmal; ganze Gruppen per Rechtsklick im Baum (als aufklappbarer Baum).
  Alles erscheint oben im Baum unter „★ Meine Favoriten“ (Strg+B), dazu eigene private Listen (siehe unten).
* **Arbeiten mit Produktlisten**: persönliche **Notiz** je Produkt (Spalte „Meine Notiz“, Doppelklick auf eine Zeile),
  Klick auf Hersteller/Gruppe/Art in den Details filtert danach, **Zeilen als Tabelle kopieren** (Strg+A, Strg+C → in
  Excel/E-Mail einfügen), Excel-Export „Meine Favoriten“ mit Notiz-Spalte. Nach einem Import werden
  **betroffene Favoriten sofort angezeigt**.
* **Notizen und Kommentare**: „Meine Notiz“ (nur für Sie) und **Kommentare** je Produkt (Reiter „Kommentare“ im
  Detailbereich, in der Datenbank, für alle sichtbar, jeweils mit Name und Zeitpunkt; eigene Kommentare lassen sich
  löschen). Beide erscheinen als Spalte, die große Suche findet beide. Das Feld **„Merkmale/Notizen“** sucht nur in
  Merkmalen, Notizen und Kommentaren – z. B. eine Zeile aus den Details wie „Energiequelle: Batterie vom Typ 10“.
  Gemeinsame Notizen aus v2.2 werden beim Start automatisch zu Kommentaren.
* **Farbkategorien**: eigene Kategorien mit Farbe (Vorgaben: Erledigt, In Prüfung, Kritisch; verwalten über
  *Mehr ▾ → Farbkategorien*). Zuweisen per Rechtsklick → *Farbkategorie* (auch für viele Zeilen) oder im Detailbereich;
  in der Liste zeigt ein kleines Farbfeld die Kategorie, Filter *Kategorie* zeigt nur diese Produkte, sortierbar.
  Die Kategorien selbst liegen in der Favoriten-Datei; im Excel-Export als Spalte „Kategorie (persönlich)“.
  Das Einfärben ist für Kollegen unter „Änderungen anderer“ sichtbar.
* **Design**: *Mehr ▾ → Design* – **AOK Modern** (Standard), **Classic** (AOK-Grün), **Hell** (neutral, weiß) oder
  **Dunkel**; Schriftgröße und Zeilenhöhe unter *Mehr ▾ → Ansicht*; alles wird je Benutzer gemerkt.
* Alle Tastenkürzel: *Mehr ▾ → Tastenkürzel*. Fenstergröße und Spaltenbreiten werden je Benutzer gemerkt.

### Neu in v3.0 – Oberfläche mit Qt Quick/QML

* **Neue Oberfläche** mit allen bisherigen Funktionen (Code: `hmv_viewer/ui/`, je Bereich ein Modul; Aussehen:
  `hmv_viewer/ui/qml/`, je Seite/Dialog eine Datei). Daten, Suche, Import/Export und Favoriten-Datei unverändert.
* **Lesbarkeit:** alle Farbpaare geprüft (Text ≥ 4,5 : 1, Fokusrahmen ≥ 3 : 1 – automatischer Test); gelber Hilfe-Knopf
  mit dunkler Schrift; deutlicher Fokusrahmen bei Tab-Bedienung; Symbol-Knöpfe mit Tooltip und Namen für Bildschirmleser.
* **Einfacher:** „Mehr Filter“ (Status, Version, Änderungsart, Hersteller, Farbkategorie, „Nicht besetzt“ – mit Anzahl
  aktiver Filter); Kopf aufgeräumt (*Daten ▾*, *Menü*; Import nur mit Schreibrecht); leere Listen mit Knopf für den
  nächsten Schritt; Einrichtung beim ersten Start als eigene Seite; alle Einstellungen in einem Dialog; Farbfelder.
* **Schmale Bildschirme:** unter 1700 px Produktgruppen als Leiste von links, unter 1500 px Kopf-Knöpfe nur mit Symbol,
  unter 1300 px Navigation nur mit Symbol; Mindestbreite 1024 px.
* **Modern:** eigene SVG-Symbole, weiche Schatten, Übergänge, neue Farbwelt **AOK Modern Dunkel**.
* **Schneller Start vom Netzlaufwerk:** Programmordner statt Einzeldatei + `start_lokal.bat` (siehe oben).
* **Tests:** `tests/test_qml.py` – Kontrast aller Farbwelten, kompletter Ablauf (jede QML-Warnung = Fehler) und
  Bildvergleich gegen `tests/baseline_qml` (neu erzeugen: Ordner löschen).
* Grenzen: Breiten von Baum | Liste | Details werden nicht gespeichert; Ziehen auf Listen nur von Hand geprüft.

### Neu in v2.6

* **Neue Standard-Oberfläche „AOK Modern“** – auch ohne PC-Erfahrung bedienbar: große Schrift (12 pt), große
  Schaltflächen, Häkchen und Bildlaufleisten, AOK-Grün mit Verlauf im Kopf, abgerundete Karten mit weichem Schatten.
* **Navigation in Klartext**: Startseite · Produkte suchen · Versionen · Änderungen anderer.
* **Hilfe zu jeder Seite**: gelber Knopf *Hilfe* oben, *Hilfe zu dieser Seite* links unten oder **F1** – erklärt
  Schritt für Schritt in einfachen Worten, was man auf der aktuellen Seite tun kann.
* *Schnellzugriff* statt „Strg+K“, Suchfeld mit Beispiel („Hier suchen, z. B. Rollator“).
* Beim ersten Start von v2.6 wird einmalig auf „AOK Modern“, 12 pt und Zeilenhöhe „Groß“ umgestellt; die alte
  Darstellung gibt es weiter unter *Mehr ▾ → Design → Classic* und *Mehr ▾ → Ansicht*. Mindestbreite bei 12 pt
  ca. 1480 Pixel (passt auch auf 1920er-Bildschirme mit 125 % Skalierung).
* Das Diagramm auf der Startseite passt Beschriftung und Abstände an die Schriftgröße an.

### Neu in v2.5

* **Schnelle Suche mit Volltext-Index** (10–90 ms statt bis zu 1 s bei 66.024 Produkten). **Ein Suchfeld** oben mit
  Schaltern *Suchen in: Bezeichnung / Hersteller · Merkmale · Notizen & Kommentare* (je Benutzer gemerkt).
  Wortanfang genügt (`batt` → Batterie), Zahlen nur als ganzes Wort (`10` ≠ `100`), `"Typ 10"` = genaue Wortfolge,
  `-netzabhängig` = ausschließen, `01.24.01` = Nummernbereich. Vereinheitlicht: `PR 70` = `PR70`, `4,7 kg` = `4.7kg`,
  Silbentrennung und doppelte Leerzeichen im Originaltext werden ignoriert. Teilwörter in der Wortmitte (`ollator`)
  findet die Suche nicht.
* **Merkmal-Zeile anklicken** (Details): übernimmt „Eigenschaft: Wert“ als genaue Phrase ins Suchfeld.
* **Spalte „Fundstelle (Merkmale)“** mit der passenden Merkmal-Zeile; die Details springen zu den markierten Treffern.
* **Spalten frei einstellen**: alle Spalten (auch „Bezeichnung“) mit der Maus breiter/schmaler ziehen, Doppelklick auf
  den Rand = passende Breite, Reihenfolge per Ziehen; **„Spalten …“** (Button über der Liste, *Mehr ▾ → Ansicht* oder
  Rechtsklick auf den Tabellenkopf) blendet Spalten ein/aus. Alles wird je Benutzer gemerkt.
* Der Index wird beim ersten Start einmalig aufgebaut (einige Sekunden) und bei jedem Import aktualisiert; die
  Datenbank wird dadurch ca. 27 MB größer.

### Neu in v2.4

* **Umgruppiert** als eigene Änderungsart (Filter, Farbe, Spalte unter *Versionen*, Excel, Diagramm).
* **„Geändert – Merkmale“** in der Auswahl der Änderungstypen: nur Produkte, bei denen sich die Merkmale geändert haben
  (reine Bezeichnungs-/Datumsänderungen erscheinen dort nicht).
* **„Nicht besetzt“ ausblenden**: Schalter in der Filterleiste, je Benutzer gemerkt.
* **Markierung der Suchtreffer** in den Merkmalen der Details (Feld „Merkmale/Notizen“ und – bei Merkmal-Suche –
  die große Suche). Farbe: *Mehr ▾ → Ansicht → Markierungsfarbe für Suchtreffer*, standardmäßig gelb, je PC gespeichert.

### Neu in v2.3

* **Startseite** (*Start*, Strg+0): Kacheln (Produkte, letzter Import, Favoriten, Listen), Diagramm der Änderungen je
  Version, zuletzt angesehene Produkte, zuletzt geänderte gemeinsame Listen und Schnellaktionen.
* **Schnellzugriff Strg+K**: ein Feld für Produkte, Nummern, Gruppen, Listen und alle Funktionen.
* **Zuletzt angesehen**: die letzten 20 geöffneten Produkte als Eintrag oben im Baum (je Windows-Benutzer).
* **Gespeicherte Suchen**: aktuelle Filterkombination unter einem Namen merken (Button über der Liste).
* **Nummernliste einfügen** (Strg+Umschalt+V): viele Nummern aus Excel/E-Mail einfügen; zeigt aktive, entfernte und
  unbekannte Nummern; Treffer anzeigen oder direkt zu einer Liste hinzufügen.
* **Vergleich**: Rechtsklick auf ein Produkt → *Vergleichen mit …* → im Popup ein oder mehrere Produkte suchen und
  wählen (ohne Suche werden Produkte derselben Produktart vorgeschlagen); oder 2–4 Produkte markieren → *vergleichen*.
  Das Vergleichsfenster ist eine Tabelle: links die Eigenschaften (Abschnitte „Allgemein“ und „Merkmale“), je Produkt
  eine Spalte, Unterschiede farbig; „Nur Unterschiede anzeigen“, „Weiteres Produkt hinzufügen“, „Als Tabelle kopieren“.
* **Was ist neu?** beim Start: neue Importe (mit betroffenen Favoriten), Änderungen an abonnierten gemeinsamen
  Listen, neue Kommentare anderer seit dem letzten Öffnen.
* **Ziehen und Ablegen**: markierte Produkte mit der Maus auf „Meine Favoriten“ oder eine Liste im Baum ziehen.
* **Spalten wählen und verschieben**: Rechtsklick auf den Tabellenkopf; Reihenfolge per Ziehen; wird gemerkt.
* **Endlos scrollen** statt Seiten: weitere Treffer werden beim Scrollen nachgeladen.
* **Rückgängig** (Strg+Z bzw. Button im Hinweis): für Favoriten-, Listen- und Kategorie-Änderungen.
* **Kartenansicht** (Umschalter über der Liste) mit Status-Chips, Kategorie, Favorit und letztem Kommentar.
* **Linien-Icons**, **Hinweis-Einblendungen** unten rechts, sanfte Übergänge, Leer-Zustände mit Grafik und klarer Aktion.
* **Detailbereich** mit Titel, Chips und aufklappbaren Abschnitten (Einordnung, Merkmale, Listen).
* **Ansicht**: *Mehr ▾ → Ansicht* – Zeilenhöhe (Kompakt/Normal/Groß) und Schriftgröße (9–12 pt), je Benutzer.
* **Verlauf je gemeinsamer Liste** (Rechtsklick → *Verlauf anzeigen*): wer hat wann was hinzugefügt/entfernt/umbenannt.
* **Abonnieren** gemeinsamer Listen (Rechtsklick): Glocke im Baum, Hinweis bei Änderungen anderer.
* **Automatische Tagessicherung**: beim ersten Start des Tages still nach `data\sicherungen\auto_JJJJMMTT.db`
  (die letzten 14 bleiben); entfällt bei Nur-Lese-Zugriff.
* **Info & Support** (*Mehr ▾*): Version, Pfade, Benutzer, Journal-Modus – „Fehlerbericht kopieren“ für den Support.
* **Änderungen anderer** (linke Leiste unter *Versionen*, Strg+3): alles, was andere Benutzer kommentiert, farblich
  markiert oder an gemeinsamen Listen geändert haben – mit Zeitpunkt, Name, Produkt und Inhalt; filterbar nach
  Zeitraum, Art und Benutzer; Doppelklick öffnet Produkt bzw. Liste. Eigene Änderungen sind ausgeblendet (Schalter
  „Eigene Änderungen auch anzeigen“); ist die Ansicht leer, erklärt ein Hinweis den Grund. Der Button zeigt die Zahl neuer Einträge seit dem
  letzten Öffnen. Hinweis: Die Farbkategorien bleiben Ihre eigenen, das **Einfärben** eines Produkts wird aber in der
  gemeinsamen Datenbank protokolliert und ist für Kollegen hier sichtbar.

### Listen: Meine Favoriten, private und gemeinsame Listen

Im Baum links gibt es zwei Bereiche, in beiden lassen sich **Listen in Listen** (Unterlisten, beliebig tief) anlegen:

* **★ Meine Favoriten** – nur für Sie (Favoriten-Datei). Rechtsklick → *Neue private Liste*, auf einer Liste →
  *Unterliste anlegen / Umbenennen / Löschen*.
* **Gemeinsame Listen** – in der Datenbank, für alle Benutzer sichtbar (mit Windows-Benutzername und Zeitpunkt).
  Gleiche Bedienung; Löschen mit Rückfrage, gilt für alle. Änderungen anderer erscheinen beim Zurückkehren ins Fenster / F5.

**Hinzufügen** per Rechtsklick → *Zu Liste hinzufügen …*: Der Dialog zeigt alle Listen als Baum (auch „Neue Liste hier“).
Bei einer **Produktgruppe** (Rechtsklick links im Baum auf Gruppe, Ort, Untergruppe oder Art) fragt der Dialog:

* **Ganze Produktgruppe** – die Gruppe erscheint in der Liste als **aufklappbarer Baum**; neue Produkte der Gruppe
  gehören bei späteren Importen automatisch dazu.
* **Einzelne Produkte** – alle aktiven Produkte werden einzeln eingetragen (fester Stand; ab 500 mit Rückfrage).

*☆ Ganze Gruppe zu Meine Favoriten* (Rechtsklick) merkt eine Gruppe direkt als Baum. In der ★-Spalte steht ★ für direkt
gemerkte Produkte und ☆ für Produkte, die über eine ganze Gruppe Favorit sind. Eine Liste zeigt beim Anklicken ihre
eigenen Produkte inkl. der Produkte ihrer Gruppen (nicht die der Unterlisten). Entfernen: Produkte markieren →
Rechtsklick → *aus „Liste“ entfernen*; Gruppen-Einträge per Rechtsklick auf die Gruppe im Baum. Die Details eines
Produkts zeigen, in welchen gemeinsamen und eigenen Listen es steht. Excel-Export einer Liste: Liste auswählen →
*Excel-Export* → „Aktuelle Auswahl“.

### Benutzer

Beim ersten Start gibt jeder seinen **Nachnamen** ein (kein Passwort). Der Name wird in der **eigenen
Favoriten-Datei** (`HMV_Favoriten.json`, Feld `benutzer`) gespeichert und oben rechts nur angezeigt – ein Wechsel im
Programm ist nicht vorgesehen. Er erscheint bei gemeinsamen Listen und Kommentaren als „zuletzt geändert von … am …“
und unter „Änderungen anderer“. Wer den Speicherort der Favoriten wechselt, übernimmt den Namen der dortigen Datei
(oder trägt seinen bisherigen ein). Es ist keine Zugriffskontrolle – der Name lässt sich in der Datei ändern.

### Datenbank sichern und im Notfall wiederherstellen

*Mehr ▾ → Datenbank sichern (Backup)* schreibt eine konsistente Kopie der gemeinsamen Datenbank (auch während andere
arbeiten). *Mehr ▾ → Datenbank aus Sicherung wiederherstellen* **überschreibt ALLE Informationen der gemeinsamen
Datenbank für alle Benutzer und ist nur für den Notfall gedacht**: deutliche Warnung, Prüfung der Datei, Bestätigung durch
Eintippen von `ÜBERSCHREIBEN`; der vorherige Stand wird automatisch unter `data\sicherungen\` gesichert.
Persönliche Favoriten, private Listen, Notizen und Kategorien liegen in der eigenen Favoriten-Datei und sind weder
in der Sicherung enthalten noch von der Wiederherstellung betroffen.

### Persönliche Favoriten & Notizen

Jeder Benutzer hat eine eigene Datei **`HMV_Favoriten.json`** in einem selbst gewählten Ordner (Abfrage beim ersten
Start, Vorschlag `Dokumente\HMV-Viewer`; ändern über *Mehr ▾ → Speicherort*). Der gewählte Ordner wird je
Windows-Benutzer gemerkt (Registry `HKCU\Software\HMV-Viewer`). Ein Ordner auf dem Netzlaufwerk bleibt beim
PC-Wechsel erhalten. Die Datenbank mit dem Verzeichnis bleibt gemeinsam. Die Datei wird atomar geschrieben;
eine beschädigte Datei wird als `HMV_Favoriten.defekt_<Zeit>.json` gesichert statt überschrieben.
Favoriten aus v1.x (gemeinsam in der Datenbank) werden beim ersten Start einmalig übernommen.

Importiert man dieselbe Datei zweimal, erkennt das Programm das (SHA-256) und fragt nach.
Enthält eine neue XML weniger als 50 % der bisherigen Produkte, wird vor dem Import gewarnt
(Schutz vor unvollständigen Dateien).

## Excel-Export

Button *Excel-Export*: aktuelle Auswahl / meine Favoriten / alle aktiven / alle inkl. entfernter Produkte,
optional mit den Spalten „Favorit“ und „Notiz (persönlich)“. Nach dem Export kann die Datei direkt geöffnet werden.
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
hmv_viewer/launcher.py   gemeinsamer Start (Fehlerdialog)
hmv_viewer/favorites.py  persönliche Favoriten & Notizen (JSON-Datei je Benutzer)
tools/build_single_file.py  erzeugt hmv_viewer_app.py
hmv_viewer_app.py        fertige Einzeldatei
hmv_viewer/ui/            Oberfläche (Qt Quick/QML): core, tree, products, detail, lists, pages, dialogs,
                         maint, theme, icons, app – QML-Dateien in hmv_viewer/ui/qml/
hmv_viewer/gui.py        bisherige Oberfläche (Qt Widgets, --klassisch) und gemeinsame Hilfsfunktionen
hmv_viewer/ui_extras.py  Icons, Startseite, Karten, Schnellzugriff, Dialoge
hmv_viewer/merkmale.py   Suche: Volltext-Index, Vereinheitlichung, Suchsyntax, Merkmal-Zerlegung
tests/                   python -m unittest discover -s tests
```
