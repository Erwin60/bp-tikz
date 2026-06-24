# bp-tikz — Blood-Pressure Diagram Generator

`generate_bp_tikz.py` turns a simple CSV of home blood-pressure (HBPM) readings
into two coordinated **LaTeX/PGFPlots** diagrams (a daily course and a
block/weekly overview) plus optional machine-readable statistics CSVs. It uses a
**two-stage aggregation** (first per calendar day, then in fixed-length blocks)
so that days with many readings do not dominate the result.

> **Disclaimer.** This is a data-processing and visualization tool, **not** a
> diagnostic system. The thresholds drawn (ESC corridors, HBPM comparison lines)
> are general orientation lines, **not** individual target values. The
> determination of individual target values rests with the treating physician.

---

## Features

- Two-stage aggregation: per calendar day, then into fixed-length blocks
  (default 7 days).
- Daily diagram: daily median points with min–max ranges; optional `n=` labels.
- Block diagram: choice of central line — calendar-day-weighted **mean** or
  **median of daily medians** — with the **IQR** of daily medians as error bars.
- Optional outlier-day marking against configurable thresholds.
- Outputs an includable LaTeX fragment, a one-page standalone, a two-sides
  standalone, and optional daily/weekly statistics CSVs.
- European and English number/date parsing; comma/semicolon/tab auto-detection.
- No third-party Python dependencies (standard library only).

For the full methodology and the rationale behind the mean/median variants and
the outlier logic, see the IEEE-format papers in [`docs/`](docs/).

---

## Companion tool: `generate_bp_daytime_tikz.py` (time-of-day × weekday)

In addition to the daily/weekly view, the repository ships a second, independent
generator that analyzes **time-of-day patterns**: `generate_bp_daytime_tikz.py`.
It groups readings into three day blocks — **Morgen/Morning** (`< a`),
**Mittag/Midday** (`a–b`), **Abend/Evening** (`> b`), default `a,b = 10,15` —
and produces a **self-contained** LaTeX/PGFPlots document (A4) with:

- **Figure 1 — daily profile:** median per block (systolic and diastolic) with
  shaded **IQR** bands, the gray **ESC orientation corridors** (120–129 / 70–79),
  and the 135/85 HBPM comparison lines.
- **Figure 1b — hour-of-day histogram:** number of readings per hour (0–23),
  coloured by day block, with dashed block boundaries — shows how evenly the day
  is sampled (coverage of the daily kinetics).
- **Figure 2 — weekday × time-of-day:** grouped median bars per weekday and
  block, with **Tukey outlier** markers (circle = high, optional `×` = low), the
  ESC corridor, and the comparison line.

It shares the project's robust CSV reader (comma/semicolon/tab auto-detection,
German/English aliases, European decimals) and additionally recovers the
**time of day** from a dedicated time column, the **Note** column (as exported by
some apps such as iBP), or a timestamp embedded in the date field. The header
prints the evaluation period (from–to) and the measurement count automatically.

Two layout variants are selectable:

- `--style color` — blue/teal/orange (default).
- `--style bw` — grayscale with patterns (solid / north-east hatch / dots) and a
  **hatched ESC corridor**, so corridor and IQR band stay distinguishable in
  black-and-white printing.

```bash
# color, default day blocks (Morgen <10, Mittag 10–15, Abend >15)
python3 generate_bp_daytime_tikz.py --csv bp_raw.csv --style color

# black-and-white, custom blocks, also mark low outliers
python3 generate_bp_daytime_tikz.py --csv bp_raw.csv --style bw \
  --blocks 10,16 --outliers both -o bp_weekday_daytime_bw.tex
```

Example outputs:
[`examples/fig_weekday_daytime_color.pdf`](examples/fig_weekday_daytime_color.pdf),
[`examples/fig_weekday_daytime_bw.pdf`](examples/fig_weekday_daytime_bw.pdf).
Full option reference: [`docs/Manual_Daytime_DE.md`](docs/Manual_Daytime_DE.md)
and [`docs/Manual_Daytime_EN.md`](docs/Manual_Daytime_EN.md).

> The evening block depends on regular evening measurements; with morning-only or
> morning/midday data it stays sparse, and the document says so. The tool is for
> visualization, not diagnosis — target values rest with the treating physician.

---

## Requirements

- **Python 3.9+** (standard library only; no `pip install` needed).
- A **LaTeX** toolchain with `tikz` and `pgfplots` to compile the generated
  output. The including document needs:
  ```latex
  \usepackage{tikz}
  \usepackage{pgfplots}
  \pgfplotsset{compat=1.18}
  ```

---

## Quick start

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv \
  --date-from 2026-05-15
```

This writes `bp_diagrams.tex` (fragment) plus two standalone documents. Include
the fragment in your own document with `\input{bp_diagrams.tex}`.

A median central line with marked outlier days and statistics export:

```bash
python3 generate_bp_tikz.py \
  --csv bp_raw.csv --date-from 2026-05-15 --date-to 2026-06-20 \
  --week-central median --week-outliers \
  --daily-stats bp_daily_stats.csv \
  --weekly-stats bp_weekly_stats.csv
```

See the [user manual](docs/) for all options and recipes, in English and German.

---

## Input format

The input CSV needs at least **Date**, **Systolic**, **Diastolic** columns
(German/English alias names recognized). Optional: Pulse, Time, Note. One row per
reading.

```csv
Date,Time,Systolic,Diastolic,Pulse,Note
2026-05-15,07:30,124,68,66,
2026-05-15,21:10,130,70,63,
2026-05-16,21:00,158,77,66,after exercise
```

Date formats: `YYYY-MM-DD`, `DD.MM.YYYY`, `DD.MM.YY`, `DD/MM/YYYY`, `DD/MM/YY`.
An anonymized example data set is provided in
[`examples/bp_anon_example.csv`](examples/bp_anon_example.csv).

> The generated `*_daily_stats.csv` / `*_weekly_stats.csv` are **outputs**, not
> valid `--csv` input.

---

## Repository layout

```
generate_bp_tikz.py         # main tool (daily + block/weekly diagrams)
generate_bp_daytime_tikz.py  # companion tool (time-of-day x weekday)
docs/                        # IEEE papers (DE/EN) + Markdown manuals (DE/EN)
examples/                    # anonymized example CSV and generated figures
LICENSE                      # MIT
CITATION.cff                 # how to cite
CHANGELOG.md
CONTRIBUTING.md
```

---

## Tested environment and software versions

This tool has been developed and tested **only** in the following environments.
It is plain Python plus a standard LaTeX toolchain and should work elsewhere, but
no other environment has been verified.

| Component | Version / notes |
|---|---|
| Python | 3.9+ (developed against CPython 3.12; standard library only) |
| LaTeX engine | `pdflatex` (TeX Live; `tikz` + `pgfplots` with `compat=1.18`) |
| Document class for the papers | `IEEEtran.cls` V1.8b |

**Tested platforms (only):**

- **macOS** — desktop Python 3 and a desktop TeX Live / MacTeX installation.
- **iPad / iPhone** with **[a-Shell](https://holzschu.github.io/a-Shell_iOS/)** —
  a local iOS terminal that bundles Python 3 and TeX Live (2025, with TikZ and
  LuaTeX). The script and the LaTeX compilation both run locally on-device in
  a-Shell.
- **[Texifier](https://www.texifier.com/)** (formerly TeXpad) on macOS and
  iPadOS/iOS — used to **edit and typeset** the LaTeX documents.

**Important platform note.** Texifier's built-in live typesetter *TexpadTeX*
runs in a sandbox and does **not** permit shell-escape (`\write18`) or external
tools. Running `generate_bp_tikz.py` itself (a Python script) is therefore done
in **a-Shell** (on iOS) or a normal shell (on macOS); Texifier is then used to
open and typeset the generated `.tex` files. On macOS, Texifier can also be
pointed at a full MacTeX distribution if a package is missing from its bundle.

Other platforms (Windows, Linux) are expected to work with any standard Python 3
and TeX Live installation but have **not** been tested.

---

## AI usage disclosure

Generative AI (Claude, Anthropic) was used in an assistive capacity for
documentation drafting, code review, LaTeX scaffolding, and preparation of the
anonymized example. The author defined the concept and algorithm, owns the data,
and reviewed and verified all output; the AI is not an author. See
[`AI_USAGE.md`](AI_USAGE.md) for the full disclosure. The IEEE papers carry the
corresponding disclosure in their Acknowledgment section, as required by IEEE
policy.

## License

Released under the [MIT License](LICENSE).

## Citation

If you use this tool in academic work, please cite it using the metadata in
[`CITATION.cff`](CITATION.cff) (GitHub shows a "Cite this repository" button once
the file is on the default branch).
