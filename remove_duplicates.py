#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rimuove le righe duplicate da meta_leads.csv e leads_history.csv.

Un duplicato e' un gruppo di righe che condividono lo stesso lead, identificato
(in ordine di priorita') da:
  1. "Personalizzato 1" (ID lead Meta), se non vuoto
  2. "Telefono mobile", se non vuoto
  3. "Email", se non vuota
Le righe senza nessuno di questi tre campi non vengono mai unite ad altre
(non c'e' modo affidabile di sapere se sono davvero lo stesso lead).

Tra le righe di uno stesso gruppo viene tenuta quella piu' recente, cioe' con la
"Data Archiviazione" piu' alta; a parita' di data vince quella con piu' campi
compilati; a ulteriore parita' vince l'ultima incontrata nel file.

Uso:
  python remove_duplicates.py                 # deduplica meta_leads.csv e leads_history.csv
  python remove_duplicates.py --dry-run        # mostra solo il riepilogo, non scrive nulla
  python remove_duplicates.py altro_file.csv   # deduplica un file specifico

Prima di sovrascrivere ogni file viene creata una copia di backup "<file>.bak".
"""

import os
import sys
import csv
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FILES = ["meta_leads.csv", "leads_history.csv"]

KEY_FIELDS = ["Personalizzato 1", "Telefono mobile", "Email"]


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
    return s                   # gia' ISO yyyy-mm-dd


def row_key(row):
    for field in KEY_FIELDS:
        val = (row.get(field) or "").strip()
        if val:
            return (field, val)
    return None  # nessuna chiave affidabile: la riga resta sempre unica


def filled_count(row):
    return sum(1 for v in row.values() if (v or "").strip())


def pick_best(items):
    """items: lista di (indice_originale, row). Restituisce la riga da tenere."""
    def sort_key(item):
        idx, row = item
        return (_iso_date(row.get("Data Archiviazione")), filled_count(row), idx)
    return max(items, key=sort_key)


def dedupe_rows(rows):
    groups = {}
    order = []  # preserva l'ordine di prima apparizione di ciascuna chiave
    for idx, row in enumerate(rows):
        key = row_key(row)
        if key is None:
            key = ("__unique__", idx)
        if key not in groups:
            order.append(key)
        groups.setdefault(key, []).append((idx, row))

    kept = []
    removed = 0
    for key in order:
        items = groups[key]
        if len(items) == 1:
            kept.append(items[0])
        else:
            kept.append(pick_best(items))
            removed += len(items) - 1

    kept.sort(key=lambda item: item[0])
    return [row for _, row in kept], removed


def dedupe_file(path, dry_run=False):
    if not os.path.exists(path):
        print("SKIP: {} non trovato".format(path))
        return

    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            print("SKIP: {} vuoto".format(path))
            return
        dict_rows = [dict(zip(header, r)) for r in reader]

    total_before = len(dict_rows)
    deduped, removed = dedupe_rows(dict_rows)

    print("{}: {} righe -> {} righe ({} duplicati rimossi)".format(
        os.path.basename(path), total_before, len(deduped), removed))

    if dry_run or removed == 0:
        return

    backup_path = path + ".bak"
    shutil.copy2(path, backup_path)
    print("  backup creato: {}".format(os.path.basename(backup_path)))

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(header)
        for row in deduped:
            writer.writerow([row.get(col, "") for col in header])
    print("  {} aggiornato.".format(os.path.basename(path)))


def main():
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    files = [a for a in args if not a.startswith("--")]
    if not files:
        files = DEFAULT_FILES

    for name in files:
        path = name if os.path.isabs(name) else os.path.join(BASE_DIR, name)
        dedupe_file(path, dry_run=dry_run)


if __name__ == "__main__":
    main()
