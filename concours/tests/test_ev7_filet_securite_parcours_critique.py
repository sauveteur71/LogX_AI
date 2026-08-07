# -*- coding: utf-8 -*-
"""Filet de sécurité EV-7 (docs/LogX_AI_PRD.md) : verrouille le comportement
OBSERVABLE du parcours critique config -> saisie QSO -> export AVANT tout
refactor du frontend (« Filet de sécurité obligatoire : constituer d'abord
une suite de non-régression UI ... avant de refactorer »).

Rejoue ce parcours par les MÊMES routes HTTP que logx_configuration.html/
logx_logbook.html appellent — jamais un appel direct à une fonction JS ou
Python interne. Un futur refactor qui réorganise le JS (ou même le découpe
en modules ES, cf. EV-7) sans changer le CONTRAT observable de ces routes ne
doit jamais faire échouer ce test ; s'il le fait, c'est une vraie régression.

Contest_id volontairement absent de CONTEST_DEFINITIONS (GOLDEN_PATH_TEST) :
ce test ne doit dépendre d'aucune définition de concours réelle qui pourrait
changer/disparaître, seulement du comportement générique des routes."""
import http.server
import json
import os
import sys
import threading
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod
import logx_storage as storage


@pytest.fixture
def server(monkeypatch):
    # Isolation totale (voir piège documenté : des tests passés ont écrit dans
    # de vrais fichiers partagés du dépôt) : log et config en mémoire, jamais
    # persistés sur disque -- chaque test démarre d'un état propre et connu.
    monkeypatch.setattr(httpmod, 'shared_log', [])
    monkeypatch.setattr(httpmod, 'current_config', {})
    monkeypatch.setattr(httpmod, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(httpmod, '_save_config_to_disk', lambda cfg: None)
    # logx_storage.deleted_qsos/log_version/hard_reset_version sont un état
    # GLOBAL module-level, pas remis à zéro entre tests -- notre /log/delete
    # (étape 8 du parcours) mutait le VRAI deleted_qsos en place et polluait
    # tests/test_log_delta_sync.py, exécuté plus tard dans le même processus
    # pytest (trouvé en vérification adversariale : suite complète rouge une
    # fois sur deux selon l'ordre de collecte, jamais en isolation).
    monkeypatch.setattr(storage, 'deleted_qsos', [])
    monkeypatch.setattr(storage, 'log_version', 0)
    monkeypatch.setattr(storage, 'hard_reset_version', 0)
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
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, json.loads(r.read().decode('utf-8'))


def _get_raw(base, path):
    with urllib.request.urlopen(base + path, timeout=5) as r:
        return r.status, r.read().decode('utf-8')


def _post(base, path, payload=None):
    body = json.dumps(payload or {}).encode('utf-8')
    req = urllib.request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json',
                 'X-RC-Token': httpmod.AUTH_TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


CONFIG_MINIMALE = {
    'callsign': 'F4GLD',
    'locator': 'JN18DU',
    'contest': 'GOLDEN_PATH_TEST',
    'usage_mode': 'contest',
}


def test_parcours_critique_config_saisie_export(server):
    """config -> saisie QSO (avec doublon puis forçage) -> liste -> export
    Cabrillo/ADIF -> suppression. Chaque étape verrouille la FORME de la
    réponse HTTP, pas une implémentation JS particulière."""
    base = server

    # 1) CONFIG : sauvegarde d'une config minimale (indicatif + concours +
    #    mode d'utilisation), ce que fait la page CONFIG en fin d'assistant.
    status, res = _post(base, '/config/save', CONFIG_MINIMALE)
    assert status == 200 and res == {'ok': True}

    status, cfg = _get(base, '/config')
    assert status == 200
    assert cfg['callsign'] == 'F4GLD'
    assert cfg['contest'] == 'GOLDEN_PATH_TEST'
    assert cfg['usage_mode'] == 'contest'

    # 2) LOGBOOK : premier enregistrement d'un QSO (bouton "Enregistrer").
    #    'contest' est posé par le CLIENT (currentContest, logx_logbook.js) --
    #    c'est lui qui détermine la portée du QSO (qso_scope_id), indépendante
    #    de la config au moment où /log/list est ensuite consulté.
    qso = {'call': 'F5ABC', 'band': '14', 'mode': 'SSB',
           'date': '20260807', 'time': '14:30',
           'rst_sent': '59', 'rst_rcvd': '59', 'locator': 'JN15XC',
           'contest': 'GOLDEN_PATH_TEST'}
    status, res = _post(base, '/log/add', qso)
    assert status == 200
    assert res == {'ok': True, 'total': 1, 'duplicate': False}

    # 3) Même station/bande/mode relogué sans force=true : refusé comme
    #    doublon. C'est le garde-fou affiché en temps réel dans le formulaire
    #    de saisie (#dupWarn) -- jamais à masquer, quel que soit le mode
    #    débutant/expert (voir CLAUDE.md, "Intuitivité -- maître mot").
    status, res = _post(base, '/log/add', qso)
    assert status == 409
    assert res['duplicate'] is True
    assert res['existing']['id'] is not None

    # 4) Le même doublon avec force=true (bouton "Enregistrer quand même")
    #    doit, lui, passer.
    status, res = _post(base, '/log/add', dict(qso, force=True))
    assert status == 200
    assert res == {'ok': True, 'total': 2, 'duplicate': False}

    # 5) La liste du journal reflète les 2 QSO enregistrés.
    status, lst = _get(base, '/log/list')
    assert status == 200
    assert [q['call'] for q in lst['qsos']] == ['F5ABC', 'F5ABC']
    assert 'version' in lst and 'boot' in lst

    # 6) Export Cabrillo : bien formé, contient les 2 QSO et l'indicatif de
    #    la station -- ce que le bouton "Exporter Cabrillo" télécharge.
    status, cab = _get_raw(base, '/log/export/cabrillo')
    assert status == 200
    assert cab.startswith('START-OF-LOG: 3.0')
    assert cab.rstrip().endswith('END-OF-LOG:')
    assert 'CALLSIGN: F4GLD' in cab
    assert cab.count('QSO:') == 2
    assert 'F5ABC' in cab

    # 7) Export ADIF : bien formé, contient les 2 QSO avec les champs de base
    #    qu'un logger tiers réimporterait.
    status, adi = _get_raw(base, '/log/export/adif')
    assert status == 200
    assert adi.count('<EOR>') == 2
    assert '<call:5>F5ABC' in adi
    assert '<band:3>20m' in adi   # ADIF_BAND['14'] == '20m'
    assert '<mode:3>SSB' in adi

    # 8) Suppression d'un QSO (modale ÉDITION QSO, chemin critique lui aussi)
    #    -- la liste et un nouvel export reflètent bien 1 seul QSO restant.
    qso_id = lst['qsos'][0]['id']
    status, res = _post(base, f'/log/delete/{qso_id}')
    assert status == 200
    assert res == {'ok': True, 'deleted': 1}

    status, lst2 = _get(base, '/log/list')
    assert len(lst2['qsos']) == 1

    status, adi2 = _get_raw(base, '/log/export/adif')
    assert adi2.count('<EOR>') == 1


def test_parcours_critique_sans_config_prealable_ne_casse_pas(server):
    """Un opérateur qui exporte avant toute config (config vide) ne doit
    jamais obtenir une erreur serveur -- juste un export vide/générique.
    État de tout premier lancement, avant même l'écran d'accueil."""
    base = server
    status, cab = _get_raw(base, '/log/export/cabrillo')
    assert status == 200
    assert cab.rstrip().endswith('END-OF-LOG:')
    status, adi = _get_raw(base, '/log/export/adif')
    assert status == 200
    assert adi.count('<EOR>') == 0
