# ViaggiaTreno

Questo è un tentativo di documentare le [API] di [ViaggiaTreno], il servizio di Trenitalia per ottenere informazioni sui treni in partenza e in arrivo dalle stazioni italiane, nonché sullo stato dei treni in viaggio.

> [!NOTE]
> Questo progetto non è affiliato con Trenitalia o con ViaggiaTreno in alcun modo. È un progetto open source che mira a semplificare l'accesso alle informazioni sui treni in Italia.

## Aggiornamenti

- L'endpoint `soluzioniViaggioNew` è stato dismesso e rimosso dalla documentazione. Per un periodo ha restituito una lista vuota, ora restituisce un errore 404. Come suggerisce il nome, serviva per ottenere le soluzioni di viaggio tra una stazione e l'altra. Non sembrava essere utilizzato dal [sito di ViaggiaTreno][ViaggiaTreno]. Al momento non ci sono alternative all'interno dell'API di ViaggiaTreno.

## Usare le API

Per usare le API di ViaggiaTreno, è necessario effettuare delle richieste HTTP ai vari endpoint. Le risposte sono generalmente in formato JSON, ma alcuni endpoint restituiscono stringhe o altri formati.

Il base-uri è <http://www.viaggiatreno.it/infomobilita/resteasy/viaggiatreno/>.

È possibile scoprire gli endpoint disponibili analizzando il contenuto del file [rest-api.js][API]. Analizzando le richieste che partono dal [sito][ViaggiaTreno], tuttavia, non tutti gli endpoint sembrano essere effettivamente usati.

### Sequenza delle chiamate

Per vedere i treni in partenza o in arrivo da una stazione, è necessario conoscere il codice della stazione. È possibile ottenerlo in vari modi. Quello usato da [ViaggiaTreno] è tramite `autocompletaStazione`, che restituisce il nome della stazione e il suo codice.

Una volta ottenuto il codice della stazione, è possibile chiamare `partenze` o `arrivi` per ottenere i treni in partenza o in arrivo da quella stazione. Il risultato di queste chiamate è una lista di treni con informazioni come il numero del treno, la destinazione, l'orario di partenza e arrivo, il ritardo, il binario programmato e quello effettivo. Queste informazioni sembrano sufficienti per ottenere le informazioni di interesse, ma alcuni dati non sono sempre affidabili. Per ovviare a questo problema, è possibile integrare con i dati di [`andamentoTreno`](#andamentotreno).

[`andamentoTreno`](#andamentotreno) ci permette di ottenere informazioni più dettagliate e accurate sullo stato di un treno in viaggio, come il suo itinerario, le fermate effettuate, i ritardi e altre informazioni utili. Questo endpoint è particolarmente utile per verificare lo stato effettivo del treno e per ottenere informazioni sulle fermate intermedie.

### Script CLI

È disponibile uno script Python CLI in [`scripts/viaggiatreno-api.py`](scripts/viaggiatreno-api.py) che fornisce accesso semplificato agli endpoint documentati:

- I nomi degli endpoint sono in _kebab-case_ invece che in _title-case_.
- I parametri sono passati come argomenti dalla linea di comando, con alcune semplificazioni:
  - Si possono passare direttamente i nomi delle stazioni al posto dei codici.
  - Le date sono accettate in formato YYYY-MM-DD e hanno come default la data corrente.
  - Gli endpoint che richiedono informazioni aggiuntive spesso possono essere chiamati con solo il dato principale (ad esempio, [`andamentoTreno`](#andamentotreno) può essere chiamato con il solo numero del treno, e lo script recupererà automaticamente stazione e data di partenza).
- L'opzione globale `-o/--output` permette di salvare l'output su file invece che visualizzarlo a schermo per tutti i comandi.
- Tramite il comando `dump-all` è possibile scaricare i dati di tutte le stazioni in un colpo solo. L'opzione `-o` specifica la cartella di destinazione (default: `dumps`).
- Tramite il comando `sample-stations` è possibile recuperare partenze e arrivi da un campione di stazioni.

Lo script richiede i pacchetti `requests` e `click`.

Di seguito sono riportati alcuni esempi di utilizzo:

```bash
# Cerca stazioni
uv run scripts/viaggiatreno-api.py autocompleta-stazione "Milano"
uv run scripts/viaggiatreno-api.py autocompleta-stazione-nts "Venezia"
uv run scripts/viaggiatreno-api.py cerca-stazione "Roma"

# Partenze da/arrivi a una stazione (accetta sia nomi che codici stazione)
uv run scripts/viaggiatreno-api.py partenze S01700
uv run scripts/viaggiatreno-api.py arrivi "Roma Termini"

# Salva output su file usando l'opzione globale -o
uv run scripts/viaggiatreno-api.py -o partenze.json partenze "Milano Centrale"

# Specifica data e ora (default: adesso)
uv run scripts/viaggiatreno-api.py partenze "Tortona" --datetime 2025-07-22T15:30:00

# Andamento di un treno (recupera stazione e data di partenza in automatico)
uv run scripts/viaggiatreno-api.py andamento-treno 9685

# Andamento con parametri specifici (accetta sia nomi che codici stazione)
uv run scripts/viaggiatreno-api.py andamento-treno 3041 --departure-station "Milano Centrale" --date 2025-07-22
uv run scripts/viaggiatreno-api.py andamento-treno 3041 --departure-station S01700 --date 2025-07-22

# Scarica tutti i dati delle stazioni
uv run scripts/viaggiatreno-api.py dump-all
uv run scripts/viaggiatreno-api.py -o my_data dump-all  # Salva nella cartella "my_data"

# Trova la regione di una stazione
uv run scripts/viaggiatreno-api.py regione "Milano Centrale"
uv run scripts/viaggiatreno-api.py regione S01700

# Mostra la tabella dei codici regione
uv run scripts/viaggiatreno-api.py regione --table

# Elenco stazioni in una regione (es. Lombardia)
uv run scripts/viaggiatreno-api.py elenco-stazioni 1

# Mostra i dettagli di una stazione recuperando codice stazione e codice regione in automatico
uv run scripts/viaggiatreno-api.py dettaglio-stazione "Milano Centrale"

# Mostra i dettagli di un treno
uv run scripts/viaggiatreno-api.py cerca-numero-treno 711

# Mostra i treni compatibili con un certo numero treno
uv run scripts/viaggiatreno-api.py cerca-numero-treno-treno-autocomplete 711
```

## Documentazione degli endpoint

Di seguito sono documentati gli endpoint più utili per ottenere informazioni sulle stazioni e sui treni, raggruppati per funzionalità.

I [JSON Schema](https://json-schema.org/) riportati sono frutto di reverse engineering e potrebbero non essere accurati al 100%. Sono da intendersi più come un'idea di come sono strutturati i dati restituiti dagli endpoint, piuttosto che una documentazione ufficiale.

- [Stazioni](#stazioni)
  - [`autocompletaStazione`](#autocompletastazione)
  - [`autocompletaStazioneImpostaViaggio`](#autocompletastazioneimpostaviaggio)
  - [`autocompletaStazioneNTS`](#autocompletastazionents)
  - [`cercaStazione`](#cercastazione)
  - [`regione`](#regione)
  - [`dettaglioStazione`](#dettagliostazione)
  - [`elencoStazioni`](#elencostazioni)
- [Partenze e arrivi](#partenze-e-arrivi)
  - [`partenze`](#partenze)
  - [`arrivi`](#partenze)
- [Stato treni](#stato-treni)
  - [`cercaNumeroTrenoTrenoAutocomplete`](#cercanumerotrenotrenoautocomplete)
  - [`cercaNumeroTreno`](#cercanumerotreno)
  - [`andamentoTreno`](#andamentotreno)

### Stazioni

#### autocompletaStazione

**Metodo e percorso:** `GET /autocompletaStazione/{prefisso}`

**Parametri:**

- `prefisso`: nome _case insensitive_ (anche parziale) della stazione di cui si vogliono sapere nome completo e codice.

**Risposta:**

- **Content-Type:** `text/plain`
- **Formato:** `NOME_STAZIONE|CODICE_STAZIONE`
  - Il nome della stazione riportato è in maiuscolo.
  - Il codice della stazione è un codice a 6 cifre formato da una `S` seguita da quello che potrebbe essere il codice che identifica la stazione nel [database ENEE][location code] o nel [Central Reference File Database](https://rne.eu/it/products/ccs/crd/), con eventuali zeri di padding dopo la `S` (regex: `^S\d{5}$`).

**Esempi:**

- Chiamando `/autocompletaStazione/firenze`, otteniamo:
  ```
  FIRENZE SANTA MARIA NOVELLA|S06421
  FIRENZE CAMPO MARTE|S06900
  FIRENZE CASTELLO|S06419
  FIRENZE RIFREDI|S06420
  FIRENZE ROVEZZANO|S06901
  FIRENZE STATUTO|S06430
  ```
- Chiamando `/autocompletaStazione/pala`, otteniamo:
  ```
  PALAGIANELLO|S11508
  PALAGIANO CHIATONA|S11464
  PALAGIANO MOTTOLA|S11509
  PALAGONIA|S12279
  PALAZZO REALE-ORLEANS|S12130
  PALAZZO S.GERVASIO-MONTEMILONE|S11303
  PALAZZOLO DELLO STELLA|S03203
  PALAZZOLO MILANESE|S01083
  PALAZZOLO SULL'OGLIO|S01538
  PALAZZOLO VERCELLESE|S00175
  ```

Questo è l'endpoint utilizzato da [ViaggiaTreno] per visualizzare i suggerimenti delle stazioni quando si inizia a digitare il nome di una stazione.
![Schermata di [ViaggiaTreno] in cui viene effettuata una chiamata ad autocompletaStazione.](images/demo-autocompleta-stazione.png)

#### autocompletaStazioneImpostaViaggio

**Metodo e percorso:** `GET /autocompletaStazioneImpostaViaggio/{prefisso}`

Identico a [`autocompletaStazione`](#autocompletastazione), ma con un risultato in meno: non è presente "PIAZZALE EST TIBURTINA|S08226".

#### autocompletaStazioneNTS

**Metodo e percorso:** `GET /autocompletaStazioneNTS/{prefisso}`

**Parametri:**

- `prefisso`: nome _case insensitive_ (anche parziale) della stazione di cui si vogliono sapere nome completo e codice.

**Risposta:**

- **Content-Type:** `text/plain`
- **Formato:** `NOME_STAZIONE|CODICE_STAZIONE`
  - Il nome della stazione è in maiuscolo.
  - Il codice della stazione è un codice di 9 o 11 cifre che inizia con `83`, seguito dal codice effettivo della stazione con eventuali zeri di padding. Il numero `83` è il [codice RICS](https://uic.org/support-activities/it/rics) privato degli zeri che identifica Ferrovie dello Stato Italiane SpA[^1]. Nella maggioranza dei casi, il codice effettivo della stazione è identico a quello restituito da `autocompletaStazione`, ma non sempre.

**Esempi:**

- Chiamando `/autocompletaStazioneNTS/firenze`, otteniamo:
  ```
  FIRENZE BINARIO S.MARCO VECCHIO|830006950
  FIRENZE CAMPO MARTE|830006900
  FIRENZE CASCINE|830006515
  FIRENZE CASTELLO|830006419
  FIRENZE RIFREDI|830006420
  FIRENZE RIFREDI DEV. OLMATELLO|830006048
  FIRENZE ROVEZZANO|830006901
  FIRENZE S.MARIA NOVELLA|830006421
  FIRENZE STATUTO|830006430
  FIRENZE P.PRATO|830006518
  FIRENZE STATUTO INT.|830006427
  FIRENZE TUTTE STAZ|830006998
  ```
- Chiamando `/autocompletaStazioneNTS/pala`, otteniamo:
  ```
  PALAGIANELLO|830011508
  PALAGIANO CHIATONA|830011464
  PALAGIANO MOTTOLA|830011509
  PALAGONIA|830012279
  PALAZZO REALE-ORLEANS|830012130
  PALAZZO S.GERVASIO-MONTEMILONE|830011303
  PALAZZOLO DELLO STELLA|830003203
  PALAZZOLO SULL'OGLIO|830001538
  PALAZZOLO VERCELLESE|830000175
  PALAZZOLO MILANESE|830025014
  ```

Ci sono diversi risultati presenti in [`autocompletaStazioneNTS`](#autocompletastazionents) che non sono presenti in [`autocompletaStazione`](#autocompletastazione) e viceversa. Nei risulati di [`autocompletaStazioneNTS`](#autocompletastazionents) in particolare sono presenti molte più località quali bivi (`BIVIO`), deviazioni (`DEV.`), posti di comunicazione (`PC`) ecc.

Ci sono anche stazioni che hanno lo stesso nome ma un codice diverso, o stazioni che hanno lo stesso codice ma un nome diverso. In quest'ultimo caso, spesso si tratta di grafie alternative per la stessa stazione, come `MALPENSA AEROPORTO T2` e `MALPENSA AEROPORTO TERMINAL 2`, ma non sempre.

Nei risultati di tutti gli altri endpoint il codice stazione è sempre nel formato restituito da [`autocompletaStazione`](#autocompletastazione), quindi è consigliabile usare tale endpoint per ottenere i codici delle stazioni.

[^1]: Una lista completa si può trovare [qui](https://www.cit-rail.org/media/files/appendix_circular_letter_10_2021_list_of_codes_2021-05-17.pdf).

#### cercaStazione

**Metodo e percorso:** `GET /cercaStazione/{prefisso}`

**Parametri:**

- `prefisso`: nome (anche parziale) della stazione di cui si vogliono sapere nome completo e codice

**Risposta:**

- **Content-Type:** `application/json`
- **Formato:** [cercaStazione.schema.json](schemas/cercaStazione.schema.json)

**Esempi:**

- Chiamando `/cercaStazione/at`, otteniamo:
  ```json
  [
    {
      "id": "S07998",
      "label": "Ateleta",
      "nomeBreve": "Ateleta",
      "nomeLungo": "ATELETA"
    },
    {
      "id": "S09904",
      "label": null,
      "nomeBreve": "Atena",
      "nomeLungo": "ATENA"
    },
    {
      "id": "S08207",
      "label": "Attigliano",
      "nomeBreve": "ATTIGLIANO",
      "nomeLungo": "ATTIGLIANO-BOMARZO"
    }
  ]
  ```
- Chiamando `/cercaStazione/apice`, otteniamo:
  ```json
  [
    {
      "id": "S09314",
      "label": "Apice",
      "nomeBreve": "Apice S.A.B.",
      "nomeLungo": "APICE S.ARCANGELO BONITO"
    }
  ]
  ```
- Chiamando `/cercaStazione/anversa`, otteniamo:
  ```json
  [
    {
      "id": "S08537",
      "label": "Anversa",
      "nomeBreve": "Anversa V. S.",
      "nomeLungo": "ANVERSA-VILLALAGO-SCANNO"
    }
  ]
  ```
- Chiamando `/cercaStazione/milano p`, otteniamo:
  ```json
  [
    {
      "id": "S01645",
      "label": "Mi.p.garibaldi",
      "nomeBreve": "MI.P.GARIBALDI",
      "nomeLungo": "MILANO PORTA GARIBALDI"
    },
    {
      "id": "S01647",
      "label": "Mi",
      "nomeBreve": "Mi P.Gar.Sott.",
      "nomeLungo": "MILANO PORTA GARIBALDI SOTTERRANEA"
    },
    {
      "id": "S01631",
      "label": "Mi.p.genova",
      "nomeBreve": "MI.P.GENOVA",
      "nomeLungo": "MILANO PORTA GENOVA"
    },
    {
      "id": "S01632",
      "label": "Milano",
      "nomeBreve": "Milano P.Romana",
      "nomeLungo": "MILANO PORTA ROMANA"
    },
    {
      "id": "S01649",
      "label": "Mi.",
      "nomeBreve": "Mi. P. Venezia",
      "nomeLungo": "MILANO PORTA VENEZIA"
    },
    {
      "id": "S01633",
      "label": "Mi.",
      "nomeBreve": "MI. P. VITTORIA",
      "nomeLungo": "MILANO PORTA VITTORIA"
    }
  ]
  ```

#### regione

**Metodo e percorso:** `GET /regione/{codiceStazione}`
**Parametri:**

- `codiceStazione`: codice della stazione di cui si vuole sapere la regione nel formato `^S\d{5}$` (es. `S01700` per Milano Centrale)

**Risposta:**

- **Content-Type:** `text/plain`
- **Formato:** codice della regione in cui si trova la stazione

**Esempi:**

- Chiamando `/regione/S01700`, dove `S01700` è il codice di Milano Centrale, otteniamo `1` (Lombardia).
- Chiamando `/regione/S06421`, dove `S06421` è il codice di Firenze Santa Maria Novella, otteniamo `13` (Toscana).

Di seguito è riportata una tabella con i codici delle regioni e i loro nomi.

| Codice | Regione                       |
| ------ | ----------------------------- |
| 0      | Italia                        |
| 1      | Lombardia                     |
| 2      | Liguria                       |
| 3      | Piemonte                      |
| 4      | Valle d'Aosta                 |
| 5      | Lazio                         |
| 6      | Umbria                        |
| 7      | Molise                        |
| 8      | Emilia Romagna                |
| 9      | Trentino-Alto Adige           |
| 10     | Friuli-Venezia Giulia         |
| 11     | Marche                        |
| 12     | Veneto                        |
| 13     | Toscana                       |
| 14     | Sicilia                       |
| 15     | Basilicata                    |
| 16     | Puglia                        |
| 17     | Calabria                      |
| 18     | Campania                      |
| 19     | Abruzzo                       |
| 20     | Sardegna                      |
| 21     | Provincia autonoma di Trento  |
| 22     | Provincia autonoma di Bolzano |

#### dettaglioStazione

**Metodo e percorso:** `GET /dettaglioStazione/{codiceStazione}/{codiceRegione}`

**Parametri:**

- `codiceStazione`: codice della stazione di cui si vogliono sapere i dettagli nel formato `^(S|F)\d{5}$` (es. `S01700` per Milano Centrale).
- `codiceRegione`: codice della regione in cui si trova la stazione (es. `1` per Lombardia), ottenibile da [`regione`](#regione).

**Risposta:**

- **Content-Type:** `application/json`
- **Formato:** [dettaglioStazione.schema.json](schemas/dettaglioStazione.schema.json)

#### elencoStazioni

**Metodo e percorso:** `GET /elencoStazioni/{codiceRegione}`

**Parametri:**

- `codiceRegione`: codice della regione in cui si vogliono sapere le stazioni (es. `1` per Lombardia), ottenibile da [`regione`](#regione).

**Risposta:**

- **Content-Type:** `application/json`
- **Formato:** [elencoStazioni.schema.json](schemas/elencoStazioni.schema.json)

### Partenze e arrivi

L'analisi dei seguenti endpoint è più complicata in quanto i dati sono molto più variabili (per quanto possano nascere nuove stazioni o possano cambiare nome, partenze e arrivi cambiano ogni minuto). Pertanto, bisogna prendere con le pinze i JSON Schema riportati, che comunque contengono esempi di dati reali restituiti dagli endpoint.

Nonostante i campi presenti siano gli stessi, le informazioni ottenibili da questi endpoint e da [`andamentoTreno`](#andamentotreno) (le cui risposte sono un'estensione di quelle di `partenze` e `arrivi`) differiscono. Alcuni campi sono `null` nelle risposte di `partenze`, ma non in quelle di `arrivi`, e viceversa. Per questo motivo sono stati creati JSON Schema distinti per ciascun endpoint.

Quanto detto di seguito vale invece per tutti e tre gli endpoint. Per capire meglio come sono strutturati i dati, è consigliabile guardare prima i JSON Schema disponibili nella cartella [`schemas`](schemas).

Il campo `codiceCliente` si riferisce al codice cliente RFI e identifica l'impresa ferroviaria.

| `codiceCliente` | Impresa ferroviaria        |
| --------------- | -------------------------- |
| 1               | Trenitalia (alta velocità) |
| 2               | Trenitalia (regionali)     |
| 4               | Trenitalia (InterCity)     |
| 18              | Trenitalia Tper            |
| 63              | Trenord                    |
| 64              | TILO                       |
| 910             | Ferrovie del Sud Est       |

Il nome effettivo con cui un'impresa ferroviaria è registrata presso RFI può essere diverso da quello riportato in questa tabella (possibilmente non esaustiva), ma non è pubblicamente disponibile o quantomeno non è stato trovato.

Le maggior parte delle immagini che indicano ritardi o cancellazioni sono visibili aprendo la legenda di [ViaggiaTreno], sebbene alcune di esse non siano più presenti (ad esempio quella per la mancata rilevazione, che è presente ma non nella legenda).

![Legenda](images/legenda.png)

#### partenze

**Metodo e percorso:** `GET /partenze/{codiceStazione}/{dataOra}`

**Parametri:**

- `codiceStazione`: codice della stazione di cui si vogliono sapere le partenze nel formato `^S\d{5}$` (es. `S01700` per Milano Centrale)
- `dataOra`: data e ora in cui si vogliono vedere le partenze un formato simile a quello prodotto dalla funzione `Date.toUTCString()` di JavaScript, ad esempio:

  - `Sun Jun 2 2024 20:00:00`
  - `Fri, Jul 11 2025 13:20:00 GMT+0100 (Central European Time)`
  - `Mon, Feb 10 2025 06:30:00 UTC-0100`

**Risposta:**

- **Content-Type:** `application/json`
- **Formato:** [partenze.schema.json](schemas/partenze.schema.json)

Si noti il gran numero di campi `const` che sono presenti in questo schema. Questi campi non danno informazioni e possono essere ignorati. Per avere maggiori informazioni, è possibile integrare i dati con [`andamentoTreno`](#andamentotreno).

#### arrivi

**Metodo e percorso:** `GET /arrivi/{codiceStazione}/{dataOra}`

**Parametri:**

- `codiceStazione`: codice della stazione di cui si vogliono sapere gli arrivi nel formato `^S\d{5}$` (es. `S01700` per Milano Centrale)
- `dataOra`: data e ora in cui si vogliono vedere gli arrivi un formato simile a quello prodotto dalla funzione `Date.toUTCString()` di JavaScript, ad esempio:

  - `Sun Jun 2 2024 20:00:00`
  - `Fri, Jul 11 2025 13:20:00 GMT+0100 (Central European Time)`
  - `Mon, Feb 10 2025 06:30:00 UTC-0100`

**Risposta:**

- **Content-Type:** `application/json`
- **Formato:** [arrivi.schema.json](schemas/arrivi.schema.json)

Anche in questo caso sono presenti molti campi `const` che non danno informazioni e possono essere ignorati. Per avere maggiori informazioni, è possibile integrare i dati con [`andamentoTreno`](#andamentotreno).

### Stato treni

#### cercaNumeroTrenoTrenoAutocomplete

**Metodo e percorso:** `GET /cercaNumeroTrenoTrenoAutocomplete/{numeroTreno}`

**Parametri:**

- `numeroTreno`: numero del treno di cui si vuole ottenere l'identificativo univoco. Il numero di un treno infatti non è univoco, ma la terna data da numero del treno, codice della stazione di partenza e data di partenza lo è.

**Risposta:**

- **Content-Type:** `text/plain`
- **Formato:** `^(\d+) - ([^|]+) - (\d{2}/\d{2}/\d{2})\|(\d+)-(S\d{5})-(\d+)$`
  - La prima parte (prima del `|`) contiene numero del treno, nome della stazione di partenza e data di partenza nel formato `dd/mm/yy`.
  - La seconda parte (dopo il `|`) contiene il numero del treno, il codice della stazione di partenza e la data di partenza in millisecondi dalla Unix Epoch.

**Esempi:**

I seguenti esempi sono stati ottenuti chiamando l'endpoint nella notte tra il 21 e il 22 luglio 2025.

- Chiamando `/cercaNumeroTrenoTrenoAutocomplete/3041`, otteniamo:
  ```
  3041 - MILANO ROGOREDO - 21/07/25|3041-S01820-1753048800000
  3041 - MILANO ROGOREDO - 22/07/25|3041-S01820-1753135200000
  ```
- Chiamando `/cercaNumeroTrenoTrenoAutocomplete/770`, otteniamo:
  ```
  770 - TRIESTE CENTRALE - 21/07/25|770-S03317-1753048800000
  770 - CAMNAGO-LENTATE - 22/07/25|770-S01316-1753135200000
  770 - TRIESTE CENTRALE - 22/07/25|770-S03317-1753135200000
  ```
- Chiamando `/cercaNumeroTrenoTrenoAutocomplete/2031`, otteniamo:
  ```
  2031 - TORINO PORTA NUOVA - 22/07/25|2031-S00219-1753135200000
  ```

Questo endpoint è utile per ottenere i dati necessari per chiamare altri endpoint come [`andamentoTreno`](#andamentotreno) o `tratteCanvas`.

#### cercaNumeroTreno

**Metodo e percorso:** `GET /cercaNumeroTreno/{numeroTreno}`

**Parametri:**

- `numeroTreno`: numero del treno di cui si vogliono ottenere le informazioni

**Risposta:**

- **Content-Type:** `application/json`
- **Formato:** [cercaNumeroTreno.schema.json](schemas/cercaNumeroTreno.schema.json)

**Esempi:**

I seguenti esempi sono stati ottenuti chiamando l'endpoint nella notte tra il 21 e il 22 luglio 2025. Si noti la differenza con i dati restituiti dall'endpoint `/cercaNumeroTrenoTrenoAutocomplete`: in questo caso, viene restituito un solo treno.

- Chiamando `/cercaNumeroTreno/770`, otteniamo:
  ```json
  {
    "numeroTreno": "770",
    "codLocOrig": "S01316",
    "descLocOrig": "CAMNAGO-LENTATE",
    "dataPartenza": "2025-07-22",
    "corsa": "00770A",
    "h24": false,
    "tipo": "PG",
    "millisDataPartenza": "1753135200000",
    "formatDataPartenza": null
  }
  ```
- Chiamando `/cercaNumeroTreno/3041`, otteniamo:
  ```json
  {
    "numeroTreno": "3041",
    "codLocOrig": "S01820",
    "descLocOrig": "MILANO ROGOREDO",
    "dataPartenza": "2025-07-22",
    "corsa": "03341A",
    "h24": true,
    "tipo": "PG",
    "millisDataPartenza": "1753135200000",
    "formatDataPartenza": " 22/07/25"
  }
  ```

#### andamentoTreno

**Metodo e percorso:** `GET /andamentoTreno/{codiceStazione}/{numeroTreno}/{dataPartenza}`

**Parametri:**

- `codiceStazione`: codice della stazione di partenza del treno nel formato `^S\d{5}$` (es. `S01700` per Milano Centrale)
- `numeroTreno`: numero del treno (es. `2030` per il treno Milano Centrale - Torino Porta Nuova)
- `dataPartenza`: data di partenza del treno in millisecondi dalla Unix Epoch (es. `1753135200000` per il 22 luglio 2025)

**Risposta:**

- **Content-Type:** `application/json`
- **Formato:** [andamentoTreno.schema.json](schemas/andamentoTreno.schema.json)

> [!WARNING]
> La documentazione di questo endpoint è un _work in progress_.
> È quasi sicuro che il JSON Schema attuale della risposta contenga errori.
> Per il momento, si può solo fare affidamento sul nome dei campi.

[API]: http://www.viaggiatreno.it/infomobilita/rest-jsapi
[location code]: https://uic.org/support-activities/it/location-codes-enee
[ViaggiaTreno]: http://www.viaggiatreno.it
