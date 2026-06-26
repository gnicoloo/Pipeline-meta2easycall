#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Lead Ads -> EasyCall  (multi-pagina)
A ogni avvio:
  1. usa /me/accounts per scoprire le Pagine e i loro token
  2. per ogni Pagina configurata scarica i moduli e i lead
  3. normalizza, instrada (per localita' o campagna fissa) e invia a EasyCall
  4. tiene uno stato locale per non duplicare

Usa SOLO la standard library di Python (nessuna dipendenza).
"""

import os
import sys
import re
import csv
import json
import time
import datetime
import urllib.request
import urllib.parse
import urllib.error

# --- Percorsi: funziona sia come .py sia come .exe (PyInstaller) -----------
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATE_PATH = os.path.join(BASE_DIR, "state.json")
LOG_PATH = os.path.join(BASE_DIR, "log.txt")
HISTORY_PATH = os.path.join(BASE_DIR, "leads_history.csv")       # export EasyCall (legacy)
META_HISTORY_PATH = os.path.join(BASE_DIR, "meta_leads.csv")      # lead importati da Meta (non sovrascrivere!)
DASHBOARD_DATA_PATH = os.path.join(BASE_DIR, "dashboard_data.js")
HISTORY_HEADER = [
    "Ragione sociale", "Partita IVA", "Cognome", "Nome",
    "Codice fiscale", "Codice fiscale giuridico",
    "Telefono fisso", "Telefono mobile", "Altro Telefono", "Numero Fax",
    "Email", "Provenienza", "Personalizzato 1", "Personalizzato 2", "Altro",
    "Strada", "Civico", "Comune", "CAP", "Provincia",
    "Campagna", "Lista",
    "Esito chiamata", "Esito Archiviazione", "Data Archiviazione", "Note", "Ultimo Operatore",
]


def log(msg):
    line = "[{}] {}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# --- Config e stato --------------------------------------------------------
def load_config():
    if not os.path.exists(CONFIG_PATH):
        log("ERRORE: config.json non trovato accanto al programma ({})".format(CONFIG_PATH))
        sys.exit(1)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state():
    if not os.path.exists(STATE_PATH):
        return {"sent_ids": []}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("sent_ids", [])
        return data
    except Exception:
        return {"sent_ids": []}


def save_state(state):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


def load_meta_history_ids():
    """Carica i Meta lead ID già presenti in meta_leads.csv (evita doppioni nel recovery)."""
    ids = set()
    if not os.path.exists(META_HISTORY_PATH):
        return ids
    try:
        with open(META_HISTORY_PATH, "r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                lead_id = (row.get("Personalizzato 1") or "").strip()
                if lead_id:
                    ids.add(lead_id)
    except Exception:
        pass
    return ids


# --- Helper HTTP GET (JSON) ------------------------------------------------
def http_get_json(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --- META: scopri le pagine e i loro token (/me/accounts) ------------------
def meta_get_pages(user_token, api_version):
    params = {"fields": "id,name,access_token", "access_token": user_token, "limit": "100"}
    url = "https://graph.facebook.com/{}/me/accounts?{}".format(api_version, urllib.parse.urlencode(params))
    pages = {}
    while url:
        try:
            payload = http_get_json(url)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log("ERRORE /me/accounts: HTTP {} - {}".format(e.code, body[:400]))
            break
        except Exception as e:
            log("ERRORE /me/accounts: {}".format(e))
            break
        for p in payload.get("data", []):
            pages[str(p.get("id"))] = {"name": p.get("name", ""), "token": p.get("access_token", "")}
        url = payload.get("paging", {}).get("next")
    return pages


# --- META: elenco moduli (form) di una pagina ------------------------------
def meta_get_forms(page_id, page_token, api_version):
    params = {"fields": "id,name", "access_token": page_token, "limit": "100"}
    url = "https://graph.facebook.com/{}/{}/leadgen_forms?{}".format(api_version, page_id, urllib.parse.urlencode(params))
    forms = []
    while url:
        try:
            payload = http_get_json(url)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log("ERRORE moduli pagina {}: HTTP {} - {}".format(page_id, e.code, body[:300]))
            break
        except Exception as e:
            log("ERRORE moduli pagina {}: {}".format(page_id, e))
            break
        forms.extend(payload.get("data", []))
        url = payload.get("paging", {}).get("next")
    return forms


# --- META: scarica i lead di un modulo -------------------------------------
def meta_fetch_leads(form_id, token, api_version, lookback_days):
    since_unix = int(time.time()) - lookback_days * 86400
    params = {
        "fields": "id,created_time,field_data",
        "access_token": token,
        "limit": "100",
        "filtering": json.dumps([{"field": "time_created", "operator": "GREATER_THAN", "value": since_unix}]),
    }
    url = "https://graph.facebook.com/{}/{}/leads?{}".format(api_version, form_id, urllib.parse.urlencode(params))
    leads = []
    while url:
        try:
            payload = http_get_json(url)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log("ERRORE lead modulo {}: HTTP {} - {}".format(form_id, e.code, body[:300]))
            break
        except Exception as e:
            log("ERRORE lead modulo {}: {}".format(form_id, e))
            break
        leads.extend(payload.get("data", []))
        url = payload.get("paging", {}).get("next")
    return leads


# --- Normalizzazione -------------------------------------------------------
def fields_to_dict(lead):
    out = {}
    for f in lead.get("field_data", []):
        name = (f.get("name") or "").strip().lower()
        values = f.get("values") or []
        if values and isinstance(values[0], str):
            out[name] = values[0].strip()
        elif values:
            out[name] = values[0]
        else:
            out[name] = ""
    return out


def extract_name(fields):
    fn = (fields.get("first_name") or "").strip()
    ln = (fields.get("last_name") or "").strip()
    if fn or ln:
        return fn, ln
    full = (fields.get("full_name") or fields.get("name") or fields.get("nome") or "").strip()
    if not full:
        return "", ""
    parts = full.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def extract_locality(fields, candidate_names):
    for key in candidate_names:
        val = (fields.get(key.strip().lower()) or "").strip()
        if val:
            return val
    return ""


def normalize_phone(raw):
    if not raw:
        return ""
    return "".join(ch for ch in raw.strip() if ch.isdigit() or ch == "+")


def normalize_lead(lead, locality_field_names):
    fields = fields_to_dict(lead)
    first, last = extract_name(fields)
    return {
        "external_id": str(lead.get("id", "")),
        "first_name": first,
        "last_name": last,
        "email": (fields.get("email") or "").strip().lower(),
        "phone": normalize_phone(fields.get("phone_number") or fields.get("phone")),
        "locality": extract_locality(fields, locality_field_names),
        "created_time": lead.get("created_time", ""),
    }


# --- Routing: localita' -> campagna EasyCall -------------------------------
def _norm(s):
    """minuscolo, accenti via, punteggiatura -> spazi singoli."""
    s = (s or "").lower()
    s = (s.replace("à", "a").replace("è", "e").replace("é", "e")
           .replace("ì", "i").replace("ò", "o").replace("ù", "u"))
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def route_campaign(locality, routing):
    """
    Risolve la campagna da una localita' (provincia, sigla o comune).
    Priorita':
      1) match esatto sull'intera stringa
      2) sigla provincia tra i token (es. 'Viareggio (LU)' -> lu) [piu' affidabile]
      3) nome composto conosciuto contenuto nella stringa
         (es. 'Massa Marittima ...' -> Grosseto, non 'massa')
      4) singola parola lunga (nome comune/provincia)
      5) default
    """
    default = routing.get("default_campaign", "")
    kw = routing.get("by_keyword", {})
    norm = _norm(locality)
    if not norm:
        return default
    tokens = norm.split()

    # 1) intera stringa
    if norm in kw:
        return kw[norm]
    # 2) sigla provincia (token di 2 lettere noto)
    for t in tokens:
        if len(t) == 2 and t in kw:
            return kw[t]
    # 3) nomi composti noti (chiavi con spazio), dal piu' lungo
    multi = sorted((k for k in kw if " " in k), key=len, reverse=True)
    for k in multi:
        if k in norm:
            return kw[k]
    # 4) parola singola lunga
    for t in tokens:
        if len(t) > 2 and t in kw:
            return kw[t]
    return default


# --- EasyCall --------------------------------------------------------------
def build_easycall_payload(lead, campaign, channel):
    payload = {}
    if lead["first_name"]:
        payload["FirstName"] = lead["first_name"]
    if lead["last_name"]:
        payload["LastName"] = lead["last_name"]
    if lead["email"]:
        payload["Email"] = lead["email"]
    if lead["phone"]:
        payload["Phone"] = lead["phone"]
    if lead["locality"]:
        payload["City"] = lead["locality"]
    if campaign:
        payload["Campaign"] = campaign
    if channel:
        payload["Channel"] = channel
    if lead["external_id"]:
        payload["ID"] = lead["external_id"]
    return payload


def easycall_send(payload, url, token):
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer " + token,
    }
    attempts = 0
    while attempts < 3:
        attempts += 1
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return True, resp.read().decode("utf-8", errors="replace").strip()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 401:
                return False, "401 token EasyCall non valido"
            if e.code == 403:
                return False, "403 operazione non permessa"
            if e.code == 400:
                return False, "400 payload non valido: " + body[:200]
            if e.code >= 500 and attempts < 3:
                time.sleep(2 * attempts)
                continue
            return False, "HTTP {}: {}".format(e.code, body[:200])
        except Exception as e:
            if attempts < 3:
                time.sleep(2 * attempts)
                continue
            return False, str(e)
    return False, "esauriti i tentativi"


# --- Storico + dati per la dashboard ---------------------------------------
def append_history(lead, page_name, campaign, import_date=None):
    """Aggiunge una riga a meta_leads.csv. import_date = data importazione (default: oggi)."""
    if import_date is None:
        import_date = datetime.date.today().isoformat()
    row = [
        "", "",                                              # Ragione sociale, Partita IVA
        lead.get("last_name", ""),                           # Cognome
        lead.get("first_name", ""),                          # Nome
        "", "",                                              # Codice fiscale, CF giuridico
        "", lead.get("phone", ""), "", "",                   # Telefono fisso, mobile, altro, fax
        lead.get("email", ""),                               # Email
        page_name,                                           # Provenienza (pagina Facebook)
        lead.get("external_id", ""),                         # Personalizzato 1 (Meta lead ID)
        (lead.get("created_time") or "")[:10],               # Personalizzato 2 (data creazione Meta)
        "",                                                  # Altro
        "", "",                                              # Strada, Civico
        lead.get("locality", ""), "", "",                    # Comune, CAP, Provincia
        campaign, "",                                        # Campagna, Lista
        "", "", import_date, "", "",                         # Esito chiam., Esito Arch., Data Arch., Note, Op.
    ]
    new_file = not os.path.exists(META_HISTORY_PATH)
    with open(META_HISTORY_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        if new_file:
            w.writerow(HISTORY_HEADER)
        w.writerow(row)


def _iso_date(raw):
    """Converte 'dd/mm/yyyy ...' o 'yyyy-mm-dd...' in 'yyyy-mm-dd'. Restituisce '' se non parsabile."""
    s = (raw or "").strip()[:10]
    if not s:
        return ""
    if s[2:3] == "/":          # formato italiano dd/mm/yyyy
        try:
            d, m, y = s.split("/")
            return "{}-{}-{}".format(y, m.zfill(2), d.zfill(2))
        except Exception:
            return ""
    return s                   # già ISO yyyy-mm-dd


def generate_dashboard_data():
    """Rigenera dashboard_data.js da meta_leads.csv (priorità) + leads_history.csv (legacy EasyCall)."""
    rows = []
    seen_phones = set()  # dedup per telefono: evita doppi conteggi

    # 1) meta_leads.csv: dati importati da Meta con data precisa di importazione
    if os.path.exists(META_HISTORY_PATH):
        with open(META_HISTORY_PATH, "r", newline="", encoding="utf-8") as f:
            for d in csv.DictReader(f):
                phone = (d.get("Telefono mobile") or "").strip()
                rows.append({
                    "date": _iso_date(d.get("Data Archiviazione")),
                    "page": d.get("Provenienza", ""),
                    "campaign": d.get("Campagna", ""),
                    "locality": d.get("Comune", ""),
                    "has_email": bool((d.get("Email") or "").strip()),
                    "has_phone": bool(phone),
                })
                if phone:
                    seen_phones.add(phone)

    # 2) leads_history.csv: storico export EasyCall (legacy), salta telefoni già contati
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", newline="", encoding="utf-8") as f:
            for d in csv.DictReader(f):
                phone = (d.get("Telefono mobile") or "").strip()
                if phone and phone in seen_phones:
                    continue
                rows.append({
                    "date": _iso_date(d.get("Data Archiviazione")),
                    "page": d.get("Provenienza", ""),
                    "campaign": d.get("Campagna", ""),
                    "locality": d.get("Comune", ""),
                    "has_email": bool((d.get("Email") or "").strip()),
                    "has_phone": bool(phone),
                })
                if phone:
                    seen_phones.add(phone)

    payload = {"generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "leads": rows}
    with open(DASHBOARD_DATA_PATH, "w", encoding="utf-8") as f:
        f.write("window.DASHBOARD = " + json.dumps(payload, ensure_ascii=False) + ";\n")


# --- MAIN ------------------------------------------------------------------
def main():
    log("=== Avvio import Meta -> EasyCall ===")
    cfg = load_config()
    state = load_state()
    sent_ids = set(state.get("sent_ids", []))
    meta_history_ids = load_meta_history_ids()

    meta_cfg = cfg["meta"]
    ec_cfg = cfg["easycall"]
    routing = cfg.get("routing", {})
    locality_fields = cfg.get("locality", {}).get("field_names", ["city", "citta", "provincia"])

    user_token = meta_cfg["access_token"]
    api_version = meta_cfg.get("api_version", "v25.0")
    lookback_days = int(meta_cfg.get("lookback_days", 7))

    tot_new = tot_sent = tot_skipped = tot_err = tot_recovered = 0

    # 1) scopri pagine + token
    log("Recupero le pagine accessibili (/me/accounts)...")
    pages_meta = meta_get_pages(user_token, api_version)
    if not pages_meta:
        log("ERRORE: nessuna pagina accessibile col token fornito. Controlla token e permessi.")
        _pausa()
        return
    log("Pagine accessibili: " + ", ".join("{} ({})".format(v["name"], k) for k, v in pages_meta.items()))

    # 2) cicla le pagine configurate
    for page_cfg in meta_cfg.get("pages", []):
        pid = str(page_cfg["id"])
        pname = page_cfg.get("name", pid)
        if pid not in pages_meta:
            log("ATTENZIONE: pagina '{}' ({}) non accessibile col token. Salto.".format(pname, pid))
            continue
        page_token = pages_meta[pid]["token"]
        mode = page_cfg.get("routing_mode", "locality")
        fixed_campaign = page_cfg.get("fixed_campaign", "")

        forms = meta_get_forms(pid, page_token, api_version)
        log("Pagina '{}': {} moduli trovati".format(pname, len(forms)))

        for form in forms:
            form_id = str(form.get("id"))
            raw_leads = meta_fetch_leads(form_id, page_token, api_version, lookback_days)

            for raw in raw_leads:
                lead = normalize_lead(raw, locality_fields)
                lead_id = lead["external_id"]
                if not lead_id:
                    continue

                # Recovery: già inviato ma non ancora in meta_leads.csv (es. dopo un merge manuale)
                if lead_id in sent_ids:
                    if lead_id not in meta_history_ids:
                        camp_r = fixed_campaign if mode == "fixed" else route_campaign(lead["locality"], routing)
                        created = (lead.get("created_time") or "")[:10]
                        append_history(lead, pname, camp_r, import_date=created)
                        meta_history_ids.add(lead_id)
                        tot_recovered += 1
                    continue

                tot_new += 1

                if not lead["email"] and not lead["phone"]:
                    log("  SKIP lead {} (manca email e telefono)".format(lead_id))
                    tot_skipped += 1
                    sent_ids.add(lead_id)
                    continue

                if mode == "fixed":
                    campaign = fixed_campaign
                else:
                    campaign = route_campaign(lead["locality"], routing)

                payload = build_easycall_payload(lead, campaign, ec_cfg.get("channel", "facebook"))
                ok, info = easycall_send(payload, ec_cfg["url"], ec_cfg["token"])
                if ok:
                    tot_sent += 1
                    sent_ids.add(lead_id)
                    meta_history_ids.add(lead_id)
                    save_state({"sent_ids": list(sent_ids)})
                    append_history(lead, pname, campaign)
                    log("  OK [{}] lead {} -> '{}' ({} {})".format(
                        pname, lead_id, campaign, lead["first_name"], lead["last_name"]))
                else:
                    tot_err += 1
                    log("  ERRORE invio lead {}: {}".format(lead_id, info))

    save_state({"sent_ids": list(sent_ids)})
    generate_dashboard_data()
    log("=== Riepilogo ===")
    log("Nuovi: {} | Inviati: {} | Recuperati in history: {} | Saltati (no contatto): {} | Errori: {}".format(
        tot_new, tot_sent, tot_recovered, tot_skipped, tot_err))
    log("=== Fine ===\n")
    _pausa()


def _pausa():
    try:
        input("Premi INVIO per chiudere...")
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        log("ERRORE FATALE: {}".format(e))
        _pausa()