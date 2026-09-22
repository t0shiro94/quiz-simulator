# Guida utente di Quiz Simulator

Quiz Simulator raccoglie domande personali, crea prove e usa i risultati per indicare che cosa ripassare. Tutti i dati restano nella cartella del programma. È possibile lavorare senza connessione; Internet serve soltanto quando si decide di aprire ChatGPT nel browser.

## Indice

1. [Avvio e primo quiz](#avvio-e-primo-quiz)
2. [Schermate dell'applicazione](#schermate-dellapplicazione)
3. [Importare un file](#importare-un-file)
4. [Preparare un file JSON](#preparare-un-file-json)
5. [Preparare un PDF](#preparare-un-pdf)
6. [Gestire raccolte e domande](#gestire-raccolte-e-domande)
7. [Svolgere un quiz](#svolgere-un-quiz)
8. [Correzione e punteggio](#correzione-e-punteggio)
9. [Statistiche e ripasso intelligente](#statistiche-e-ripasso-intelligente)
10. [Spiegazioni con ChatGPT](#spiegazioni-con-chatgpt)
11. [Backup, ripristino e dati locali](#backup-ripristino-e-dati-locali)
12. [Risoluzione dei problemi](#risoluzione-dei-problemi)

## Avvio e primo quiz

### Avviare il pacchetto Windows

Estrarre l'intera cartella ricevuta e aprire `QuizSimulator.exe`. In una copia del progetto che contiene la distribuzione compilata è possibile usare anche `Avvia Quiz Simulator.cmd`.

La cartella va mantenuta completa: l'eseguibile utilizza le librerie e gli esempi distribuiti al suo fianco. Scegliere una posizione in cui il proprio account Windows possa creare e modificare file.

### Avviare il codice sorgente

Da PowerShell, nella cartella del progetto:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
& '.\Avvia Quiz Simulator.cmd'
```

In alternativa:

```powershell
.\.venv\Scripts\python.exe run_quiz.py
```

### Fare una prima prova

Al primo avvio la Panoramica non contiene domande. Scegliere **Prova la raccolta di esempio**, controllare l'elenco e confermare **Crea nuova raccolta**. Tornare in **Nuovo quiz**, lasciare le impostazioni iniziali e scegliere **Inizia il quiz**.

L'applicazione ammette una sola prova in corso. Se una prova è già stata iniziata, il pulsante di avvio riporta alla sessione salvata.

## Schermate dell'applicazione

### Panoramica

Mostra quante raccolte e domande sono disponibili, le ultime prove concluse e l'eventuale sessione da riprendere. Da qui si avviano rapidamente un allenamento, un esame o un percorso sui punti deboli.

### Archivio domande

È il centro di gestione dei contenuti. Consente di:

- importare JSON e PDF;
- creare raccolte e domande a mano;
- cercare nel testo e filtrare per raccolta, argomento o preferiti;
- modificare domande, soluzioni e spiegazioni;
- assegnare un argomento a più domande;
- consultare tentativi e annotazioni;
- archiviare, esportare, eliminare o ripristinare contenuti.

L'elenco mostra 50 domande alla volta. Usare **Precedenti** e **Successive** per cambiare pagina. Per selezionare più righe usare `Ctrl` o `Maiusc`.

### Nuovo quiz

Permette di scegliere raccolta, modalità e numero di domande. Le opzioni avanzate aggiungono filtri per argomento, tipo e preferiti, oltre a timer, mescolamento delle alternative e punteggi personalizzati.

### Ripasso intelligente

Raccoglie gli indicatori calcolati dall'app: tentativi ricordati, domande da recuperare, ripassi scaduti, difficoltà per argomento ed errori ricorrenti.

### Risultati

Conserva l'intero storico e mostra 100 prove alla volta, con i comandi per passare da una pagina all'altra. Una prova può essere riaperta per rivedere domande, risposte e soluzioni. Da questa schermata si gestisce anche il cestino delle prove.

### Impostazioni e Guida

Le Impostazioni permettono di cambiare la dimensione del testo, aprire le cartelle del programma e dei backup, creare o ripristinare un backup, azzerare la memoria di apprendimento e ricostruire gli indicatori. La guida che si sta leggendo è disponibile anche nella barra laterale dell'app.

## Importare un file

Aprire **Archivio domande** e scegliere **Importa JSON o PDF**. Il file viene letto senza modificare subito l'archivio.

Nella schermata di controllo:

1. verificare titolo e identificatore della raccolta;
2. controllare il riepilogo delle domande valide e di quelle da correggere;
3. fare doppio clic su una riga per modificarla;
4. selezionare più righe e usare **Assegna argomento** quando serve;
5. lasciare selezionate soltanto le domande da importare; con raccolte grandi usare **Seleziona tutte le valide**, **Deseleziona tutte** e i comandi di pagina;
6. scegliere il tipo di importazione;
7. leggere il conteggio di domande nuove, modificate, identiche o rimosse;
8. confermare l'operazione.

Le righe non valide partono deselezionate. Possono essere corrette nell'editor oppure lasciate fuori dall'importazione. Se nessuna domanda selezionata forma una raccolta valida, l'applicazione non applica modifiche.

Per un PDF viene chiesto anche l'intervallo di pagine. Il documento originale appare accanto alle domande riconosciute; selezionando una riga il visualizzatore raggiunge la pagina in cui è iniziato il quesito.

### Crea, aggiorna o sostituisci

| Operazione | Effetto |
| --- | --- |
| **Crea nuova raccolta** | Crea un elemento indipendente. L'ID deve essere diverso da quelli già presenti. |
| **Aggiorna raccolta** | Aggiunge gli ID nuovi e aggiorna quelli già presenti. Le domande assenti dal file restano nella raccolta. |
| **Sostituisci raccolta** | Applica il nuovo contenuto e sposta nel cestino le domande attive che non compaiono nel file. Prima crea automaticamente un backup. |

L'identificatore della domanda stabilisce se un quesito è nuovo o già presente. Per questo gli ID vanno mantenuti stabili tra un'importazione e la successiva.

L'opzione **Mantieni i progressi delle domande identiche** conserva l'apprendimento quando il contratto di correzione non cambia. Un cambiamento a testo, alternative, risposte corrette, varianti ammesse, risposta modello o criteri crea una nuova revisione; quella revisione costruisce nuovi indicatori senza alterare le prove precedenti. Cambiare soltanto argomento o spiegazione non cambia il contratto di correzione.

Disattivando l'opzione, il progresso delle domande incluse nell'importazione riparte dal momento dell'aggiornamento. Lo storico resta comunque consultabile.

## Preparare un file JSON

Il JSON è il formato più preciso e adatto a raccolte grandi. Salvare il file in UTF-8, con estensione `.json`.

Regole generali:

- la radice deve essere un oggetto con `versione_schema`, `id`, `titolo` e `domande`;
- `id` e `titolo` non possono essere vuoti;
- `domande` deve contenere almeno un elemento;
- ogni domanda deve avere un ID unico nella raccolta;
- non sono ammessi commenti, virgole finali o campi estranei;
- tutti i testi obbligatori devono contenere almeno un carattere;
- `argomento` e `spiegazione` sono facoltativi;
- un argomento assente o vuoto diventa `Da classificare`.

Le domande `Da classificare` possono comparire nei quiz e memorizzano i propri errori, ma non alimentano le conclusioni statistiche per argomento.

### Formato JSON v2

La versione 2 rappresenta tutti i tipi di domanda. Questo esempio è un file completo e valido:

```json
{
  "versione_schema": 2,
  "id": "esempio-completo",
  "titolo": "Esempio con quattro tipi di domanda",
  "domande": [
    {
      "id": "geo-001",
      "tipo": "scelta_singola",
      "testo": "Qual è la capitale della Francia?",
      "argomento": "Geografia",
      "risposte": [
        { "id": "A", "testo": "Roma" },
        { "id": "B", "testo": "Parigi" },
        { "id": "C", "testo": "Madrid" }
      ],
      "corrette": ["B"],
      "spiegazione": "Parigi è la capitale della Francia."
    },
    {
      "id": "mat-001",
      "tipo": "scelta_multipla",
      "testo": "Seleziona tutti i numeri pari.",
      "argomento": "Aritmetica",
      "risposte": [
        { "id": "A", "testo": "2" },
        { "id": "B", "testo": "3" },
        { "id": "C", "testo": "4" },
        { "id": "D", "testo": "7" }
      ],
      "corrette": ["A", "C"]
    },
    {
      "id": "geo-002",
      "tipo": "aperta_breve",
      "testo": "Scrivi la capitale della Francia.",
      "argomento": "Geografia",
      "risposte_ammesse": ["Parigi", "Paris"]
    },
    {
      "id": "mat-002",
      "tipo": "aperta_libera",
      "testo": "Spiega che cosa rappresenta una frazione e fai un esempio.",
      "argomento": "Aritmetica",
      "risposta_modello": "Una frazione rappresenta un rapporto o parti uguali di un intero.",
      "criteri": [
        "Descrive il significato della frazione",
        "Distingue numeratore e denominatore",
        "Presenta un esempio coerente"
      ]
    }
  ]
}
```

Il riferimento formale è `schemas/quiz-v2.schema.json`. Nella cartella `examples` si trovano anche file separati per ogni tipo.

### Scelta singola

Valore di `tipo`: `scelta_singola`.

Campi specifici:

- `risposte`: almeno due oggetti, ciascuno con `id` e `testo`;
- `corrette`: un elenco con un solo ID presente in `risposte`.

Un vero/falso usa lo stesso tipo con due alternative, per esempio `Vero` e `Falso`.

### Scelta multipla

Valore di `tipo`: `scelta_multipla`.

Usa gli stessi campi delle scelte singole, ma `corrette` deve contenere almeno due ID distinti. La risposta è corretta soltanto se l'utente seleziona tutte e soltanto le alternative indicate.

Gli ID delle alternative possono essere lettere, numeri o brevi codici. Devono essere unici all'interno della domanda. La correzione usa gli ID, quindi il mescolamento visivo non cambia la soluzione.

### Risposta aperta breve

Valore di `tipo`: `aperta_breve`.

Il campo `risposte_ammesse` contiene una o più stringhe valide. Il confronto ignora differenze tra maiuscole e minuscole e normalizza gli spazi iniziali, finali o ripetuti. Accenti, punteggiatura, simboli e separatori decimali restano significativi.

Per esempio, se sono ammesse sia `0,25` sia `0.25`, vanno inserite entrambe:

```json
{
  "id": "decimale-001",
  "tipo": "aperta_breve",
  "testo": "Scrivi il valore decimale di un quarto.",
  "argomento": "Aritmetica",
  "risposte_ammesse": ["0,25", "0.25"]
}
```

L'applicazione non usa somiglianze linguistiche per indovinare l'intenzione. Dopo una prova è possibile rettificare manualmente l'esito e aggiungere la risposta data alle varianti ammesse.

### Risposta aperta libera

Valore di `tipo`: `aperta_libera`.

Campi specifici:

- `risposta_modello`: il testo di riferimento mostrato dopo la conferma o la consegna;
- `criteri`: uno o più punti con cui confrontare la risposta.

La risposta resta **Da valutare** fino a quando l'utente sceglie **Corretta**, **Parziale** o **Sbagliata**. La valutazione viene registrata come manuale.

### Compatibilità con JSON v1

La versione 1 rimane importabile per le vecchie raccolte a scelta singola. Non usa il campo `tipo`; la soluzione è una stringa chiamata `corretta`:

```json
{
  "versione_schema": 1,
  "id": "geografia-base",
  "titolo": "Geografia di base",
  "domande": [
    {
      "id": "geo-001",
      "testo": "Qual è la capitale della Francia?",
      "argomento": "Capitali europee",
      "risposte": [
        { "id": "A", "testo": "Roma" },
        { "id": "B", "testo": "Parigi" }
      ],
      "corretta": "B",
      "spiegazione": "Parigi è la capitale della Francia."
    }
  ]
}
```

Durante l'importazione viene convertito internamente in v2. Per nuovi file conviene usare sempre la versione 2. La versione 1 non rappresenta scelte multiple o risposte aperte.

## Preparare un PDF

Il PDF deve contenere testo selezionabile e, per ottenere risultati affidabili, una sola colonna. L'importazione riconosce domande numerate con `1.` oppure `1)`, alternative con `A)` oppure `A.` e marcatori testuali espliciti.

### Scelta singola

```text
1. Qual è la capitale della Francia?
A) Roma
B) Parigi
C) Madrid
D) Berlino
Risposta corretta: B
Argomento: Capitali europee
Spiegazione: Parigi è la capitale della Francia.
```

### Scelta multipla

```text
2. Seleziona tutti i numeri pari.
A) 2
B) 3
C) 4
D) 7
Risposte corrette: A, C
Argomento: Aritmetica
```

Con più soluzioni, separare gli ID con virgole o punti e virgola. Il tipo viene riconosciuto come scelta multipla quando sono presenti più risposte corrette.

### Risposta aperta breve

```text
3. Scrivi la capitale della Francia.
Tipo: aperta_breve
Risposte ammesse: Parigi | Paris
Argomento: Capitali europee
```

Le varianti ammesse sono separate dal carattere `|`. Possono continuare sulla riga successiva, mantenendo lo stesso separatore.

### Risposta aperta libera

```text
4. Spiega che cosa rappresenta una frazione e fai un esempio.
Tipo: aperta_libera
Risposta modello: Una frazione rappresenta un rapporto o parti uguali di un intero.
Criteri:
- Descrive il significato della frazione
- Distingue numeratore e denominatore
- Presenta un esempio coerente
Argomento: Aritmetica
```

I criteri possono iniziare con `-` oppure `•`. I marcatori `Tipo`, `Risposta modello`, `Criteri`, `Argomento` e `Spiegazione` devono essere seguiti dai due punti.

### Soluzioni raccolte alla fine

Per le domande a scelta, le risposte possono essere riunite alla fine dello stesso PDF:

```text
SOLUZIONI
1: B
2: A, C
3: D
```

Dopo la riga `SOLUZIONI`, usare soltanto righe nel formato mostrato. Se una soluzione inline e quella finale non coincidono, la domanda viene segnalata come contraddittoria e deve essere corretta nell'anteprima.

Il testo della domanda, delle alternative, della risposta modello e della spiegazione può proseguire su più righe. Una domanda può anche continuare nella pagina successiva: il numero di pagina associato resta quello in cui è iniziata.

### PDF che richiedono revisione

Il riconoscimento automatico non è adatto a:

- scansioni o pagine composte soltanto da immagini;
- impaginazioni a più colonne o tabelle complesse;
- formule e figure indispensabili alla domanda;
- soluzioni indicate soltanto con colore, grassetto o simboli grafici;
- PDF cifrati o protetti.

Una pagina senza testo estraibile viene segnalata come possibile caso OCR. Questa versione non esegue OCR: occorre procurare un PDF testuale, convertire prima la scansione oppure inserire le domande a mano nell'anteprima.

## Gestire raccolte e domande

### Creare e modificare

Per creare una raccolta vuota usare **Nuova raccolta**. Selezionarla nel filtro e scegliere **Nuova domanda**. L'editor adatta i campi al tipo scelto:

- per le scelte, una alternativa per riga nel formato `A | testo` e gli ID corretti separati da virgola;
- per una risposta breve, una variante ammessa per riga;
- per un testo libero, risposta modello e un criterio per riga.

Fare doppio clic su una domanda, oppure selezionarla e premere **Modifica**, per aprire lo stesso editor. L'ID di una domanda esistente non è modificabile perché collega importazioni, revisioni e storico.

Il pulsante **Argomento** applica una classificazione a tutte le righe selezionate. Cambiare argomento riclassifica anche i tentativi collegati a quella domanda.

### Preferiti, ricerca e storico

Una o più domande possono essere marcate come preferite e poi usate come filtro per un quiz. La ricerca trova parole nel testo e nell'argomento; più parole restringono il risultato.

**Storico / note** mostra fino agli ultimi 100 tentativi attivi della domanda, con data, esito, origine della valutazione, versione e risposta data. Da qui si possono anche leggere, aggiungere o eliminare annotazioni della revisione corrente.

### Archiviare una raccolta

Da **Gestisci raccolta** scegliere **Archivia**. La raccolta resta conservata e modificabile, ma viene esclusa da nuovi quiz, statistiche e ripasso intelligente. Selezionarla esplicitamente nell'Archivio per vedere le sue domande, quindi scegliere **Riattiva** quando deve tornare disponibile.

### Cestino delle domande

**Elimina** sposta le domande selezionate nel cestino. I risultati già registrati restano leggibili. Attivare **Domande nel cestino** per mostrarle, quindi usare **Ripristina** oppure **Elimina definitivamente**.

L'eliminazione definitiva rimuove la domanda attuale e le relative note. Le prove storiche conservano una copia del testo e della soluzione usati al momento del quiz.

### Cestino delle raccolte

Da **Gestisci raccolta** si può spostare l'intera raccolta nel cestino. Aprire poi **Cestino delle raccolte** e scegliere una delle operazioni disponibili:

- ripristinare la raccolta;
- eliminarla definitivamente conservando le prove storiche;
- eliminarla definitivamente insieme alle prove collegate.

Nell'ultimo caso vengono eliminate per intero anche eventuali prove miste che contengono domande di altre raccolte. Questa scelta serve a mantenere coerenti punteggi e totali della sessione.

Prima di un'eliminazione definitiva importante, creare manualmente un backup.

### Esportare e azzerare una raccolta

**Esporta JSON** salva tutte le domande attive della raccolta nel formato v2. Le domande nel cestino non sono incluse.

**Azzera memoria di apprendimento** fa ripartire errori, ripassi e analisi di quella raccolta. Viene creato un backup automatico; le prove rimangono visibili in Risultati, ma i tentativi precedenti all'azzeramento non alimentano i nuovi indicatori.

## Svolgere un quiz

### Impostazioni iniziali

Per impostazione predefinita vengono richieste 20 domande. Se i filtri ne trovano meno, l'applicazione usa tutte quelle disponibili. Il limite per una sessione è 1.000 domande e lo stesso quesito non viene ripetuto nella prova.

Le opzioni avanzate permettono di scegliere:

- un argomento;
- uno o più tipi di domanda;
- soltanto i preferiti;
- durata dell'esame da 1 a 1.440 minuti, oppure nessun timer;
- mescolamento delle alternative;
- punti per risposta corretta, sbagliata e omessa.

Il mescolamento è disattivato in partenza. Va lasciato così per alternative che contengono frasi come “tutte le precedenti” o che fanno riferimento alle lettere.

### Allenamento

Selezionare una risposta e premere **Conferma risposta**. La risposta diventa definitiva, viene corretta e mostra subito soluzione e spiegazione disponibile. È possibile saltare un quesito e tornarci prima di terminare.

Il testo digitato o le selezioni non ancora confermate sono salvati come bozza. Se si termina l'allenamento senza confermarli, quei quesiti vengono registrati come omessi.

### Esame

Le soluzioni restano nascoste fino alla consegna. Si può navigare tra le domande e cambiare le risposte finché la prova è attiva. Le altre sezioni dell'app rimangono bloccate, salvo la Panoramica e il ritorno alla prova.

Se è impostato un timer, la scadenza è assoluta: chiudere il programma non sospende il tempo. Alla riapertura, una prova scaduta viene consegnata automaticamente. Anche le risposte aperte libere restano da valutare dopo la consegna.

### Allenamento intelligente

Si svolge con la correzione immediata dell'Allenamento, ma le domande vengono scelte dal motore di ripasso. Sopra ogni quesito compare il motivo della selezione, per esempio **Errore ricorrente**, **Argomento da rinforzare**, **Ripasso previsto** oppure **Esplorazione e consolidamento**.

### Salvataggio e ripresa

Risposte e posizione corrente vengono salvate durante la prova. Chiudendo l'app è possibile riprendere dalla Panoramica. Può esistere una sola sessione attiva alla volta: per iniziarne un'altra occorre terminare quella corrente.

## Correzione e punteggio

### Scelte singole e multiple

La scelta singola è corretta quando coincide con l'unico ID previsto. La scelta multipla richiede tutte e soltanto le alternative corrette: una selezione incompleta o con un'opzione in più è sbagliata. Non viene assegnato un punteggio parziale automatico alle scelte multiple.

### Risposte brevi

Il confronto è automatico rispetto a `risposte_ammesse`. Se una formulazione valida non era prevista, dopo la correzione usare **Corretta** per rettificare l'esito. **Aggiungi la mia risposta alle varianti ammesse** aggiorna anche la domanda e crea una nuova revisione.

Le rettifiche sono indicate come manuali e non aggiungono un secondo tentativo.

### Risposte libere

Dopo la conferma vengono mostrate risposta modello e criteri. Scegliere:

- **Corretta** se la risposta soddisfa il riferimento;
- **Parziale** se coglie una parte significativa ma resta incompleta;
- **Sbagliata** se non soddisfa i criteri.

Finché non si sceglie, l'esito è **Da valutare** e il punteggio della prova è provvisorio. In modalità Esame l'autovalutazione è disponibile soltanto dopo la consegna.

### Calcolo del risultato

Le impostazioni iniziali assegnano:

- 1 punto a una risposta corretta;
- 0 punti a una risposta sbagliata;
- 0 punti a una risposta omessa;
- metà dei punti della risposta corretta a una risposta parziale.

I valori per corretta, sbagliata e omessa possono essere personalizzati, anche con una penalità negativa. La percentuale **Corrette sul totale** è indipendente dal punteggio e usa il numero di risposte pienamente corrette diviso per tutte le domande della prova.

## Statistiche e ripasso intelligente

Il motore di apprendimento usa i tentativi delle revisioni correnti, successivi all'ultimo azzeramento e appartenenti a raccolte attive. Spostare una prova nel cestino la toglie dai calcoli; ripristinarla la reinserisce. Archiviare o cestinare una raccolta la esclude dalle analisi attive.

### Memoria degli errori

Per ogni domanda vengono ricordati tentativi, esiti, ultimo risultato, serie di risposte corrette e data del prossimo ripasso. Un errore, un'omissione o una risposta parziale porta il quesito tra quelli da recuperare e programma un nuovo incontro dal giorno successivo.

Dopo un errore, due risposte pienamente corrette consecutive in sessioni diverse segnano il quesito come recuperato. Lo storico dell'errore rimane disponibile. Gli intervalli di ripasso crescono progressivamente a 1, 3, 7, 14 e 30 giorni; un nuovo errore riporta la scadenza al giorno successivo.

La tabella **Errori ricorrenti** mostra fino a 30 domande con almeno due esiti sbagliati, ordinando prima quelle ancora da recuperare e con più errori.

### Analisi per argomento

La situazione recente considera fino agli ultimi 20 tentativi valutati per argomento e distingue correzioni automatiche da autovalutazioni manuali.

Per formulare un'indicazione servono almeno:

- 5 risposte valutate;
- 3 domande distinte.

Con meno dati appare **Dati insufficienti**. La difficoltà viene calcolata assegnando peso 0 a una risposta corretta, 0,5 a una risposta parziale e 1 a una risposta sbagliata. Se raggiunge almeno il 40%, l'argomento è indicato come **Da rinforzare**; altrimenti compare **In consolidamento**. Le omissioni restano visibili nei totali, ma non entrano in questo indice per argomento.

Quando sono disponibili 20 tentativi, gli ultimi 10 vengono confrontati con i 10 precedenti. Una differenza di almeno 10 punti percentuali produce **In miglioramento** oppure **Da rivedere**; negli altri casi l'andamento è **Stabile**.

Queste indicazioni descrivono i risultati registrati nell'applicazione. Non sono una certificazione del livello di preparazione.

### Come vengono scelte le domande intelligenti

La composizione obiettivo è:

- circa 60% dagli argomenti da rinforzare, con precedenza agli errori non recuperati;
- circa 20% dai ripassi già arrivati a scadenza;
- il resto da domande nuove o da consolidare.

Una domanda non viene inserita due volte nella stessa sessione. Se una categoria non ha abbastanza contenuti, i posti liberi vengono riempiti dalle altre domande disponibili. Per un utente senza storico, l'app distribuisce le domande tra gli argomenti e dà precedenza a quelle mai affrontate.

## Spiegazioni con ChatGPT

Il pulsante **Spiegami con ChatGPT / note** appare quando la soluzione è visibile. L'applicazione prepara una richiesta che contiene:

- testo e alternative della domanda;
- risposta dell'utente;
- soluzione e spiegazione della fonte;
- risposta modello e criteri, per le domande aperte.

La richiesta è modificabile. **Copia richiesta** la mette negli appunti; **Copia e apri ChatGPT** esegue la stessa copia e apre `chatgpt.com` nel browser predefinito. Incollare il testo nella chat e inviarlo con il proprio account.

Quiz Simulator non legge l'account, non usa cookie del browser e non invia dati in automatico. Prima di incollare, rimuovere eventuali nomi o contenuti riservati.

La risposta ricevuta può essere incollata nel riquadro delle note e salvata come **ChatGPT · riportata dall'utente**. In alternativa si può scrivere una **Nota personale**. Le note sono associate alla revisione della domanda e non modificano soluzione, punteggio o valutazione. Se la fonte contiene un errore, correggere la domanda dall'Archivio.

## Backup, ripristino e dati locali

### Dove sono i dati

Il percorso esatto compare nelle Impostazioni e nella barra di stato. Le cartelle principali sono:

```text
data/quiz.sqlite3    raccolte, domande, prove, note e impostazioni
data/sources/        copie dei JSON e PDF importati
data/app.log         dettagli degli errori non gestiti
backups/             backup creati dall'applicazione
tmp/                 file temporanei e verifiche locali
```

Questa organizzazione rende il programma portatile. Per trasferire l'intera installazione, chiudere l'applicazione e copiare tutta la cartella su un'unità in cui si disponga dei permessi di scrittura.

### Creare un backup

Aprire **Impostazioni** e scegliere **Crea backup completo**. Indicare un file `.zip` e attendere la conferma. Il backup contiene una copia coerente del database e le fonti importate; non contiene l'eseguibile.

Sono creati automaticamente backup preventivi prima di:

- sostituire una raccolta;
- azzerare la memoria di una raccolta o di tutta l'app;
- ripristinare un altro backup.

Conservare periodicamente una copia su un supporto diverso dalla cartella del programma.

### Ripristinare

Scegliere **Ripristina un backup**, selezionare lo ZIP e confermare. Prima di modificare l'archivio corrente, l'app verifica formato, percorsi interni, integrità del database e relazioni. Crea quindi un backup preventivo dei dati correnti.

Il ripristino sostituisce raccolte, prove, note, statistiche e impostazioni con lo stato contenuto nello ZIP. Non rinominare né modificare manualmente i file interni del backup.

### Azzerare o ricostruire gli indicatori

**Azzera memoria di apprendimento** riparte da zero per errori e ripassi di tutte le raccolte, conservando lo storico consultabile. Crea prima un backup.

**Ricostruisci indicatori** ricalcola la memoria a partire dai tentativi ancora validi e rispetta gli azzeramenti già eseguiti. È utile dopo aver eliminato o ripristinato molte prove.

## Risoluzione dei problemi

### Il programma dice che è già aperto

È consentita una sola istanza per cartella, per proteggere il database da modifiche concorrenti. Portare in primo piano la finestra già aperta oppure chiuderla prima di riprovare.

### Un JSON non viene importato

Il messaggio indica riga e colonna per gli errori di sintassi oppure il campo e la domanda per gli errori di contenuto. Controllare soprattutto:

- `versione_schema` uguale a `1` o `2`;
- virgolette doppie e assenza di virgole finali;
- ID unici;
- ID in `corrette` presenti nelle alternative;
- campi coerenti con il valore di `tipo`.

Confrontare il file con gli esempi forniti. Un editor con validazione JSON aiuta a individuare parentesi o virgolette mancanti.

### Il PDF riconosce poche domande

Provare a selezionare del testo nel lettore PDF. Se non è possibile, il documento è probabilmente una scansione e richiede OCR esterno. Per un PDF testuale, controllare numerazione, marcatori e impaginazione a una colonna. Nell'anteprima è sempre possibile modificare i quesiti riconosciuti o aggiungerne a mano.

### Il PDF mostra soluzioni contraddittorie

Una risposta inline non coincide con la sezione finale, oppure la stessa soluzione compare più volte con valori diversi. Aprire la domanda nell'anteprima e scegliere gli ID corretti prima dell'importazione.

### Non trovo domande per un nuovo quiz

Rimuovere temporaneamente filtri per argomento, tipo e preferiti. Controllare poi che la raccolta non sia archiviata o nel cestino e che le domande non siano state eliminate. Se esiste già una sessione attiva, terminarla oppure riprenderla dalla Panoramica.

### Una risposta breve corretta è stata segnata come sbagliata

Il confronto non ignora accenti, punteggiatura o simboli. Aprire il risultato, rettificarlo con **Corretta** e, se quella forma deve essere accettata in futuro, scegliere **Aggiungi la mia risposta alle varianti ammesse**.

### Il punteggio è provvisorio

Una o più risposte aperte libere sono ancora **Da valutare**. Aprire la prova nei Risultati, raggiungere ogni domanda pendente e scegliere Corretta, Parziale o Sbagliata.

### Le statistiche non segnalano ancora un argomento

Servono almeno cinque tentativi valutati su tre quesiti distinti per la stessa origine di valutazione. Le domande `Da classificare`, le raccolte archiviate e le prove nel cestino non alimentano la diagnosi per argomento.

### ChatGPT non si apre

La richiesta è già stata copiata negli appunti. Aprire manualmente [chatgpt.com](https://chatgpt.com/) nel browser e incollarla. Verificare la connessione e l'associazione del browser predefinito in Windows.

### Un backup non viene accettato

Il ripristino accetta backup integri prodotti da una versione compatibile di Quiz Simulator. Usare un'altra copia se lo ZIP è stato alterato, è incompleto o supera il limite di ripristino di 4 GB. L'archivio attuale non viene sostituito quando la verifica fallisce.

### Si verifica un errore inatteso

Chiudere e riaprire l'applicazione, quindi ripetere l'operazione. Se il problema continua, creare un backup e consultare `data/app.log`. Prima di condividere il log, rimuovere eventuali percorsi o testi personali.
