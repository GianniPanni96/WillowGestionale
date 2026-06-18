# Willow Gestionale — v{{VERSION}}

Pacchetto di installazione di Willow Gestionale per Windows.

## Contenuto del pacchetto

| File / Cartella | Cosa contiene |
|---|---|
| `installer.exe` | Programma di installazione. **Lancia questo per installare il gestionale.** |
| `_internal/` | File di supporto dell'installer. Non rimuovere. |
| `WillowGestionale_X_Y.exe` | L'eseguibile del gestionale che verra' copiato nella cartella di installazione. |
| `Data/` | Risorse grafiche (icone, immagini). Vengono copiate nella cartella di installazione. |
| `Patches/` | Script di migrazione del database eseguiti in automatico se stai aggiornando da una versione precedente. |

## Come installare

1. Estrai tutto il contenuto dello zip in una cartella temporanea (es. Desktop).
2. Doppio click su **`installer.exe`**.
3. Scegli (oppure conferma quelli predefiniti):
   - **Percorso applicazione**: dove vivra' l'eseguibile. Predefinito: `C:\Program Files\WillowGestionale` (richiede conferma amministratore).
   - **Percorso dati**: dove vivranno database, backup e configurazioni. Predefinito: `%LOCALAPPDATA%\WillowGestionale` (non richiede privilegi).
4. Lascia attiva la spunta **Crea shortcut sul Desktop** se vuoi un collegamento.
5. Clicca **Installa**.

Se hai scelto un percorso applicazione diverso da quello predefinito, **riavvia il PC** al termine dell'installazione: serve perche' il gestionale legge il percorso da una variabile d'ambiente che viene aggiornata solo al login.

## Cosa fa l'installer

- Crea le cartelle applicazione e dati (`Books/`, `Backups/`).
- Inizializza il database SQLite con tutte le 12 tabelle del gestionale.
- Copia `WillowGestionale_X_Y.exe` e `Data/` nella cartella applicazione.
- Imposta le variabili d'ambiente `GESTIONALE_INSTALLATION_PATH` e `GESTIONALE_DB_PATH`.
- (Opzionale) crea uno shortcut sul Desktop.

Se hai gia' una versione precedente installata, l'installer:
- mantiene il tuo database e i tuoi dati;
- esegue automaticamente gli script di migrazione necessari per allineare lo schema alla versione corrente.

## Disinstallazione

Non c'e' un uninstaller dedicato. Per rimuovere completamente l'app:
1. Cancella la cartella applicazione (`C:\Program Files\WillowGestionale` o quella che hai scelto).
2. Cancella la cartella dati (`%LOCALAPPDATA%\WillowGestionale` o quella che hai scelto).
3. Rimuovi le variabili d'ambiente `GESTIONALE_INSTALLATION_PATH` e `GESTIONALE_DB_PATH` dal Pannello di controllo (`Sistema` → `Impostazioni di sistema avanzate` → `Variabili d'ambiente`).

## Risoluzione problemi

**L'installer non parte**: assicurati di aver estratto **tutto** il contenuto dello zip prima di lanciarlo. `installer.exe` ha bisogno della cartella `_internal/`, dell'exe del gestionale e delle cartelle `Data/` e `Patches/` accanto a se'.

**Il gestionale dice "Database non trovato"**: probabilmente il PC non e' stato riavviato dopo un'installazione in percorso custom, oppure la cartella dati e' stata spostata. Apri le variabili d'ambiente di sistema e controlla `GESTIONALE_DB_PATH`, poi riavvia.

**Il gestionale dice "mancano tabelle"**: rilancia `installer.exe` sul percorso applicazione corrente; quando ti chiede cosa fare del database esistente scegli **Sovrascrivi i dati** per ricreare lo schema da zero (perderai i dati attuali — fai un backup prima!).

## Log di installazione

L'installer scrive un log dettagliato in `%TEMP%\willow_installer_debug.log`. Allega questo file se devi segnalare un problema.
