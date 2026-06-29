# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.
Format orientiert an *Keep a Changelog*; Versionierung nach *SemVer*.

## [1.2.3] – 2026-06

### Hinzugefügt
- `--name NAME` in **beiden** Skripten: stellt allen Ausgabedateien einen
  Präfix voran, um mehrere Personen zu unterscheiden
  (`--name Gerti` → `Gerti_bp_diagrams.tex`,
  `Gerti_bp_diagrams_both_onepage_standalone.tex`,
  `Gerti_bp_weekday_daytime.tex`, …). Ein explizit gesetzter Pfad
  (`--out`, `--standalone-out`, `--two-sides-out`) hat Vorrang vor dem
  präfigierten Standardnamen.
- `--help`-Beispiele in beiden Skripten (u. a. Zwei-Personen-Aufruf).

### Geändert
- README beschreibt beide Skripte gemeinsam inklusive `--name`.
- Optionstabellen aktualisiert: `docs/optionen_bp_tikz.csv` (mit `--name`),
  `docs/optionen_daytime.csv` (mit `--name`).

## [1.2.x] – früher

### Hinzugefügt
- Wochen-Mittellinie wählbar über `--week-central mean|median`
  (Standard `mean`, anschlussfähig an HBPM/ESC-Mittelwertschwellen;
  `median` konsistent zur IQR-Box und robuster gegen Ausreißertage).
- Ausreißertage im Wochendiagramm über `--week-outliers` (mit
  konfigurierbaren Schwellen `--week-outlier-sys-hi/-dia-hi` und optionalen
  unteren Schwellen).
- One-Page-Standalone als echte A4-Seite, deren Diagramme die verfügbare
  Höhe automatisch ausfüllen.
- Tageszeit-×-Wochentag-Diagramm (`generate_bp_daytime_tikz.py`) mit
  `--style color|bw`, konfigurierbaren Blöcken `--blocks "a,b"`,
  `--outliers up|both|none` und Datumsfilter `--date-from` / `--date-to`.

## [1.1.0] – früher

### Hinzugefügt
- Datumsfilter `--date-from` / `--date-to` (beide inklusive); der Kopf des
  Diagramms zeigt den tatsächlich ausgewerteten Zeitraum.
- Drei konfigurierbare Tageszeit-Blöcke via `--blocks "a,b"`.

## [1.0.0] – Erstveröffentlichung

### Hinzugefügt
- `generate_bp_tikz.py`: Tagesdiagramm (Median + Spannweite) und
  verdichtetes 7-Tage-Diagramm (IQR der Tagesmediane + Verlaufslinie),
  LaTeX/PGFPlots, Fragment + Standalone-Ausgaben, optionale Statistik-CSVs.
