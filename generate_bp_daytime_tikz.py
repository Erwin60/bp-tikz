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
  * Statistik-Seite: Blutdruck-Kennzahlentabelle (immer) sowie optional
    Abbildung 3 (--pulse): Puls-Tagesprofil + Kennzahlenbox

Zwei Layout-Parameter sind frei einstellbar:

  --style {color,bw}    Farbvariante oder Schwarz-Weiss (Graustufen + Muster:
                        schraffiert / punktiert / gefuellt). BW ist fuer
                        Schwarz-Weiss-Druck optimiert.
  --blocks "a,b"        Grenzen der drei Tageszeitbloecke in Stunden:
                        Morgen < a, Mittag a..b (inkl.), Abend > b.
                        Standard: "10,15"  (Morgen <10, Mittag 10-15, Abend >15)
  --date-from DATE      Optionales Startdatum (inkl.); Messungen davor entfallen.
  --date-to DATE        Optionales Enddatum (inkl.); Messungen danach entfallen.
  --pulse               Zusaetzliche Puls-Auswertung (Abb. 3 + Kennzahlenbox).
  --pulse-low N         Bradykardie-Schwelle in 1/min (Standard 50).
  --fences              Obere Tukey-Grenze (Q3+1,5*IQR) je Saeule als kurzen
                        waagrechten Strich zeichnen.

Das Skript verwendet nur die Python-Standardbibliothek (csv, statistics, ...).

Beispiele
---------
  python3 generate_bp_daytime_tikz.py --csv bp.csv --style color
  python3 generate_bp_daytime_tikz.py --csv bp.csv --style bw --blocks 10,15
  python3 generate_bp_daytime_tikz.py --csv bp.csv --date-from 2026-05-15 \
      --date-to 2026-06-20
  python3 generate_bp_daytime_tikz.py --csv bp.csv --style bw -o bp_bw.tex
  python3 generate_bp_daytime_tikz.py --csv bp.csv --pulse --pulse-low 48 --fences

Kompilieren:
  pdflatex bp_weekday_daytime.tex   (zweimal nicht noetig; eine Passage genuegt)
"""

import argparse
import csv
import datetime as _dt
import math
import statistics
import sys
from decimal import Decimal, ROUND_HALF_UP

WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
BLOCK_NAMES = ["Morgen", "Mittag", "Abend"]


# --------------------------------------------------------------------------
# Datenaufbereitung
# --------------------------------------------------------------------------
import re as _re
from pathlib import Path as _Path

# Spalten-Aliase (Deutsch/Englisch), analog zum bestehenden BP-Skript
COL_ALIASES = {
    "date":      ["date", "datum", "messdatum", "measurement date", "tag"],
    "time":      ["time", "zeit", "uhrzeit", "messzeit"],
    "systolic":  ["systolic", "systole", "sys", "sbp", "systolisch"],
    "diastolic": ["diastolic", "diastole", "dia", "dbp", "diastolisch"],
    "note":      ["note", "notes", "bemerkung", "notiz", "kommentar"],
    "pulse":     ["pulse", "puls", "heart rate", "hr", "bpm", "herzfrequenz", "hf"],
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


def streamline_ibp(raw):
    """Normalisiert das iBP-Export-CSV in ein kanonisches Format.

    Die iBP-App exportiert eine Kopfzeile mit acht Spalten
    (Systolic,Diastolic,Pulse,Weight,Mean Arterial Pressure,Pulse Pressure,
    Date,Note), legt aber Datum UND Uhrzeit als ZWEI komma-getrennte Felder im
    Date-Bereich ab (z. B. ``05.07.26, 20:23``). Dadurch hat jede Datenzeile ein
    Feld mehr als die Kopfzeile, die Uhrzeit rutscht in die Note-Spalte und die
    eigentliche Notiz in ein ueberzaehliges Feld.

    Diese Funktion erkennt dieses Format eindeutig und schreibt es in ein
    sauberes, semikolongetrenntes CSV mit den Spalten
    ``Datum;Zeit;Systolisch;Diastolisch;Puls;note`` um, das anschliessend wie
    ein normales (z. B. aus Excel exportiertes) CSV verarbeitet werden kann.
    Nicht-iBP-Dateien werden unveraendert zurueckgegeben.
    """
    lines = [l for l in raw.splitlines() if l.strip() != ""]
    if not lines:
        return raw
    header = lines[0]
    hl = header.lower()
    # Eindeutige iBP-Signatur: die beiden iBP-spezifischen Spalten sind vorhanden
    # und die Datenzeilen tragen (durch das komma-getrennte Datum/Uhrzeit) ein
    # Feld mehr als die Kopfzeile.
    is_ibp = (
        "mean arterial pressure" in hl
        and "pulse pressure" in hl
        and header.count(",") >= 6
    )
    if not is_ibp:
        return raw
    n_head = header.count(",") + 1

    out = ["Datum;Zeit;Systolisch;Diastolisch;Puls;note"]
    reader = csv.reader(lines[1:])
    for fields in reader:
        if not fields or all(f.strip() == "" for f in fields):
            continue
        # Bei iBP hat die Zeile ein Feld mehr als die Kopfzeile: Systolic,
        # Diastolic, Pulse, Weight, MAP, PP, Date, Time, Note.
        # Wir greifen die benoetigten Werte positionsbasiert ab; ueberzaehlige
        # (Note kann selbst Kommas enthalten) werden am Ende zusammengefasst.
        if len(fields) < n_head:
            continue
        try:
            sys_v = fields[0].strip()
            dia_v = fields[1].strip()
            pulse_v = fields[2].strip()
            # Date und Time liegen an Position 6 und 7 (0-basiert), Note ab 8.
            date_v = fields[6].strip()
            time_v = fields[7].strip()
            note_v = ",".join(fields[8:]).strip() if len(fields) > 8 else ""
        except IndexError:
            continue
        # Semikolons in der Notiz maskieren wir simpel, um das Zielformat nicht
        # zu zerstoeren.
        note_v = note_v.replace(";", ",")
        out.append(f"{date_v};{time_v};{sys_v};{dia_v};{pulse_v};{note_v}")
    return "\n".join(out) + "\n"


def read_rows(path):
    """Liest ein Blutdruck-CSV robust ein.

    - Spaltentrenner (Komma/Semikolon/Tab) wird automatisch erkannt.
    - Spaltennamen werden ueber Aliase erkannt (Deutsch/Englisch); zusaetzliche
      Spalten (Weight, ...) werden ignoriert.
    - Zahlen mit Dezimalkomma oder -punkt werden korrekt geparst.
    - Die Uhrzeit wird aus einer Time/Zeit-Spalte ODER aus einem Zeitstempel
      im Date-Feld extrahiert.
    - Der Puls (falls vorhanden) wird als 5. Tupelelement zurueckgegeben; fehlt
      er, ist der Wert None.

    Rueckgabe: Liste von (date, hour, sys, dia, pulse_or_None).
    """
    raw = open(path, encoding="utf-8-sig", errors="replace").read()
    if not raw.strip():
        sys.exit(f"CSV ist leer: {path}")

    # iBP-Export zuerst in ein kanonisches CSV normalisieren; andere Formate
    # (z. B. aus Excel) bleiben unveraendert.
    raw = streamline_ibp(raw)

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
    c_pulse = find("pulse", required=False)

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
        pu = parse_number(r.get(c_pulse)) if c_pulse else None

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
        pulse_val = int(round(pu)) if (pu is not None and pu > 0) else None
        rows.append((d, h, int(round(s)), int(round(di)), pulse_val))

    if not rows:
        diag = [
            "Keine gueltigen Datenzeilen gefunden.",
            f"  Erkannter Spaltentrenner: {repr(getattr(dialect, 'delimiter', '?'))}",
            f"  Erkannte Spalten: {', '.join(reader.fieldnames or [])}",
            f"  Zugeordnet: Systolic={c_sys!r}, Diastolic={c_dia!r}, "
            f"Date={c_date!r}, Time={c_time!r}, Note={c_note!r}, Pulse={c_pulse!r}",
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


def round_half_up(value):
    """Kaufmaennische Rundung auf ganze Zahlen fuer die Anzeige.

    Pythons format(".0f") verwendet Banker's Rounding und wuerde z. B. 126.5
    auf 126 abrunden. Fuer die Kennzahlentabellen ist die kaufmaennische
    Rundung (126.5 -> 127) erwartungskonform. Die Rundung betrifft nur die
    Darstellung; alle Berechnungen und Diagrammkoordinaten arbeiten
    unveraendert mit den exakten Gleitkommawerten.
    """
    return int(Decimal(repr(float(value))).quantize(Decimal("1"),
                                                    rounding=ROUND_HALF_UP))


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


def agg_pulse_profile(rows, morning_end, midday_end):
    """Wie agg_profile, aber fuer den Puls (Index 4) und ohne fehlende Werte."""
    out = {}
    for b in BLOCK_NAMES:
        v = [r[4] for r in rows
             if r[4] is not None and block_of(r[1], morning_end, midday_end) == b]
        if v:
            out[b] = (statistics.median(v), quantile(v, .25), quantile(v, .75), len(v))
        else:
            out[b] = None
    return out


def pulse_stats(rows, morning_end, midday_end, low_thr):
    """Kennzahlen zum Puls insgesamt und je Tageszeitblock.

    Rueckgabe: dict mit 'overall' und je Block (Median, Q1, Q3, Min, Max, n,
    n_low = Anzahl Werte unter der Bradykardie-Schwelle low_thr).
    """
    def _stats(vals):
        if not vals:
            return None
        return {
            "med": statistics.median(vals),
            "q1": quantile(vals, .25),
            "q3": quantile(vals, .75),
            "min": min(vals),
            "max": max(vals),
            "n": len(vals),
            "n_low": sum(1 for x in vals if x < low_thr),
        }
    allv = [r[4] for r in rows if r[4] is not None]
    out = {"overall": _stats(allv)}
    for b in BLOCK_NAMES:
        vb = [r[4] for r in rows
              if r[4] is not None and block_of(r[1], morning_end, midday_end) == b]
        out[b] = _stats(vb)
    return out


def bp_block_stats(rows, idx, morning_end, midday_end, hi_thr, corridor=None):
    """Kennzahlen zu Blutdruck (systolisch idx=2 / diastolisch idx=3) insgesamt
    und je Tageszeitblock; zaehlt Werte oberhalb der Vergleichsschwelle hi_thr
    und -- falls corridor=(lo,hi) angegeben -- Werte innerhalb des Zielkorridors.

    Rueckgabe: dict mit 'overall' und je Block (med, q1, q3, min, max, n,
    n_hi = Anzahl Werte >= hi_thr, n_in = Anzahl Werte im Korridor [lo,hi]).
    """
    def _stats(vals):
        if not vals:
            return None
        n_in = None
        if corridor is not None:
            lo, hi = corridor
            n_in = sum(1 for x in vals if lo <= x <= hi)
        return {
            "med": statistics.median(vals),
            "q1": quantile(vals, .25),
            "q3": quantile(vals, .75),
            "min": min(vals),
            "max": max(vals),
            "n": len(vals),
            "n_hi": sum(1 for x in vals if x >= hi_thr),
            "n_in": n_in,
        }
    allv = [r[idx] for r in rows]
    out = {"overall": _stats(allv)}
    for b in BLOCK_NAMES:
        vb = [r[idx] for r in rows
              if block_of(r[1], morning_end, midday_end) == b]
        out[b] = _stats(vb)
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

    Rueckgabe: dict (weekday,block) -> {"hi": [..], "lo": [..],
               "hi_fence": float|None, "lo_fence": float|None}
    (Die Zaeune werden zusaetzlich zurueckgegeben, damit die Tukey-Grenzen
    optional sichtbar gemacht werden koennen.)
    """
    out = {}
    for i in range(7):
        for b in BLOCK_NAMES:
            v = [r[idx] for r in rows
                 if r[0].weekday() == i and block_of(r[1], morning_end, midday_end) == b]
            hi_list, lo_list = [], []
            hi_fence = lo_fence = None
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
            out[(i, b)] = {"hi": hi_list, "lo": lo_list,
                           "hi_fence": hi_fence, "lo_fence": lo_fence}
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
            "pulse_line": "violet!70!black,very thick,mark=triangle*",
            "pulse_band": "violet!12",
            "fence": "red!55!black",
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
        "pulse_line": "black,very thick,densely dotted,mark=triangle*",
        "pulse_band": "gray!22",
        "fence": "black",
    }


# --------------------------------------------------------------------------
# LaTeX-Erzeugung
# --------------------------------------------------------------------------
def fmt(med):
    """Anzeigeformat fuer Mediane im Fliesstext (kaufmaennisch gerundet)."""
    return f"{round_half_up(med)}"


def build_profile_plot(sys_p, dia_p, st):
    """Abbildung 1: Tagesprofil mit IQR-Baendern + Medianlinien."""
    x = {"Morgen": 1, "Mittag": 2, "Abend": 3}
    # Visible marker when a custom (e.g. aneurysm) corridor is in use.
    if st.get("corridor_is_custom"):
        cs_lo, cs_hi = f"{st['corridor_sys'][0]:g}", f"{st['corridor_sys'][1]:g}"
        cd_lo, cd_hi = f"{st['corridor_dia'][0]:g}", f"{st['corridor_dia'][1]:g}"
        # Relative to the axis' top edge so it scales with the y-range and
        # stays just inside the top-right corner regardless of data values.
        corridor_annotation = (
            rf"\node[anchor=north east,font=\scriptsize\bfseries,fill=white,"
            rf"fill opacity=0.75,text opacity=1,inner sep=1.5pt] "
            rf"at ([yshift=1pt]rel axis cs:0.99,1.0) "
            rf"{{Individueller Zielkorridor {cs_lo}--{cs_hi}/{cd_lo}--{cd_hi}\,mmHg}};"
        )
    else:
        corridor_annotation = ""
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
\fill[{st['corridor_fill']}] (axis cs:0.7,{st['corridor_sys'][0]}) rectangle (axis cs:3.3,{st['corridor_sys'][1]});
\fill[{st['corridor_fill']}] (axis cs:0.7,{st['corridor_dia'][0]}) rectangle (axis cs:3.3,{st['corridor_dia'][1]});
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
{corridor_annotation}
{n_nodes}
\end{{axis}}
\end{{tikzpicture}}"""


def build_pulse_plot(pu_p, st, low_thr):
    """Abbildung 3: Puls-Tagesprofil (Median je Block, IQR-Band) mit Schwelle."""
    x = {"Morgen": 1, "Mittag": 2, "Abend": 3}

    def coords(which):
        pts = []
        for b in BLOCK_NAMES:
            if pu_p[b] is None:
                continue
            med, q1, q3, n = pu_p[b]
            val = q3 if which == "hi" else (q1 if which == "lo" else med)
            pts.append(f"({x[b]},{val:.0f})")
        return " ".join(pts)

    med_pts, ns, allvals = [], [], []
    for b in BLOCK_NAMES:
        if pu_p[b] is None:
            continue
        med, q1, q3, n = pu_p[b]
        med_pts.append(f"({x[b]},{med:.0f})")
        ns.append((x[b], n))
        allvals += [q1, q3, med]
    med_line = " ".join(med_pts)
    ymin = min(35, (min(allvals) - 8) if allvals else 40, low_thr - 5)
    ymax = max((max(allvals) + 8) if allvals else 90, 90)
    n_nodes = "\n".join(
        rf"\node[font=\tiny,gray!50!black] at (axis cs:{xi},{ymin+3:.0f}){{n={n}}};"
        for xi, n in ns
    )
    return rf"""\begin{{tikzpicture}}
\begin{{axis}}[
    width=0.86\textwidth, height=5.2cm,
    ymin={ymin:.0f}, ymax={ymax:.0f}, xmin=0.7, xmax=3.3,
    xtick={{1,2,3}}, xticklabels={{Morgen,Mittag,Abend}},
    ylabel={{Puls [1/min]}},
    ymajorgrids=true, grid style={{gray!25}},
    title={{\footnotesize\bfseries Abb.~3: Puls-Tagesprofil (alle Tage; Band = IQR)}},
    legend style={{at={{(0.5,-0.18)}},anchor=north,legend columns=2,font=\scriptsize,draw=gray!50}},
    legend image post style={{scale=1.5}},
]
\addplot[name path=puhi,draw=none,forget plot] coordinates {{{coords('hi')}}};
\addplot[name path=pulo,draw=none,forget plot] coordinates {{{coords('lo')}}};
\addplot[{st['pulse_band']},forget plot] fill between[of=puhi and pulo];
\addplot[{st['pulse_line']}] coordinates {{{med_line}}};
\addlegendentry{{Puls (Median)}}
\draw[densely dotted,thick,{st['thresh']}] (axis cs:0.7,{low_thr:g}) -- (axis cs:3.3,{low_thr:g})
   node[pos=0.9,above,font=\tiny,{st['thresh']}]{{{low_thr:g}/min}};
{n_nodes}
\end{{axis}}
\end{{tikzpicture}}"""


def build_pulse_box(ps, low_thr, date_range, n_days):
    """Kompakte Kennzahlenbox zum Puls (gesamt + je Tageszeitblock).

    date_range/n_days werden im Kommentar genannt, damit auch auf dieser neuen
    Seite der ausgewertete Zeitraum eindeutig ist (analog zu den BP-Diagrammen).
    """
    def fmt_cell(s):
        if s is None:
            return "-- & -- & -- & -- & --"
        return (f"{round_half_up(s['med'])} & "
                f"{round_half_up(s['q1'])}--{round_half_up(s['q3'])} & "
                f"{round_half_up(s['min'])}--{round_half_up(s['max'])} & "
                f"{s['n']} & {s['n_low']}")
    rows_tex = []
    for label, key in [("Gesamt", "overall"), ("Morgen", "Morgen"),
                       ("Mittag", "Mittag"), ("Abend", "Abend")]:
        rows_tex.append(rf"{label} & {fmt_cell(ps[key])} \\")
    body = "\n".join(rows_tex)
    ov = ps["overall"]
    n_pulse = ov["n"] if ov else 0
    n_low_total = ov["n_low"] if ov else 0
    low_note = ""
    if n_low_total > 0:
        low_note = (rf" Davon liegen {n_low_total} Messung(en) unter "
                    rf"{low_thr:g}/min (Bradykardie-Schwelle).")
    # Median-Puls fuer den Datenkommentar
    med_txt = f"{round_half_up(ov['med'])}" if ov else "--"
    return rf"""\vspace{{2mm}}
\begin{{center}}
{{\footnotesize\textbf{{Puls-Kennzahlen (1/min).}} Median, Interquartilsbereich (Q1--Q3), Spanne (Min--Max), Anzahl der Messungen \texttt{{n}} und Anzahl Werte unterhalb der Schwelle {low_thr:g}/min ($<${low_thr:g}).}}\\[1.5mm]
{{\footnotesize
\begin{{tabular}}{{@{{}}l r r r r r@{{}}}}
\toprule
\textbf{{Zeitraum}} & \textbf{{Median}} & \textbf{{Q1--Q3}} & \textbf{{Min--Max}} & \textbf{{n}} & \textbf{{$<${low_thr:g}}} \\
\midrule
{body}
\bottomrule
\end{{tabular}}}}
\end{{center}}
\vspace{{1mm}}

\noindent{{\footnotesize\textbf{{Interpretationshinweis (automatisch aus den aktuellen Daten).}} Grundlage: {n_pulse} Pulsmessungen an {n_days} Tagen im Zeitraum {date_range}. Der Median-Puls liegt bei etwa {med_txt}/min.{low_note} In der Spalte \texttt{{n}} steht die Anzahl der Messungen im jeweiligen Zeitraum (Gesamt bzw.\ Tageszeitblock), nicht die Anzahl der Tage.}}
\vspace{{1mm}}

\noindent{{\scriptsize Blutdrucksenker (z.\,B.\ Calciumkanalblocker, teils auch Sartane) k\"onnen den Puls senken; eine anhaltend niedrige Herzfrequenz oder Symptome (Schwindel, M\"udigkeit) sollten \"arztlich abgekl\"art werden. Diese Statistik ersetzt keine \"arztliche Beurteilung.}}
"""


def build_bp_box(sps, dps, sys_thr, dia_thr, corridor_sys, corridor_dia,
                 corridor_label):
    """Kompakte Kennzahlentabelle fuer systolisch und diastolisch (gesamt + je
    Tageszeitblock), analog zur Puls-Box, mit den beiden BP-Schwellen und einer
    zusaetzlichen Spalte 'im Ziel' (Anzahl Werte innerhalb des Zielkorridors).
    """
    cs_lo, cs_hi = f"{corridor_sys[0]:g}", f"{corridor_sys[1]:g}"
    cd_lo, cd_hi = f"{corridor_dia[0]:g}", f"{corridor_dia[1]:g}"

    def fmt_cell(s):
        if s is None:
            return "-- & -- & -- & -- & -- & --"
        n_in = s['n_in'] if s['n_in'] is not None else "--"
        return (f"{round_half_up(s['med'])} & "
                f"{round_half_up(s['q1'])}--{round_half_up(s['q3'])} & "
                f"{round_half_up(s['min'])}--{round_half_up(s['max'])} & "
                f"{s['n']} & {s['n_hi']} & {n_in}")
    rows_tex = []
    for label, key in [("Gesamt", "overall"), ("Morgen", "Morgen"),
                       ("Mittag", "Mittag"), ("Abend", "Abend")]:
        rows_tex.append(rf"{label} & {fmt_cell(sps[key])} & {fmt_cell(dps[key])} \\")
    body = "\n".join(rows_tex)
    return rf"""\vspace{{2mm}}
\begin{{center}}
{{\scriptsize\textbf{{Blutdruck-Kennzahlen (mmHg).}} Je Zeitraum Median, Interquartilsbereich (Q1--Q3), Spanne (Min--Max), Anzahl der Messungen \texttt{{n}}, Anzahl Werte ab der Vergleichsschwelle ($\geq${sys_thr:g}/$\geq${dia_thr:g}) sowie ,,im Ziel`` = Anzahl Messungen \emph{{innerhalb}} des Zielkorridors ({corridor_label}: {cs_lo}--{cs_hi} systolisch, {cd_lo}--{cd_hi} diastolisch).}}\\[1mm]
{{\scriptsize
\begin{{tabular}}{{@{{}}l r r r r r r r r r r r r@{{}}}}
\toprule
 & \multicolumn{{6}}{{c}}{{\textbf{{Systolisch}}}} & \multicolumn{{6}}{{c}}{{\textbf{{Diastolisch}}}} \\
\cmidrule(lr){{2-7}}\cmidrule(lr){{8-13}}
\textbf{{Zeitraum}} & \textbf{{Med.}} & \textbf{{Q1--Q3}} & \textbf{{Min--Max}} & \textbf{{n}} & \textbf{{$\geq${sys_thr:g}}} & \textbf{{im Ziel}} & \textbf{{Med.}} & \textbf{{Q1--Q3}} & \textbf{{Min--Max}} & \textbf{{n}} & \textbf{{$\geq${dia_thr:g}}} & \textbf{{im Ziel}} \\
 & & & & & \multicolumn{{1}}{{c}}{{}} & \multicolumn{{1}}{{c}}{{\scriptsize {cs_lo}--{cs_hi}}} & & & & & \multicolumn{{1}}{{c}}{{}} & \multicolumn{{1}}{{c}}{{\scriptsize {cd_lo}--{cd_hi}}} \\
\midrule
{body}
\bottomrule
\end{{tabular}}}}
\end{{center}}

\noindent{{\scriptsize \textbf{{Bezugsebene der Kennzahlen.}} Alle Werte dieser Tabelle sind \emph{{messungsbezogen}}: Median, Quartile und Spannweite werden \"uber die einzelnen Messwerte des jeweiligen Zeitraums gebildet, ohne vorherige Zusammenfassung nach Kalendertagen. Tage mit vielen Messungen gehen daher st\"arker in die Kennzahlen ein als Tage mit wenigen Messungen. Die Verlaufsdiagramme der Langzeitauswertung sind demgegen\"uber \emph{{tagesgewichtet}}: dort wird zun\"achst ein Median je Kalendertag gebildet und anschlie\ss{{}}end der Median \"uber diese Tageswerte, damit jeder Tag unabh\"angig von der Messanzahl gleich z\"ahlt. Beide Bezugsebenen sind statistisch korrekt; sie k\"onnen -- je nach Verteilung der Messzeitpunkte \"uber die Tage -- um wenige mmHg voneinander abweichen. In der Spalte \texttt{{n}} steht die Anzahl der Messungen im jeweiligen Zeitraum (Gesamt bzw.\ Tageszeitblock), nicht die Anzahl der Tage. Die Spalten $\geq${sys_thr:g}/$\geq${dia_thr:g} z\"ahlen Messungen \emph{{ab}} der h\"auslichen Vergleichsschwelle; ,,im Ziel`` z\"ahlt Messungen, die \emph{{innerhalb}} des angestrebten Zielkorridors ({corridor_label}: {cs_lo}--{cs_hi}\,mmHg systolisch bzw.\ {cd_lo}--{cd_hi}\,mmHg diastolisch) liegen -- also die Zahl der Messungen, die den Zielbereich treffen. Diese Statistik ersetzt keine \"arztliche Beurteilung.}}
"""


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
    legend style={{at={{(0.5,-0.42)}},anchor=north,legend columns=3,font=\scriptsize,draw=gray!50}},
    legend image post style={{scale=1.2}},
]
{sep}
{series_tex}
\end{{axis}}
\end{{tikzpicture}}"""


def agg_hour_stats(rows, idx):
    """Kennzahlen je Stunde (0--23) ueber den gesamten Auswertungszeitraum.

    Fuer jede der 24 Tagesstunden werden Median, Q1, Q3, Min, Max und die
    Anzahl der Messungen n aus allen Messwerten dieser Stunde gebildet --
    messungsbezogen, ohne vorherige Zusammenfassung nach Kalendertagen und
    damit konsistent zur Block-Kennzahlentabelle. Stunden ohne Messung
    liefern None.

    idx : 2 = systolisch, 3 = diastolisch (Tupelposition wie in read_rows()).
    Rueckgabe: dict hour -> {"med","q1","q3","min","max","n"} | None.
    """
    out = {}
    for h in range(24):
        v = [r[idx] for r in rows if r[1] == h]
        if v:
            out[h] = {
                "med": statistics.median(v),
                "q1": quantile(v, .25),
                "q3": quantile(v, .75),
                "min": min(v),
                "max": max(v),
                "n": len(v),
            }
        else:
            out[h] = None
    return out


def _hour_runs(prof):
    """Zusammenhaengende Laeufe belegter Stunden (fuer die Verbindungslinien).

    Gibt eine Liste von Stundenlisten zurueck, wobei nur unmittelbar
    aufeinanderfolgende belegte Stunden (h, h+1, ...) zu einem Lauf gehoeren.
    So verbindet im Diagramm keine Linie ueber eine messfreie (Nacht-)Luecke
    hinweg -- es wird also nicht ueber fehlende Stunden interpoliert.
    """
    hrs = [h for h in range(24) if prof[h]]
    runs, cur = [], []
    for h in hrs:
        if cur and h == cur[-1] + 1:
            cur.append(h)
        else:
            if len(cur) >= 2:
                runs.append(cur)
            cur = [h]
    if len(cur) >= 2:
        runs.append(cur)
    return runs


def build_hour_profile_plot(sys_h, dia_h, st):
    """Abbildung 4: 24-Stunden-Profil.

    Je Tagesstunde 0--23 wird der Median als Marker mit einem IQR-Whisker
    (Q1--Q3) fuer systolisch und diastolisch gezeichnet. Leere Stunden bleiben
    als Luecke sichtbar; innerhalb zusammenhaengender Stundenlaeufe verbindet
    eine duenne Linie die Mediane, ohne ueber messfreie Stunden zu
    interpolieren. Zielkorridor und Vergleichsschwellen (135/85) werden -- wie
    in Abbildung 1 -- als Hintergrund bzw. punktierte Linien hinterlegt.
    """
    cs, cd = st['corridor_sys'], st['corridor_dia']
    sys_line, dia_line = st['line_sys'], st['line_dia']

    def err_coords(prof):
        pts = []
        for h in range(24):
            s = prof[h]
            if not s:
                continue
            up = s['q3'] - s['med']
            dn = s['med'] - s['q1']
            pts.append(f"({h},{s['med']:.0f}) += (0,{up:.1f}) -= (0,{dn:.1f})")
        return "\n".join(pts)

    def seg_lines(prof, style):
        segs = []
        for run in _hour_runs(prof):
            coords = " ".join(f"({h},{prof[h]['med']:.0f})" for h in run)
            segs.append(rf"\addplot[{style},thin,no marks,forget plot] "
                        rf"coordinates {{{coords}}};")
        return "\n".join(segs)

    # Datenabhaengige y-Grenzen: Whisker-Enden (Q1/Q3) beider Messgroessen,
    # Korridor und Vergleichsschwellen einbeziehen, dann etwas Luft ergaenzen.
    lows, highs = [], []
    for prof in (sys_h, dia_h):
        for s in prof.values():
            if s:
                lows.append(s['q1'])
                highs.append(s['q3'])
    lows += [cd[0], 85]
    highs += [cs[1], 135]
    ymin = int((min(lows) - 6) // 2 * 2) if lows else 60
    ymax = int(((max(highs) + 6) + 1) // 2 * 2) if highs else 150

    sys_seg = seg_lines(sys_h, sys_line)
    dia_seg = seg_lines(dia_h, dia_line)
    sys_err = err_coords(sys_h)
    dia_err = err_coords(dia_h)

    # Sichtbarer Hinweis, wenn ein individueller (z. B. aneurysmaspezifischer)
    # Korridor verwendet wird -- analog zu Abbildung 1.
    if st.get("corridor_is_custom"):
        cs_lo, cs_hi = f"{cs[0]:g}", f"{cs[1]:g}"
        cd_lo, cd_hi = f"{cd[0]:g}", f"{cd[1]:g}"
        corridor_annotation = (
            rf"\node[anchor=north east,font=\scriptsize\bfseries,fill=white,"
            rf"fill opacity=0.75,text opacity=1,inner sep=1.5pt] "
            rf"at ([yshift=1pt]rel axis cs:0.99,1.0) "
            rf"{{Individueller Zielkorridor {cs_lo}--{cs_hi}/{cd_lo}--{cd_hi}\,mmHg}};"
        )
    else:
        corridor_annotation = ""

    return rf"""\begin{{tikzpicture}}
\begin{{axis}}[
    width=0.92\textwidth, height=6.2cm,
    xmin=-0.5, xmax=23.5, ymin={ymin}, ymax={ymax},
    xtick={{0,2,4,6,8,10,12,14,16,18,20,22}},
    xticklabel style={{font=\scriptsize}},
    yticklabel style={{font=\scriptsize}},
    xlabel={{\footnotesize Uhrzeit [h]}},
    ylabel={{Blutdruck [mmHg]}},
    ymajorgrids=true, grid style={{gray!25}},
    title={{\footnotesize\bfseries Abb.~4: 24-Stunden-Profil (Median je Stunde, Whisker\,=\,IQR)}},
    legend style={{at={{(0.5,-0.20)}},anchor=north,legend columns=2,font=\scriptsize,draw=gray!50}},
    legend image post style={{scale=1.3}},
]
\fill[{st['corridor_fill']}] (axis cs:-0.5,{cs[0]}) rectangle (axis cs:23.5,{cs[1]});
\fill[{st['corridor_fill']}] (axis cs:-0.5,{cd[0]}) rectangle (axis cs:23.5,{cd[1]});
{sys_seg}
{dia_seg}
\addplot[{sys_line},only marks,error bars/.cd,y dir=both,y explicit,error bar style={{line width=0.5pt}}] coordinates {{
{sys_err}
}};
\addlegendentry{{Systolisch (Median, Whisker\,=\,IQR)}}
\addplot[{dia_line},only marks,error bars/.cd,y dir=both,y explicit,error bar style={{line width=0.5pt}}] coordinates {{
{dia_err}
}};
\addlegendentry{{Diastolisch (Median, Whisker\,=\,IQR)}}
\draw[densely dotted,thick,{st['thresh']}] (axis cs:-0.5,135) -- (axis cs:23.5,135)
   node[pos=0.96,above,font=\tiny,{st['thresh']}]{{135 syst.}};
\draw[densely dotted,thick,{st['thresh']}] (axis cs:-0.5,85) -- (axis cs:23.5,85)
   node[pos=0.96,above,font=\tiny,{st['thresh']}]{{85 diast.}};
{corridor_annotation}
\end{{axis}}
\end{{tikzpicture}}"""


def build_hour_bp_box(sys_h, dia_h, date_range, n_days):
    """Kennzahlentabelle je Tagesstunde 0--23 (systolisch + diastolisch).

    Aufbau wie build_bp_box, jedoch zeilenweise je voller Stunde. Es werden
    alle 24 Tagesstunden aufgefuehrt; Stunden ohne Messung erhalten in allen
    Zellen den Strich ,,--``. Alle Kennzahlen sind messungsbezogen (ohne
    Tagesgewichtung).
    """
    def cell(s):
        if s is None:
            return "-- & -- & -- & --"
        return (f"{round_half_up(s['med'])} & "
                f"{round_half_up(s['q1'])}--{round_half_up(s['q3'])} & "
                f"{round_half_up(s['min'])}--{round_half_up(s['max'])} & "
                f"{s['n']}")
    rows_tex = []
    n_hours = 0
    n_meas = 0
    for h in range(24):
        if sys_h[h] is not None:
            n_hours += 1
            n_meas += sys_h[h]['n']
        rows_tex.append(rf"{h:02d}:00 & {cell(sys_h[h])} & {cell(dia_h[h])} \\")
    body = "\n".join(rows_tex)
    return rf"""\begin{{center}}
{{\scriptsize\textbf{{Blutdruck-Kennzahlen je Stunde (mmHg).}} Je voller Tagesstunde (Bin h:00--h:59) Median, Interquartilsbereich (Q1--Q3), Spanne (Min--Max) und Anzahl der Messungen \texttt{{n}}, getrennt fuer systolisch und diastolisch. Aufgef\"uhrt sind alle 24 Tagesstunden; Stunden ohne Messung sind in allen Zellen mit ,,--`` markiert.}}\\[1mm]
{{\scriptsize\renewcommand{{\arraystretch}}{{0.9}}
\begin{{tabular}}{{@{{}}l r r r r r r r r@{{}}}}
\toprule
 & \multicolumn{{4}}{{c}}{{\textbf{{Systolisch}}}} & \multicolumn{{4}}{{c}}{{\textbf{{Diastolisch}}}} \\
\cmidrule(lr){{2-5}}\cmidrule(lr){{6-9}}
\textbf{{Stunde}} & \textbf{{Med.}} & \textbf{{Q1--Q3}} & \textbf{{Min--Max}} & \textbf{{n}} & \textbf{{Med.}} & \textbf{{Q1--Q3}} & \textbf{{Min--Max}} & \textbf{{n}} \\
\midrule
{body}
\bottomrule
\end{{tabular}}}}
\end{{center}}

\noindent{{\scriptsize \textbf{{Bezugsebene und Lesehilfe.}} Grundlage: {n_meas} Messungen an {n_days} Tagen im Zeitraum {date_range}; Messwerte lagen an {n_hours} der 24 Tagesstunden vor. Alle Werte sind \emph{{messungsbezogen}} (Median, Quartile und Spannweite je Stunde \"uber die Einzelmesswerte, ohne vorherige Zusammenfassung nach Kalendertagen) und damit konsistent zur Block-Kennzahlentabelle. Einzelne Stunden sind bei h\"auslicher Messung oft nur d\"unn besetzt (h\"aufig \texttt{{n}}=1--2); bei \texttt{{n}}=1 fallen Median, Q1--Q3 und Min--Max auf denselben Einzelwert zusammen. Die Stunden-Kennzahlen zeigen die feinere Tageskinetik; f\"ur robuste Aussagen bleiben die Tageszeitbl\"ocke (Morgen/Mittag/Abend) ma\ss{{}}geblich. Diese Statistik ersetzt keine \"arztliche Beurteilung.}}
"""


def build_weekday_plot(wd, outl, st, metric, ymin, ymax, ylabel, title,
                       block_labels, xlabel=None, thresh=None, corridor=None,
                       show_fences=False):
    """Eine gruppierte Balkengrafik (Wochentag x Block) fuer eine Messgroesse.

    wd       : dict (weekday,block)->median  (Balkenhoehe)
    outl     : dict (weekday,block)->{"hi","lo","hi_fence","lo_fence"}
    corridor : (lo,hi) grau hinterlegter ESC-Orientierungskorridor oder None
    show_fences : wenn True, wird die obere Tukey-Grenze je Zelle als kurzer
                  waagrechter Strich gezeichnet (erst ab n>=4 und IQR>=1 belegt).
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

    def fence_coords(b, key):
        pts = []
        for i in range(7):
            cell = outl.get((i, b), {})
            fv = cell.get(key)
            if fv is not None:
                pts.append(f"({WEEKDAYS[i]},{fv:.0f})")
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
        # Optionale obere Tukey-Grenze (Q3+1.5*IQR) als kurzer waagrechter
        # Strich ueber der jeweiligen Saeule. Nur der OBERE Zaun wird gezeigt,
        # damit die Balken nicht durch untere Striche zerschnitten wirken; er
        # markiert die Schwelle, ab der ein Wert als Ausreisser nach oben gilt.
        if show_fences:
            fc = fence_coords(b, "hi_fence")
            if fc:
                bars.append(
                    rf"\addplot+[ybar,bar width=0pt,draw=none,fill=none,forget plot,"
                    rf"mark=-,mark size=4.5pt,"
                    rf"mark options={{draw={st['fence']},thick}}] "
                    rf"coordinates {{{fc}}};"
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
    # When an x-axis label is present it occupies the space directly below the
    # axis, so the legend (also placed below the axis) must sit lower to avoid
    # overprinting the label (e.g. "Wochentag" in Abb. 2b).
    legend_y = "-0.34" if xlabel else "-0.24"
    return rf"""\begin{{tikzpicture}}
\begin{{axis}}[
    width=0.92\textwidth, height=5.9cm,
    ybar=1.5pt, bar width=7pt, enlarge x limits=0.08,
    ymin={ymin}, ymax={ymax},
    ylabel={{{ylabel}}}, {xlab}
    symbolic x coords={{Mo,Di,Mi,Do,Fr,Sa,So}}, xtick=data,
    ymajorgrids=true, grid style={{gray!25}},
    axis on top=false,
    legend style={{at={{(0.5,{legend_y})}},anchor=north,legend columns=3,font=\scriptsize,draw=gray!50}},
    legend image post style={{scale=1.6}},
    title={{\footnotesize\bfseries {title}}},
]
{corr}
{bars_tex}
{thr}
\end{{axis}}
\end{{tikzpicture}}"""


def build_document(rows, style, morning_end, midday_end, direction="up",
                   corridor_sys=(120, 129), corridor_dia=(70, 79),
                   corridor_is_custom=False, corridor_label="ESC",
                   pulse=False, pulse_low=50, show_fences=False, hourly=True):
    st = style_defs(style)
    # Thread the (possibly custom) target corridor through the style dict so
    # the plot builders can draw and label it without extra parameters.
    st["corridor_sys"] = corridor_sys
    st["corridor_dia"] = corridor_dia
    st["corridor_is_custom"] = corridor_is_custom
    st["corridor_label"] = corridor_label
    sys_p = agg_profile(rows, 2, morning_end, midday_end)
    dia_p = agg_profile(rows, 3, morning_end, midday_end)
    wd_sys = agg_weekday_block(rows, 2, morning_end, midday_end)
    wd_dia = agg_weekday_block(rows, 3, morning_end, midday_end)
    ol_sys = agg_weekday_outliers(rows, 2, morning_end, midday_end, direction)
    ol_dia = agg_weekday_outliers(rows, 3, morning_end, midday_end, direction)

    # Blutdruck-Kennzahlen (systolisch/diastolisch) fuer die Statistik-Tabelle
    # auf der Seite "Statistische Kennzahlen" (Schwellen 135/85 wie die
    # Vergleichslinien).
    sps = bp_block_stats(rows, 2, morning_end, midday_end, 135, corridor_sys)
    dps = bp_block_stats(rows, 3, morning_end, midday_end, 85, corridor_dia)

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
    # Warnung bei verdaechtig grosser Luecke am Anfang (moeglicher Datums-Tippfehler).
    uniq_dates = sorted(set(all_dates))
    if len(uniq_dates) >= 2 and (uniq_dates[1] - uniq_dates[0]).days > 90:
        print(
            f"WARNUNG: Das frueheste Messdatum ({uniq_dates[0].strftime('%d.%m.%Y')}) "
            f"liegt mehr als 90 Tage vor der naechsten Messung "
            f"({uniq_dates[1].strftime('%d.%m.%Y')}). Moeglicher Datums-Tippfehler "
            f"(z. B. falsches Jahr)? Andernfalls --date-from setzen.",
            file=sys.stderr,
        )
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
                   f"{round_half_up(wd_day_sys[lo_day])}\\,mmHg ({WEEKDAYS[lo_day]}) und "
                   f"{round_half_up(wd_day_sys[hi_day])}\\,mmHg ({WEEKDAYS[hi_day]}).")

    # Tagesgang-Beschreibung (Morgen vs. Abend systolisch)
    trend = ""
    if sys_p["Morgen"] and sys_p["Abend"]:
        d = sys_p["Abend"][0] - sys_p["Morgen"][0]
        if abs(d) < 3:
            trend = " Der Tagesgang ist nach aktueller Datenlage flach."
        elif d > 0:
            trend = (f" Tendenziell liegt der Abendwert systolisch ueber dem Morgenwert "
                     f"(Differenz ca.\\ {round_half_up(d)}\\,mmHg).")
        else:
            trend = (f" Tendenziell liegt der Morgenwert systolisch ueber dem Abendwert "
                     f"(Differenz ca.\\ {round_half_up(abs(d))}\\,mmHg).")

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

    # Y-Achsengrenzen datenabhaengig bestimmen, damit kein Balken oder
    # Ausreisser ausserhalb des Bereichs liegt (fixe Grenzen konnten z. B. einen
    # niedrigen Sonntag-Mittag-Median unter ymin abschneiden). Es werden alle
    # Blockmediane, alle Ausreisser, die Zaeune, der Korridor und die
    # Vergleichsschwelle einbezogen; anschliessend etwas Luft ergaenzt.
    def axis_bounds(wd, outl, corridor, thresh, fallback):
        vals = [v for v in wd.values() if v is not None]
        for cell in outl.values():
            vals += list(cell.get("hi", [])) + list(cell.get("lo", []))
            for fk in ("hi_fence", "lo_fence"):
                if show_fences and cell.get(fk) is not None:
                    vals.append(cell[fk])
        if corridor:
            vals += [corridor[0], corridor[1]]
        if thresh is not None:
            vals.append(thresh)
        if not vals:
            return fallback
        lo = min(vals) - 6
        hi = max(vals) + 6
        # Auf ganze 2er runden fuer saubere Ticks.
        lo = int(lo // 2 * 2)
        hi = int((hi + 1) // 2 * 2)
        return lo, hi

    sys_lo, sys_hi = axis_bounds(wd_sys, ol_sys, st['corridor_sys'], 135, (110, 146))
    dia_lo, dia_hi = axis_bounds(wd_dia, ol_dia, st['corridor_dia'], 85, (60, 92))

    wd_sys_tex = build_weekday_plot(
        wd_sys, ol_sys, st, "sys", sys_lo, sys_hi, "Systolisch [mmHg]",
        "Abb.~2a: Systolischer Median je Wochentag und Tageszeit",
        block_labels, thresh=135, corridor=st['corridor_sys'], show_fences=show_fences)
    wd_dia_tex = build_weekday_plot(
        wd_dia, ol_dia, st, "dia", dia_lo, dia_hi, "Diastolisch [mmHg]",
        "Abb.~2b: Diastolischer Median je Wochentag und Tageszeit",
        block_labels, xlabel="Wochentag", thresh=85, corridor=st['corridor_dia'],
        show_fences=show_fences)

    style_note = ("Farbkodiert" if style == "color"
                  else "Schwarz-Wei\\ss{} (Graustufen und Muster: solide / schraffiert / punktiert)")

    # Corridor description for the methodik box; adapts to a custom corridor.
    cs_lo, cs_hi = f"{st['corridor_sys'][0]:g}", f"{st['corridor_sys'][1]:g}"
    cd_lo, cd_hi = f"{st['corridor_dia'][0]:g}", f"{st['corridor_dia'][1]:g}"
    if st['corridor_is_custom']:
        corridor_sentence = (
            rf"die \textbf{{grau hinterlegten Korridore}} ({cs_lo}--{cs_hi}\,mmHg "
            rf"systolisch, {cd_lo}--{cd_hi}\,mmHg diastolisch) sind ein "
            rf"\textbf{{individuell gew\"ahlter, spezifischer Zielkorridor}} "
            rf"(hier {st['corridor_label']}) und nicht die allgemeine "
            rf"ESC-Orientierung"
        )
    else:
        corridor_sentence = (
            rf"die \textbf{{grau hinterlegten Korridore}} ({cs_lo}--{cs_hi}\,mmHg "
            rf"systolisch, {cd_lo}--{cd_hi}\,mmHg diastolisch) sind allgemeine "
            rf"ESC-Orientierungsbereiche unter Therapie bei individueller "
            rf"Vertr\"aglichkeit und keine aneurysmaspezifischen Zielwerte"
        )

    # Erlaeuterungen zu den optionalen Tukey-Grenzen (--fences)
    fences_note = ""
    fences_caption = ""
    if show_fences:
        fences_note = (r" Zus\"atzlich markiert je S\"aule ein kurzer waagrechter Strich "
                       r"die \emph{obere} Tukey-Grenze ($Q_3+1{,}5\cdot\mathrm{IQR}$): ein "
                       r"Messwert oberhalb dieses Strichs gilt als Ausrei\ss{}er nach oben "
                       r"und wird als Kreis markiert. Der Strich erscheint nur bei "
                       r"mindestens vier Messungen je Zelle und ausreichender Streuung.")
        fences_caption = (r" Der kurze waagrechte Strich \"uber jeder S\"aule ist die "
                          r"\emph{obere Ausrei\ss{}er-Grenze} ($Q_3+1{,}5\cdot\mathrm{IQR}$): "
                          r"Werte oberhalb dieses Strichs sind die als Kreis markierten "
                          r"Ausrei\ss{}er nach oben.")

    # Statistik-Seite (neue Seite): Blutdruck-Kennzahlen immer, Puls optional.
    has_pulse = any(r[4] is not None for r in rows)
    stats_parts = [
        r"\clearpage",
        r"\begin{center}",
        r"{\large\bfseries Statistische Kennzahlen}\\[2pt]",
        rf"{{\footnotesize\bfseries Auswertungszeitraum: {date_range} \quad ({n_days} Tage)}}",
        r"\end{center}",
        r"\vspace{2mm}",
        build_bp_box(sps, dps, 135, 85, corridor_sys, corridor_dia, corridor_label),
    ]
    stats_section = "\n".join(stats_parts)

    # Puls-Auswertung als EIGENER Abschnitt. Sie wird -- falls angefordert --
    # bewusst als LETZTER Abschnitt des Dokuments ausgegeben (nach der
    # stuendlichen Auswertung), damit sie unveraendert am Dokumentende steht.
    # Eigene Seite (\clearpage), da sie nicht mehr mit der BP-Kennzahlenbox
    # dieselbe Seite teilt.
    pulse_parts = []
    if pulse and has_pulse:
        pu_p = agg_pulse_profile(rows, morning_end, midday_end)
        ps = pulse_stats(rows, morning_end, midday_end, pulse_low)
        pulse_plot_tex = build_pulse_plot(pu_p, st, pulse_low)
        pulse_box_tex = build_pulse_box(ps, pulse_low, date_range, n_days)
        pulse_parts = [
            r"\clearpage",
            r"\begin{center}",
            r"{\large\bfseries Puls-Auswertung (Herzfrequenz)}\\[2pt]",
            r"{\footnotesize Median-Puls je Tageszeitblock; relevant zur Beobachtung eines "
            r"m\"oglichen Pulsabfalls unter Blutdruckmedikation.}",
            r"\end{center}",
            r"\vspace{2mm}",
            r"\begin{center}",
            pulse_plot_tex + r"\\[1mm]",
            rf"{{\footnotesize Abbildung~3: Puls-Tagesprofil. Punkte = Median je "
            rf"Tageszeitblock, schattiertes Band = Interquartilsbereich; die punktierte "
            rf"Linie markiert die w\"ahlbare Bradykardie-Schwelle ({pulse_low:g}/min).}}",
            r"\end{center}",
            pulse_box_tex,
        ]
    elif pulse and not has_pulse:
        pulse_parts = [
            r"\clearpage",
            r"\vspace*{4mm}",
            r"\noindent{\footnotesize\emph{Hinweis:} Es wurde eine Puls-Auswertung "
            r"angefordert (\texttt{--pulse}), aber das CSV enth\"alt keine verwertbare "
            r"Puls-/Pulsspalte.}",
        ]
    pulse_section = "\n".join(pulse_parts)

    # Stuendliche Auswertung (eigene Seite): 24-Stunden-Profil (Abb. 4) plus
    # Kennzahlentabelle je belegter Stunde. Standardmaessig aktiv; mit
    # --no-hourly abschaltbar. Steht nach der BP-Kennzahlenseite und -- falls
    # eine Puls-Auswertung angefordert ist -- VOR dieser, sodass die
    # Puls-Auswertung der letzte Abschnitt des Dokuments bleibt. Die
    # Seitenzaehlung der ersten Seiten bleibt unveraendert.
    if hourly:
        sys_h = agg_hour_stats(rows, 2)
        dia_h = agg_hour_stats(rows, 3)
        hour_profile_tex = build_hour_profile_plot(sys_h, dia_h, st)
        hour_box_tex = build_hour_bp_box(sys_h, dia_h, date_range, n_days)
        hour_section = "\n".join([
            r"\clearpage",
            r"\begin{center}",
            r"{\large\bfseries St\"undliche Auswertung (24-Stunden-Profil)}\\[2pt]",
            rf"{{\footnotesize\bfseries Auswertungszeitraum: {date_range} \quad ({n_days} Tage)}}",
            r"\end{center}",
            r"\vspace{2mm}",
            r"\begin{center}",
            hour_profile_tex + r"\\[1mm]",
            r"{\footnotesize Abbildung~4: Median je voller Tagesstunde (Marker) mit "
            r"Whisker \"uber den Interquartilsbereich (Q1--Q3); systolisch und "
            r"diastolisch getrennt. Leere Stunden bleiben als L\"ucke sichtbar, "
            r"eine d\"unne Linie verbindet nur unmittelbar aufeinanderfolgende "
            r"Stunden (keine Interpolation \"uber messfreie Stunden). Grau "
            r"hinterlegt der Zielkorridor, punktiert die Vergleichsschwellen "
            r"135/85\,mmHg.}",
            r"\end{center}",
            r"\vspace{1mm}",
            hour_box_tex,
        ])
    else:
        hour_section = ""

    return rf"""\documentclass[11pt]{{article}}
\usepackage[ngerman]{{babel}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{tikz}}
\usepackage{{pgfplots}}
\pgfplotsset{{compat=1.18}}
\usepgfplotslibrary{{fillbetween}}
{patterns_lib}
\usepackage{{booktabs}}
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
\textbf{{Methodik und Lesehilfe.}} Grundlage sind die h\"auslichen Blutdruckmessungen ({n_total} Messungen an {n_days} Tagen), eingeteilt in drei Tageszeitbl\"ocke: \emph{{Morgen}} ($<${morning_end}:00), \emph{{Mittag}} ({morning_end}:00--{midday_end}:00) und \emph{{Abend}} ($>${midday_end}:00). Alle Balken und Linien sind \emph{{median}}-basiert\footnotemark[1], schattierte B\"ander bzw.\ die grau hinterlegten Korridore dienen der Streuungs- und Vergleichsdarstellung. Abbildung~1 zeigt das gemittelte \emph{{Tagesprofil}} (Median je Block; schattiert der Interquartilsbereich, 25.--75.\ Perzentil). Abbildung~2 schl\"usselt die Mediane nach Wochentag auf; kleine Kreise markieren \emph{{Ausrei\ss{{}}er}}\footnotemark[2].{fences_note} Die Zahl \texttt{{n}} nennt die Anzahl der Messungen. Die punktierten Linien markieren die h\"auslichen Vergleichsschwellen 135\,mmHg systolisch bzw.\ 85\,mmHg diastolisch; {corridor_sentence}. \textbf{{Hinweis zur Datenlage:}} {datenlage} Die Darstellung ersetzt keine \"arztliche Zielwertfestlegung.}}}}
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
{wd_sys_tex}\\[9mm]
{wd_dia_tex}\\[1mm]
{{\footnotesize Abbildung~2: Mediane je Wochentag und Tageszeitblock (Balken). \emph{{Ausrei\ss{{}}er}} nach der Tukey-Regel liegen \emph{{au\ss{{}}erhalb}} der Balken: Kreise ($\circ$) markieren Ausrei\ss{{}}er nach oben (Blutdruckspitzen), das Kreuz ($\times$) Ausrei\ss{{}}er nach unten. Sie werden nur bei mindestens vier Messungen je Zelle und ausreichender Streuung bestimmt.{fences_caption} Nicht besetzte Bl\"ocke werden ausgelassen.}}
\end{{center}}
\vspace{{3mm}}

\noindent{{\footnotesize\textbf{{Interpretationshinweis (automatisch aus den aktuellen Daten).}} Grundlage: {n_total} Messungen an {n_days} Tagen im Zeitraum {date_range}. Systolischer Median morgens ca.\ {med_or_dash(sys_p,'Morgen')}\,mmHg, mittags ca.\ {med_or_dash(sys_p,'Mittag')}\,mmHg, abends ca.\ {med_or_dash(sys_p,'Abend')}\,mmHg (Abend: n={n_abend}); diastolisch morgens ca.\ {med_or_dash(dia_p,'Morgen')}\,mmHg, mittags ca.\ {med_or_dash(dia_p,'Mittag')}\,mmHg, abends ca.\ {med_or_dash(dia_p,'Abend')}\,mmHg.{trend}{wd_span} Insgesamt wurden {n_outliers} Tukey-Ausrei\ss{{}}er markiert ({n_out_hi} nach oben, {n_out_lo} nach unten).{cov} {abend_belastbar} Mit regelm\"a\ss{{}}iger Drei-Punkt-Messung wird insbesondere ein morgendlicher Blutdruckanstieg oder ein abendlicher Wiederanstieg sichtbar -- beides kann f\"ur Einnahmezeitpunkt und Dosierung der Antihypertensiva bedeutsam sein. Die Entscheidung trifft die behandelnde \"Arztin oder der behandelnde Arzt.}}
{stats_section}
{hour_section}
{pulse_section}
\end{{document}}
"""


def main():
    ap = argparse.ArgumentParser(
        description="Erzeugt das LaTeX/TikZ-Diagramm 'Tageszeit x Wochentag' "
                    "aus einem Blutdruck-CSV; umschaltbar zwischen Farbe und Schwarz-Weiss. "
                    "Mit --name wird der Ausgabedatei ein Praefix vorangestellt, um z. B. "
                    "zwei Personen zu unterscheiden (--name Eva -> Eva_bp_weekday_daytime.tex).",
        epilog="Beispiele:\n"
               "  Minimal:        python3 generate_bp_daytime_tikz.py --csv iBP.csv\n"
               "  Zwei Personen:  python3 generate_bp_daytime_tikz.py --csv Eva.csv --name Eva\n"
               "                  python3 generate_bp_daytime_tikz.py --csv Adam.csv --name Adam\n"
               "  Schwarz-Weiss:  python3 generate_bp_daytime_tikz.py --csv iBP.csv --style bw\n"
               "  Puls-Auswertung: python3 generate_bp_daytime_tikz.py --csv iBP.csv --pulse --pulse-low 48\n"
               "  Aneurysma-Korridor: python3 generate_bp_daytime_tikz.py --csv iBP.csv --corridor 110-119/70-79\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
    ap.add_argument("--fences", action="store_true",
                    help="Zeichnet zusaetzlich die obere Tukey-Grenze (Q3+1,5*IQR) je Zelle "
                         "als kurzen waagrechten Strich, sodass sichtbar ist, ab welchem "
                         "Wert ein Punkt als Ausreisser gilt. Standard: aus.")
    ap.add_argument("--no-hourly", action="store_true",
                    help="Unterdrueckt die stuendliche Auswertung (24-Stunden-Profil "
                         "Abb. 4 + Kennzahlentabelle je Stunde auf einer eigenen Seite). "
                         "Standard: an. Zeigt je voller Tagesstunde 0-23 Median, "
                         "Q1-Q3, Min-Max und n fuer systolisch und diastolisch, "
                         "messungsbezogen ueber den gewaehlten Zeitraum.")
    ap.add_argument("--date-from", default=None,
                    help="Startdatum der Auswertung (inklusive). Messungen davor "
                         "werden ignoriert. Formate wie bei den Daten, z. B. "
                         "2026-05-15 oder 15.05.2026. Standard: alle ab Beginn.")
    ap.add_argument("--date-to", default=None,
                    help="Enddatum der Auswertung (inklusive). Messungen danach "
                         "werden ignoriert. Ohne Angabe werden alle Messungen "
                         "ab --date-from verwendet.")
    ap.add_argument("--name", default=None,
                    help="Optionaler Personen-/Lauf-Name. Die Ausgabe wird in ein "
                         "gleichnamiges Unterverzeichnis neben diesem Skript geschrieben "
                         "und erhaelt den Namen zusaetzlich als Dateipraefix "
                         "(--name Eva -> Eva/Eva_bp_weekday_daytime.tex). Das Verzeichnis "
                         "wird bei Bedarf angelegt. Ein explizit gesetztes --out hat Vorrang. "
                         "Standard: kein Praefix, Ausgabe im aktuellen Verzeichnis.")
    ap.add_argument("--pulse", action="store_true",
                    help="Zusaetzliche Puls-Auswertung auf der Statistik-Seite: Puls-Tagesprofil "
                         "(Abb. 3) und Kennzahlenbox (Median, IQR, Spanne, n, Werte unter "
                         "der Bradykardie-Schwelle). Benoetigt eine Puls-/Pulse-Spalte im CSV. "
                         "Standard: aus.")
    ap.add_argument("--pulse-low", type=float, default=50,
                    help="Bradykardie-Schwelle in 1/min fuer die Puls-Auswertung; Werte "
                         "darunter werden gezaehlt und im Profil als Linie markiert. "
                         "Standard: 50.")
    ap.add_argument("-o", "--out", default=None,
                    help="Ausgabedatei (.tex). Standard: [name_]bp_weekday_daytime.tex")
    ap.add_argument("--corridor", default=None, metavar="SYS_LO-SYS_HI/DIA_LO-DIA_HI",
                    help="Zielkorridor als 'sys_lo-sys_hi/dia_lo-dia_hi', z. B. '110-119/70-79' fuer einen aneurysmaspezifisch niedrigeren Korridor. Ohne Angabe bleibt der Standard (ESC 120-129/70-79). Ein abweichender Korridor wird im Methodik-Text und als sichtbarer Hinweis in Abb. 1 gekennzeichnet.")
    ap.add_argument("--corridor-label", default=None,
                    help="Kurzbezeichnung des Zielkorridors (z. B. 'Aneurysma', 'individuell'). Standard: 'ESC' bzw. 'individuell' bei abweichendem Korridor.")
    args = ap.parse_args()

    # Ausgabedateiname aufloesen: --name erzeugt ein Unterverzeichnis gleichen
    # Namens neben diesem Skript und dient zugleich als Dateipraefix
    # (z. B. --name Erwin -> <Skriptordner>/Erwin/Erwin_bp_weekday_daytime.tex).
    # Das Verzeichnis wird bei Bedarf angelegt. Die Verankerung am Skriptordner
    # (statt am aktuellen Arbeitsverzeichnis) sorgt dafuer, dass die Dateien
    # immer neben dem Code landen, egal von wo aufgerufen wird.
    # Ein explizites --out hat immer Vorrang.
    if args.out is None:
        prefix = (args.name.strip() if args.name else "")
        if prefix:
            prefix = _re.sub(r"[^A-Za-z0-9._-]+", "_", prefix).strip("_")
        if prefix:
            outdir = _Path(__file__).resolve().parent / prefix
            outdir.mkdir(parents=True, exist_ok=True)
            args.out = str(outdir / f"{prefix}_bp_weekday_daytime.tex")
        else:
            args.out = "bp_weekday_daytime.tex"

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

    # Zielkorridor aufloesen (Standard ESC 120-129/70-79).
    corridor_sys, corridor_dia = (120, 129), (70, 79)
    corridor_is_custom = False
    corridor_label = "ESC"
    if args.corridor:
        try:
            sys_part, dia_part = args.corridor.split("/")
            corridor_sys = tuple(float(x) for x in sys_part.split("-"))
            corridor_dia = tuple(float(x) for x in dia_part.split("-"))
            if len(corridor_sys) != 2 or len(corridor_dia) != 2:
                raise ValueError
        except ValueError:
            sys.exit("--corridor erwartet 'sys_lo-sys_hi/dia_lo-dia_hi', z. B. 110-119/70-79")
        if corridor_sys[0] >= corridor_sys[1] or corridor_dia[0] >= corridor_dia[1]:
            sys.exit("--corridor: es muss lo < hi fuer syst. und diast. gelten.")
        corridor_is_custom = not (
            corridor_sys == (120, 129) and corridor_dia == (70, 79))
        corridor_label = args.corridor_label or ("individuell" if corridor_is_custom else "ESC")
    elif args.corridor_label:
        corridor_label = args.corridor_label

    tex = build_document(rows, args.style, a, b, args.outliers,
                         corridor_sys=corridor_sys, corridor_dia=corridor_dia,
                         corridor_is_custom=corridor_is_custom,
                         corridor_label=corridor_label,
                         pulse=args.pulse, pulse_low=args.pulse_low,
                         show_fences=args.fences,
                         hourly=not args.no_hourly)
    with open(args.out, "w") as f:
        f.write(tex)
    span_txt = ""
    if d_from or d_to:
        span_txt = (f", Zeitraum={(d_from.strftime('%d.%m.%Y') if d_from else 'Anfang')}"
                    f"--{(d_to.strftime('%d.%m.%Y') if d_to else 'Ende')}"
                    f" ({len(rows)} von {n_all} Messungen)")
    print(f"[ok] {args.out} erzeugt  (style={args.style}, blocks=Morgen<{a}, Mittag {a}-{b}, "
          f"Abend>{b}, outliers={args.outliers}, pulse={args.pulse}, {len(rows)} Messungen{span_txt})")
    print(f"     Kompilieren:  pdflatex {args.out}")


if __name__ == "__main__":
    main()
