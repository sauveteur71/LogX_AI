#!/usr/bin/env python3
"""
RadioContest AI - Serveur principal v3.1
Point d'entrée : démarrage du serveur HTTP et des tâches de fond.
Lance avec : python serveur.py
Puis ouvre  : http://localhost:8080/configuration.html

Le code est organisé en modules :
  utils.py                — réseau, géodésie locator, modes numériques
  contest_definitions.py  — base des concours (définitions, scoring, URLs règlements)
  storage.py              — log partagé multi-opérateur + persistance disque
  rules.py                — dates, mise à jour annuelle des règlements, concours externes WA7BNM
  scoring.py              — moteur de score (valeur QSO, classement stations)
  clusters.py             — sources de spots (clusters DX, propagation, lookups)
  prompts.py              — prompts système du copilote IA
  http_handler.py         — endpoints HTTP + orchestration du refresh
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

from utils import PORT
from storage import load_log_from_disk
from rules import load_rules_cache, load_external_contests, schedule_annual_check
from http_handler import Handler


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    load_log_from_disk()
    load_rules_cache()
    load_external_contests()

    threading.Thread(target=schedule_annual_check, daemon=True).start()

    import socket as _sock
    try:
        _s = _sock.socket(_sock.AF_INET, _sock.SOCK_DGRAM)
        _s.connect(('8.8.8.8', 80))
        local_ip = _s.getsockname()[0]
        _s.close()
    except Exception:
        local_ip = '127.0.0.1'

    print('=' * 60)
    print('  RadioContest AI v3.1 -- F6KQJ/P JN15XC')
    print('  Rallye des Points Hauts 2026')
    print('=' * 60)
    print(f'  -> http://localhost:{PORT}/logbook.html')
    print(f'  -> http://localhost:{PORT}/rallye-vhf-terrain.html')
    print(f'  -> http://localhost:{PORT}/configuration.html')
    print(f'  -> http://localhost:{PORT}/calendrier.html')
    print('=' * 60)
    print(f'  Autres postes WiFi : http://{local_ip}:{PORT}/logbook.html')
    print()
    print('  Ctrl+C pour arreter')
    print()

    server = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('73 de F6KQJ/P !')
