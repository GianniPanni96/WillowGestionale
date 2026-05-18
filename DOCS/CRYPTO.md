# Come funziona la protezione dei dati in Willow Gestionale

Questo documento spiega in modo accessibile come l'app protegge i dati
sensibili degli utenti, cosa succede dietro le quinte quando esegui
determinate azioni nell'interfaccia, e perché il sistema è stato
progettato in questo modo.

---

## Il problema che stavamo cercando di risolvere

Willow salva alcune informazioni sensibili nel database — per esempio
le credenziali per accedere al provider di fatturazione elettronica
(nome utente e password Aruba). Il database è un semplice file `.db`
sul disco del PC. Chiunque riuscisse a copiare quel file potrebbe
aprirlo con qualsiasi strumento e leggerne il contenuto.

Per evitarlo, quei dati vengono **cifrati** prima di essere scritti
nel database: anche se qualcuno ruba il file, vede solo dati
incomprensibili senza la password giusta.

---

## Cos'è la cifratura e come funziona in questo contesto

**Cifrare** un dato significa trasformarlo in una sequenza di caratteri
senza senso usando un algoritmo matematico e una **chiave segreta**.
Solo chi conosce la stessa chiave può fare il processo inverso
(decifrare) e riottenere il dato originale.

L'app usa un algoritmo chiamato **AES-256-CBC**, uno standard
crittografico molto robusto usato anche da banche e governi. Il "256"
indica la lunghezza della chiave in bit: più è lunga, più è difficile
da indovinare con la forza bruta.

### Il problema della chiave: dove la tieni?

La difficoltà non è cifrare i dati — è decidere dove tenere la chiave.
Se la chiave è scritta nel codice dell'app (hardcoded), chiunque
smontasse l'eseguibile potrebbe trovarla e decifrare tutti i dati.

La soluzione che abbiamo scelto: **derivare la chiave dalla password
di login dell'utente**. La password non viene mai salvata nel database
in chiaro — viene usata solo come ingrediente per costruire la chiave
crittografica al momento del login. Se non conosci la password,
non puoi costruire la chiave, e senza la chiave i dati cifrati
sono inutilizzabili.

---

## PBKDF2: come si passa dalla password alla chiave

La password di un utente tipico è corta (es. `Margherita99`) e
prevedibile. Usarla direttamente come chiave AES sarebbe poco sicuro.
Invece usiamo un algoritmo chiamato **PBKDF2** (Password-Based Key
Derivation Function 2) che trasforma la password in una chiave robusta.

Come funziona PBKDF2 a grandi linee:

1. Prende la password e un valore casuale chiamato **salt** (vedi sotto).
2. Applica una funzione di hash crittografica (SHA-256) **600.000 volte
   in cascata**. Ogni iterazione riprende l'output della precedente.
3. Il risultato finale è una sequenza di 32 byte (= 256 bit) —
   questa è la chiave AES.

Il motivo delle 600.000 iterazioni è rallentare un eventuale
attaccante: anche avendo il file del database, per provare ogni
password possibile dovrebbe eseguire 600.000 calcoli per ciascuna —
rendendo un attacco a forza bruta proibitivamente lento.

### Cos'è il salt?

Il **salt** è una stringa di 16 byte generata casualmente la prima
volta che un utente imposta la password. Viene salvata nel database
nella colonna `crypto_salt`.

Serve a garantire che due utenti con la stessa password producano
chiavi diverse. Senza salt, un attaccante potrebbe precalcolare
una tabella di hash per le password più comuni (rainbow table) e
confrontarla con i dati del database. Con il salt, ogni utente ha
il suo "ingrediente segreto" aggiuntivo che rende inutili queste
tabelle precalcolate.

Il salt non è segreto in sé — anche se un attaccante lo vede, senza
la password non può ricostruire la chiave.

---

## Cosa viene cifrato e cosa no

**Viene cifrato nel database:**
- `username_provider` — il nome utente per il provider di fatturazione
- `password_provider` — la password per il provider di fatturazione

**Non viene cifrato** (ma protetto a livello di interfaccia):
- Reddito esterno, spese dedotte, acconti IRPEF/INPS — questi campi
  sono visibili solo nel dettaglio del proprio profilo, non di altri
  utenti. L'app li nasconde con un campo di tipo "password" e un toggle
  per mostrarli, ma nel database sono in chiaro.

La scelta di non cifrare questi ultimi è pragmatica: sono dati numerici
usati in calcoli fiscali continui, e cifrarli richiederebbe di
decifrarli ad ogni operazione, complicando molto il codice senza un
reale beneficio dato il contesto d'uso locale dell'app.

---

## La chiave non viene mai salvata su disco

Questo è il principio più importante del sistema: **la chiave AES
esiste solo in memoria RAM mentre l'utente è loggato**. Non viene mai
scritta su disco, nel database o in qualsiasi file.

- Al **login**: viene ricalcolata dalla password e tenuta in RAM
  nel servizio `UserCryptoService`.
- Al **logout** (o alla chiusura dell'app): viene cancellata dalla RAM.

Questo significa che anche se qualcuno ruba il database *e* il file
dell'app, non può decifrare i dati senza conoscere la password
dell'utente.

---

## Sessione persistente ("Mantieni l'accesso")

Al login è possibile attivare l'opzione **"Mantieni l'accesso dopo la
chiusura dell'app"**, che consente di riaprire l'app senza dover
reinserire la password per un intervallo di tempo configurabile
(da 5 a 60 minuti, in passi da 5).

### Come funziona

Abilitare l'opzione non fa nulla da sola: la chiave non viene salvata
nel momento in cui si attiva il checkbox.

Alla **chiusura dell'app**, se l'opzione era attiva, appare un popup
di conferma: "Vuoi rimanere loggato per N minuti?". Questo è il momento
in cui l'utente decide se procedere.

Se si risponde **Sì**:
1. La chiave AES attiva in RAM viene letta e serializzata in una
   struttura JSON che contiene anche il tipo di sessione, lo `user_id`
   e il timestamp di scadenza (`adesso + N minuti`).
2. La struttura JSON viene **cifrata con DPAPI** (Windows Data
   Protection API) prima di essere scritta su disco.
3. Il file cifrato viene salvato come `session.bin` nella stessa
   cartella degli altri file di configurazione (`storage_root`).

Se si risponde **No**, nessun file viene scritto (o eventuale file
precedente viene cancellato).

### Cos'è DPAPI e perché la usiamo

**DPAPI** è un servizio di Windows che cifra dati usando una chiave
derivata dalle credenziali dell'utente Windows corrente. In pratica:
il file `session.bin` può essere decifrato **solo dallo stesso utente
Windows sulla stessa macchina**. Nessun altro utente del PC, nessun
programma esterno, nessuno che copia solo il file può leggerlo.

Questo ci consente di salvare la chiave AES senza introdurre una
"master key hardcoded" nel codice: la protezione è delegata al sistema
operativo, che usa a sua volta le credenziali di accesso al PC.

Su macOS / Linux la persistenza della sessione è disabilitata
(i widget non compaiono nel dialog di login) perché non esiste un
equivalente di DPAPI su quelle piattaforme senza dipendenze aggiuntive.

### Cosa viene salvato nel file

Per un utente normale:
```
{
  "kind": "user",
  "user_id": 3,
  "crypto_key_hex": "<32 byte hex>",
  "expires_at": "2026-05-18T16:45:00"
}
```
*(tutto cifrato con DPAPI prima della scrittura — questo è solo lo schema del payload in chiaro)*

Per una sessione admin:
```
{
  "kind": "admin",
  "user_id": -1,
  "expires_at": "2026-05-18T16:45:00"
}
```
*(l'admin non ha una chiave AES da salvare)*

### All'avvio successivo

Prima di mostrare il dialog di login, l'app:
1. Controlla se esiste `session.bin`.
2. Tenta di decifrarlo con DPAPI.
3. Verifica che `expires_at` non sia nel passato.
4. Se tutto è valido: ripristina la sessione (utente → ricarica la
   chiave in RAM senza ricalcolarla; admin → segna la sessione admin
   come attiva) e apre direttamente l'app, saltando il dialog di login.
5. Se il file non esiste, è corrotto, o è scaduto: lo cancella e
   mostra il dialog di login normalmente.

### Quando la sessione persistente viene cancellata

- **Logout esplicito** (dal menu in alto a destra): cancella subito
  `session.bin`. Un logout è una revoca esplicita del consenso
  a restare loggati.
- **Scadenza naturale**: se al successivo avvio `expires_at` è già
  passato, il file viene cancellato prima del login.
- **Risposta "No" al popup di chiusura**: se l'utente aveva abilitato
  l'opzione ma alla chiusura risponde No, nessun file viene salvato.

### Limitazione di sicurezza da tenere presente

Salvare la chiave AES su disco — anche cifrata con DPAPI — è una
concessione di convenienza che riduce leggermente la sicurezza rispetto
al modello base "chiave solo in RAM". In particolare:

- Se qualcuno ottiene accesso alla sessione Windows dell'utente
  mentre `session.bin` è presente, potrebbe leggere la chiave.
- L'intervallo di tempo è breve per design: il valore massimo è 60
  minuti, e il timer parte dalla chiusura dell'app.

Per uso normale in un ambiente di fiducia (PC personale, ufficio) il
rischio è accettabile. In ambienti condivisi o non sicuri è
preferibile non usare questa opzione.

---

## Il crypto_check: come l'app sa che hai inserito la password giusta

Quando cifri qualcosa con una chiave sbagliata ottieni solo spazzatura —
l'algoritmo non dà errori, produce semplicemente dati privi di senso.
Quindi come fa l'app a sapere che la password inserita al login è
quella giusta, prima ancora di tentare di decifrare dati reali?

Al momento della creazione dell'utente, l'app cifra una frase fissa
nota ("Willow crypto check" — o simile) con la chiave derivata dalla
password, e salva il risultato cifrato nel database come `crypto_check`.

Al login:
1. L'app ricava la chiave dalla password inserita.
2. Decifra `crypto_check` con quella chiave.
3. Controlla che il risultato sia la frase fissa attesa.
4. Se corrisponde: password corretta, la chiave viene tenuta in RAM.
5. Se non corrisponde: password sbagliata, la chiave viene scartata.

---

## Il recovery code: cosa fare se dimentichi la password

Ogni volta che un utente imposta o cambia password, l'app genera
automaticamente un **recovery code** — un codice di 16 caratteri
diviso in 4 gruppi da 4, simile a questo: `WLLW-G35T-PASS-K3Y9`.

Questo codice viene mostrato **una volta sola** in una finestra
dedicata, con un pulsante "Copia" e un checkbox obbligatorio di
conferma ("Ho salvato il codice"). Dopo aver chiuso quella finestra,
il codice in chiaro non esiste più da nessuna parte — nemmeno nel
database. Nel database viene salvato solo il suo **hash** (una
"impronta digitale" non reversibile), che serve solo a verificare
se il codice inserito in futuro è corretto, senza dover conservare
il codice stesso.

### Come usarlo se dimentichi la password

Sul dialog di login c'è il link "Password dimenticata?". Cliccandolo
si apre una finestra dove inserisci il tuo recovery code e scegli
una nuova password. L'app verifica l'hash del codice, e se corrisponde
ti permette di reimpostare la password.

**Limitazione importante**: il reset via recovery code non recupera
le credenziali del provider di fatturazione che erano cifrate con la
vecchia password. Quelle vengono cancellate — dovrai reinserirle
manualmente. Questo è inevitabile: senza la vecchia password non c'è
modo di decifrarle, e nemmeno noi sviluppatori possiamo farlo.

**Se perdi sia la password che il recovery code**, i dati cifrati
di quell'utente sono persi per sempre. Non esiste backdoor.

---

## Cosa succede nei vari scenari dell'interfaccia

### Primo avvio dell'app (nessun utente nel database)
1. L'app rileva che il database è vuoto.
2. Si apre automaticamente la finestra di **configurazione iniziale**,
   che guida alla creazione del primo conto corrente e del primo
   utente con password obbligatoria.
3. Alla conferma, la password viene usata per generare salt e chiave,
   vengono creati `crypto_salt` e `crypto_check` nel database, e viene
   mostrato il recovery code.
4. L'utente è loggato automaticamente e l'app è pronta.

### Avvio normale (utenti già esistenti)
1. Se è presente una sessione persistente valida (`session.bin` non
   scaduto), l'app ripristina automaticamente la sessione — nessun
   dialog di login mostrato.
2. Altrimenti si apre il dialog di login (non si può chiudere con la
   X o con ESC, ma è presente il pulsante "Esci dall'app" per poter
   chiudere il programma senza fare il login).
3. Inserisci la password → l'app esegue PBKDF2, costruisce la chiave,
   verifica il `crypto_check`.
4. Se corretto: la chiave rimane in RAM, l'app si apre con il tuo
   profilo attivo.

### Logout
1. Clicchi su "Esegui il logout" nel menu dell'icona utente.
2. La chiave AES viene cancellata dalla RAM (`crypto_service.lock()`).
3. I dati sensibili non sono più accessibili finché non accade un
   nuovo login.

### Cambio password (dal dettaglio utente)
1. Inserisci la nuova password nel form e salvi.
2. L'app genera un **nuovo** salt casuale, ricalcola la chiave con
   la nuova password, aggiorna `crypto_salt` e `crypto_check`.
3. Le credenziali del provider vengono **svuotate** perché erano
   cifrate con la vecchia chiave — dovrai reinserirle.
4. Viene generato un **nuovo** recovery code, mostrato una volta sola.
5. Se stai cambiando la password del tuo utente loggato, la sessione
   in RAM viene aggiornata automaticamente (non devi fare un nuovo login).

### Creazione di un nuovo utente
1. Compili il form e (opzionalmente) inserisci una password.
2. Se inserisci la password: vengono creati salt, crypto_check e
   recovery code esattamente come al primo avvio.
3. Se non inserisci la password: l'utente viene creato senza capacità
   di login. Un amministratore dovrà impostargliela dal dettaglio utente
   prima che possa accedere.

### Primo login post-aggiornamento (installazioni esistenti)
L'app è stata aggiornata da una versione precedente che usava una
chiave condivisa hardcoded. Al primo login di un utente su un database
"vecchio":
1. L'app rileva che `crypto_salt` è vuoto (colonna aggiunta con la
   migrazione del database).
2. Genera un nuovo salt, costruisce la chiave dalla password inserita.
3. Decifra le credenziali del provider con la vecchia chiave condivisa
   (presente nel codice solo per questa migrazione).
4. Ricifra quelle credenziali con la nuova chiave per-utente.
5. Salva tutto. Da quel momento l'utente usa il nuovo sistema.
6. Nessuna azione manuale richiesta: l'utente non si accorge di nulla.

---

---

## L'amministratore di sistema

In aggiunta agli utenti normali, l'app prevede un **singolo
amministratore di sistema**. È un'entità separata dagli utenti: vive
nella propria tabella `admin` del database e non rappresenta una
persona che lavora nel gestionale, ma un ruolo tecnico per le
operazioni che vanno oltre il normale uso quotidiano.

### Cosa rende l'admin diverso da un utente normale

- **Non cifra dati propri**: non ha credenziali del provider di
  fatturazione, non ha campi sensibili da proteggere. Per questo nella
  tabella `admin` non esistono colonne `crypto_salt` o `crypto_check`,
  solo `password_login` (hash PBKDF2) e `recovery_hash`.
- **È sempre uno solo**: il codice rifiuta la creazione di un secondo
  admin. Niente "promote/demote" tra utenti — il ruolo è una colonna
  vuota o piena in una tabella separata, non un permesso da scambiare.
- **Non può "spiare" gli utenti**: l'admin non conosce le password
  degli utenti, quindi non può ricostruire le loro chiavi AES, quindi
  non può decifrare le loro credenziali del provider. I limiti
  crittografici valgono anche per lui.

### Cosa può fare l'admin

| Azione | Note |
|---|---|
| Impostare la password a un utente che non ne ha | Sblocca un utente esistente senza dati cifrati da perdere |
| Forzare un reset password a un utente esistente | L'utente potrà di nuovo loggarsi, ma le sue credenziali provider vengono svuotate (sono illeggibili senza la vecchia password) |
| Eliminare altri utenti | Operazione distruttiva, solo admin |
| Modificare/eliminare conti correnti | Sono dati che impattano tutti, solo admin |

Tutte le altre operazioni (creare clienti, fatture, ecc.) restano
accessibili agli utenti normali come prima.

### Flussi che coinvolgono l'admin

**Primo avvio dopo installazione**
1. L'app rileva che la tabella `admin` è vuota → si apre il
   `QTAdminCreateDialog`, dialog non chiudibile che chiede di
   impostare la password admin.
2. Viene generato un recovery code admin e mostrato una volta sola.
3. Dopodiché parte l'onboarding normale (creazione conto + primo
   utente).

**Primo avvio dopo aggiornamento (installazione esistente)**
1. Dopo aver eseguito lo script `fix_db/add_admin_table.py` (che
   crea la tabella admin nel database), al primo avvio dell'app si
   attiva lo stesso `QTAdminCreateDialog`.
2. Se nessuno degli utenti esistenti ha una password (caso di chi
   non l'aveva mai impostata): si apre il `QTFirstPasswordSetupDialog`
   che permette di scegliere uno degli utenti e impostargli la
   password. In alternativa, "Salta" e si entra direttamente come
   admin per gestire tutto da lì.

**Login come admin in qualsiasi momento**
- L'icona utente in alto a destra ha la voce "Login come
  amministratore" nel menu a tendina.
- Si apre il `QTAdminLoginDialog`: una sola riga password.
- Una volta autenticato, l'icona del corner cambia in `ADMIN.png`
  per dare un feedback visivo immediato.

**Logout admin**
- Funziona esattamente come per gli utenti normali: dal menu in alto
  a destra, "Esegui il logout". La sessione admin si chiude.

**Cosa succede se l'admin dimentica la password**
- Stesso meccanismo degli utenti: il dialog di login admin ha il
  link "Password admin dimenticata?" che apre il flusso di reset via
  recovery code. Verificato l'hash del recovery code, si imposta una
  nuova password admin e viene generato un nuovo recovery code.
- **Se l'admin perde sia la password che il recovery code**, l'unica
  via di uscita è eliminare manualmente la riga dalla tabella `admin`
  del database e ricrearlo al successivo avvio dell'app. Nessun dato
  utente viene perso in questo scenario (l'admin non cifra nulla).

---

## Tabella riassuntiva: da cosa siamo protetti (e da cosa no)

| Scenario | Protetti? | Perché |
|---|---|---|
| Qualcuno copia il file `.db` dal PC | Sì | I campi cifrati sono illeggibili senza la password utente |
| Qualcuno smonta l'eseguibile dell'app | Sì | Non c'è nessuna chiave hardcoded da estrarre |
| Compromissione delle credenziali di un utente | Parzialmente | Solo quell'utente è esposto, gli altri restano al sicuro |
| Password dimenticata, recovery code salvato | Sì | Si reimposta la password; le credenziali provider vanno reinserite |
| Password dimenticata, recovery code perso | No | I dati cifrati di quell'utente sono irrecuperabili |
| Keylogger attivo sul PC | No | Problema fuori dal nostro modello di sicurezza |
| Accesso alla RAM mentre l'utente è loggato | Rischio basso | La chiave è in RAM ma viene cancellata al logout |

---

## File coinvolti nel codice

Per chi volesse esplorare l'implementazione:

| File | Cosa fa |
|---|---|
| `OtherServices/User_crypto_service.py` | Cifratura/decifratura per-utente, decifrazione legacy |
| `OtherServices/User_auth_service.py` | Login utente + admin, sblocco sessione crypto, migrazione trasparente |
| `Controllerss/User_controller.py` | Gestione crypto e recovery code al salvataggio/aggiornamento utente |
| `Controllerss/Admin_controller.py` | Creazione/aggiornamento del singolo admin + reset via recovery |
| `QueryServices/Admin_query_service.py` | Lettura dell'admin (exists, password hash, recovery hash) |
| `Utils/Controller_utils.py` | Generazione e verifica del recovery code |
| `QTViews/MenuWindows/QT_login_dialog.py` | Finestra di login utente con link "Password dimenticata?" |
| `QTViews/MenuWindows/QT_admin_login_dialog.py` | Finestra di login admin |
| `QTViews/MenuWindows/QT_admin_create_dialog.py` | Dialog di creazione admin (primo avvio / post-update) |
| `QTViews/MenuWindows/QT_admin_recovery_reset_dialog.py` | Flusso "Password admin dimenticata?" |
| `QTViews/MenuWindows/QT_first_password_setup_dialog.py` | Bootstrap dialog per utenti esistenti senza password |
| `QTViews/MenuWindows/QT_onboarding_dialog.py` | Wizard di primo avvio (conto + primo utente) |
| `QTViews/MenuWindows/QT_recovery_code_show_dialog.py` | Finestra di consegna del recovery code |
| `QTViews/MenuWindows/QT_recovery_reset_dialog.py` | Flusso "Password dimenticata?" per utenti |
| `OtherServices/Session_persistence_service.py` | Salvataggio/caricamento sessione persistente cifrata con DPAPI |
| `MainQT.py` | Orchestrazione boot: ripristino sessione, creazione admin, onboarding, bootstrap password, login |
| `fix_db/add_crypto_columns_to_users_db.py` | Migrazione schema crypto utenti (installazioni esistenti) |
| `fix_db/add_admin_table.py` | Creazione tabella admin (installazioni esistenti) |
