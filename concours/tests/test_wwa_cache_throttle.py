# -*- coding: utf-8 -*-
"""_fetch_roster_blocking() doit actualiser l'horodatage du cache même en repli,
pour que le throttle CACHE_TTL s'applique aussi aux échecs réseau.

Sur les deux replis (fetch échoué, ou page vide avec cache existant), la fonction
renvoyait le cache sans mettre à jour son 'ts'. get_roster() recalcule 'stale' à
partir de ce ts inchangé -> chaque appel reste 'stale' et re-déclenche
_refresh_roster_async(). Le throttle de 6h était donc totalement neutralisé dès
que hamaward.cloud tombait (ou changeait de mise en page = roster vide) :
martèlement de l'API à chaque spot/QSO.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import logx_wwa as wwa  # noqa: E402


def test_echec_reseau_actualise_le_ts(monkeypatch):
    monkeypatch.setattr(wwa, '_cache', {'ED': {'ts': 1000.0, 'roster': {'F4GLD': 'France'}}})
    monkeypatch.setattr(wwa, 'fetch_url', lambda url, timeout=10: None)   # réseau échoue

    r = wwa._fetch_roster_blocking('ED')

    assert r == {'F4GLD': 'France'}                    # cache périmé renvoyé
    assert wwa._cache['ED']['ts'] > 1000.0             # ts actualisé (avant : inchangé)


def test_page_vide_actualise_le_ts(monkeypatch):
    monkeypatch.setattr(wwa, '_cache', {'ED': {'ts': 1000.0, 'roster': {'F4GLD': 'France'}}})
    # page renvoyée mais roster vide (mise en page changée) + cache existant
    monkeypatch.setattr(wwa, 'fetch_url', lambda url, timeout=10: '<html>rien</html>')
    monkeypatch.setattr(wwa, '_parse_teams_html', lambda html: {})

    r = wwa._fetch_roster_blocking('ED')

    assert r == {'F4GLD': 'France'}                    # dernier roster non-vide gardé
    assert wwa._cache['ED']['ts'] > 1000.0
