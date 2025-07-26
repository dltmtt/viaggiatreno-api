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

Una volta ottenuto il codice della stazione, è possibile chiamare `partenze` o `arrivi` per ottenere i treni in partenza o in arrivo da quella stazione. Il risultato di queste chiamate è una lista di treni con informazioni come il numero del treno, la destinazione, l'orario di partenza e arrivo, il ritardo, il binario programmato e quello effettivo. Queste informazioni sembrano sufficienti per ottenere le informazioni di interesse, ma alcuni dati non sono sempre affidabili. Per ovviare a questo problema, è possibile integrare con i dati di `andamentoTreno`.

`andamentoTreno` ci permette di ottenere informazioni più dettagliate e accurate sullo stato di un treno in viaggio, come il suo itinerario, le fermate effettuate, i ritardi e altre informazioni utili. Questo endpoint è particolarmente utile per verificare lo stato effettivo del treno e per ottenere informazioni sulle fermate intermedie.

### Script CLI

È disponibile uno script Python CLI in [`scripts/viaggiatreno-api.py`](scripts/viaggiatreno-api.py) che fornisce accesso semplificato agli endpoint documentati:

- I nomi degli endpoint sono in _kebab-case_ invece che in _title-case_.
- I parametri sono passati come argomenti dalla linea di comando, con alcune semplificazioni:
  - Si possono passare direttamente i nomi delle stazioni al posto dei codici.
  - Le date sono accettate in formato YYYY-MM-DD e hanno come default la data corrente.
  - Gli endpoint che richiedono informazioni aggiuntive spesso possono essere chiamati con solo il dato principale (ad esempio, [`andamentoTreno`](#andamentotreno) può essere chiamato con il solo numero del treno, e lo script recupererà automaticamente stazione e data di partenza).
- L'opzione globale `-o/--output` permette di salvare l'output su file invece che visualizzarlo a schermo per tutti i comandi.
- Tramite il comando `dump-all` è possibile scaricare i dati di tutte le stazioni in un colpo solo. L'opzione `-o` specifica la cartella di destinazione (default: `dumps`).

Lo script richiede i pacchetti `requests` e `click`.

Di seguito sono riportati alcuni esempi di utilizzo:

```bash
# Cerca stazioni
uv run scripts/viaggiatreno-api.py autocompleta-stazione "Milano"

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
- **Formato:**

  ```json
  {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^S\\d{5}$",
          "description": "Codice della stazione."
        },
        "label": {
          "type": ["string", "null"],
          "description": "Nome in title case. Generalmente più corto di nomeBreve."
        },
        "nomeBreve": {
          "type": "string",
          "description": "Nome breve, tendenzialmente in title case ma talvolta in maiuscolo. Può essere uguale a nomeLungo. In genere contiene qualche abbreviazione."
        },
        "nomeLungo": {
          "type": "string",
          "description": "Nome lungo in maiuscolo."
        }
      },
      "required": ["id", "label", "nomeBreve", "nomeLungo"]
    }
  }
  ```

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
- **Formato:**

```json
{
  "$id": "RispostaDettaglioStazione",
  "type": "object",
  "properties": {
    "key": {
      "type": "string",
      "pattern": "^(S|F)\\d{5}_\\d{1,2}$",
      "description": "Chiave identificativa formata da codice della stazione e codice della regione, separati da un trattino basso.",
      "examples": ["S01700_1", "F00001_0"]
    },
    "codReg": {
      "type": "number",
      "minimum": 0,
      "maximum": 22,
      "description": "Codice della regione, lo stesso della chiamata all'endpoint."
    },
    "tipoStazione": {
      "type": "integer",
      "minimum": 1,
      "maximum": 4
    },
    "dettZoomStaz": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "key": {
            "type": "string",
            "pattern": "^(S|F)\\d{5}_\\d{1,2}$",
            "description": "Chiave identificativa formata da codice della stazione e codice della regione, separati da un trattino basso.",
            "examples": ["S01700_1", "F00001_0"]
          },
          "codiceStazione": {
            "const": { "$data": "3/codiceStazione" }
          },
          "zoomStartRange": {
            "enum": [6, 8, 9, 10]
          },
          "zoomStopRange": {
            "enum": [7, 8, 9, 11]
          },
          "pinpointVisibile": {
            "type": "boolean"
          },
          "pinpointVisible": {
            "const": { "$data": "1/pinpointVisibile" }
          },
          "labelVisibile": {
            "type": "boolean"
          },
          "labelVisible": {
            "const": { "$data": "1/labelVisibile" }
          },
          "codiceRegione": {
            "const": { "$data": "3/codReg" }
          }
        },
        "required": [
          "key",
          "codiceStazione",
          "zoomStartRange",
          "zoomStopRange",
          "pinpointVisibile",
          "pinpointVisible",
          "labelVisibile",
          "labelVisible",
          "codiceRegione"
        ]
      }
    },
    "pstaz": {
      "const": [],
      "deprecated": true
    },
    "mappaCitta": {
      "const": {
        "urlImagePinpoint": "",
        "urlImageBaloon": ""
      },
      "deprecated": true
    },
    "codiceStazione": {
      "type": "string",
      "pattern": "^(S|F)\\d{5}$",
      "description": "Codice identificativo della stazione",
      "examples": ["S01700", "F00001"]
    },
    "codStazione": {
      "const": { "$data": "1/codiceStazione" }
    },
    "lat": {
      "type": "number",
      "description": "Latitudine della stazione.",
      "minimum": -90.0,
      "maximum": 90.0
    },
    "lon": {
      "type": "number",
      "description": "Longitudine della stazione.",
      "minimum": -180.0,
      "maximum": 180.0
    },
    "latMappaCitta": {
      "$comment": "Sempre a 0.0 tranne per l'AV di Reggio Emilia (codice S05254).",
      "type": "number",
      "minimum": -90.0,
      "maximum": 90.0
    },
    "lonMappaCitta": {
      "$comment": "Sempre a 0.0 tranne per l'AV di Reggio Emilia.",
      "type": "number",
      "minimum": -180.0,
      "maximum": 180.0
    },
    "localita": {
      "type": "object",
      "properties": {
        "nomeLungo": {
          "type": "string",
          "description": "Nome lungo in maiuscolo, rarissime eccezioni in title case."
        },
        "nomeBreve": {
          "type": "string",
          "description": "Nome breve, può essere uguale a nomeLungo. In rare eccezioni addirittura più lungo di nomeLungo."
        },
        "label": {
          "type": "string"
        },
        "id": {
          "const": { "$data": "2/codiceStazione" }
        }
      },
      "required": ["nomeLungo", "nomeBreve", "label", "id"]
    },
    "esterno": {
      "type": "boolean",
      "description": "Vero se la stazione non è realmente nella regione indicata da codReg."
    },
    "offsetX": {
      "type": "integer"
    },
    "offsetY": {
      "type": "integer"
    },
    "nomeCitta": {
      "type": "string",
      "description": "Nome della città della stazione. Non affidabile: in quasi l'80% dei casi è 'A'."
    }
  },
  "required": [
    "key",
    "codReg",
    "tipoStazione",
    "dettZoomStaz",
    "pstaz",
    "mappaCitta",
    "codiceStazione",
    "codStazione",
    "lat",
    "lon",
    "latMappaCitta",
    "lonMappaCitta",
    "localita",
    "esterno",
    "offsetX",
    "offsetY",
    "nomeCitta"
  ],
  "allOf": [
    {
      "if": {
        "properties": { "codiceStazione": { "pattern": "^F\\d{5}$" } }
      },
      "then": {
        "properties": {
          "tipoStazione": { "const": 4 },
          "localita": {
            "properties": {
              "nomeLungo": { "const": { "$data": "2/codiceStazione" } },
              "nomeBreve": { "const": { "$data": "2/codiceStazione" } },
              "label": { "const": "" },
              "id": { "const": { "$data": "2/codiceStazione" } }
            },
            "nomeCitta": { "const": { "$data": "2/codiceStazione" } }
          }
        }
      }
    }
  ]
}
```

#### elencoStazioni

**Metodo e percorso:** `GET /elencoStazioni/{codiceRegione}`

**Parametri:**

- `codiceRegione`: codice della regione in cui si vogliono sapere le stazioni (es. `1` per Lombardia), ottenibile da [`regione`](#regione).

**Risposta:**

- **Content-Type:** `application/json`
- **Formato:**

```json
{
  "type": "array",
  "items": {
    "$ref": "#RispostaDettaglioStazione"
  }
}
```

### Partenze e arrivi

L'analisi dei seguenti endpoint è più complicata in quanto i dati sono molto più variabili (per quanto possano nascere nuove stazioni o possano cambiare nome, partenze e arrivi cambiano ogni minuto). Pertanto, bisogna prendere con le pinze i JSON Schema riportati, che comunque contengono esempi di dati reali restituiti dagli endpoint.

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
- **Formato:** array di oggetti che rappresentano i treni in partenza

```json
{
  "$id": "RispostaPartenzeArrivi",
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "arrivato": {
        "type": "boolean",
        "description": "Se il treno è già arrivato a destinazione."
      },
      "dataPartenzaTrenoAsDate": {
        "type": "string",
        "format": "date",
        "description": "Data di partenza del treno in formato YYYY-MM-DD."
      },
      "dataPartenzaTreno": {
        "type": "integer",
        "description": "Data di partenza del treno in millisecondi dalla Unix Epoch."
      },
      "partenzaTreno": {
        "type": ["integer", "null"],
        "description": "Ora di partenza del treno in millisecondi dalla Unix Epoch."
      },
      "millisDataPartenza": {
        "type": "string",
        "description": "Data di partenza del treno in millisecondi dalla Unix Epoch come stringa."
      },
      "numeroTreno": {
        "type": "integer",
        "description": "Numero identificativo del treno."
      },
      "categoria": {
        "$comment": "Sembra essere meno dettagliato di categoriaDescrizione, ad esempio le  Frecce vedono questo campo vuoto.",
        "type": "string",
        "examples": ["REG", "EXP", "IC", "ICN", "EC", ""]
      },
      "categoriaDescrizione": {
        "$comment": "Lo spazio non è un errore, è così che viene restituito.",
        "type": "string",
        "description": "Categoria del treno.",
        "examples": [
          "REG",
          "EXP",
          "IC",
          "ICN",
          "EC",
          "EC FR",
          " FR",
          " FA",
          " FB"
        ]
      },
      "origine": {
        "type": ["string", "null"],
        "description": "Nome della stazione di origine del treno, più o meno. Ad esempio, i treni che collegano Parigi con Milano hanno questo campo impostato a `MODANE`."
      },
      "codOrigine": {
        "type": "string",
        "pattern": "^S\\d{5}$",
        "description": "Codice della stazione di origine del treno."
      },
      "destinazione": {
        "type": "string",
        "description": "Nome della stazione di destinazione del treno, più o meno. Anche se è presente un campo `destinazioneEstera`, è possibile che anche questo campo contenga il nome di una stazione che si trova all'estero. Ad esempio, i treni che collegano Milano con Parigi hanno questo campo impostato a `MODANE` e `destinazioneEstera` a `PARIS-GARE-DE-LYON`."
      },
      "codDestinazione": {
        "type": ["string", "null"],
        "pattern": "^S\\d{5}$",
        "description": "Codice della stazione di destinazione del treno."
      },
      "origineEstera": {
        "const": null
      },
      "destinazioneEstera": {
        "type": ["string", "null"],
        "description": "Nome della stazione di destinazione estera del treno.",
        "examples": ["PARIS-GARE-DE-LYON", "ZUERICH HB"]
      },
      "oraPartenzaEstera": {
        "const": null
      },
      "oraArrivoEstera": {
        "const": null
      },
      "tratta": {
        "const": 0
      },
      "regione": {
        "const": 0
      },
      "origineZero": {
        "const": null,
        "description": "Origine programmata del treno. Può cambiare se il treno parte da una stazione diversa da quella programmata. Questo il significato teorico, ma in pratica è sempre `null`."
      },
      "destinazioneZero": {
        "const": null,
        "description": "Destinazione programmata del treno. Può cambiare se il treno arriva in una stazione diversa da quella programmata. Questo il significato teorico, ma in pratica è sempre `null`."
      },
      "orarioPartenzaZero": {
        "const": null
      },
      "orarioArrivoZero": {
        "const": null
      },
      "circolante": {
        "type": "boolean"
      },
      "codiceCliente": {
        "type": "integer",
        "examples": [1, 2, 4, 18, 63, 910]
      },
      "binarioEffettivoArrivoCodice": {
        "type": ["string", "null"],
        "examples": ["161", "167", "169", "344", "1075"]
      },
      "binarioEffettivoArrivoDescrizione": {
        "type": ["string", "null"],
        "examples": ["5", "7", "VII", "14"]
      },
      "binarioEffettivoArrivoTipo": {
        "type": ["string", "null"],
        "examples": ["0"]
      },
      "binarioProgrammatoArrivoCodice": {
        "type": ["string", "null"],
        "examples": ["0"]
      },
      "binarioProgrammatoArrivoDescrizione": {
        "type": ["string", "null"],
        "examples": ["4", "VII", "13"]
      },
      "binarioEffettivoPartenzaCodice": {
        "type": ["string", "null"],
        "examples": ["2", "166", "167", "171", "1979", "1985"]
      },
      "binarioEffettivoPartenzaDescrizione": {
        "type": ["string", "null"],
        "examples": ["16", "1", "6", "2TR"]
      },
      "binarioEffettivoPartenzaTipo": {
        "type": ["string", "null"],
        "examples": ["0"]
      },
      "binarioProgrammatoPartenzaCodice": {
        "type": ["string", "null"]
      },
      "binarioProgrammatoPartenzaDescrizione": {
        "type": ["string", "null"],
        "examples": ["9", "II", "15", "XVII", "18", "1 Tr MI", "VIT"]
      },
      "subTitle": {
        "$comment": "Sempre `null` con `partenze` e `arrivi`, ma presente in `andamentoTreno`.",
        "type": ["string", "null"],
        "examples": [
          "Treno cancellato da TREVIGLIO a MILANO VILLAPIZZONE. Il treno oggi parte da MILANO PORTA GARIBALDI.",
          "Treno cancellato",
          ""
        ]
      },
      "esisteCorsaZero": {
        "$comment": "Sempre `null` in `partenze` e `arrivi`, ma presente in `andamentoTreno`.",
        "type": ["string", "null"],
        "examples": ["0", null]
      },
      "orientamento": {
        "enum": ["A", "B", null],
        "description": "Orientamento del treno, può essere A (executive/business/1 classe in coda) o B (executive/business/1 classe in testa). È `null` per i treni che non sono distinti in classi o che non prevedono la prenotazione dei posti, come i regionali."
      },
      "inStazione": {
        "type": "boolean"
      },
      "haCambiNumero": {
        "type": "boolean",
        "description": "Indica se il treno cambia numero durante il viaggio."
      },
      "nonPartito": {
        "type": "boolean",
        "description": "Se il treno non è ancora partito."
      },
      "provvedimento": {
        "$comment": "Probabilmente ha a che fare con soppressioni di fermate, cancellazioni o simili.",
        "type": "number",
        "$examples": [0, 1, 3]
      },
      "riprogrammazione": {
        "$comment": "Sembra essere sempre `N` in `partenze` e `arrivi`, e `null` in `andamentoTreno`.",
        "type": ["string", "null"],
        "examples": ["N", null]
      },
      "orarioPartenza": {
        "type": ["integer", "null"],
        "description": "Orario di partenza in millisecondi dalla Unix Epoch."
      },
      "orarioArrivo": {
        "type": ["integer", "null"],
        "description": "Orario di arrivo in millisecondi dalla Unix Epoch."
      },
      "stazionePartenza": {
        "const": null
      },
      "stazioneArrivo": {
        "const": null
      },
      "statoTreno": {
        "const": null
      },
      "corrispondenze": {
        "const": []
      },
      "servizi": {
        "const": []
      },
      "ritardo": {
        "type": "number",
        "description": "Ritardo del treno in minuti. Se negativo indica un anticipo. Spesso a 0 anche quando il treno è in ritardo, utilizzare andamentoTreno per informazioni più accurate."
      },
      "tipoProdotto": {
        "$comment": "Il valore 100 è associato ai Frecciarossa, il 101 è associato ai Frecciargento e il 102 ai Frecciabianca.",
        "type": "string",
        "examples": ["0", "100", "101", "102"]
      },
      "compOrarioPartenzaZeroEffettivo": {
        "type": ["string", "null"],
        "format": "time",
        "description": "Orario di partenza dalla stazione di partenza programmata",
        "examples": ["11:52", null]
      },
      "compOrarioArrivoZeroEffettivo": {
        "$comment": "Sempre `null` in `partenze` e `arrivi`, ma presente in `andamentoTreno`.",
        "type": ["string", "null"],
        "format": "time",
        "description": "Orario di arrivo effettivo nella  stazione di arrivo programmata",
        "examples": ["00:17", null]
      },
      "compOrarioPartenzaZero": {
        "type": ["string", "null"],
        "format": "time",
        "description": "Orario di partenza zero formattato (HH:MM)."
      },
      "compOrarioArrivoZero": {
        "$comment": "Sempre `null` in `partenze` e `arrivi`, ma presente in `andamentoTreno`.",
        "type": ["string", "null"],
        "format": "time",
        "description": "Orario di arrivo programmato nella stazione di arrivo programmata.",
        "examples": ["00:17", null]
      },
      "compOrarioArrivo": {
        "type": ["string", "null"],
        "format": "time",
        "description": "Orario di arrivo formattato (HH:MM)."
      },
      "compOrarioPartenza": {
        "type": ["string", "null"],
        "format": "time",
        "description": "Orario di partenza formattato (HH:MM)."
      },
      "compNumeroTreno": {
        "type": "string",
        "description": "Nome completo del treno formato da categoria e numero.",
        "examples": ["REG 2328"]
      },
      "compOrientamento": {
        "type": "array",
        "items": {
          "type": "string"
        },
        "minItems": 9,
        "maxItems": 9,
        "description": "Orientamento del treno in diverse lingue (IT, EN, DE, FR, ES, RO, JA, ZH, RU).",
        "examples": [
          ["--", "--", "--", "--", "--", "--", "--", "--", "--"],
          [
            "Business in coda",
            "Business at the rear",
            "Business Zugende",
            "Businesse en queue",
            "Business al final del tren",
            "Business la coada trenului",
            "背面のBusiness",
            "Business在后几节车厢",
            "Business в хвосте поезда"
          ],
          [
            "Executive in testa",
            "Executive in the head",
            "Executive Zugspitze",
            "Executive en t&ecirc;te",
            "Executive al inicio del tren",
            "Executive la &icirc;nceputul trenului",
            "頭の中でExecutive",
            "Executive在前几节车厢",
            "Executive в головной части поезда"
          ],
          [
            "1 classe in testa",
            "1st Class in the head",
            "1. Klasse Zugspitze ",
            "1&egrave;re classe en t&ecirc;te",
            "1&ordf; clase al inicio del tren",
            "clasa I la &icirc;nceputul trenului",
            "1等車前方",
            "一等车厢在前几节车厢",
            "1 класс в головной части поезда"
          ]
        ]
      },
      "compTipologiaTreno": {
        "type": "string",
        "description": "Tipologia del treno.",
        "examples": ["regionale", "nazionale"]
      },
      "compClassRitardoTxt": {
        "type": ["string", "null"],
        "examples": ["", "ritardo01_txt", "ritardo02_txt", "ritardo03_txt"]
      },
      "compClassRitardoLine": {
        "type": ["string", "null"],
        "examples": [
          "regolare_line",
          "ritardo01_line",
          "ritardo02_line",
          "ritardo03_line"
        ]
      },
      "compImgRitardo2": {
        "$comment": "L'immagine che indica la cancellazione del treno è presente solo qua, non in compImgRitardo.",
        "enum": [
          "/vt_static/img/legenda/icone_legenda/nonpartito.png",
          "/vt_static/img/legenda/icone_legenda/regolare.png",
          "/vt_static/img/legenda/icone_legenda/ritardo01.png",
          "/vt_static/img/legenda/icone_legenda/ritardo02.png",
          "/vt_static/img/legenda/icone_legenda/ritardo03.png",
          "/vt_static/img/avvisi/alert3.png",
          "/vt_static/img/legenda/icone_legenda/cancellazione.png"
        ]
      },
      "compImgRitardo": {
        "enum": [
          "/vt_static/img/legenda/icone_legenda/nonpartito.png",
          "/vt_static/img/legenda/icone_legenda/regolare.png",
          "/vt_static/img/legenda/icone_legenda/ritardo01.png",
          "/vt_static/img/legenda/icone_legenda/ritardo02.png",
          "/vt_static/img/legenda/icone_legenda/ritardo03.png",
          "/vt_static/img/avvisi/alert3.png"
        ],
        "description": "URL relativo del bollino che indica il ritardo. È usato da ViaggiaTreno."
      },
      "compRitardo": {
        "type": "array",
        "description": "Descrizioni del ritardo in diverse lingue (IT, EN, DE, FR, ES, RO, JA, ZH, RU).",
        "items": {
          "type": ["string", "null"]
        },
        "minItems": 9,
        "maxItems": 9,
        "examples": [
          [
            "non partito",
            "not departed",
            "keine Partei",
            "pas encore partit",
            "no sali&oacute;",
            "nu a plecat",
            "未発車",
            "未出发",
            "не отправленный"
          ],
          [
            "in orario",
            "on time",
            "p&#252;nktlich",
            "&agrave; l'heure",
            "en horario",
            "conform orarului",
            "定刻",
            "按时",
            "по расписанию"
          ],
          [
            "ritardo 1 min.",
            "delay 1 min.",
            "Versp&#228;tung 1 Min.",
            "retard de 1 min.",
            "retraso de 1 min.",
            "&icirc;nt&acirc;rziere 1 min.",
            "遅延 1 分",
            "误点 1分钟",
            "опоздание на 1 минут"
          ],
          [
            "Mancato rilevamento",
            "Missing detection",
            "Erkennung fehlgeschlagen",
            "D&eacutetection manqu&eacutee",
            "Detecciónn fallida",
            null,
            null,
            null,
            null
          ],
          [
            "Cancellato",
            "Canceled",
            "Storniert",
            "Annul&eacute",
            "Cancelado",
            null,
            null,
            null,
            null
          ]
        ]
      },
      "compRitardoAndamento": {
        "type": "array",
        "items": {
          "type": "string"
        },
        "minItems": 9,
        "maxItems": 9,
        "examples": [
          [
            "non partito",
            "not departed",
            "keine Partei",
            "pas encore partit",
            "no sali&oacute;",
            "nu a plecat",
            "未発車",
            "未出发",
            "не отправленный"
          ],
          [
            "con un anticipo di 1 min.",
            "1 minutes early",
            "mit einem Vorsprung von 1 Min.",
            "en avance de 1 min.",
            "est&aacute; adelantado 1 min.",
            "cu un avans de 1 min.",
            "1 分の繰上",
            "提前 1分钟",
            "con un anticipo di 1 min."
          ],
          [
            "con un ritardo di 1 min.",
            "1 minutes late",
            "mit einer Verz&#246;gerung von 1 Min.",
            "avec un retard de 1 min.",
            "con un retraso de 1 min.",
            "cu o &icirc;nt&acirc;rziere de 1 min.",
            "1 分の遅延",
            "误点 1分钟",
            "с опозданием в 1 минут"
          ]
        ]
      },
      "compInStazionePartenza": {
        "type": "array",
        "items": {
          "type": "string"
        },
        "minItems": 9,
        "maxItems": 9,
        "examples": [
          ["", "", "", "", "", "", "", "", ""],
          [
            "Partito",
            "Departed",
            "angef&#228;hrt",
            "Partit",
            "Salido",
            "Plecat",
            "発車済",
            "已出发",
            "отправленный"
          ]
        ]
      },
      "compInStazioneArrivo": {
        "type": "array",
        "items": {
          "type": "string"
        },
        "minItems": 9,
        "maxItems": 9,
        "examples": [
          ["", "", "", "", "", "", "", "", ""],
          [
            "Arrivato",
            "Arrived",
            "angekommen",
            "Arriv&eacute;",
            "Llegado",
            "Sosit",
            "到着済",
            "已到达",
            "прибывший"
          ]
        ]
      },
      "compOrarioEffettivoArrivo": {
        "type": ["string", "null"],
        "examples": ["/vt_static/img/legenda/icone_legenda/regolare.png17:20"]
      },
      "compDurata": {
        "$comment": "Stringa vuota in `partenze` e `arrivi`, ma presente in `andamentoTreno`. Un tempo era sbagliato se la durata superava le 24h, ma potrebbe essere stato corretto.",
        "type": "string",
        "format": "duration",
        "pattern": "^\\d{1,2}:\\d{1,2}$",
        "description": "Durata del viaggio dalla stazione di partenza a quella di arrivo",
        "examples": ["1:6", ""]
      },
      "compImgCambiNumerazione": {
        "type": "string",
        "description": "HTML per l'immagine del cambio numerazione.",
        "examples": [
          "&nbsp;&nbsp;",
          "&nbsp;&nbsp;<img src=\"/vt_static/img/legenda/icone_legenda/numerazioni.png\">"
        ]
      },
      "materiale_label": {
        "type": ["string", "null"],
        "examples": ["business"]
      },
      "ultimoRilev": {
        "type": ["integer", "null"],
        "description": "Ultimo rilevamento del treno in millisecondi dalla Unix Epoch."
      },
      "iconTreno": {
        "const": null
      }
    },
    "required": [
      "arrivato",
      "dataPartenzaTrenoAsDate",
      "dataPartenzaTreno",
      "partenzaTreno",
      "millisDataPartenza",
      "numeroTreno",
      "categoria",
      "categoriaDescrizione",
      "origine",
      "codOrigine",
      "destinazione",
      "codDestinazione",
      "origineEstera",
      "destinazioneEstera",
      "oraPartenzaEstera",
      "oraArrivoEstera",
      "tratta",
      "regione",
      "origineZero",
      "destinazioneZero",
      "orarioPartenzaZero",
      "orarioArrivoZero",
      "circolante",
      "codiceCliente",
      "binarioEffettivoArrivoCodice",
      "binarioEffettivoArrivoDescrizione",
      "binarioEffettivoArrivoTipo",
      "binarioProgrammatoArrivoCodice",
      "binarioProgrammatoArrivoDescrizione",
      "binarioEffettivoPartenzaCodice",
      "binarioEffettivoPartenzaDescrizione",
      "binarioEffettivoPartenzaTipo",
      "binarioProgrammatoPartenzaCodice",
      "binarioProgrammatoPartenzaDescrizione",
      "subTitle",
      "esisteCorsaZero",
      "orientamento",
      "inStazione",
      "haCambiNumero",
      "nonPartito",
      "provvedimento",
      "riprogrammazione",
      "orarioPartenza",
      "orarioArrivo",
      "stazionePartenza",
      "stazioneArrivo",
      "statoTreno",
      "corrispondenze",
      "servizi",
      "ritardo",
      "tipoProdotto",
      "compOrarioPartenzaZeroEffettivo",
      "compOrarioArrivoZeroEffettivo",
      "compOrarioPartenzaZero",
      "compOrarioArrivoZero",
      "compOrarioArrivo",
      "compOrarioPartenza",
      "compNumeroTreno",
      "compOrientamento",
      "compTipologiaTreno",
      "compClassRitardoTxt",
      "compClassRitardoLine",
      "compImgRitardo2",
      "compImgRitardo",
      "compRitardo",
      "compRitardoAndamento",
      "compInStazionePartenza",
      "compInStazioneArrivo",
      "compOrarioEffettivoArrivo",
      "compDurata",
      "compImgCambiNumerazione",
      "materiale_label",
      "ultimoRilev",
      "iconTreno"
    ]
  }
}
```

Il campo `codiceCliente` si riferisce al codice cliente RFI e identifica l'impresa ferroviaria. La seguente tabella, possibilmente non esaustiva, elenca i codici cliente e le relative imprese ferroviarie:

| `codiceCliente` | Impresa ferroviaria        |
| --------------- | -------------------------- |
| 1               | Trenitalia (alta velocità) |
| 2               | Trenitalia (regionali)     |
| 4               | Trenitalia (InterCity)     |
| 18              | Trenitalia Tper            |
| 63              | Trenord                    |
| 64              | TILO                       |
| 910             | Ferrovie del Sud Est       |

Il nome effettivo con cui un'impresa ferroviaria è registrata presso RFI può essere diverso da quello riportato in questa tabella, ma non è pubblicamente disponibile o quantomeno non è stato trovato.

Le maggior parte delle immagini che indicano ritardi o cancellazioni sono visibili aprendo la legenda di [ViaggiaTreno], sebbene alcune di esse non siano più presenti (ad esempio quella per la mancata rilevazione, che è presente ma non nella legenda).

![Legenda](images/legenda.png)

#### arrivi

**Metodo e percorso:** `GET /arrivi/{codiceStazione}/{dataOra}`

Identico a [`partenze`](#partenze), salvo ovviamente per il fatto che `codiceStazione` indica la stazione di cui si vogliono conoscere gli arrivi e non le partenze. In realtà, alcuni campi sono sempre impostati a `null` in questo endpoint, mentre altri lo sono in [`partenze`](#partenze). Lo schema riportato precedentemente cerca di essere generico e di coprire entrambi i casi.

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

Questo endpoint è utile per ottenere i dati necessari per chiamare altri endpoint come `andamentoTreno` o `tratteCanvas`.

#### cercaNumeroTreno

**Metodo e percorso:** `GET /cercaNumeroTreno/{numeroTreno}`

**Parametri:**

- `numeroTreno`: numero del treno di cui si vogliono ottenere le informazioni

**Risposta:**

- **Content-Type:** `application/json`
- **Formato:**

```json
{
  "type": "object",
  "properties": {
    "numeroTreno": {
      "type": "string",
      "description": "Numero del treno"
    },
    "codLocOrig": {
      "type": "string",
      "pattern": "^S\\d{5}$",
      "description": "Codice della stazione di partenza"
    },
    "descLocOrig": {
      "type": "string",
      "description": "Nome della stazione di partenza"
    },
    "dataPartenza": {
      "type": "string",
      "format": "date",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
      "description": "Data di partenza del treno",
      "examples": ["2025-07-22"]
    },
    "corsa": {
      "type": "string",
      "examples": ["00770A", "03341A"]
    },
    "h24": {
      "type": "boolean"
    },
    "tipo": {
      "type": "string",
      "description": "Tipo di treno",
      "examples": ["PG", "ST"]
    },
    "millisDataPartenza": {
      "type": "string",
      "description": "Data di partenza in millisecondi dalla Unix Epoch"
    },
    "formatDataPartenza": {
      "type": ["string", "null"],
      "format": "date",
      "pattern": "^\\s\\d{2}/\\d{2}/\\d{2}$",
      "examples": [" 22/07/25"],
      "description": "Data di partenza"
    }
  },
  "required": [
    "numeroTreno",
    "codLocOrig",
    "descLocOrig",
    "dataPartenza",
    "corsa",
    "h24",
    "tipo",
    "millisDataPartenza",
    "formatDataPartenza"
  ]
}
```

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
- **Formato:** estensione dell'oggetto restituito da [`partenze`](#partenze) e [`arrivi`](#partenze) con campi aggiuntivi

```json
{
  "allOf": [
    {
      "$ref": "#RispostaPartenzeArrivi"
    },
    {
      "type": "object",
      "properties": {
        "tipoTreno": {
          "type": "string",
          "description": "Tipo di treno",
          "examples": ["PG", "ST", "VO"]
        },
        "dataPartenza": {
          "type": "string",
          "format": "date-time",
          "description": "Data e ora di partenza del treno",
          "examples": ["2025-07-22 00:00:00.0"]
        },
        "fermateSoppresse": {
          "type": "array",
          "description": "Lista delle fermate soppresse",
          "items": {
            "type": "object"
          }
        },
        "fermate": {
          "type": "array",
          "description": "Lista dettagliata delle fermate del treno",
          "items": {
            "type": "object",
            "properties": {
              "stazione": {
                "type": "string",
                "description": "Nome della fermata"
              },
              "id": {
                "type": "string",
                "pattern": "^S\\d{5}$",
                "description": "Codice della fermata"
              },
              "codLocOrig": {
                "type": "string",
                "pattern": "^S\\d{5}$",
                "description": "Codice della stazione di origine del treno"
              },
              "programmata": {
                "type": "integer",
                "description": "Ora di partenza programmata dalla fermata se la fermata è la partenza, o di arrivo programmato se la fermata intermedia o l'arrivo, espressa in millisecondi dalla Unix Epoch"
              },
              "programmataZero": {
                "type": ["integer", "null"]
              },
              "effettiva": {
                "type": ["integer", "null"],
                "description": "Ora di partenza effettiva dalla fermata se la fermata è la partenza o è una fermata intermedia, o di arrivo effettivo se la fermata è l'arrivo, espressa in millisecondi dalla Unix Epoch"
              },
              "partenza_teorica": {
                "type": ["integer", "null"],
                "description": "Ora di partenza teorica dalla fermata in millisecondi dalla Unix Epoch"
              },
              "arrivo_teorico": {
                "type": ["integer", "null"],
                "description": "Ora di arrivo teorica dalla fermata in millisecondi dalla Unix Epoch"
              },
              "partenzaTeoricaZero": {
                "type": ["integer", "null"]
              },
              "arrivoTeoricoZero": {
                "type": ["integer", "null"]
              },
              "partenzaReale": {
                "type": ["integer", "null"],
                "description": "Ora di partenza reale dalla fermata in millisecondi dalla Unix Epoch"
              },
              "arrivoReale": {
                "type": ["integer", "null"],
                "description": "Ora di arrivo reale nella fermata in millisecondi dalla Unix Epoch"
              },
              "ritardo": {
                "type": "number",
                "description": "Ritardo in minuti. Il valore assunto equivale al ritardo alla partenza se la stazione è quella di partenza, o al ritardo all'arrivo se la stazione è una fermata intermedia o l'arrivo."
              },
              "ritardoPartenza": {
                "type": "number",
                "description": "Ritardo alla partenza in minuti"
              },
              "ritardoArrivo": {
                "type": "number",
                "description": "Ritardo all'arrivo in minuti"
              },
              "tipoFermata": {
                "type": "string",
                "enum": ["P", "F", "A", ""],
                "description": "Tipo di fermata: P (partenza), F (fermata intermedia), A (arrivo) o vuoto per fermate soppresse"
              },
              "actualFermataType": {
                "type": "integer",
                "description": "Tipo di fermata. 3 per fermate soppresse.",
                "examples": [0, 3]
              },
              "progressivo": {
                "type": "integer",
                "examples": [1, 16, 31, 33, 50, 66]
              },
              "binarioEffettivoArrivoCodice": {
                "type": ["string", "null"],
                "description": "Codice del binario effettivo di arrivo"
              },
              "binarioEffettivoArrivoDescrizione": {
                "type": ["string", "null"],
                "description": "Binario effettivo di arrivo"
              },
              "binarioEffettivoArrivoTipo": {
                "type": ["string", "null"],
                "description": "Tipo del binario effettivo di arrivo"
              },
              "binarioProgrammatoArrivoCodice": {
                "type": ["string", "null"],
                "description": "Codice del binario programmato di arrivo"
              },
              "binarioProgrammatoArrivoDescrizione": {
                "type": ["string", "null"],
                "description": "Binario programmato di arrivo",
                "examples": ["1", "6"]
              },
              "binarioEffettivoPartenzaCodice": {
                "type": ["string", "null"],
                "description": "Codice del binario effettivo di partenza"
              },
              "binarioEffettivoPartenzaDescrizione": {
                "type": ["string", "null"],
                "description": "Binario effettivo di partenza",
                "examples": ["ITR O"]
              },
              "binarioEffettivoPartenzaTipo": {
                "type": ["string", "null"],
                "description": "Tipo del binario effettivo di partenza",
                "examples": ["0"]
              },
              "binarioProgrammatoPartenzaCodice": {
                "type": ["string", "null"],
                "description": "Codice del binario programmato di partenza",
                "examples": ["601"]
              },
              "binarioProgrammatoPartenzaDescrizione": {
                "type": ["string", "null"],
                "description": "Binario programmato di partenza",
                "examples": ["5"]
              },
              "visualizzaPrevista": {
                "type": "boolean"
              },
              "nextChanged": {
                "type": "boolean"
              },
              "isNextChanged": {
                "type": "boolean"
              },
              "nextTrattaType": {
                "type": "integer"
              },
              "listaCorrispondenze": {
                "const": []
              },
              "orientamento": {
                "enum": ["A", "B", null],
                "description": "Orientamento del treno, può essere A (executive/business/1 classe in coda) o B (executive/business/1 classe in testa). È `null` per i treni che non sono distinti in classi o che non prevedono la prenotazione dei posti, come i regionali."
              },
              "kcNumTreno": {
                "type": ["string", "null"],
                "description": "Numero KC del treno"
              },
              "materiale_label": {
                "type": ["string", "null"],
                "description": "Etichetta del materiale rotabile"
              }
            },
            "required": [
              "stazione",
              "id",
              "codLocOrig",
              "programmata",
              "programmataZero",
              "effettiva",
              "partenza_teorica",
              "arrivo_teorico",
              "partenzaTeoricaZero",
              "arrivoTeoricoZero",
              "partenzaReale",
              "arrivoReale",
              "ritardo",
              "ritardoPartenza",
              "ritardoArrivo",
              "tipoFermata",
              "actualFermataType",
              "progressivo",
              "visualizzaPrevista",
              "nextChanged",
              "isNextChanged",
              "nextTrattaType",
              "listaCorrispondenze",
              "orientamento",
              "kcNumTreno",
              "materiale_label"
            ]
          }
        },
        "oraUltimoRilevamento": {
          "type": ["integer", "null"],
          "description": "Timestamp dell'ultimo rilevamento del treno in millisecondi dalla Unix Epoch",
          "examples": [1753177620000, null]
        },
        "stazioneUltimoRilevamento": {
          "type": "string",
          "description": "Nome della stazione dell'ultimo rilevamento",
          "examples": ["--", "Bivio Casirate", "MILANO CENTRALE"]
        },
        "compOraUltimoRilevamento": {
          "type": "string",
          "description": "Ora dell'ultimo rilevamento",
          "examples": ["--", "14:30"]
        },
        "idOrigine": {
          "type": "string",
          "pattern": "^S\\d{5}$",
          "description": "Codice identificativo della stazione di origine"
        },
        "idDestinazione": {
          "type": "string",
          "pattern": "^S\\d{5}$",
          "description": "Codice identificativo della stazione di destinazione"
        },
        "cambiNumero": {
          "$comment": "Sembra essere vuoto anche quando il treno ha cambi numerazione. Le proprietà erano state ricavate tempo fa, ma potrebbero essere cambiate.",
          "type": "array",
          "description": "Lista dei cambi di numerazione del treno",
          "items": {
            "type": "object",
            "properties": {
              "nuovoNumeroTreno": {
                "type": "string",
                "description": "Nuovo numero del treno dopo il cambio"
              },
              "stazione": {
                "type": "string",
                "description": "Stazione in cui avviene il cambio di numerazione"
              }
            },
            "required": ["nuovoNumeroTreno", "stazione"]
          }
        },
        "hasProvvedimenti": {
          "$comment": "Può essere `false` anche se `provvedimenti` è diverso da `0`.",
          "type": "boolean"
        },
        "anormalita": {
          "type": "array",
          "description": "Lista delle anomalie del treno",
          "items": {
            "type": "object"
          }
        },
        "provvedimenti": {
          "type": "array",
          "description": "Lista dei provvedimenti applicati al treno",
          "items": {
            "type": "object"
          }
        },
        "segnalazioni": {
          "type": "array",
          "description": "Lista delle segnalazioni relative al treno",
          "items": {
            "type": "object"
          }
        },
        "motivoRitardoPrevalente": {
          "type": ["string", "null"],
          "description": "Motivo prevalente del ritardo"
        },
        "descOrientamento": {
          "type": "array",
          "description": "Descrizione dell'orientamento del treno in diverse lingue (IT, EN, DE, FR, ES, RO, JA, ZH, RU).",
          "items": {
            "type": "string"
          },
          "minItems": 9,
          "maxItems": 9,
          "examples": [
            [
              "Executive in testa",
              "Executive in the head",
              "Executive Zugspitze",
              "Executive en t&ecirc;te",
              "Executive al inicio del tren",
              "Executive la &icirc;nceputul trenului",
              "頭の中でExecutive",
              "Executive在前几节车厢",
              "Executive в головной части поезда"
            ]
          ]
        },
        "descrizioneVCO": {
          "type": "string",
          "examples": [""]
        }
      }
    }
  ]
}
```

[API]: http://www.viaggiatreno.it/infomobilita/rest-jsapi
[location code]: https://uic.org/support-activities/it/location-codes-enee
[ViaggiaTreno]: http://www.viaggiatreno.it
