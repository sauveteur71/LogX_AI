# -*- coding: utf-8 -*-
"""Coach PENDANT un concours : cibles = multiplicateurs DU CONCOURS, pas le carnet à vie.

Défaut F4GLD (24/10/2026, CQ WW SSB) : « l'IA me propose des mults basés sur
mon log général alors que ça doit être basé sur le log du concours ». Les
conseils « 🎯 NOUVEAU PAYS jamais travaillé » venaient de
logx_awards.spotted_new_ones (carnet À VIE), même concours en cours.
Harnais serveur réel, carnet et spots simulés :
  - UZ7C   (Ukraine)  : contacté DANS le concours  -> jamais proposé en concours ;
  - CT1END (Portugal) : contacté HORS concours seul -> mult du concours, proposé ;
  - 3D2USU (Fiji)     : jamais contacté             -> proposé dans les deux cas."""
import datetime
import http.server
import json
import os
import sys
import threading
import re
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod  # noqa: E402

from logx_utils import utcnow  # noqa: E402
AUJ = utcnow()
AN = AUJ.strftime('%Y')


def _spots():
    return {'HF': [
        {'dx': 'UZ7C', 'freq': '7150.0', 'spotter': 'F5XX', 'time': '0500Z', 'info': ''},
        {'dx': 'CT1END', 'freq': '7160.0', 'spotter': 'F5XX', 'time': '0500Z', 'info': ''},
        {'dx': '3D2USU', 'freq': '21220.0', 'spotter': 'F5XX', 'time': '0500Z', 'info': ''},
    ]}


def _qso(call, band, contest):
    q = {'id': call, 'call': call, 'band': band, 'mode': 'SSB', 'date': AUJ.strftime('%Y%m%d'),
         'time': '0400', 'rst_sent': '59', 'rst_rcvd': '59'}
    if contest:
        q['contest'] = contest
    return q


def _cfg(en_cours=True):
    debut = AUJ - datetime.timedelta(days=1 if en_cours else 30)
    fin = AUJ + datetime.timedelta(days=1) if en_cours else AUJ - datetime.timedelta(days=28)
    return {'contest': 'CQ_WW_SSB', 'usage_mode': 'contest', 'callsign': 'F4GLD',
            'callsign_contest': 'F4GLD', 'locator': 'JN15WD',
            'contest_start_date': debut.strftime('%Y-%m-%d'),
            'contest_end_date': fin.strftime('%Y-%m-%d'), 'contest_end_utc': '23:59'}


@pytest.fixture
def serveur(monkeypatch):
    monkeypatch.setattr(httpmod, '_spots_from_caches', _spots)
    monkeypatch.setattr(httpmod, '_warm_band_spots', lambda *a, **k: None)
    # Modifié SUR PLACE : logx_http, logx_storage et logx_scoring tiennent la
    # MÊME liste ; la remplacer laisserait le moteur lire l'ancienne.
    log = httpmod.shared_log
    sauve = list(log)
    log[:] = [_qso('UZ7C', '7', 'CQ_WW_SSB'), _qso('CT1END', '7', None)]
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield 'http://127.0.0.1:%d' % srv.server_address[1]
    finally:
        srv.shutdown(); srv.server_close(); t.join(timeout=5)
        log[:] = sauve


def _etat(base, monkeypatch, cfg):
    monkeypatch.setattr(httpmod, 'current_config', cfg)
    req = urllib.request.Request(base + '/coach/state?lang=fr&nudges=1',
                                 headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))


def test_en_concours_les_cibles_sont_les_mults_du_concours(serveur, monkeypatch):
    st = _etat(serveur, monkeypatch, _cfg(en_cours=True))
    assert st['clock']['status'] == 'en_cours'
    cibles = {c['call']: c for c in st.get('new_targets') or []}
    assert 'UZ7C' not in cibles                          # déjà fait DANS le concours
    assert 'CT1END' in cibles and cibles['CT1END']['type'] == 'mult'   # fait hors concours seulement
    assert '3D2USU' in cibles
    assert cibles['3D2USU']['label'].startswith('Fiji')   # nom du pays, pas le préfixe
    # POURQUOI c'est un mult, dit en clair (rapporté au log DU concours) :
    assert '(aucun QSO sur 21 MHz dans ce concours)' in cibles['3D2USU']['label']
    assert '(pas encore fait sur 7 MHz dans ce concours)' in cibles['CT1END']['label']
    textes = ' | '.join(h['text'] for h in st['hints'])
    assert 'NOUVEAU MULT du concours' in textes
    assert 'jamais travaillé' not in textes              # plus de cibles « à vie » en concours
    assert st.get('nudge') and 'mult du concours' in st['nudge']['text']


def test_hors_concours_les_cibles_restent_a_vie(serveur, monkeypatch):
    st = _etat(serveur, monkeypatch, _cfg(en_cours=False))
    assert st['clock']['status'] != 'en_cours'
    cibles = {c['call'] for c in st.get('new_targets') or []}
    assert 'CT1END' not in cibles                        # Portugal déjà fait à vie
    assert 'UZ7C' not in cibles
    assert '3D2USU' in cibles                            # Fiji jamais fait


def test_bandeau_carte_ne_recopie_plus_la_prose_de_l_agent():
    """« QSO TOTAL 2 · — pts » alors que le concours comptait 47 QSO : le
    bandeau recopiait un nombre trouvé dans un message de l'agent."""
    src = open('logx_carte.html', encoding='utf-8').read()
    f = src[src.index('function parseScores'):]
    f = f[:f.index('\n}\n')]
    assert re.search(r"if\(typeof _scoreServeur !== 'undefined' && _scoreServeur\)\{", f)
    bloc = f[f.index("&& _scoreServeur){"):]
    bloc = bloc[:bloc.index('return;')]
    assert 'scoreQSO' not in bloc and 'scoreTotal' not in bloc
    assert "_scoreServeur = true" in src
    assert re.search(r"setTimeout\(\(\)=>\{ fetchTerrainData\(\); \}, 1500\)", src)
