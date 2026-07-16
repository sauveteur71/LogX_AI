# -*- coding: utf-8 -*-
"""Log partagé multi-opérateur : état en mémoire + persistance disque (shared_log.json)."""

import json
import os
import threading

# ─── LOG PARTAGÉ MULTI-OPÉRATEUR ─────────────────────────────────────────────
shared_log = []        # log en mémoire partagé entre tous les postes
log_lock = threading.Lock()

def save_log_to_disk():
    """Sauvegarde le log sur disque — thread-safe via log_lock"""
    try:
        with log_lock:
            data = list(shared_log)  # copie sous verrou
        with open('shared_log.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[LOG] Erreur sauvegarde : {e}")

def load_log_from_disk():
    """Charge le log depuis le disque au démarrage.

    Mutation EN PLACE (shared_log[:] = ...) et non réassignation : les autres
    modules importent shared_log par référence, une réassignation les laisserait
    pointer sur l'ancienne liste vide."""
    try:
        if os.path.exists('shared_log.json'):
            with open('shared_log.json', 'r', encoding='utf-8') as f:
                shared_log[:] = json.load(f)
            print(f"[LOG] {len(shared_log)} QSO chargés depuis shared_log.json")
    except Exception as e:
        print(f"[LOG] Impossible de charger le log : {e}")
