# -*- coding: utf-8 -*-
"""Log partagé multi-opérateur : état en mémoire + persistance disque (shared_log.json)."""

import json
import os
import threading

# ─── LOG PARTAGÉ MULTI-OPÉRATEUR ─────────────────────────────────────────────
shared_log = []        # log en mémoire partagé entre tous les postes
log_lock = threading.Lock()

# Verrou dédié à calldb.json : écrit depuis plusieurs threads
# (lookups HamQTH, imports, mises à jour navigateur).
calldb_lock = threading.Lock()


def save_json_atomic(path, data, lock=None, compact=False):
    """Écriture JSON ATOMIQUE : fichier temporaire dans le même dossier puis
    os.replace — un crash ou une coupure en pleine écriture ne peut plus
    laisser un fichier tronqué. Thread-safe si un lock est fourni."""
    import tempfile

    def _write():
        target_dir = os.path.dirname(os.path.abspath(path)) or '.'
        fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + '.',
                                   suffix='.tmp', dir=target_dir)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                if compact:
                    json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
                else:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise

    if lock is not None:
        with lock:
            _write()
    else:
        _write()


def save_log_to_disk():
    """Sauvegarde le log sur disque — thread-safe via log_lock, écriture atomique"""
    try:
        with log_lock:
            data = list(shared_log)  # copie sous verrou
        save_json_atomic('shared_log.json', data)
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
