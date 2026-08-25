# -*- coding: utf-8 -*-
"""Câblage serveur du crédit CHASSE : /data/focus ET /data/spots_ranked
annotent leurs spots via logx_awards.annoter_credit (comportement couvert par
test_chasse_annoter_credit ; ici on vérifie que les DEUX handlers l'appellent,
avec le profil d'objectifs de la config)."""
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8').read()


def _handler(nom_path):
    """Corps du handler `if path == '/data/<x>'` (ou startswith) jusqu'au
    prochain `if path`/`if path.startswith`. Les handlers sont indentés de 8
    espaces (borne exacte : sur-capturer engloberait le handler suivant et
    rendrait les assertions vacantes)."""
    m = re.search(r"if path(?:\.startswith\(| == )'%s'.*?(?=\n        if path)"
                  % re.escape(nom_path), SRC, re.S)
    assert m, 'handler %s introuvable' % nom_path
    return m.group(0)


def test_focus_annoté():
    h = _handler('/data/focus')
    assert re.search(r'annoter_credit\(\s*spots,\s*log_copy', h), '/data/focus ne câble pas annoter_credit'
    assert 'operator_goals' in h


def test_spots_ranked_annoté():
    h = _handler('/data/spots_ranked')
    assert re.search(r'annoter_credit\(\s*full_entries,\s*log_copy', h), '/data/spots_ranked ne câble pas annoter_credit'
    assert 'operator_goals' in h


def test_annoter_credit_existe_bien():
    aw = open(os.path.join(CONCOURS, 'logx_awards.py'), encoding='utf-8').read()
    assert 'def annoter_credit(' in aw


def test_focus_porte_le_locator():
    """Sans le locator dans l'entrée, le crédit « carré neuf » VHF ne peut pas
    être calculé (annoter_credit lit s['locator'])."""
    h = _handler('/data/focus')
    assert re.search(r"'locator':\s*s\.get\('locator'", h), \
        "/data/focus ne porte pas le locator dans l'entrée"


def test_spots_ranked_porte_le_locator():
    h = _handler('/data/spots_ranked')
    assert re.search(r"'locator':\s*s\.get\('locator'", h), \
        "/data/spots_ranked ne porte pas le locator dans l'entrée"
