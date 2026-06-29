# GitHub – fertige Befehle

Copy-paste-fertige Befehle, um den Ordner `bp-tikz/` als GitHub-Repository
anzulegen bzw. ein bestehendes Repo zu aktualisieren. Ausführen aus dem
Verzeichnis `bp-tikz/`.

## 0. Einmalig: GitHub-Anmeldung (Device-Code-Flow)

```bash
gh auth login
# -> GitHub.com -> HTTPS -> "Login with a web browser"
# Den angezeigten 8-stelligen Code unter https://github.com/login/device eingeben.
```

Prüfen:

```bash
gh auth status
```

## A. Neues Repository anlegen und ersten Stand pushen

```bash
cd bp-tikz

git init
git add .
git commit -m "bp-tikz: Blutdruck-Diagramm-Generatoren (Tages/Wochen + Tageszeit x Wochentag)

- generate_bp_tikz.py: Tages- und 7-Tage-Diagramme, One-page-Standalone (A4),
  --week-central mean|median, --week-outliers
- generate_bp_daytime_tikz.py: Tageszeit x Wochentag, Farbe/SW
- --name Praefix in beiden Skripten zur Unterscheidung mehrerer Personen
- Optionstabellen in docs/"

gh repo create bp-tikz --private --source=. --remote=origin --push
```

Für ein öffentliches Repo `--private` durch `--public` ersetzen.

## B. Bestehendes Repository aktualisieren

```bash
cd bp-tikz

git add -A
git commit -m "Add --name to both scripts; help examples; docs update"
git push
```

Falls das Remote noch fehlt:

```bash
git remote add origin https://github.com/<DEIN_USER>/bp-tikz.git
git branch -M main
git push -u origin main
```

## C. Update über heruntergeladene Einzeldateien (ZIP)

Wenn du neue Versionen der Skripte heruntergeladen hast und in ein bereits
geklontes Repo übernehmen willst:

```bash
cp ~/Downloads/generate_bp_tikz.py          ./generate_bp_tikz.py
cp ~/Downloads/generate_bp_daytime_tikz.py  ./generate_bp_daytime_tikz.py
cp ~/Downloads/optionen_bp_tikz.csv         ./docs/optionen_bp_tikz.csv
cp ~/Downloads/optionen_daytime.csv         ./docs/optionen_daytime.csv

git add -A
git commit -m "Update scripts and option tables"
git push
```

## Hinweise

- Die `.gitignore` schließt generierte LaTeX/PDF-Dateien **und** echte
  Messdaten (`*_Readings*.csv`) bewusst aus. Lade keine realen
  Gesundheitsdaten hoch; im Repo liegt nur `examples/example_readings.csv`
  mit synthetischen Werten.
- Vor dem ersten Push mit `git status` prüfen, dass keine persönlichen CSVs
  oder PDFs aufgenommen werden – besonders bei einem öffentlichen Repo.
