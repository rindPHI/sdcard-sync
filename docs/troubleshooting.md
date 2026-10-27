# Troubleshooting

## „Kein Android-Gerät gefunden"

```
adb devices
```

| Ausgabe | Ursache | Lösung |
|---|---|---|
| leer | Kabel, Modus oder Debugging | Kabel prüfen, USB-Modus „Dateien übertragen", USB-Debugging an |
| `unauthorized` | Bestätigung am Handy fehlt | Handy entsperren, „USB-Debugging zulassen?" bestätigen |
| `offline` | Verbindung hängt | Kabel ab/anstecken, `adb kill-server && adb start-server` |

Häufig hilft auch: anderen USB-Port bzw. direkt am Mac statt am Hub testen.

## „Keine echte SD-Karte gefunden"

`adb shell ls /storage` zeigt nur `emulated` und `self`. Dann ist die
SD-Karte nicht eingelegt oder nicht eingebunden. Prüfen:

```bash
adb shell sm list-volumes
adb shell ls /storage
```

Ziel alternativ explizit angeben:

```bash
sdcard-sync --source "…" --remote /storage/XXXX-XXXX
```

## „Permission denied" beim Schreiben

- Zielpfad prüfen (Tippfehler, interner statt externer Speicher).
- `Android/data` ist ab Android 11 teils gesperrt. Betroffene Ordner werden
  als fehlgeschlagen gemeldet, der Rest läuft weiter.
- SD-Karte ggf. am Handy neu einbinden (Einstellungen → Speicher).

## Übertragung bricht ab

Einfach erneut starten:

```bash
sdcard-sync --source "…"
```

Es wird nur die Differenz übertragen. Bereits kopierte Dateien werden
übersprungen.

## Sehr langsam

- USB-Hub oder Monitor-Dock vermeiden, direkt am Mac anstecken.
- Große Dateien laufen mit ~35 MB/s, viele kleine Dateien deutlich langsamer
  (Protokoll-Overhead pro Datei). Das ist normal.
- `--batch-files` erhöhen (z. B. 250) reduziert die Anzahl der adb-Aufrufe.

## „Keine interaktive Eingabe möglich"

Das Skript läuft ohne Terminal (z. B. aus einem Cronjob). Entweder
interaktiv starten oder bewusst bestätigen:

```bash
sdcard-sync --source "…" --yes
```

## Nach dem Lauf: „Noch offen: N Dateien"

- Fehlgeschlagene Pakete werden erneut versucht, wenn man das Programm
  nochmals startet.
- Bei `Android/data` kann es dauerhaft an Berechtigungen scheitern.
- Log prüfen: `~/Library/Logs/sdcard-sync.log`

## Log ansehen

```bash
tail -n 50 ~/Library/Logs/sdcard-sync.log
```
