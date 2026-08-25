# -*- coding: utf-8 -*-
"""Câblage de l'amorçage « importer les prénoms de mon journal » : bouton
expert-only + handler + POST /calldb/enrich_from_log. Le comportement est
couvert par test_calldb_enrich_from_log (pur) et test_calldb_enrich_http (bout
en bout) ; ici on vérifie la présence et l'invariant expert-only.
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(nom):
    with open(os.path.join(BASE, nom), encoding='utf-8') as f:
        return f.read()


def test_bouton_present_et_expert_only():
    html = _lire('logx_logbook.html')
    assert 'id="enrichNomsBtn"' in html
    assert 'enrichirNomsDepuisJournal()' in html
    # plomberie de station : hors chemin critique (masquable en mode simple)
    import re
    m = re.search(r'<button[^>]*id="enrichNomsBtn"[^>]*>', html)
    assert m and 'expert-only' in m.group(0)


def test_handler_poste_l_endpoint():
    js = _lire('logx_lookup.js')
    assert 'function enrichirNomsDepuisJournal' in js
    assert "fetch('/calldb/enrich_from_log'" in js
    assert "method:'POST'" in js
