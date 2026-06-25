# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [1.2.1] - 2026-06-25

### Fixed
- `generate_bp_tikz.py`: x-axis date labels on the daily chart could overlap at
  the right edge when the most recent day fell just after a regular tick (e.g.
  ticks 40 and 41 printed "24.0625.06"). The final tick is now replaced by the
  most recent day instead of appended when the gap is smaller than half a tick
  step, so the latest date is still labelled but never collides. Applies to both
  the one-page and two-sides standalone layouts.

## [1.2.0] - 2026-06-24

### Added
- `generate_bp_daytime_tikz.py`: an **hour-of-day measurement histogram**
  (Figure 1b) directly below the daily profile. Bars count readings per hour
  (0–23), are coloured by time-of-day block (Morning/Midday/Evening) in the same
  color/BW style as the other figures, and dashed vertical lines mark the block
  boundaries. This visualizes measurement coverage across the day, i.e. how well
  the daily kinetics are sampled.

### Changed
- `generate_bp_daytime_tikz.py`: the data-availability note and interpretation
  text are now **fully data-driven** with respect to block coverage. Instead of
  always referring to the evening block as sparse, the text now names the
  actually weakest block (using a < 60 % of-average threshold) and automatically
  switches to a "blocks are now evenly covered" wording once coverage is
  balanced.
- Regenerated example outputs
  (`examples/fig_weekday_daytime_color.pdf`, `…_bw.pdf`) to include Figure 1b.

## [1.1.0] - 2026-06-23

### Added
- Companion tool `generate_bp_daytime_tikz.py` for **time-of-day × weekday**
  analysis: a self-contained LaTeX/PGFPlots document with a daily profile
  (median per Morning/Midday/Evening block with IQR bands) and grouped
  weekday × time-of-day median bars.
- Three configurable time-of-day blocks via `--blocks "a,b"` (labels adapt
  automatically).
- Tukey outlier marking (`--outliers up|both|none`) with an `IQR ≥ 1 mmHg`
  guard against pseudo-outliers; high outliers as circles, low as `×`.
- Color and black-and-white styles (`--style color|bw`); in BW the ESC corridor
  is hatched to stay distinct from the solid IQR bands.
- Time-of-day recovery from a time column, the **Note** column (iBP export), or
  a timestamp in the date field; two-digit years and AM/PM supported.
- Automatic evaluation-period (from–to) and count header, plus a fully
  data-driven interpretation note.
- German and English manuals (`docs/Manual_Daytime_DE.md`,
  `docs/Manual_Daytime_EN.md`) and example outputs
  (`examples/fig_weekday_daytime_color.pdf`, `…_bw.pdf`).

## [1.0.0] - 2026-06-23

### Added
- Two-stage aggregation (per calendar day, then fixed-length blocks).
- Daily diagram with daily-median points, min–max ranges, optional `n=` labels,
  and an automatic summary line.
- Block diagram with selectable central line (`--week-central mean|median`) and
  IQR error bars of daily medians.
- Outlier-day marking (`--week-outliers`) with configurable upper/lower
  thresholds.
- Optional daily and weekly statistics CSV export.
- One-page and two-sides standalone LaTeX outputs; the one-page layout scales
  the diagram heights to fill the available page height.
- European/English number and date parsing; comma/semicolon/tab delimiter
  auto-detection.
- IEEE-format documentation (DE/EN) and Markdown manuals (DE/EN).

### Fixed
- One-page standalone now fills the full page height regardless of caption and
  legend length.
