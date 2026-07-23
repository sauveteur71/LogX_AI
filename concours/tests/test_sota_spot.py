# -*- coding: utf-8 -*-
"""Tests de l'auto-spot SOTA (logx_sota_spot.py) : authentification SOTA SSO
(Authorization Code + PKCE, endpoints Keycloak réels vérifiés en observant le
flux de connexion officiel de sotawatch.sota.org.uk — voir docstring du
module) puis publication du spot. Aucun appel réseau réel : urllib et
logx_utils.post_url_form/post_url_json sont systématiquement monkeypatchés.

Ce module a deux garde-fous VOLONTAIREMENT distincts du seul clientId — voir
sota_spot_settings() : le clientId (vide = inactif, comme les autres
services externes) ET la case sota_ai_approval_ack (exigée par les CGU de
l'API SOTA pour tout logiciel assisté par IA, voir docstring du module) —
ces tests vérifient que les DEUX sont bien requis avant le moindre appel
réseau d'ÉCRITURE (post_spot), alors que la simple connexion SSO (obtenir un
jeton) ne nécessite que le clientId."""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_sota_spot as sotaspot

CFG_BASE = {'sota_client_id': 'CLIENT123', 'callsign': 'F6KQJ'}
CFG_READY = dict(CFG_BASE, sota_ai_approval_ack='1')


@pytest.fixture(autouse=True)
def _isolate_module_state(monkeypatch):
    """Les jetons/état en attente sont des singletons au niveau module (comme
    HRDLOG_FAIL_CIRCUIT dans logx_qsl) — on les réinitialise avant CHAQUE test
    et on empêche toute écriture disque réelle (sota_oauth_tokens.json)."""
    monkeypatch.setattr(sotaspot, '_tokens',
                        {'access_token': '', 'refresh_token': '', 'expires_at': 0})
    monkeypatch.setattr(sotaspot, '_tokens_loaded', True)   # évite une vraie lecture disque
    monkeypatch.setattr(sotaspot, '_pending', {})
    monkeypatch.setattr(sotaspot, '_save_tokens', lambda: None)
    yield


# ─── Réglages ─────────────────────────────────────────────────────────────────

def test_settings_vide_par_defaut_inactif():
    s = sotaspot.sota_spot_settings({})
    assert not s['configured'] and not s['ready_to_post']


def test_settings_client_id_seul_sans_ack_pas_pret_a_poster():
    """Le clientId seul ne suffit pas à publier — la case CGU (ack) est une
    condition INDÉPENDANTE, exigée par les Conditions d'Utilisation SOTA."""
    s = sotaspot.sota_spot_settings(CFG_BASE)
    assert s['configured'] and not s['ai_approval_ack'] and not s['ready_to_post']


def test_settings_les_deux_prets_a_poster():
    s = sotaspot.sota_spot_settings(CFG_READY)
    assert s['configured'] and s['ai_approval_ack'] and s['ready_to_post']


# ─── build_authorize_url (PKCE) ───────────────────────────────────────────────

def test_build_authorize_url_sans_client_id():
    url, err = sotaspot.build_authorize_url({})
    assert url is None and 'clientId' in err


def test_build_authorize_url_contient_pkce_et_state():
    url, err = sotaspot.build_authorize_url(CFG_BASE)
    assert err == ''
    assert url.startswith(sotaspot.SSO_AUTHORIZE_URL + '?')
    assert 'client_id=CLIENT123' in url
    assert 'code_challenge=' in url and 'code_challenge_method=S256' in url
    assert 'response_type=code' in url and 'scope=openid' in url
    # Un couple state/verifier a été enregistré pour le callback à venir.
    assert len(sotaspot._pending) == 1


def test_build_authorize_url_redirect_uri_localhost():
    import urllib.parse
    url, err = sotaspot.build_authorize_url(CFG_BASE)
    # redirect_uri est une VALEUR de la query string : les '/' y sont
    # percent-encodés (%2F) par urlencode, il faut donc décoder le paramètre
    # plutôt que chercher '/sota/oauth/callback' tel quel dans l'URL brute.
    qs = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    redirect_uri = qs['redirect_uri'][0]
    assert 'localhost' in redirect_uri and redirect_uri.endswith('/sota/oauth/callback')


# ─── handle_oauth_callback (échange code -> jeton) ────────────────────────────

def test_callback_state_invalide():
    ok, msg = sotaspot.handle_oauth_callback('code123', 'state-inconnu', CFG_BASE)
    assert not ok and 'expirée ou invalide' in msg


def test_callback_succes(monkeypatch):
    url, _ = sotaspot.build_authorize_url(CFG_BASE)
    state = list(sotaspot._pending.keys())[0]
    captured = {}
    def fake_post_url_form(url, fields, timeout=10, headers=None):
        captured['fields'] = fields
        return 200, '{"access_token": "AT1", "refresh_token": "RT1", "expires_in": 300}'
    monkeypatch.setattr('logx_utils.post_url_form', fake_post_url_form)

    ok, msg = sotaspot.handle_oauth_callback('the-code', state, CFG_BASE)
    assert ok is True
    assert sotaspot._tokens['access_token'] == 'AT1'
    assert sotaspot._tokens['refresh_token'] == 'RT1'
    assert captured['fields']['grant_type'] == 'authorization_code'
    assert captured['fields']['code'] == 'the-code'
    assert captured['fields']['client_id'] == 'CLIENT123'
    assert 'code_verifier' in captured['fields']
    # L'état ne doit plus être réutilisable (protection anti-rejeu).
    assert state not in sotaspot._pending


def test_callback_echange_refuse(monkeypatch):
    url, _ = sotaspot.build_authorize_url(CFG_BASE)
    state = list(sotaspot._pending.keys())[0]
    monkeypatch.setattr('logx_utils.post_url_form',
                        lambda url, fields, timeout=10, headers=None: (400, 'invalid_grant'))
    ok, msg = sotaspot.handle_oauth_callback('bad-code', state, CFG_BASE)
    assert not ok and 'refusé' in msg


# ─── ensure_access_token ──────────────────────────────────────────────────────

def test_ensure_access_token_sans_configuration():
    token, err = sotaspot.ensure_access_token({})
    assert token is None and 'clientId' in err


def test_ensure_access_token_cache_valide_pas_d_appel_reseau(monkeypatch):
    import time
    sotaspot._tokens.update(access_token='CACHED', refresh_token='RT', expires_at=time.time() + 300)
    monkeypatch.setattr('logx_utils.post_url_form',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('ne doit pas être appelé')))
    token, err = sotaspot.ensure_access_token(CFG_BASE)
    assert token == 'CACHED' and err == ''


def test_ensure_access_token_rafraichit_si_expire(monkeypatch):
    sotaspot._tokens.update(access_token='OLD', refresh_token='RT-VALID', expires_at=0)
    captured = {}
    def fake(url, fields, timeout=10, headers=None):
        captured['fields'] = fields
        return 200, '{"access_token": "NEW", "expires_in": 600}'
    monkeypatch.setattr('logx_utils.post_url_form', fake)
    token, err = sotaspot.ensure_access_token(CFG_BASE)
    assert token == 'NEW' and err == ''
    assert captured['fields']['grant_type'] == 'refresh_token'
    assert captured['fields']['refresh_token'] == 'RT-VALID'


def test_ensure_access_token_sans_refresh_demande_reconnexion():
    token, err = sotaspot.ensure_access_token(CFG_BASE)
    assert token is None and 'Se connecter' in err


# ─── post_spot (écriture — gatée par ready_to_post) ───────────────────────────

def test_post_spot_sans_client_id():
    r = sotaspot.post_spot({}, 'F/AL-001', 145.500, 'FM')
    assert not r['ok'] and 'non configuré' in r['error']


def test_post_spot_sans_ack_bloque_avant_tout_reseau(monkeypatch):
    """Le clientId seul ne débloque PAS l'envoi réel — la case CGU est
    obligatoire. Aucun appel réseau ne doit être tenté."""
    monkeypatch.setattr('logx_utils.post_url_json',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('ne doit pas être appelé')))
    r = sotaspot.post_spot(CFG_BASE, 'F/AL-001', 145.500, 'FM')
    assert not r['ok'] and 'accord préalable' in r['error']


def test_post_spot_reference_manquante():
    r = sotaspot.post_spot(CFG_READY, '', 145.500, 'FM')
    assert not r['ok'] and 'sommet' in r['error'].lower()


def test_post_spot_frequence_invalide():
    r = sotaspot.post_spot(CFG_READY, 'F/AL-001', 0, 'FM')
    assert not r['ok'] and 'Fréquence' in r['error']


def test_post_spot_sans_authentification():
    r = sotaspot.post_spot(CFG_READY, 'F/AL-001', 145.500, 'FM')
    assert not r['ok'] and 'Se connecter' in r['error']


def test_post_spot_succes(monkeypatch):
    import time
    sotaspot._tokens.update(access_token='AT1', refresh_token='RT1', expires_at=time.time() + 300)
    captured = {}
    def fake_post_json(url, payload, timeout=10, headers=None):
        captured['url'] = url
        captured['payload'] = payload
        captured['headers'] = headers
        return 200, 'spot accepted'
    monkeypatch.setattr('logx_utils.post_url_json', fake_post_json)

    r = sotaspot.post_spot(CFG_READY, 'f/al-001', 145.500, 'fm', comment='test LogX AI')
    assert r['ok'] is True
    assert captured['url'] == sotaspot.SOTA_SPOT_POST_URL
    assert captured['payload']['activatorCallsign'] == 'F6KQJ'
    assert captured['payload']['summitCode'] == 'F/AL-001'
    assert captured['payload']['mode'] == 'FM'
    assert captured['headers']['Authorization'] == 'Bearer AT1'


def test_post_spot_refuse_par_sota(monkeypatch):
    import time
    sotaspot._tokens.update(access_token='AT1', refresh_token='RT1', expires_at=time.time() + 300)
    monkeypatch.setattr('logx_utils.post_url_json',
                        lambda *a, **k: (422, 'invalid summit code'))
    r = sotaspot.post_spot(CFG_READY, 'F/AL-001', 145.500, 'FM')
    assert not r['ok'] and 'refusé' in r['error']


# ─── status() ─────────────────────────────────────────────────────────────────

def test_status_reflete_configuration_et_authentification():
    assert sotaspot.status({}) == {
        'configured': False, 'ai_approval_ack': False,
        'ready_to_post': False, 'authenticated': False,
    }
    import time
    sotaspot._tokens.update(access_token='AT1', refresh_token='', expires_at=time.time() + 300)
    st = sotaspot.status(CFG_READY)
    assert st['configured'] and st['ai_approval_ack'] and st['ready_to_post'] and st['authenticated']
