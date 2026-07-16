#!/usr/bin/env python3
"""
RadioContest AI - Serveur principal v3.1
Point d'entrée : démarrage du serveur HTTP et des tâches de fond.
Lance avec : python radiocontest_serveur.py
Puis ouvre  : http://localhost:8080/radiocontest_configuration.html

Le code est organisé en modules :
  radiocontest_utils.py                — réseau, géodésie locator, modes numériques
  radiocontest_definitions.py  — base des concours (définitions, scoring, URLs règlements)
  radiocontest_storage.py              — log partagé multi-opérateur + persistance disque
  radiocontest_rules.py                — dates, mise à jour annuelle des règlements, concours externes WA7BNM
  radiocontest_scoring.py              — moteur de score (valeur QSO, classement stations)
  radiocontest_clusters.py             — sources de spots (clusters DX, propagation, lookups)
  radiocontest_prompts.py              — prompts système du copilote IA
  radiocontest_http.py         — endpoints HTTP + orchestration du refresh
"""

import sys

# Console Windows en cp1252 : un simple print() contenant une flèche → ou un
# emoji lève UnicodeEncodeError et tue la requête en cours. Forcer l'UTF-8
# (errors='replace' garantit qu'aucun log ne pourra jamais crasher le serveur).
# Doit être fait AVANT d'importer les modules applicatifs (qui peuvent printer).
for _stream in (sys.stdout, sys.stderr):
    if _stream and hasattr(_stream, 'reconfigure'):
        try:
            _stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass

import http.server
import threading

from radiocontest_utils import PORT
from radiocontest_storage import load_log_from_disk, load_qtc_from_disk
from radiocontest_rules import load_rules_cache, load_external_contests, schedule_annual_check
from radiocontest_http import Handler


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    load_log_from_disk()
    load_qtc_from_disk()
    load_rules_cache()
    load_external_contests()

    threading.Thread(target=schedule_annual_check, daemon=True).start()

    # Base DXCC : rafraîchit cty.dat s'il a plus de 30 jours (AD1C publie
    # des mises à jour avant chaque gros concours). En fond : le serveur
    # démarre sans attendre le réseau, la base actuelle sert en attendant.
    from radiocontest_dxcc import update_cty_if_stale
    threading.Thread(target=update_cty_if_stale, daemon=True).start()

    import socket as _sock
    try:
        _s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
        _s.connect(('8.8.8.8', 80))
        local_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        local_ip = '127.0.0.1'

    print('=' * 60)
    print('  RadioContest AI -- logiciel de concours multi-tout')
    print('  (config du concours actif : page CONFIG)')
    print('=' * 60)
    print(f'  -> http://localhost:{PORT}/radiocontest_configuration.html')
    print(f'  -> http://localhost:{PORT}/radiocontest_logbook.html')
    print(f'  -> http://localhost:{PORT}/radiocontest_propagation.html')
    print(f'  -> http://localhost:{PORT}/radiocontest_calendrier.html')
    print(f'  -> http://localhost:{PORT}/radiocontest_mobile.html (telephone)')
    print('=' * 60)
    print(f'  Autres postes WiFi : http://{local_ip}:{PORT}/radiocontest_logbook.html')
    print()
    print('  Ctrl+C pour arreter')
    print()

    server = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('73 de F6KQJ/P !')
