# `generate_bp_tikz.py` — typische Aufrufvarianten

Stand der CLI laut hochgeladenem Skript. Alle Beispiele gehen davon aus, dass
die **Roh-CSV** (Spalten mindestens `Date, Systolic, Diastolic`; optional
`Time, Pulse, Note`) z. B. `bp_raw.csv` heißt. Die mitgelieferten Dateien
`bp_daily_stats.csv` und `bp_weekly_stats.csv` sind dagegen *Ausgaben* des
Skripts (`--daily-stats` / `--weekly-stats`) und nicht als `--csv`-Eingabe
gedacht.

Datumsformate für `--date-from` / `--date-to`: `YYYY-MM-DD`, `DD.MM.YYYY`,
`DD.MM.YY`, `DD/MM/YYYY`, `DD/MM/YY`.

---

## 1. Minimaler Aufruf

Nur Pflichtargumente. Schreibt Fragment + beide Standalone-Dokumente mit den
Default-Namen ins aktuelle Verzeichnis.

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15
```

Erzeugt: `bp_diagrams.tex`, `bp_diagrams_both_onepage_standalone.tex`,
`bp_diagrams_standalone_two_sides.tex`.

---

## 2. Mit explizitem Datumsfenster und benannten Ausgaben

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 15.05.2026 \
  --date-to 20.06.2026 \
  --out bp_fragment.tex \
  --daily-stats bp_daily_stats.csv \
  --weekly-stats bp_weekly_stats.csv
```

Reproduziert u. a. die beiden Statistik-CSVs, die in das Hauptdokument
einfließen.

---

## 3. Nur das LaTeX-Fragment (keine Standalone-Dateien)

Sinnvoll, wenn das Fragment direkt per `\input{}` ins Hauptdokument
eingebunden wird.

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15 \
  --out bp_fragment.tex \
  --no-standalone \
  --no-two-sides
```

---

## 4. Tagesdiagramm mit `n=`-Beschriftung

Zeigt pro Tag, wie viele Messungen dahinterstehen.

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15 \
  --show-daily-n
```

Mit manueller Höhe der `n=`-Labels (statt automatischer Platzierung):

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15 \
  --show-daily-n \
  --daily-n-y 150
```

---

## 5. Wochenchart: Zentrallinie Median statt Mittelwert

`--week-central median` nutzt den Median der Tagesmediane (robuster gegen
Ausreißertage, konsistent zur IQR-Box); Default ist `mean` (nach Kalendertagen
gewichteter Mittelwert der Tagesmittelwerte).

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15 \
  --week-central median
```

---

## 6. Wochenchart mit markierten Ausreißertagen

Markiert einzelne Tagesmediane oberhalb der Schwelle (Default 135/85 mmHg, die
HBPM-Vergleichslinien) als kleine Punkte neben dem jeweiligen IQR-Marker.

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15 \
  --week-outliers
```

Mit eigenen oberen Schwellen:

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15 \
  --week-outliers \
  --week-outlier-sys-hi 130 \
  --week-outlier-dia-hi 80
```

Zusätzlich auch *untere* Schwellen markieren (z. B. zu niedrige Tage unter
Therapie sichtbar machen):

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15 \
  --week-outliers \
  --week-outlier-sys-hi 135 --week-outlier-dia-hi 85 \
  --week-outlier-sys-lo 110 --week-outlier-dia-lo 65
```

---

## 7. Andere Blocklänge als 7 Tage

`--block-days` steuert die Aggregationslänge des zweiten Diagramms.

```bash
# 14-Tage-Blöcke
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15 \
  --block-days 14
```

Hinweis: Die Default-Ausgabenamen und Beschriftungen sprechen von „7-Tage";
bei abweichendem `--block-days` ggf. eigene `--out`-Namen vergeben.

---

## 8. Standalone-Dokumente anpassen

Titel über der Einseiten-Variante und feste Achsenbreite der Zweiseiten-Variante.

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15 \
  --standalone-title "Blutdruckverlauf 05–06/2026" \
  --standalone-out bp_onepage.tex \
  --two-sides-out bp_two_sides.tex \
  --two-sides-width-cm 14
```

---

## 9. Eingabe mit Semikolon-Trennung (typische DE-Export-CSV)

```bash
python3 generate_bp_tikz.py \
  --csv bp_export_de.csv \
  --date-from 2026-05-15 \
  --delimiter semicolon
```

`--delimiter` kennt `auto` (Default), `comma`, `semicolon`, `tab`.

---

## 10. Tagesdiagramm ohne automatische Zusammenfassungszeile

Unterdrückt die automatische `Mittel/Median/<135/85`-Zeile und nutzt nur die
einfache x-Achsenbeschriftung.

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15 \
  --no-daily-summary-label
```

---

## 11. „Voll bestückter" Aufruf für die Dokument-Anhänge

Kombiniert die im Hauptdokument verwendeten Optionen in einem Lauf: Median-Linie,
markierte Ausreißertage auf 135/85, `n=`-Labels, beide Statistik-CSVs sowie
eigene Ausgabenamen für Fragment und Standalone-Dateien.

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15 \
  --date-to 2026-06-20 \
  --week-central median \
  --week-outliers \
  --week-outlier-sys-hi 135 \
  --week-outlier-dia-hi 85 \
  --show-daily-n \
  --out bp_fragment.tex \
  --standalone-out bp_onepage.tex \
  --two-sides-out bp_two_sides.tex \
  --two-sides-width-cm 16 \
  --daily-stats bp_daily_stats.csv \
  --weekly-stats bp_weekly_stats.csv
```

---

## Parameter-Kurzreferenz

| Parameter | Default | Zweck |
|---|---|---|
| `--csv` | — (Pflicht) | Eingabe-CSV (Date, Systolic, Diastolic; optional Time/Pulse/Note) |
| `--date-from` | — (Pflicht) | erstes Datum im Auswertungsfenster |
| `--date-to` | alle ab `date-from` | letztes Datum |
| `--out` | `bp_diagrams.tex` | LaTeX-Fragment (beide Diagramme) |
| `--daily-stats` | aus | Tagesstatistik als CSV schreiben |
| `--weekly-stats` | aus | Blockstatistik als CSV schreiben |
| `--block-days` | `7` | Aggregationslänge des zweiten Diagramms |
| `--delimiter` | `auto` | `auto`/`comma`/`semicolon`/`tab` |
| `--standalone-out` | `bp_diagrams_both_onepage_standalone.tex` | Einseiten-Standalone |
| `--no-standalone` | aus | Einseiten-Standalone nicht schreiben |
| `--standalone-title` | `Blutdruckdiagramme` | Titel über den Standalone-Diagrammen |
| `--show-daily-n` | aus | `n=`-Labels im Tagesdiagramm |
| `--daily-n-y` | automatisch | feste y-Position der `n=`-Labels |
| `--week-outliers` | aus | Ausreißertage im Wochenchart markieren |
| `--week-outlier-sys-hi` | `135` | obere systolische Ausreißerschwelle |
| `--week-outlier-dia-hi` | `85` | obere diastolische Ausreißerschwelle |
| `--week-outlier-sys-lo` | aus | optionale untere systolische Schwelle |
| `--week-outlier-dia-lo` | aus | optionale untere diastolische Schwelle |
| `--week-central` | `mean` | Zentrallinie Wochenchart: `mean`/`median` |
| `--no-daily-summary-label` | aus | automatische Zusammenfassungszeile aus |
| `--two-sides-out` | `bp_diagrams_standalone_two_sides.tex` | Zweiseiten-Standalone |
| `--no-two-sides` | aus | Zweiseiten-Standalone nicht schreiben |
| `--two-sides-width-cm` | `16.0` | feste Achsenbreite (cm) der Zweiseiten-Variante |
