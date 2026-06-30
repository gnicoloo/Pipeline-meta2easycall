# Meta Lead Ads → EasyCall

Pipeline leggera che scarica i lead da **più Pagine Facebook**, estrae `nome, cognome, email, telefono, località`, instrada ogni lead alla campagna **EasyCall** giusta e lo invia via API.

Lo script **scopre le Pagine e i loro moduli da solo** (via `/me/accounts`): non serve cercare gli ID dei moduli a mano.

Dipendenze: nessuna. Solo Python standard library.

---

## File del progetto

| File | A cosa serve |
| --- | --- |
| `main.py` | Lo script principale. Non va modificato. |
| `config.json` | **Qui inserisci i tuoi dati** (token, pagine, campagne). |
| `dashboard.html` | Dashboard interattiva. Aprila nel browser dopo ogni import. |
| `state.json` | Automatico. IDs dei lead già inviati (deduplica). |
| `log.txt` | Automatico. Storico di ogni esecuzione. |
| `meta_leads.csv` | Automatico. Storico di tutti i lead importati da Meta. |
| `leads_history.csv` | Automatico. Export EasyCall (legacy) unificato con meta_leads. |
| `dashboard_data.js` | Automatico. Dati per la dashboard, rigenerati ad ogni avvio. |
| `csv/` | Cartella con CSV di riferimento per campagna (arezzo, figline, firenze, maiora). |

---

## Configurazione (`config.json`)

### 1. Token Meta — `meta.access_token`

Un **token utente long-lived** (~60 giorni). Lo script lo usa per chiamare `/me/accounts` e ottenere i token delle Pagine. Vedi la sezione [Creare il token Meta](#creare-il-token-meta) per crearlo.

### 2. Pagine — `meta.pages`

Tre pagine preconfigurate:

| ID | Nome | Modalità |
| --- | --- | --- |
| `93644523828` | Mobilmarket | routing per località |
| `108078727754043` | Arredamento Italia | routing per località |
| `1840294139572597` | Maiora Interiors | campagna fissa (`LEAD giornalieri Maiora`) |

Parametri opzionali:
- `lookback_days` (default `7`): quanti giorni indietro scaricare i lead.
- `api_version` (default `"v25.0"`): versione Graph API.

### 3. EasyCall — `easycall`

| Campo | Descrizione |
| --- | --- |
| `url` | Endpoint API EasyCall di produzione. |
| `token` | Token di fallback (usato se la campagna non ha un token dedicato). |
| `channel` | Canale da impostare (default `"facebook"`). |
| `campaign_tokens` | **Mappa campagna → token.** Ogni campagna ha il suo token API EasyCall. |

Struttura `campaign_tokens`:

```json
"campaign_tokens": {
  "LEAD giornalieri Firenze": "<token>",
  "LEAD giornalieri Arezzo":  "<token>",
  "LEAD giornalieri Figline": "<token>",
  "LEAD giornalieri Maiora":  "<token>"
}
```

I nomi delle campagne devono coincidere **esattamente** con quelli configurati su EasyCall (campo `Campaign`).

### 4. Campi località — `locality.field_names`

Lista di nomi di campo Meta da cui estrarre la località del lead. Già impostati su `["city", "citta", "città", "provincia", "localita", "località", "comune"]`.

### 5. Routing per provincia — `routing`

Associa province, sigle e comuni alla campagna giusta.

| Zona | Campagna |
| --- | --- |
| Arezzo, Grosseto, Livorno e relativi comuni | `LEAD giornalieri Arezzo` |
| Pisa, Massa-Carrara, Lucca e relativi comuni | `LEAD giornalieri Figline` |
| Firenze | `LEAD giornalieri Firenze` |
| Tutto il resto (default) | `LEAD giornalieri Firenze` |

La tabella `by_keyword` contiene sigle (`ar`, `gr`, `lu`…), nomi di provincia e nomi di comuni. Lo script risolve nell'ordine: stringa intera → sigla provincia → nome composto → parola singola → default.

> ⚠️ La lista dei comuni non è esaustiva. Se un comune viene instradato male, aggiungi una riga in `by_keyword` in `config.json` (es. `"pietrasanta": "LEAD giornalieri Figline"`) e riavvia. Niente ricompilazione.

---

## Creare il token Meta

1. Vai su **developers.facebook.com/tools/explorer** (Graph API Explorer).
2. Seleziona la tua App.
3. Clicca **Generate Access Token → Get User Access Token** (token **utente**, non "page").
4. Spunta i permessi: `leads_retrieval`, `pages_show_list`, `pages_read_engagement`, `ads_management`.
5. Copia il token.

### Renderlo long-lived (~60 giorni)

Nell'Explorer esegui:

```
GET /oauth/access_token?grant_type=fb_exchange_token
    &client_id={APP_ID}
    &client_secret={APP_SECRET}
    &fb_exchange_token={TOKEN_BREVE}
```

`APP_ID` e `APP_SECRET` si trovano in developers.facebook.com → **Impostazioni → Base**.
Copia il token dalla risposta e incollalo in `config.json` → `meta.access_token`.

> I token-pagina ricavati da `/me/accounts` a partire da un token utente long-lived non scadono finché non cambi password o permessi.

---

## Avviare lo script

```bash
python main.py
```

L'output mostra le pagine trovate, i moduli per pagina e il riepilogo finale:

```
Nuovi: 12 | Inviati: 11 | Recuperati in history: 0 | Saltati (no contatto): 1 | Errori: 0
```

Alla fine viene aggiornato anche `dashboard_data.js`.

---

## Dashboard

Apri `dashboard.html` nel browser dopo ogni import per visualizzare lead per campagna, data e pagina di provenienza. I dati vengono letti direttamente da `dashboard_data.js` (aggiornato ad ogni avvio di `main.py`).

---

## Creare l'eseguibile (`.exe`)

Sul PC Windows, una volta sola:

```bash
pip install pyinstaller
pyinstaller --onefile --name MetaEasyCall main.py
```

Poi:

1. Copia `dist/MetaEasyCall.exe` nella cartella dell'operatore.
2. **Metti `config.json` nella stessa cartella** dell'`.exe`.
3. `state.json`, `log.txt`, `meta_leads.csv` e `dashboard_data.js` si creano lì automaticamente.
4. Copia anche `dashboard.html` nella stessa cartella se vuoi usare la dashboard.

### Avvio automatico all'accensione (opzionale)

`Win + R` → `shell:startup` → Invio: crea un collegamento a `MetaEasyCall.exe`. Ad ogni avvio del PC lo script gira, importa i nuovi lead e si chiude (se non è in modalità interattiva non attende l'INVIO).

---

## Deduplica

Ogni lead Meta ha un `id` univoco. Dopo un invio riuscito l'ID finisce in `state.json` e non verrà mai rispedito. **Non cancellare `state.json`** o rischi doppioni su EasyCall.

Lo script gestisce anche il caso di lead già presenti in `state.json` ma assenti da `meta_leads.csv` (recovery automatico dopo merge manuali del CSV).

---

## Errori comuni (in `log.txt`)

| Messaggio | Causa | Soluzione |
| --- | --- | --- |
| `nessuna pagina accessibile` | Token errato/scaduto o permessi mancanti | Rigenera il token |
| `pagina '...' non accessibile` | Il token non amministra quella pagina | Verifica di essere Admin della pagina |
| `nessun token EasyCall configurato per la campagna '...'` | Campagna non presente in `campaign_tokens` | Aggiungi il token in `config.json` |
| `401 token EasyCall non valido` | Token EasyCall errato | Controlla `campaign_tokens` |
| `400 payload non valido` | Campo non accettato da EasyCall | Verifica con Easy4Cloud i campi attesi |
| `SKIP lead ... manca email e telefono` | Lead senza contatti | Normale: EasyCall richiede almeno uno dei due |

---

## Nota privacy (GDPR)

I lead sono dati personali. Assicurati che le form Meta raccolgano il consenso e che il trattamento su EasyCall sia coperto da informativa. Se necessario, lo script può essere esteso per mappare anche il campo consenso (`Optin`).
