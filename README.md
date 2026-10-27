# sdcard-sync

Gleicht einen lokalen Ordner (z. B. eine Handy-Sicherung) mit der SD-Karte
eines Android-Geräts ab – über `adb`, nicht über MTP.

Das Werkzeug vergleicht **Dateipfad und Dateigröße**, legt fehlende Ordner an
und überträgt ausschließlich die Differenz. Es ist idempotent: Ein zweiter
Lauf kopiert nur, was neu oder geändert ist.

```
=== Ziel prüfen ===
  Gerät:      Fairphone FP5
  Zielpfad:   /storage/7EDF-B83A
  Frei:       349.2 GB
  Schreiben:  42 Dateien / 3.15 GB
  Hinweis:    vorhandene Dateien mit gleicher Größe werden NICHT angefasst.

Auf dieses Ziel schreiben? [ja/nein]
```

## Warum adb statt MTP?

MTP ist auf macOS langsam und bei vielen kleinen Dateien unzuverlässig
(realistisch 2–3 MB/s, hoher Overhead pro Datei). `adb push` erreicht auf
demselben Gerät 13–37 MB/s und bricht nicht bei jeder Kleinigkeit ab.
Details: [docs/entscheidungen.md](docs/entscheidungen.md).

## Voraussetzungen

| Was | Warum |
|---|---|
| Python ≥ 3.9 | Laufzeit (nur Standardbibliothek) |
| `adb` (Android Platform Tools) | Datentransfer |
| USB-Debugging am Handy | Voraussetzung für adb |
| Kabelverbindung | – |

`adb` installieren:

```bash
brew install --cask android-platform-tools
```

USB-Debugging aktivieren (Fairphone/Android):

1. Einstellungen → Über das Telefon → 7× auf „Build-Nummer" tippen
2. Einstellungen → System → Entwickleroptionen → „USB-Debugging" einschalten
3. Kabel anstecken, USB-Modus „Dateien übertragen" wählen
4. Meldung „USB-Debugging zulassen?" bestätigen

Prüfen:

```bash
adb devices
# 208cb67d    device
```

## Installation

### Variante A: lokal im Projekt (empfohlen für Entwicklung)

```bash
cd ~/PycharmProjects/sdcard-sync
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/sdcard-sync --help
```

### Variante B: als Kommando im PATH

Im Projekt liegt ein Wrapper, der ohne Installation funktioniert:

```bash
~/PycharmProjects/sdcard-sync/bin/sdcard-sync --help
```

Für den globalen Aufruf `sdcard-sync` genügt ein Symlink:

```bash
ln -sf ~/PycharmProjects/sdcard-sync/bin/sdcard-sync ~/bin/sdcard-sync
```

## Benutzung

Die Quelle ist **Pflicht** – es gibt bewusst keinen Standardordner.

```bash
# Ziel wird automatisch als SD-Karte erkannt, danach Bestätigung
sdcard-sync --source "/Users/dsteinhoefel/Pictures/2026-10-23 SD Card Backup"

# Nur anzeigen, was übertragen würde
sdcard-sync --source "…" --dry-run

# Ziel manuell vorgeben (Bestätigung bleibt trotzdem)
sdcard-sync --source "…" --remote /storage/7EDF-B83A

# Bestätigung überspringen (nur für Automatisierung)
sdcard-sync --source "…" --yes
```

### Optionen

| Option | Bedeutung |
|---|---|
| `--source PFAD` | Quellordner (Pflicht) |
| `--remote PFAD` | Zielpfad; sonst automatische Erkennung der SD-Karte |
| `--dry-run` | Nur Diff anzeigen, nichts schreiben |
| `--yes` | Bestätigung überspringen |
| `--batch-files N` | Max. Dateien pro adb-Aufruf (Standard: 120) |
| `--batch-mb N` | Max. Paketgröße in MB (Standard: 2048) |

### Ablauf

1. Gerät prüfen (`adb devices`)
2. Ziel bestimmen (automatisch oder `--remote`)
3. SD-Karte einlesen (Dateien + Größen)
4. Lokalen Ordner scannen
5. Differenz bilden
6. Ziel, Gerät, freien Speicher und Umfang anzeigen
7. **Bestätigung abwarten**
8. Fehlende Ordner anlegen, Dateien paketweise übertragen
9. Abschließend erneut vergleichen und Restmenge melden

## Sicherheitsverhalten

- **Es wird nie gelöscht.** Dateien auf dem Ziel bleiben unangetastet, auch
  wenn sie lokal nicht existieren.
- Überschrieben wird nur, wenn eine Datei am selben Pfad eine **andere
  Größe** hat.
- Reicht der freie Speicher nicht, bricht das Programm vor dem ersten
  Schreibzugriff ab.
- Ohne ausdrückliches `ja` (oder `--yes`) wird nichts geschrieben.
- Bei Abbruch/Verbindungsverlust: einfach erneut starten, der nächste Lauf
  überträgt nur die Restmenge.

## Log

Alle Läufe werden zusätzlich protokolliert:

```
~/Library/Logs/sdcard-sync.log
```

## Projektstruktur

```
sdcard-sync/
├── bin/
│   └── sdcard-sync          # Wrapper ohne Installation
├── docs/
│   ├── entscheidungen.md    # Warum adb statt MTP
│   ├── funktionsweise.md    # Interner Ablauf, Vergleichslogik
│   └── troubleshooting.md   # Typische Fehler und Lösungen
├── src/sdcard_sync/
│   ├── __init__.py
│   ├── __main__.py          # python -m sdcard_sync
│   ├── adb.py               # Kapselung der adb-Aufrufe
│   ├── cli.py               # Argumente, Bestätigung, Ablaufsteuerung
│   └── sync.py              # Scan, Diff, Paketplanung (ohne I/O)
├── tests/
│   ├── test_cli.py
│   └── test_sync.py
├── pyproject.toml
└── README.md
```

## Tests

```bash
cd ~/PycharmProjects/sdcard-sync
.venv/bin/python -m pytest
```

Die Tests decken Scan, Diff, Paketbildung und die Bestätigungslogik ab; sie
benötigen kein angeschlossenes Gerät.

## Grenzen

- Verglichen wird **Größe + Pfad**, keine Prüfsumme. Das ist für den
  Massenabgleich schnell genug; für Integritätsprüfungen einzelner Dateien
  gibt es `adb shell md5sum`.
- Ausgeschlossen werden `.DS_Store` und `.Trashes`.
- Zwei Dateien mit gleichem Namen und gleicher Größe, aber unterschiedlichem
  Inhalt werden nicht erkannt.
- Der Zielpfad muss beschreibbar sein; `Android/data` ist je nach
  Android-Version eingeschränkt.

## Lizenz

MIT – siehe [LICENSE](LICENSE). SPDX-Kennung: `MIT`, Copyright (c) 2026 Dominic Steinhöfel.
