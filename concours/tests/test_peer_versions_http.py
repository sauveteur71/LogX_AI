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
import http.client
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


# ── Purge TTL des postes partis (non-régression du badge fantôme) ────────────
# Bug corrigé : peer_versions n'était JAMAIS purgé. Un poste qui avait pollé
# UNE fois avec une version différente (téléphone d'un visiteur, poste pas
# encore mis à jour changeant ensuite d'IP DHCP, onglet de test) laissait son
# entrée servie à vie par /log/status → badge "⚠️ versions différentes" et
# item CHECKLIST "Version cohérente sur tous les postes" ROUGES en permanence,
# irrécupérables sans redémarrer le serveur — et l'IP périmée restait
# candidate du scan de mise à jour réseau (_known_peer_ips).

def _get_from(base, path, source_ip):
    """GET en forçant l'IP SOURCE de la socket (127.0.0.2 est aussi une
    boucle locale) : le serveur voit une vraie IP socket différente dans
    client_address — même mécanisme que le vrai réseau, pas une injection."""
    hostname, port = base.split('//')[1].split(':')
    conn = http.client.HTTPConnection(hostname, int(port), timeout=5,
                                      source_address=(source_ip, 0))
    try:
        conn.request('GET', path)
        return json.loads(conn.getresponse().read().decode('utf-8'))
    finally:
        conn.close()


def _backdate(ip, seconds):
    """Vieillit last_seen d'une entrée (seule simulation du temps du test)."""
    with httpmod.peer_versions_lock:
        httpmod.peer_versions[ip]['last_seen'] -= seconds


def test_poste_parti_purge_de_peer_list_apres_ttl(server):
    """Scénario exact du bug : un visiteur en 0.9-beta3 polle UNE fois depuis
    127.0.0.2 puis quitte le réseau ; l'hôte (127.0.0.1, version courante)
    continue de poller. Une fois PEER_VERSION_TTL dépassé, /log/status ne
    doit PLUS servir l'entrée du visiteur — sinon badge "⚠️ versions
    différentes" + checklist rouges DÉFINITIVEMENT (les polls sains d'un
    autre poste ne doivent pas la ressusciter). Échoue sans le correctif :
    l'entrée périmée restait servie sans condition d'âge."""
    _get_from(server, '/log/list?ver=0.9-beta3', '127.0.0.2')
    _get(server, f'/log/list?ver={APP_VERSION}')
    ips = {p['ip'] for p in _get(server, '/log/status')['peer_list']}
    assert ips == {'127.0.0.1', '127.0.0.2'}   # avant TTL : les deux visibles
    _backdate('127.0.0.2', httpmod.PEER_VERSION_TTL + 1)
    _get(server, f'/log/list?ver={APP_VERSION}')   # l'hôte, lui, polle encore
    peer_list = _get(server, '/log/status')['peer_list']
    ips = {p['ip'] for p in peer_list}
    assert '127.0.0.2' not in ips   # le fantôme a disparu (badge/checklist OK)
    assert '127.0.0.1' in ips       # le poste encore actif reste affiché
    # Suppression RÉELLE, pas un simple filtre d'affichage : la mémoire est
    # libérée (croissance par IP distincte sinon, cf. audit).
    with httpmod.peer_versions_lock:
        assert '127.0.0.2' not in httpmod.peer_versions


def test_poste_encore_actif_jamais_purge_avant_ttl(server):
    """Garde-fou inverse : une entrée plus vieille que quelques polls mais
    PLUS JEUNE que le TTL (onglet en arrière-plan dont les timers sont
    ralentis par le navigateur) reste servie — la purge ne doit jamais faire
    disparaître un poste simplement lent à poller."""
    _get_from(server, '/log/list?ver=0.9-beta3', '127.0.0.2')
    _backdate('127.0.0.2', httpmod.PEER_VERSION_TTL - 30)
    ips = {p['ip'] for p in _get(server, '/log/status')['peer_list']}
    assert '127.0.0.2' in ips


def test_ip_perimee_hors_candidats_scan_maj_reseau(server):
    """L'IP d'un poste parti ne doit plus être réinjectée comme candidate du
    scan de mise à jour réseau (_known_peer_ips filtre les IP locales, d'où
    des IP TEST-NET routables ici). Échoue sans le correctif : toute IP
    jamais vue restait candidate à vie."""
    now_entry = {'version': '0.9-beta3', 'last_seen': 0}   # epoch 1970 → périmée
    with httpmod.peer_versions_lock:
        httpmod.peer_versions['192.0.2.10'] = dict(now_entry)
    _get_from(server, '/log/list?ver=0.9-beta3', '127.0.0.2')  # pair frais réel
    import time as _t
    with httpmod.peer_versions_lock:
        httpmod.peer_versions['192.0.2.20'] = {'version': '0.9-beta3',
                                               'last_seen': _t.time()}
    ips = httpmod._known_peer_ips()
    assert '192.0.2.10' not in ips   # périmée : plus jamais sondée
    assert '192.0.2.20' in ips       # fraîche : toujours candidate
