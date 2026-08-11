#!/usr/bin/env python3
"""bp_merge.py -- Bestands-CSV und App-Export zu einer Datei zusammenfuehren.

Ausgangslage
------------
Die Blutdruckwerte wurden bisher in Excel gepflegt und von dort als CSV
exportiert. Ab einem Stichtag werden sie stattdessen in einer Android-App
erfasst; die Excel-Datei wird eingefroren und nicht mehr erweitert. Die App
exportiert bei jedem Mal ihren KOMPLETTEN Bestand, nicht nur die Neuzugaenge.

Wuerde man diesen Export einfach anhaengen, entstuenden bei jedem Lauf
Dubletten. Dieses Skript baut den Master stattdessen jedes Mal neu auf:

    Master = Basis (Tage VOR dem Stichtag) + App-Export (Tage AB dem Stichtag)

Der Stichtag ist der Tag der Umstellung und bleibt fuer immer derselbe. Das
Ergebnis haengt nur von den beiden Eingangsdateien ab, nicht davon, wie oft
oder wann das Skript gelaufen ist: Zweimal aufgerufen entsteht dieselbe Datei
(idempotent). Dubletten sind konstruktiv ausgeschlossen, weil sich die beiden
Quellen taggenau nicht ueberlappen koennen.

Aufruf
------
Es bleibt bei EINER vollstaendigen Datei; sie wird an Ort und Stelle neu
geschrieben. Der Stichtag ist der Tag der Umstellung auf die App und aendert
sich nie:

    python3 bp_merge.py --csv iBP_Readings_Gerti.csv \\
                        --app Gerti_App_Export.csv \\
                        --ab  2026-08-09
    python3 bp_build.py Gerti

Das funktioniert auch dann, wenn die Datei bereits App-Daten aus einem
frueheren Lauf enthaelt: Diese Tage werden verworfen und aus dem aktuellen
App-Export neu aufgebaut. Deshalb ist --ab hier Pflicht -- ein automatisch
abgeleiteter Stichtag wuerde nach jedem Lauf weiterwandern und die App-Daten
einfrieren, statt sie neu aufzubauen.

Vor dem Schreiben wird eine Sicherungskopie angelegt
(<datei>.bak-JJJJMMTT-HHMMSS). Enthaelt der App-Export keine Messung ab dem
Stichtag, bricht das Skript ab, statt die App-Tage zu loeschen.

Weitere Moeglichkeiten:

    # Ergebnis in eine andere Datei schreiben, Quelle unangetastet lassen
    python3 bp_merge.py --csv basis.csv --app export.csv --ab 2026-08-09 \\
                        --aus master_neu.csv

    # nur pruefen und anzeigen, nichts schreiben
    python3 bp_merge.py --csv iBP_Readings_Gerti.csv --app export.csv \\
                        --ab 2026-08-09 --probelauf

Eingangsformate
---------------
Beide Eingangsdateien duerfen sein:
  * der klassische iBP-Export (Systolic,Diastolic,Pulse,Weight,
    Mean Arterial Pressure,Pulse Pressure,Date,Note -- mit Datum und Uhrzeit
    als zwei komma-getrennte Felder),
  * oder ein normales Spalten-CSV mit Komma, Semikolon oder Tabulator.

Die Spaltenzuordnung erfolgt ueber die Namen, nicht ueber die Position; die
Reihenfolge der Spalten ist also frei. Fuer den Puls werden unter anderem
"Pul", "Puls", "Pulse", "HR" und "BPM" akzeptiert.

Ausgabeformat
-------------
Geschrieben wird immer dieselbe kanonische Datei:

    Datum;Zeit;Systolisch;Diastolisch;Puls;Notiz

Diese Kopfzeile ist bewusst gewaehlt: Sie enthaelt NICHT die Begriffe
"Mean Arterial Pressure"/"Pulse Pressure". Genau diese beiden Namen schalten
in generate_bp_tikz.py und generate_bp_daytime_tikz.py auf positionsbasiertes
Lesen um, bei dem die Spaltenreihenfolge fest verdrahtet ist. Mit der
kanonischen Kopfzeile arbeiten beide Generatoren rein namensbasiert.

Nur Standardbibliothek -- laeuft in a-Shell auf dem iPad.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

VERSION = "1.3.2"

# Verzeichnis dieses Skripts -- dort liegen bp_build.py und die CSV-Dateien.
BASIS = Path(__file__).resolve().parent

# Kopfzeile der erzeugten Datei. Reihenfolge und Trenner sind fix.
AUSGABE_KOPF = ["Datum", "Zeit", "Systolisch", "Diastolisch", "Puls", "Notiz"]
AUSGABE_TRENNER = ";"

# Erlaubte Spaltennamen je Feld. "pul" ist bewusst enthalten, weil manche
# Exporte die Spalte so abkuerzen.
ALIASE = {
    "datum":       ["date", "datum", "messdatum", "measurement date", "tag"],
    "zeit":        ["time", "zeit", "uhrzeit", "messzeit"],
    "systolisch":  ["systolic", "systole", "sys", "sbp", "systolisch"],
    "diastolisch": ["diastolic", "diastole", "dia", "dbp", "diastolisch"],
    "puls":        ["pulse", "puls", "pul", "heart rate", "hr", "bpm",
                    "herzfrequenz", "hf"],
    "notiz":       ["note", "notes", "bemerkung", "notiz", "kommentar"],
}

DATUMSFORMATE = ["%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y", "%d/%m/%y"]


# --------------------------------------------------------------------------
# Hilfsfunktionen
# --------------------------------------------------------------------------
def norm_kopf(s: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).strip().lower())


def parse_datum(wert: object) -> Optional[date]:
    s = str(wert or "").strip()
    if not s:
        return None
    for fmt in DATUMSFORMATE:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def parse_zeit(*werte: object) -> Optional[Tuple[int, int]]:
    """Erste als HH:MM lesbare Angabe. 'HH:MM:SS' wird ebenfalls erkannt."""
    for w in werte:
        if w is None:
            continue
        m = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", str(w))
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def parse_zahl(wert: object) -> Optional[float]:
    """Zahlen im englischen oder europaeischen Format (130 / 130,5)."""
    if wert is None:
        return None
    s = str(wert).strip().replace("\u00a0", "").replace(" ", "")
    if not s:
        return None
    m = re.search(r"[-+]?\d[\d.,]*", s)
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


@dataclass(frozen=True)
class Messung:
    datum: date
    stunde: int
    minute: int
    sys: int
    dia: int
    puls: Optional[int]
    notiz: str = ""

    @property
    def sortier(self) -> Tuple:
        return (self.datum, self.stunde, self.minute, self.sys, self.dia)

    @property
    def identitaet(self) -> Tuple:
        """Vollstaendiger Datensatz -- Grundlage der Dublettenkontrolle."""
        return (self.datum, self.stunde, self.minute, self.sys, self.dia,
                self.puls)

    def __str__(self) -> str:
        p = f", Puls {self.puls}" if self.puls is not None else ""
        return (f"{self.datum.strftime('%d.%m.%Y')} "
                f"{self.stunde:02d}:{self.minute:02d}  "
                f"{self.sys}/{self.dia} mmHg{p}")


# --------------------------------------------------------------------------
# Einlesen
# --------------------------------------------------------------------------
def _trenner(kopfzeile: str) -> str:
    z = {",": kopfzeile.count(","), ";": kopfzeile.count(";"),
         "\t": kopfzeile.count("\t")}
    best = max(z, key=z.get)
    return best if z[best] > 0 else ","


def _dialekt(trenner: str):
    class D(csv.excel):
        delimiter = trenner
    return D


def lies_messungen(pfad: Path) -> Tuple[List[Messung], List[str], str]:
    """Liest eine CSV und liefert Messungen, Problemmeldungen, Formattext."""
    if not pfad.exists():
        raise SystemExit(f"[FEHLER] Datei nicht gefunden: {pfad}")
    roh = pfad.read_bytes().decode("utf-8-sig", errors="replace")
    zeilen = [z for z in roh.splitlines() if z.strip() != ""]
    if not zeilen:
        raise SystemExit(f"[FEHLER] {pfad.name}: Datei ist leer.")

    kopf = zeilen[0]
    hl = kopf.lower()
    if ("mean arterial pressure" in hl and "pulse pressure" in hl
            and kopf.count(",") >= 6):
        return _lies_ibp(zeilen[1:], pfad.name)
    return _lies_spalten(zeilen, pfad.name)


def _lies_ibp(datenzeilen: Sequence[str],
              name: str) -> Tuple[List[Messung], List[str], str]:
    """Klassischer iBP-Export: Datum und Uhrzeit liegen in zwei Feldern.

    Feldbelegung: 0 Systolic | 1 Diastolic | 2 Pulse | 3 Weight | 4 MAP |
    5 Pulse Pressure | 6 Date | 7 Time | 8.. Note
    """
    messungen: List[Messung] = []
    probleme: List[str] = []
    for nr, f in enumerate(csv.reader(datenzeilen), start=2):
        if not f or all(x.strip() == "" for x in f):
            continue
        if len(f) < 8:
            probleme.append(f"{name} Zeile {nr}: nur {len(f)} Felder "
                            f"(mindestens 8 erwartet) -- uebersprungen")
            continue
        s, d = parse_zahl(f[0]), parse_zahl(f[1])
        p = parse_zahl(f[2])
        datum = parse_datum(f[6])
        zeit = parse_zeit(f[7], f[6])
        if datum is None or zeit is None or s is None or d is None:
            probleme.append(f"{name} Zeile {nr}: Datum, Uhrzeit oder Messwert "
                            f"nicht lesbar -- uebersprungen")
            continue
        messungen.append(Messung(
            datum=datum, stunde=zeit[0], minute=zeit[1],
            sys=int(round(s)), dia=int(round(d)),
            puls=int(round(p)) if (p is not None and p > 0) else None,
            notiz=(",".join(f[8:]).strip() if len(f) > 8 else "")))
    return messungen, probleme, "klassischer iBP-Export (positionsbasiert)"


def _lies_spalten(zeilen: Sequence[str],
                  name: str) -> Tuple[List[Messung], List[str], str]:
    """Normales Spalten-CSV. Zuordnung ueber Spaltennamen, Reihenfolge frei."""
    trenner = _trenner(zeilen[0])
    leser = csv.DictReader(zeilen, dialect=_dialekt(trenner))
    kopf = [h for h in (leser.fieldnames or []) if h is not None]
    norm = {norm_kopf(h): h for h in kopf}

    def spalte(kanon: str) -> Optional[str]:
        for alias in ALIASE[kanon]:
            if norm_kopf(alias) in norm:
                return norm[norm_kopf(alias)]
        return None

    c = {k: spalte(k) for k in ALIASE}
    fehlend = [n for n, k in (("Datum", "datum"), ("Systolisch", "systolisch"),
                              ("Diastolisch", "diastolisch")) if c[k] is None]
    if fehlend:
        raise SystemExit(
            f"[FEHLER] {name}: Pflichtspalte(n) nicht gefunden: "
            f"{', '.join(fehlend)}\n"
            f"         Gefundene Spalten: {', '.join(kopf)}")

    trenner_txt = {",": "Komma", ";": "Semikolon",
                   "\t": "Tabulator"}.get(trenner, repr(trenner))
    puls_txt = (f", Puls aus Spalte '{c['puls']}'" if c["puls"]
                else ", KEINE Pulsspalte gefunden")
    format_txt = (f"Spalten-CSV (Trenner {trenner_txt}, "
                  f"{len(kopf)} Spalten{puls_txt})")

    messungen: List[Messung] = []
    probleme: List[str] = []
    for nr, zeile in enumerate(leser, start=2):
        werte = [v for v in zeile.values() if isinstance(v, str)]
        if not zeile or all((v or "").strip() == "" for v in werte):
            continue
        datum = parse_datum(zeile.get(c["datum"]))
        zeit = parse_zeit(zeile.get(c["zeit"]) if c["zeit"] else None,
                          zeile.get(c["notiz"]) if c["notiz"] else None,
                          zeile.get(c["datum"]))
        s = parse_zahl(zeile.get(c["systolisch"]))
        d = parse_zahl(zeile.get(c["diastolisch"]))
        p = parse_zahl(zeile.get(c["puls"])) if c["puls"] else None
        if datum is None or s is None or d is None:
            probleme.append(f"{name} Zeile {nr}: Datum oder Messwert nicht "
                            f"lesbar -- uebersprungen")
            continue
        if zeit is None:
            probleme.append(f"{name} Zeile {nr}: keine Uhrzeit gefunden -- "
                            f"uebersprungen (die Tageszeit-Auswertung "
                            f"braucht sie)")
            continue
        messungen.append(Messung(
            datum=datum, stunde=zeit[0], minute=zeit[1],
            sys=int(round(s)), dia=int(round(d)),
            puls=int(round(p)) if (p is not None and p > 0) else None,
            notiz=(str(zeile.get(c["notiz"]) or "").strip()
                   if c["notiz"] else "")))
    return messungen, probleme, format_txt


# --------------------------------------------------------------------------
# Schreiben
# --------------------------------------------------------------------------
def schreibe_kanonisch(pfad: Path, messungen: Sequence[Messung]) -> None:
    """Schreibt die kanonische Datei atomar (temporaere Datei + os.replace)."""
    fd, tmp = tempfile.mkstemp(dir=str(pfad.parent),
                              prefix=pfad.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, dialect=_dialekt(AUSGABE_TRENNER),
                           lineterminator="\n")
            w.writerow(AUSGABE_KOPF)
            for m in messungen:
                w.writerow([m.datum.strftime("%d.%m.%Y"),
                            f"{m.stunde:02d}:{m.minute:02d}",
                            m.sys, m.dia,
                            m.puls if m.puls is not None else "",
                            m.notiz])
        os.replace(tmp, pfad)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def zeitraum(messungen: Sequence[Messung]) -> str:
    if not messungen:
        return "leer"
    tage = sorted(m.datum for m in messungen)
    return (f"{tage[0].strftime('%d.%m.%Y')} bis "
            f"{tage[-1].strftime('%d.%m.%Y')}")


def melde(name: str, pfad: Path, messungen: Sequence[Messung],
          probleme: Sequence[str], format_txt: str) -> None:
    print(f"\n{name}: {pfad.name}")
    print(f"  Format:   {format_txt}")
    print(f"  Gelesen:  {len(messungen)} Messungen ({zeitraum(messungen)})")
    for p in probleme[:10]:
        print(f"  [Hinweis] {p}")
    if len(probleme) > 10:
        print(f"  [Hinweis] ... {len(probleme) - 10} weitere Zeile(n) "
              f"mit demselben Problem")


# --------------------------------------------------------------------------
def bauen(basis_pfad: Path, app_pfad: Path, aus_pfad: Path,
          ab: Optional[date], probelauf: bool,
          an_ort_und_stelle: bool = False) -> int:
    print(f"bp_merge.py v{VERSION} -- Master neu aufbauen")
    if an_ort_und_stelle:
        print(f"Modus: {basis_pfad.name} wird an Ort und Stelle neu "
              f"geschrieben (Sicherungskopie wird angelegt)")

    basis, p_basis, f_basis = lies_messungen(basis_pfad)
    melde("Bestand", basis_pfad, basis, p_basis, f_basis)
    app, p_app, f_app = lies_messungen(app_pfad)
    melde("App-Export", app_pfad, app, p_app, f_app)

    if not basis:
        print("\n[FEHLER] Die Basis enthaelt keine auswertbaren Messungen.")
        return 1
    if not app:
        print("\n[FEHLER] Der App-Export enthaelt keine auswertbaren "
              "Messungen.")
        return 1

    # Stichtag bestimmen. Ohne --ab: der Tag nach der letzten Messung der
    # Basis. Das ist der Umstellungstag und aendert sich nicht mehr, sobald
    # die Basis eingefroren ist.
    if ab is None:
        ab = max(m.datum for m in basis) + timedelta(days=1)
        print(f"\nStichtag (automatisch): {ab.strftime('%d.%m.%Y')} "
              f"-- Tag nach der letzten Messung der Basis")
    else:
        print(f"\nStichtag (--ab): {ab.strftime('%d.%m.%Y')}")

    teil_basis = [m for m in basis if m.datum < ab]
    teil_app = [m for m in app if m.datum >= ab]
    basis_verworfen = len(basis) - len(teil_basis)
    app_verworfen = len(app) - len(teil_app)

    print(f"  aus der Basis:      {len(teil_basis)} Messungen "
          f"(Tage vor dem Stichtag)")
    if basis_verworfen:
        print(f"     [WARNUNG] {basis_verworfen} Messung(en) der Basis liegen "
              f"AM oder NACH dem Stichtag")
        print(f"               und werden nicht uebernommen. Fuer diese Tage "
              f"gilt allein der App-Export.")
    print(f"  aus dem App-Export: {len(teil_app)} Messungen "
          f"(Tage ab dem Stichtag)")
    if app_verworfen:
        print(f"                      ({app_verworfen} Messung(en) des "
              f"App-Exports liegen vor dem Stichtag")
        print(f"                      und stammen dort aus der Basis.)")

    if not teil_app:
        print("\n[WARNUNG] Der App-Export enthaelt keine Messung ab dem "
              "Stichtag.")
        if an_ort_und_stelle and not probelauf:
            print("[FEHLER] Abbruch: Beim Schreiben in dieselbe Datei wuerden "
                  "dadurch alle Messungen")
            print("         ab dem Stichtag geloescht. Stichtag und "
                  "App-Export pruefen.")
            return 1

    # Schutz vor einem veralteten App-Export: Enthaelt die Datei bereits
    # Tage ab dem Stichtag, die im Export fehlen, wuerden diese Messungen
    # beim Neuaufbau verlorengehen. Das passiert z. B., wenn versehentlich
    # ein aelterer Export gewaehlt wurde.
    vorhandene_app_tage = {m.datum for m in basis if m.datum >= ab}
    fehlende_tage = sorted(vorhandene_app_tage - {m.datum for m in teil_app})
    if fehlende_tage:
        print(f"\n[WARNUNG] {len(fehlende_tage)} Tag(e) ab dem Stichtag stehen "
              f"bereits in {basis_pfad.name},")
        print(f"          fehlen aber im App-Export: "
              f"{', '.join(t.strftime('%d.%m.%Y') for t in fehlende_tage[:8])}"
              f"{' ...' if len(fehlende_tage) > 8 else ''}")
        print(f"          Vermutlich ist der App-Export nicht der aktuelle.")
        if an_ort_und_stelle and not probelauf:
            print("[FEHLER] Abbruch: Diese Messungen wuerden geloescht.")
            return 1

    ergebnis = sorted(teil_basis + teil_app, key=lambda m: m.sortier)

    # Sicherheitsnetz: Dubletten koennen durch die taggenaue Trennung nicht
    # aus den beiden Quellen zusammen entstehen -- wohl aber innerhalb einer
    # Quelle. Deshalb wird hier trotzdem geprueft und gemeldet.
    gesehen = set()
    bereinigt: List[Messung] = []
    dubletten: List[Messung] = []
    for m in ergebnis:
        if m.identitaet in gesehen:
            dubletten.append(m)
            continue
        gesehen.add(m.identitaet)
        bereinigt.append(m)

    # Zeitstempel-Kollisionen mit abweichenden Werten sind ein Hinweis auf
    # nachtraeglich korrigierte Messungen und werden nur gemeldet.
    nach_zeit: Dict[Tuple, List[Messung]] = {}
    for m in bereinigt:
        nach_zeit.setdefault((m.datum, m.stunde, m.minute), []).append(m)
    kollisionen = {k: v for k, v in nach_zeit.items() if len(v) > 1}

    print("\n" + "-" * 58)
    print(f"Ergebnis: {len(bereinigt)} Messungen ({zeitraum(bereinigt)})")
    if dubletten:
        print(f"  [WARNUNG] {len(dubletten)} exakte Dublette(n) entfernt "
              f"(innerhalb einer Quelldatei):")
        for m in dubletten[:5]:
            print(f"            {m}")
        if len(dubletten) > 5:
            print(f"            ... und {len(dubletten) - 5} weitere")
    if kollisionen:
        print(f"  [WARNUNG] {len(kollisionen)} Zeitstempel mit abweichenden "
              f"Werten (moeglicherweise nachtraeglich korrigiert):")
        for _, v in list(kollisionen.items())[:5]:
            for m in v:
                print(f"            {m}")
    if not dubletten and not kollisionen:
        print("  Keine Dubletten, keine Zeitstempel-Konflikte.")

    if probelauf:
        print(f"\n[Probelauf] {aus_pfad.name} wurde NICHT geschrieben.")
        print("Die Datei saehe so aus (erste Zeilen):")
        print("  " + AUSGABE_TRENNER.join(AUSGABE_KOPF))
        for m in bereinigt[:2]:
            print(f"  {m.datum.strftime('%d.%m.%Y')};"
                  f"{m.stunde:02d}:{m.minute:02d};{m.sys};{m.dia};"
                  f"{m.puls if m.puls is not None else ''};{m.notiz}")
        return 0

    if an_ort_und_stelle:
        marke = datetime.now().strftime("%Y%m%d-%H%M%S")
        kopie = aus_pfad.with_name(aus_pfad.name + f".bak-{marke}")
        shutil.copy2(aus_pfad, kopie)
        print(f"\nSicherungskopie: {kopie.name}")

    schreibe_kanonisch(aus_pfad, bereinigt)

    # Nachkontrolle: die geschriebene Datei wieder einlesen und vergleichen.
    kontrolle, p_kontrolle, _ = lies_messungen(aus_pfad)
    if len(kontrolle) != len(bereinigt) or p_kontrolle:
        print(f"[FEHLER] Nachkontrolle: {len(kontrolle)} Messungen gelesen, "
              f"{len(bereinigt)} erwartet.")
        for p in p_kontrolle[:5]:
            print(f"         {p}")
        return 1
    if [m.identitaet for m in kontrolle] != [m.identitaet for m in bereinigt]:
        print("[FEHLER] Nachkontrolle: die geschriebene Datei stimmt "
              "inhaltlich nicht mit dem Ergebnis ueberein.")
        return 1

    print(f"\n[fertig] {aus_pfad.name} geschrieben "
          f"({len(bereinigt)} Messungen). Nachkontrolle bestanden.")
    print(f"         Weiter mit:  python3 bp_build.py <Name>")
    return 0


def personen_konfiguration() -> Optional[Dict]:
    """Liest die PERSONEN-Tabelle aus bp_build.py, falls vorhanden.

    So steht die Konfiguration an genau einer Stelle. Erwartet wird je Person:

        "Gerti": {
            "csv":   "iBP_Readings_Gerti.csv",
            "merge": {"app": "Gerti_App_Export.csv", "ab": "2026-08-09"},
            ...
        }

    Personen ohne "merge"-Eintrag brauchen keinen Neuaufbau -- ihre Datei
    kommt bereits gesamthaft aus der App (z. B. der iBP-Export von Erwin).
    """
    pfad = BASIS / "bp_build.py"
    if not pfad.exists():
        print(f"[FEHLER] bp_build.py nicht gefunden neben {Path(__file__).name}.")
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("bp_build_cfg", pfad)
        modul = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modul)
        return getattr(modul, "PERSONEN", None)
    except Exception as exc:                                    # noqa: BLE001
        print(f"[FEHLER] bp_build.py nicht auswertbar: {exc}")
        return None


def finde_app_datei(muster: Path) -> Optional[Path]:
    """Loest ein Dateimuster wie 'Blutdruck_*.csv' auf.

    Die App legt bei jedem Export einen neuen Dateinamen mit Datum an
    (z. B. Blutdruck_09_08_2026.csv). Ein fest eingetragener Name waere
    deshalb schon beim naechsten Export falsch. Mit einem Muster wird die
    zuletzt geaenderte passende Datei genommen; gibt es mehrere, werden
    alle Kandidaten mit Zeitstempel genannt, damit die Auswahl sichtbar ist.
    """
    text = str(muster)
    if not any(z in text for z in "*?["):
        return muster
    ordner = muster.parent if str(muster.parent) not in ("", ".") else BASIS
    treffer = sorted(ordner.glob(muster.name),
                     key=lambda p: p.stat().st_mtime, reverse=True)
    if not treffer:
        print(f"[FEHLER] Kein App-Export passt auf das Muster: {muster}")
        return None
    if len(treffer) > 1:
        print(f"Zum Muster {muster.name} passen {len(treffer)} Dateien:")
        for p in treffer:
            marke = datetime.fromtimestamp(p.stat().st_mtime).strftime(
                "%d.%m.%Y %H:%M")
            print(f"   {p.name:34} zuletzt geaendert {marke}")
        print(f"   -> verwendet wird die neueste: {treffer[0].name}")
    return treffer[0]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Vollstaendige Blutdruck-CSV neu aufbauen: Tage vor "
                    "dem Stichtag aus der bestehenden Datei, Tage ab dem "
                    "Stichtag aus dem kompletten App-Export.",
        epilog="Beispiel (eine einzige vollstaendige Datei):\n"
               "  python3 bp_merge.py --csv iBP_Readings_Gerti.csv \\\n"
               "                      --app Gerti_App_Export.csv \\\n"
               "                      --ab  2026-08-09\n"
               "  python3 bp_build.py Gerti\n",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--person", default=None, metavar="NAME",
                    help="Name aus der PERSONEN-Tabelle in bp_build.py "
                         "(z. B. Gerti). Holt Datei, App-Export und Stichtag "
                         "aus dem dortigen 'merge'-Eintrag. Personen ohne "
                         "diesen Eintrag brauchen keinen Neuaufbau.")
    ap.add_argument("--csv", type=Path, default=None,
                    help="Die vollstaendige CSV, z. B. iBP_Readings_Gerti.csv. "
                         "Sie liefert die Tage vor dem Stichtag und wird ohne "
                         "--aus an Ort und Stelle neu geschrieben.")
    ap.add_argument("--app", type=Path, default=None,
                    help="Vollstaendiger Export der Android-App.")
    ap.add_argument("--ab", default=None, metavar="DATUM",
                    help="Stichtag (Tag der Umstellung), z. B. 2026-08-09 "
                         "oder 09.08.2026. Pflicht beim Schreiben in dieselbe "
                         "Datei. Ohne --ab und mit --aus: der Tag nach der "
                         "letzten Messung in --csv.")
    ap.add_argument("--aus", type=Path, default=None,
                    help="Optionale abweichende Zieldatei. Ohne Angabe wird "
                         "--csv selbst neu geschrieben (mit Sicherungskopie).")
    ap.add_argument("--probelauf", action="store_true",
                    help="Nur pruefen und anzeigen, nichts schreiben.")
    ap.add_argument("--version", action="version",
                    version=f"bp_merge.py {VERSION}")
    args = ap.parse_args()

    csv_pfad, app_pfad, ab_text = args.csv, args.app, args.ab

    if args.person:
        personen = personen_konfiguration()
        if personen is None:
            return 1
        if args.person not in personen:
            print(f"[FEHLER] Person '{args.person}' steht nicht in "
                  f"bp_build.py. Bekannt: {', '.join(personen) or '(keine)'}")
            return 1
        cfg = personen[args.person]
        merge = cfg.get("merge")
        if not merge:
            print(f"Fuer '{args.person}' ist kein Neuaufbau konfiguriert "
                  f"(kein 'merge'-Eintrag in bp_build.py).")
            print(f"Die Datei {cfg.get('csv', '?')} kommt bereits gesamthaft "
                  f"aus der App und wird unveraendert verwendet.")
            print(f"Weiter mit:  python3 bp_build.py {args.person}")
            return 0
        # Explizite Kommandozeilenwerte haben Vorrang vor der Konfiguration.
        csv_pfad = csv_pfad or BASIS / cfg["csv"]
        app_pfad = app_pfad or BASIS / merge["app"]
        ab_text = ab_text or merge.get("ab")

    if csv_pfad is None or app_pfad is None:
        ap.error("Entweder --person angeben oder --csv und --app.")

    app_pfad = finde_app_datei(app_pfad)
    if app_pfad is None:
        return 1

    ab = None
    if ab_text:
        ab = parse_datum(ab_text)
        if ab is None:
            print(f"[FEHLER] Stichtag nicht lesbar: {ab_text!r} "
                  f"(erwartet z. B. 2026-08-09 oder 09.08.2026)")
            return 1

    ziel = args.aus if args.aus is not None else csv_pfad
    an_ort_und_stelle = ziel.resolve() == csv_pfad.resolve()

    if an_ort_und_stelle and ab is None:
        print("[FEHLER] Beim Schreiben in dieselbe Datei ist --ab Pflicht.")
        print("         Der Stichtag ist der Tag der Umstellung auf die App "
              "und bleibt immer derselbe,")
        print("         z. B. --ab 2026-08-09. Automatisch abgeleitet wuerde "
              "er nach jedem Lauf")
        print("         weiterwandern und die App-Daten einfrieren statt sie "
              "neu aufzubauen.")
        return 1
    if ziel.resolve() == app_pfad.resolve():
        print("[FEHLER] Das Ziel darf nicht der App-Export sein.")
        return 1

    return bauen(csv_pfad, app_pfad, ziel, ab, args.probelauf,
                 an_ort_und_stelle)


if __name__ == "__main__":
    raise SystemExit(main())
