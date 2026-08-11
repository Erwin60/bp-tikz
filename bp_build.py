#!/usr/bin/env python3
"""Kompletter Blutdruck-Aufbereitungslauf in einem Durchgang (a-Shell/macOS).

Aufruf:   python3 bp_build.py Eva
          python3 bp_build.py Adam
          python3 bp_build.py Eva Adam         (beide nacheinander)
          python3 bp_build.py --alle           (alle konfigurierten Personen)
          python3 bp_build.py --liste          (zeigt die Konfiguration)
          python3 bp_build.py Eva --keep-aux   (Hilfsdateien behalten)
          python3 bp_build.py Adam --kein-merge (Merge-Schritt ueberspringen)

Der Ausgabeordner ergibt sich aus dem Namen: 'Eva' schreibt nach Eva/,
'Adam' nach Adam/. Die Generator-Skripte legen den Ordner selbst an.

Die Tabelle PERSONEN unten ist eine VORLAGE mit zwei Beispielpersonen. Sie
wird fuer den eigenen Gebrauch angepasst; echte Namen, Dateinamen und
medizinische Angaben gehoeren nicht in ein oeffentliches Repository.

Nach erfolgreichem Lauf werden die LaTeX-Hilfsdateien (.aux, .log, .out ...)
im Ausgabeordner geloescht; im Fehlerfall bleiben sie zur Diagnose erhalten.

Merge-Schritt (neu)
-------------------
Personen, deren CSV aus zwei Quellen besteht, bekommen einen 'merge'-Eintrag.
Vor den Generatoren laeuft dann bp_merge.py und baut die CSV neu auf:

    CSV = Bestand (Tage VOR dem Stichtag) + App-Export (Tage AB dem Stichtag)

Der App-Export enthaelt jedes Mal den kompletten Bestand der App. Weil die
Tage ab dem Stichtag immer vollstaendig aus dem Export uebernommen werden,
koennen keine Dubletten entstehen, und der Lauf ist beliebig wiederholbar.

Personen ohne 'merge'-Eintrag -- deren CSV also bereits gesamthaft aus einer
App kommt -- laufen unveraendert wie bisher.

Warum ein Python-Skript und keine Befehlsliste:
In a-Shell kehrt der Prompt teilweise zurueck, bevor der vorherige Prozess
seine Dateien vollstaendig geschrieben hat. Beim Einfuegen mehrerer Zeilen
startet pdflatex dann auf einer noch nicht fertigen .tex-Datei. subprocess.run()
wartet dagegen garantiert auf das Prozessende, und wir pruefen zusaetzlich, ob
die erwarteten Dateien wirklich existieren.

Ausserdem funktioniert 'jump' nur in der interaktiven Shell; hier werden die
Verzeichnisse stattdessen direkt als Pfade gesetzt.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Personen-Konfiguration
# ---------------------------------------------------------------------------
# Pro Person werden die beiden Generator-Aufrufe getrennt konfiguriert, weil
# sie sich in Datum, Stil und Optionen unterscheiden koennen.
#
#   "trend"   -> generate_bp_tikz.py
#   "daytime" -> generate_bp_daytime_tikz.py
#
# Die Werte sind exakt die Kommandozeilen-Argumente, jeweils als Liste. Was
# nicht gebraucht wird, laesst man einfach weg (z. B. hat Gerti beim Trend-
# Aufruf bewusst keinen Korridor und kein --trend).
#
# --csv und --name werden automatisch ergaenzt und duerfen hier fehlen.
#
# Optional "merge" -> bp_merge.py, laeuft VOR den Generatoren:
#
#   "merge": {"app": "Blutdruck_*.csv", "ab": "2026-08-09"}
#
#     "app" Dateiname des App-Exports. Weil die App den Exportnamen mit dem
#           Datum versieht (Blutdruck_09_08_2026.csv), wird hier ein Muster
#           eingetragen; bp_merge.py nimmt die neueste passende Datei.
#     "ab"  Stichtag = Tag der Umstellung auf die App. Bleibt fuer immer
#           derselbe und darf NICHT mitwandern.
#
# Neue Person: einfach einen weiteren Eintrag anlegen.
PERSONEN = {
    # Beispiel 1: Die CSV kommt gesamthaft aus einer App (kein "merge").
    "Eva": {
        "csv": "Eva_readings.csv",
        "trend": [
            "--date-from", "15.05.2026",
            "--show-daily-n",
            "--week-outliers",
            "--trend",
            "--trend-edge-policy", "symmetric",
        ],
        "daytime": [
            "--date-from", "2026-05-15",
            "--style", "bw",
            "--pulse",
            "--pulse-low", "50",
            "--fences",
        ],
    },
    # Beispiel 2: Bestand bis zum Vortag der Umstellung, ab dem Stichtag
    # kommen die Daten aus einer neuen App -> "merge".
    "Adam": {
        "csv": "Adam_readings.csv",
        "merge": {
            "app": "Blutdruck_*.csv",
            "ab": "2026-08-09",
        },
        "trend": [
            "--date-from", "15.06.2026",
            "--show-daily-n",
            "--week-outliers",
        ],
        "daytime": [
            "--date-from", "2026-06-15",
            "--style", "color",
            "--pulse",
            "--pulse-low", "50",
            "--fences",
        ],
    },
}

# Basis = Ordner, in dem dieses Skript liegt (enthaelt CSV + Generator-Skripte)
BASE = Path(__file__).resolve().parent


def build_commands(name: str, cfg: dict) -> tuple[list, list]:
    """Baut die beiden Python-Aufrufe fuer die angegebene Person."""
    trend = ([sys.executable, "generate_bp_tikz.py",
              "--csv", cfg["csv"], "--name", name]
             + list(cfg.get("trend", [])))
    daytime = ([sys.executable, "generate_bp_daytime_tikz.py",
                "--csv", cfg["csv"], "--name", name]
               + list(cfg.get("daytime", [])))
    return trend, daytime


def merge_command(cfg: dict) -> list:
    """Baut den bp_merge.py-Aufruf aus dem 'merge'-Eintrag der Person.

    Die Zieldatei wird nicht gesondert angegeben: ohne --aus schreibt
    bp_merge.py in dieselbe Datei zurueck und legt vorher eine
    Sicherungskopie an.
    """
    merge = cfg["merge"]
    return [sys.executable, "bp_merge.py",
            "--csv", cfg["csv"],
            "--app", merge["app"],
            "--ab", merge["ab"]]


def tex_jobs(name: str) -> list[tuple[str, int]]:
    """Die drei LaTeX-Dokumente mit Personen-Praefix, je zwei Durchlaeufe."""
    return [
        (f"{name}_bp_diagrams_standalone_two_sides.tex", 2),
        (f"{name}_bp_diagrams_both_onepage_standalone.tex", 2),
        (f"{name}_bp_weekday_daytime.tex", 2),
    ]


# ---------------------------------------------------------------------------
def run(cmd: list[str], cwd: Path, label: str,
        zeige_ausgabe: bool = False) -> None:
    """Fuehrt einen Befehl aus und bricht bei Fehler sofort ab.

    Mit zeige_ausgabe=True wird die Ausgabe direkt durchgereicht statt
    eingesammelt. Das wird fuer den Merge-Schritt genutzt, dessen Zahlen
    und Warnungen man auch bei erfolgreichem Lauf sehen will.
    """
    print(f"\n=== {label} ===")
    print("    " + " ".join(str(c) for c in cmd))
    print(f"    (in {cwd})")

    t0 = time.time()
    if zeige_ausgabe:
        print()
        proc = subprocess.run(cmd, cwd=str(cwd))
    else:
        # errors="replace" ist notwendig: pdflatex gibt gesetzten Text im
        # Log wieder und schreibt Umlaute dabei als 8-Bit-Byte (z. B. 0xfc
        # fuer "tagsueber"). Mit der Voreinstellung text=True/strict wirft
        # subprocess dann UnicodeDecodeError -- und zwar erst nachdem
        # pdflatex bereits erfolgreich war. Ob es auftritt, haengt vom
        # Zeilenumbruch im Log ab, der Fehler tritt daher nur sporadisch auf.
        proc = subprocess.run(cmd, cwd=str(cwd),
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    dt = time.time() - t0

    if proc.returncode != 0:
        print(f"[FEHLER] {label} -- Exit-Code {proc.returncode}")
        if not zeige_ausgabe:
            # Bei pdflatex die relevanten Fehlerzeilen zeigen, nicht das ganze Log
            out = (proc.stdout or "") + (proc.stderr or "")
            errs = [ln for ln in out.splitlines() if ln.startswith("!")]
            if errs:
                print("  Erste LaTeX-Fehler:")
                for ln in errs[:5]:
                    print("   ", ln)
            else:
                print(out[-1500:])
        sys.exit(1)

    print(f"[ok] {label}  ({dt:.1f}s)")


def require(path: Path, label: str) -> None:
    """Stellt sicher, dass eine erwartete Datei existiert."""
    if not path.exists():
        print(f"[FEHLER] Erwartete Datei fehlt: {path}")
        print(f"         ({label} hat sie nicht erzeugt)")
        sys.exit(1)
    size = path.stat().st_size
    print(f"       -> {path.name} ({size:,} Bytes)")


# Hilfsdateien, die pdflatex erzeugt und die nach dem Lauf nicht mehr
# gebraucht werden. .pdf und .tex bleiben selbstverstaendlich erhalten.
AUX_SUFFIXES = (".aux", ".log", ".out", ".toc", ".lof", ".lot",
                ".nav", ".snm", ".vrb", ".fls", ".fdb_latexmk",
                ".synctex.gz", ".bbl", ".blg")


def cleanup(directory: Path) -> None:
    """Loescht LaTeX-Hilfsdateien im angegebenen Ordner."""
    print(f"\n=== Aufraeumen in {directory.name}/ ===")
    removed = []
    for entry in sorted(directory.iterdir()):
        if not entry.is_file():
            continue
        if entry.name.endswith(AUX_SUFFIXES):
            try:
                entry.unlink()
                removed.append(entry.name)
            except OSError as exc:
                print(f"    [Warnung] {entry.name} nicht loeschbar: {exc}")

    if removed:
        print(f"    {len(removed)} Hilfsdatei(en) geloescht:")
        for name in removed:
            print(f"      - {name}")
    else:
        print("    Keine Hilfsdateien vorhanden.")


def build_person(name: str, cfg: dict, keep_aux: bool,
                 kein_merge: bool = False) -> None:
    """Kompletter Lauf fuer eine Person: ggf. mergen, Grafiken, LaTeX."""
    outdir = BASE / name

    print("\n" + "#" * 60)
    print(f"#  {name}")
    print("#" * 60)

    # --- CSV aus Bestand und App-Export neu aufbauen -----------------------
    # Muss vor der Existenzpruefung der CSV laufen, damit auch ein erster
    # Aufbau moeglich waere. Die Ausgabe von bp_merge.py wird durchgereicht,
    # weil dort Zahlen und Warnungen stehen, die man sehen will.
    if cfg.get("merge") and not kein_merge:
        run(merge_command(cfg), BASE,
            f"{name}: CSV neu aufbauen (bp_merge.py)", zeige_ausgabe=True)
    elif cfg.get("merge") and kein_merge:
        print("\n(Merge-Schritt uebersprungen: --kein-merge; "
              f"{cfg['csv']} wird unveraendert verwendet)")

    csv_path = BASE / cfg["csv"]
    if not csv_path.exists():
        print(f"[FEHLER] CSV nicht gefunden: {csv_path}")
        sys.exit(1)

    trend_cmd, daytime_cmd = build_commands(name, cfg)
    jobs = tex_jobs(name)

    # --- Grafiken erzeugen -------------------------------------------------
    run(trend_cmd, BASE, f"{name}: Verlaufsgrafiken (generate_bp_tikz.py)")
    run(daytime_cmd, BASE,
        f"{name}: Tageszeit-Auswertung (generate_bp_daytime_tikz.py)")

    # --- Pruefen, dass die .tex-Dateien wirklich da sind --------------------
    print(f"\n=== Erzeugte LaTeX-Dateien ({name}) ===")
    for tex, _ in jobs:
        require(outdir / tex, "Python-Schritt")

    # --- LaTeX kompilieren -------------------------------------------------
    for tex, passes in jobs:
        for i in range(1, passes + 1):
            run(["pdflatex", "-interaction=nonstopmode",
                 "-halt-on-error", tex],
                outdir, f"{name}: pdflatex {tex}  (Durchlauf {i}/{passes})")
        require(outdir / tex.replace(".tex", ".pdf"), "pdflatex")

    # --- Hilfsdateien entfernen --------------------------------------------
    # Erst hier, nachdem alle Laeufe erfolgreich waren: im Fehlerfall bricht
    # das Skript vorher ab und die .log-Datei bleibt zur Diagnose erhalten.
    if keep_aux:
        print("\n(Aufraeumen uebersprungen: --keep-aux)")
    else:
        cleanup(outdir)

    print(f"\n[fertig] {name}: PDFs liegen in {outdir}")


def pruefe_merge_konfiguration(auswahl: list[str]) -> bool:
    """Prueft die 'merge'-Eintraege, bevor irgendetwas laeuft."""
    ok = True
    for name in auswahl:
        merge = PERSONEN[name].get("merge")
        if not merge:
            continue
        fehlend = [s for s in ("app", "ab") if not merge.get(s)]
        if fehlend:
            print(f"[FEHLER] {name}: 'merge' ist unvollstaendig, es fehlt: "
                  f"{', '.join(fehlend)}")
            ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Blutdruck-Aufbereitung: CSV ggf. neu aufbauen, "
                    "Grafiken erzeugen und LaTeX-Dokumente kompilieren.",
        epilog="Beispiele:  python3 bp_build.py Eva\n"
               "            python3 bp_build.py Adam\n"
               "            python3 bp_build.py Eva Adam\n"
               "            python3 bp_build.py --alle\n"
               "            python3 bp_build.py Adam --kein-merge",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("personen", nargs="*", metavar="NAME",
                    help="Name(n) der zu verarbeitenden Person(en). "
                         f"Verfuegbar: {', '.join(PERSONEN)}")
    ap.add_argument("--alle", action="store_true",
                    help="Alle konfigurierten Personen nacheinander.")
    ap.add_argument("--keep-aux", action="store_true",
                    help="LaTeX-Hilfsdateien (.aux, .log ...) behalten.")
    ap.add_argument("--kein-merge", action="store_true",
                    help="Den Merge-Schritt ueberspringen und die vorhandene "
                         "CSV unveraendert verwenden (z. B. um die PDFs neu "
                         "zu bauen, ohne einen neuen App-Export zu haben).")
    ap.add_argument("--liste", action="store_true",
                    help="Konfigurierte Personen anzeigen und beenden.")
    args = ap.parse_args()

    if args.liste:
        print("Konfigurierte Personen:")
        for name, cfg in PERSONEN.items():
            vorhanden = "ok" if (BASE / cfg["csv"]).exists() else "CSV fehlt!"
            print(f"  {name:10} {cfg['csv']:28} [{vorhanden}]")
            merge = cfg.get("merge")
            if merge:
                treffer = sorted(BASE.glob(merge["app"]))
                if treffer:
                    stand = f"{len(treffer)} Datei(en), neueste: " \
                            f"{max(treffer, key=lambda p: p.stat().st_mtime).name}"
                else:
                    stand = "kein Export gefunden!"
                print(f"  {'':10} Merge: App-Export {merge['app']} "
                      f"ab {merge['ab']}  [{stand}]")
            else:
                print(f"  {'':10} Merge: nicht konfiguriert "
                      f"(CSV kommt gesamthaft aus der App)")
        return 0

    # Auswahl bestimmen
    if args.alle:
        auswahl = list(PERSONEN)
    elif args.personen:
        auswahl = args.personen
    else:
        ap.print_help()
        print(f"\nKeine Person angegeben. Verfuegbar: {', '.join(PERSONEN)}")
        return 1

    # Namen pruefen, bevor irgendetwas laeuft
    unbekannt = [n for n in auswahl if n not in PERSONEN]
    if unbekannt:
        print(f"[FEHLER] Unbekannte Person(en): {', '.join(unbekannt)}")
        print(f"         Verfuegbar: {', '.join(PERSONEN)}")
        print("         Neue Person im Abschnitt PERSONEN ergaenzen.")
        return 1

    if not pruefe_merge_konfiguration(auswahl):
        return 1

    # Generator-Skripte pruefen
    skripte = ["generate_bp_tikz.py", "generate_bp_daytime_tikz.py"]
    # bp_merge.py nur verlangen, wenn es auch gebraucht wird
    if not args.kein_merge and any(PERSONEN[n].get("merge") for n in auswahl):
        skripte.append("bp_merge.py")
    for script in skripte:
        if not (BASE / script).exists():
            print(f"[FEHLER] Skript nicht gefunden: {BASE / script}")
            print("         Liegt bp_build.py im richtigen Ordner?")
            return 1

    print("Blutdruck-Aufbereitung -- Komplettlauf")
    print(f"Basis:     {BASE}")
    print(f"Personen:  {', '.join(auswahl)}")

    t0 = time.time()
    for name in auswahl:
        build_person(name, PERSONEN[name], args.keep_aux, args.kein_merge)

    print("\n" + "=" * 60)
    print(f"Alle Laeufe abgeschlossen ({time.time() - t0:.1f}s): "
          f"{', '.join(auswahl)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
