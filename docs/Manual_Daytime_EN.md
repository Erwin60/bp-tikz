# `generate_bp_daytime_tikz.py` — Manual (EN)

Companion to `generate_bp_tikz.py`. It analyzes **time-of-day and weekday**
patterns in home blood pressure and produces a **self-contained** LaTeX/PGFPlots
document (A4) with two figures.

> **Note.** This is a visualization tool, **not** a diagnostic system. The
> thresholds drawn (ESC corridors, HBPM comparison lines) are general orientation
> lines, **not** individual target values. The determination of individual target
> values rests with the treating physician.

---

## What it produces

- **Figure 1 — daily profile:** median per time-of-day block (systolic and
  diastolic) across all days, with shaded **IQR** bands (25th–75th percentile),
  the gray **ESC orientation corridors** (120–129 systolic, 70–79 diastolic), and
  the dotted **HBPM comparison lines** at 135/85.
- **Figure 1b — hour-of-day histogram:** number of readings per hour (0–23),
  coloured by time-of-day block, with dashed block boundaries. Shows how evenly
  the day is sampled (coverage of the daily kinetics), i.e. how reliable the
  time-of-day trend statement is.
- **Figure 2 — weekday × time-of-day:** grouped median bars per weekday and block
  (2a systolic, 2b diastolic), with **Tukey outlier** markers (circle = high,
  optional `×` = low), the ESC corridor, and the comparison line.

The header automatically prints the **evaluation period** (from–to) and the
number of readings/days. The interpretation note at the foot is computed entirely
from the data (block medians, trend statement, weekday span, outlier counts,
per-block measurement coverage). The data-availability hints are data-driven:
they name the weakest block automatically and switch to an "evenly covered"
wording once coverage is balanced.

---

## Time-of-day blocks

Three blocks, controlled by `--blocks "a,b"`:

- **Morning:** hour `< a`
- **Midday:** hour `a` to `b` (inclusive)
- **Evening:** hour `> b`

Default: `10,15` (Morning < 10:00, Midday 10:00–15:00, Evening > 15:00). Labels in
the legend, title, and methodology adapt automatically.

---

## Input format

At least **Date**, **Systolic**, **Diastolic**; a **time of day** is also
required. It is searched for — in this order — in:

1. a dedicated time column (`Time`/`Zeit`),
2. the **Note** column (some apps such as iBP store the time there),
3. a timestamp embedded in the date field (`2026-05-15 07:30`).

Column names are recognized via German/English aliases; the delimiter
(comma/semicolon/tab) and decimal comma are auto-detected. Extra columns (Pulse,
Weight, Mean Arterial Pressure, …) are ignored. Two- and four-digit years and
AM/PM times are supported.

```csv
Date,Time,Systolic,Diastolic,Pulse
2026-05-15,07:00,118,66,66
2026-05-15,13:00,124,68,66
2026-05-15,20:10,128,72,63
```

The iBP format, where the time is held in the `Note` column, is handled as well.

---

## Options

| Option | Required | Default | Purpose |
|---|---|---|---|
| `--csv CSV` | no | `bp.csv` | Input file with the readings. |
| `--style color\|bw` | no | `color` | Color or black-and-white variant. |
| `--blocks "a,b"` | no | `10,15` | Boundaries of the three blocks (hours). |
| `--outliers up\|both\|none` | no | `up` | Tukey outliers: high only / high+low / none. |
| `-o`, `--out OUT` | no | `bp_weekday_daytime.tex` | Output file name. |

**Black-and-white (`--style bw`):** grayscale + patterns (morning solid, midday
north-east hatch, evening dots); in the daily profile, systolic solid and
diastolic dashed. The ESC corridor is drawn **hatched with a dashed border** so
it stays distinct from the solidly shaded IQR bands.

**Outliers (Tukey):** a value is an outlier if it lies above `Q3 + 1.5·IQR`
(high) or below `Q1 − 1.5·IQR` (low). They are only computed when a cell has at
least **four** readings and the interquartile range is non-degenerate
(`IQR ≥ 1 mmHg`), which prevents pseudo-outliers when values are nearly identical.
Default `up`, because for blood pressure the high spikes are usually the
clinically relevant ones.

---

## Usage examples

### 1. Minimal (color, default blocks)

```bash
python3 generate_bp_daytime_tikz.py --csv bp_raw.csv --style color
```

Produces `bp_weekday_daytime.tex` (compile standalone with `pdflatex`).

### 2. Black-and-white for printing

```bash
python3 generate_bp_daytime_tikz.py --csv bp_raw.csv --style bw \
  -o bp_weekday_daytime_bw.tex
```

### 3. Custom blocks and low outliers

```bash
python3 generate_bp_daytime_tikz.py --csv bp_raw.csv \
  --blocks 10,16 --outliers both
```

### 4. iBP export (time in the Note column)

```bash
python3 generate_bp_daytime_tikz.py --csv iBP_Readings.csv --style color
```

---

## Compiling

```bash
pdflatex bp_weekday_daytime.tex
```

A single pass is enough. The document needs `tikz`, `pgfplots`
(`compat=1.18`), and in the BW variant the TikZ `patterns` library (included
automatically).

---

## Diagnostics

If reading fails, the script prints a **diagnostic**: detected delimiter, mapped
columns, number of data rows read, per-field failures
(systolic/diastolic/date/time), and the first unparsable row. This makes a
deviating date or time format easy to pin down.
