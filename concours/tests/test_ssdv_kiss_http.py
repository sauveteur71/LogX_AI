# -*- coding: utf-8 -*-
"""Tests de l'endpoint GET /ssdv/kiss/state et de son inclusion dans
/hardware/state (supervision du lien Direwolf/KISS, demandé par F4GLD :
« exposer l'état de la connexion Direwolf via un endpoint HTTP léger »).

Même patron que /wsjtx/state (_wsjtx_state_dict) : démarrage à chaud
idempotent du client quand la config l'active, aucune I/O bloquante sur le
thread HTTP (le client tourne en thread de fond, cf. logx_ssdv_reception).
"""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as h                 # noqa: E402
import logx_ssdv_reception as rx      # noqa: E402


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=10) as r:
        return r.status, json.loads(r.read())


def _serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, 'http://127.0.0.1:%d' % port


def _reset_rx():
    rx.arreter_client_kiss(attendre=True)
    with rx._lock:
        rx._started = False
    with rx._status_lock:
        rx.status.update(connected=False, host=None, port=None, last_seen=None,
                          paquets_recus=0, trames_ignorees=0, derniere_erreur='')


def test_ssdv_kiss_state_desactive_par_defaut():
    srv, base = _serveur()
    _reset_rx()
    try:
        with h.config_lock:
            sauve = dict(h.current_config)
            h.current_config.pop('ssdv', None)
        code, j = _get(base, '/ssdv/kiss/state')
        assert code == 200
        assert j['enabled'] is False
        with rx._lock:
            assert rx._started is False   # rien ne démarre si désactivé
    finally:
        with h.config_lock:
            h.current_config.clear()
            h.current_config.update(sauve)
        srv.shutdown()
        _reset_rx()


def test_ssdv_kiss_state_active_demarre_le_client_et_expose_le_statut():
    srv, base = _serveur()
    _reset_rx()
    try:
        with h.config_lock:
            sauve = dict(h.current_config)
            h.current_config['ssdv'] = {'kiss_enabled': True, 'kiss_host': '127.0.0.1',
                                        'kiss_port': 1}   # port fermé exprès : pas de vrai Direwolf ici
        code, j = _get(base, '/ssdv/kiss/state')
        assert code == 200
        assert j['enabled'] is True
        assert 'connected' in j and 'paquets_recus' in j and 'trames_ignorees' in j
        with rx._lock:
            assert rx._started is True   # démarrage à chaud idempotent déclenché
    finally:
        with h.config_lock:
            h.current_config.clear()
            h.current_config.update(sauve)
        srv.shutdown()
        _reset_rx()


def test_hardware_state_inclut_ssdv_kiss():
    srv, base = _serveur()
    _reset_rx()
    try:
        with h.config_lock:
            sauve = dict(h.current_config)
            h.current_config.pop('ssdv', None)
        code, j = _get(base, '/hardware/state')
        assert code == 200
        assert 'ssdv_kiss' in j
        assert j['ssdv_kiss']['enabled'] is False
    finally:
        with h.config_lock:
            h.current_config.clear()
            h.current_config.update(sauve)
        srv.shutdown()
        _reset_rx()
