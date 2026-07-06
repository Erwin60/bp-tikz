# bp-tikz

[![DOI](https://zenodo.org/badge/1279557482.svg)](https://doi.org/10.5281/zenodo.21216463)

Werkzeuge, die aus einer CSV mit häuslichen Blutdruckmessungen LaTeX/PGFPlots-Diagramme erzeugen.
Werkzeuge, die aus einer CSV mit häuslichen Blutdruckmessungen LaTeX/PGFPlots-Diagramme erzeugen.

Zwei Skripte:

### `generate_bp_tikz.py` – Tages- und Wochenverlauf

1. **Tagesdiagramm** – je Kalendertag Median und Spannweite (Min–Max), systolisch und diastolisch.
2. **Wochendiagramm** – verdichtete 7-Tage-Übersicht mit Interquartilsbox der Tagesmediane und einer zentralen Verlaufslinie (Mittelwert *oder* Median, wählbar).

Die Aggregation ist zweistufig (zuerst Tageskennwerte, dann über die Tage), damit unregelmäßige Messhäufigkeit das Ergebnis nicht verzerrt.

### `generate_bp_daytime_tikz.py` – Tageszeit × Wochentag

Ein Diagramm, das die Messungen nach Tageszeit-Blöcken (Morgen/Mittag/Abend) und Wochentag aufschlüsselt; umschaltbar zwischen Farbe und Schwarz-Weiß.

## Schnellstart

```bash
python3 generate_bp_tikz.py --csv iBP_Readings.csv --date-from 15.05.2026
python3 generate_bp_daytime_tikz.py --csv iBP_Readings.csv
```

`--date-from` ist bei beiden Skripten optional. Ohne die Angabe werden alle Messungen ab dem frühesten Datum ausgewertet; beide Skripte verhalten sich dabei identisch. Weicht das früheste Datum auffällig weit ab (mehr als 90 Tage vor der nächsten Messung, ein typischer Datums-Tippfehler wie ein falsches Jahr), geben beide eine Warnung aus.

Kompilieren (deutsches Babel benötigt; aus dem Arbeitsverzeichnis):

```bash
TEXINPUTS=.: pdflatex bp_diagrams_both_onepage_standalone.tex
TEXINPUTS=.: pdflatex bp_weekday_daytime.tex
```

## Eingabeformat und iBP-Normalisierung

Beide Skripte akzeptieren zwei CSV-Varianten:

Ein **normales, z. B. aus Excel exportiertes** CSV mit getrennten Spalten für Datum, Uhrzeit, systolischen und diastolischen Wert (Spaltennamen werden über Aliase in Deutsch und Englisch erkannt; zusätzliche Spalten wie Puls, Gewicht oder Notizen werden ignoriert).

Das **Export-CSV der iBP-App**. Dieses hat eine Besonderheit: Es legt Datum und Uhrzeit als zwei komma-getrennte Felder in der Date-Spalte ab (z. B. `05.07.26, 20:23`), obwohl die Kopfzeile nur eine Date-Spalte vorsieht. Dadurch hat jede Datenzeile ein Feld mehr als die Kopfzeile, die Uhrzeit rutscht in die Note-Spalte und eine echte Notiz in ein überzähliges Feld. Ohne Behandlung führt das zu falsch zugeordneten oder verlorenen Messungen.

Beide Skripte erkennen das iBP-Format automatisch an seiner Signatur (Spalten „Mean Arterial Pressure" und „Pulse Pressure" plus die überzählige Feldzahl) und **normalisieren es vor der eigentlichen Verarbeitung** („streamlining") in ein kanonisches Format `Datum;Zeit;Systolisch;Diastolisch;Puls;note`. Anschließend durchläuft es denselben Verarbeitungsweg wie ein Excel-CSV. Nicht-iBP-Dateien werden unverändert weitergereicht. Es ist also keine manuelle Vorbereitung der iBP-Datei nötig.

## Mehrere Personen unterscheiden – `--name`

Beide Skripte stellen mit `--name` allen Ausgabedateien einen Präfix voran:

```bash
python3 generate_bp_tikz.py        --csv Eva.csv --date-from 15.05.2026 --name Eva
python3 generate_bp_daytime_tikz.py --csv Eva.csv --name Eva

python3 generate_bp_tikz.py        --csv Adam.csv --date-from 15.05.2026 --name Adam
python3 generate_bp_daytime_tikz.py --csv Adam.csv --name Adam
```

Ergebnis u. a. `Eva_bp_diagrams.tex`, `Eva_bp_diagrams_both_onepage_standalone.tex`, `Eva_bp_weekday_daytime.tex` und analog `Adam_…`.

Ein explizit gesetzter Pfad (`--out`, bei `generate_bp_tikz.py` auch `--standalone-out` / `--two-sides-out`) hat Vorrang vor dem präfigierten Standardnamen.

Im Hauptdokument die jeweils passende PDF referenzieren, z. B.:

```latex
\includegraphics{Eva_bp_diagrams_both_onepage_standalone}
```

`generate_bp_tikz.py` gibt den erwarteten PDF-Namen am Ende seines Laufs aus.

## Wochen-Mittellinie: Mittelwert vs. Median (`--week-central`)

`--week-central mean` (Standard) zeichnet den nach Kalendertagen gewichteten Mittelwert der Tagesmittelwerte – anschlussfähig an die mittelwertbasierten klinischen Vergleichsschwellen (HBPM 135/85 mmHg, ESC-Orientierungen).

`--week-central median` zeichnet den Median der Tagesmediane – konsistent zur Interquartilsbox (gleiche Quantilsfamilie) und robuster gegen einzelne Ausreißertage. Legende und Bildunterschrift passen sich automatisch an.

## Ausreißertage im Wochendiagramm (`--week-outliers`)

Markiert zusätzlich einzelne Tage, deren Tagesmedian eine klinische Schwelle überschreitet (Standard: syst. > 135, diast. > 85 mmHg), als kleine Kreise neben dem IQR-Marker.

## Individueller Zielkorridor (`--corridor`)

Standardmäßig zeigen beide Diagramme den allgemeinen ESC-orientierten Zielkorridor (120–129 mmHg systolisch, 70–79 mmHg diastolisch). Bei besonderen Indikationen — etwa einem Aortenaneurysma, für das ein niedrigerer Druck angeraten wird — lässt sich ein eigener Korridor angeben:

```bash
python3 generate_bp_tikz.py --csv iBP.csv --date-from 15.05.2026 --corridor 110-119/70-79
```

Das Format ist `sys_lo-sys_hi/dia_lo-dia_hi`. Ohne die Option bleibt der ESC-Standardkorridor unverändert. Weicht der Korridor vom Standard ab, wird das an mehreren Stellen deutlich gekennzeichnet, damit es nicht übersehen wird: in der Legende, im erläuternden Absatz, in den Bildunterschriften und als sichtbarer Hinweis direkt in beiden Diagrammen. Mit `--corridor-label` lässt sich die Kurzbezeichnung anpassen (z. B. `--corridor-label Aneurysma`).

Hinweis: Der Korridor ist eine Orientierungshilfe für die Darstellung, keine ärztliche Zielwertfestlegung — die konkreten Zielwerte legt die behandelnde Ärztin oder der behandelnde Arzt fest.

## Alle Optionen

- [`docs/optionen_bp_tikz.csv`](docs/optionen_bp_tikz.csv) – vollständige Optionstabelle für `generate_bp_tikz.py`.
- [`docs/optionen_daytime.csv`](docs/optionen_daytime.csv) – Optionstabelle für `generate_bp_daytime_tikz.py`.

Beide Skripte zeigen mit `--help` zusätzlich Anwendungsbeispiele.

## Anforderungen

- Python 3.8+ (nur Standardbibliothek, keine externen Pakete).
- LaTeX mit `pgfplots`, `tikz` und `babel`/`ngerman` zum Kompilieren.

## Änderungshistorie

Siehe [`CHANGELOG.md`](CHANGELOG.md).

## Lizenz

Siehe [`LICENSE`](LICENSE).
