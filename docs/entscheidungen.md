# Entscheidungen

## adb statt MTP

**Ausgangslage:** Ein Fairphone 5 mit 512-GB-SD-Karte sollte mit einer
135-GB-Sicherung (16.857 Dateien) abgeglichen werden.

**Versuch 1 – MTP (OpenMTP/libmtp):**

- MTP-Session auf macOS ließ sich nur mit Mühe öffnen; `ptpcamerad` hielt das
  Gerät, ein abgebrochener Transfer hinterließ eine hängende Session
  (`LIBUSB_ERROR_TIMEOUT`), die erst durch Ab- und Anstecken wieder frei wurde.
- Nach dem Start: 2,3 MB/s Durchsatz, geschätzte 15 Stunden.
- Pro Datei fällt spürbarer Protokoll-Overhead an; kleine Dateien dominieren
  die Laufzeit.

**Versuch 2 – adb:**

- Einrichtung: USB-Debugging aktivieren, einmal bestätigen.
- Durchsatz: 36,8 MB/s bei großen Dateien, 13,5 MB/s im Schnitt über den
  gesamten Bestand (inkl. zehntausender kleiner Dateien).
- Laufzeit: 2 h 48 min für 135,6 GB.
- Robust: Abbrüche sind unkritisch, weil der Zustand bei jedem Lauf neu aus
  dem Dateibestand berechnet wird.

**Entscheidung:** adb. Der einmalige Einrichtungsaufwand amortisiert sich
beim ersten Lauf um ein Vielfaches.

## Kein Standard-Quellordner

Die Sicherung war eine ad-hoc-Kopie. Ein fest verdrahteter Pfad wäre schnell
veraltet und würde bei falscher Annahme womöglich den falschen Ordner
abgleichen. Deshalb ist `--source` Pflicht.

## Bestätigung vor dem Schreiben

Automatische Zielerkennung ist bequem, aber ein falsch erkannter Einhängepunkt
könnte Daten an unerwarteter Stelle ablegen. Vor dem ersten Schreibzugriff
werden deshalb Gerät, Zielpfad, freier Speicher und Umfang angezeigt und eine
ausdrückliche Bestätigung verlangt. `--yes` existiert nur für bewusste
Automatisierung.

## Vergleich über Pfad + Größe

Alternative wäre ein vollständiger Hash-Vergleich gewesen. Bei 135 GB und
einem USB-2-High-Speed-Gerät hätte das den Lauf verdoppelt bis verdreifacht,
ohne praktischen Mehrwert für eine Wiederherstellung. Größe + Pfad erkennt
die real vorkommenden Fälle (fehlende Dateien, abgebrochene Transfers,
unterschiedliche Versionen). Einzelne Stichproben lassen sich jederzeit per
`md5sum` prüfen.

## Nichts löschen

Ein Spiegel-Abgleich mit Löschungen wäre riskant: Ein unvollständiger
Quellordner hätte auf der SD-Karte Daten entfernt. Das Werkzeug ergänzt und
überschreibt nur; Dateien, die nur auf der SD-Karte existieren, bleiben
unangetastet.

## Paketierung statt Einzeldatei-Aufrufe

`adb push` hat pro Prozessstart Overhead. 120 Dateien bzw. 2 GB pro Aufruf
sind ein Kompromiss: deutlich weniger Aufrufe, aber Pakete bleiben klein
genug, dass ein Fehler nur einen überschaubaren Teil betrifft und schnell
wiederholt werden kann.
