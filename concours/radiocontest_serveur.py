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

# Amorçage AVANT tout import applicatif : en mode figé (PyInstaller), bascule
# le répertoire de travail vers le dossier de données utilisateur (inscriptible)
# et y recopie les fichiers de référence embarqués. En dev : sans effet.
from radiocontest_bootstrap import bootstrap, open_browser, is_frozen
bootstrap()

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

    # Scoreboard en direct + sauvegarde cloud : deux threads de fond qui lisent
    # la config à chaud (activés/intervalles réglés dans CONFIG). Inactifs tant
    # que rien n'est configuré ; ne perturbent jamais le serveur en cas d'échec.
    def _scoreboard_loop():
        import time as _t
        import radiocontest_http as h
        import radiocontest_scoreboard as sb
        import radiocontest_storage as st
        while True:
            _t.sleep(60)
            try:
                with h.config_lock:
                    cfg = dict(h.current_config)
                s = sb.scoreboard_settings(cfg)
                if not s['enabled']:
                    continue
                last = sb.status(cfg).get('last', {}).get('last')
                # Respecte l'intervalle (le stamp est en 'YYYY-MM-DD HH:MM')
                import datetime as _dt
                due = True
                if last:
                    try:
                        age = (_dt.datetime.utcnow()
                               - _dt.datetime.strptime(last, '%Y-%m-%d %H:%M')).total_seconds()
                        due = age >= s['interval_min'] * 60 - 5
                    except Exception:
                        due = True
                if due:
                    with st.log_lock:
                        log_copy = list(st.shared_log)
                    r = sb.push(cfg, log_copy)
                    if r.get('ok'):
                        print(f"[SCOREBOARD] score {r['score']} / {r['qso']} QSO publie")
            except Exception as _e:
                print(f"[SCOREBOARD] {_e}")

    def _backup_loop():
        import time as _t
        import radiocontest_http as h
        import radiocontest_backup as bk
        import radiocontest_storage as st
        import datetime as _dt
        while True:
            _t.sleep(120)
            try:
                with h.config_lock:
                    cfg = dict(h.current_config)
                s = bk.backup_settings(cfg)
                if not s['enabled']:
                    continue
                last = bk.status(cfg).get('last', {}).get('last')
                due = True
                if last:
                    try:
                        age = (_dt.datetime.utcnow()
                               - _dt.datetime.strptime(last, '%Y-%m-%d %H:%M')).total_seconds()
                        due = age >= s['interval_min'] * 60 - 5
                    except Exception:
                        due = True
                if due:
                    with st.log_lock:
                        log_copy = list(st.shared_log)
                    r = bk.run_backup(cfg, log_copy)
                    if r.get('ok'):
                        print(f"[BACKUP] {len(r['files'])} fichiers -> {r['folder']}")
            except Exception as _e:
                print(f"[BACKUP] {_e}")

    def _cloudsync_loop():
        import time as _t
        import radiocontest_http as h
        import radiocontest_cloudsync as cs
        import radiocontest_storage as st
        import datetime as _dt
        while True:
            _t.sleep(60)
            try:
                with h.config_lock:
                    cfg = dict(h.current_config)
                s = cs.cloudsync_settings(cfg)
                if not s['enabled']:
                    continue
                last = cs.status(cfg).get('last', {}).get('last')
                due = True
                interval_min = int(cfg.get('cloudsync_interval', 3) or 3)
                if last:
                    try:
                        age = (_dt.datetime.utcnow()
                               - _dt.datetime.strptime(last, '%Y-%m-%d %H:%M')).total_seconds()
                        due = age >= interval_min * 60 - 5
                    except Exception:
                        due = True
                if due:
                    with st.log_lock:
                        log_copy = list(st.shared_log)
                    r = cs.sync_now(cfg, log_copy)
                    if r.get('ok') and (r.get('pulled') or r.get('pushed')):
                        print(f"[CLOUDSYNC] mode={r['mode']} pushed={r['pushed']} pulled={r['pulled']}")
            except Exception as _e:
                print(f"[CLOUDSYNC] {_e}")

    threading.Thread(target=_scoreboard_loop, daemon=True).start()
    threading.Thread(target=_backup_loop, daemon=True).start()
    threading.Thread(target=_cloudsync_loop, daemon=True).start()

    # Pont WSJT-X : écouteur UDP FT8/FT4 démarré si activé dans config.json
    # (ou plus tard à chaud dès qu'un /wsjtx/state le voit activé côté client).
    try:
        import radiocontest_wsjtx as wsjtx
        import radiocontest_http as http_mod
        w = wsjtx.wsjtx_settings(None)
        if w['enabled']:
            wsjtx.start_listener(
                get_cfg=lambda: dict(http_mod.current_config),
                add_qso=lambda q: http_mod.add_qso_to_log(q, force=False)[0],
                port=w['port'])
    except Exception as _e:
        print(f"[WSJTX] Demarrage differe: {_e}")

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

    # Application figée : ouvre le navigateur automatiquement.
    if is_frozen():
        open_browser(PORT)

    server = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('73 de F6KQJ/P !')
