# -*- coding: utf-8 -*-
"""Tests HTTP de bout en bout pour GET /pota/export_adif — export de
l'activation POTA en cours, au format ET au nom de fichier attendus par
l'auto-uploader « My Log Uploads » de pota.app (pas d'upload automatique :
POTA n'a pas d'API publique documentée pour ça, voir logx_pota.py). Même
harnais que tests/test_pota_spot_http.py (vrai serveur sur port éphémère)."""
import http.server
import os
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod


@pytest.fixture
def server():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _get(base, path):
    req = urllib.request.Request(base + path, headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, dict(r.headers), r.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode('utf-8')


def test_sans_activation_en_cours_400(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config', {'callsign': 'F4GLD', 'contest': ''})
    status, _, body = _get(server, '/pota/export_adif')
    assert status == 400 and 'Aucun parc POTA' in body


def test_activation_non_pota_400(server, monkeypatch):
    """SOTA/IOTA/WWFF en cours mais pas POTA : ce bouton est spécifique à
    POTA (seul programme visé par ce chantier), la route refuse plutôt que
    d'exporter silencieusement une autre activation sous un nom POTA."""
    monkeypatch.setattr(httpmod, 'current_config',
                        {'callsign': 'F4GLD', 'contest': '',
                         'activation_program': 'SOTA', 'my_activation_ref': 'F/AB-001'})
    status, _, body = _get(server, '/pota/export_adif')
    assert status == 400 and 'Aucun parc POTA' in body


def test_activation_pota_sans_qso_400(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config',
                        {'callsign': 'F4GLD', 'contest': '',
                         'activation_program': 'POTA', 'my_activation_ref': 'FR-0123'})
    monkeypatch.setattr(httpmod, 'shared_log', [])
    status, _, body = _get(server, '/pota/export_adif')
    assert status == 400 and 'Aucun QSO' in body


def test_export_reussi_bon_nom_de_fichier_et_bon_contenu(server, monkeypatch):
    monkeypatch.setattr(httpmod, 'current_config',
                        {'callsign': 'F4GLD', 'contest': '',
                         'activation_program': 'POTA', 'my_activation_ref': 'FR-0123'})
    monkeypatch.setattr(httpmod, 'shared_log', [
        {'call': 'DL1AA', 'band': '14', 'mode': 'SSB', 'my_sig': 'POTA', 'my_sig_info': 'FR-0123',
         'date': '20260816', 'time': '1230'},
        {'call': 'G3XYZ', 'band': '14', 'mode': 'CW', 'my_sig': 'POTA', 'my_sig_info': 'FR-0123',
         'date': '20260816', 'time': '1245'},
        {'call': 'HB9ZZ', 'band': '7', 'mode': 'SSB', 'my_sig': 'POTA', 'my_sig_info': 'FR-9999',
         'date': '20260816', 'time': '1300'},  # autre activation : absent de l'export
    ])
    status, headers, body = _get(server, '/pota/export_adif')
    assert status == 200
    assert headers['Content-Disposition'] == 'attachment; filename="F4GLD@FR-0123-20260816.adi"'
    assert 'DL1AA' in body and 'G3XYZ' in body
    assert 'HB9ZZ' not in body
    assert '<my_sig:4>POTA' in body
    assert '<my_sig_info:7>FR-0123' in body


def test_callsign_contest_prioritaire_dans_le_nom_de_fichier(server, monkeypatch):
    """Cohérence avec le reste du serveur (callsign_contest partout en mode
    concours/activation portable, ex. suffixe /P) — même priorité que
    /log/export/adif et /pota/spot."""
    monkeypatch.setattr(httpmod, 'current_config',
                        {'callsign': 'F4GLD', 'callsign_contest': 'F4GLD/P', 'contest': '',
                         'activation_program': 'POTA', 'my_activation_ref': 'FR-0123'})
    monkeypatch.setattr(httpmod, 'shared_log', [
        {'call': 'DL1AA', 'band': '14', 'mode': 'SSB', 'my_sig_info': 'FR-0123', 'date': '20260816'},
    ])
    status, headers, _ = _get(server, '/pota/export_adif')
    assert status == 200
    assert headers['Content-Disposition'] == 'attachment; filename="F4GLDP@FR-0123-20260816.adi"'
