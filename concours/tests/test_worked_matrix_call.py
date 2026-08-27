# -*- coding: utf-8 -*-
"""Matrice bande × mode POUR UN INDICATIF PRÉCIS (worked_matrix_call).

DEMANDE UTILISATEUR (F4GLD, 27/08/2026), mot pour mot : « il faudrait pouvoir
afficher un worked matrix par call en général une pédition sur une île par
exemple on essaie de les faires dans tout les modes et bandes ».

C'est le complément à `lotw_grid()` (qui répond pour l'ENTITÉ DXCC, et
seulement sur la confirmation LoTW) : ici la grille porte sur l'INDICATIF EXACT
et sur « travaillé / confirmé (toute source) / rien », pour suivre en un coup
d'œil quels créneaux bande×mode il reste à faire AVEC CETTE STATION — le besoin
typique d'une DXpedition qu'on essaie de contacter sur toutes les bandes/modes.

Distinct de `worked_matrix()` (station entière ou concours, comptes par case) :
celui-ci est PAR CALL, à statut, jamais un simple compteur.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_awards as aw   # noqa: E402


def _qso(call, band, mode, time='1200'):
    return {'call': call, 'band': band, 'mode': mode,
            'date': '2026-01-01', 'time': time}


@pytest.fixture
def sans_fichiers(monkeypatch):
    """Ni archives ni QSL du poste : le test décide seul des confirmations."""
    monkeypatch.setattr(aw, '_read_archives', lambda: [])
    monkeypatch.setattr(aw, '_read_qso_archive', lambda: [])
    aw.invalidate()

    def _conf(d):
        monkeypatch.setattr(aw, '_load_confirmations', lambda: d)
        aw.invalidate()
    return _conf


# ─── Activation ──────────────────────────────────────────────────────────────

def test_indicatif_trop_court_inactif(sans_fichiers):
    sans_fichiers({})
    assert aw.worked_matrix_call('XX', []) == {'active': False}


def test_active_meme_sans_aucun_qso(sans_fichiers):
    """Une pédition qu'on n'a PAS encore contactée : la grille doit s'afficher
    pleine de cases 'none' — c'est justement la liste des créneaux à viser."""
    sans_fichiers({})
    m = aw.worked_matrix_call('TX7X', [])
    assert m['active'] is True
    assert m['call'] == 'TX7X'
    assert m['modes'] == ['CW', 'PHONE', 'DIGITAL']
    # Les bandes standard DX sont toujours présentes, même vides.
    for b in ('1.8', '7', '14', '28', '50', '144', '432'):
        assert b in m['grid']
        assert m['grid'][b]['CW'] == 'none'
    assert m['worked'] == 0 and m['confirmed'] == 0


# ─── Statut par case ─────────────────────────────────────────────────────────

def test_travaille_non_confirme(sans_fichiers):
    sans_fichiers({})
    log = [_qso('TX7X', '14', 'CW'), _qso('TX7X', '7', 'SSB')]
    m = aw.worked_matrix_call('TX7X', log)
    assert m['grid']['14']['CW'] == 'worked'
    assert m['grid']['7']['PHONE'] == 'worked'
    assert m['grid']['14']['PHONE'] == 'none'
    assert m['worked'] == 2 and m['confirmed'] == 0


def test_confirme_toutes_sources(sans_fichiers):
    """Contrairement à lotw_grid(), N'IMPORTE QUELLE source de confirmation
    (eQSL, papier, LoTW) marque la case 'confirmed' : la question ici est
    « ai-je bouclé ce créneau avec cette station », pas « est-ce créditable
    DXCC »."""
    conf = sans_fichiers
    conf({'TX7X|14|CW': {'eqsl': True}})
    m = aw.worked_matrix_call('TX7X', [_qso('TX7X', '14', 'CW')])
    assert m['grid']['14']['CW'] == 'confirmed'
    assert m['confirmed'] == 1


def test_seul_cet_indicatif_compte(sans_fichiers):
    """Un QSO avec une AUTRE station sur 20 m CW ne doit pas remplir la case
    de la pédition."""
    sans_fichiers({})
    log = [_qso('W1ABC', '14', 'CW')]
    m = aw.worked_matrix_call('TX7X', log)
    assert m['grid']['14']['CW'] == 'none'
    assert m['worked'] == 0


def test_suffixe_portable_compte_pour_la_base(sans_fichiers):
    """TX7X/MM (maritime mobile) doit compter pour la pédition TX7X — même
    règle de rapprochement que history()."""
    sans_fichiers({})
    m = aw.worked_matrix_call('TX7X', [_qso('TX7X/MM', '21', 'CW')])
    assert m['grid']['21']['CW'] == 'worked'


def test_numerique_range_dans_digital(sans_fichiers):
    sans_fichiers({})
    m = aw.worked_matrix_call('TX7X', [_qso('TX7X', '14', 'FT8')])
    assert m['grid']['14']['DIGITAL'] == 'worked'
    assert m['grid']['14']['CW'] == 'none'


# ─── Bandes hors set standard ────────────────────────────────────────────────

def test_bande_travaillee_hors_standard_apparait(sans_fichiers):
    """Un créneau réellement travaillé sur une bande hors set standard (60 m)
    ne doit jamais être masqué : la colonne apparaît en plus des standard."""
    sans_fichiers({})
    m = aw.worked_matrix_call('TX7X', [_qso('TX7X', '5', 'SSB')])
    assert '5' in m['grid']
    assert m['grid']['5']['PHONE'] == 'worked'
    # et les bandes standard restent là
    assert '14' in m['grid']


def test_bandes_triees_par_frequence(sans_fichiers):
    sans_fichiers({})
    m = aw.worked_matrix_call('TX7X', [_qso('TX7X', '5', 'SSB')])
    freqs = [float(b) for b in m['bands']]
    assert freqs == sorted(freqs)
