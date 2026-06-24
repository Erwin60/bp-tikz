# Benutzerhandbuch — `generate_bp_tikz.py`

Erzeugt aus einer CSV mit häuslichen Blutdruckmessungen zwei abgestimmte
LaTeX/PGFPlots-Diagramme (tagesweise und in Blöcken) sowie optionale
Statistik-CSVs. Dieses Handbuch beschreibt die Bedienung; die methodische
Begründung der Berechnungsvarianten steht ausführlich im begleitenden
IEEE-Paper.

---

## 1. Überblick in einem Satz

Roh-CSV rein → zwei Diagramme (Tagesverlauf + 7-Tage-Übersicht) plus
Statistik-CSVs raus, vollständig über Kommandozeilenparameter steuerbar und
deterministisch reproduzierbar.

---

## 2. Voraussetzungen

- **Python 3** (nur Standardbibliothek, keine Zusatzpakete nötig).
- Für das Einbinden der Ausgabe ins eigene LaTeX-Dokument:
  ```latex
  \usepackage{tikz}
  \usepackage{pgfplots}
  \pgfplotsset{compat=1.18}
  ```

---

## 3. Eingabeformat

Die **Eingabe-CSV** (`--csv`) braucht mindestens diese Spalten (Aliasnamen
deutsch/englisch werden erkannt, Groß/Kleinschreibung egal):

| Inhalt | erkannte Namen (Auswahl) | Pflicht |
|---|---|---|
| Datum | `date`, `datum`, `messdatum` | ja |
| Systolisch | `systolic`, `systolisch`, `sys`, `sbp` | ja |
| Diastolisch | `diastolic`, `diastolisch`, `dia`, `dbp` | ja |
| Puls | `pulse`, `puls`, `hr` | nein |
| Notiz/Zeit | `note`, `notiz`, `bemerkung`, `time`, `zeit` | nein |

**Datumsformate:** `YYYY-MM-DD`, `DD.MM.YYYY`, `DD.MM.YY`, `DD/MM/YYYY`,
`DD/MM/YY`.

**Zahlen:** englisch *und* europäisch (`130`, `130.5`, `130,5`, `1.234,56`,
`1,234.56`); Zusätze wie `mmHg` werden toleriert.

**Trennzeichen:** automatisch erkannt (Komma, Semikolon, Tab) oder per
`--delimiter` erzwungen.

> **Wichtig:** Die zuvor erzeugten `bp_daily_stats.csv` / `bp_weekly_stats.csv`
> sind **Ausgaben** des Skripts, keine gültige Eingabe für `--csv`. Als Eingabe
> dienen die **Einzelmessungen** (eine Zeile pro Messung).

Beispiel einer gültigen Eingabe-CSV:

```csv
Date,Time,Systolic,Diastolic,Pulse,Note
2026-05-15,07:30,124,68,66,
2026-05-15,21:10,130,70,63,
2026-05-16,07:20,119,62,70,
2026-05-16,21:00,158,77,66,nach Sport
```

---

## 4. Schnellstart

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15
```

Erzeugt:

- `bp_diagrams.tex` — einbindbares Fragment mit beiden Diagrammen
- `bp_diagrams_both_onepage_standalone.tex` — beide Diagramme auf einer A4-Seite
- `bp_diagrams_standalone_two_sides.tex` — je Diagramm eine beschnittene Seite

Einbinden ins eigene Dokument:

```latex
\input{bp_diagrams.tex}
```

---

## 5. Was die beiden Diagramme zeigen

**Diagramm 1 — Tagesverlauf.** Pro Tag ein Punkt (Tagesmedian) plus vertikaler
Balken (Tagesspannweite Min–Max). Tage mit nur einer Messung haben keine
sichtbare Spannweite. Unten eine Zusammenfassungszeile mit gewichtetem
Mittelwert, Median der Tagesmediane und Anzahl Tage unter 135/85 mmHg.

**Diagramm 2 — Blockübersicht (Standard 7 Tage).** Linie = Lagemaß des Blocks
(Mittelwert oder Median, siehe unten), Fehlerbalken = Interquartilsabstand
(IQR) der Tagesmediane. Optional einzelne Ausreißertage als Punkte.

**Beide** enthalten die ESC-Korridore (120–129 / 70–79 mmHg, hellgrau) und die
HBPM-Vergleichslinien (135 / 85 mmHg, punktiert). Diese sind Vergleichs- und
Orientierungslinien, **keine** individuellen Zielwerte.

---

## 6. Die wichtigen Stellschrauben

### 6.1 Zentrallinie: Mittelwert oder Median

```bash
--week-central mean     # Standard: nach Tagen gewichteter Mittelwert
--week-central median   # Median der Tagesmediane (robuster, IQR-konsistent)
```

- `mean` — anschlussfähig an mittelwertbasierte HBPM/ESC-Schwellen.
- `median` — robuster gegen einzelne Ausreißertage, konsistent zur IQR-Box.

Beide sind legitim; die Wahl hängt vom Zweck ab. Da Lage und Streuung getrennt
gezeigt werden, geht keine Information verloren.

### 6.2 Ausreißertage markieren

```bash
--week-outliers                       # an, Standardschwellen 135/85
--week-outlier-sys-hi 130             # eigene obere systolische Schwelle
--week-outlier-dia-hi 80              # eigene obere diastolische Schwelle
--week-outlier-sys-lo 110             # optionale untere Schwelle
--week-outlier-dia-lo 65              # optionale untere Schwelle
```

Markiert einzelne Tage als Punkte, **entfernt sie aber nicht** aus Mittelwert,
Median und IQR.

### 6.3 Blocklänge

```bash
--block-days 7     # Standard
--block-days 14    # z. B. 14-Tage-Blöcke
```

### 6.4 Tagesdiagramm-Optionen

```bash
--show-daily-n               # kleine n=-Labels (Messungen pro Tag)
--daily-n-y 150              # feste Höhe der n=-Labels
--no-daily-summary-label     # Zusammenfassungszeile ausblenden
```

### 6.5 Statistik-CSVs exportieren

```bash
--daily-stats bp_daily_stats.csv
--weekly-stats bp_weekly_stats.csv
```

### 6.6 Ausgabesteuerung

```bash
--out bp_fragment.tex
--standalone-out bp_onepage.tex
--two-sides-out bp_two_sides.tex
--two-sides-width-cm 14
--standalone-title "Blutdruckverlauf 05–06/2026"
--no-standalone        # einseitiges Standalone nicht schreiben
--no-two-sides         # zweiseitiges Standalone nicht schreiben
```

---

## 7. Typische Rezepte

**Datumsfenster + Statistik-Export:**
```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 15.05.2026 --date-to 20.06.2026 \
  --out bp_fragment.tex \
  --daily-stats bp_daily_stats.csv \
  --weekly-stats bp_weekly_stats.csv
```

**Median-Linie mit Ausreißern:**
```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv --date-from 2026-05-15 \
  --week-central median --week-outliers
```

**Nur Fragment, keine Standalone-Dateien:**
```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv --date-from 2026-05-15 \
  --out bp_fragment.tex --no-standalone --no-two-sides
```

**DE-Export mit Semikolon:**
```bash
python3 generate_bp_tikz.py \
  --csv bp_export_de.csv --date-from 2026-05-15 \
  --delimiter semicolon
```

**Voll bestückt (wie für die Dokument-Anhänge):**
```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15 --date-to 2026-06-20 \
  --week-central median --week-outliers \
  --week-outlier-sys-hi 135 --week-outlier-dia-hi 85 \
  --show-daily-n \
  --out bp_fragment.tex \
  --standalone-out bp_onepage.tex \
  --two-sides-out bp_two_sides.tex --two-sides-width-cm 16 \
  --daily-stats bp_daily_stats.csv \
  --weekly-stats bp_weekly_stats.csv
```

---

## 8. Ausgabe-CSVs verstehen

### Tagesstatistik (`--daily-stats`)
`date, day_index, n, sys_min, sys_max, sys_median, sys_mean,
dia_min, dia_max, dia_median, dia_mean, pulse_min…mean,
pulse_pressure_min…mean`

Eine Zeile pro Kalendertag; `n` = Anzahl Messungen, `day_index` zählt ab
`--date-from` (0-basiert).

### Blockstatistik (`--weekly-stats`)
`block, start_date, end_date, x_mid, n_days, n_readings, label,
sys_mean_of_daily_means, sys_q1_daily_medians, sys_q3_daily_medians,
dia_mean_of_daily_means, dia_q1_daily_medians, dia_q3_daily_medians,
pulse_pressure_*`

`*_mean_of_daily_means` = gewichteter Mittelwert; `*_q1/q3_daily_medians` =
Quartile der Tagesmediane (IQR-Grenzen).

---

## 9. Reproduzierbarkeit prüfen

Gleiche CSV + gleiches Datumsfenster + gleiche Parameter → identische Ausgabe.
Schnelltest: Werte der Zusammenfassungszeile (Mittelwert, Median, „<135/85:
x/y Tage") gegen die Tagesstatistik-CSV abgleichen.

---

## 10. Fehlerbehebung

| Symptom | Ursache / Lösung |
|---|---|
| `Missing required column for 'date'` | Datums-/Wertespalte nicht erkannt → Spaltennamen prüfen oder umbenennen. |
| `Row N: systolic/diastolic value missing or invalid` | Leere/ungültige Zelle in Zeile N → Wert ergänzen oder Zeile korrigieren. |
| `--date-to must be >= --date-from` | Datumsfenster vertauscht. |
| `No valid readings in the requested date range` | Fenster enthält keine Daten → `--date-from`/`--date-to` prüfen. |
| Falsch interpretierte Dezimalzahlen | `--delimiter` explizit setzen; Komma vs. Punkt prüfen. |
| Seite des einseitigen Standalone nicht gefüllt | aktuelle Skriptversion verwenden (Höhe wird zur Laufzeit aus der Seitenhöhe berechnet). |
| Diagramme erscheinen nicht im Hauptdokument | `tikz`, `pgfplots` und `\pgfplotsset{compat=1.18}` in der Präambel ergänzen. |

---

## 11. Grenzen

Dies ist ein Aufbereitungs- und Darstellungswerkzeug, **kein** diagnostisches
System. Die eingezeichneten Schwellen sind Vergleichs- und Orientierungslinien;
individuelle Zielwerte legt die behandelnde Ärztin oder der behandelnde Arzt
fest. Kurze Blöcke mit wenigen Tagen sind weniger belastbar (die
Bildunterschrift weist darauf hin). Die Ausreißermarkierung ist eine
schwellenbasierte Hervorhebung, keine statistische Ausreißerklassifikation.

---

## 12. Parameter-Kurzreferenz

| Parameter | Default | Zweck |
|---|---|---|
| `--csv` | — (Pflicht) | Eingabe-CSV (Date, Systolic, Diastolic; opt. Time/Pulse/Note) |
| `--date-from` | — (Pflicht) | erstes Datum |
| `--date-to` | alle ab `date-from` | letztes Datum |
| `--out` | `bp_diagrams.tex` | LaTeX-Fragment |
| `--daily-stats` | aus | Tagesstatistik-CSV |
| `--weekly-stats` | aus | Blockstatistik-CSV |
| `--block-days` | `7` | Blocklänge |
| `--delimiter` | `auto` | `auto`/`comma`/`semicolon`/`tab` |
| `--standalone-out` | `bp_diagrams_both_onepage_standalone.tex` | Einseiten-Standalone |
| `--no-standalone` | aus | Einseiten-Standalone aus |
| `--standalone-title` | `Blutdruckdiagramme` | Titel der Standalone-Seite |
| `--show-daily-n` | aus | `n=`-Labels |
| `--daily-n-y` | automatisch | feste Höhe der `n=`-Labels |
| `--week-outliers` | aus | Ausreißertage markieren |
| `--week-outlier-sys-hi` | `135` | obere syst. Schwelle |
| `--week-outlier-dia-hi` | `85` | obere diast. Schwelle |
| `--week-outlier-sys-lo` | aus | untere syst. Schwelle |
| `--week-outlier-dia-lo` | aus | untere diast. Schwelle |
| `--week-central` | `mean` | `mean`/`median` |
| `--no-daily-summary-label` | aus | Zusammenfassungszeile aus |
| `--two-sides-out` | `bp_diagrams_standalone_two_sides.tex` | Zweiseiten-Standalone |
| `--no-two-sides` | aus | Zweiseiten-Standalone aus |
| `--two-sides-width-cm` | `16.0` | Achsenbreite (cm) zweiseitig |

---

## 13. Getestete Umgebung und Software-Versionen

Dieses Werkzeug wurde **ausschließlich** in den folgenden Umgebungen entwickelt
und getestet. Es ist reines Python plus eine übliche LaTeX-Toolchain und sollte
auch anderswo laufen, anderes wurde aber nicht verifiziert.

| Komponente | Version / Hinweis |
|---|---|
| Python | 3.9+ (entwickelt mit CPython 3.12; nur Standardbibliothek) |
| LaTeX-Engine | `pdflatex` (TeX Live; `tikz` + `pgfplots`, `compat=1.18`) |
| Dokumentklasse der Papers | `IEEEtran.cls` V1.8b |

**Getestete Plattformen (nur diese):**

- **macOS** — Desktop-Python 3 und Desktop-TeX-Live/MacTeX.
- **iPad / iPhone** mit **a-Shell** (<https://holzschu.github.io/a-Shell_iOS/>) —
  lokales iOS-Terminal, das Python 3 und TeX Live (mit TikZ und LuaTeX) bündelt;
  Skript und LaTeX-Übersetzung laufen lokal auf dem Gerät.
- **Texifier** (vormals TeXpad, <https://www.texifier.com/>) auf macOS und
  iPadOS/iOS — zum Bearbeiten und Setzen der LaTeX-Dokumente.

**Wichtiger Plattform-Hinweis.** Der integrierte Live-Setzer von Texifier
(*TexpadTeX*) läuft in einer Sandbox und erlaubt **keinen** Shell-Escape
(`\write18`). Das Python-Skript `generate_bp_tikz.py` wird daher in **a-Shell**
(iOS) bzw. einer normalen Shell (macOS) ausgeführt; Texifier dient anschließend
zum Öffnen und Setzen der erzeugten `.tex`-Dateien. Auf macOS kann Texifier
zusätzlich auf eine vollständige MacTeX-Distribution verwiesen werden, falls ein
Paket im Bundle fehlt.

Windows und Linux sollten mit jeder üblichen Python-3- und TeX-Live-Installation
funktionieren, wurden aber **nicht** getestet.

---

## 14. Hinweis zur KI-Nutzung

Bei der Erstellung der Dokumentation, beim Code-Review und bei der Aufbereitung
des anonymisierten Beispiels wurde generative KI (Claude, Anthropic)
unterstützend eingesetzt. Konzept, Algorithmus und Daten stammen vom Autor, der
alle Ergebnisse geprüft und verantwortet; die KI ist kein Autor. Die
vollständige Offenlegung steht in `AI_USAGE.md`; die IEEE-Paper enthalten die
entsprechende Offenlegung im Acknowledgment-Abschnitt gemäß IEEE-Vorgabe.
