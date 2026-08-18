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
    # Assertions par CHAMP, pas égalité stricte du dict : la réponse est un
    # contrat EXTENSIBLE, et figer sa forme exacte faisait échouer ce test au
    # premier champ ajouté sans qu'aucune régression n'ait eu lieu (c'est
    # arrivé avec 'id', ajouté le 18/08/2026 — sans lui, « annuler le dernier
    # QSO » supprimait un QSO historique après un import ADIF).
    # Même correction de méthode que test_page_chasse_split.py, qui figeait le
    # titre exact de 5 panneaux, préfixe décoratif compris.
    assert res['ok'] is True
    assert res['total'] == 1
    assert res['duplicate'] is False

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
    # Par champ, même raison qu'au point 2 ci-dessus.
    assert res['ok'] is True
    assert res['total'] == 2
    assert res['duplicate'] is False

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


def test_correction_qso_via_modale_edition(server):
    """Modale ÉDITION QSO (correction d'un indicatif mal saisi, chemin
    critique au même titre que la saisie initiale -- voir CLAUDE.md,
    "Intuitivité -- maître mot") : /log/update remplace le QSO en entier,
    par son id. La correction doit se retrouver dans la liste ET dans un
    nouvel export, jamais l'ancienne valeur."""
    base = server
    _post(base, '/config/save', CONFIG_MINIMALE)
    qso = {'call': 'F5TYPO', 'band': '14', 'mode': 'SSB',
           'date': '20260807', 'time': '14:30',
           'rst_sent': '59', 'rst_rcvd': '59', 'contest': 'GOLDEN_PATH_TEST'}
    status, res = _post(base, '/log/add', qso)
    assert status == 200
    status, lst = _get(base, '/log/list')
    qso_id = lst['qsos'][0]['id']

    corrige = dict(qso, id=qso_id, call='F5ABCD')
    status, res = _post(base, '/log/update', corrige)
    assert status == 200 and res == {'ok': True}

    status, lst2 = _get(base, '/log/list')
    assert [q['call'] for q in lst2['qsos']] == ['F5ABCD']

    status, adi = _get_raw(base, '/log/export/adif')
    assert '<call:6>F5ABCD' in adi
    assert 'F5TYPO' not in adi   # l'ancienne valeur ne doit survivre nulle part

    # QSO déjà supprimé par un autre poste entre-temps (course multi-op,
    # scénario documenté dans le handler) : erreur explicite, pas un faux ok.
    status, res = _post(base, '/log/update', dict(corrige, id=999999))
    assert status == 404 and res['ok'] is False


def test_logbook_simple_pas_de_regle_doublon(server):
    """usage_mode='simple' (carnet de trafic courant, hors concours) :
    recontacter la même station sur la même bande est normal, PAS un
    doublon -- règle explicitement différente du mode concours (voir
    add_qso_to_log). Aucun 'contest' posé sur les QSO, comme le fait
    réellement un carnet simple."""
    base = server
    status, res = _post(base, '/config/save',
                         {'callsign': 'F4GLD', 'usage_mode': 'simple'})
    assert status == 200

    qso = {'call': 'DL1AA', 'band': '14', 'mode': 'SSB',
           'date': '20260807', 'time': '09:00',
           'rst_sent': '59', 'rst_rcvd': '59'}
    status, res = _post(base, '/log/add', qso)
    assert status == 200 and res['duplicate'] is False

    # Même station/bande/mode, un autre jour -- accepté sans force=true.
    status, res = _post(base, '/log/add', dict(qso, date='20260808'))
    assert status == 200 and res['duplicate'] is False

    status, lst = _get(base, '/log/list')
    assert len(lst['qsos']) == 2   # aucune portée concours -> rien filtré


def test_import_adif_preview_puis_commit(server):
    """Import d'un log existant (bouton "Importer ADIF" de CONFIG/LOGBOOK) :
    preview = aperçu SANS écrire, commit = écriture réelle. Chemin
    d'ingestion alternatif à la saisie manuelle, tout aussi critique pour
    un opérateur qui rejoint LogX AI avec un log déjà commencé ailleurs.
    usage_mode='simple' (carnet, pas concours) : les QSO importés ne
    portent pas de 'contest' -- sous une portée concours active, ils
    seraient filtrés hors de /log/list (comportement réel et voulu, voir
    _scope_filtered/qso_scope_id)."""
    base = server
    _post(base, '/config/save', {'callsign': 'F4GLD', 'usage_mode': 'simple'})
    adif = ("En-tête\n<adif_ver:5>3.1.4<programid:4>Test<EOH>\n"
            "<CALL:5>DL1AA<BAND:2>2m<MODE:3>SSB<QSO_DATE:8>20260710"
            "<TIME_ON:4>1230<RST_SENT:2>59<RST_RCVD:2>59<EOR>\n"
            "<CALL:5>F5XXX<BAND:3>20m<MODE:2>CW<QSO_DATE:8>20260711"
            "<TIME_ON:6>081500<RST_SENT:3>599<RST_RCVD:3>599<EOR>\n")

    status, preview = _post(base, '/log/import_adif/preview', {'adif': adif})
    assert status == 200
    status, lst = _get(base, '/log/list')
    assert lst['qsos'] == []   # preview = aperçu, AUCUNE écriture

    status, res = _post(base, '/log/import_adif/commit', {'adif': adif})
    assert status == 200
    assert res['ok'] is True and res['imported'] == 2 and res['errors'] == []

    status, lst2 = _get(base, '/log/list')
    assert sorted(q['call'] for q in lst2['qsos']) == ['DL1AA', 'F5XXX']


def test_multi_operateur_categorie_cabrillo(server):
    """Session multi-opérateur (radioclub/expédition) : au moins 2 opérateurs
    distincts sur le même log fait basculer la catégorie déclarée du
    Cabrillo -- SINGLE-OP -> MULTI-OP. Comportement du barème, pas un détail
    d'affichage : une régression ici fausse la déclaration du concours."""
    base = server
    _post(base, '/config/save', CONFIG_MINIMALE)
    _post(base, '/log/add', {'call': 'F5ABC', 'band': '14', 'mode': 'SSB',
                              'date': '20260807', 'time': '10:00',
                              'contest': 'GOLDEN_PATH_TEST', 'operator': 'OP1'})
    _post(base, '/log/add', {'call': 'G4ZZZ', 'band': '21', 'mode': 'CW',
                              'date': '20260807', 'time': '11:00',
                              'contest': 'GOLDEN_PATH_TEST', 'operator': 'OP2'})
    status, cab = _get_raw(base, '/log/export/cabrillo')
    assert status == 200
    assert 'CATEGORY-OPERATOR: MULTI-OP' in cab
