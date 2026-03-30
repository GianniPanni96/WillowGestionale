# Architecture Tools

Strumenti locali per osservare le dipendenze del progetto e individuare piu' facilmente accoppiamenti forti o cicli tra moduli.

## Generazione grafi

Esegui:

```powershell
python .\ArchitectureTools\generate_dependency_report.py
```

Output generati:

- `ArchitectureTools/output/dependency_graph.html`
- `ArchitectureTools/output/dependency_graph.svg`
- `ArchitectureTools/output/dependency_graph.dot`
- `ArchitectureTools/output/class_dependencies.json`

Il generatore rimuove automaticamente il vecchio `dependency_report.md`, che non viene piu' prodotto.

## Cosa contiene

- `dependency_graph.html`
  - grafo interattivo a nodi
  - zoom, pan e ricerca live
  - nodi gia' distanziati all'apertura
  - colori diversi per layer/cartella
- `dependency_graph.svg`
  - snapshot statico facilmente condivisibile
- `dependency_graph.dot`
  - export riusabile con tool Graphviz esterni
- `class_dependencies.json`
  - base dati strutturata per estensioni future

## Librerie usate

- `networkx`
- `pyvis`
- `pydot`

Nota: per questo tool non e' necessario avere l'eseguibile `dot` installato nel sistema. Se in futuro installerai Graphviz di sistema, il file `.dot` potra' essere renderizzato anche con tool esterni.

## Limiti

L'analisi e' statica e basata su AST:

- rileva bene ereditarieta', import, assegnazioni a `self` e istanziazioni esplicite
- non copre tutta la dinamica runtime di Python
- e' pensata come strumento di supporto architetturale, non come verita' assoluta

## Aggiornamento

Lo strumento non richiede configurazioni manuali: rigeneralo ogni volta che cambi architettura, introduci nuovi layer o vuoi verificare possibili dipendenze circolari.
