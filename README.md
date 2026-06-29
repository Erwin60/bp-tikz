# bp-tikz

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

Kompilieren (deutsches Babel benötigt; aus dem Arbeitsverzeichnis):

```bash
TEXINPUTS=.: pdflatex bp_diagrams_both_onepage_standalone.tex
TEXINPUTS=.: pdflatex bp_weekday_daytime.tex
```

## Mehrere Personen unterscheiden – `--name`

Beide Skripte stellen mit `--name` allen Ausgabedateien einen Präfix voran:

```bash
python3 generate_bp_tikz.py        --csv Gerti.csv --date-from 15.05.2026 --name Gerti
python3 generate_bp_daytime_tikz.py --csv Gerti.csv --name Gerti

python3 generate_bp_tikz.py        --csv Erwin.csv --date-from 15.05.2026 --name Erwin
python3 generate_bp_daytime_tikz.py --csv Erwin.csv --name Erwin
```

Ergebnis u. a. `Gerti_bp_diagrams.tex`, `Gerti_bp_diagrams_both_onepage_standalone.tex`, `Gerti_bp_weekday_daytime.tex` und analog `Erwin_…`.

Ein explizit gesetzter Pfad (`--out`, bei `generate_bp_tikz.py` auch `--standalone-out` / `--two-sides-out`) hat Vorrang vor dem präfigierten Standardnamen.

Im Hauptdokument die jeweils passende PDF referenzieren, z. B.:

```latex
\includegraphics{Gerti_bp_diagrams_both_onepage_standalone}
```

`generate_bp_tikz.py` gibt den erwarteten PDF-Namen am Ende seines Laufs aus.

## Wochen-Mittellinie: Mittelwert vs. Median (`--week-central`)

`--week-central mean` (Standard) zeichnet den nach Kalendertagen gewichteten Mittelwert der Tagesmittelwerte – anschlussfähig an die mittelwertbasierten klinischen Vergleichsschwellen (HBPM 135/85 mmHg, ESC-Orientierungen).

`--week-central median` zeichnet den Median der Tagesmediane – konsistent zur Interquartilsbox (gleiche Quantilsfamilie) und robuster gegen einzelne Ausreißertage. Legende und Bildunterschrift passen sich automatisch an.

## Ausreißertage im Wochendiagramm (`--week-outliers`)

Markiert zusätzlich einzelne Tage, deren Tagesmedian eine klinische Schwelle überschreitet (Standard: syst. > 135, diast. > 85 mmHg), als kleine Kreise neben dem IQR-Marker.

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
