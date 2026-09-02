# -*- coding: utf-8 -*-
"""QSO EN COURS visible et coloré, TOUS MODES (demande F4GLD).

DÉFAUT : le panneau « QSO en cours » et le repère visuel ne s'affichaient que
pour le SÉQUENCEUR (condition `seq && call === seq.cible`). En mode MANUEL (seq
nul), un QSO se faisait sans aucun affichage du QSO en cours — « un QSO fait sans
que je voie nulle part l'affichage du QSO en cours ». Et le repère était en gras,
pas en code couleur.

CE QUI EST TENU : un correspondant courant UNIFIÉ (_qsoEnCoursCible : séquenceur
-> copilote -> sélection manuelle), un CODE COULEUR (classe qso-actif, fond) sur
la ligne du QSO en cours, et la sélection manuelle qui alimente cet état.
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_ft8_sequenceur import _extraire_fonction  # noqa: E402

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE_FT8 = os.path.join(CONCOURS, 'logx_ft8.html')


def _lire():
    with open(PAGE_FT8, encoding='utf-8') as f:
        return f.read()


def _sans_commentaires(src):
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'//.*$', '', li) for li in src.splitlines())


# ─── Comportement : le correspondant courant unifié (vrai code extrait) ──────

def _ctx(seq_cible=None, copilote=None, sel=''):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval('var seq = %s;' % ('{cible:%r}' % seq_cible if seq_cible else 'null'))
    ctx.eval('var _copiloteQso = %s;' % ('{dxCall:%r}' % copilote if copilote else 'null'))
    ctx.eval('var _selCall = %r;' % (sel or ''))
    ctx.eval(_extraire_fonction(_lire(), '_qsoEnCoursCible'))
    return ctx


def test_priorite_sequenceur_copilote_manuel():
    # séquenceur prime
    assert _ctx(seq_cible='F4ABC', copilote='SP9QQQ', sel='E70SZ').eval('_qsoEnCoursCible()') == 'F4ABC'
    # sans séquence : copilote
    assert _ctx(copilote='SP9QQQ', sel='E70SZ').eval('_qsoEnCoursCible()') == 'SP9QQQ'
    # ni séquence ni copilote : la sélection MANUELLE (le cas de F4GLD)
    assert _ctx(sel='E70SZ').eval('_qsoEnCoursCible()') == 'E70SZ'
    # rien en cours
    assert _ctx().eval('_qsoEnCoursCible()') == ''


def test_cible_normalisee_en_majuscules():
    assert _ctx(sel='e70sz').eval('_qsoEnCoursCible()') == 'E70SZ'


# ─── Structure : sélection manuelle -> état, coloration, panneau tous modes ──

def test_selection_manuelle_alimente_le_correspondant_courant():
    corps = _sans_commentaires(_extraire_fonction(_lire(), 'afficherAppelSelectionne'))
    assert '_selCall =' in corps, (
        'afficherAppelSelectionne doit mémoriser la station sélectionnée '
        '(correspondant du QSO en cours en mode manuel) :\n' + corps)


def test_ajouterDecodage_colore_le_qso_en_cours_tous_modes():
    corps = _sans_commentaires(_extraire_fonction(_lire(), 'ajouterDecodage'))
    # ne dépend plus du seul séquenceur
    assert 'seq && call === seq.cible' not in corps, (
        'le panneau/repère QSO en cours ne doit plus être limité au séquenceur')
    assert '_qsoEnCoursCible()' in corps, (
        'ajouterDecodage doit utiliser le correspondant courant UNIFIÉ')
    # CODE COULEUR sur la ligne, pas juste du gras
    assert "classList.add('qso-actif')" in corps, (
        'la ligne du QSO en cours doit recevoir la classe couleur qso-actif :\n' + corps)


def test_le_code_couleur_qso_actif_est_defini_avec_un_fond():
    src = _lire()
    m = re.search(r'tr\.qso-actif td\s*\{([^}]*)\}', src)
    assert m, 'la règle .qso-actif doit exister'
    assert 'background' in m.group(1), (
        'qso-actif doit être un CODE COULEUR (fond), pas seulement du gras : ' + m.group(1))
