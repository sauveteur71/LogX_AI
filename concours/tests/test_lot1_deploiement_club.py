# -*- coding: utf-8 -*-
"""Lot 1 — les trois correctifs qui doivent être en place AVANT qu'un
radio-club utilise LogX AI en conditions réelles (audit du 18/08/2026).

A02 — /log/add renvoie l'id RÉELLEMENT attribué. Sans lui, le carnet client
      gardait un id fantôme après une collision (typiquement juste après un
      import ADIF) : la fusion delta dupliquait la ligne, et « annuler le
      dernier QSO » supprimait un QSO HISTORIQUE au lieu du QSO courant.

A03 — une exception dans un handler laisse une trace ET une réponse 500.
      socketserver rattrape l'exception à l'intérieur de
      process_request_thread(), donc elle n'atteignait ni sys.excepthook ni
      threading.excepthook posés par logx_errorlog.install() : ni errors.log,
      ni /debug/errors, et une connexion coupée côté navigateur que
      l'opérateur attribuait à son réseau.

A06 — /hardware/state expose l'état WinKeyer, sans quoi le client ne pouvait
      pas savoir qu'une émission CW était possible sans CAT (le serveur route
      pourtant /rig/cw et /rig/stop vers le WinKeyer INDÉPENDAMMENT du CAT).
      Conséquence : aucun moyen d'arrêter une émission en cours.
"""
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

import logx_http as h          # noqa: E402
import logx_singleton          # noqa: E402


@pytest.fixture
def serveur():
    """Vrai serveur HTTP, avec la classe de PRODUCTION (LogXHTTPServer) — pas
    ThreadingHTTPServer : c'est justement sa surcharge handle_error() qu'on
    teste en A03."""
    srv = logx_singleton.LogXHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % port
    srv.shutdown()


# X-RC-Token : le jeton d'API persistant du serveur (logx_http._load_auth_token).
# Même en-tête que tests/test_log_delta_sync.py — c'est la voie prévue pour un
# client non-navigateur, le cookie n'étant que le repli du navigateur.
def _headers():
    return {'Content-Type': 'application/json', 'X-RC-Token': h.AUTH_TOKEN}


def _get(base, path):
    req = urllib.request.Request(base + path, headers={'X-RC-Token': h.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _post(base, path, payload):
    req = urllib.request.Request(
        base + path, data=json.dumps(payload).encode('utf-8'),
        headers=_headers(), method='POST')
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read())


# ─── A02 : l'id attribué revient au client ──────────────────────────────────

def test_log_add_renvoie_l_id_attribue(serveur):
    base = serveur
    _st, d = _post(base, '/log/add', {'call': 'F1TEST', 'band': '14', 'mode': 'SSB'})
    assert d['ok'] is True
    assert 'id' in d, "l'id attribué doit revenir au client (sinon undoLastQSO cible un QSO périmé)"
    assert d['id'] is not None


def test_log_add_id_different_quand_collision(serveur):
    """Le cœur du défaut : deux QSO proposant le MÊME id. Le second doit se voir
    attribuer un id DIFFÉRENT, et surtout l'apprendre."""
    base = serveur
    propose = 1234567890123
    _st1, d1 = _post(base, '/log/add', {'call': 'F2AAA', 'band': '14', 'mode': 'SSB', 'id': propose})
    _st2, d2 = _post(base, '/log/add', {'call': 'F2BBB', 'band': '14', 'mode': 'SSB', 'id': propose})
    assert d1['ok'] is True and d2['ok'] is True
    assert d1['id'] == propose, "sans collision, l'id proposé est conservé"
    assert d2['id'] != propose, "en collision, le serveur DOIT réattribuer"
    assert d2['id'] is not None


def test_add_qso_to_log_expose_l_id_dans_info():
    """La fonction elle-même expose l'id, pas seulement l'endpoint : le pont
    WSJT-X passe par add_qso_to_log() sans toucher à do_POST."""
    qso = {'call': 'F3CCC', 'band': '7', 'mode': 'CW'}
    ok, info = h.add_qso_to_log(qso)
    assert ok is True
    assert 'id' in info
    assert info['id'] == qso['id'], "l'id rendu doit être celui réellement posé sur le QSO"


# ─── A03 : une panne laisse une trace ET une réponse ────────────────────────

def test_exception_dans_une_route_get_rend_500_et_journalise(serveur, monkeypatch):
    """Avant ce correctif : ni réponse HTTP (connexion coupée), ni entrée dans
    /debug/errors. L'opérateur voyait un problème réseau, et le rapport de
    bogue arrivait vide."""
    base = serveur

    def _boom(self):
        raise RuntimeError('panne simulee lot1')

    monkeypatch.setattr(h.Handler, '_do_GET_impl', _boom)

    with pytest.raises(urllib.error.HTTPError) as exc:
        _get(base, '/data/spots')
    assert exc.value.code == 500, 'une panne de route doit rendre un 500, pas fermer la connexion'
    corps = json.loads(exc.value.read())
    assert corps['ok'] is False
    assert 'error' in corps

    monkeypatch.undo()
    erreurs = _get(base, '/debug/errors')
    texte = json.dumps(erreurs)
    assert 'panne simulee lot1' in texte, 'la panne doit être journalisée et lisible dans /debug/errors'


def test_exception_dans_une_route_post_rend_500(serveur, monkeypatch):
    base = serveur

    def _boom(self):
        raise RuntimeError('panne post lot1')

    monkeypatch.setattr(h.Handler, '_do_POST_impl', _boom)
    with pytest.raises(urllib.error.HTTPError) as exc:
        _post(base, '/log/add', {'call': 'F4DDD', 'band': '14', 'mode': 'SSB'})
    assert exc.value.code == 500


def test_handle_error_est_surcharge():
    """Le filet de dernier recours : même si l'exception échappe au try/except
    des wrappers (erreur pendant l'écriture de la réponse, par exemple),
    handle_error doit journaliser plutôt que d'écrire sur un stderr invisible
    quand le serveur tourne minimisé."""
    assert 'handle_error' in vars(logx_singleton.LogXHTTPServer), \
        'LogXHTTPServer doit surcharger handle_error (socketserver avale sinon les exceptions des handlers)'


# ─── A06 : le client peut savoir qu'une émission CW est possible ────────────

def test_hardware_state_expose_le_winkeyer(serveur):
    """Sans cette clé, un opérateur WinKeyer SANS CAT n'a aucun moyen de voir
    le bouton STOP CW ni d'envoyer ses macros à la clé — alors que le serveur
    route /rig/cw et /rig/stop vers le WinKeyer avant tout backend CAT."""
    d = _get(serveur, '/hardware/state')
    assert 'winkeyer' in d, '/hardware/state doit exposer l\'état WinKeyer'
    assert 'enabled' in d['winkeyer']
    assert isinstance(d['winkeyer']['enabled'], bool)


def test_jeton_non_ascii_refuse_proprement_sans_planter():
    """Défaut RÉEL trouvé par le filet A03 lui-même, en vérification navigateur :
    secrets.compare_digest() lève TypeError sur une chaîne non-ASCII. Un jeton
    accentué (copier-coller depuis un document, en-tête mal encodé par un outil
    tiers) faisait donc PLANTER la route d'authentification au lieu d'être
    refusé — et avant le filet, la requête mourait sans réponse ni trace.

    Testé au niveau de la FONCTION et non par HTTP : urllib refuse lui-même
    d'encoder un en-tête non-ASCII (UnicodeEncodeError côté client), alors que
    curl l'envoie sans broncher — c'est exactement par là que le défaut a été
    déclenché. Passer par la fonction teste la vraie logique sans dépendre du
    client HTTP utilisé."""
    class _FauxHandler:
        def __init__(self, tok):
            self.headers = {'X-RC-Token': tok, 'Cookie': ''}

    faux = _FauxHandler('jetoné-accentué-€')
    # Ne doit NI lever, NI autoriser.
    assert h.Handler._client_authorized(faux) is False

    # Le jeton légitime, lui, continue d'être accepté (non-régression).
    faux_ok = _FauxHandler(h.AUTH_TOKEN)
    assert h.Handler._client_authorized(faux_ok) is True


def test_winkeyer_state_dict_ne_fait_aucune_io_serie(monkeypatch):
    """Garde-fou de performance : /hardware/state est sondé toutes les
    quelques secondes. On ne renvoie QUE le drapeau de configuration —
    ouvrir le port pour tester la liaison coûterait un aller-retour série à
    chaque sondage."""
    import logx_winkeyer as wk

    def _interdit(*a, **k):
        raise AssertionError('aucune ouverture de port ne doit avoir lieu ici')

    monkeypatch.setattr(wk, 'envoyer', _interdit, raising=False)
    monkeypatch.setattr(wk, 'arreter', _interdit, raising=False)
    d = h._winkeyer_state_dict({'winkeyer_enabled': '1', 'winkeyer_port': 'COM9'})
    assert d == {'enabled': True}
    assert h._winkeyer_state_dict({})['enabled'] is False
