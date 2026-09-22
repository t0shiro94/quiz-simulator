# Contribuire a Quiz Simulator

Contributi piccoli, leggibili e facili da verificare sono benvenuti. Prima di iniziare un cambiamento ampio, apri una discussione o una issue che descriva il problema concreto, il comportamento desiderato e l'impatto sui dati già salvati.

## Preparare l'ambiente

Il progetto richiede Windows e Python 3.14.

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\.venv\Scripts\python.exe -m pytest
```

Crea un branch dedicato e limita ogni pull request a un solo obiettivo. Non includere `.venv`, database personali, backup, file di log, contenuti di `tmp` o artefatti di build.

## Linee guida per il codice

- Mantieni l'interfaccia in italiano e usa messaggi che dicano all'utente che cosa è successo e come rimediare.
- Tieni le regole di valutazione indipendenti dai widget. Il dominio deve poter essere verificato senza avviare l'interfaccia.
- Conserva la separazione tra interfaccia, importazione, archivio e analisi dei progressi.
- Preferisci nomi espliciti e funzioni brevi; aggiungi un commento soltanto quando chiarisce una scelta che il codice non rende evidente.
- Non cambiare il significato di un formato, di un punteggio o di una statistica senza aggiornare schema, esempi, test e guida.
- Ogni modifica allo schema SQLite deve prevedere un percorso di migrazione e una prova con un archivio della versione precedente.
- Le operazioni che sostituiscono o eliminano dati devono rimanere transazionali e, quando previsto, creare prima un backup.
- Nessun dato personale o contenuto di quiz deve essere inviato in rete senza un'azione chiara dell'utente.

## Test

Esegui l'intera suite prima di aprire una pull request:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check quiz_simulator tests scripts run_quiz.py
.\.venv\Scripts\ruff.exe format --check quiz_simulator tests scripts run_quiz.py
```

Per cambiamenti all'interfaccia, verifica anche l'avvio reale e il percorso interessato. Lo smoke test isolato è disponibile con:

```powershell
.\.venv\Scripts\python.exe run_quiz.py --smoke-test
```

Un nuovo comportamento deve avere un test che dimostri il risultato osservabile. Per importazioni e persistenza, includi anche il caso non valido o interrotto e controlla che i dati precedenti restino coerenti.

## Formati ed esempi

`schemas/quiz-v2.schema.json` è il riferimento formale del JSON. Gli esempi in `examples` devono restare validi e importabili. Se li modifichi, rigenerali con:

```powershell
.\.venv\Scripts\python.exe scripts\create_examples.py
```

Controlla poi i due PDF dall'anteprima dell'applicazione, oltre ai test automatici.

## Pull request

La descrizione dovrebbe indicare:

- il problema risolto;
- il comportamento prima e dopo la modifica;
- i test eseguiti;
- eventuali conseguenze su database, backup o formati importabili;
- schermate essenziali quando cambia l'interfaccia.

Prima dell'invio, verifica che `README.md` e `GUIDA_UTENTE.md` descrivano il comportamento effettivo. Le vulnerabilità non vanno pubblicate in una issue ordinaria: segui [SECURITY.md](SECURITY.md).
