#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Meta Lead Ads -> EasyCall
Pipeline "one-shot": a ogni avvio scarica i lead nuovi dalle form Meta,
estrae nome/cognome/email/telefono/localita, instrada per provincia e
li invia a EasyCall via API. Tiene uno stato locale per non duplicare.

Usa SOLO la standard library di Python (nessuna dipendenza da installare).
"""

import os
import sys
import json
import time
import datetime
import urllib.request
import urllib.parse
import urllib.error

# ---------------------------------------------------------------------------
# Percorsi: funziona sia come script .py sia come .exe (PyInstaller).
# config.json / state.json / il log stanno SEMPRE accanto all'eseguibile,
# cosi' l'operatore puo' modificare il config senza ricompilare nulla.
# ---------------------------------------------------------------------------
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATE_PATH = os.path.join(BASE_DIR, "state.json")
LOG_PATH = os.path.join(BASE_DIR, "log.txt")


# ---------------------------------------------------------------------------
# Logging semplice: scrive a video e su log.txt
# ---------------------------------------------------------------------------
def log(msg):
    line = "[{}] {}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Config e stato
# ---------------------------------------------------------------------------
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
        if "sent_ids" not in data:
            data["sent_ids"] = []
        return data
    except Exception:
        return {"sent_ids": []}


def save_state(state):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


# ---------------------------------------------------------------------------
# META: scarica i lead di una form (con paginazione e filtro temporale)
# ---------------------------------------------------------------------------
def meta_fetch_leads(form_id, token, api_version, lookback_days):
    since_unix = int(time.time()) - lookback_days * 86400
    params = {
        "fields": "id,created_time,field_data",
        "access_token": token,
        "limit": "100",
        "filtering": json.dumps(
            [{"field": "time_created", "operator": "GREATER_THAN", "value": since_unix}]
        ),
    }
    url = "https://graph.facebook.com/{}/{}/leads?{}".format(
        api_version, form_id, urllib.parse.urlencode(params)
    )

    leads = []
    while url:
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            log("ERRORE Meta (form {}): HTTP {} - {}".format(form_id, e.code, body[:500]))
            break
        except Exception as e:
            log("ERRORE Meta (form {}): {}".format(form_id, e))
            break

        leads.extend(payload.get("data", []))
        # paginazione: Meta fornisce l'URL completo della pagina successiva
        url = payload.get("paging", {}).get("next")

    return leads


# ---------------------------------------------------------------------------
# NORMALIZZAZIONE del singolo lead Meta
# ---------------------------------------------------------------------------
def fields_to_dict(lead):
    """field_data: [{name, values:[...]}] -> {name: primo_valore}"""
    out = {}
    for f in lead.get("field_data", []):
        name = (f.get("name") or "").strip().lower()
        values = f.get("values") or []
        out[name] = values[0].strip() if values and isinstance(values[0], str) else (values[0] if values else "")
    return out


def extract_name(fields):
    """Gestisce sia first_name/last_name separati sia full_name unico."""
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
    raw = raw.strip()
    keep = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    return keep


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


# ---------------------------------------------------------------------------
# ROUTING: localita -> campagna EasyCall
# ---------------------------------------------------------------------------
def route_campaign(locality, routing):
    default = routing.get("default_campaign", "")
    mapping = routing.get("map", {})
    if not locality:
        return default
    loc = locality.strip().lower()
    # 1) match esatto
    if loc in mapping:
        return mapping[loc]
    # 2) match per contenuto (es. "Firenze (FI)" contiene "firenze")
    for key, camp in mapping.items():
        if key in loc:
            return camp
    # 3) fallback: campagna di default ("la piu' vicina")
    return default


# ---------------------------------------------------------------------------
# EASYCALL: invio del lead
# ---------------------------------------------------------------------------
def build_easycall_payload(lead, campaign, channel):
    """Costruisce il body JSON includendo SOLO i campi valorizzati."""
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
    """Ritorna (ok: bool, info: str). Ritenta su errori 500/rete."""
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
                body = resp.read().decode("utf-8", errors="replace")
                return True, body.strip()
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


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    log("=== Avvio import Meta -> EasyCall ===")
    cfg = load_config()
    state = load_state()
    sent_ids = set(state.get("sent_ids", []))

    meta_cfg = cfg["meta"]
    ec_cfg = cfg["easycall"]
    routing = cfg.get("routing", {})
    locality_fields = cfg.get("locality", {}).get("field_names", ["city", "citta", "provincia"])

    token = meta_cfg["access_token"]
    api_version = meta_cfg.get("api_version", "v25.0")
    lookback_days = int(meta_cfg.get("lookback_days", 7))

    total_new = 0
    total_sent = 0
    total_skipped = 0
    total_errors = 0

    for form_id in meta_cfg["form_ids"]:
        log("Form {}: scarico i lead...".format(form_id))
        raw_leads = meta_fetch_leads(form_id, token, api_version, lookback_days)
        log("Form {}: {} lead ricevuti da Meta".format(form_id, len(raw_leads)))

        for raw in raw_leads:
            lead = normalize_lead(raw, locality_fields)
            lead_id = lead["external_id"]

            if not lead_id or lead_id in sent_ids:
                continue  # gia' inviato in un run precedente -> salta
            total_new += 1

            # requisito EasyCall: almeno email O telefono
            if not lead["email"] and not lead["phone"]:
                log("  SKIP lead {} (manca sia email sia telefono)".format(lead_id))
                total_skipped += 1
                sent_ids.add(lead_id)  # marcalo come gestito per non riprovarlo all'infinito
                continue

            campaign = route_campaign(lead["locality"], routing)
            payload = build_easycall_payload(lead, campaign, ec_cfg.get("channel", "facebook"))

            ok, info = easycall_send(payload, ec_cfg["url"], ec_cfg["token"])
            if ok:
                total_sent += 1
                sent_ids.add(lead_id)
                save_state({"sent_ids": list(sent_ids)})  # salvo subito: niente doppi invii se crasha
                log("  OK lead {} -> campagna '{}' ({} {})".format(
                    lead_id, campaign, lead["first_name"], lead["last_name"]))
            else:
                total_errors += 1
                log("  ERRORE invio lead {}: {}".format(lead_id, info))
                # NON lo marco come inviato: verra' ritentato al prossimo avvio

    save_state({"sent_ids": list(sent_ids)})

    log("=== Riepilogo ===")
    log("Nuovi: {} | Inviati: {} | Saltati (no contatto): {} | Errori: {}".format(
        total_new, total_sent, total_skipped, total_errors))
    log("=== Fine ===\n")

    # Pausa finale: cosi' la finestra non si chiude subito se avviata con doppio click
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
        try:
            input("Premi INVIO per chiudere...")
        except Exception:
            pass
