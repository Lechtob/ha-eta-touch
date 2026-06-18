# ETA Touch for Home Assistant

HACS-faehige Home-Assistant-Integration fuer ETA Touch Heizkessel.

## Installation

1. Dieses Repository als HACS Custom Repository vom Typ `Integration` hinzufuegen.
2. Integration installieren.
3. Home Assistant neu starten.
4. `Einstellungen > Geraete & Dienste > Integration hinzufuegen > ETA Touch` auswaehlen.

## Konfiguration

Der Config Flow fragt:

- Host/IP des ETA Touch Geraets.
- Port, normalerweise `8080`.
- Polling-Intervall in Sekunden.
- Eine Sensorliste, eine Variable pro Zeile.

Sensorzeilen koennen so aussehen:

```text
Kesseltemperatur=112/10021/0/0/12150
112/10021/0/0/12112
```

Die URIs koennen aus `/user/menu` und `/user/varinfo/<uri>` ermittelt werden.

## Status

Dies ist ein erster Projekt-Schnitt. Sensoren und aktive Fehler sind umgesetzt. Selects,
Switches und Services fuer schreibbare Variablen sollten auf Basis von `/user/varinfo`
als naechste Features folgen.

## Repository Setup

Empfohlene GitHub-Repo-Einstellungen:

- Repository-Name: `ha-eta-touch`
- Default Branch: `main`
- Develop Branch: `develop`
- HACS Kategorie: `Integration`
- Home-Assistant-Domain: `eta_touch`

Initialer Push in ein leeres Repo:

```powershell
git init
git add .
git commit -m "Initial ETA Touch Home Assistant integration"
git branch -M main
git remote add origin https://github.com/<user>/ha-eta-touch.git
git push -u origin main
git switch -c develop
git push -u origin develop
```

## Dependency Hinweis

`custom_components/eta_touch/manifest.json` referenziert aktuell
`py-etatouch-restful==0.1.0`. Fuer HACS-Installationen muss diese Version auf PyPI
verfuegbar sein oder waehrend der fruehen Entwicklung lokal in Home Assistant
installiert werden.
