# -*- coding: utf-8 -*-
"""Suite d'ÉVALS INVARIANTS — verrouille par test automatisé, DE BOUT EN BOUT,
les 4 garanties de sécurité les plus critiques de LogX AI :

  I1  0 émission sans consentement      (aucune fonction d'émission RF n'est
                                         atteinte tant que garde-fou ET
                                         consentement n'ont pas TOUS deux passé)
  I2  0 écriture QSO par le LLM         (aucun chemin agent n'appelle
                                         add_qso_to_log de façon autonome)
  I3  0 faux crédit diplôme automatique (une source non sourcée / « IA » ne
                                         crédite jamais un diplôme)
  I4  0 exécution d'action aberrante    (une action LLM à valeur hors-bornes
                                         est rejetée, rien n'est exécuté)

Ces tests COMPLÈTENT les tests unitaires existants (test_tx_consent*,
test_tx_guard, test_agent_act*, test_awards_qsl…) en fermant les trous de
CÂBLAGE : ils exercent les vrais endpoints et prouvent qu'AUCUNE fonction
d'émission / d'écriture n'est appelée sur les chemins interdits.

Non-vacance : chaque test isole UNE barrière et a été confirmé par
contre-épreuve de mutation — le défaut exact qui le fait rougir est cité dans
sa docstring. « masquer un test vert ne prouve rien » (CLAUDE.md).
"""
import http.server
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_http as h            # noqa: E402
import logx_tx_consent as txc    # noqa: E402
import logx_tx_guard as txg      # noqa: E402
import logx_voicekeyer as vk     # noqa: E402
import logx_winkeyer as wk       # noqa: E402
import logx_so2r as so2r         # noqa: E402
import logx_award_credit as ac   # noqa: E402


@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h.Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield 'http://127.0.0.1:%d' % port
    srv.shutdown()


def _post(base, path, obj, token=True):
    hdr = {'Content-Type': 'application/json'}
    if token:
        hdr['X-RC-Token'] = h.AUTH_TOKEN
    rq = urllib.request.Request(base + path, data=json.dumps(obj).encode(), headers=hdr, method='POST')
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _poll(base, aid, n=50):
    state = None
    for _ in range(n):
        with urllib.request.urlopen(base + '/agent/act/state?id=' + aid, timeout=5) as r:
            state = json.loads(r.read())
        if state.get('status') != 'running':
            break
        time.sleep(0.1)
    return state


def _seed_cfg(cfg):
    with h.config_lock:
        saved = dict(h.current_config)
        h.current_config.clear()
        h.current_config.update(cfg)
    return saved


def _restore_cfg(saved):
    with h.config_lock:
        h.current_config.clear()
        h.current_config.update(saved)


def _armer_les_mouchards_emission(monkeypatch):
    """Remplace TOUTES les fonctions d'émission RF réellement atteignables par
    /tx/authorize par des mouchards. `emissions` reste vide si — et seulement
    si — aucune émission n'a été déclenchée."""
    emissions = []
    monkeypatch.setattr(wk, 'envoyer', lambda *a, **k: emissions.append(('cw',) + a) or {'ok': True, 'backend': 'test'})
    monkeypatch.setattr(vk, 'send_voice_message', lambda *a, **k: emissions.append(('tts',) + a) or {'ok': True, 'backend': 'test'})
    monkeypatch.setattr(vk, 'envoyer_message', lambda *a, **k: emissions.append(('wav',) + a) or {'ok': True, 'backend': 'test'})
    # Verrou SO2R neutralisé : on veut isoler garde-fou/consentement comme SEULE
    # barrière restante, pas un 409 de verrou qui masquerait le vrai chemin.
    monkeypatch.setattr(so2r, 'verrouiller_tx', lambda *a, **k: {'ok': True})
    monkeypatch.setattr(so2r, 'deverrouiller_tx', lambda *a, **k: None)
    return emissions


# ─────────────────────────── I1 — 0 émission sans consentement ───────────────

def test_i1_tx_authorize_jeton_inconnu_refuse_sans_emettre(serveur, monkeypatch):
    """Jeton inconnu -> 404 et AUCUNE émission. Rougit si on retire le garde
    `if not c: 404` (logx_http.py ~6685) : le flux continuerait sans jeton."""
    emissions = _armer_les_mouchards_emission(monkeypatch)
    code, j = _post(serveur, '/tx/authorize',
                    {'token': 'jeton-bidon-inexistant', 'duree_max': 5, 'armed': True})
    assert code == 404
    assert emissions == []


def test_i1_garde_maitre_bloque_l_emission(serveur, monkeypatch):
    """Interrupteur maître : armed=false -> 403 et AUCUNE émission, MÊME si le
    consentement passait. On isole le garde-fou (consentement neutralisé) :
    rougit si on casse `if not ok_g` (logx_http.py ~6710) — l'émission partirait."""
    emissions = _armer_les_mouchards_emission(monkeypatch)
    # Consentement neutralisé -> le garde-fou mode/bande est la SEULE barrière.
    monkeypatch.setattr(txc, 'authorize_transmission', lambda *a, **k: {'ok': True, 'audit': 'test'})
    _, prep = _post(serveur, '/tx/prepare',
                    {'operator': 'F4TEST', 'radio_id': 'r1', 'frequency_hz': 14074000,
                     'mode': 'USB', 'power_w': 5, 'message': 'CQ TEST'})
    token = prep.get('token')
    assert token
    code, j = _post(serveur, '/tx/authorize', {'token': token, 'duree_max': 5, 'armed': False})
    assert code == 403 and j.get('blocked')
    assert emissions == []          # armé=non -> rien n'est parti


def test_i1_consentement_exige_avant_emission(serveur, monkeypatch):
    """Consentement : garde-fou passé, mais l'état CAT réel ne valide pas le
    jeton (pas de radio) -> 403 et AUCUNE émission. On isole le consentement
    (garde-fou neutralisé) : rougit si authorize_transmission cesse de lever
    (usage unique / relecture CAT cassés, logx_tx_consent.py ~298/311)."""
    emissions = _armer_les_mouchards_emission(monkeypatch)
    # Garde-fou mode/bande neutralisé -> le consentement est la SEULE barrière.
    monkeypatch.setattr(txg, 'tx_autorise', lambda *a, **k: (True, ''))
    _, prep = _post(serveur, '/tx/prepare',
                    {'operator': 'F4TEST', 'radio_id': 'r1', 'frequency_hz': 14074000,
                     'mode': 'USB', 'power_w': 5, 'message': 'CQ TEST'})
    token = prep.get('token')
    assert token
    code, j = _post(serveur, '/tx/authorize', {'token': token, 'duree_max': 5, 'armed': True})
    assert code == 403 and j.get('blocked')
    assert emissions == []          # consentement non validé -> rien n'est parti


# ─────────────────────────── I2 — 0 écriture QSO par le LLM ──────────────────

def test_i2_agent_act_ne_logue_jamais_de_qso(serveur, monkeypatch):
    """Le tool `loguer_station` renvoyé par le LLM ne fait que PROPOSER : le
    serveur ne doit JAMAIS appeler add_qso_to_log. Rougit si on injecte un
    add_qso_to_log(pending) dans _run (logx_http.py ~8120)."""
    ecritures = []
    monkeypatch.setattr(h, 'add_qso_to_log', lambda *a, **k: ecritures.append(a) or (True, {}))
    monkeypatch.setattr(h, 'call_llm_actions', lambda *a, **k: {
        'text': 'Tu peux loguer JA1XYZ.',
        'action': {'tool': 'loguer_station',
                   'input': {'indicatif': 'JA1XYZ', 'band': '20m', 'mode': 'FT8'}}})
    saved = _seed_cfg({'api_key': 'x', 'api_provider': 'anthropic'})
    try:
        code, j = _post(serveur, '/agent/act', {'needs_context': False, 'system': 's', 'message': 'x'})
        assert code == 200 and j.get('id')
        state = _poll(serveur, j['id'])
        assert state['status'] == 'done'
        assert ecritures == []                         # AUCUNE écriture au log
        assert state['action'] and state['action'].get('type') == 'log'  # juste une proposition
    finally:
        _restore_cfg(saved)


# ─────────────────────────── I3 — 0 faux crédit diplôme ──────────────────────

def test_i3_source_llm_ou_inconnue_ne_credite_jamais():
    """Le crédit d'un diplôme est déterministe et sourcé : une source « IA » ou
    non sourcée ne crédite JAMAIS. Rougit si on ajoute une AwardCreditRule
    ALLOWED pour une source non sourcée (logx_award_credit.py)."""
    assert ac.credite('ARRL_DXCC', 'AI') is False          # le LLM ne crédite pas
    assert ac.credite('ARRL_DXCC', 'CHATGPT') is False     # aucune source « IA »
    assert ac.credite('ARRL_DXCC', 'INCONNUE') is False    # règle absente = pas de crédit
    assert ac.credite('ARRL_DXCC', 'EQSL') is False        # explicitement refusée (contrôle)
    assert ac.credite('ARRL_DXCC', 'LOTW') is True         # contrôle positif : la vraie source crédite


# ─────────────────────────── I4 — 0 exécution d'action aberrante ─────────────

def test_i4_action_aberrante_rejetee_de_bout_en_bout(serveur, monkeypatch):
    """Une action LLM à valeur hors-bornes (azimut 400°) est rejetée : l'état du
    job renvoie action=None, rien n'est exécutable. Rougit si on casse la borne
    azimut de pending_action_from_tool (logx_http.py ~561)."""
    monkeypatch.setattr(h, 'call_llm_actions', lambda *a, **k: {
        'text': 'Vise par ici.',
        'action': {'tool': 'pointer_rotor', 'input': {'azimut': 400, 'cible': 'X'}}})
    saved = _seed_cfg({'api_key': 'x', 'api_provider': 'anthropic'})
    try:
        code, j = _post(serveur, '/agent/act', {'needs_context': False, 'system': 's', 'message': 'x'})
        assert code == 200 and j.get('id')
        state = _poll(serveur, j['id'])
        assert state['status'] == 'done'
        assert state['action'] is None                 # valeur aberrante -> aucune action proposable
    finally:
        _restore_cfg(saved)


# ─────────────── I5 — le jeton de consentement n'est jamais journalisé ───────

def test_i5_audit_ne_journalise_jamais_le_jeton_en_clair():
    """Confidentialité : le journal d'audit d'émission ne contient JAMAIS le
    jeton de consentement en clair (il pourrait rejouer une autorisation).
    Rougit si _audit_entry expose consent.token au lieu de 'redacted'."""
    c = txc.create_tx_consent('F4GLD', 'r1', 14074000, 'USB', 5, 'CQ TEST')
    rs = {'cat_connected': True, 'ptt_locked': False,
          'frequency_hz': c.frequency_hz, 'mode': c.mode, 'power_w': c.power_w}
    entry = txc.authorize_transmission(c, rs)
    assert entry['consent_token'] == 'redacted'
    assert c.token not in str(entry)          # le vrai jeton n'apparaît nulle part
