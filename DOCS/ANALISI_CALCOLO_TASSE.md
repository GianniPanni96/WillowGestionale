# Analisi del calcolo e della visualizzazione delle tasse (P. IVA nel collettivo)

> Documento di revisione tecnica/fiscale generato il 2026-05-25.
> Scope: funzioni di **previsione tasse** mostrate nel pannello *Dettaglio Utente*
> (`PREVISIONE TASSE`) e nella tab *Tasse* (`Previsione Tasse <Collettivo>`).
> Confronto tra le logiche implementate e il report fiscale di riferimento
> (`ExternalContextForAIAgents/Calcolo Tasse p. iva 2025`) + le regole in
> `ExternalContextForAIAgents/fiscal_rules.json`.

---

## 0. Mappa dei componenti coinvolti

| Livello | File | Ruolo |
|--------|------|------|
| Calcolo | `AnalyzerServices/User_analyzer_service.py` | Tutte le funzioni di calcolo/retrieving tasse |
| Calcolo (a monte) | `AnalyzerServices/Invoice_analyzer_service.py` | Compone `TOT_DOCUMENTO`, `IMPONIBILE`, `RITENUTA` delle fatture |
| Config | `ConfigManagers/config_models.py` | Parsing di `fiscal_rules.json` (scaglioni, aliquote) |
| View dettaglio | `QTViews/Details/QT_user_detail_view.py` | Sezioni `DATI FISCALI`, `PREVISIONE TASSE`, `IVA TRIMESTRALE` + tooltip |
| View aggregata | `QTViews/QT_taxes_view.py` | Tab Tasse: saldi/acconti e ripartizione IRPEF/INPS per utente |

Funzioni di calcolo centrali:
- `calculate_previsione_tasse_ordinaria` (`User_analyzer_service.py:345`)
- `calculate_previsione_tasse_forfettaria` (`User_analyzer_service.py:205`)
- `calculate_previsione_tasse_willow` (`User_analyzer_service.py:560`) — aggrega le quote "collettivo" per la tab Tasse
- `_calcola_irpef` (`User_analyzer_service.py:626`) — IRPEF a scaglioni marginali

---

## 1. Sintesi esecutiva (cosa è corretto / cosa no)

**Impianto generalmente corretto:**
- L'IRPEF ordinaria è calcolata **a scaglioni marginali** in modo corretto (`_calcola_irpef`, `User_analyzer_service.py:626-650`): somma `parte_scaglione × aliquota` scaglione per scaglione, con gestione di `+Infinity` per l'ultimo scaglione. Coerente col report.
- La **deducibilità dei contributi INPS dalla base IRPEF** è implementata correttamente per l'ordinaria (`base_irpef = reddito_netto − inps`, riga 374). Coerente col report (reddito imponibile IRPEF = reddito − contributi).
- La **ritenuta d'acconto** viene sottratta dall'IRPEF lorda per ottenere l'IRPEF netta (riga 376), e l'eventuale credito è "azzerato" ai fini del versamento (`max(0, …)`), coerente col report ("con imposta netta ≤ 0 non si versa").
- La meccanica **saldo + acconti** (40%/60% IRPEF, 80% INPS in due rate del 50%) rispecchia i parametri di `fiscal_rules.json` e del report.

**Errori / criticità rilevati** (dettaglio nelle sezioni successive):

| # | Severità | Area | Sintesi |
|---|----------|------|---------|
| E1 | 🔴 ALTA | Ordinaria – base imponibile | La base ricavi usa `TOT_DOCUMENTO` che **include l'IVA** → INPS e IRPEF sovrastimate |
| E2 | 🔴 ALTA | Forfettaria – aliquota | Bug di **doppia sottrazione** nell'anno di attività → quasi sempre applicata l'aliquota 15% anche nei primi 5 anni (dovrebbe essere 5%) |
| E3 | 🔴 ALTA | Forfettaria – imposta | I **contributi INPS non vengono dedotti** dalla base dell'imposta sostitutiva → imposta sostitutiva sovrastimata (diverge dal report) |
| E4 | 🟠 MEDIA | Ripartizione collettivo | La quota IRPEF "Willow" usa un metodo **ibrido** (proporzionale + marginale) che può sovra-attribuire l'IRPEF al collettivo |
| E5 | 🟠 MEDIA | Forfettaria – cassa | Le fatture **non incassate** sono incluse nel fatturato forfettario (principio di cassa violato), mentre l'ordinaria le esclude |
| E6 | 🟡 BASSA | Versamenti ordinaria | La **seconda rata acconto INPS** (novembre) manca dalla ripartizione per scadenza |
| E7 | 🟡 BASSA | Forfettaria – base | `reddito_esterno` sommato **senza coefficiente** di redditività + `TOT_DOCUMENTO` forfettario include rivalsa 4% e rimborsi |
| E8 | 🟡 BASSA | INPS Gestione Separata | Mancano **minimale/massimale** contributivo |
| E9 | 🟡 BASSA | Coerenza dati | `tooltip` e `DATI FISCALI` mostrano un'aliquota forfettaria che **diverge** da quella effettivamente usata nel calcolo (conseguenza di E2) |
| E10 | ⚪ INFO | Manutenibilità | `calcola_aliquota_tax_ordinaria` / `calcola_reddito_tot_utente` sono **codice morto** |

---

## 2. Regime ORDINARIO — analisi del calcolo

Funzione: `calculate_previsione_tasse_ordinaria` (`User_analyzer_service.py:345-558`).

### Flusso implementato
```
ricavi_totali          = fatturato_willow + reddito_esterno
spese_totali           = spese_willow + spese_esterne
reddito_netto          = ricavi_totali − spese_totali
inps                   = reddito_netto × 0,2607
base_irpef             = reddito_netto − inps          # INPS deducibile ✔
irpef_lorda            = scaglioni(base_irpef)         # marginale ✔
irpef_netta            = irpef_lorda − ritenuta        # può essere < 0 ✔
totale_tasse           = inps + max(0, irpef_netta)
```
Questa catena è **concettualmente corretta** e aderente al secondo esempio del report (€60k ricavi, €30k spese, ritenute 20%).

### 🔴 E1 — La base ricavi include l'IVA (errore grave)
`fatturato_willow` deriva da `calcola_tot_fatturato_utente` (`:40`), che somma il campo **`TOT_DOCUMENTO`** delle fatture.
Ma in `Invoice_analyzer_service.py:300`:
```python
tot_documento = imponibile + cassa_inps + iva + tot_rimborsi
```
Quindi `TOT_DOCUMENTO` è il **lordo documento, IVA inclusa**. Usarlo come "ricavo" ai fini IRPEF/INPS è errato: l'IVA è un debito verso l'Erario, non reddito.

**Effetto numerico**: con IVA al 22%, la base ricavi è gonfiata di circa il 22% (più cassa e rimborsi). Di conseguenza **INPS e IRPEF risultano entrambe sovrastimate** in modo significativo per ogni P. IVA ordinaria.

**Fix consigliato**: usare il campo **`IMPONIBILE`** (esiste già: `Gestionale_Enums.py:249`, valorizzato in fattura) come base imponibile, oppure il metodo `calculate_FATTURATO_NETTO_IVA` (`Invoice_analyzer_service.py:140`, = `tot_documento − iva`) già presente nell'analyzer fatture. Va deciso se la base deve includere la cassa INPS/rivalsa e i rimborsi spese (vedi nota E7): per la pura base IRPEF/INPS dei compensi professionali, lo standard è l'imponibile dei compensi, al netto di IVA e rimborsi spese ex art. 15.

### Note minori ordinaria
- **Ritenuta vs incassato**: `fatturato_willow` esclude le fatture non pagate (`include_unpaid_invoices=False`, riga 353), ma `calcola_tot_ritenuta_acconto_ordinaria` (`:115`) **non** filtra sull'incassato → la ritenuta può includere fatture non ancora incassate, disallineando ricavi e ritenute. Allineare i due perimetri escludendo le fatture non saldate.
- **Credito IRPEF perso**: se `irpef_netta < 0` (credito da ritenute), il credito viene azzerato (`max(0, …)`) e non compensa l'INPS. È coerente col report ("rimborso o compensazione" separati), ma nella realtà F24 il credito IRPEF è compensabile con l'INPS: è una **semplificazione prudenziale**, da documentare all'utente.

---

## 3. Regime FORFETTARIO — analisi del calcolo

Funzione: `calculate_previsione_tasse_forfettaria` (`User_analyzer_service.py:205-343`).

### 🔴 E2 — Bug di doppia sottrazione sull'aliquota agevolata
La funzione `calcola_aliquota_tax_forfettaria(anno_apertura_piva)` (`:124-133`) si aspetta **l'anno di apertura** della P. IVA e calcola internamente:
```python
anni_di_attivita = current_year - int(anno_apertura_piva)
```
Ci sono **due chiamate con semantica incoerente**:
- ✔ corretta — `pick_fiscal_data_by_user_id` (`:186`): passa `anno` = anno di apertura (es. `2020`).
- ✖ errata — dentro il calcolo tasse (`:231-233`):
  ```python
  aliquota_irpef = self.calcola_aliquota_tax_forfettaria(
      int(datetime.today().date().year) - anno_apertura   # passa GIÀ gli anni di attività
  )
  ```
  Qui viene passato `2026 − 2020 = 6` (anni di attività), ma la funzione lo tratta come *anno di apertura* e ricalcola `2026 − 6 = 2020`. Poiché `2020 < 5` è falso, **ritorna sempre l'aliquota massima (15%)**.

**Effetto**: una P. IVA forfettaria nei primi 5 anni, che dovrebbe avere l'aliquota agevolata **5%**, viene tassata al **15%** nel calcolo della previsione. (Nel pannello `DATI FISCALI`, che usa la chiamata corretta, vede invece il 5% → vedi E9, incoerenza tra le due sezioni della stessa schermata.)

**Fix**: passare `anno_apertura` (l'anno) anche alla riga 231, oppure uniformare la firma della funzione a "anni di attività". Va scelta **una** convenzione e applicata a entrambe le chiamate.

### 🔴 E3 — Contributi INPS non dedotti dall'imposta sostitutiva
Implementazione attuale (righe 236-242):
```python
reddito_willow = fatturato_willow × coefficiente_imponibile
reddito_tot    = reddito_willow + reddito_esterno
irpef = reddito_tot × aliquota_irpef      # nessuna deduzione INPS
inps  = reddito_tot × aliquota_inps
```
Il report di riferimento (sezione forfettario) prescrive invece:
> Imposta = (reddito imponibile − contributi INPS) × 15%

Esempio del report: imponibile 23.400 €, INPS 6.100 € → base imposta 17.300 € → imposta 2.595 € (non 3.510 €).
**Il gestionale non deduce l'INPS** e quindi **sovrastima l'imposta sostitutiva** (nell'esempio, +35% circa). Questa è una divergenza esplicita dal documento fiscale fornito.

> Nota: la deduzione dei contributi nel forfettario avviene per cassa (anno di versamento) ed è un'opzione del contribuente; va deciso se modellarla. Ma poiché il report la applica, il comportamento attuale va quantomeno reso configurabile/documentato.

### 🟡 E7 — Composizione della base forfettaria
- `reddito_esterno` viene sommato **dopo** il coefficiente (`reddito_tot = reddito_willow + reddito_esterno`, riga 237): il reddito esterno **non** riceve il coefficiente di redditività. Va chiarito se `reddito_esterno` è già un *reddito imponibile* (allora ok) o un *fatturato esterno* (allora andrebbe moltiplicato per il coefficiente). Il tooltip (vedi §5) lo descrive come "Fatturato totale × Coefficiente", il che è fuorviante.
- `fatturato_willow` forfettario usa `TOT_DOCUMENTO` che per il forfettario (`Invoice_analyzer_service.py:317`) = `imponibile + rivalsa_inps(4%) + rimborsi`. Il report precisa che i contributi vanno calcolati sul **compenso**, non sulla rivalsa. Quindi la base è leggermente gonfiata da rivalsa e rimborsi.

### 🟡 E5 — Principio di cassa (incoerenza tra regimi)
`calcola_tot_fatturato_utente` ha default `include_unpaid_invoices=True`. Il forfettario lo chiama col default (riga 211 → **include le non incassate**), mentre l'ordinaria forza `False` (riga 353). Sia il forfettario sia il professionista ordinario sono tassati **per cassa** (incassato): il forfettario non dovrebbe includere le fatture non incassate. Uniformare a `False` (o rendere esplicita la scelta) per entrambi.

### 🟡 E8 — Minimale/massimale Gestione Separata
Il modello applica un'aliquota INPS piatta sul reddito, senza il **minimale** (~4.837 €) né il **massimale** (~120.607 €) della Gestione Separata. Per redditi molto bassi/alti la stima INPS è imprecisa. `fiscal_rules.json` non prevede questi parametri: è una limitazione nota, da segnalare se rilevante per i casi d'uso.

---

## 4. Ripartizione "quota collettivo" (Willow) — analisi

È il cuore della richiesta utente: capire quanto delle tasse è imputabile all'attività interna e quindi rimborsabile dai conti del collettivo.

### Forfettario (semplice e coerente)
`quota_willow = reddito_willow / reddito_tot` (riga 248); IRPEF/INPS Willow = totale × quota. Metodo **proporzionale lineare**, internamente coerente (`irpef_w + irpef_non_w = irpef`). Ragionevole.

### 🟠 E4 — Ordinaria: metodo ibrido potenzialmente sovra-attributivo
Righe 390-405:
```python
irpef_comune       = irpef su base_senza_willow
quota_willow_base  = reddito_netto_willow / reddito_netto_completo
irpef_aggiuntiva   = irpef_lorda_completo − irpef_lorda_senza_willow   # marginale
irpef_willow       = irpef_comune × quota_willow_base + irpef_aggiuntiva
```
Il collettivo si vede attribuire **tutta l'IRPEF marginale** generata dal reddito interno (corretto come concetto di "incremento") **più** una quota proporzionale dell'IRPEF "di base" che però è calcolata sul reddito **esterno** (`base_senza_willow`). Quest'ultimo addendo attribuisce al collettivo una porzione di imposta che grava su redditi esterni: tende a **sovrastimare** la quota Willow.

Due metodi "puri" e coerenti sarebbero:
- **Marginale**: `irpef_willow = irpef_lorda_completo − irpef_lorda_senza_willow` (l'imposta aggiuntiva causata dal reddito interno).
- **Proporzionale**: `irpef_willow = irpef_lorda_completo × quota_willow_base`.

Il metodo attuale è una via di mezzo non standard. **Raccomandazione**: definire con l'utente quale principio di attribuzione si vuole (chi "ordina" lo scaglione più alto: il reddito esterno o quello interno?) e renderlo esplicito. Verificare inoltre l'identità di quadratura `tasse_willow + tasse_non_willow == totale_tasse` con un test numerico: con il metodo ibrido attuale questa identità **non è garantita**.

> `inps_willow` (riga 405) è invece puramente proporzionale al reddito netto: coerente.

---

## 5. Analisi della VIEW — validità informativa per l'utente

### Pannello Dettaglio (`QT_user_detail_view.py`)
Punti di forza:
- I **tooltip educativi** (`:863-1020`) ricostruiscono passo-passo il calcolo: ottima trasparenza per l'utente.
- Separazione visiva chiara tra **Totali** e **Versamenti**, e tra quota collettivo (header blu, `_tax_header_color`) e quota propria.
- La localizzazione del nome collettivo è gestita solo sulle label, non sulle chiavi interne (`_localize_collective`, `:102`): scelta corretta.

Criticità di coerenza dato/vista:
- **E9** — Nel forfettario, la sezione `DATI FISCALI` mostra l'aliquota IRPEF calcolata con la chiamata *corretta* (5% nei primi anni), mentre la sezione `PREVISIONE TASSE` calcola con la chiamata *buggata* (15%). L'utente vede **due aliquote diverse nella stessa schermata** → confusione e sfiducia nel dato. Risolvendo E2 si risolve anche E9.
- Il tooltip forfettario IRPEF (`:876-883`) dichiara *"Imposta = Reddito imponibile × Aliquota"*: documenta fedelmente una formula che **omette la deduzione INPS** (E3). Una volta corretto E3, aggiornare anche il testo del tooltip.
- Il tooltip forfettario INPS (`:891-899`) dice *"Reddito imponibile = Fatturato totale × Coefficiente"* ma nel codice il `reddito_esterno` non riceve il coefficiente (E7): testo fuorviante.

### Tab Tasse (`QT_taxes_view.py`)
- Mostra **solo le quote del collettivo** (`SALDO/ACCONTO/IRPEF/INPS WILLOW`): coerente con l'obiettivo "quanto rimborsarsi dai conti del collettivo". Buona scelta di scope.
- Il sottotitolo della seconda tabella ("Non tiene conto di acconti precedenti o futuri", `:249`) è un'indicazione corretta e utile.
- La doppia sorgente **anno corrente** (ricalcolo live) vs **anno precedente** (libri archiviati via `BooksRetriever`) con formato unificato (`_convert_retriever_to_analyzer_format`, `:152`) è ben progettata; il messaggio di "nessun dato" è chiaro.
- ⚠️ Le quote mostrate ereditano **tutti** gli errori di calcolo a monte (E1–E4): la tab è il punto in cui un errore sulla base imponibile (E1) o sull'aliquota (E2) si propaga ai numeri che l'utente userà per i rimborsi reali. È quindi la vista a **massimo impatto pratico**.

---

## 6. Versamenti, acconti e scadenze

- Parametri (40/60 IRPEF, 80% INPS, rate 50%) letti correttamente da `fiscal_rules.json`.
- 🟡 **E6** — Nella ripartizione per scadenza dell'ordinaria (righe 449-455):
  ```python
  totale_giugno   = saldo_corrente + rata_inps + rata_irpef_primo
  totale_novembre = rata_irpef_secondo
  ```
  La **seconda rata di acconto INPS** (quella di novembre, pari a un altro `rata_inps`) **non compare** in `totale_novembre`. La somma giugno+novembre risulta inferiore all'`ACCONTO_TOTALE` di un `rata_inps`. Le card "ACCONTO TOTALE" restano corrette (usano `acconto_totale`), ma la ripartizione per data è incompleta. Aggiungere `rata_inps` a `totale_novembre`.
- Le date scadenza sono hard-coded "30/06" e "30/11" (`:548-549`). Per il 2025 il report segnala proroghe (21/07, 02/12): se la previsione deve essere "operativa" conviene rendere le date configurabili; altrimenti documentare che sono le scadenze ordinarie teoriche.

---

## 7. Manutenibilità

- **E10** — `calcola_aliquota_tax_ordinaria` (`:135`) e `calcola_reddito_tot_utente` (`:14`) non sono usate da nessuna view/funzione attiva (la prima chiama la seconda, ma nessuno chiama la prima). Inoltre `calcola_aliquota_tax_ordinaria` restituirebbe una **singola aliquota di scaglione** (logica errata per un'imposta progressiva): se mai venisse riutilizzata sarebbe una trappola. Valutare la rimozione o un commento di deprecazione.
- `calculate_previsione_tasse_willow` cattura `Exception` generica per utente (`:607`) e azzera i valori: utile per robustezza UI, ma maschera errori di calcolo. Almeno loggare in modo strutturato (oggi è un `print`).

---

## 8. Raccomandazioni prioritarie

1. **(E1)** Sostituire `TOT_DOCUMENTO` con `IMPONIBILE` (o `FATTURATO_NETTO_IVA`) come base imponibile nel calcolo tasse ordinarie. *Impatto: alto, corregge la sovrastima sistematica di IRPEF e INPS.*
2. **(E2/E9)** Correggere la chiamata a `calcola_aliquota_tax_forfettaria` (riga 231) per passare l'anno di apertura, uniformando la convenzione. *Impatto: alto, ripristina l'aliquota agevolata 5%.*
3. **(E3)** Dedurre i contributi INPS dalla base dell'imposta sostitutiva forfettaria (o renderlo opzionale e documentato). *Impatto: alto, allinea al report.*
4. **(E4)** Concordare e implementare un metodo di attribuzione IRPEF al collettivo coerente (marginale **o** proporzionale), con test di quadratura `willow + non_willow == totale`.
5. **(E5)** Uniformare il principio di cassa: escludere le fatture non incassate anche per il forfettario.
6. **(E6)** Aggiungere la seconda rata INPS a `totale_novembre`.
7. **(E7/E8)** Chiarire la semantica di `reddito_esterno` (fatturato vs reddito) e valutare minimale/massimale Gestione Separata.
8. Aggiornare i **tooltip** dopo le correzioni, così che descrizione e calcolo coincidano.

> **Suggerimento di verifica**: prima di applicare i fix, creare un piccolo test con i due scenari numerici del report (€60k ordinaria con/ senza spese; €30k forfettario coeff. 78%) e confrontare gli output delle funzioni con i valori attesi del documento. Oggi questi scenari **non** sono coperti da test e darebbero risultati divergenti su E1, E2 ed E3.
