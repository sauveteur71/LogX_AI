# -*- coding: utf-8 -*-
"""Tests fonctionnels de l'endpoint GET /log/question (C1, incrément 1).

Vrai serveur HTTP (comme test_le_pilotage_par_bande..., test_revue_jour_
correctifs.py) -- pas un test de logx_carnet_questions.py en isolation
(déjà couvert par test_carnet_questions.py), mais du CÂBLAGE : jeton
requis, dispatch topic/texte, erreurs propres.

Isolation : `shared_log` est un état GLOBAL du module logx_http, partagé par
tous les fichiers de test dans le même process pytest (piège déjà rencontré
et documenté pour `deleted_qsos`, voir PASSATION.md/corbeille). On le
remplace via monkeypatch.setattr, jamais en le vidant/le remplissant en
place -- restauré automatiquement par pytest en fin de test, sans dépendre
d'un bloc finally écrit à la main."""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as h  # noqa: E402


def _get(base, path, token=True):
    hdr = {}
    if token:
        hdr['X-RC-Token'] = h.AUTH_TOKEN
    rq = urllib.request.Request(base + path, headers=hdr, method='GET')
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % port
    srv.shutdown()


def _seed(monkeypatch, qsos):
    monkeypatch.setattr(h, 'shared_log', list(qsos))


def test_sans_jeton_refuse(serveur):
    code, _ = _get(serveur, '/log/question?topic=total', token=False)
    assert code == 403


def test_topic_total_avec_carnet(serveur, monkeypatch):
    _seed(monkeypatch, [{'id': 1, 'call': 'F4ABC', 'band': '20m', 'mode': 'SSB',
                        'date': '20260901', 'time': '10:00'}])
    code, j = _get(serveur, '/log/question?topic=total')
    assert code == 200 and j['ok'] is True
    assert '1' in j['reponse']


def test_topic_deja_travaille_avec_indicatif(serveur, monkeypatch):
    _seed(monkeypatch, [{'id': 1, 'call': 'F4ABC', 'band': '20m', 'mode': 'SSB',
                        'date': '20260901', 'time': '10:00'}])
    code, j = _get(serveur, '/log/question?topic=deja_travaille&indicatif=F4ABC')
    assert code == 200 and j['ok'] is True
    assert 'F4ABC' in j['reponse']


def test_topic_inconnu_renvoie_erreur_propre_pas_500(serveur):
    code, j = _get(serveur, '/log/question?topic=ceci_n_existe_pas')
    assert code == 200          # erreur PROPRE en payload, pas un crash HTTP
    assert j['ok'] is False


def test_texte_libre_reconnu_route_vers_deja_travaille(serveur, monkeypatch):
    _seed(monkeypatch, [{'id': 1, 'call': 'W1AW', 'band': '40m', 'mode': 'CW',
                        'date': '20260902', 'time': '11:00'}])
    code, j = _get(serveur, '/log/question?texte=' +
                    'j%27ai%20deja%20travaille%20W1AW%20%3F')
    assert code == 200 and j['ok'] is True
    assert j['topic'] == 'deja_travaille'
    assert 'W1AW' in j['reponse']


def test_texte_libre_non_reconnu_repond_repli_explicite(serveur):
    code, j = _get(serveur, '/log/question?texte=' +
                    'combien%20de%20QSO%20en%2020m%20ce%20mois')
    assert code == 200
    assert j['ok'] is False
    assert 'pas encore comprise' in j['error'].lower()


def test_ni_topic_ni_texte_est_une_erreur_propre(serveur):
    code, j = _get(serveur, '/log/question')
    assert code == 200 and j['ok'] is False
