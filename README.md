# bp-tikz

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21216463.svg)](https://doi.org/10.5281/zenodo.21216463)

Werkzeuge, die aus einer CSV mit häuslichen Blutdruckmessungen LaTeX/PGFPlots-Diagramme erzeugen.

Zwei Generatoren erzeugen die Diagramme, zwei Hilfsskripte automatisieren den Ablauf drumherum:

### `generate_bp_tikz.py` – Tages- und Wochenverlauf

1. **Tagesdiagramm** – je Kalendertag Median und Spannweite (Min–Max), systolisch und diastolisch.
2. **Wochendiagramm** – verdichtete 7-Tage-Übersicht mit Interquartilsbox der Tagesmediane und einer zentralen Verlaufslinie (Mittelwert *oder* Median, wählbar).

Die Aggregation ist zweistufig (zuerst Tageskennwerte, dann über die Tage), damit unregelmäßige Messhäufigkeit das Ergebnis nicht verzerrt.

### `generate_bp_daytime_tikz.py` – Tageszeit × Wochentag

Ein Diagramm, das die Messungen nach Tageszeit-Blöcken (Nacht/Morgen/Tag/Abend) und Wochentag aufschlüsselt; umschaltbar zwischen Farbe und Schwarz-Weiß. Dazu eine eigene Seite **„Statistische Kennzahlen"** mit einer Blutdruck-Kennzahlentabelle und eine Seite **„Stündliche Auswertung"** mit einem 24-Stunden-Profil (Median je Stunde mit IQR-Whisker) samt Kennzahlentabelle je Stunde 0–23. Optional als letzte Seite eine Puls-Auswertung (`--pulse`).

### `bp_build.py` – Komplettlauf

Erzeugt für eine oder mehrere konfigurierte Personen nacheinander die Grafiken und kompiliert die LaTeX-Dokumente. Optional läuft davor `bp_merge.py`.

### `bp_merge.py` – Bestand und App-Export zusammenführen

Führt eine bestehende CSV und den vollständigen Export einer Blutdruck-App taggenau zu einer Datei zusammen, ohne Dubletten zu erzeugen.

## Schnellstart

```bash
python3 generate_bp_tikz.py --csv iBP_Readings.csv --date-from 15.05.2026
python3 generate_bp_daytime_tikz.py --csv iBP_Readings.csv
```

Oder in einem Zug über die Personen-Konfiguration:

```bash
python3 bp_build.py Eva
```

`--date-from` ist bei beiden Skripten optional. Ohne die Angabe werden alle Messungen ab dem frühesten Datum ausgewertet; beide Skripte verhalten sich dabei identisch. Weicht das früheste Datum auffällig weit ab (mehr als 90 Tage vor der nächsten Messung, ein typischer Datums-Tippfehler wie ein falsches Jahr), geben beide eine Warnung aus.

Kompilieren (deutsches Babel benötigt; aus dem Arbeitsverzeichnis):

```bash
TEXINPUTS=.: pdflatex bp_diagrams_both_onepage_standalone.tex
TEXINPUTS=.: pdflatex bp_weekday_daytime.tex
```

## Eingabeformat und iBP-Normalisierung

Beide Skripte akzeptieren zwei CSV-Varianten:

Ein **normales, z. B. aus Excel exportiertes** CSV mit getrennten Spalten für Datum, Uhrzeit, systolischen und diastolischen Wert (Spaltennamen werden über Aliase in Deutsch und Englisch erkannt; zusätzliche Spalten wie Gewicht oder Notizen werden ignoriert). Eine Puls-Spalte (`Pulse`/`Puls`/`HR`/…) wird von `generate_bp_daytime_tikz.py` für die optionale Puls-Auswertung (`--pulse`) mit eingelesen.

Das **Export-CSV der iBP-App**. Dieses hat eine Besonderheit: Es legt Datum und Uhrzeit als zwei komma-getrennte Felder in der Date-Spalte ab (z. B. `05.07.26, 20:23`), obwohl die Kopfzeile nur eine Date-Spalte vorsieht. Dadurch hat jede Datenzeile ein Feld mehr als die Kopfzeile, die Uhrzeit rutscht in die Note-Spalte und eine echte Notiz in ein überzähliges Feld. Ohne Behandlung führt das zu falsch zugeordneten oder verlorenen Messungen.

Beide Skripte erkennen das iBP-Format automatisch an seiner Signatur (Spalten „Mean Arterial Pressure" und „Pulse Pressure" plus die überzählige Feldzahl) und **normalisieren es vor der eigentlichen Verarbeitung** („streamlining") in ein kanonisches Format `Datum;Zeit;Systolisch;Diastolisch;Puls;note`. Anschließend durchläuft es denselben Verarbeitungsweg wie ein Excel-CSV. Nicht-iBP-Dateien werden unverändert weitergereicht. Es ist also keine manuelle Vorbereitung der iBP-Datei nötig.

## Mehrere Personen unterscheiden – `--name`

Mit `--name` schreiben beide Skripte ihre Ausgaben in ein **gleichnamiges
Unterverzeichnis neben dem Skript** und stellen den Namen zusätzlich als Präfix
voran:

```bash
python3 generate_bp_tikz.py        --csv Eva.csv --date-from 15.05.2026 --name Eva
python3 generate_bp_daytime_tikz.py --csv Eva.csv --name Eva

python3 generate_bp_tikz.py        --csv Adam.csv --date-from 15.05.2026 --name Adam
python3 generate_bp_daytime_tikz.py --csv Adam.csv --name Adam
```

Ergebnis:

```
Eva/
  Eva_bp_diagrams.tex
  Eva_bp_diagrams_both_onepage_standalone.tex
  Eva_bp_diagrams_standalone_two_sides.tex
  Eva_bp_weekday_daytime.tex
Adam/
  Adam_…
```

Das Verzeichnis wird bei Bedarf automatisch angelegt. Es liegt immer neben dem
Skript – unabhängig davon, aus welchem Verzeichnis der Aufruf erfolgt.

Ohne `--name` bleibt alles wie bisher: Ausgabe ins aktuelle Verzeichnis, ohne
Präfix. Ein explizit gesetzter Pfad (`--out`, bei `generate_bp_tikz.py` auch
`--standalone-out` / `--two-sides-out`) hat weiterhin Vorrang.

Im Hauptdokument die jeweils passende PDF referenzieren, z. B.:

```latex
\includegraphics{Eva/Eva_bp_diagrams_both_onepage_standalone}
```

`generate_bp_tikz.py` gibt den vollständigen Pfad der erzeugten Dateien am Ende
seines Laufs aus.

## Wochen-Mittellinie: Mittelwert vs. Median (`--week-central`)

`--week-central mean` (Standard) zeichnet den nach Kalendertagen gewichteten Mittelwert der Tagesmittelwerte – anschlussfähig an die mittelwertbasierten klinischen Vergleichsschwellen (HBPM 135/85 mmHg, ESC-Orientierungen).

`--week-central median` zeichnet den Median der Tagesmediane – konsistent zur Interquartilsbox (gleiche Quantilsfamilie) und robuster gegen einzelne Ausreißertage. Legende und Bildunterschrift passen sich automatisch an.

## Ausreißertage im Wochendiagramm (`--week-outliers`)

Markiert zusätzlich einzelne Tage, deren Tagesmedian eine klinische Schwelle überschreitet (Standard: syst. > 135, diast. > 85 mmHg), als kleine Kreise neben dem IQR-Marker.

## Lange Zeiträume: rotierte Wochenlabels und Trend-Diagramm (`--trend`)

Ab elf 7-Tage-Blöcken (ca. 11 Wochen) rotiert `generate_bp_tikz.py` die Datumslabels des Wochendiagramms automatisch um 45° — damit bleibt es bis zu einem vollen Jahr bei Wochenauflösung lesbar, ohne über `--block-days` stärker glätten zu müssen. Bis zehn Blöcke ändert sich nichts.

Für Halbjahres- und Jahresübersichten, bei denen das Tagesdiagramm zu dicht wird, aber Blockbildung zu viel glätten würde, erzeugt `--trend` zusätzlich ein **Langzeit-Trend-Diagramm** (Abbildung 3, im One-Page-Standalone auf eigener Seite): alle Tagesmediane als ungeglättete Punktwolke plus ein zentrierter gleitender Median als Verlaufslinie (Fensterbreite `--trend-window`, Standard 7 Tage, kalenderbasiert — Messlücken verbreitern das Fenster nicht), mit Monats-Ticks auf der x-Achse:

```bash
python3 generate_bp_tikz.py --csv iBP_Readings.csv --trend --trend-window 7
```

Die Randbehandlung der Verlaufslinie steuert `--trend-edge-policy` (Standard `symmetric`): Die Linie beginnt bzw. endet erst dort, wo das zentrierte Fenster **beidseitig** vollständig gefüllt ist — das vermeidet den Randartefakt, dass die Linie am ersten/letzten Tag durch das einseitig verkürzte Fenster neben der Punktwolke startet. `both` blendet nur echte Einzel-Randtage aus, `full` zeichnet wie früher über alle Tage; die Tagesmedian-Punkte bleiben in allen Fällen vollständig.

## Individueller Zielkorridor (`--corridor`)

Standardmäßig zeigen beide Diagramme den allgemeinen ESC-orientierten Zielkorridor (120–129 mmHg systolisch, 70–79 mmHg diastolisch). Bei besonderen Indikationen — etwa einem Aortenaneurysma, für das ein niedrigerer Druck angeraten wird — lässt sich ein eigener Korridor angeben:

```bash
python3 generate_bp_tikz.py --csv iBP.csv --date-from 15.05.2026 --corridor 110-119/70-79
```

Das Format ist `sys_lo-sys_hi/dia_lo-dia_hi`. Ohne die Option bleibt der ESC-Standardkorridor unverändert. Weicht der Korridor vom Standard ab, wird das an mehreren Stellen deutlich gekennzeichnet, damit es nicht übersehen wird: in der Legende, im erläuternden Absatz, in den Bildunterschriften und als sichtbarer Hinweis direkt in beiden Diagrammen. Mit `--corridor-label` lässt sich die Kurzbezeichnung anpassen (z. B. `--corridor-label Aneurysma`).

Hinweis: Der Korridor ist eine Orientierungshilfe für die Darstellung, keine ärztliche Zielwertfestlegung — die konkreten Zielwerte legt die behandelnde Ärztin oder der behandelnde Arzt fest.

## Statistik-Seite, Stündliche Auswertung und Puls (`--pulse`, `--pulse-low`, `--fences`, `--no-hourly`)

`generate_bp_daytime_tikz.py` hängt an das Dokument eine eigene Seite **„Statistische Kennzahlen"** an. Sie enthält immer eine Blutdruck-Kennzahlentabelle: je Zeitraum (Gesamt/Morgen/Tag/Abend/Nacht) für systolisch und diastolisch Median, Interquartilsbereich (Q1–Q3), Spanne (Min–Max), Anzahl der Messungen `n`, Anzahl Werte ab der Vergleichsschwelle (≥ 135/≥ 85 mmHg) sowie die Spalte **„im Ziel"** — die Anzahl der Messungen *innerhalb* des Zielkorridors (nicht die Anzahl der Tage); die konkrete Korridorspanne steht in einer zweiten Kopfzeile.

Danach folgt eine Seite **„Stündliche Auswertung"** mit einem **24-Stunden-Profil** (Abb. 4): je voller Tagesstunde 0–23 der Median als Marker mit IQR-Whisker (Q1–Q3), systolisch und diastolisch getrennt. Leere Stunden bleiben als Lücke sichtbar; eine dünne Linie verbindet nur unmittelbar aufeinanderfolgende Stunden (keine Interpolation über messfreie Stunden). Darunter eine Kennzahlentabelle über **alle 24 Stunden** (Median, Q1–Q3, Min–Max, `n`; Stunden ohne Messung mit „–"), messungsbezogen über den gewählten Zeitraum. Mit `--no-hourly` lässt sich diese Seite abschalten.

Mit `--pulse` kommt als **letzte Seite** eine eigene **Puls-Auswertung** hinzu: Abb. 3 zeigt das Puls-Tagesprofil (Median je Tageszeitblock mit IQR-Band), eine punktierte Linie markiert die Bradykardie-Schwelle (wählbar über `--pulse-low`, Standard 50/min), darunter eine Kennzahlenbox (Median, Q1–Q3, Min–Max, `n`, Anzahl Werte unter der Schwelle) mit Interpretationshinweis — nützlich zur Beobachtung eines möglichen Pulsabfalls unter Blutdruckmedikation. Fehlt im CSV die Pulsspalte, erscheint ein sachlicher Hinweis; das iBP-Export-CSV liefert den Puls automatisch mit.

```bash
python3 generate_bp_daytime_tikz.py --csv iBP_Readings.csv --date-from 2026-05-15 \
  --style bw --name Erwin --corridor 110-119/70-79 --corridor-label Aneurysma \
  --pulse --pulse-low 48 --fences
```

Mit `--fences` markiert in Abb. 2a/2b ein kurzer waagrechter Strich über jeder Säule die **obere Tukey-Grenze** (Q3+1,5·IQR): Werte oberhalb dieses Strichs sind die als Kreis markierten Ausreißer nach oben. (Achtung: `--pulse` mit zwei Bindestrichen; `-pulse` ist ein argparse-Fehler.)

## Komplettlauf – `bp_build.py`

Statt beide Generatoren und anschließend mehrfach `pdflatex` von Hand aufzurufen, erledigt `bp_build.py` den gesamten Ablauf für eine oder mehrere Personen. Die Aufrufe stehen in der Tabelle `PERSONEN` am Kopf des Skripts; die mitgelieferte Fassung ist eine **Vorlage mit zwei Beispielpersonen** und wird für den eigenen Gebrauch angepasst.

```bash
python3 bp_build.py Eva              # eine Person
python3 bp_build.py Eva Adam         # mehrere nacheinander
python3 bp_build.py --alle           # alle konfigurierten Personen
python3 bp_build.py --liste          # Konfiguration und Dateistand anzeigen
python3 bp_build.py Eva --keep-aux   # LaTeX-Hilfsdateien behalten
```

Das Skript wartet mit `subprocess.run()` garantiert auf das Ende jedes Schritts und prüft anschließend, ob die erwartete Datei wirklich existiert. Das ist der Grund für ein Python-Skript statt einer Befehlsliste: In a-Shell kehrt der Prompt teilweise zurück, bevor der vorherige Prozess seine Dateien fertig geschrieben hat, sodass `pdflatex` auf einer unvollständigen `.tex`-Datei startet. Nach erfolgreichem Lauf werden die LaTeX-Hilfsdateien entfernt; im Fehlerfall bleiben sie zur Diagnose liegen.

## Bestand und App-Export zusammenführen – `bp_merge.py`

Wer die Messungen bisher in einer Tabellenkalkulation gepflegt hat und ab einem Stichtag auf eine App umsteigt, steht vor einem Problem: Die App exportiert bei jedem Mal ihren **kompletten** Bestand, nicht nur die Neuzugänge. Einfaches Anhängen erzeugt deshalb bei jedem Lauf Dubletten.

`bp_merge.py` hängt nicht an, sondern baut die Datei jedes Mal neu auf:

```
CSV = Bestand (Tage VOR dem Stichtag) + App-Export (Tage AB dem Stichtag)
```

Der Stichtag ist der Tag der Umstellung und bleibt für immer derselbe. Dubletten sind dadurch konstruktiv ausgeschlossen — die beiden Quellen können sich taggenau nicht überlappen — und der Lauf ist beliebig wiederholbar: Zweimal aufgerufen entsteht dieselbe Datei.

```bash
python3 bp_merge.py --csv readings.csv --app Blutdruck_09_08_2026.csv --ab 2026-08-09
python3 bp_merge.py --csv readings.csv --app "Blutdruck_*.csv" --ab 2026-08-09 --probelauf
```

Zum Ausprobieren liegen zwei synthetische Dateien bei:

```bash
cp examples/merge_bestand_example.csv arbeit.csv
python3 bp_merge.py --csv arbeit.csv --app examples/merge_app_export_example.csv --ab 2026-08-09
```

Eigenschaften im Einzelnen:

- **Formate gemischt erlaubt.** Bestand und Export dürfen unterschiedliche Formate haben (klassischer iBP-Export oder Spalten-CSV mit Komma, Semikolon oder Tabulator). Die Spaltenzuordnung erfolgt über die Namen, die Reihenfolge ist frei; für den Puls werden unter anderem `Pul`, `Puls`, `Pulse`, `HR` und `BPM` akzeptiert.
- **Kanonische Ausgabe** `Datum;Zeit;Systolisch;Diastolisch;Puls;Notiz`. Diese Kopfzeile enthält bewusst **nicht** die Begriffe `Mean Arterial Pressure`/`Pulse Pressure`, die in beiden Generatoren die positionsbasierte iBP-Normalisierung auslösen — die Spaltenreihenfolge bleibt dadurch dauerhaft unkritisch.
- **Korrekturen kommen mit.** Wird eine Messung in der App nachträglich geändert oder gelöscht, wirkt sich das beim nächsten Lauf aus, weil der Bereich ab dem Stichtag neu aufgebaut wird. Der Bereich davor wird nie angetastet.
- **Schutzmechanismen.** Beim Schreiben in dieselbe Datei ist `--ab` Pflicht (ein automatisch abgeleiteter Stichtag würde mitwandern). Vor dem Schreiben entsteht eine Sicherungskopie `<datei>.bak-JJJJMMTT-HHMMSS`, geschrieben wird atomar über `os.replace`. Enthält der Export keine Messung ab dem Stichtag, oder fehlen darin Tage, die in der Datei bereits stehen (Hinweis auf einen veralteten Export), bricht das Skript ab, statt Messungen zu löschen. Nach dem Schreiben wird die Datei erneut eingelesen und mit dem berechneten Ergebnis verglichen.
- **Dateimuster.** Weil viele Apps das Exportdatum in den Dateinamen schreiben, akzeptiert `--app` ein Muster wie `Blutdruck_*.csv`; verwendet wird die zuletzt geänderte passende Datei, bei mehreren Treffern werden alle mit Zeitstempel genannt.

Über `--person NAME` holt sich `bp_merge.py` Datei, Export-Muster und Stichtag aus der `PERSONEN`-Tabelle von `bp_build.py`; Personen ohne `merge`-Eintrag brauchen keinen Neuaufbau. In `bp_build.py` läuft der Schritt automatisch vor den Generatoren und lässt sich mit `--kein-merge` überspringen.

## Alle Optionen

- [`docs/optionen_bp_tikz.csv`](docs/optionen_bp_tikz.csv) – vollständige Optionstabelle für `generate_bp_tikz.py`.
- [`docs/optionen_daytime.csv`](docs/optionen_daytime.csv) – Optionstabelle für `generate_bp_daytime_tikz.py`.
- [`docs/optionen_merge.csv`](docs/optionen_merge.csv) – Optionstabelle für `bp_merge.py`.
- [`docs/Manual_Merge_DE.md`](docs/Manual_Merge_DE.md) – Ablauf, Beispiele und Grenzfälle des Zusammenführens.

Alle Skripte zeigen mit `--help` zusätzlich Anwendungsbeispiele.

## Hinweis zu echten Messdaten

Im Repository liegen ausschließlich **synthetische** Beispieldateien unter `examples/`. Die `.gitignore` schließt reale Messdaten (`*_Readings*.csv`, `iBP_*.csv`, `Blutdruck_*.csv`, Sicherungskopien) und eine persönliche Konfiguration (`bp_build_local.py`) aus. Vor einem Push mit `git status` prüfen, dass keine echten Gesundheitsdaten aufgenommen werden.

## Anforderungen

- Python 3.8+ (nur Standardbibliothek, keine externen Pakete).
- LaTeX mit `pgfplots`, `tikz`, `booktabs` und `babel`/`ngerman` zum Kompilieren.

## Änderungshistorie

Siehe [`CHANGELOG.md`](CHANGELOG.md).

## Lizenz

Siehe [`LICENSE`](LICENSE).
