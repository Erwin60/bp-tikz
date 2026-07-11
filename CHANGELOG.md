# Changelog

Alle nennenswerten Änderungen an diesem Projekt werden hier dokumentiert.
Format orientiert an *Keep a Changelog*; Versionierung nach *SemVer*.

## [1.2.8] – 2026-07

### Hinzugefügt
- `generate_bp_daytime_tikz.py`: Neue Seite **„Statistische Kennzahlen"**
  (nach `\clearpage`) mit einer Blutdruck-Kennzahlentabelle (immer aktiv):
  je Zeitraum (Gesamt/Morgen/Mittag/Abend) für systolisch und diastolisch
  Median, Q1–Q3, Min–Max, n, Anzahl Werte ≥ Vergleichsschwelle (135/85) und
  Spalte **„im Ziel"** = Anzahl Messungen *innerhalb* des Zielkorridors
  (konkrete Spanne in einer zweiten Kopfzeile; Erläuterung im
  Einleitungssatz und in der Fußnote).
- `--pulse` (Standard: aus): Puls-Auswertung auf der Statistik-Seite –
  Abb. 3 Puls-Tagesprofil (Median je Tageszeitblock, IQR-Band, punktierte
  Bradykardie-Schwellenlinie) plus Puls-Kennzahlenbox (Median, Q1–Q3,
  Min–Max, n, Anzahl < Schwelle) mit Interpretationshinweis und dem Hinweis,
  dass Blutdrucksenker den Puls senken können. Der Puls wird dazu als
  5. Tupelelement mit eingelesen (neuer `COL_ALIASES`-Eintrag `pulse`;
  iBP-Exporte liefern ihn bereits in der kanonischen Spalte `Puls`).
  Fehlt die Pulsspalte, erscheint ein sachlicher Hinweis statt eines Fehlers.
- `--pulse-low N` (Standard: 50): Bradykardie-Schwelle in 1/min für die
  Puls-Auswertung.
- `--fences` (Standard: aus): zeichnet je Säule in Abb. 2a/2b die **obere**
  Tukey-Grenze (Q3+1,5·IQR) als kurzen waagrechten Strich (`mark=-`,
  `mark size=4.5pt`); die Bildunterschrift erklärt, dass Werte oberhalb des
  Strichs die als Kreis markierten Ausreißer sind. Die dynamischen
  y-Achsengrenzen beziehen die Zäune mit ein.
- Präambel: `\usepackage{booktabs}` für die neuen Tabellen.
- `generate_bp_tikz.py`: `--trend` (Standard: aus) ergänzt ein
  **Langzeit-Trend-Diagramm** (Abbildung 3, im One-Page-Standalone auf
  eigener Seite): alle Tagesmediane als Punkte (keine Blockglättung) plus
  zentrierter gleitender Median (`--trend-window N`, Standard 7 Tage,
  kalenderbasiert) als Verlaufslinie, mit Monats-Ticks — für Halbjahres-
  und Jahresübersichten, bei denen das Tagesdiagramm zu dicht und längere
  Blöcke zu stark glättend wären.

### Geändert
- `generate_bp_tikz.py`: Die Datumslabels des Wochendiagramms werden ab
  elf Blöcken automatisch um 45° rotiert und verkleinert (vorher
  überlappten sie ab ca. 11–12 Wochen); bis zehn Blöcke bleibt die Ausgabe
  byte-identisch. Damit bleibt das Wochendiagramm bis zu einem vollen Jahr
  (52 Blöcke) bei 7-Tage-Auflösung lesbar.
- Abstand zwischen Abb. 2a und 2b auf `\\[9mm]` vergrößert; die
  BP-Kennzahlentabelle liegt deshalb (zusammen mit der Puls-Auswertung) auf
  der eigenen Seite „Statistische Kennzahlen", damit die beiden
  vollformatigen Wochentag-Diagramme lesbar groß bleiben und die
  Statistik-Seite auf eine Seite passt.

## [1.2.6] – 2026-07

### Behoben
- `generate_bp_daytime_tikz.py`: Balken konnten unsichtbar bleiben, wenn ein
  Median ausserhalb der fest kodierten y-Achsengrenzen lag (z. B. ein
  niedriger systolischer Sonntag-Mittag-Median unter der bisherigen
  Untergrenze von 110 mmHg wurde abgeschnitten, waehrend der zugehoerige
  diastolische Balken sichtbar blieb). Die y-Achsengrenzen von Abb. 2a/2b
  werden nun datenabhaengig bestimmt und umfassen alle Mediane, Ausreisser,
  den Zielkorridor und die Vergleichsschwelle.

### Geändert
- `--date-from` ist in `generate_bp_tikz.py` jetzt optional (vorher Pflicht).
  Ohne Angabe werden alle Messungen ab dem frühesten Datum ausgewertet,
  konsistent zu `generate_bp_daytime_tikz.py`. Damit verarbeiten beide
  Skripte bei gleichem Aufruf dieselbe Datenmenge.

### Hinzugefügt
- Warnung in beiden Skripten, wenn das automatisch ermittelte früheste
  Messdatum mehr als 90 Tage vor der nächsten Messung liegt (typischer
  Hinweis auf einen Datums-Tippfehler wie ein falsches Jahr).
- Automatische Normalisierung des iBP-Export-CSV („streamlining") in beiden
  Skripten. Das iBP-Format legt Datum und Uhrzeit als zwei komma-getrennte
  Felder ab, wodurch jede Datenzeile ein Feld mehr als die Kopfzeile hat und
  Messungen bisher falsch zugeordnet oder verworfen werden konnten. Das Format
  wird nun an seiner Signatur (Spalten „Mean Arterial Pressure"/„Pulse
  Pressure" plus überzählige Feldzahl) erkannt und vor der eigentlichen
  Verarbeitung in ein kanonisches CSV überführt. Normale (z. B. aus Excel
  exportierte) CSVs bleiben unverändert. Siehe README, Abschnitt
  „Eingabeformat und iBP-Normalisierung".

### Behoben
- Fehlende bzw. falsch zugeordnete Messwerte (u. a. einzelne Wochentag-Blöcke
  im Tageszeit-Diagramm) bei direkter Verwendung eines unveränderten
  iBP-Exports.

## [1.2.5] – 2026-07

### Hinzugefügt
- `generate_bp_tikz.py`: konfigurierbarer Zielkorridor über
  `--corridor sys_lo-sys_hi/dia_lo-dia_hi` (z. B. `110-119/70-79` für einen
  aneurysmaspezifisch niedrigeren Korridor). Ohne Angabe bleibt der bisherige
  ESC-Standardkorridor (120–129/70–79) unverändert. Ein abweichender Korridor
  wird in Legende, Referenzabsatz und Bildunterschrift als individuell
  gewählt gekennzeichnet und zusätzlich als sichtbarer Hinweis in beide
  Diagramme eingeblendet, damit er nicht übersehen wird. Optionales
  `--corridor-label` für die Kurzbezeichnung.
- `generate_bp_daytime_tikz.py`: dieselbe `--corridor` /
  `--corridor-label`-Unterstützung, konsistent zum Haupt-Skript. Der Korridor
  wirkt auf das Tagesprofil (Abb. 1) und die Wochentag-Diagramme (Abb. 2a/2b);
  bei abweichendem Korridor wird der Methodik-Text angepasst und ein
  sichtbarer Hinweis in Abb. 1 eingeblendet.

## [1.2.4] – 2026-07

### Behoben
- `generate_bp_daytime_tikz.py`: In den unteren Diagrammen überdeckte die
  Legende den x-Achsentitel (Abb. 1b „Uhrzeit [h]", Abb. 2b „Wochentag").
  Der vertikale Legendenversatz hängt jetzt davon ab, ob ein Achsentitel
  vorhanden ist, sodass Titel und Legende getrennt stehen.

### Geändert
- Beispiel-Namen in Doku und Skript-Hilfen von Adam/Eva verwendet
  (zuvor andere Vornamen).

### Ergänzt (Release-Assets)
- Beispiel-PDFs des Tageszeit-×-Wochentag-Diagramms in Farbe und
  Schwarz-Weiß (`fig_weekday_daytime_color.pdf`,
  `fig_weekday_daytime_bw.pdf`) neu erzeugt aus `bp_anon_example.csv`,
  mit korrigierter Legendenplatzierung. Die früheren, fehlerhaften
  Beispiele wurden ersetzt.
- Einzelfiguren des Tages-/Wochendiagramms (`fig1`–`fig4b`) als farbige
  Referenz beigelegt.

## [1.2.3] – 2026-06

### Hinzugefügt
- `--name NAME` in **beiden** Skripten: stellt allen Ausgabedateien einen
  Präfix voran, um mehrere Personen zu unterscheiden
  (`--name Eva` → `Eva_bp_diagrams.tex`,
  `Eva_bp_diagrams_both_onepage_standalone.tex`,
  `Eva_bp_weekday_daytime.tex`, …). Ein explizit gesetzter Pfad
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
