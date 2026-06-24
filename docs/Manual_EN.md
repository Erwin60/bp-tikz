# User Manual — `generate_bp_tikz.py`

Turns a CSV of home blood-pressure readings into two coordinated
LaTeX/PGFPlots diagrams (daily and block views) plus optional statistics CSVs.
This manual describes operation; the methodological rationale for the
computation variants is covered in detail in the companion IEEE paper.

---

## 1. One-sentence overview

Raw CSV in → two diagrams (daily course + 7-day overview) plus statistics CSVs
out, fully controllable via command-line parameters and deterministically
reproducible.

---

## 2. Prerequisites

- **Python 3** (standard library only, no extra packages required).
- To include the output in your own LaTeX document:
  ```latex
  \usepackage{tikz}
  \usepackage{pgfplots}
  \pgfplotsset{compat=1.18}
  ```

---

## 3. Input format

The **input CSV** (`--csv`) needs at least these columns (German/English alias
names recognized, case-insensitive):

| Content | recognized names (selection) | Required |
|---|---|---|
| Date | `date`, `datum`, `messdatum` | yes |
| Systolic | `systolic`, `systolisch`, `sys`, `sbp` | yes |
| Diastolic | `diastolic`, `diastolisch`, `dia`, `dbp` | yes |
| Pulse | `pulse`, `puls`, `hr` | no |
| Note/Time | `note`, `notiz`, `bemerkung`, `time`, `zeit` | no |

**Date formats:** `YYYY-MM-DD`, `DD.MM.YYYY`, `DD.MM.YY`, `DD/MM/YYYY`,
`DD/MM/YY`.

**Numbers:** English *and* European (`130`, `130.5`, `130,5`, `1.234,56`,
`1,234.56`); suffixes such as `mmHg` are tolerated.

**Delimiter:** auto-detected (comma, semicolon, tab) or forced via
`--delimiter`.

> **Important:** The previously generated `bp_daily_stats.csv` /
> `bp_weekly_stats.csv` are **outputs** of the script, not valid input for
> `--csv`. The input is the **individual readings** (one row per reading).

Example of a valid input CSV:

```csv
Date,Time,Systolic,Diastolic,Pulse,Note
2026-05-15,07:30,124,68,66,
2026-05-15,21:10,130,70,63,
2026-05-16,07:20,119,62,70,
2026-05-16,21:00,158,77,66,after exercise
```

---

## 4. Quick start

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15
```

Produces:

- `bp_diagrams.tex` — includable fragment with both diagrams
- `bp_diagrams_both_onepage_standalone.tex` — both diagrams on one A4 page
- `bp_diagrams_standalone_two_sides.tex` — one cropped page per diagram

Include in your own document:

```latex
\input{bp_diagrams.tex}
```

---

## 5. What the two diagrams show

**Diagram 1 — daily course.** One point per day (daily median) plus a vertical
bar (daily range min–max). Days with only one reading have no visible range. A
summary line at the bottom gives the weighted mean, the median of daily medians,
and the number of days below 135/85 mmHg.

**Diagram 2 — block overview (default 7 days).** Line = block location measure
(mean or median, see below), error bars = interquartile range (IQR) of daily
medians. Optionally individual outlier days as points.

**Both** contain the ESC corridors (120–129 / 70–79 mmHg, light gray) and the
HBPM comparison lines (135 / 85 mmHg, dotted). These are comparison and
orientation lines, **not** individual target values.

---

## 6. The key knobs

### 6.1 Central line: mean or median

```bash
--week-central mean     # default: day-weighted mean
--week-central median   # median of daily medians (robust, IQR-consistent)
```

- `mean` — compatible with mean-based HBPM/ESC thresholds.
- `median` — robust against individual outlier days, consistent with the IQR
  box.

Both are legitimate; the choice depends on purpose. Because location and
dispersion are shown separately, no information is lost.

### 6.2 Mark outlier days

```bash
--week-outliers                       # on, default thresholds 135/85
--week-outlier-sys-hi 130             # custom upper systolic threshold
--week-outlier-dia-hi 80              # custom upper diastolic threshold
--week-outlier-sys-lo 110             # optional lower threshold
--week-outlier-dia-lo 65              # optional lower threshold
```

Marks individual days as points but **does not remove them** from mean, median,
and IQR.

### 6.3 Block length

```bash
--block-days 7     # default
--block-days 14    # e.g. 14-day blocks
```

### 6.4 Daily-diagram options

```bash
--show-daily-n               # small n= labels (readings per day)
--daily-n-y 150              # fixed height of the n= labels
--no-daily-summary-label     # hide the summary line
```

### 6.5 Export statistics CSVs

```bash
--daily-stats bp_daily_stats.csv
--weekly-stats bp_weekly_stats.csv
```

### 6.6 Output control

```bash
--out bp_fragment.tex
--standalone-out bp_onepage.tex
--two-sides-out bp_two_sides.tex
--two-sides-width-cm 14
--standalone-title "Blood-pressure course 05–06/2026"
--no-standalone        # do not write the single-page standalone
--no-two-sides         # do not write the two-sides standalone
```

---

## 7. Common recipes

**Date window + statistics export:**
```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 15.05.2026 --date-to 20.06.2026 \
  --out bp_fragment.tex \
  --daily-stats bp_daily_stats.csv \
  --weekly-stats bp_weekly_stats.csv
```

**Median line with outliers:**
```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv --date-from 2026-05-15 \
  --week-central median --week-outliers
```

**Fragment only, no standalone files:**
```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv --date-from 2026-05-15 \
  --out bp_fragment.tex --no-standalone --no-two-sides
```

**German export with semicolons:**
```bash
python3 generate_bp_tikz.py \
  --csv bp_export_de.csv --date-from 2026-05-15 \
  --delimiter semicolon
```

**Fully specified (as for the document appendix):**
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

## 8. Understanding the output CSVs

### Daily statistics (`--daily-stats`)
`date, day_index, n, sys_min, sys_max, sys_median, sys_mean,
dia_min, dia_max, dia_median, dia_mean, pulse_min…mean,
pulse_pressure_min…mean`

One row per calendar day; `n` = number of readings, `day_index` counts from
`--date-from` (0-based).

### Block statistics (`--weekly-stats`)
`block, start_date, end_date, x_mid, n_days, n_readings, label,
sys_mean_of_daily_means, sys_q1_daily_medians, sys_q3_daily_medians,
dia_mean_of_daily_means, dia_q1_daily_medians, dia_q3_daily_medians,
pulse_pressure_*`

`*_mean_of_daily_means` = weighted mean; `*_q1/q3_daily_medians` = quartiles of
the daily medians (IQR bounds).

---

## 9. Checking reproducibility

Same CSV + same date window + same parameters → identical output. Quick test:
compare the values in the summary line (mean, median, "<135/85: x/y days")
against the daily-statistics CSV.

---

## 10. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Missing required column for 'date'` | date/value column not recognized → check or rename column names. |
| `Row N: systolic/diastolic value missing or invalid` | empty/invalid cell in row N → add the value or fix the row. |
| `--date-to must be >= --date-from` | date window reversed. |
| `No valid readings in the requested date range` | window contains no data → check `--date-from`/`--date-to`. |
| Decimal numbers misinterpreted | set `--delimiter` explicitly; check comma vs. dot. |
| Single-page standalone not filling the page | use the current script version (height computed at runtime from page height). |
| Diagrams do not appear in the main document | add `tikz`, `pgfplots`, and `\pgfplotsset{compat=1.18}` to the preamble. |

---

## 11. Limitations

This is a processing and visualization tool, **not** a diagnostic system. The
thresholds drawn are comparison and orientation lines; individual target values
are set by the treating physician. Short blocks with few days are less robust
(the caption notes this). The outlier marking is a threshold-based highlighting,
not a statistical outlier classification.

---

## 12. Parameter quick reference

| Parameter | Default | Purpose |
|---|---|---|
| `--csv` | — (required) | Input CSV (date, systolic, diastolic; opt. time/pulse/note) |
| `--date-from` | — (required) | first date |
| `--date-to` | all from `date-from` | last date |
| `--out` | `bp_diagrams.tex` | LaTeX fragment |
| `--daily-stats` | off | daily statistics CSV |
| `--weekly-stats` | off | block statistics CSV |
| `--block-days` | `7` | block length |
| `--delimiter` | `auto` | `auto`/`comma`/`semicolon`/`tab` |
| `--standalone-out` | `bp_diagrams_both_onepage_standalone.tex` | single-page standalone |
| `--no-standalone` | off | disable single-page standalone |
| `--standalone-title` | `Blutdruckdiagramme` | title of the standalone page |
| `--show-daily-n` | off | `n=` labels |
| `--daily-n-y` | automatic | fixed height of `n=` labels |
| `--week-outliers` | off | mark outlier days |
| `--week-outlier-sys-hi` | `135` | upper systolic threshold |
| `--week-outlier-dia-hi` | `85` | upper diastolic threshold |
| `--week-outlier-sys-lo` | off | lower systolic threshold |
| `--week-outlier-dia-lo` | off | lower diastolic threshold |
| `--week-central` | `mean` | `mean`/`median` |
| `--no-daily-summary-label` | off | disable summary line |
| `--two-sides-out` | `bp_diagrams_standalone_two_sides.tex` | two-sides standalone |
| `--no-two-sides` | off | disable two-sides standalone |
| `--two-sides-width-cm` | `16.0` | axis width (cm) two-sides |

---

## 13. Tested environment and software versions

This tool has been developed and tested **only** in the following environments.
It is plain Python plus a standard LaTeX toolchain and should work elsewhere, but
no other environment has been verified.

| Component | Version / notes |
|---|---|
| Python | 3.9+ (developed against CPython 3.12; standard library only) |
| LaTeX engine | `pdflatex` (TeX Live; `tikz` + `pgfplots`, `compat=1.18`) |
| Document class for the papers | `IEEEtran.cls` V1.8b |

**Tested platforms (only):**

- **macOS** — desktop Python 3 and a desktop TeX Live / MacTeX installation.
- **iPad / iPhone** with **a-Shell** (<https://holzschu.github.io/a-Shell_iOS/>) —
  a local iOS terminal bundling Python 3 and TeX Live (with TikZ and LuaTeX);
  the script and the LaTeX compilation both run on-device.
- **Texifier** (formerly TeXpad, <https://www.texifier.com/>) on macOS and
  iPadOS/iOS — used to edit and typeset the LaTeX documents.

**Important platform note.** Texifier's built-in live typesetter *TexpadTeX*
runs in a sandbox and does **not** permit shell-escape (`\write18`). The Python
script `generate_bp_tikz.py` is therefore run in **a-Shell** (iOS) or a normal
shell (macOS); Texifier is then used to open and typeset the generated `.tex`
files. On macOS, Texifier can also be pointed at a full MacTeX distribution if a
package is missing from its bundle.

Windows and Linux are expected to work with any standard Python 3 and TeX Live
installation but have **not** been tested.

---

## 14. AI usage note

Generative AI (Claude, Anthropic) was used in an assistive capacity for
documentation, code review, and preparation of the anonymized example. The
concept, algorithm, and data are the author's, who reviewed and is responsible
for all output; the AI is not an author. The full disclosure is in `AI_USAGE.md`;
the IEEE papers carry the corresponding disclosure in their Acknowledgment
section per IEEE policy.
