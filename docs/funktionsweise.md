# Funktionsweise

## Überblick

```
┌──────────────┐    adb shell find/stat     ┌────────────────┐
│  lokaler     │ ─────────────────────────▶ │  Android-Gerät │
│  Ordner      │                            │  /storage/…    │
│  (Quelle)    │ ◀───────────────────────── │  (SD-Karte)    │
└──────────────┘        adb push            └────────────────┘
```

## 1. Gerät und Ziel bestimmen

`adb devices` muss genau ein Gerät im Zustand `device` liefern. Der Zielpfad
wird – sofern nicht per `--remote` gesetzt – aus `ls /storage` abgeleitet:
Alles außer `emulated` und `self` ist die echte externe SD-Karte, also
typischerweise `/storage/XXXX-XXXX` mit der Volume-UUID.

Der interne Speicher (`/storage/emulated/0`) ist bewusst nicht der Standard,
weil das Werkzeug für die SD-Karte gedacht ist.

## 2. Zielbestand einlesen

Auf dem Gerät läuft ein einzelner `find`-Aufruf:

```sh
cd /storage/XXXX-XXXX && find . -type f -exec stat -c '%s %n' {} +
```

Das liefert pro Zeile Größe und relativen Pfad. `-exec … +` bündelt viele
Dateien pro `stat`-Prozess, was den Aufruf auch bei zehntausenden Dateien
schnell hält (Sekunden statt Minuten).

Ergebnis: `dict[relativer Pfad] → Größe in Bytes`.

## 3. Quellbestand einlesen

`os.walk` über den Quellordner. Ausgeschlossen werden:

- `.DS_Store` (macOS-Metadaten)
- `.Trashes` (Papierkorb-Reste)
- symbolische Links (würden sonst doppelt oder ins Leere zeigen)
- nicht lesbare Dateien (z. B. wegen Berechtigungen)

Ergebnis: Liste von `FileEntry(rel, size, path)`.

## 4. Differenzbildung

Eine Datei gilt als zu übertragen, wenn

```
remote.get(rel) != local.size
```

also entweder gar nicht vorhanden ist oder eine abweichende Größe hat.
Reine Zeitstempel werden nicht verglichen: Android setzt `dateAdded` beim
Schreiben ohnehin neu, und MTP/adb erhalten `mtime` nicht zuverlässig.

## 5. Paketplanung

`adb push` hat pro Aufruf Overhead. Deshalb werden Dateien nach Zielordner
gruppiert und dann in Pakete zerlegt:

- maximal 120 Dateien pro Aufruf
- maximal 2 GB pro Aufruf

Beide Grenzen sind über `--batch-files` und `--batch-mb` justierbar. Große
Einzeldateien bilden jeweils ein eigenes Paket.

## 6. Übertragung

Fehlende Ordner werden vorab mit `mkdir -p` angelegt – gebündelt, 60 Ordner
pro adb-Aufruf.

Anschließend wird jedes Paket mit `adb push datei1 datei2 … ziel/`
übertragen. Bei Fehlern: bis zu drei Versuche, dazwischen `adb wait-for-device`.
Ein fehlgeschlagenes Paket bricht den Lauf nicht ab; es wird am Ende gezählt
und ist beim nächsten Start automatisch wieder Teil der Differenz.

## 7. Verifikation

Nach dem Upload wird der Zielbestand erneut eingelesen und erneut verglichen.
Ausgegeben wird die Restmenge:

```
Noch offen: 0 Dateien / 0.00 GB
```

Damit ist der Lauf nachweislich vollständig – ohne dass eine teure
Prüfsummenbildung über 100+ GB nötig wäre.

## Zustandslosigkeit

Es gibt keine Datenbank und keine Merkliste. Der Zustand ist immer der
tatsächliche Dateibestand auf beiden Seiten. Das macht das Werkzeug robust
gegenüber Abbrüchen, Stromausfall oder Kabelziehen: Ein Neustart berechnet
die Differenz einfach neu.

## Grenzen der Erkennung

Der Vergleich über Pfad + Größe ist ein Kompromiss aus Geschwindigkeit und
Sicherheit. Nicht erkannt werden:

- gleicher Pfad, gleiche Größe, anderer Inhalt
- Umbenennungen (werden als „neu" übertragen, das Original bleibt liegen)

Für eine echte Integritätsprüfung einzelner Dateien:

```bash
md5 -q lokal/datei.jpg
adb shell md5sum /storage/XXXX-XXXX/pfad/datei.jpg
```
