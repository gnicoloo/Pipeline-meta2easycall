# Meta Lead Ads → EasyCall — Guida

# Meta Lead Ads → EasyCall — Guida (multi-pagina)

Pipeline leggera che scarica i lead da **più Pagine Facebook**, estrae `nome, cognome, email, telefono, località`, instrada il lead alla campagna **EasyCall** giusta e lo invia via API.

Lo script **scopre le Pagine e i loro moduli da solo** (via `/me/accounts`): non devi cercare gli ID dei moduli a mano, ti bastano i 3 ID delle Pagine.

Niente database, niente librerie esterne: solo Python standard.

---

## 1. File del progetto


| File          | A cosa serve                               |
| ------------- | ------------------------------------------ |
| `main.py`     | Lo script. Non si tocca.                   |
| `config.json` | **Qui inserisci i tuoi dati.**             |
| `state.json`  | Automatico: lead già inviati (deduplica). |
| `log.txt`     | Automatico: storico esecuzioni.            |

---

## 2. Cosa inserire in `config.json`

Apri `config.json` col Blocco note. Da compilare:

### a) Token Meta — `meta.access_token`

Un **token utente long-lived** (sezione 3). Serve perché lo script chiama `/me/accounts` per ottenere le Pagine e i loro token.

### b) Le 3 Pagine — `meta.pages`

Già precompilate con i tuoi ID:

* `93644523828` → Mobilmarket (routing per località)
* `108078727754043` → Arredamento Italia (routing per località)
* `1840294139572597` → Maiora Interiors (campagna **fissa**, niente routing)

Per Maiora il campo `fixed_campaign` decide la campagna unica. Per le altre due vale la tabella `routing` (punto d).

### c) EasyCall — `easycall.token` e `easycall.url`

* `token`: la API key che ti dà Easy4Cloud.
* `url`: già impostato su `https://mobilmarket.web3.easycallcloud.com/easycall/spring/lead`. Conferma con Easy4Cloud che il percorso sia corretto.

### d) Campagne per località — `routing`

Il routing segue le tue regole **per provincia**:


| Provincia del lead                       | Campagna EasyCall                  |
| ---------------------------------------- | ---------------------------------- |
| Arezzo, Grosseto, Livorno                | LEAD giornalieri Arezzo            |
| Pisa, Massa-Carrara, Lucca               | LEAD giornalieri Figline           |
| Firenze                                  | LEAD giornalieri Firenze           |
| tutto il resto (estero, comuni distanti) | LEAD giornalieri Firenze (default) |

La tabella `by_keyword` in `config.json` associa **province, sigle e comuni** alla campagna giusta (es. `viareggio`, `lu`, `lucca` → Figline). Lo script riconosce sia la provincia diretta sia il comune, e gestisce i casi come "Massa Marittima" (che è in provincia di Grosseto → Arezzo, **non** Figline).

> ⚠️ La lista dei comuni è precompilata con i principali di ogni provincia, ma **non è esaustiva**: un comune non presente finisce nel default (Firenze). In `log.txt` vedi la località di ogni lead: se ne noti uno instradato male, aggiungi una riga in `by_keyword` (es. `"pietrasanta": "LEAD giornalieri Figline"`) e sei a posto. Niente ricompilazione.

> I valori delle campagne devono coincidere **esattamente** con il nome campagna su EasyCall (campo `Campaign` della loro API).

---

## 3. Creare il token Meta (utente long-lived)

Sei Admin delle 3 Pagine, quindi:

1. Vai su **developers.facebook.com/tools/explorer** (Graph API Explorer).
2. Seleziona la tua **App** nel menu in alto.
3. Clicca **Generate Access Token** / **Get User Access Token** (token **utente**, non "page").
4. Spunta i permessi:
   * `leads_retrieval`
   * `pages_show_list`
   * `pages_read_engagement`
   * `ads_management`
5. Copia il token (dura poche ore: ora lo rendiamo long-lived).

### Renderlo long-lived (≈60 giorni)

Sempre nell'Explorer, cambia la richiesta in:

```
GET /oauth/access_token?grant_type=fb_exchange_token&client_id={APP_ID}&client_secret={APP_SECRET}&fb_exchange_token={TOKEN_BREVE}
```

* `{APP_ID}` e `{APP_SECRET}`: in developers.facebook.com → **Impostazioni → Base**.
* `{TOKEN_BREVE}`: il token appena copiato.

La risposta contiene un token più lungo: **quello** va in `config.json`.

> Nota: i token-pagina che lo script ricava da `/me/accounts` a partire da questo token utente long-lived non scadono finché non cambi password o permessi. Quando in futuro avrai un System User, potrai sostituirlo con un token permanente senza toccare il resto.

---

## 4. Provare lo script

Su un PC con Python:

```bash
python main.py
```

Vedrai prima l'elenco delle pagine accessibili, poi i moduli trovati per pagina, e infine il riepilogo:

```
Nuovi: 12 | Inviati: 11 | Saltati (no contatto): 1 | Errori: 0
```

---

## 5. Creare l'eseguibile per l'operatore (`.exe`)

Sul PC Windows, una volta sola:

```bash
pip install pyinstaller
pyinstaller --onefile --name MetaEasyCall main.py
```

Poi:

1. Copia `dist/MetaEasyCall.exe` in una cartella dedicata.
2. **Metti `config.json` nella stessa cartella** dell'`.exe`.
3. `state.json` e `log.txt` si creano lì in automatico.

### Avvio automatico all'accensione (opzionale)

`Win + R` → `shell:startup` → Invio: crea lì un collegamento a `MetaEasyCall.exe`.

---

## 6. Deduplica

Ogni lead Meta ha un `id` univoco. Dopo l'invio riuscito finisce in `state.json` e non verrà più rispedito, anche lanciando il programma più volte al giorno. **Non cancellare `state.json`** o rischi doppioni su EasyCall.

---

## 7. Errori comuni (in `log.txt`)


| Messaggio                              | Causa                                    | Soluzione                                     |
| -------------------------------------- | ---------------------------------------- | --------------------------------------------- |
| `nessuna pagina accessibile`           | Token errato/scaduto o permessi mancanti | Rigenera il token (sez. 3)                    |
| `pagina '...' non accessibile`         | Il token non amministra quella pagina    | Verifica di essere Admin della pagina         |
| `401 token EasyCall non valido`        | Token EasyCall errato                    | Controlla`easycall.token`                     |
| `400 payload non valido`               | Campo non accettato da EasyCall          | Verifica con Easy4Cloud i campi attesi        |
| `SKIP lead ... manca email e telefono` | Lead senza contatti                      | Normale: EasyCall richiede almeno uno dei due |

---

## 8. Nota privacy (GDPR)

I lead sono dati personali: assicurati che le form raccolgano il consenso e che il trattamento su EasyCall sia coperto da informativa. Si può estendere lo script per mappare anche il campo consenso (`Optin`) se servirà.

# Meta Lead Ads → EasyCall — Guida (multi-pagina)

Pipeline leggera che scarica i lead da **più Pagine Facebook**, estrae `nome, cognome, email, telefono, località`, instrada il lead alla campagna **EasyCall** giusta e lo invia via API.

Lo script **scopre le Pagine e i loro moduli da solo** (via `/me/accounts`): non devi cercare gli ID dei moduli a mano, ti bastano i 3 ID delle Pagine.

Niente database, niente librerie esterne: solo Python standard.

---

## 1. File del progetto


| File          | A cosa serve                               |
| ------------- | ------------------------------------------ |
| `main.py`     | Lo script. Non si tocca.                   |
| `config.json` | **Qui inserisci i tuoi dati.**             |
| `state.json`  | Automatico: lead già inviati (deduplica). |
| `log.txt`     | Automatico: storico esecuzioni.            |

---

## 2. Cosa inserire in `config.json`

Apri `config.json` col Blocco note. Da compilare:

### a) Token Meta — `meta.access_token`

Un **token utente long-lived** (sezione 3). Serve perché lo script chiama `/me/accounts` per ottenere le Pagine e i loro token.

### b) Le 3 Pagine — `meta.pages`

Già precompilate con i tuoi ID:

* `93644523828` → Mobilmarket (routing per località)
* `108078727754043` → Arredamento Italia (routing per località)
* `1840294139572597` → Maiora Interiors (campagna **fissa**, niente routing)

Per Maiora il campo `fixed_campaign` decide la campagna unica. Per le altre due vale la tabella `routing` (punto d).

### c) EasyCall — `easycall.token` e `easycall.url`

* `token`: la API key che ti dà Easy4Cloud.
* `url`: già impostato su `https://mobilmarket.web3.easycallcloud.com/easycall/spring/lead`. Conferma con Easy4Cloud che il percorso sia corretto.

### d) Campagne per località — `routing`

Il routing segue le tue regole **per provincia**:


| Provincia del lead                       | Campagna EasyCall                  |
| ---------------------------------------- | ---------------------------------- |
| Arezzo, Grosseto, Livorno                | LEAD giornalieri Arezzo            |
| Pisa, Massa-Carrara, Lucca               | LEAD giornalieri Figline           |
| Firenze                                  | LEAD giornalieri Firenze           |
| tutto il resto (estero, comuni distanti) | LEAD giornalieri Firenze (default) |

La tabella `by_keyword` in `config.json` associa **province, sigle e comuni** alla campagna giusta (es. `viareggio`, `lu`, `lucca` → Figline). Lo script riconosce sia la provincia diretta sia il comune, e gestisce i casi come "Massa Marittima" (che è in provincia di Grosseto → Arezzo, **non** Figline).

> ⚠️ La lista dei comuni è precompilata con i principali di ogni provincia, ma **non è esaustiva**: un comune non presente finisce nel default (Firenze). In `log.txt` vedi la località di ogni lead: se ne noti uno instradato male, aggiungi una riga in `by_keyword` (es. `"pietrasanta": "LEAD giornalieri Figline"`) e sei a posto. Niente ricompilazione.

> I valori delle campagne devono coincidere **esattamente** con il nome campagna su EasyCall (campo `Campaign` della loro API).

---

## 3. Creare il token Meta (utente long-lived)

Sei Admin delle 3 Pagine, quindi:

1. Vai su **developers.facebook.com/tools/explorer** (Graph API Explorer).
2. Seleziona la tua **App** nel menu in alto.
3. Clicca **Generate Access Token** / **Get User Access Token** (token **utente**, non "page").
4. Spunta i permessi:
   * `leads_retrieval`
   * `pages_show_list`
   * `pages_read_engagement`
   * `ads_management`
5. Copia il token (dura poche ore: ora lo rendiamo long-lived).

### Renderlo long-lived (≈60 giorni)

Sempre nell'Explorer, cambia la richiesta in:

```
GET /oauth/access_token?grant_type=fb_exchange_token&client_id={APP_ID}&client_secret={APP_SECRET}&fb_exchange_token={TOKEN_BREVE}
```

* `{APP_ID}` e `{APP_SECRET}`: in developers.facebook.com → **Impostazioni → Base**.
* `{TOKEN_BREVE}`: il token appena copiato.

La risposta contiene un token più lungo: **quello** va in `config.json`.

> Nota: i token-pagina che lo script ricava da `/me/accounts` a partire da questo token utente long-lived non scadono finché non cambi password o permessi. Quando in futuro avrai un System User, potrai sostituirlo con un token permanente senza toccare il resto.

---

## 4. Provare lo script

Su un PC con Python:

```bash
python main.py
```

Vedrai prima l'elenco delle pagine accessibili, poi i moduli trovati per pagina, e infine il riepilogo:

```
Nuovi: 12 | Inviati: 11 | Saltati (no contatto): 1 | Errori: 0
```

---

## 5. Creare l'eseguibile per l'operatore (`.exe`)

Sul PC Windows, una volta sola:

```bash
pip install pyinstaller
pyinstaller --onefile --name MetaEasyCall main.py
```

Poi:

1. Copia `dist/MetaEasyCall.exe` in una cartella dedicata.
2. **Metti `config.json` nella stessa cartella** dell'`.exe`.
3. `state.json` e `log.txt` si creano lì in automatico.

### Avvio automatico all'accensione (opzionale)

`Win + R` → `shell:startup` → Invio: crea lì un collegamento a `MetaEasyCall.exe`.

---

## 6. Deduplica

Ogni lead Meta ha un `id` univoco. Dopo l'invio riuscito finisce in `state.json` e non verrà più rispedito, anche lanciando il programma più volte al giorno. **Non cancellare `state.json`** o rischi doppioni su EasyCall.

---

## 7. Errori comuni (in `log.txt`)


| Messaggio                              | Causa                                    | Soluzione                                     |
| -------------------------------------- | ---------------------------------------- | --------------------------------------------- |
| `nessuna pagina accessibile`           | Token errato/scaduto o permessi mancanti | Rigenera il token (sez. 3)                    |
| `pagina '...' non accessibile`         | Il token non amministra quella pagina    | Verifica di essere Admin della pagina         |
| `401 token EasyCall non valido`        | Token EasyCall errato                    | Controlla`easycall.token`                     |
| `400 payload non valido`               | Campo non accettato da EasyCall          | Verifica con Easy4Cloud i campi attesi        |
| `SKIP lead ... manca email e telefono` | Lead senza contatti                      | Normale: EasyCall richiede almeno uno dei due |

---

## 8. Nota privacy (GDPR)

I lead sono dati personali: assicurati che le form raccolgano il consenso e che il trattamento su EasyCall sia coperto da informativa. Si può estendere lo script per mappare anche il campo consenso (`Optin`) se servirà.

Pipeline leggera che scarica i lead dalle form di **Meta Lead Ads**, estrae
`nome, cognome, email, telefono, località`, li instrada alla campagna
**EasyCall** giusta in base alla provincia e li invia via API.

Niente database, niente librerie esterne: solo Python standard. Lo stato
(per non duplicare i lead) è un file `state.json`.

---

## 1. File del progetto


| File          | A cosa serve                                                  |
| ------------- | ------------------------------------------------------------- |
| `main.py`     | Lo script. Non va modificato per l'uso normale.               |
| `config.json` | **Qui inserisci i tuoi dati** (token, form, campagne).        |
| `state.json`  | Creato in automatico. Memorizza gli ID dei lead già inviati. |
| `log.txt`     | Creato in automatico. Storico delle esecuzioni.               |

---

## 2. Cosa devi inserire in `config.json`

Apri `config.json` con un editor di testo (Blocco note va benissimo) e
compila **quattro cose**:

### a) Token Meta — `meta.access_token`

Il token "System User" long-lived (vedi sezione 3 per crearlo).

### b) Gli ID delle 3 form — `meta.form_ids`

Vedi sezione 4 per trovarli.

### c) Token EasyCall — `easycall.token`

Te lo fornisce Easy4Cloud dal pannello EasyCall (è la API key).
Controlla anche `easycall.url`: nella documentazione è l'ambiente di **test**
(`test.web3.easycallcloud.com`). Per andare in produzione fatti dare da
Easy4Cloud l'URL definitivo e sostituiscilo.

### d) Le campagne per provincia — `routing.map`

Associa ogni provincia (e la sua sigla) al nome/ID campagna EasyCall:

```json
"routing": {
  "default_campaign": "CAMPAGNA_DEFAULT",
  "map": {
    "firenze": "CAMP_FIRENZE", "fi": "CAMP_FIRENZE",
    "pisa": "CAMP_PISA",       "pi": "CAMP_PISA"
  }
}
```

- Le **chiavi** sono scritte tutte minuscole; lo script confronta in modo
  case-insensitive e anche per contenuto (es. `Firenze (FI)` trova `firenze`).
- `default_campaign` è la campagna usata quando la località non corrisponde a
  nessuna provincia in elenco (è la regola "la più vicina" / fallback).

> Il valore di `CAMP_*` deve essere **esattamente** il nome della campagna
> come configurata su EasyCall (campo `Campaign` della loro API).

---

## 3. Creare il token Meta (System User)

Serve un token che **non scada** e non sia legato a una persona. Si crea così:

1. Vai su **business.facebook.com** → **Impostazioni azienda** (Business Settings).
2. **Utenti → Utenti di sistema** → crea un nuovo *System User* (ruolo Admin).
3. **Aggiungi risorse** → assegna al System User le **Pagine** delle 3 form e
   l'**account pubblicitario**.
4. **Genera nuovo token**, seleziona la tua app, e spunta questi permessi:
   - `leads_retrieval`
   - `ads_management`
   - `pages_show_list`
   - `pages_read_engagement`
5. Copia il token e incollalo in `config.json` → `meta.access_token`.

> I token di System User sono long-lived: è esattamente ciò che evita che lo
> script smetta di funzionare quando scade un token personale.

---

## 4. Trovare gli ID delle form

Modo più rapido: **Graph API Explorer**
(developers.facebook.com/tools/explorer):

1. Seleziona la tua app e il token.
2. Query: `GET /{PAGE_ID}/leadgen_forms`
3. Nel risultato copia il campo `id` di ciascuna form e mettili in
   `config.json` → `meta.form_ids`.

In alternativa li trovi in **Meta Business Suite → Strumenti per i lead**.

---

## 5. Provare lo script (in fase di setup)

Su un PC con Python installato, nella cartella del progetto:

```bash
python main.py
```

Alla fine vedrai un riepilogo tipo:

```
Nuovi: 12 | Inviati: 11 | Saltati (no contatto): 1 | Errori: 0
```

Per un test "a vuoto" che non duplichi i lead veri: il primo giro li invia,
i successivi li riconoscono come già spediti (grazie a `state.json`).

---

## 6. Creare l'eseguibile per l'operatore (`.exe`)

Sul PC Windows, una volta sola:

```bash
pip install pyinstaller
pyinstaller --onefile --name MetaEasyCall main.py
```

Troverai `MetaEasyCall.exe` nella cartella `dist`. Poi:

1. Copia `MetaEasyCall.exe` in una cartella dedicata sul PC dell'operatore.
2. **Metti `config.json` nella stessa cartella** dell'`.exe` (lo script lo
   legge da lì; lo puoi modificare senza ricompilare).
3. `state.json` e `log.txt` verranno creati automaticamente accanto all'`.exe`.

### Avvio automatico all'accensione del PC (opzionale)

Premi `Win + R`, digita `shell:startup`, premi Invio: si apre la cartella
*Esecuzione automatica*. Crea lì un collegamento a `MetaEasyCall.exe`.
Ad ogni avvio del PC il programma partirà, importerà i nuovi lead e si fermerà
sul messaggio "Premi INVIO per chiudere".

L'operatore può comunque avviarlo a mano in qualsiasi momento con doppio click.

---

## 7. Come funziona la deduplica

Ogni lead Meta ha un `id` univoco. Dopo un invio riuscito lo script lo salva in
`state.json`. Agli avvii successivi i lead già presenti vengono saltati, quindi
**lo stesso lead non viene mai inviato due volte**, anche se il programma viene
lanciato più volte al giorno.

⚠️ Non cancellare `state.json`: equivale a "dimenticare" cosa è già stato
inviato e rischieresti dei doppioni su EasyCall.

---

## 8. Errori comuni (in `log.txt`)


| Messaggio                            | Causa                           | Soluzione                                              |
| ------------------------------------ | ------------------------------- | ------------------------------------------------------ |
| `401 token EasyCall non valido`      | Token EasyCall errato/scaduto   | Verifica`easycall.token`                               |
| `ERRORE Meta ... HTTP 190`           | Token Meta scaduto/permessi     | Rigenera il System User token (sez. 3)                 |
| `400 payload non valido`             | Campo non accettato da EasyCall | Controlla con Easy4Cloud i campi attesi della campagna |
| `SKIP lead ... manca email/telefono` | Lead senza contatti             | Normale: EasyCall richiede almeno uno dei due          |

---

## 9. Nota privacy (GDPR)

I lead sono dati personali. Assicurati che le form Meta raccolgano il consenso
e che il trattamento su EasyCall sia coperto da informativa. Se in futuro serve,
si può estendere lo script per mappare anche il campo consenso (`Optin`).
