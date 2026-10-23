# -*- coding: utf-8 -*-
"""Position du bouton ENREGISTRER LE QSO (demande F4GLD 23/10/2026) : juste
SOUS le champ « LOCATOR CORRESPONDANT », avant le commentaire, les onglets et
la grille départements — avant, il était tout en bas et il fallait défiler.
Vérifié aussi en navigateur (fenêtre de saisie détachée) : clic -> QSO ajouté."""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = re.sub(r'<!--.*?-->', '', open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read(),
              flags=re.S)


def _pos(motif):
    m = re.search(motif, HTML)
    assert m, motif
    return m.start()


def test_un_seul_bouton_enregistrer():
    assert len(re.findall(r'id="submitBtn"', HTML)) == 1


def test_bouton_juste_sous_le_locator():
    loc = _pos(r'id="locatorGroup"')
    btn = _pos(r'<button[^>]*id="submitBtn"[^>]*onclick="submitQSO\(\)"')
    com = _pos(r'id="commentGroup"')
    onglets = _pos(r'<div class="entry-tabs">')
    dept = _pos(r'id="deptGridWrap"')
    assert loc < btn < com < onglets < dept
    # rien d'autre qu'une fin de bloc entre le locator et le bouton
    entre = HTML[_pos(r'id="locHint"'):btn]
    assert 'field-group' not in entre and '<input' not in entre


def test_bouton_toujours_dans_la_saisie_principale():
    debut = _pos(r'<div class="saisie-panel">')
    fin = _pos(r'<div class="saisie-secondary">')
    assert debut < _pos(r'id="submitBtn"') < fin
