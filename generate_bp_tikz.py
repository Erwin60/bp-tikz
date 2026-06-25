#!/usr/bin/env python3
r"""
Generate LaTeX/PGFPlots code for two blood-pressure diagrams from a CSV file.

Inputs
------
Required:
  --csv PATH
  --date-from DATE
Optional:
  --date-to DATE
  --out PATH
  --standalone-out PATH
  --no-standalone
  --daily-stats PATH
  --weekly-stats PATH
  --delimiter auto|comma|semicolon|tab
  --show-daily-n
  --daily-n-y FLOAT
  --no-daily-summary-label

Supported date formats: YYYY-MM-DD, DD.MM.YYYY, DD.MM.YY, DD/MM/YYYY, DD/MM/YY.
The CSV must contain at least: Date, Systolic, Diastolic.
Common additional columns such as Pulse, Weight, Mean Arterial Pressure,
Pulse Pressure, Note, Time are preserved or recalculated where useful.

Method
------
1. Filter rows by date range. If --date-to is omitted, all rows from --date-from
   onward are used.
2. Aggregate first by calendar day so that days with many readings do not
   dominate the result.
3. Diagram 1: daily median points plus min--max ranges for systolic and
   diastolic pressure.
4. Diagram 2: 7-day blocks from date-from. Lines show equal-by-day means of
   daily means; vertical bars show the IQR of daily medians.
5. With --show-daily-n, the daily diagram shows small n= labels for
   the number of readings behind each day.
6. Reference elements are added to both charts:
   - HBPM comparison lines 135/85 mmHg.
   - ESC-oriented corridors 120--129 mmHg systolic and 70--79 mmHg diastolic.

The generated LaTeX fragment requires:
  \usepackage{tikz}
  \usepackage{pgfplots}
  \pgfplotsset{compat=1.18}

In addition to the fragment, the script creates by default a one-page standalone
TikZ/PGFPlots document with both diagrams placed one below the other. This is
useful for embedding the generated PDF as an appendix figure in another LaTeX
document.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DATE_FORMATS = [
    "%Y-%m-%d",
    "%d.%m.%Y",
    "%d.%m.%y",
    "%d/%m/%Y",
    "%d/%m/%y",
]

# Shared explanation of the recurring reference elements (ESC corridors and
# HBPM comparison lines). It is stated once per output so the two figure
# captions can cross-reference it instead of repeating it. The captions say
# "siehe Absatz oben"; this text supplies that paragraph.
REFERENCE_LINES_NOTE = (
    "Die hellgrauen Korridore 120--129\\,mmHg systolisch und 70--79\\,mmHg "
    "diastolisch sind allgemeine ESC-Orientierungen unter Therapie bei "
    "individueller Verträglichkeit und keine aneurysmaspezifischen "
    "Zielwertlinien. Die punktierten Linien bei 135\\,mmHg systolisch und "
    "85\\,mmHg diastolisch markieren häufig verwendete häusliche "
    "Vergleichsschwellen. Diese Referenzlinien gelten für beide Abbildungen."
)


COLUMN_ALIASES = {
    "date": ["date", "datum", "measurement date", "messdatum"],
    "systolic": ["systolic", "systole", "sys", "sbp", "systolisch"],
    "diastolic": ["diastolic", "diastole", "dia", "dbp", "diastolisch"],
    "pulse": ["pulse", "puls", "heart rate", "hr"],
    "note": ["note", "notes", "bemerkung", "notiz", "time", "zeit"],
}


@dataclass(frozen=True)
class Reading:
    d: date
    systolic: float
    diastolic: float
    pulse: Optional[float] = None
    note: str = ""

    @property
    def pulse_pressure(self) -> float:
        return self.systolic - self.diastolic

    @property
    def map_estimate(self) -> float:
        # Standard approximation: DBP + 1/3*(SBP-DBP)
        return self.diastolic + (self.systolic - self.diastolic) / 3.0


@dataclass
class DailyStats:
    d: date
    day_index: int
    n: int
    sys_min: float
    sys_max: float
    sys_median: float
    sys_mean: float
    dia_min: float
    dia_max: float
    dia_median: float
    dia_mean: float
    pulse_min: Optional[float]
    pulse_max: Optional[float]
    pulse_median: Optional[float]
    pulse_mean: Optional[float]
    pp_min: float
    pp_max: float
    pp_median: float
    pp_mean: float


@dataclass
class BlockStats:
    block: int
    start_date: date
    end_date: date
    x_mid: float
    n_days: int
    n_readings: int
    label: str
    sys_mean_of_daily_means: float
    sys_q1_daily_medians: float
    sys_q3_daily_medians: float
    dia_mean_of_daily_means: float
    dia_q1_daily_medians: float
    dia_q3_daily_medians: float
    pp_mean_of_daily_means: float
    pp_q1_daily_medians: float
    pp_q3_daily_medians: float
    # Per-day medians within the block, kept so the weekly chart can mark
    # individual outlier days against a clinical threshold.
    sys_daily_medians: List[float] = field(default_factory=list)
    dia_daily_medians: List[float] = field(default_factory=list)


def parse_date(value: str) -> date:
    value = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Could not parse date: {value!r}. Supported examples: 2026-05-15, 15.05.2026, 15.05.26")


def parse_number(value: Any) -> Optional[float]:
    """Parse English or European-style numbers.

    Supported examples:
      130
      130.5
      130,5
      1,234.56
      1.234,56

    Non-numeric suffixes such as "mmHg" are tolerated.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    s = s.replace("\u00a0", "").replace(" ", "")
    # Keep only the first plausible numeric token. This avoids problems with
    # comments such as "128 mmHg" while leaving time values in non-numeric
    # columns untouched.
    m = re.search(r"[-+]?\d[\d\.,]*", s)
    if not m:
        return None
    token = m.group(0)

    if "," in token and "." in token:
        # Decide by the last separator: 1.234,56 -> decimal comma;
        # 1,234.56 -> decimal dot.
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        token = token.replace(",", ".")
    # If only a dot is present, it is treated as decimal dot. Thousands-only
    # forms like 1.234 are not expected for blood pressure values and are left
    # unchanged.

    try:
        return float(token)
    except ValueError:
        return None


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def median(values: Sequence[float]) -> float:
    if not values:
        raise ValueError("median of empty list")
    vals = sorted(values)
    n = len(vals)
    mid = n // 2
    if n % 2:
        return vals[mid]
    return (vals[mid - 1] + vals[mid]) / 2.0


def quantile_linear(values: Sequence[float], q: float) -> float:
    """Linear-interpolated quantile, comparable to common statistical packages."""
    if not values:
        raise ValueError("quantile of empty list")
    if not 0 <= q <= 1:
        raise ValueError("q must be in [0, 1]")
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return vals[int(pos)]
    frac = pos - lo
    return vals[lo] * (1 - frac) + vals[hi] * frac


def format_num(x: Optional[float], decimals: int = 2) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    return f"{x:.{decimals}f}"


def latex_escape(text: str) -> str:
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("$", r"\$")
        .replace("#", r"\#")
        .replace("_", r"\_")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )


def dialect_from_delimiter(delimiter: str) -> csv.Dialect:
    class Custom(csv.excel):
        pass

    if delimiter == "comma":
        Custom.delimiter = ","
    elif delimiter == "semicolon":
        Custom.delimiter = ";"
    elif delimiter == "tab":
        Custom.delimiter = "\t"
    else:
        raise ValueError(f"Unsupported delimiter: {delimiter}")
    return Custom


def detect_delimiter(path: Path) -> Tuple[csv.Dialect, str]:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        delim = dialect.delimiter
    except csv.Error:
        dialect = dialect_from_delimiter("comma")
        delim = ","

    name = {",": "comma", ";": "semicolon", "\t": "tab"}.get(delim, repr(delim))
    return dialect, name


def normalize_header(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.strip().lower())


def find_column(headers: Sequence[str], canonical: str, required: bool = True) -> Optional[str]:
    aliases = COLUMN_ALIASES[canonical]
    norm_to_header = {normalize_header(h): h for h in headers}
    for alias in aliases:
        key = normalize_header(alias)
        if key in norm_to_header:
            return norm_to_header[key]
    if required:
        raise KeyError(f"Missing required column for {canonical!r}. Available columns: {headers}")
    return None


def read_csv(path: Path, date_from: date, date_to: Optional[date], delimiter: str = "auto") -> Tuple[List[Reading], str]:
    if delimiter == "auto":
        dialect, delimiter_name = detect_delimiter(path)
    else:
        dialect = dialect_from_delimiter(delimiter)
        delimiter_name = delimiter
    readings: List[Reading] = []
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")
        headers = [h for h in reader.fieldnames if h is not None]
        date_col = find_column(headers, "date")
        sys_col = find_column(headers, "systolic")
        dia_col = find_column(headers, "diastolic")
        pulse_col = find_column(headers, "pulse", required=False)
        note_col = find_column(headers, "note", required=False)

        for row_no, row in enumerate(reader, start=2):
            try:
                d = parse_date(row.get(date_col, ""))
            except ValueError as exc:
                raise ValueError(f"Row {row_no}: {exc}") from exc
            if d < date_from:
                continue
            if date_to is not None and d > date_to:
                continue
            s = parse_number(row.get(sys_col))
            dia = parse_number(row.get(dia_col))
            if s is None or dia is None:
                raise ValueError(f"Row {row_no}: systolic/diastolic value missing or invalid")
            p = parse_number(row.get(pulse_col)) if pulse_col else None
            note = str(row.get(note_col, "") or "") if note_col else ""
            readings.append(Reading(d=d, systolic=s, diastolic=dia, pulse=p, note=note))
    readings.sort(key=lambda r: (r.d, r.note))
    return readings, delimiter_name


def aggregate_daily(readings: Sequence[Reading], date_from: date) -> List[DailyStats]:
    grouped: Dict[date, List[Reading]] = defaultdict(list)
    for r in readings:
        grouped[r.d].append(r)

    stats: List[DailyStats] = []
    for d in sorted(grouped):
        rs = grouped[d]
        sys_vals = [r.systolic for r in rs]
        dia_vals = [r.diastolic for r in rs]
        pp_vals = [r.pulse_pressure for r in rs]
        pulse_vals = [r.pulse for r in rs if r.pulse is not None]
        stats.append(
            DailyStats(
                d=d,
                day_index=(d - date_from).days,
                n=len(rs),
                sys_min=min(sys_vals),
                sys_max=max(sys_vals),
                sys_median=median(sys_vals),
                sys_mean=mean(sys_vals),
                dia_min=min(dia_vals),
                dia_max=max(dia_vals),
                dia_median=median(dia_vals),
                dia_mean=mean(dia_vals),
                pulse_min=min(pulse_vals) if pulse_vals else None,
                pulse_max=max(pulse_vals) if pulse_vals else None,
                pulse_median=median(pulse_vals) if pulse_vals else None,
                pulse_mean=mean(pulse_vals) if pulse_vals else None,
                pp_min=min(pp_vals),
                pp_max=max(pp_vals),
                pp_median=median(pp_vals),
                pp_mean=mean(pp_vals),
            )
        )
    return stats


def block_label(start: date, end: date) -> str:
    if start.year == end.year and start.month == end.month:
        return f"{start.day:02d}--{end.day:02d}.{start.month:02d}"
    if start.year == end.year:
        return f"{start.day:02d}.{start.month:02d}--{end.day:02d}.{end.month:02d}"
    return f"{start.day:02d}.{start.month:02d}.{start.year}--{end.day:02d}.{end.month:02d}.{end.year}"


def aggregate_blocks(daily: Sequence[DailyStats], date_from: date, block_days: int = 7) -> List[BlockStats]:
    grouped: Dict[int, List[DailyStats]] = defaultdict(list)
    for d in daily:
        grouped[d.day_index // block_days].append(d)

    blocks: List[BlockStats] = []
    for block in sorted(grouped):
        ds = sorted(grouped[block], key=lambda x: x.d)
        start = date_from + timedelta(days=block * block_days)
        theoretical_end = start + timedelta(days=block_days - 1)
        end = min(theoretical_end, ds[-1].d)
        sys_daily_means = [x.sys_mean for x in ds]
        dia_daily_means = [x.dia_mean for x in ds]
        pp_daily_means = [x.pp_mean for x in ds]
        sys_daily_medians = [x.sys_median for x in ds]
        dia_daily_medians = [x.dia_median for x in ds]
        pp_daily_medians = [x.pp_median for x in ds]
        blocks.append(
            BlockStats(
                block=block,
                start_date=start,
                end_date=end,
                x_mid=(ds[0].day_index + ds[-1].day_index) / 2.0,
                n_days=len(ds),
                n_readings=sum(x.n for x in ds),
                label=block_label(start, end),
                sys_mean_of_daily_means=mean(sys_daily_means),
                sys_q1_daily_medians=quantile_linear(sys_daily_medians, 0.25),
                sys_q3_daily_medians=quantile_linear(sys_daily_medians, 0.75),
                dia_mean_of_daily_means=mean(dia_daily_means),
                dia_q1_daily_medians=quantile_linear(dia_daily_medians, 0.25),
                dia_q3_daily_medians=quantile_linear(dia_daily_medians, 0.75),
                pp_mean_of_daily_means=mean(pp_daily_means),
                pp_q1_daily_medians=quantile_linear(pp_daily_medians, 0.25),
                pp_q3_daily_medians=quantile_linear(pp_daily_medians, 0.75),
                sys_daily_medians=list(sys_daily_medians),
                dia_daily_medians=list(dia_daily_medians),
            )
        )
    return blocks


def coord_error(x: float, center: float, err: float) -> str:
    return f"({x:.2f},{center:.2f}) +- (0,{err:.2f})"


def coord_point(x: float, y: float) -> str:
    return f"({x:.2f},{y:.2f})"


def daily_n_nodes(daily: Sequence[DailyStats], y: float = 154.5) -> str:
    """Return PGFPlots nodes showing the number of readings per day.

    Each label is placed directly above the day's x position, centered on
    the day line, and rotated 90 degrees. The node is anchored east so the
    rotated text hangs downward from just below the top border. A frameless
    white background keeps it readable above the data.
    """
    nodes: List[str] = []
    for d in daily:
        nodes.append(
            rf"\node[font=\tiny, text=gray, rotate=90, anchor=east, "
            rf"fill=white, draw=none, inner sep=1pt] "
            rf"at (axis cs:{d.day_index:.2f},{y:.2f}) {{n={d.n}}};"
        )
    return "\n".join(nodes)



def daily_coordinates(daily: Sequence[DailyStats]) -> Dict[str, str]:
    """Build coordinate strings for the daily chart.

    Systolic and diastolic markers of a day are both drawn exactly on the
    day's x position. The vertical day grid lines are not drawn through the
    data area (only short tick stubs at the bottom and in the top label
    band), so the two bars do not visually merge with a grid line and need
    no horizontal offset.
    """
    sys_range, sys_median = [], []
    dia_range, dia_median = [], []
    for d in daily:
        x = float(d.day_index)
        sys_center = (d.sys_min + d.sys_max) / 2.0
        sys_err = (d.sys_max - d.sys_min) / 2.0
        dia_center = (d.dia_min + d.dia_max) / 2.0
        dia_err = (d.dia_max - d.dia_min) / 2.0
        sys_range.append(coord_error(x, sys_center, sys_err))
        sys_median.append(coord_point(x, d.sys_median))
        dia_range.append(coord_error(x, dia_center, dia_err))
        dia_median.append(coord_point(x, d.dia_median))
    return {
        "sys_range": " ".join(sys_range),
        "sys_median": " ".join(sys_median),
        "dia_range": " ".join(dia_range),
        "dia_median": " ".join(dia_median),
    }


def weekly_outlier_coordinates(
    blocks: Sequence[BlockStats],
    sys_hi: float,
    sys_lo: Optional[float],
    dia_hi: float,
    dia_lo: Optional[float],
    x_offset: float = 0.12,
) -> Dict[str, str]:
    """Coordinates of individual daily-median outliers per block.

    A day's systolic (diastolic) median is an outlier if it exceeds the
    upper clinical threshold sys_hi (dia_hi) or, when a lower threshold is
    given, falls below sys_lo (dia_lo). Outliers are drawn as small points
    slightly offset from the block's IQR marker so they stay distinguishable
    (systolic to the left, diastolic to the right)."""
    sys_pts, dia_pts = [], []
    for b in blocks:
        for v in b.sys_daily_medians:
            if v > sys_hi or (sys_lo is not None and v < sys_lo):
                sys_pts.append(coord_point(b.x_mid - x_offset, v))
        for v in b.dia_daily_medians:
            if v > dia_hi or (dia_lo is not None and v < dia_lo):
                dia_pts.append(coord_point(b.x_mid + x_offset, v))
    return {"sys_out": " ".join(sys_pts), "dia_out": " ".join(dia_pts)}


def weekly_coordinates(blocks: Sequence[BlockStats], central: str = "mean") -> Dict[str, str]:
    """Coordinates for the weekly chart.

    The IQR boxes always use Q1..Q3 of the daily medians. The central line
    uses either the mean of the daily means ("mean", default) or the median
    of the daily medians ("median"). The median variant is fully consistent
    with the IQR box (same quantile family) and more robust to outlier days;
    the mean variant matches the mean-based clinical HBPM/ESC thresholds.
    """
    sys_iqr, sys_central = [], []
    dia_iqr, dia_central = [], []
    for b in blocks:
        sys_center = (b.sys_q1_daily_medians + b.sys_q3_daily_medians) / 2.0
        sys_err = (b.sys_q3_daily_medians - b.sys_q1_daily_medians) / 2.0
        dia_center = (b.dia_q1_daily_medians + b.dia_q3_daily_medians) / 2.0
        dia_err = (b.dia_q3_daily_medians - b.dia_q1_daily_medians) / 2.0
        sys_iqr.append(coord_error(b.x_mid, sys_center, sys_err))
        dia_iqr.append(coord_error(b.x_mid, dia_center, dia_err))
        if central == "median":
            sys_c = median(b.sys_daily_medians) if b.sys_daily_medians else b.sys_mean_of_daily_means
            dia_c = median(b.dia_daily_medians) if b.dia_daily_medians else b.dia_mean_of_daily_means
        else:
            sys_c = b.sys_mean_of_daily_means
            dia_c = b.dia_mean_of_daily_means
        sys_central.append(coord_point(b.x_mid, sys_c))
        dia_central.append(coord_point(b.x_mid, dia_c))
    return {
        "sys_iqr": " ".join(sys_iqr),
        "sys_mean": " ".join(sys_central),
        "dia_iqr": " ".join(dia_iqr),
        "dia_mean": " ".join(dia_central),
    }


def xticks_for_daily(daily: Sequence[DailyStats]) -> Tuple[str, str]:
    max_day = daily[-1].day_index
    if max_day <= 0:
        ticks = [0]
    else:
        step = max(1, round(max_day / 5))
        ticks = list(range(0, max_day + 1, step))
        # Ensure the most recent day is labelled at the right edge. If the last
        # regular tick is not max_day, append it -- but only if it is far enough
        # from the previous tick, otherwise the two date labels overlap (e.g.
        # ticks 40 and 41 -> "24.0625.06"). When too close (< half a step), drop
        # the last regular tick and use max_day instead.
        if ticks[-1] != max_day:
            if max_day - ticks[-1] < max(1, step / 2):
                ticks[-1] = max_day
            else:
                ticks.append(max_day)
    labels = []
    date_by_index = {d.day_index: d.d for d in daily}
    # If a tick has no exact reading date, label by date_from + offset using first date as baseline.
    baseline = daily[0].d - timedelta(days=daily[0].day_index)
    for t in ticks:
        labels.append((date_by_index.get(t) or (baseline + timedelta(days=t))).strftime("%d.%m"))
    return ",".join(str(t) for t in ticks), ",".join(labels)


def xticks_for_blocks(blocks: Sequence[BlockStats]) -> Tuple[str, str]:
    ticks = ",".join(f"{b.x_mid:.2f}" for b in blocks)
    labels = ",".join(b.label for b in blocks)
    return ticks, labels


def generate_latex(
    daily: Sequence[DailyStats],
    blocks: Sequence[BlockStats],
    date_from: date,
    date_to: Optional[date],
    source_csv_name: str,
    show_daily_n: bool = False,
    daily_n_y: float = 154.5,
    daily_n_y_is_default: bool = True,
    show_daily_summary_label: bool = True,
    week_outliers: bool = False,
    week_outlier_sys_hi: float = 135.0,
    week_outlier_dia_hi: float = 85.0,
    week_outlier_sys_lo: Optional[float] = None,
    week_outlier_dia_lo: Optional[float] = None,
    week_central: str = "mean",
) -> str:
    if not daily:
        raise ValueError("No daily statistics available")

    weekly_coords = weekly_coordinates(blocks, central=week_central)
    # Legend/caption wording for the weekly central line depends on the choice.
    if week_central == "median":
        central_legend = "7-Tage-Median"
        central_caption = (
            "Linien zeigen den Median der Tagesmediane, Fehlerbalken den "
            "Interquartilsbereich der Tagesmediane"
        )
    else:
        central_legend = "7-Tage-Mittelwert"
        central_caption = (
            "Linien zeigen den nach Kalendertagen gewichteten Mittelwert der "
            "Tagesmittelwerte, Fehlerbalken den Interquartilsbereich der "
            "Tagesmediane"
        )
    if week_outliers:
        weekly_outliers = weekly_outlier_coordinates(
            blocks, week_outlier_sys_hi, week_outlier_sys_lo,
            week_outlier_dia_hi, week_outlier_dia_lo,
        )
    else:
        weekly_outliers = {"sys_out": "", "dia_out": ""}
    daily_ticks, daily_labels = xticks_for_daily(daily)
    block_ticks, block_labels = xticks_for_blocks(blocks)
    max_day = daily[-1].day_index
    xmax = max_day + 1
    xmin = -1

    daily_coords = daily_coordinates(daily)

    # Fixed lower bounds for both charts.
    daily_ymin = 55
    weekly_ymin = 60

    # Dynamic upper bounds so the highest plotted value (and, for the daily
    # chart, the n= labels) always fit. Bounds are aligned to a 20 mmHg grid
    # so that PGFPlots draws clean, evenly spaced y-ticks (60, 80, 100, ...)
    # instead of picking coarse automatic ticks like 100/150 on an odd range.
    def round_up_20(v: float) -> int:
        return int(math.ceil(v / 20.0) * 20)

    def round_up_10(v: float) -> int:
        return int(math.ceil(v / 10.0) * 10)

    def round_down_20(v: float) -> int:
        return int(math.floor(v / 20.0) * 20)

    def ytick_list(lo: int, hi: int, step: int = 20) -> str:
        return ",".join(str(v) for v in range(lo, hi + 1, step))

    # Daily chart: tallest plotted element is the top of the systolic range
    # bars, i.e. the per-day maximum systolic value. When n= labels are
    # shown, reserve an additional band above the data so the rotated labels
    # sit in a clear strip just under the top border rather than overlapping
    # the data.
    daily_data_max = max(d.sys_max for d in daily)
    # The upper bound is aligned to a 10 mmHg grid (so it can sit at e.g. 170,
    # closer to the data than a 20-grid would allow) while the labelled ticks
    # stay on the 20 mmHg grid (60, 80, 100, ...). A minimum clear band is
    # kept above the highest value; it is larger when n= labels are shown so
    # the rotated labels and the gap above them fit.
    min_headroom = 22.0 if show_daily_n else 6.0
    daily_ymax = round_up_10(daily_data_max + min_headroom)
    daily_ymax = max(daily_ymax, daily_ymin + 40)
    # The chart references fixed thresholds in its legend: the HBPM 135 mmHg
    # systolic line and the ESC corridor up to 129 mmHg. Keep ymax high enough
    # that these are always visible (with a little air above the 135 line),
    # otherwise the legend would point to lines that lie above the top border.
    REF_TOP = 135.0  # highest referenced systolic threshold (HBPM)
    daily_ymax = max(daily_ymax, round_up_10(REF_TOP + 5.0))  # >= 140
    # Ticks are labelled every 20 mmHg, only up to the last 20-multiple that
    # fits at or below ymax (avoids a label drawn above the top border).
    daily_tick_top = round_down_20(daily_ymax)
    daily_ytick = ytick_list(round_up_20(daily_ymin), daily_tick_top)

    # Place the n= labels inside the top band, leaving a clear gap above them
    # to the top border (where the top tick stubs sit). If the caller
    # explicitly overrode --daily-n-y, honour that value; otherwise sit a few
    # mmHg below the top edge.
    if daily_n_y_is_default:
        effective_daily_n_y = daily_ymax - 6.0
    else:
        effective_daily_n_y = daily_n_y

    # Weekly chart: the tallest plotted element is the upper IQR whisker of
    # the systolic daily medians, which reaches sys_q3 (the bar is centered on
    # (q1+q3)/2 with half-width (q3-q1)/2). Use that, and the systolic block
    # mean, as the data top. The upper bound is aligned to a 5 mmHg grid with
    # a small headroom so the systolic markers are not glued to the top border
    # (e.g. a whisker top of ~133 yields ymax 145, not 140). Labelled ticks
    # stay on the 20 mmHg grid.
    def round_up_5(v: float) -> int:
        return int(math.ceil(v / 5.0) * 5)

    if blocks:
        weekly_data_max = max(
            max(b.sys_q3_daily_medians for b in blocks),
            max(b.sys_mean_of_daily_means for b in blocks),
        )
        # If outlier days are drawn, make sure the highest one still fits.
        if week_outliers:
            all_medians = [v for b in blocks for v in b.sys_daily_medians]
            hi = [v for v in all_medians if v > week_outlier_sys_hi]
            if hi:
                weekly_data_max = max(weekly_data_max, max(hi))
    else:
        weekly_data_max = daily_data_max
    weekly_ymax = max(round_up_5(weekly_data_max + 8.0), weekly_ymin + 40)
    # Keep the HBPM 135 / ESC 129 reference lines visible here as well.
    weekly_ymax = max(weekly_ymax, round_up_5(135.0 + 5.0))  # >= 140
    weekly_tick_top = round_down_20(weekly_ymax)
    weekly_ytick = ytick_list(round_up_20(weekly_ymin), weekly_tick_top)

    total_readings = sum(d.n for d in daily)
    n_days = len(daily)
    avg_sys = mean([d.sys_mean for d in daily])
    avg_dia = mean([d.dia_mean for d in daily])
    med_sys_med = median([d.sys_median for d in daily])
    med_dia_med = median([d.dia_median for d in daily])
    under_135_85 = sum(1 for d in daily if d.sys_mean < 135 and d.dia_mean < 85)
    actual_to = daily[-1].d if date_to is None else date_to
    incomplete_blocks = [b for b in blocks if b.n_days < 7]
    incomplete_note = ""
    if incomplete_blocks:
        last = incomplete_blocks[-1]
        incomplete_note = f" Der letzte Block umfasst nur {last.n_days} Tag(e) und ist daher weniger belastbar."

    daily_n_annotation = daily_n_nodes(daily, y=effective_daily_n_y) if show_daily_n else ""

    # Vertical day markers as short tick stubs instead of full grid lines.
    # One stub rises from the bottom border into the empty strip below the
    # data, and one descends from the top border, so the data area stays free
    # of vertical lines that could merge with the systolic/diastolic bars.
    # Both stubs are drawn regardless of whether n= labels are shown.
    stub_h = 5.0
    stub_lines: List[str] = []
    for d in daily:
        x = d.day_index
        stub_lines.append(
            rf"\draw[gray!55, line width=0.4pt] (axis cs:{x:.2f},{daily_ymin}) -- "
            rf"(axis cs:{x:.2f},{daily_ymin + stub_h:.1f});"
        )
        stub_lines.append(
            rf"\draw[gray!55, line width=0.4pt] (axis cs:{x:.2f},{daily_ymax - stub_h:.1f}) -- "
            rf"(axis cs:{x:.2f},{daily_ymax});"
        )
    daily_stub_annotation = "\n".join(stub_lines)

    daily_n_caption_note = (
        " Graue `n=`-Angaben oben zeigen die Messungen pro Tag."
        if show_daily_n else ""
    )

    daily_xlabel = f"Tage seit {date_from.strftime('%d.%m.%Y')}"
    if show_daily_summary_label:
        daily_xlabel = (
            f"Tage seit {date_from.strftime('%d.%m.%Y')} | "
            f"Mittelwert {avg_sys:.1f}/{avg_dia:.1f} mmHg | "
            f"Median {med_sys_med:.1f}/{med_dia_med:.1f} mmHg | "
            f"\\textless{{}}135/85: {under_135_85}/{n_days} Tage"
        )

    preamble_note = r"""% Requires in the main LaTeX document:
% \usepackage{tikz}
% \usepackage{pgfplots}
% \pgfplotsset{compat=1.18}
"""

    summary = f"""
% Automatically generated from {latex_escape(source_csv_name)}
% Date range used: {date_from.isoformat()} to {actual_to.isoformat()}
% Readings used: {total_readings}; calendar days: {n_days}
% Equal-by-day mean: {avg_sys:.1f}/{avg_dia:.1f} mmHg
% Median of daily medians: {med_sys_med:.1f}/{med_dia_med:.1f} mmHg
% Daily means below 135/85: {under_135_85} of {n_days}
"""

    text_paragraph = f"""
Seit dem {date_from.strftime('%d.%m.%Y')} liegen im ausgewerteten Zeitraum bis zum {actual_to.strftime('%d.%m.%Y')} insgesamt {total_readings} dokumentierte häusliche Blutdruckmessungen an {n_days} Kalendertagen vor. Für die Auswertung werden die Einzelmessungen zunächst pro Kalendertag zusammengefasst, damit Tage mit vielen Messungen nicht stärker gewichtet werden als Tage mit wenigen Messungen. Auf Basis der gleich nach Tagen gewichteten Tagesmittel ergibt sich ein durchschnittlicher häuslicher Blutdruck von ungefähr {avg_sys:.1f}/{avg_dia:.1f}\\,mmHg. Der Median der Tagesmediane liegt bei ungefähr {med_sys_med:.1f}/{med_dia_med:.1f}\\,mmHg. {under_135_85} von {n_days} Tagesmitteln lagen unter 135/85\\,mmHg. {REFERENCE_LINES_NOTE}
"""

    fig1 = f"""
\\begin{{figure*}}[!t]
\\centering
\\begin{{tikzpicture}}
\\begin{{axis}}[
    width=0.95\\textwidth,
    height=7.2cm,
    ymin={daily_ymin},
    ymax={daily_ymax},
    ytick={{{daily_ytick}}},
    xmin={xmin},
    xmax={xmax},
    ymajorgrids=true,
    xmajorgrids=false,
    xlabel={{{daily_xlabel}}},
    xlabel style={{font=\\scriptsize}},
    ylabel={{Blutdruck [mmHg]}},
    xtick={{{daily_ticks}}},
    xticklabels={{{daily_labels}}},
    xtick style={{draw=none}},
    legend style={{font=\\scriptsize, at={{(0.5,-0.25)}}, anchor=north, legend columns=3, draw=none}},
    tick label style={{font=\\scriptsize}},
    label style={{font=\\small}},
]
\\addplot[draw=none, fill=black!8] coordinates {{({xmin},120) ({xmax},120) ({xmax},129) ({xmin},129)}} \\closedcycle;
\\addlegendentry{{ESC-Zielkorridor syst. 120--129}}
\\addplot[draw=none, fill=gray!8] coordinates {{({xmin},70) ({xmax},70) ({xmax},79) ({xmin},79)}} \\closedcycle;
\\addlegendentry{{ESC-Zielkorridor diast. 70--79}}
\\addplot[dashdotted, black] coordinates {{({xmin},129) ({xmax},129)}};
\\addlegendentry{{Obergrenze ESC-Korridor syst. 129}}
\\addplot[only marks, mark=|, mark size=7pt, black, error bars/.cd, y dir=both, y explicit] coordinates {{{daily_coords['sys_range']}}};
\\addlegendentry{{Systolische Tages-Spannweite}}
\\addplot[only marks, mark=*, mark size=1.4pt, black] coordinates {{{daily_coords['sys_median']}}};
\\addlegendentry{{Systolischer Tagesmedian}}
\\addplot[only marks, mark=|, mark size=6pt, gray, error bars/.cd, y dir=both, y explicit] coordinates {{{daily_coords['dia_range']}}};
\\addlegendentry{{Diastolische Tages-Spannweite}}
\\addplot[only marks, mark=square*, mark size=1.2pt, gray] coordinates {{{daily_coords['dia_median']}}};
\\addlegendentry{{Diastolischer Tagesmedian}}
\\addplot[dotted, black] coordinates {{({xmin},135) ({xmax},135)}};
\\addlegendentry{{HBPM-Vergleich syst. 135}}
\\addplot[dotted, gray] coordinates {{({xmin},85) ({xmax},85)}};
\\addlegendentry{{HBPM-Vergleich diast. 85}}
{daily_stub_annotation}
{daily_n_annotation}
\\end{{axis}}
\\end{{tikzpicture}}
\\caption{{Tagesweise Darstellung ab {date_from.strftime('%d.%m.%Y')}: Punkte zeigen den Tagesmedian, vertikale Balken die Tagesspannweite (Min--Max); Tage mit nur einer Messung haben keine sichtbare Spannweite. Zu Korridoren und Vergleichslinien siehe Absatz oben.{daily_n_caption_note}}}
\\label{{fig:bp_daily_range}}
\\end{{figure*}}
"""

    # Outlier markers for the weekly chart (only when enabled and present).
    if week_outliers and (weekly_outliers["sys_out"] or weekly_outliers["dia_out"]):
        parts = []
        if weekly_outliers["sys_out"]:
            parts.append(
                "\\addplot[only marks, mark=o, mark size=1.6pt, black] coordinates {"
                + weekly_outliers["sys_out"] + "};\n"
                "\\addlegendentry{Systolische Ausreißer-Tage}\n"
            )
        if weekly_outliers["dia_out"]:
            parts.append(
                "\\addplot[only marks, mark=o, mark size=1.4pt, gray] coordinates {"
                + weekly_outliers["dia_out"] + "};\n"
                "\\addlegendentry{Diastolische Ausreißer-Tage}\n"
            )
        weekly_outlier_plots = "".join(parts)
        outlier_caption_note = (
            f" Kreise markieren einzelne Tage (ggf. mehrere je Block), deren "
            f"Tagesmedian die Schwelle überschreitet "
            f"(syst. >{week_outlier_sys_hi:g}, diast. >{week_outlier_dia_hi:g}\\,mmHg)."
        )
    else:
        weekly_outlier_plots = ""
        outlier_caption_note = ""

    fig2 = f"""
\\begin{{figure*}}[!t]
\\centering
\\begin{{tikzpicture}}
\\begin{{axis}}[
    width=0.95\\textwidth,
    height=6.8cm,
    ymin={weekly_ymin},
    ymax={weekly_ymax},
    ytick={{{weekly_ytick}}},
    xmin={xmin},
    xmax={xmax},
    grid=major,
    xlabel={{Tage seit {date_from.strftime('%d.%m.%Y')}}},
    ylabel={{Blutdruck [mmHg]}},
    xtick={{{block_ticks}}},
    xticklabels={{{block_labels}}},
    legend style={{font=\\scriptsize, at={{(0.5,-0.27)}}, anchor=north, legend columns=3, draw=none}},
    tick label style={{font=\\scriptsize}},
    label style={{font=\\small}},
]
\\addplot[draw=none, fill=black!8] coordinates {{({xmin},120) ({xmax},120) ({xmax},129) ({xmin},129)}} \\closedcycle;
\\addlegendentry{{ESC-Zielkorridor syst. 120--129}}
\\addplot[draw=none, fill=gray!8] coordinates {{({xmin},70) ({xmax},70) ({xmax},79) ({xmin},79)}} \\closedcycle;
\\addlegendentry{{ESC-Zielkorridor diast. 70--79}}
\\addplot[dashdotted, black] coordinates {{({xmin},129) ({xmax},129)}};
\\addlegendentry{{Obergrenze ESC-Korridor syst. 129}}
\\addplot[only marks, mark=|, mark size=7pt, black, error bars/.cd, y dir=both, y explicit] coordinates {{{weekly_coords['sys_iqr']}}};
\\addlegendentry{{Systolischer IQR der Tagesmediane}}
\\addplot[thick, mark=*, mark size=1.6pt, black] coordinates {{{weekly_coords['sys_mean']}}};
\\addlegendentry{{Systolischer {central_legend}}}
\\addplot[only marks, mark=|, mark size=6pt, gray, error bars/.cd, y dir=both, y explicit] coordinates {{{weekly_coords['dia_iqr']}}};
\\addlegendentry{{Diastolischer IQR der Tagesmediane}}
\\addplot[thick, dashed, mark=square*, mark size=1.3pt, gray] coordinates {{{weekly_coords['dia_mean']}}};
\\addlegendentry{{Diastolischer {central_legend}}}
{weekly_outlier_plots}\\addplot[dotted, black] coordinates {{({xmin},135) ({xmax},135)}};
\\addlegendentry{{HBPM-Vergleich syst. 135}}
\\addplot[dotted, gray] coordinates {{({xmin},85) ({xmax},85)}};
\\addlegendentry{{HBPM-Vergleich diast. 85}}
\\end{{axis}}
\\end{{tikzpicture}}
\\caption{{Verdichtete 7-Tage-Übersicht: {central_caption}; dies dämpft unregelmäßige Messhäufigkeit, ohne die Streuung ganz zu verbergen. Zu Korridoren und Vergleichslinien siehe Absatz oben.{outlier_caption_note}{incomplete_note}}}
\\label{{fig:bp_weekly_agg}}
\\end{{figure*}}
"""

    return preamble_note + summary + text_paragraph + "\n" + fig1 + "\n" + fig2


def extract_tikz_blocks_and_captions(fragment: str) -> Tuple[List[str], List[str]]:
    tikz_blocks = re.findall(
        r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}",
        fragment,
        flags=re.S,
    )
    captions = re.findall(
        r"\\caption\{(.*?)\}\s*\\label",
        fragment,
        flags=re.S,
    )
    return tikz_blocks, captions


def generate_standalone_onepage(fragment: str, title: str = "Blutdruckdiagramme") -> str:
    """Build a standalone LaTeX file with both diagrams on one A4 page.

    Instead of cropping tightly to the content, the page is a real A4 sheet
    and the two diagrams are scaled to fill the vertical space that the title,
    the shared reference paragraph and the two captions leave free. The
    diagram heights are computed at runtime from \\textheight minus the
    measured height of the surrounding text, split evenly between the two
    charts, so the charts always use the maximum available height regardless
    of how long the captions turn out to be.
    """
    tikz_blocks, captions = extract_tikz_blocks_and_captions(fragment)
    if len(tikz_blocks) < 2:
        raise ValueError("Could not find two tikzpicture blocks in generated LaTeX fragment")

    cap1 = captions[0] if len(captions) >= 1 else "Tagesweise Darstellung des häuslichen Blutdrucks."
    cap2 = captions[1] if len(captions) >= 2 else "Verdichtete 7-Tage-Übersicht des Blutdruckverlaufs."

    # The pgfplots "height" key fixes the axis height. To make the charts fill
    # the page, that fixed height is replaced by a LaTeX length (\chartheight)
    # whose value is derived from the remaining vertical space at typeset time.
    block0 = tikz_blocks[0].replace("height=7.2cm", "height=\\chartheight")
    block1 = tikz_blocks[1].replace("height=6.8cm", "height=\\chartheight")

    return rf"""\documentclass[11pt]{{article}}
\usepackage[T1]{{fontenc}}
\usepackage[utf8]{{inputenc}}
\usepackage[ngerman]{{babel}}
\usepackage[a4paper,margin=12mm]{{geometry}}
\usepackage{{tikz}}
\usepackage{{pgfplots}}
\pgfplotsset{{compat=1.18}}
\pagestyle{{empty}}
\setlength{{\parindent}}{{0pt}}

% Measure the height of a box without printing it, so we can subtract the
% text blocks (title, reference paragraph, both captions) from \textheight
% and give the remaining space, halved, to each diagram.
\newlength{{\chartheight}}
\newsavebox{{\headerbox}}
\newsavebox{{\capAbox}}
\newsavebox{{\capBbox}}

\begin{{document}}
\centering

\sbox{{\headerbox}}{{\parbox{{\textwidth}}{{\centering
\textbf{{\large {latex_escape(title)}}}\par\vspace{{2mm}}
{{\footnotesize {REFERENCE_LINES_NOTE}\par}}}}}}

\sbox{{\capAbox}}{{\parbox{{\textwidth}}{{\footnotesize \textbf{{Abbildung 1.}} {cap1}\par}}}}
\sbox{{\capBbox}}{{\parbox{{\textwidth}}{{\footnotesize \textbf{{Abbildung 2.}} {cap2}\par}}}}

% Remaining vertical space split between the two charts. Each pgfplots axis
% places its legend below the axis at about (0.5,-0.25), i.e. the legend sits
% roughly 0.25*\chartheight below the axis and is NOT counted by the "height"
% key. Each diagram therefore occupies about 1.25*\chartheight plus the
% legend's own text lines. Solving 2*(1.25*\chartheight) = available gives the
% factor 2/5. Only the genuinely fixed surrounding spacing is reserved here
% (the \vspace amounts between the elements); the legends' own text lines are
% absorbed by the trailing \vfill below so that the page is always filled to
% the bottom margin regardless of how many legend rows each chart has.
\newlength{{\availspace}}
\setlength{{\availspace}}{{\dimexpr\textheight
  - \ht\headerbox - \dp\headerbox
  - \ht\capAbox - \dp\capAbox
  - \ht\capBbox - \dp\capBbox
  - 12mm\relax}}
\setlength{{\chartheight}}{{\dimexpr\availspace/5*2\relax}}

\usebox{{\headerbox}}\par\vspace{{3mm}}

{block0}\par\vspace{{1.5mm}}
\usebox{{\capAbox}}\par\vspace{{6mm}}

{block1}\par\vspace{{1.5mm}}
\usebox{{\capBbox}}
\par\vfill

\end{{document}}
"""




def generate_standalone_two_sides(
    fragment: str,
    fig_width_cm: float = 16.0,
) -> str:
    r"""Build a standalone LaTeX file in the "two sides" layout.

    This reproduces the layout of bp_diagrams_standalone_two_sides.tex:
      - documentclass[tikz,border=3mm]{standalone}
      - each tikzpicture is its own cropped standalone page
      - the figure caption is rendered as a \node placed below the axis
        (anchored to the bounding box), not as a float \caption
      - axis width is a fixed length (default 16.0cm) instead of a fraction
        of \textwidth, since standalone has no meaningful \textwidth.
    """
    tikz_blocks, captions = extract_tikz_blocks_and_captions(fragment)
    if len(tikz_blocks) < 2:
        raise ValueError("Could not find two tikzpicture blocks in generated LaTeX fragment")

    cap1 = (captions[0] if len(captions) >= 1 else "").strip()
    cap2 = (captions[1] if len(captions) >= 2 else "").strip()

    width_str = f"{fig_width_cm:g}cm"

    # The two-sides layout puts each figure on its own cropped page with no
    # shared running paragraph, so the captions' "siehe Absatz oben" cross-
    # reference would dangle. Replace it on each page with the full shared
    # reference-lines note so every page stays self-contained.
    ref_plain = REFERENCE_LINES_NOTE
    cross_ref = "Zu Korridoren und Vergleichslinien siehe Absatz oben."

    def fix_caption(cap: str) -> str:
        if cross_ref in cap:
            return cap.replace(cross_ref, ref_plain)
        return cap

    cap1 = fix_caption(cap1)
    cap2 = fix_caption(cap2)

    def adapt_block(block: str, fig_number: int, caption: str) -> str:
        # Replace the fractional axis width with a fixed length.
        adapted = block.replace(r"width=0.95\textwidth", f"width={width_str}")
        # Insert a caption node before the closing of the tikzpicture, anchored
        # to the bounding box south west, matching the two-sides template.
        caption_node = (
            "\n\\node[anchor=north west, align=left, "
            f"text width={width_str}, font=\\footnotesize, yshift=-4mm] "
            "at (current bounding box.south west) "
            f"{{Abbildung {fig_number}. {caption}}};\n"
        )
        adapted = adapted.replace(
            "\\end{axis}\n\\end{tikzpicture}",
            "\\end{axis}\n" + caption_node + "\\end{tikzpicture}",
        )
        return adapted

    block1 = adapt_block(tikz_blocks[0], 1, cap1)
    block2 = adapt_block(tikz_blocks[1], 2, cap2)

    return (
        "\\documentclass[tikz,border=3mm]{standalone}\n"
        "\\usepackage[T1]{fontenc}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage[ngerman]{babel}\n"
        "\\usepackage{pgfplots}\n"
        "\\pgfplotsset{compat=1.18}\n"
        "\\begin{document}\n"
        f"{block1}\n"
        "\\vspace{8mm}\n"
        f"{block2}\n"
        "\\end{document}\n"
    )


def write_daily_stats(path: Path, daily: Sequence[DailyStats]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "date", "day_index", "n",
            "sys_min", "sys_max", "sys_median", "sys_mean",
            "dia_min", "dia_max", "dia_median", "dia_mean",
            "pulse_min", "pulse_max", "pulse_median", "pulse_mean",
            "pulse_pressure_min", "pulse_pressure_max", "pulse_pressure_median", "pulse_pressure_mean",
        ])
        for d in daily:
            writer.writerow([
                d.d.isoformat(), d.day_index, d.n,
                format_num(d.sys_min), format_num(d.sys_max), format_num(d.sys_median), format_num(d.sys_mean),
                format_num(d.dia_min), format_num(d.dia_max), format_num(d.dia_median), format_num(d.dia_mean),
                format_num(d.pulse_min), format_num(d.pulse_max), format_num(d.pulse_median), format_num(d.pulse_mean),
                format_num(d.pp_min), format_num(d.pp_max), format_num(d.pp_median), format_num(d.pp_mean),
            ])


def write_block_stats(path: Path, blocks: Sequence[BlockStats]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "block", "start_date", "end_date", "x_mid", "n_days", "n_readings", "label",
            "sys_mean_of_daily_means", "sys_q1_daily_medians", "sys_q3_daily_medians",
            "dia_mean_of_daily_means", "dia_q1_daily_medians", "dia_q3_daily_medians",
            "pulse_pressure_mean_of_daily_means", "pulse_pressure_q1_daily_medians", "pulse_pressure_q3_daily_medians",
        ])
        for b in blocks:
            writer.writerow([
                b.block, b.start_date.isoformat(), b.end_date.isoformat(), format_num(b.x_mid), b.n_days, b.n_readings, b.label,
                format_num(b.sys_mean_of_daily_means), format_num(b.sys_q1_daily_medians), format_num(b.sys_q3_daily_medians),
                format_num(b.dia_mean_of_daily_means), format_num(b.dia_q1_daily_medians), format_num(b.dia_q3_daily_medians),
                format_num(b.pp_mean_of_daily_means), format_num(b.pp_q1_daily_medians), format_num(b.pp_q3_daily_medians),
            ])


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate LaTeX/PGFPlots code for daily and 7-day blood-pressure diagrams from CSV."
    )
    parser.add_argument("--csv", required=True, type=Path, help="Input CSV file with Date, Systolic and Diastolic columns.")
    parser.add_argument("--date-from", required=True, help="First date to include, e.g. 2026-05-15 or 15.05.2026.")
    parser.add_argument("--date-to", default=None, help="Last date to include. If omitted, all values from date-from onward are used.")
    parser.add_argument("--out", type=Path, default=Path("bp_diagrams.tex"), help="Output LaTeX fragment path.")
    parser.add_argument("--daily-stats", type=Path, default=None, help="Optional daily statistics CSV output.")
    parser.add_argument("--weekly-stats", type=Path, default=None, help="Optional 7-day block statistics CSV output.")
    parser.add_argument("--block-days", type=int, default=7, help="Aggregation block length in days; default: 7.")
    parser.add_argument("--delimiter", choices=["auto", "comma", "semicolon", "tab"], default="auto", help="Input CSV delimiter; default: auto-detect comma, semicolon or tab.")
    parser.add_argument("--standalone-out", type=Path, default=Path("bp_diagrams_both_onepage_standalone.tex"), help="Output standalone LaTeX/TikZ file with both diagrams on one page.")
    parser.add_argument("--no-standalone", action="store_true", help="Do not write the standalone one-page TikZ/LaTeX document.")
    parser.add_argument("--standalone-title", default="Blutdruckdiagramme", help="Title printed above the two standalone diagrams.")
    parser.add_argument("--show-daily-n", action="store_true", help="Show small gray n= labels at the top of the daily chart, indicating the number of readings per day.")
    parser.add_argument("--daily-n-y", type=float, default=None, help="Y-position (anchor near top) for the optional daily n= labels. If omitted, it is placed automatically just under the (dynamic) top border of the daily chart.")
    parser.add_argument("--week-outliers", action="store_true", help="In the weekly chart, additionally mark individual daily-median outlier days (above a fixed clinical threshold) as small points next to each block's IQR marker.")
    parser.add_argument("--week-outlier-sys-hi", type=float, default=135.0, help="Upper systolic threshold for weekly outlier days; default: 135 mmHg (HBPM comparison line).")
    parser.add_argument("--week-outlier-dia-hi", type=float, default=85.0, help="Upper diastolic threshold for weekly outlier days; default: 85 mmHg (HBPM comparison line).")
    parser.add_argument("--week-outlier-sys-lo", type=float, default=None, help="Optional lower systolic threshold for weekly outlier days; if omitted, only high outliers are marked.")
    parser.add_argument("--week-outlier-dia-lo", type=float, default=None, help="Optional lower diastolic threshold for weekly outlier days; if omitted, only high outliers are marked.")
    parser.add_argument("--week-central", choices=["mean", "median"], default="mean", help="Central line of the weekly chart: 'mean' (default; nach Kalendertagen gewichteter Mittelwert der Tagesmittelwerte, an die klinischen HBPM/ESC-Mittelwertschwellen anschlussfähig) or 'median' (Median der Tagesmediane; konsistent zur IQR-Box und robuster gegen Ausreißertage).")
    parser.add_argument("--no-daily-summary-label", action="store_true", help="Use only the simple x-axis label in the daily chart and suppress the automatic mean/median/<135/85 summary line.")
    parser.add_argument("--two-sides-out", type=Path, default=Path("bp_diagrams_standalone_two_sides.tex"), help="Output standalone LaTeX/TikZ file with each diagram on its own cropped page and the caption rendered as a node below the axis.")
    parser.add_argument("--no-two-sides", action="store_true", help="Do not write the two-sides standalone TikZ/LaTeX document.")
    parser.add_argument("--two-sides-width-cm", type=float, default=16.0, help="Fixed axis width in cm for the two-sides standalone document; default: 16.0.")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    date_from = parse_date(args.date_from)
    date_to = parse_date(args.date_to) if args.date_to else None
    if date_to is not None and date_to < date_from:
        raise SystemExit("--date-to must be >= --date-from")
    if args.block_days <= 0:
        raise SystemExit("--block-days must be positive")

    readings, delimiter_name = read_csv(args.csv, date_from, date_to, delimiter=args.delimiter)
    if not readings:
        raise SystemExit("No valid readings in the requested date range")
    daily = aggregate_daily(readings, date_from)
    blocks = aggregate_blocks(daily, date_from, block_days=args.block_days)

    latex = generate_latex(
        daily,
        blocks,
        date_from,
        date_to,
        args.csv.name,
        show_daily_n=args.show_daily_n,
        daily_n_y=(args.daily_n_y if args.daily_n_y is not None else 154.5),
        daily_n_y_is_default=(args.daily_n_y is None),
        show_daily_summary_label=not args.no_daily_summary_label,
        week_outliers=args.week_outliers,
        week_outlier_sys_hi=args.week_outlier_sys_hi,
        week_outlier_dia_hi=args.week_outlier_dia_hi,
        week_outlier_sys_lo=args.week_outlier_sys_lo,
        week_outlier_dia_lo=args.week_outlier_dia_lo,
        week_central=args.week_central,
    )
    args.out.write_text(latex, encoding="utf-8")

    standalone_path: Optional[Path] = None
    if not args.no_standalone:
        standalone_path = args.standalone_out
        standalone_tex = generate_standalone_onepage(latex, title=args.standalone_title)
        standalone_path.write_text(standalone_tex, encoding="utf-8")

    two_sides_path: Optional[Path] = None
    if not args.no_two_sides:
        two_sides_path = args.two_sides_out
        two_sides_tex = generate_standalone_two_sides(latex, fig_width_cm=args.two_sides_width_cm)
        two_sides_path.write_text(two_sides_tex, encoding="utf-8")

    if args.daily_stats:
        write_daily_stats(args.daily_stats, daily)
    if args.weekly_stats:
        write_block_stats(args.weekly_stats, blocks)

    print(f"Input delimiter: {delimiter_name}")
    print(f"Daily n labels: {'on' if args.show_daily_n else 'off'}")
    print(f"Daily summary label: {'on' if not args.no_daily_summary_label else 'off'}")
    print(f"Wrote LaTeX fragment: {args.out}")
    if standalone_path is not None:
        print(f"Wrote standalone one-page TikZ/LaTeX: {standalone_path}")
    if two_sides_path is not None:
        print(f"Wrote two-sides standalone TikZ/LaTeX: {two_sides_path}")
    if args.daily_stats:
        print(f"Wrote daily stats: {args.daily_stats}")
    if args.weekly_stats:
        print(f"Wrote 7-day stats: {args.weekly_stats}")
    print(f"Readings used: {len(readings)}; days: {len(daily)}; 7-day blocks: {len(blocks)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
