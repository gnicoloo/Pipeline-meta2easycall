# Meta Ads API — Guida Completa per l'Indipendenza

*Calibrata sul tuo caso: 3 Pagine (Mobilmarket, Arredamento Italia, Maiora Interiors), arredamento/interior design, Toscana, pipeline verso EasyCall.*

---

## PARTE 1 — L'ARCHITETTURA: COME È FATTO IL SISTEMA META

### 1.1 La gerarchia degli oggetti

Tutto in Meta segue una struttura ad albero. Ogni livello è un "nodo" collegato al successivo:

```
Business Manager (la tua azienda)
  └── Ad Account (account pubblicitario)
        └── Campaign (campagna: es. "Lead Arezzo Giugno")
              └── Ad Set (gruppo di inserzioni: target, budget, posizionamento)
                    └── Ad (la singola inserzione: immagine, testo, CTA)
                          └── Lead Form (il modulo che raccoglie i dati)
```

Perché è importante capirlo: ogni livello ha il suo ID e le sue metriche. Quando chiedi dati all'API, specifichi **a quale livello** li vuoi. Esempio concreto dal tuo caso:

- **Livello Campaign**: "Quanto ho speso in totale sulla campagna Lead Arezzo?"
- **Livello Ad Set**: "Il target donne 35-55 performa meglio del target 25-34?"
- **Livello Ad**: "Il carosello con cucine moderne ha più click del video con bagni?"
- **Livello Lead Form**: "Quanti lead ha generato il modulo 'Preventivo Cucina'?"

### 1.2 Le tre API di Meta (e quale ti serve davvero)

**Marketing API (Core)** — gestisce gli oggetti (campagne, inserzioni). È quella che usi per creare, modificare, accendere/spegnere campagne via codice. Per ora non ti serve: lo fai da Ads Manager.

**Insights API** — è la miniera d'oro. Ti dà le **performance**: quanto hai speso, quanti click, quanti lead, il costo per lead, il ROAS. È un "edge" (estensione) della Marketing API. Endpoint:

```
GET /act_{AD_ACCOUNT_ID}/insights?fields=spend,impressions,clicks,actions&level=campaign
```

**Lead Ads API** — quella che usi già nella pipeline. Scarica i dati dei lead (nome, email, telefono) dai moduli. È separata dalla Insights API: la Insights ti dice *quanti* lead, la Lead Ads ti dice *chi sono*.

**Ad Library API** — dati pubblici sulle inserzioni dei concorrenti. Utile per ricerca di mercato: cosa pubblicizzano Mondo Convenienza, IKEA, Poltronesofà nella tua zona? Che creatività usano? Non dà performance (niente click, niente costi), solo cosa stanno facendo.

### 1.3 Il token: cos'è davvero e perché scade

Un token è una **chiave temporanea** che dice a Meta "questo utente ha il permesso di accedere a questi dati". Non è una password statica.

Esistono tre tipi, in ordine di durata:

- **Short-lived** (2 ore): quello che ottieni dal Graph API Explorer. Utile per test, inutile per automazione.
- **Long-lived** (60 giorni): quello che usi nella pipeline. Lo ottieni "scambiando" lo short-lived con la chiamata `fb_exchange_token`.
- **System User** (permanente): il migliore per automazione. Non scade, non è legato a una persona. Lo crei dal Business Manager, ma hai bisogno che l'app sia registrata anche lì (il tuo prossimo step).

**Cosa succede quando scade?** Lo script smette di funzionare con errore "Error validating access token" (codice 190). Soluzione: rigeneri il token e lo incolli in `config.json`.

**Consiglio pratico**: segna in calendario "Rinnova token Meta" ogni 50 giorni. Oppure, quando vuoi, migra al System User e non ci pensi più.

### 1.4 I permessi: cosa significano

Ogni token ha dei "permessi" che determinano cosa può fare:

| Permesso | Cosa ti dà |
|----------|-----------|
| `leads_retrieval` | Leggere i dati dei lead (nome, email, telefono) |
| `pages_read_engagement` | Leggere le interazioni con la pagina |
| `pages_show_list` | Vedere l'elenco delle pagine che amministri |
| `ads_management` | Accedere alle campagne e ai dati pubblicitari |
| `ads_read` | Solo lettura dei dati pubblicitari (senza poter modificare) |
| `read_insights` | Leggere le metriche di performance |

Per la pipeline attuale ti bastano i primi quattro. Per le analisi avanzate (Parte 3) aggiungerai `ads_read` e `read_insights`.

### 1.5 Rate limit: il semaforo di Meta

Meta non ti lascia fare richieste infinite. Ha un sistema a "budget di tempo": ogni richiesta consuma CPU time e total time. Se superi la soglia, Meta ti blocca per qualche ora.

Nel tuo caso concreto (10-50 lead/giorno, 3 pagine): **non è un problema**. Lo script fa poche decine di richieste per run. I rate limit diventano un problema quando fai centinaia di richieste al minuto (es. agenzie con 50 account).

Regola pratica: se lo script ti dà errore 17 o 32 ("User request limit reached"), aspetta 15 minuti e riprova.

### 1.6 Paginazione: perché Meta non ti dà tutto insieme

Quando chiedi i lead di un modulo, Meta non ti dà 500 risultati in una botta. Te ne dà 25-100 per volta (una "pagina"), con un link `next` per la pagina successiva. Lo script che hai già gestisce questo automaticamente (cicla finché `next` esiste).

Perché lo fa Meta: per non sovraccaricare i server e per non far esplodere la memoria del tuo client.

### 1.7 Versioning: il ciclo trimestrale

Meta rilascia una nuova versione dell'API ogni 3 mesi (v24.0 → v25.0 → v26.0...). Ogni versione resta attiva per 2 anni, poi viene "deprecata" (smette di funzionare).

Il tuo script usa `v25.0`. Non devi aggiornarlo subito: hai ~2 anni. Ma quando vedrai errori tipo "API version expired", dovrai cambiare `api_version` in `config.json` (es. da `v25.0` a `v28.0`). È una riga, non un dramma.

---

## PARTE 2 — I DATI CHE HAI GIÀ (E COSA CI PUOI FARE)

### 2.1 Cosa contiene ogni lead che scarichi

Dalla pipeline attuale, per ogni lead hai:

| Campo | Esempio | Da dove viene |
|-------|---------|--------------|
| Nome e cognome | Nadia Frulli | Il modulo Meta |
| Email | nadia@email.com | Il modulo Meta |
| Telefono | +393331234567 | Il modulo Meta |
| Località | Arezzo / Firenze / Viareggio | Il modulo Meta |
| Pagina di provenienza | Mobilmarket / Arredamento Italia / Maiora | Il config.json |
| Campagna EasyCall assegnata | LEAD giornalieri Arezzo | Il routing |
| Data di creazione | 2026-06-26T10:00:00 | Meta |
| ID Meta del lead | 2262020034624629 | Meta |

### 2.2 Cosa NON hai (ma potresti avere)

Dalla **Insights API** (che non stai usando ancora) potresti estrarre, per ogni campagna:

| Metrica | Significato | Perché ti interessa |
|---------|------------|-------------------|
| **Spend** | Quanto hai speso | Budget consumato per campagna/giorno |
| **Impressions** | Quante volte l'inserzione è stata vista | Saturazione del pubblico |
| **Reach** | Quante persone uniche l'hanno vista | Ampiezza reale del target |
| **Clicks** | Click sul link/CTA | Interesse reale |
| **CPM** (Cost Per Mille) | Costo per 1000 visualizzazioni | Efficienza della distribuzione |
| **CPC** (Cost Per Click) | Costo per click | Efficienza del traffico |
| **CPL** (Cost Per Lead) | Costo per lead | LA metrica chiave per te |
| **CTR** (Click-Through Rate) | % di chi vede e clicca | Qualità della creatività |
| **Frequency** | Media di volte che ogni persona vede l'ad | Sopra 3-4 = fatica creativa |
| **Actions** | Azioni (lead generati, visualizzazioni form) | Volume di conversioni |

### 2.3 Le 5 analisi concrete che puoi fare OGGI (con i dati della pipeline)

**Analisi 1: Distribuzione geografica dei lead**

Prendi il log dello script e conta quanti lead finiscono in ogni campagna:

```
LEAD giornalieri Arezzo:   ~55 lead (≈50%)
LEAD giornalieri Firenze:  ~45 lead (≈40%)
LEAD giornalieri Figline:  ~5 lead  (≈5%)
LEAD giornalieri Maiora:   ~10 lead
```

Domanda strategica: "Se Figline riceve solo il 5% dei lead, sto spendendo budget lì per niente? O il target non è presente in quelle province?"

**Analisi 2: Volume per pagina**

Dal log vedi che Mobilmarket genera ~95 lead, Arredamento Italia ~7, Maiora ~10. Questo ti dice:
- Mobilmarket è il motore principale
- Arredamento Italia ha un volume bassissimo: i moduli sono attivi? Le campagne girano?
- Maiora è stabile

**Analisi 3: Qualità dei dati di contatto**

Conta quanti lead hanno email, quanti telefono, quanti entrambi, quanti nessuno (SKIP nel log). Se il 30% non ha il telefono, il dialer di EasyCall non potrà chiamarli: la form Meta deve rendere il telefono obbligatorio.

**Analisi 4: Lead duplicati cross-pagina**

Cerchi nella stessa email (o telefono) se la stessa persona ha compilato il modulo su Mobilmarket E su Arredamento Italia. Se sì, stai pagando due volte per lo stesso contatto: serve una deduplica cross-pagina su EasyCall.

**Analisi 5: Trend nel tempo**

Se salvi i log giornalieri, puoi tracciare:
- Lunedì = 15 lead, Martedì = 8, Mercoledì = 22...
- Vedi i pattern: il volume cala nel weekend? Ci sono giorni morti?
- Questo ti dice **quando** schedulare il budget più alto.

### 2.4 Il dato che ti manca: il feedback da EasyCall

La pipeline è unidirezionale: Meta → EasyCall. Non sai cosa succede dopo. Il dato più prezioso che puoi ottenere da EasyCall (manualmente o chiedendo a Easy4Cloud) è:

- **Quanti lead sono stati contattati?**
- **Quanti hanno risposto?**
- **Quanti hanno fissato un appuntamento?**
- **Quanti hanno comprato?**

Con questo chiudi il cerchio: sai non solo quanto costa un lead (CPL) ma quanto costa un **cliente** (CPA = Cost Per Acquisition). È la differenza tra ottimizzare alla cieca e ottimizzare con dati reali.

---

## PARTE 3 — ANALISI AVANZATE (IL PROSSIMO LIVELLO)

### 3.1 Collegare i dati di spesa ai lead (Insights + Lead Ads)

Oggi sai "ho 55 lead su Arezzo". Ma non sai "quanto ho speso per averli". Per saperlo devi incrociare due fonti:

```
INSIGHTS API (spesa per campagna)     LEAD ADS API (lead per località)
         │                                      │
         └──────────── JOIN ────────────────────┘
                        │
              CPL per provincia
     Arezzo: €500 spesi / 55 lead = €9.09/lead
     Firenze: €400 spesi / 45 lead = €8.89/lead
     Figline: €200 spesi / 5 lead = €40.00/lead ← PROBLEMA
```

Se il CPL di Figline è 4 volte quello di Arezzo, hai due opzioni: o il target lì non è buono (riduci budget), o la creatività non funziona per quel pubblico (cambia messaggio).

**Come farlo in pratica**: aggiungiamo allo script un secondo modulo che chiama la Insights API per ogni ad account e scarica `spend` per campagna. Lo incrociamo col conteggio dei lead per località. Te lo posso costruire quando vuoi.

### 3.2 Costo per Appuntamento e Costo per Vendita

Se EasyCall ti dà (anche manualmente) i dati di conversione:

```
Provincia    Lead    Contattati    Appuntamenti    Vendite    Spesa
Arezzo        55        48            12             4        €500
Firenze       45        40             8             3        €400
Figline        5         4             1             0        €200
```

Puoi calcolare:

- **Tasso di contatto**: Arezzo 87%, Firenze 89%, Figline 80%
- **Tasso di conversione lead→appuntamento**: Arezzo 22%, Firenze 18%, Figline 20%
- **Costo per appuntamento**: Arezzo €41, Firenze €50, Figline €200
- **Costo per vendita (CPA)**: Arezzo €125, Firenze €133, Figline ∞ (zero vendite!)

Questo ti dice: "Figline costa troppo e non converte. Sposto quel budget su Arezzo dove il CPA è il migliore." **Questa è la decisione strategica che i dati rendono ovvia.**

### 3.3 Le metriche della Insights API spiegate con esempi tuoi

**Frequency (frequenza)**: quante volte in media la stessa persona vede la tua inserzione.

Esempio: hai una campagna su Arezzo che mostra cucine moderne. Dopo 3 settimane la frequency è 5.2. Significa che ogni persona nel target ha visto l'inserzione 5 volte. Dopo la terza volta il cervello la ignora ("banner blindness"). Devi cambiare la creatività: nuove foto, nuovo testo, nuovo formato (passa da immagine a video o carosello).

**Reach vs Impressions**: reach = persone uniche, impressions = visualizzazioni totali.

Se reach = 10.000 e impressions = 50.000, la frequency è 5. Se reach = 10.000 e impressions = 12.000, la frequency è 1.2: stai raggiungendo persone nuove, non saturando le stesse.

**CTR (Click-Through Rate)**: percentuale di chi vede l'inserzione e ci clicca.

Per Lead Ads nell'arredamento, un CTR buono è 1-2%. Sotto lo 0.5%: la creatività non attira. Sopra il 3%: hai trovato un angolo creativo vincente, spingilo.

**CPM (Cost Per Mille)**: quanto paghi per 1000 visualizzazioni.

Un CPM alto (sopra €15-20 per il tuo settore) significa: il target è troppo piccolo o troppo conteso, oppure il periodo è competitivo (Black Friday, Natale). Un CPM basso (€3-5) significa: audience ampia e poca concorrenza, è il momento di spingere.

---

## PARTE 4 — STRATEGIA PERSONALIZZATA (COSA FARE CON TUTTO QUESTO)

### 4.1 Il framework "Measure → Decide → Act"

Non servono 700 metriche. Servono **5 numeri** che guardi ogni settimana:

| # | Metrica | Dove la trovi | Soglia d'allarme |
|---|---------|--------------|-----------------|
| 1 | **Lead totali / settimana** | Log della pipeline | Sotto 30: budget insufficiente o form rotte |
| 2 | **CPL per provincia** | Insights API + pipeline | Sopra €15: rivaluta target o creatività |
| 3 | **Frequency** | Ads Manager o Insights API | Sopra 3.5: cambia creatività |
| 4 | **Tasso contatto** (da EasyCall) | Report EasyCall | Sotto 70%: problema qualità lead o timing |
| 5 | **CPA** (costo per appuntamento) | Insights + EasyCall | Sopra €60: rivaluta l'intero funnel |

### 4.2 Strategia per le 3 pagine

**Mobilmarket** (il motore, 95 lead/settimana): qui il volume c'è. La priorità è **ottimizzare il costo**, non aumentare il volume. Azioni:
- Guarda il CPL per provincia: se Figline costa 4x, sposta budget
- Testa 2-3 creatività diverse ogni 2 settimane
- Monitora la frequency: quando supera 3.5, cambia creatività

**Arredamento Italia** (7 lead/settimana): il volume è troppo basso. Due ipotesi:
- Il budget è piccolo → aumentalo e misura se il CPL resta stabile
- I moduli non convertono → guarda il tasso di apertura form vs completamento (in Ads Manager: "Lead Form Opens" vs "Leads")
- Il target è troppo stretto → amplia (età, interessi, lookalike)

**Maiora Interiors** (10 lead/settimana, campagna fissa): qui il routing è semplice. Focus su:
- Qualità dei lead: quanti rispondono al telefono?
- Se Maiora è un brand premium, il CPL può essere più alto (€20-25) perché il ticket medio è più alto

### 4.3 Test A/B concreti da fare

**Test 1: Formato della creatività**
- Variante A: Carosello con 5 foto di cucine realizzate
- Variante B: Video di 15 secondi "prima e dopo" di una ristrutturazione
- Misuri: CTR e CPL dopo 500 impressioni ciascuno

**Test 2: Copy del modulo**
- Variante A: "Richiedi un preventivo gratuito"
- Variante B: "Scopri quanto costa la tua cucina ideale"
- Misuri: tasso di completamento del form (quanti aprono vs quanti inviano)

**Test 3: Target per età**
- Ad Set A: donne 30-45
- Ad Set B: donne 45-60
- Misuri: CPL e CPA (quale fascia genera lead che poi comprano)

### 4.4 Il calendario operativo (cosa fare e quando)

**Ogni giorno** (automatico): lo script gira e importa i lead in EasyCall. L'operatore vede il riepilogo.

**Ogni lunedì** (5 minuti): apri il log della settimana, conta i lead per campagna. Confronta con la settimana prima: il volume sale, scende, è stabile?

**Ogni 2 settimane** (15 minuti): apri Ads Manager, guarda frequency e CTR. Se frequency > 3.5, prepara nuove creatività. Se CTR < 0.5%, cambia angolo creativo.

**Ogni mese** (30 minuti): incrocia i dati Meta (spesa, lead) con i dati EasyCall (appuntamenti, vendite). Calcola il CPA per provincia. Decidi dove spostare il budget il mese dopo.

**Ogni 50 giorni**: rinnova il token Meta (finché non migri al System User permanente).

**Ogni 6 mesi**: controlla la versione API (`api_version` in config.json). Se Meta ha deprecato la tua, aggiorna.

---

## PARTE 5 — STRUMENTI E PROSSIMI PASSI

### 5.1 Graph API Explorer (il tuo laboratorio)

**URL**: developers.facebook.com/tools/explorer

Qui puoi testare qualsiasi richiesta API prima di metterla in uno script. Esempi pratici:

Vedere i lead di un modulo:
```
GET /{FORM_ID}/leads?fields=id,created_time,field_data
```

Vedere le metriche di una campagna (ultimi 7 giorni):
```
GET /act_{AD_ACCOUNT_ID}/insights?fields=campaign_name,spend,impressions,clicks,actions&level=campaign&date_preset=last_7d
```

Vedere i moduli di una pagina:
```
GET /{PAGE_ID}/leadgen_forms?fields=id,name,status
```

### 5.2 Il JSON spiegato: come leggere una risposta API

Quando fai una richiesta, Meta ti risponde in JSON. Esempio reale di un lead:

```json
{
  "data": [
    {
      "id": "2262020034624629",
      "created_time": "2026-06-20T10:00:00+0000",
      "field_data": [
        {
          "name": "full_name",
          "values": ["Nadia Frulli"]
        },
        {
          "name": "email",
          "values": ["nadia@email.com"]
        },
        {
          "name": "phone_number",
          "values": ["+393331234567"]
        },
        {
          "name": "city",
          "values": ["Arezzo"]
        }
      ]
    }
  ],
  "paging": {
    "cursors": {
      "before": "abc123",
      "after": "xyz789"
    },
    "next": "https://graph.facebook.com/v25.0/..."
  }
}
```

Come si legge:
- `data` è un array (lista) di lead
- Ogni lead ha un `id`, un `created_time` e un `field_data`
- `field_data` è un array di coppie nome-valore (i campi del modulo)
- `paging.next` è il link alla pagina successiva (se esiste, ci sono altri lead)

### 5.3 Glossario dei termini chiave

| Termine | Significato pratico |
|---------|-------------------|
| **API** | Un "contratto" che ti permette di parlare col server di Meta via codice, non via browser |
| **Endpoint** | L'indirizzo specifico a cui fai la richiesta (es. `/{form_id}/leads`) |
| **Graph API** | L'API principale di Meta: tutto passa da qui (lead, insights, pagine, post) |
| **Token** | La chiave temporanea che ti autentica |
| **OAuth 2.0** | Il protocollo di sicurezza che Meta usa per darti il token |
| **JSON** | Il formato dei dati (testo strutturato con parentesi graffe e quadre) |
| **ETL** | Extract-Transform-Load: il pattern della tua pipeline (estrai da Meta, trasformi, carichi su EasyCall) |
| **Webhook** | Meta ti "chiama" quando arriva un lead (push), invece di aspettare che tu chieda (pull/polling) |
| **Polling** | Tu chiedi periodicamente "ci sono lead nuovi?" (pull). È quello che fa il tuo script |
| **Rate limit** | Il numero massimo di richieste che puoi fare in un periodo |
| **Paginazione** | Meta divide i risultati in "pagine" da 25-100 elementi |
| **ROAS** | Return On Ad Spend: per ogni €1 speso, quanti € di vendite generi |
| **CPL** | Cost Per Lead: quanto costa ogni contatto acquisito |
| **CPA** | Cost Per Acquisition: quanto costa ogni cliente acquisito |
| **CTR** | Click-Through Rate: % di chi vede e clicca |
| **CPM** | Cost Per Mille: costo per 1000 visualizzazioni |
| **Frequency** | Quante volte in media la stessa persona vede l'inserzione |
| **Pixel** | Un codice che metti sul sito per tracciare cosa fanno gli utenti dopo il click |
| **Lookalike** | Pubblico "simile" ai tuoi clienti, creato da Meta sulla base dei dati del Pixel |
| **Attribution window** | La finestra temporale entro cui Meta attribuisce una conversione all'inserzione |
| **Deprecation** | Quando Meta "spegne" una vecchia versione dell'API |

### 5.4 Risorse per approfondire

- **Meta for Developers — Marketing API**: developers.facebook.com/docs/marketing-apis
- **Graph API Explorer**: developers.facebook.com/tools/explorer (testa le richieste live)
- **Meta Business Help Center**: business.facebook.com/help (guide su Ads Manager)
- **Lead Ads API docs**: developers.facebook.com/docs/marketing-api/guides/lead-ads
- **Insights API docs**: developers.facebook.com/docs/marketing-api/insights
- **Documentazione EasyCall**: il PDF che hai già (v1.1, dec 2019)

---

## RIEPILOGO: LE 3 COSE DA RICORDARE

**1. Hai già il pezzo più difficile.** La pipeline Meta → EasyCall funziona. La maggior parte delle aziende è ancora a "esporto CSV e lo mando per email". Tu hai un sistema automatico che gira con un doppio click.

**2. Il prossimo salto è collegare la spesa ai lead.** Senza sapere quanto costa ogni lead per provincia, ottimizzi alla cieca. Con la Insights API (che possiamo aggiungere allo script) hai il CPL in tempo reale.

**3. Il salto finale è chiudere il cerchio con EasyCall.** Lead → Contattato → Appuntamento → Vendita. Quando hai questo dato, sai esattamente dove mettere ogni euro di budget. Non ti serve un data warehouse: ti basta un foglio Excel aggiornato ogni mese con i numeri di EasyCall incrociati col conteggio dei lead.
