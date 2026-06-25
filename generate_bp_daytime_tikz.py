#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_bp_daytime_tikz.py
===========================
Erzeugt ein eigenstaendiges LaTeX/TikZ-Dokument, das den haeuslichen
Blutdruckverlauf nach *Tageszeit* (Morgen/Mittag/Abend) und *Wochentag*
darstellt:

  * Abbildung 1: gemitteltes Tagesprofil (Median je Tageszeitblock, IQR-Band)
  * Abbildung 2: gruppierte Balken Wochentag x Tageszeit (systolisch + diastolisch)

Zwei Layout-Parameter sind frei einstellbar:

  --style {color,bw}    Farbvariante oder Schwarz-Weiss (Graustufen + Muster:
                        schraffiert / punktiert / gefuellt). BW ist fuer
                        Schwarz-Weiss-Druck optimiert.
  --blocks "a,b"        Grenzen der drei Tageszeitbloecke in Stunden:
                        Morgen < a, Mittag a..b (inkl.), Abend > b.
                        Standard: "10,15"  (Morgen <10, Mittag 10-15, Abend >15)
  --date-from DATE      Optionales Startdatum (inkl.); Messungen davor entfallen.
  --date-to DATE        Optionales Enddatum (inkl.); Messungen danach entfallen.

Das Skript verwendet nur die Python-Standardbibliothek (csv, statistics, ...).

Beispiele
---------
  python3 generate_bp_daytime_tikz.py --csv bp.csv --style color
  python3 generate_bp_daytime_tikz.py --csv bp.csv --style bw --blocks 10,15
  python3 generate_bp_daytime_tikz.py --csv bp.csv --date-from 2026-05-15 \
      --date-to 2026-06-20
  python3 generate_bp_daytime_tikz.py --csv bp.csv --style bw -o bp_bw.tex

Kompilieren:
  pdflatex bp_weekday_daytime.tex   (zweimal nicht noetig; eine Passage genuegt)
"""

import argparse
import csv
import datetime as _dt
import math
import statistics
import sys

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
BLOCK_NAMES = ["Morgen", "Mittag", "Abend"]


# --------------------------------------------------------------------------
# Datenaufbereitung
# --------------------------------------------------------------------------
import re as _re

# Spalten-Aliase (Deutsch/Englisch), analog zum bestehenden BP-Skript
COL_ALIASES = {
    "date":      ["date", "datum", "messdatum", "measurement date", "tag"],
    "time":      ["time", "zeit", "uhrzeit", "messzeit"],
    "systolic":  ["systolic", "systole", "sys", "sbp", "systolisch"],
    "diastolic": ["diastolic", "diastole", "dia", "dbp", "diastolisch"],
    "note":      ["note", "notes", "bemerkung", "notiz", "kommentar"],
}


def _norm_header(s):
    return _re.sub(r"[^a-z0-9]+", "", str(s).strip().lower())


def parse_number(value):
    """Parst Zahlen im englischen oder europaeischen Format (130 / 130,5 / 1.234,56)."""
    if value is None:
        return None
    s = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not s:
        return None
    m = _re.search(r"[-+]?\d[\d.,]*", s)
    if not m:
        return None
    tok = m.group(0)
    if "," in tok and "." in tok:
        if tok.rfind(",") > tok.rfind("."):
            tok = tok.replace(".", "").replace(",", ".")
        else:
            tok = tok.replace(",", "")
    elif "," in tok:
        tok = tok.replace(",", ".")
    try:
        return float(tok)
    except ValueError:
        return None


def _parse_date(s):
    """Parst Datum aus vielen Formaten, auch mit angehaengter Uhrzeit.

    Akzeptiert u. a.: 2026-05-15, 15.05.2026, 15/05/2026, 05/15/2026,
    2026/05/15, '2026-05-15 07:30:00', '15.05.2026 07:30',
    'May 15, 2026', '15 May 2026', '15. Mai 2026' (Monatsname wird ignoriert,
    es zaehlen die Zahlen). Gibt date oder None.
    """
    s = str(s).strip()
    if not s:
        return None
    # Uhrzeit/Zeitzone abtrennen (alles ab erstem 'T' oder Leerzeichen+Ziffer:Ziffer)
    s_date = s.split("T")[0].strip()
    # Falls 'YYYY-MM-DD HH:MM...' oder 'DD.MM.YYYY HH:MM...': Zeitteil entfernen
    m = _re.match(r"^(.*?\d{4}|\d{4}.*?\d{1,2})\b", s_date)
    # Erst strptime mit gaengigen numerischen/Monatsnamen-Formaten versuchen
    fmts = (
        "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
        "%d-%m-%Y", "%m-%d-%Y", "%d %b %Y", "%b %d, %Y", "%d %B %Y", "%B %d, %Y",
        "%Y.%m.%d", "%d.%m.%y", "%m/%d/%y",
    )
    candidate = s_date.split(" ")[0] if _re.match(r"^\d", s_date) else s_date
    for fmt in fmts:
        for cand in (candidate, s_date):
            try:
                return _dt.datetime.strptime(cand.strip(), fmt).date()
            except ValueError:
                continue
    # Letzter Versuch: drei Zahlengruppen heuristisch interpretieren
    nums = _re.findall(r"\d+", s_date)
    if len(nums) >= 3:
        a, b, c = (int(nums[0]), int(nums[1]), int(nums[2]))
        try:
            if a > 31:                      # YYYY M D
                return _dt.date(a, b, c)
            if c > 31:                      # D M YYYY  (oder M D YYYY)
                if a > 12:                  # eindeutig Tag zuerst
                    return _dt.date(c, b, a)
                return _dt.date(c, b, a)    # Default: Tag.Monat.Jahr (DE/EU)
        except ValueError:
            return None
    return None


def _extract_hour(*fields):
    """Stunde (0--23) aus dem ersten Feld, das eine Uhrzeit enthaelt.

    Unterstuetzt 24-Stunden ('07:30', '21:05') und 12-Stunden mit AM/PM
    ('7:30 AM', '9:05 PM'). Felder ohne Uhrzeit (z. B. 'nach Sport') werden
    uebersprungen. Reihenfolge = Prioritaet (Zeit-Spalte, dann Note, dann Date).
    """
    for src in fields:
        if not src:
            continue
        text = str(src)
        m = _re.search(r"(\d{1,2}):(\d{2})\s*([AaPp][Mm])?", text)
        if not m:
            continue
        h = int(m.group(1))
        ampm = m.group(3)
        if ampm:
            ampm = ampm.lower()
            if ampm == "pm" and h != 12:
                h += 12
            elif ampm == "am" and h == 12:
                h = 0
        if 0 <= h <= 23:
            return h
    return None


def read_rows(path):
    """Liest ein Blutdruck-CSV robust ein.

    - Spaltentrenner (Komma/Semikolon/Tab) wird automatisch erkannt.
    - Spaltennamen werden ueber Aliase erkannt (Deutsch/Englisch); zusaetzliche
      Spalten (Pulse, Weight, Note, ...) werden ignoriert.
    - Zahlen mit Dezimalkomma oder -punkt werden korrekt geparst.
    - Die Uhrzeit wird aus einer Time/Zeit-Spalte ODER aus einem Zeitstempel
      im Date-Feld extrahiert.
    """
    raw = open(path, encoding="utf-8-sig", errors="replace").read()
    if not raw.strip():
        sys.exit(f"CSV ist leer: {path}")

    # Delimiter robust erkennen: zuerst anhand der Kopfzeile ausz\u00e4hlen
    # (zuverlaessiger als Sniffer bei Spaltennamen mit Leerzeichen),
    # dann Sniffer als Rueckfall.
    first_line = raw.splitlines()[0] if raw.splitlines() else ""
    counts = {",": first_line.count(","), ";": first_line.count(";"),
              "\t": first_line.count("\t")}
    best = max(counts, key=counts.get)
    if counts[best] > 0:
        class _D(csv.excel):
            delimiter = best
        dialect = _D
    else:
        try:
            dialect = csv.Sniffer().sniff(raw[:4096], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel  # Standard: Komma

    reader = csv.DictReader(raw.splitlines(), dialect=dialect)
    if not reader.fieldnames:
        sys.exit("CSV ohne Kopfzeile / nicht lesbar.")

    norm_to_real = {_norm_header(h): h for h in reader.fieldnames}

    def find(canon, required=True):
        for alias in COL_ALIASES[canon]:
            key = _norm_header(alias)
            if key in norm_to_real:
                return norm_to_real[key]
        if required:
            return None
        return None

    c_sys = find("systolic")
    c_dia = find("diastolic")
    c_date = find("date")
    c_time = find("time", required=False)
    c_note = find("note", required=False)

    missing = [n for n, c in [("Systolic/Systolisch", c_sys),
                              ("Diastolic/Diastolisch", c_dia),
                              ("Date/Datum", c_date)] if c is None]
    if missing:
        sys.exit("Fehlende Pflichtspalten im CSV: " + ", ".join(missing)
                 + f".\nGefundene Spalten: {', '.join(reader.fieldnames)}")

    rows = []
    n_seen = 0
    fail = {"sys": 0, "dia": 0, "date": 0, "hour": 0}
    sample_bad = None

    def all_values(r):
        """Alle Feldwerte einer Zeile, inkl. ueberzaehliger (DictReader: Key None)."""
        vals = []
        for v in r.values():
            if isinstance(v, list):      # ueberzaehlige Felder landen in einer Liste
                vals.extend(v)
            elif v is not None:
                vals.append(v)
        return vals

    for r in reader:
        n_seen += 1
        s = parse_number(r.get(c_sys))
        di = parse_number(r.get(c_dia))

        # Datum: zuerst die zugeordnete Spalte, sonst irgendein Feld der Zeile,
        # das wie ein Datum aussieht (robust gegen verschobene Spalten, wie bei
        # iBP-Exporten, die Datum und Uhrzeit als zwei Komma-Felder ablegen).
        d = _parse_date(r.get(c_date, ""))
        if d is None:
            for v in all_values(r):
                d = _parse_date(v)
                if d is not None:
                    break

        # Uhrzeit: zuerst Zeit-/Note-/Datumsspalte, sonst irgendein Feld mit 'HH:MM'.
        h = _extract_hour(
            r.get(c_time) if c_time else None,
            r.get(c_note) if c_note else None,
            r.get(c_date, ""),
        )
        if h is None:
            h = _extract_hour(*all_values(r))

        if s is None or di is None or d is None or h is None:
            if s is None: fail["sys"] += 1
            if di is None: fail["dia"] += 1
            if d is None: fail["date"] += 1
            if h is None: fail["hour"] += 1
            if sample_bad is None:
                sample_bad = {
                    "Date": r.get(c_date), "Note": r.get(c_note) if c_note else None,
                    "Time": r.get(c_time) if c_time else None,
                    "Systolic": r.get(c_sys), "Diastolic": r.get(c_dia),
                    "parsed": f"date={d}, hour={h}, sys={s}, dia={di}",
                }
            continue
        rows.append((d, h, int(round(s)), int(round(di))))

    if not rows:
        diag = [
            "Keine gueltigen Datenzeilen gefunden.",
            f"  Erkannter Spaltentrenner: {repr(getattr(dialect, 'delimiter', '?'))}",
            f"  Erkannte Spalten: {', '.join(reader.fieldnames or [])}",
            f"  Zugeordnet: Systolic={c_sys!r}, Diastolic={c_dia!r}, "
            f"Date={c_date!r}, Time={c_time!r}, Note={c_note!r}",
            f"  Datenzeilen gelesen: {n_seen}; Fehlschlaege -> "
            f"Systolic:{fail['sys']}, Diastolic:{fail['dia']}, "
            f"Datum:{fail['date']}, Uhrzeit:{fail['hour']}",
        ]
        if sample_bad:
            diag.append("  Erste nicht verarbeitbare Zeile (Auszug):")
            diag.append(f"    Date={sample_bad['Date']!r}  Note={sample_bad['Note']!r}  "
                        f"Time={sample_bad['Time']!r}")
            diag.append(f"    Systolic={sample_bad['Systolic']!r}  "
                        f"Diastolic={sample_bad['Diastolic']!r}")
            diag.append(f"    -> {sample_bad['parsed']}")
        diag.append("  Tipp: Stimmen die Spaltenzuordnung und das Datums-/Uhrzeitformat? "
                    "Bitte ggf. die ersten Zeilen der Datei pruefen.")
        sys.exit("\n".join(diag))
    return rows


def quantile(vals, p):
    """Lineares Quantil (Typ 7), wie in der bisherigen Auswertung."""
    vals = sorted(vals)
    if len(vals) == 1:
        return float(vals[0])
    k = (len(vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(vals[int(k)])
    return vals[f] * (c - k) + vals[c] * (k - f)


def block_of(hour, morning_end, midday_end):
    """Ordnet eine Stunde einem Tageszeitblock zu."""
    if hour < morning_end:
        return "Morgen"
    if hour <= midday_end:
        return "Mittag"
    return "Abend"


def agg_profile(rows, idx, morning_end, midday_end):
    """Median/IQR/n je Tageszeitblock ueber alle Tage. Gibt dict block->(med,q1,q3,n)."""
    out = {}
    for b in BLOCK_NAMES:
        v = [r[idx] for r in rows if block_of(r[1], morning_end, midday_end) == b]
        if v:
            out[b] = (statistics.median(v), quantile(v, .25), quantile(v, .75), len(v))
        else:
            out[b] = None
    return out


def agg_weekday_block(rows, idx, morning_end, midday_end):
    """Median je (Wochentag,Block). Gibt dict (weekday_index,block)->median."""
    out = {}
    for i in range(7):
        for b in BLOCK_NAMES:
            v = [r[idx] for r in rows
                 if r[0].weekday() == i and block_of(r[1], morning_end, midday_end) == b]
            out[(i, b)] = statistics.median(v) if v else None
    return out


def agg_weekday_outliers(rows, idx, morning_end, midday_end, direction="up"):
    """
    Ausreisser je (Wochentag,Block) nach Tukey-Regel:
    unten: Wert < Q1 - 1.5*IQR ; oben: Wert > Q3 + 1.5*IQR.

    Wichtige Absicherungen:
      * Es werden nur Zellen mit n>=4 betrachtet.
      * Bei degeneriertem Interquartilsabstand (IQR sehr klein, z. B. fast alle
        Werte gleich) wird KEIN Ausreisser bestimmt -- sonst entstuenden
        Pseudo-Ausreisser direkt am Median. Schwelle: IQR < 1 mmHg.
      * direction steuert, welche Ausreisser zurueckgegeben werden:
        "up"   -> nur Ausreisser nach oben (Blutdruckspitzen; Standard),
        "both" -> Ausreisser nach oben und unten getrennt.

    Rueckgabe: dict (weekday,block) -> {"hi": [..], "lo": [..]}
    """
    out = {}
    for i in range(7):
        for b in BLOCK_NAMES:
            v = [r[idx] for r in rows
                 if r[0].weekday() == i and block_of(r[1], morning_end, midday_end) == b]
            hi_list, lo_list = [], []
            if direction != "none" and len(v) >= 4:
                q1 = quantile(v, .25)
                q3 = quantile(v, .75)
                iqr = q3 - q1
                if iqr >= 1.0:  # degenerierte Verteilung ausschliessen
                    hi_fence = q3 + 1.5 * iqr
                    lo_fence = q1 - 1.5 * iqr
                    hi_list = sorted({x for x in v if x > hi_fence})
                    if direction == "both":
                        lo_list = sorted({x for x in v if x < lo_fence})
            out[(i, b)] = {"hi": hi_list, "lo": lo_list}
    return out


# --------------------------------------------------------------------------
# Stil-Definitionen
# --------------------------------------------------------------------------
def style_defs(style):
    """
    Liefert ein dict mit TikZ/pgfplots-Stilfragmenten fuer die drei Bloecke
    (Morgen/Mittag/Abend) sowie fuer die zwei Profil-Linien (sys/dia).
    """
    if style == "color":
        return {
            "needs_patterns": False,
            "bar": {
                "Morgen": "fill=blue!55,draw=blue!70!black",
                "Mittag": "fill=teal!55,draw=teal!70!black",
                "Abend":  "fill=orange!75,draw=orange!85!black",
            },
            "band_sys": "blue!12",
            "band_dia": "orange!15",
            "line_sys": "blue!70!black,very thick,mark=*",
            "line_dia": "orange!85!black,very thick,mark=square*",
            "thresh":   "red!60!black",
            "outlier_mark": "draw=red!65!black,thick",
            "corridor": "gray!18",
            "corridor_fill": "fill=gray!18",
        }
    # ---- Schwarz-Weiss: Graustufen + Muster, maximal unterscheidbar ----
    return {
        "needs_patterns": True,
        "bar": {
            # Morgen: solide hellgrau; Mittag: nordost-schraffiert; Abend: punktiert
            "Morgen": "fill=gray!25,draw=black",
            "Mittag": "fill=white,draw=black,postaction={pattern=north east lines}",
            "Abend":  "fill=white,draw=black,postaction={pattern=dots}",
        },
        "band_sys": "gray!30",
        "band_dia": "gray!18",
        "line_sys": "black,very thick,mark=*",
        "line_dia": "black,very thick,densely dashed,mark=square*",
        "thresh":   "black",
        "outlier_mark": "draw=black,thick",
        "corridor": "gray!18",
        # ESC-Korridor in S/W: schraffiert + gestrichelter Rand, damit er sich
        # klar von den flaechig grauen IQR-Baendern unterscheidet.
        "corridor_fill": "pattern=north west lines,pattern color=gray!55,"
                         "draw=gray!60,densely dashed",
    }


# --------------------------------------------------------------------------
# LaTeX-Erzeugung
# --------------------------------------------------------------------------
def fmt(med):
    return f"{med:.0f}"


def build_profile_plot(sys_p, dia_p, st):
    """Abbildung 1: Tagesprofil mit IQR-Baendern + Medianlinien."""
    x = {"Morgen": 1, "Mittag": 2, "Abend": 3}
    # Baender nur fuer vorhandene Bloecke; fehlende ueberspringen.
    def coords(profile, which):
        pts = []
        for b in BLOCK_NAMES:
            if profile[b] is None:
                continue
            med, q1, q3, n = profile[b]
            val = q3 if which == "hi" else (q1 if which == "lo" else med)
            pts.append(f"({x[b]},{val:.0f})")
        return " ".join(pts)

    def med_coords(profile):
        pts, ns = [], []
        for b in BLOCK_NAMES:
            if profile[b] is None:
                continue
            med, q1, q3, n = profile[b]
            pts.append(f"({x[b]},{med:.0f})")
            ns.append((x[b], n))
        return " ".join(pts), ns

    sys_line, sys_ns = med_coords(sys_p)
    dia_line, _ = med_coords(dia_p)

    n_nodes = "\n".join(
        rf"\node[font=\tiny,gray!50!black] at (axis cs:{xi},62){{n={n}}};"
        for xi, n in sys_ns
    )

    return rf"""\begin{{tikzpicture}}
\begin{{axis}}[
    width=0.86\textwidth, height=6.2cm,
    ymin=60, ymax=145, xmin=0.7, xmax=3.3,
    xtick={{1,2,3}}, xticklabels={{Morgen,Mittag,Abend}},
    ylabel={{Blutdruck [mmHg]}},
    ymajorgrids=true, grid style={{gray!25}},
    title={{\footnotesize\bfseries Abb.~1: Gemitteltes Tagesprofil (alle Tage; Band = IQR)}},
    legend style={{at={{(0.5,-0.16)}},anchor=north,legend columns=2,font=\scriptsize,draw=gray!50}},
    legend image post style={{scale=1.5}},
]
\fill[{st['corridor_fill']}] (axis cs:0.7,120) rectangle (axis cs:3.3,129);
\fill[{st['corridor_fill']}] (axis cs:0.7,70) rectangle (axis cs:3.3,79);
\addplot[name path=syshi,draw=none,forget plot] coordinates {{{coords(sys_p,'hi')}}};
\addplot[name path=syslo,draw=none,forget plot] coordinates {{{coords(sys_p,'lo')}}};
\addplot[{st['band_sys']},forget plot] fill between[of=syshi and syslo];
\addplot[name path=diahi,draw=none,forget plot] coordinates {{{coords(dia_p,'hi')}}};
\addplot[name path=dialo,draw=none,forget plot] coordinates {{{coords(dia_p,'lo')}}};
\addplot[{st['band_dia']},forget plot] fill between[of=diahi and dialo];
\addplot[{st['line_sys']}] coordinates {{{sys_line}}};
\addlegendentry{{Systolisch (Median)}}
\addplot[{st['line_dia']}] coordinates {{{dia_line}}};
\addlegendentry{{Diastolisch (Median)}}
\draw[densely dotted,thick,{st['thresh']}] (axis cs:0.7,135) -- (axis cs:3.3,135)
   node[pos=0.9,above,font=\tiny,{st['thresh']}]{{135 syst.}};
\draw[densely dotted,thick,{st['thresh']}] (axis cs:0.7,85) -- (axis cs:3.3,85)
   node[pos=0.9,above,font=\tiny,{st['thresh']}]{{85 diast.}};
{n_nodes}
\end{{axis}}
\end{{tikzpicture}}"""


def agg_hour_counts(rows):
    """Anzahl Messungen je Stunde (0--23). Gibt dict hour->count."""
    counts = {h: 0 for h in range(24)}
    for r in rows:
        counts[r[1]] += 1
    return counts


def build_hour_histogram(rows, st, morning_end, midday_end):
    """Abbildung 1b: Histogramm der Messhaeufigkeit je Stunde.

    Zeigt, zu welchen Tageszeiten tatsaechlich gemessen wird (Messdisziplin /
    Abdeckung der Tageskinetik). Jeder Stundenbalken wird nach seinem
    Tageszeitblock (Morgen/Mittag/Abend) im selben S/W- bzw. Farbstil wie die
    uebrigen Abbildungen eingefaerbt; senkrechte Linien markieren die
    Blockgrenzen. Leere Stunden bleiben sichtbar als Luecke (Wert 0).
    """
    counts = agg_hour_counts(rows)
    ymax = max(counts.values()) if counts else 1
    ymax = ymax + 1  # etwas Luft nach oben

    # Je Block eine eigene Balkenserie, damit Stil (Fuellung/Muster) konsistent
    # mit Abbildung 2 ist. Stunden ohne Messung werden ausgelassen.
    def block_coords(b):
        pts = []
        for h in range(24):
            if block_of(h, morning_end, midday_end) == b and counts[h] > 0:
                pts.append(f"({h},{counts[h]})")
        return " ".join(pts)

    series = []
    block_labels_hist = {
        "Morgen": f"Morgen ($<${morning_end}:00)",
        "Mittag": f"Mittag ({morning_end}--{midday_end})",
        "Abend":  f"Abend ($>${midday_end}:00)",
    }
    for b in BLOCK_NAMES:
        c = block_coords(b)
        if not c:
            continue
        series.append(
            rf"\addplot[ybar,bar width=5pt,bar shift=0pt,{st['bar'][b]}] coordinates {{{c}}};"
            + "\n" + rf"\addlegendentry{{{block_labels_hist[b]}}}"
        )
    series_tex = "\n".join(series)

    # Senkrechte Blockgrenzen (zwischen den Stunden, daher -0.5 versetzt)
    sep = (
        rf"\draw[densely dashed,gray!60] (axis cs:{morning_end-0.5},0) -- "
        rf"(axis cs:{morning_end-0.5},{ymax});" + "\n" +
        rf"\draw[densely dashed,gray!60] (axis cs:{midday_end+0.5},0) -- "
        rf"(axis cs:{midday_end+0.5},{ymax});"
    )

    return rf"""\begin{{tikzpicture}}
\begin{{axis}}[
    width=0.86\textwidth, height=4.2cm,
    ybar, bar width=5pt, bar shift=0pt,
    xmin=-0.6, xmax=23.6, ymin=0, ymax={ymax},
    xtick={{0,2,4,6,8,10,12,14,16,18,20,22}},
    xticklabel style={{font=\scriptsize}},
    yticklabel style={{font=\scriptsize}},
    ytick distance=2,
    xlabel={{\footnotesize Uhrzeit [h]}},
    ylabel={{\footnotesize Messungen}},
    ymajorgrids=true, grid style={{gray!25}},
    title={{\footnotesize\bfseries Abb.~1b: Anzahl Messungen je Stunde}},
    legend style={{at={{(0.5,-0.30)}},anchor=north,legend columns=3,font=\scriptsize,draw=gray!50}},
    legend image post style={{scale=1.2}},
]
{sep}
{series_tex}
\end{{axis}}
\end{{tikzpicture}}"""


def build_weekday_plot(wd, outl, st, metric, ymin, ymax, ylabel, title,
                       block_labels, xlabel=None, thresh=None, corridor=None):
    """Eine gruppierte Balkengrafik (Wochentag x Block) fuer eine Messgroesse.

    wd       : dict (weekday,block)->median  (Balkenhoehe)
    outl     : dict (weekday,block)->Liste Ausreisserwerte (kleine Kreise)
    corridor : (lo,hi) grau hinterlegter ESC-Orientierungskorridor oder None
    """
    def block_coords(b):
        pts = []
        for i in range(7):
            v = wd[(i, b)]
            if v is not None:
                pts.append(f"({WEEKDAYS[i]},{v:.0f})")
        return " ".join(pts)

    # Ausreisser je Block: an derselben x-Kategorie wie der zugehoerige Balken.
    # Damit die Punkte die ybar-Verschiebung der jeweiligen Serie erben, wird
    # je Block ein 'only marks'-Plot in DERSELBEN ybar-Reihenfolge ausgegeben
    # (jeweils direkt nach dem Balken-Plot, mit forget plot).
    def outlier_coords(b, key):
        pts = []
        for i in range(7):
            cell = outl.get((i, b), {})
            for val in cell.get(key, []):
                pts.append(f"({WEEKDAYS[i]},{val:.0f})")
        return " ".join(pts)

    bars = []
    for b in BLOCK_NAMES:
        coords = block_coords(b)
        if not coords:
            continue
        bars.append(
            rf"\addplot+[ybar,{st['bar'][b]}] coordinates {{{coords}}};"
            "\n" rf"\addlegendentry{{{block_labels[b]}}}"
        )
        # Ausreisser derselben Serie (erben den ybar-x-Versatz), nicht in Legende.
        # bar width=0pt + draw/fill=none unterdrueckt den Balken; nur die Marke bleibt.
        oc_hi = outlier_coords(b, "hi")
        if oc_hi:
            bars.append(
                rf"\addplot+[ybar,bar width=0pt,draw=none,fill=none,forget plot,"
                rf"mark=o,mark size=1.6pt,mark options={{{st['outlier_mark']}}}] "
                rf"coordinates {{{oc_hi}}};"
            )
        oc_lo = outlier_coords(b, "lo")
        if oc_lo:
            bars.append(
                rf"\addplot+[ybar,bar width=0pt,draw=none,fill=none,forget plot,"
                rf"mark=x,mark size=2.2pt,mark options={{{st['outlier_mark']}}}] "
                rf"coordinates {{{oc_lo}}};"
            )
    bars_tex = "\n".join(bars)

    thr = ""
    if thresh is not None:
        thr = (rf"\draw[densely dotted,thick,{st['thresh']}] (axis cs:Mo,{thresh}) -- "
               rf"(axis cs:So,{thresh}) node[pos=0.97,above,font=\tiny,{st['thresh']}]{{{thresh}}};")
    # Grau hinterlegter ESC-Orientierungskorridor (hinter den Balken).
    corr = ""
    if corridor is not None:
        clo, chi = corridor
        corr = (rf"\fill[{st['corridor_fill']}] "
                rf"([xshift=-7mm]axis cs:Mo,{clo}) rectangle ([xshift=7mm]axis cs:So,{chi});")
    xlab = rf"xlabel={{{xlabel}}}," if xlabel else ""
    return rf"""\begin{{tikzpicture}}
\begin{{axis}}[
    width=0.92\textwidth, height=5.9cm,
    ybar=1.5pt, bar width=7pt, enlarge x limits=0.08,
    ymin={ymin}, ymax={ymax},
    ylabel={{{ylabel}}}, {xlab}
    symbolic x coords={{Mo,Di,Mi,Do,Fr,Sa,So}}, xtick=data,
    ymajorgrids=true, grid style={{gray!25}},
    axis on top=false,
    legend style={{at={{(0.5,-0.24)}},anchor=north,legend columns=3,font=\scriptsize,draw=gray!50}},
    legend image post style={{scale=1.6}},
    title={{\footnotesize\bfseries {title}}},
]
{corr}
{bars_tex}
{thr}
\end{{axis}}
\end{{tikzpicture}}"""


def build_document(rows, style, morning_end, midday_end, direction="up"):
    st = style_defs(style)
    sys_p = agg_profile(rows, 2, morning_end, midday_end)
    dia_p = agg_profile(rows, 3, morning_end, midday_end)
    wd_sys = agg_weekday_block(rows, 2, morning_end, midday_end)
    wd_dia = agg_weekday_block(rows, 3, morning_end, midday_end)
    ol_sys = agg_weekday_outliers(rows, 2, morning_end, midday_end, direction)
    ol_dia = agg_weekday_outliers(rows, 3, morning_end, midday_end, direction)

    # Kennzahlen fuer den Interpretationstext (vollstaendig aus dem CSV)
    def med_or_dash(p, b):
        return fmt(p[b][0]) if p[b] else "--"
    n_abend = sys_p["Abend"][3] if sys_p["Abend"] else 0
    def _count(d):
        return sum(len(c["hi"]) + len(c["lo"]) for c in d.values())
    n_outliers = _count(ol_sys) + _count(ol_dia)
    n_out_hi = sum(len(c["hi"]) for c in ol_sys.values()) + sum(len(c["hi"]) for c in ol_dia.values())
    n_out_lo = sum(len(c["lo"]) for c in ol_sys.values()) + sum(len(c["lo"]) for c in ol_dia.values())
    n_total = len(rows)
    n_days = len({r[0] for r in rows})
    # Auswertungszeitraum (von--bis) aus den tatsaechlichen Daten
    all_dates = sorted(r[0] for r in rows)
    date_from = all_dates[0].strftime("%d.%m.%Y")
    date_to = all_dates[-1].strftime("%d.%m.%Y")
    if date_from == date_to:
        date_range = date_from
    else:
        date_range = f"{date_from}--{date_to}"

    # Wochentag mit hoechstem/niedrigstem systolischen Median (ueber alle Bloecke)
    wd_day_sys = {}
    for i in range(7):
        vals = [r[2] for r in rows if r[0].weekday() == i]
        if vals:
            wd_day_sys[i] = statistics.median(vals)
    hi_day = max(wd_day_sys, key=wd_day_sys.get) if wd_day_sys else None
    lo_day = min(wd_day_sys, key=wd_day_sys.get) if wd_day_sys else None
    wd_span = ""
    if hi_day is not None and lo_day is not None and hi_day != lo_day:
        wd_span = (f" Der wochentagsbezogene systolische Median schwankt zwischen "
                   f"{wd_day_sys[lo_day]:.0f}\\,mmHg ({WEEKDAYS[lo_day]}) und "
                   f"{wd_day_sys[hi_day]:.0f}\\,mmHg ({WEEKDAYS[hi_day]}).")

    # Tagesgang-Beschreibung (Morgen vs. Abend systolisch)
    trend = ""
    if sys_p["Morgen"] and sys_p["Abend"]:
        d = sys_p["Abend"][0] - sys_p["Morgen"][0]
        if abs(d) < 3:
            trend = " Der Tagesgang ist nach aktueller Datenlage flach."
        elif d > 0:
            trend = (f" Tendenziell liegt der Abendwert systolisch ueber dem Morgenwert "
                     f"(Differenz ca.\\ {d:.0f}\\,mmHg).")
        else:
            trend = (f" Tendenziell liegt der Morgenwert systolisch ueber dem Abendwert "
                     f"(Differenz ca.\\ {abs(d):.0f}\\,mmHg).")

    patterns_lib = r"\usetikzlibrary{patterns}" if st["needs_patterns"] else ""

    # Messverteilung je Block (fuer Interpretationshinweis zum Histogramm)
    block_counts = {b: 0 for b in BLOCK_NAMES}
    for r in rows:
        block_counts[block_of(r[1], morning_end, midday_end)] += 1
    block_label_de = {"Morgen": "morgens", "Mittag": "mittags", "Abend": "abends"}
    # Schwaechster Block (zur dynamischen Datenlage-Aussage); nur Bloecke mit Messungen
    present = {b: c for b, c in block_counts.items() if c > 0}
    weakest = min(present, key=present.get) if present else None
    n_total_blocks = sum(block_counts.values())
    # "Dünn besetzt" nur, wenn der schwaechste Block deutlich unter dem
    # Durchschnitt liegt (< 60 % des Mittels der besetzten Bloecke).
    avg = (n_total_blocks / len(present)) if present else 0
    weak_is_thin = weakest is not None and block_counts[weakest] < 0.6 * avg

    if weakest is not None and weak_is_thin:
        cov = (f" Die Messungen verteilen sich auf {block_counts['Morgen']} morgens, "
               f"{block_counts['Mittag']} mittags und {block_counts['Abend']} abends "
               rf"(siehe Abb.~1b); der {block_label_de[weakest]} d\"unner besetzte Block "
               f"({weakest}, n={block_counts[weakest]}) gewinnt mit weiteren Messungen an "
               f"Aussagekraft.")
        datenlage = (rf"Sofern einzelne Tageszeitbl\"ocke -- aktuell vor allem {block_label_de[weakest]} "
                     rf"(n={block_counts[weakest]}) -- noch d\"unner besetzt sind, werden mit "
                     rf"regelm\"a\ss{{}}igen Messungen morgens, mittags \emph{{und}} abends "
                     rf"(ggf.\ auch dazwischen) alle Bl\"ocke belastbarer und ein etwaiger Tagesgang "
                     rf"-- relevant f\"ur Einnahmezeitpunkt und Dosierung der Medikation -- "
                     rf"statistisch besser beurteilbar.")
        abend_belastbar = rf"Aussagen zum {weakest} sind erst bei ausreichender Messzahl belastbar."
    else:
        cov = (f" Die Messungen verteilen sich auf {block_counts['Morgen']} morgens, "
               f"{block_counts['Mittag']} mittags und {block_counts['Abend']} abends "
               rf"(siehe Abb.~1b) und decken den Tagesverlauf inzwischen gleichm\"a\ss{{}}ig ab.")
        datenlage = (rf"Die drei Tageszeitbl\"ocke sind ausreichend besetzt; mit fortlaufenden "
                     rf"Messungen morgens, mittags \emph{{und}} abends bleibt ein etwaiger Tagesgang "
                     rf"-- relevant f\"ur Einnahmezeitpunkt und Dosierung der Medikation -- "
                     rf"zuverl\"assig beurteilbar.")
        abend_belastbar = ""

    block_desc = (f"Morgen ($<${morning_end}:00), Mittag ({morning_end}:00--{midday_end}:00), "
                  f"Abend ($>${midday_end}:00)")
    # Dynamische Block-Labels fuer Legenden (passen sich den Zeitfenstern an)
    block_labels = {
        "Morgen": f"Morgen ($<${morning_end}:00)",
        "Mittag": f"Mittag ({morning_end}--{midday_end})",
        "Abend":  f"Abend ($>${midday_end}:00)",
    }

    profile_tex = build_profile_plot(sys_p, dia_p, st)
    hist_tex = build_hour_histogram(rows, st, morning_end, midday_end)
    wd_sys_tex = build_weekday_plot(
        wd_sys, ol_sys, st, "sys", 110, 146, "Systolisch [mmHg]",
        "Abb.~2a: Systolischer Median je Wochentag und Tageszeit",
        block_labels, thresh=135, corridor=(120, 129))
    wd_dia_tex = build_weekday_plot(
        wd_dia, ol_dia, st, "dia", 60, 92, "Diastolisch [mmHg]",
        "Abb.~2b: Diastolischer Median je Wochentag und Tageszeit",
        block_labels, xlabel="Wochentag", thresh=85, corridor=(70, 79))

    style_note = ("Farbkodiert" if style == "color"
                  else "Schwarz-Wei\\ss{} (Graustufen und Muster: solide / schraffiert / punktiert)")

    return rf"""\documentclass[11pt]{{article}}
\usepackage[ngerman]{{babel}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{tikz}}
\usepackage{{pgfplots}}
\pgfplotsset{{compat=1.18}}
\usepgfplotslibrary{{fillbetween}}
{patterns_lib}
\usepackage[a4paper,margin=18mm]{{geometry}}
\pagestyle{{empty}}

\begin{{document}}
\begin{{center}}
{{\large\bfseries Tageszeit- und wochentagsabh\"angiger Blutdruckverlauf}}\\[2pt]
{{\footnotesize\bfseries Auswertungszeitraum: {date_range} \quad ({n_total} Messungen an {n_days} Tagen)}}\\[2pt]
{{\footnotesize H\"ausliche Messungen, aggregiert nach Tageszeit ({block_desc}) und Wochentag. Layout: {style_note}.}}
\end{{center}}
\vspace{{1mm}}

\noindent\fbox{{\parbox{{\dimexpr\textwidth-2\fboxsep-2\fboxrule\relax}}{{\footnotesize
\textbf{{Methodik und Lesehilfe.}} Grundlage sind die h\"auslichen Blutdruckmessungen ({n_total} Messungen an {n_days} Tagen), eingeteilt in drei Tageszeitbl\"ocke: \emph{{Morgen}} ($<${morning_end}:00), \emph{{Mittag}} ({morning_end}:00--{midday_end}:00) und \emph{{Abend}} ($>${midday_end}:00). Alle Balken und Linien sind \emph{{median}}-basiert\footnotemark[1], schattierte B\"ander bzw.\ die grau hinterlegten Korridore dienen der Streuungs- und Vergleichsdarstellung. Abbildung~1 zeigt das gemittelte \emph{{Tagesprofil}} (Median je Block; schattiert der Interquartilsbereich, 25.--75.\ Perzentil). Abbildung~2 schl\"usselt die Mediane nach Wochentag auf; kleine Kreise markieren \emph{{Ausrei\ss{{}}er}}\footnotemark[2]. Die Zahl \texttt{{n}} nennt die Anzahl der Messungen. Die punktierten Linien markieren die h\"auslichen Vergleichsschwellen 135\,mmHg systolisch bzw.\ 85\,mmHg diastolisch; die \textbf{{grau hinterlegten Korridore}} (120--129\,mmHg systolisch, 70--79\,mmHg diastolisch) sind allgemeine ESC-Orientierungsbereiche unter Therapie bei individueller Vertr\"aglichkeit und keine aneurysmaspezifischen Zielwerte. \textbf{{Hinweis zur Datenlage:}} {datenlage} Die Darstellung ersetzt keine \"arztliche Zielwertfestlegung.}}}}
\footnotetext[1]{{Der Median (50.\ Perzentil) wird gegen\"uber dem arithmetischen Mittel verwendet, weil er unempfindlich gegen einzelne Extremwerte ist und so kurzfristige Verzerrungen -- etwa durch eine einzelne Messung nach k\"orperlicher Belastung -- auff\"angt; die typische Lage der Werte wird dadurch realistischer abgebildet.}}
\footnotetext[2]{{Ausrei\ss{{}}er nach der Tukey-Regel: ein Wert gilt als Ausrei\ss{{}}er, wenn er oberhalb von $Q_3+1{{,}}5\cdot\mathrm{{IQR}}$ (nach oben) oder unterhalb von $Q_1-1{{,}}5\cdot\mathrm{{IQR}}$ (nach unten) liegt, wobei $Q_1$ und $Q_3$ das 25.\ bzw.\ 75.\ Perzentil und $\mathrm{{IQR}}=Q_3-Q_1$ den Interquartilsabstand bezeichnen. Ausrei\ss{{}}er liegen damit definitionsgem\"a\ss{{}} \emph{{au\ss{{}}erhalb}} des mittleren Wertebereichs. Sie werden nur bestimmt, wenn je Zelle mindestens vier Messungen vorliegen und der Interquartilsabstand nicht entartet ist ($\mathrm{{IQR}}\geq 1$\,mmHg); andernfalls w\"urden bei nahezu identischen Werten Pseudo-Ausrei\ss{{}}er direkt am Median entstehen.}}
\vspace{{4mm}}

\begin{{center}}
{profile_tex}\\[1mm]
{{\footnotesize Abbildung~1: Punkte = Median je Tageszeitblock, schattierte B\"ander = Interquartilsbereich.}}
\end{{center}}
\vspace{{3mm}}

\begin{{center}}
{hist_tex}\\[1mm]
{{\footnotesize Abbildung~1b: Anzahl der Messungen je Stunde, eingef\"arbt nach Tageszeitblock. Zeigt die Messverteilung \"uber den Tag (Abdeckung der Tageskinetik); senkrechte Linien markieren die Blockgrenzen.}}
\end{{center}}
\vspace{{5mm}}

\begin{{center}}
{wd_sys_tex}\\[3mm]
{wd_dia_tex}\\[1mm]
{{\footnotesize Abbildung~2: Mediane je Wochentag und Tageszeitblock (Balken). \emph{{Ausrei\ss{{}}er}} nach der Tukey-Regel liegen \emph{{au\ss{{}}erhalb}} der Balken: Kreise ($\circ$) markieren Ausrei\ss{{}}er nach oben (Blutdruckspitzen), das Kreuz ($\times$) Ausrei\ss{{}}er nach unten. Sie werden nur bei mindestens vier Messungen je Zelle und ausreichender Streuung bestimmt. Nicht besetzte Bl\"ocke werden ausgelassen.}}
\end{{center}}
\vspace{{3mm}}

\noindent{{\footnotesize\textbf{{Interpretationshinweis (automatisch aus den aktuellen Daten).}} Grundlage: {n_total} Messungen an {n_days} Tagen im Zeitraum {date_range}. Systolischer Median morgens ca.\ {med_or_dash(sys_p,'Morgen')}\,mmHg, mittags ca.\ {med_or_dash(sys_p,'Mittag')}\,mmHg, abends ca.\ {med_or_dash(sys_p,'Abend')}\,mmHg (Abend: n={n_abend}); diastolisch morgens ca.\ {med_or_dash(dia_p,'Morgen')}\,mmHg, mittags ca.\ {med_or_dash(dia_p,'Mittag')}\,mmHg, abends ca.\ {med_or_dash(dia_p,'Abend')}\,mmHg.{trend}{wd_span} Insgesamt wurden {n_outliers} Tukey-Ausrei\ss{{}}er markiert ({n_out_hi} nach oben, {n_out_lo} nach unten).{cov} {abend_belastbar} Mit regelm\"a\ss{{}}iger Drei-Punkt-Messung wird insbesondere ein morgendlicher Blutdruckanstieg oder ein abendlicher Wiederanstieg sichtbar -- beides kann f\"ur Einnahmezeitpunkt und Dosierung der Antihypertensiva bedeutsam sein. Die Entscheidung trifft die behandelnde \"Arztin oder der behandelnde Arzt.}}
\end{{document}}
"""


def main():
    ap = argparse.ArgumentParser(
        description="Erzeugt das LaTeX/TikZ-Diagramm 'Tageszeit x Wochentag' "
                    "aus einem Blutdruck-CSV; umschaltbar zwischen Farbe und Schwarz-Weiss.")
    ap.add_argument("--csv", default="bp.csv",
                    help="Pfad zur CSV-Datei. Spaltentrenner (Komma/Semikolon/Tab) und "
                         "Dezimalkomma werden automatisch erkannt; benoetigt Datum, Uhrzeit "
                         "(eigene Spalte oder im Datumsfeld) sowie systolisch/diastolisch. "
                         "Zusatzspalten werden ignoriert. Standard: bp.csv")
    ap.add_argument("--style", choices=["color", "bw"], default="color",
                    help="Layout: 'color' (Farbe) oder 'bw' (Schwarz-Weiss, Graustufen+Muster). Standard: color")
    ap.add_argument("--blocks", default="10,15",
                    help="Blockgrenzen in Stunden 'morning_end,midday_end': "
                         "Morgen<a, Mittag a..b, Abend>b. Standard: 10,15")
    ap.add_argument("--outliers", choices=["up", "both", "none"], default="up",
                    help="Ausreisser: 'up' nur nach oben (Kreise; Standard, fuer Blutdruck "
                         "meist relevant), 'both' zusaetzlich nach unten (Kreuz x), "
                         "'none' keine. ")
    ap.add_argument("--date-from", default=None,
                    help="Startdatum der Auswertung (inklusive). Messungen davor "
                         "werden ignoriert. Formate wie bei den Daten, z. B. "
                         "2026-05-15 oder 15.05.2026. Standard: alle ab Beginn.")
    ap.add_argument("--date-to", default=None,
                    help="Enddatum der Auswertung (inklusive). Messungen danach "
                         "werden ignoriert. Ohne Angabe werden alle Messungen "
                         "ab --date-from verwendet.")
    ap.add_argument("-o", "--out", default="bp_weekday_daytime.tex",
                    help="Ausgabedatei (.tex). Standard: bp_weekday_daytime.tex")
    args = ap.parse_args()

    try:
        a, b = (int(x) for x in args.blocks.split(","))
    except ValueError:
        sys.exit("--blocks erwartet zwei ganze Zahlen, z. B. --blocks 10,15")
    if not (0 < a <= b < 24):
        sys.exit("--blocks: es muss 0 < morning_end <= midday_end < 24 gelten.")

    # Datumsgrenzen parsen (gleiche Formate wie die CSV-Daten)
    d_from = d_to = None
    if args.date_from:
        d_from = _parse_date(args.date_from)
        if d_from is None:
            sys.exit(f"--date-from: Datum nicht erkannt: {args.date_from!r}")
    if args.date_to:
        d_to = _parse_date(args.date_to)
        if d_to is None:
            sys.exit(f"--date-to: Datum nicht erkannt: {args.date_to!r}")
    if d_from and d_to and d_from > d_to:
        sys.exit("--date-from darf nicht nach --date-to liegen.")

    rows = read_rows(args.csv)
    n_all = len(rows)
    if d_from is not None:
        rows = [r for r in rows if r[0] >= d_from]
    if d_to is not None:
        rows = [r for r in rows if r[0] <= d_to]
    if not rows:
        span = []
        if d_from: span.append(f"ab {d_from.strftime('%d.%m.%Y')}")
        if d_to: span.append(f"bis {d_to.strftime('%d.%m.%Y')}")
        sys.exit("Keine Messungen im gewaehlten Zeitraum (" + " ".join(span)
                 + f"). Eingelesen wurden {n_all} Messungen ueber den gesamten Datensatz.")

    tex = build_document(rows, args.style, a, b, args.outliers)
    with open(args.out, "w") as f:
        f.write(tex)
    span_txt = ""
    if d_from or d_to:
        span_txt = (f", Zeitraum={(d_from.strftime('%d.%m.%Y') if d_from else 'Anfang')}"
                    f"--{(d_to.strftime('%d.%m.%Y') if d_to else 'Ende')}"
                    f" ({len(rows)} von {n_all} Messungen)")
    print(f"[ok] {args.out} erzeugt  (style={args.style}, blocks=Morgen<{a}, Mittag {a}-{b}, "
          f"Abend>{b}, outliers={args.outliers}, {len(rows)} Messungen{span_txt})")
    print(f"     Kompilieren:  pdflatex {args.out}")


if __name__ == "__main__":
    main()
