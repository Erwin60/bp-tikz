# `generate_bp_daytime_tikz.py` — Handbuch (DE)

Begleitwerkzeug zu `generate_bp_tikz.py`. Es untersucht **tageszeit- und
wochentagsabhängige** Muster im häuslichen Blutdruck und erzeugt ein
**eigenständig kompilierbares** LaTeX/PGFPlots-Dokument (A4) mit zwei
Abbildungen.

> **Hinweis.** Dies ist ein Visualisierungswerkzeug, **kein** Diagnosesystem.
> Die eingezeichneten Schwellen (ESC-Korridore, HBPM-Vergleichslinien) sind
> allgemeine Orientierungslinien, **keine** individuellen Zielwerte. Die
> Festlegung individueller Zielwerte obliegt der behandelnden Ärztin bzw. dem
> behandelnden Arzt.

---

## Was wird erzeugt?

- **Abbildung 1 — Tagesprofil:** Median je Tageszeitblock (systolisch und
  diastolisch) über alle Tage, mit schattierten **IQR**-Bändern (25.–75.
  Perzentil), den grau hinterlegten **ESC-Korridoren** (120–129 systolisch,
  70–79 diastolisch) und den punktierten **HBPM-Vergleichslinien** 135/85.
- **Abbildung 1b — Stunden-Histogramm:** Anzahl der Messungen je Stunde (0–23),
  eingefärbt nach Tageszeitblock, mit gestrichelten Blockgrenzen. Zeigt die
  Messverteilung über den Tag (Abdeckung der Tageskinetik) und damit, wie
  belastbar die Tagesgang-Aussage ist.
- **Abbildung 2 — Wochentag × Tageszeit:** gruppierte Median-Balken je Wochentag
  und Block (2a systolisch, 2b diastolisch), mit **Tukey-Ausreißern** (Kreis =
  nach oben, optional `×` = nach unten), ESC-Korridor und Vergleichslinie.
- **Statistische Kennzahlen (eigene Seite):** eine Blutdruck-Kennzahlentabelle je
  Zeitraum (Gesamt/Morgen/Tag/Abend/Nacht), für systolisch und diastolisch getrennt —
  Median, Q1–Q3, Min–Max, Anzahl der Messungen `n`, Anzahl Werte ab der
  Vergleichsschwelle (≥ 135/≥ 85) und die Spalte **„im Ziel"** (Messungen
  *innerhalb* des Zielkorridors).
- **Abbildung 4 — 24-Stunden-Profil (eigene Seite):** je voller Tagesstunde 0–23
  der Median als Marker mit **IQR-Whisker** (Q1–Q3), systolisch und diastolisch
  getrennt. Leere Stunden bleiben als Lücke sichtbar; eine dünne Linie verbindet
  nur unmittelbar aufeinanderfolgende Stunden (keine Interpolation über messfreie
  Stunden). Darunter eine **Kennzahlentabelle je Stunde** über alle 24 Stunden
  (Median, Q1–Q3, Min–Max, `n`; Stunden ohne Messung mit „–"), messungsbezogen
  über den Zeitraum. Abschaltbar mit `--no-hourly`.
- **Puls-Auswertung (`--pulse`, letzte Seite):** Abb. 3 Puls-Tagesprofil (Median je
  Block, IQR-Band, punktierte Bradykardie-Schwellenlinie) plus Kennzahlenbox —
  als eigener Abschnitt am **Dokumentende**.

Die Kopfzeile nennt automatisch den **Auswertungszeitraum** (von–bis) und die
Anzahl der Messungen/Tage. Der Interpretationshinweis am Fuß wird vollständig aus
den Daten berechnet (Block-Mediane, Trendaussage, Wochentagsspanne, Ausreißer,
Messverteilung je Block). Die Datenlage-Hinweise sind datengetrieben: Sie nennen
automatisch den schwächsten Block und wechseln zu einer „gleichmäßig abgedeckt"-
Formulierung, sobald die Belegung ausgewogen ist.

### Beispielausgabe

Aus der anonymisierten Beispiel-CSV (`examples/bp_anon_example.csv`) erzeugte
Beispieldokumente liegen im Ordner `examples/`:

- [`examples/fig_weekday_daytime_bw.pdf`](../examples/fig_weekday_daytime_bw.pdf)
  — Schwarz-Weiß-Variante (`--style bw`)
- [`examples/fig_weekday_daytime_color.pdf`](../examples/fig_weekday_daytime_color.pdf)
  — Farbvariante (`--style color`)

Beide zeigen auf mehreren Seiten das Tagesprofil (Abb. 1), das Stunden-Histogramm
(Abb. 1b) und die Wochentagsauswertung (Abb. 2a/2b), gefolgt von der Seite
„Statistische Kennzahlen" und der Seite „Stündliche Auswertung" mit dem
24-Stunden-Profil (Abb. 4) und der Kennzahlentabelle je Stunde (ohne `--pulse`
erzeugt; mit `--pulse` käme eine abschließende Seite „Puls-Auswertung" hinzu).

---

## Tageszeitblöcke

Vier Blöcke, gesteuert über `--blocks "m,d,e,n"`:

- **Morgen:** Stunde `m` bis `< d`
- **Tag:** Stunde `d` bis `< e`
- **Abend:** Stunde `e` bis `< n`
- **Nacht:** sonst (`≥ n` oder `< m`) — läuft über Mitternacht

Standard: `6,10,18,22` (Nacht 22:00–06:00, Morgen 06:00–10:00, Tag 10:00–18:00,
Abend 18:00–22:00). Die Beschriftungen in Legende, Titel und Methodik passen
sich automatisch an. Nachtmessungen fallen dadurch in einen eigenen Block statt
in „Morgen".

---

## Eingabeformat

Mindestens **Datum**, **systolischer** und **diastolischer** Wert; zusätzlich
wird eine **Uhrzeit** benötigt. Diese wird – in dieser Reihenfolge – gesucht in:

1. einer eigenen Zeit-/Uhrzeit-Spalte (`Time`/`Zeit`),
2. der **Note-Spalte** (manche Programme wie iBP legen die Uhrzeit dort ab),
3. einem Zeitstempel im Datumsfeld (`2026-05-15 07:30`).

Spaltennamen werden über deutsche/englische Aliase erkannt; das Trennzeichen
(Komma/Semikolon/Tab) und Dezimalkomma werden automatisch erkannt. Zusatzspalten
(Pulse, Weight, Mean Arterial Pressure, …) werden ignoriert. Zwei- und
vierstellige Jahre sowie AM/PM-Uhrzeiten werden unterstützt.

```csv
Date,Time,Systolic,Diastolic,Pulse
2026-05-15,07:00,118,66,66
2026-05-15,13:00,124,68,66
2026-05-15,20:10,128,72,63
```

Auch das iBP-Format, bei dem die Uhrzeit in der `Note`-Spalte steht, wird
verarbeitet.

---

## Optionen

| Option | Pflicht | Standard | Zweck |
|---|---|---|---|
| `--csv CSV` | nein | `bp.csv` | Eingabedatei mit den Messungen. |
| `--style color\|bw` | nein | `color` | Farb- oder Schwarz-Weiß-Variante. |
| `--blocks "m,d,e,n"` | nein | `6,10,18,22` | Grenzen der vier Tageszeitblöcke (Stunden; Nacht läuft über Mitternacht). |
| `--outliers up\|both\|none` | nein | `up` | Tukey-Ausreißer: nur oben / oben+unten / keine. |
| `--pulse` | nein | aus | Puls-Auswertung als eigener Abschnitt am Dokumentende (Abb. 3 + Kennzahlenbox). |
| `--no-hourly` | nein | aus | Unterdrückt die stündliche Auswertung (24-Stunden-Profil Abb. 4 + Kennzahlentabelle je Stunde). |
| `-o`, `--out OUT` | nein | `bp_weekday_daytime.tex` | Name der Ausgabedatei. |

Die vollständige Optionsliste (u. a. `--corridor`, `--corridor-label`,
`--pulse-low`, `--fences`, `--name`, `--date-from`/`--date-to`) steht in
[`optionen_daytime.csv`](optionen_daytime.csv).

**Schwarz-Weiß (`--style bw`):** Graustufen + Muster (Morgen solide, Tag
nordost-schraffiert, Abend punktiert, Nacht kreuzschraffiert); im Tagesprofil systolisch durchgezogen,
diastolisch gestrichelt. Der ESC-Korridor ist **schraffiert mit gestricheltem
Rand** dargestellt, damit er sich klar von den flächig grauen IQR-Bändern
abhebt.

**Ausreißer (Tukey):** ein Wert gilt als Ausreißer, wenn er oberhalb von
`Q3 + 1,5·IQR` (oben) oder unterhalb von `Q1 − 1,5·IQR` (unten) liegt. Sie werden
nur bestimmt, wenn je Zelle mindestens **vier** Messungen vorliegen und der
Interquartilsabstand nicht entartet ist (`IQR ≥ 1 mmHg`) — das verhindert
Pseudo-Ausreißer bei nahezu identischen Werten. Standard `up`, weil beim
Blutdruck die Spitzen meist die klinisch relevanten sind.

---

## Aufrufvarianten

### 1. Minimal (Farbe, Standardblöcke)

```bash
python3 generate_bp_daytime_tikz.py --csv bp_raw.csv --style color
```

Erzeugt `bp_weekday_daytime.tex` (eigenständig mit `pdflatex` kompilierbar).

### 2. Schwarz-Weiß für den Druck

```bash
python3 generate_bp_daytime_tikz.py --csv bp_raw.csv --style bw \
  -o bp_weekday_daytime_bw.tex
```

### 3. Eigene Tageszeitfenster und Tief-Ausreißer

```bash
python3 generate_bp_daytime_tikz.py --csv bp_raw.csv \
  --blocks 5,9,17,21 --outliers both
```

### 4. iBP-Export (Uhrzeit in der Note-Spalte)

```bash
python3 generate_bp_daytime_tikz.py --csv iBP_Readings.csv --style color
```

---

## Kompilieren

```bash
pdflatex bp_weekday_daytime.tex
```

Eine Passage genügt. Das Dokument benötigt `tikz`, `pgfplots`
(`compat=1.18`) und in der S/W-Variante die TikZ-Bibliothek `patterns`
(automatisch eingebunden).

---

## Diagnose

Schlägt das Einlesen fehl, gibt das Skript eine **Diagnose** aus: erkannter
Spaltentrenner, zugeordnete Spalten, Anzahl gelesener Zeilen, Fehlschläge je Feld
(Systolisch/Diastolisch/Datum/Uhrzeit) sowie die erste nicht verarbeitbare Zeile.
Damit lässt sich ein abweichendes Datums- oder Uhrzeitformat schnell eingrenzen.
