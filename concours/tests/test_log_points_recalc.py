# -*- coding: utf-8 -*-
"""add_qso_to_log recalcule TOUJOURS les points côté serveur (logx_scoring.
score_new_qso), quelle que soit la valeur envoyée par le client — corrige
notamment la page mobile (logx_mobile.html), qui assumait un barème
"points = distance" en dur même hors barème kilométrique (ex. CQ WW, European
HF Championship...), et le pont WSJT-X/ADIF réseau qui n'envoyait même pas de
champ 'points' du tout.

Recalcul seulement à l'AJOUT (pas de migration rétroactive du log existant) :
voir tests/test_storage.py pour la persistance, qui n'est pas concernée ici."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as http


def _qso(**kw):
    base = {'call': 'DL1ABC', 'band': '14', 'mode': 'SSB', 'contest': 'EU_HF_CHAMP',
            'my_call': 'F6KQJ', 'my_locator': 'JN15XC', 'locator': '',
            'date': '20270718', 'time': '10:00'}
    base.update(kw)
    return base


def _prep(monkeypatch, log=None):
    monkeypatch.setattr(http, 'shared_log', log if log is not None else [])
    monkeypatch.setattr(http, 'save_log_to_disk', lambda: None)
    monkeypatch.setattr(http, 'current_config', {'usage_mode': 'simple'})


def test_add_qso_recalcule_les_points_meme_si_le_client_ment(monkeypatch):
    """Le client envoie 'points': 9999 — le serveur impose sa propre valeur
    (EU_HF_CHAMP, station européenne = 1 pt)."""
    _prep(monkeypatch)
    ok, _info = http.add_qso_to_log(_qso(points=9999))
    assert ok
    assert http.shared_log[0]['points'] == 1


def test_add_qso_mobile_hors_perimetre_corrige_a_zero(monkeypatch):
    """La mobile enverrait 'points' = distance même pour une station hors
    Europe (EU_HF_CHAMP : hors périmètre = 0 pt) — le serveur corrige."""
    _prep(monkeypatch)
    ok, _info = http.add_qso_to_log(_qso(call='W1AW', points=555, source='mobile'))
    assert ok
    assert http.shared_log[0]['points'] == 0


def test_add_qso_wsjtx_sans_champ_points_recoit_une_valeur(monkeypatch):
    """Le pont WSJT-X (logx_wsjtx.qso_from_logged) n'envoie même pas de champ
    'points' — après insertion, le QSO doit en avoir un correctement calculé,
    jamais rester silencieusement absent."""
    _prep(monkeypatch)
    qso = {'call': 'DL1ABC', 'band': '14', 'mode': 'SSB', 'contest': 'EU_HF_CHAMP',
           'my_locator': 'JN15XC', 'locator': '', 'source': 'wsjtx',
           'date': '20270718', 'time': '10:00'}
    ok, _info = http.add_qso_to_log(qso)
    assert ok
    assert http.shared_log[0]['points'] == 1


def test_add_qso_ne_touche_pas_les_qso_deja_loggues(monkeypatch):
    """Recalcul seulement à l'ajout : un QSO déjà présent dans shared_log
    (points historiques, potentiellement d'un ancien barème) ne doit jamais
    être modifié par l'insertion d'un NOUVEAU QSO."""
    existing = _qso(call='F5XYZ', id=1, points=42)
    _prep(monkeypatch, log=[existing])
    ok, _info = http.add_qso_to_log(_qso(call='DL1ABC', points=9999))
    assert ok
    assert http.shared_log[0]['points'] == 42   # inchangé
    assert http.shared_log[1]['points'] == 1    # nouveau QSO, recalculé
