# Sicurezza

## Versioni supportate

Le correzioni di sicurezza vengono applicate alla versione più recente del ramo `1.x`.

| Versione | Supporto |
| --- | --- |
| 1.x | Sì |
| precedenti | No |

## Segnalare un problema

Se il repository è ospitato su GitHub, usa una **segnalazione privata di sicurezza** dalla scheda *Security* del progetto. Non aprire una issue pubblica prima che il problema sia stato analizzato.

La segnalazione dovrebbe contenere:

- versione dell'applicazione e versione di Windows;
- descrizione del comportamento e del possibile impatto;
- passaggi minimi per riprodurlo;
- un file di prova ridotto, privo di dati personali, quando necessario;
- eventuali messaggi pertinenti presenti in `data/app.log`.

Non allegare archivi personali, backup completi o domande riservate. Dopo la verifica verranno concordati tempi e modalità di pubblicazione della correzione.

## Modello di sicurezza e riservatezza

Quiz Simulator conserva database, copie delle fonti e backup nella cartella del programma. Non contiene telemetria e non richiede credenziali online. La funzione ChatGPT copia una richiesta negli appunti e apre il browser soltanto quando l'utente preme il relativo pulsante; l'applicazione non accede alla sessione del browser e non invia la richiesta in modo automatico.

I file JSON, PDF e ZIP di backup vanno comunque trattati come contenuti non affidabili. Prima di importarli:

- ottienili da una fonte conosciuta;
- conserva un backup recente dell'archivio;
- mantieni aggiornate le dipendenze dichiarate dal progetto;
- non eseguire file o macro ricevuti insieme al materiale del quiz.

Il ripristino accetta soltanto il formato ZIP prodotto dall'applicazione, verifica struttura e database e crea una copia preventiva dell'archivio attuale. Questi controlli riducono il rischio di perdita dei dati, ma non sostituiscono un backup conservato su un supporto separato.
