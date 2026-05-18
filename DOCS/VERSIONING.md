# Versionamento e rilasci

Questo progetto usa **Semantic Versioning** (`MAJOR.MINOR.PATCH`) con tag git
come unica fonte di verita'. Il numero di versione viene **calcolato
automaticamente** dai messaggi di commit (Conventional Commits) e applicato come
tag annotato da una GitHub Action.

## Branch model

| Branch          | Ruolo                                                        |
| --------------- | ------------------------------------------------------------ |
| `master`        | Branch di release. Ogni merge qui produce una nuova versione |
| `Development`   | Branch di lavoro. Stabile-ish, base per le feature           |
| `feature/<x>`   | Branch effimeri, partono da `Development`                    |

Flusso tipico:
```
feature/foo  -->  Development  -->  master  -->  tag + release
                                    ^^^^^^^
                                    PR "Squash and merge"
```

## Conventional Commits

Il **tipo di commit** decide il salto di versione:

| Prefisso              | Esempio                                          | Bump da 1.3.2 → |
| --------------------- | ------------------------------------------------ | --------------- |
| `fix:`                | `fix: pulsante salva non funziona`               | **1.3.3**       |
| `perf:`               | `perf: query clienti piu' veloce`                | **1.3.3**       |
| `feat:`               | `feat: nuovo report IVA trimestrale`             | **1.4.0**       |
| `feat!:` / `fix!:`    | `feat!: nuovo schema DB (rottura compat)`        | **2.0.0**       |
| `BREAKING CHANGE:` in footer | (qualsiasi tipo + footer)                 | **2.0.0**       |
| `chore: docs: refactor: style: test: build: ci:` | (varie)               | nessun bump     |

Esempio di breaking change in footer:
```
feat: nuovo formato export CSV

BREAKING CHANGE: il vecchio formato non e' piu' leggibile.
```

## Workflow di rilascio

### Sviluppo quotidiano
1. `git checkout Development && git pull`
2. `git checkout -b feature/qualcosa`
3. Commit liberi (anche "wip", "save before lunch" — non finiranno in master)
4. Push e PR `feature/qualcosa -> Development`, **Merge normale**
5. Test su Development

### Quando vuoi rilasciare
1. Apri PR `Development -> master` su GitHub
2. **"Squash and merge"** con un messaggio in formato Conventional Commits
   (es. `feat: aggiunti grafici report mensile e fix CSV import`)
3. Al merge, l'action `release.yml` calcola la versione e crea:
   - tag annotato `vX.Y.Z`
   - commit di changelog
   - GitHub Release (senza binari)
4. Su un PC di build:
   ```powershell
   git checkout master
   git pull --tags
   .\release.ps1                # builda e carica l'exe nella Release
   ```

### Build di test (senza rilascio)
Su Development o feature branch:
```powershell
git pull --tags
pyinstaller MainQT_noconsole.spec
```
L'exe sara' nominato `WillowGestionale_<major>_<minor>.exe` e i metadati
Windows riporteranno una versione di sviluppo (es. `1.3.0+dev.5.gabc1234`).

## Versione nell'exe

- **Nome file**: `WillowGestionale_<MAJOR>_<MINOR>.exe`
  (es. `WillowGestionale_1_3.exe` — sempre troncato a 2 cifre come richiesto)
- **Dettagli file di Windows** (tasto destro -> Proprieta' -> Dettagli):
  Product Version e File Version contengono la versione completa
  (`1.3.0` per release, `1.3.0+dev.5.gabc1234` per build off-tag).

## Override manuale della versione

Solo per emergenze (es. ricreare un build storico):
```powershell
$env:WILLOW_VERSION = "1.2.7"
pyinstaller MainQT_noconsole.spec
```

## Bootstrap iniziale

Eseguito una volta sola per inizializzare il versionamento moderno:
```powershell
git checkout master
git tag -a v1.0.0 -m "Baseline semantic versioning"
git push Willow_gestionale_origin v1.0.0
```
