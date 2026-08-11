# `bp_merge.py` — Bestand und App-Export zusammenführen

## Wozu

Die Messungen wurden bisher in einer Tabellenkalkulation gepflegt und von dort
als CSV exportiert. Ab einem Stichtag werden sie stattdessen in einer App
erfasst. Die App exportiert bei jedem Mal ihren **kompletten** Bestand, nicht
nur die Neuzugänge — einfaches Anhängen erzeugt deshalb bei jedem Lauf
Dubletten.

## Das Prinzip: Neuaufbau statt Anhängen

```
CSV = Bestand (Tage VOR dem Stichtag) + App-Export (Tage AB dem Stichtag)
```

Der Stichtag ist der Tag der Umstellung und ändert sich **nie**. Daraus folgen
drei Eigenschaften:

1. **Keine Dubletten.** Die beiden Quellen können sich taggenau nicht
   überlappen.
2. **Wiederholbar.** Zweimal aufgerufen entsteht dieselbe Datei; das Ergebnis
   hängt nur von den beiden Eingangsdateien ab, nicht davon, wie oft oder wann
   das Skript gelaufen ist.
3. **Korrekturen kommen mit.** Wird eine Messung in der App nachträglich
   geändert oder gelöscht, wirkt sich das beim nächsten Lauf aus, weil der
   Bereich ab dem Stichtag komplett neu aufgebaut wird. Der Bereich davor wird
   nie angetastet.

Zu Punkt 3 gehört die Kehrseite: In der App gelöschte Messungen verschwinden
auch aus der CSV. Wer das nicht will, arbeitet mit `--aus` auf einer zweiten
Datei.

## Aufruf

```bash
# Regelfall: in dieselbe Datei zurueckschreiben
python3 bp_merge.py --csv readings.csv --app Blutdruck_09_08_2026.csv --ab 2026-08-09

# Dateiname der App enthaelt das Exportdatum -> Muster
python3 bp_merge.py --csv readings.csv --app "Blutdruck_*.csv" --ab 2026-08-09

# vorher ansehen, ohne zu schreiben
python3 bp_merge.py --csv readings.csv --app "Blutdruck_*.csv" --ab 2026-08-09 --probelauf

# Ergebnis in eine andere Datei, Quelle unangetastet
python3 bp_merge.py --csv bestand.csv --app export.csv --ab 2026-08-09 --aus neu.csv

# ueber die Personen-Konfiguration von bp_build.py
python3 bp_merge.py --person Adam
```

In `bp_build.py` läuft der Schritt automatisch vor den Generatoren, sobald die
Person einen `merge`-Eintrag hat:

```python
"Adam": {
    "csv": "Adam_readings.csv",
    "merge": {"app": "Blutdruck_*.csv", "ab": "2026-08-09"},
    ...
}
```

Mit `python3 bp_build.py Adam --kein-merge` lässt sich der Schritt überspringen,
etwa um die PDFs neu zu bauen, ohne einen neuen Export zur Hand zu haben.

## Zum Ausprobieren

```bash
cp examples/merge_bestand_example.csv arbeit.csv
python3 bp_merge.py --csv arbeit.csv --app examples/merge_app_export_example.csv --ab 2026-08-09
```

Der Bestand (24 Messungen, 01.–08.08.) ist ein Semikolon-CSV mit deutschen
Spaltennamen, der Export (9 Messungen, 09.–11.08.) ein Komma-CSV mit
englischen Kürzeln und absteigender Sortierung. Ergebnis: 33 Messungen,
chronologisch, keine Dubletten.

## Eingangsformate

Erkannt werden

* der klassische iBP-Export (`Systolic,Diastolic,Pulse,Weight,Mean Arterial
  Pressure,Pulse Pressure,Date,Note` mit Datum und Uhrzeit als zwei
  komma-getrennte Felder) und
* jedes normale Spalten-CSV mit Komma, Semikolon oder Tabulator.

Bestand und Export dürfen unterschiedliche Formate haben. Die Zuordnung
erfolgt über die Spaltennamen, die Reihenfolge ist frei. Für den Puls werden
`Pul`, `Puls`, `Pulse`, `HR`, `BPM`, `Herzfrequenz` und `HF` akzeptiert.

Eine **Uhrzeit ist Pflicht** — ohne sie wäre die Tageszeit-Auswertung nicht
möglich. Zeilen ohne lesbare Uhrzeit werden mit Zeilennummer gemeldet und
übersprungen.

## Ausgabeformat

Geschrieben wird immer

```
Datum;Zeit;Systolisch;Diastolisch;Puls;Notiz
```

Diese Kopfzeile enthält bewusst **nicht** die Begriffe `Mean Arterial Pressure`
und `Pulse Pressure`. Genau diese beiden Namen schalten in
`generate_bp_tikz.py` und `generate_bp_daytime_tikz.py` die positionsbasierte
iBP-Normalisierung ein, bei der die Spaltenreihenfolge fest verdrahtet ist.
Mit der kanonischen Kopfzeile arbeiten beide Generatoren rein namensbasiert.

Spalten, für die es im Ausgabeformat keine Entsprechung gibt (etwa `Gewicht`
oder eine Blutdruck-Klassifikation der App), entfallen. Notizen bleiben
erhalten.

## Schutzmechanismen

| Situation | Verhalten |
|---|---|
| `--ab` fehlt beim Schreiben in dieselbe Datei | Abbruch mit Begründung |
| Export enthält keine Messung ab dem Stichtag | Abbruch, statt die App-Tage zu löschen |
| Tage stehen bereits in der Datei, fehlen aber im Export | Abbruch — Hinweis auf einen veralteten Export |
| Bestand enthält Messungen am oder nach dem Stichtag | Warnung; für diese Tage gilt allein der Export |
| gleicher Zeitstempel, abweichende Werte | Warnung (mögliche nachträgliche Korrektur) |
| exakte Dublette innerhalb einer Quelldatei | wird entfernt und gemeldet |

Vor dem Schreiben entsteht eine Sicherungskopie `<datei>.bak-JJJJMMTT-HHMMSS`.
Geschrieben wird atomar über eine temporäre Datei und `os.replace`, damit die
Datei bei einem Abbruch nicht halb beschrieben zurückbleibt. Danach wird sie
erneut eingelesen und mit dem berechneten Ergebnis verglichen.

## Reihenfolge in der Datei

Das Ergebnis wird chronologisch sortiert geschrieben. Für die Auswertung wäre
das nicht nötig — beide Generatoren sortieren die eingelesenen Messungen selbst
bzw. gruppieren sie tageweise, die Dateireihenfolge geht in kein Ergebnis ein —
aber es macht die Datei lesbar. Viele Apps exportieren absteigend; das wird
dabei mit korrigiert.

## Alle Optionen

Siehe [`optionen_merge.csv`](optionen_merge.csv).
