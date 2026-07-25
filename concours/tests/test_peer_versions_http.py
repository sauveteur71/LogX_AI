# -*- coding: utf-8 -*-
"""Vérification de version entre postes connectés (multi-op / DXpédition) :
GET /log/list?ver=X enregistre la version DÉCLARÉE par le poste appelant
(logx_http.peer_versions, clé = IP), et GET /log/status l'expose sous forme
de 'peer_list' ({ip, version, last_seen}) + 'app_version' (version RÉELLE et
toujours à jour du serveur, source unique de vérité — voir logx_version.
APP_VERSION). C'est ce que lit logx_logbook.js pour afficher le badge
"⚠️ versions différentes" avant un événement — comme les équipes N1MM qui
s'alignent sur un numéro de version. Sans ce test, un renommage silencieux
du paramètre ?ver= ou des champs 'peer_list'/'app_version' laisserait le
badge introuvable côté client (toujours '—', jamais d'alerte) sans qu'aucune
requête ne le signale (toujours 200 OK)."""
import http.server
import json
import os
import sys
import threading
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod
from logx_version import APP_VERSION


@pytest.fixture
def server(monkeypatch):
    # Isolation : peer_versions/connected_peers sont des globals partagés par
    # tout le process — sans repli à vide, l'ordre d'exécution des autres
    # tests (déjà passés par le même endpoint) polluerait les assertions ici.
    monkeypatch.setattr(httpmod, 'peer_versions', {})
    monkeypatch.setattr(httpmod, 'connected_peers', set())
    srv = http.server.HTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        t.join(timeout=5)


def _get(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return json.loads(r.read().decode('utf-8'))


def test_log_status_expose_app_version(server):
    """/log/status doit toujours porter la version RÉELLE du serveur, même
    sans aucun poste n'ayant encore pollé /log/list?ver=."""
    d = _get(server, '/log/status')
    assert d['app_version'] == APP_VERSION
    assert d['peer_list'] == []


def test_network_info_expose_app_version(server):
    """/network/info (lu une seule fois au chargement de la page par
    initShareLink()) doit aussi porter app_version — c'est la valeur que le
    client fige comme "sa propre version"."""
    d = _get(server, '/network/info')
    assert d['app_version'] == APP_VERSION


def test_log_list_avec_ver_alimente_peer_list(server):
    """Un poll /log/list?ver=X enregistre la version déclarée, ensuite
    visible dans /log/status → peer_list."""
    _get(server, '/log/list?ver=0.9-beta3')
    status = _get(server, '/log/status')
    assert len(status['peer_list']) == 1
    entry = status['peer_list'][0]
    assert entry['ip'] == '127.0.0.1'
    assert entry['version'] == '0.9-beta3'
    assert entry['last_seen'] > 0


def test_log_list_sans_ver_ne_plante_pas_et_najoute_rien(server):
    """Repli explicite : un client qui n'envoie pas ?ver= (ancienne version
    du front, ou requête manuelle) reste servi normalement, sans entrée
    fantôme dans peer_list — compatibilité ascendante totale."""
    d = _get(server, '/log/list')
    assert 'qsos' in d or 'unchanged' in d
    status = _get(server, '/log/status')
    assert status['peer_list'] == []


def test_log_list_ver_ecrase_la_valeur_precedente_meme_ip(server):
    """Rejouer /log/list?ver= depuis la même IP (ex. la page se recharge
    avec une nouvelle version installée entretemps) doit mettre à jour
    l'entrée existante, jamais en accumuler une deuxième pour la même IP."""
    _get(server, '/log/list?ver=0.9-beta2')
    _get(server, '/log/list?ver=0.9-beta3')
    status = _get(server, '/log/status')
    assert len(status['peer_list']) == 1
    assert status['peer_list'][0]['version'] == '0.9-beta3'
