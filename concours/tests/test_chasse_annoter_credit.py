# -*- coding: utf-8 -*-
"""annoter_credit(spots) : câble logx_chasse_priorite sur l'index bande×mode de
logx_awards, en UN scan. On isole la logique en monkeypatchant le carnet et les
confirmations (données synthétiques) ; dx_country est fourni par le spot pour
éviter la dépendance à cty.dat (sauf un cas de lookup manquant -> inconnu)."""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_awards as aw  # noqa: E402
import logx_chasse_priorite as cp  # noqa: E402


# Carnet : Japon travaillé en 20 m DIGITAL et 40 m DIGITAL. Aucune confirmation.
_LOG = [
    {'dxcc_country': 'Japan', 'band': '14', 'mode': 'FT8', 'call': 'JA1AAA'},
    {'dxcc_country': 'Japan', 'band': '7', 'mode': 'FT8', 'call': 'JA1BBB'},
]


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(aw, 'collect_all_qsos', lambda shared_log=None: list(_LOG))
    monkeypatch.setattr(aw, '_load_confirmations', lambda: {})   # rien de confirmé LoTW


def _spot(band, mode, pays='Japan', call='JA1ZZZ'):
    return {'call': call, 'band': band, 'mode': mode, 'scoring': {'dx_country': pays}}


def test_creneau_travaille_non_confirme():
    s = _spot('14', 'FT8')                      # Japon 20 m DIGITAL : déjà loggé, pas confirmé
    aw.annoter_credit([s])
    assert s['credit_classe'] == cp.CLASSE_NEEDED_CONFIRM
    assert s['credit_score'] == 200


def test_nouveau_mode():
    s = _spot('14', 'CW')                        # 20 m fait en DIGITAL, jamais CW
    aw.annoter_credit([s])
    assert s['credit_classe'] == cp.CLASSE_NEW_MODE and s['credit_score'] == 500


def test_nouvelle_bande():
    s = _spot('21', 'CW')                        # Japon fait, mais jamais 15 m
    aw.annoter_credit([s])
    assert s['credit_classe'] == cp.CLASSE_NEW_BAND and s['credit_score'] == 600


def test_atno_entite_absente():
    s = _spot('14', 'CW', pays='France')         # France jamais travaillée
    aw.annoter_credit([s])
    assert s['credit_classe'] == cp.CLASSE_ATNO and s['credit_score'] == 1000


def test_inconnu_si_entite_non_resolue():
    s = {'call': '', 'band': '14', 'mode': 'CW', 'scoring': {}}   # pas de dx_country, call vide
    aw.annoter_credit([s])
    assert s['credit_classe'] == cp.CLASSE_INCONNU


def test_profil_objectif_desactive_annule_le_credit():
    s = _spot('14', 'CW', pays='France')
    aw.annoter_credit([s], objectifs={'dxcc': False})
    assert s['credit_classe'] == cp.CLASSE_ATNO       # classe inchangée
    assert s['credit_score'] == 0                     # mais crédit annulé


def test_raison_presente():
    s = _spot('21', 'CW')
    aw.annoter_credit([s])
    assert s['credit_raison'] and 'bande' in s['credit_raison'].lower()


# ─── crédit carré VHF/UHF (new_grid) ───────────────────────────────────────

# Carnet : Japon travaillé sur 6 m CW (créneau déjà fait mais non confirmé ->
# DXCC = needed_confirm, score 200) et un carré JN39 travaillé sur 2 m.
_LOG_VHF = [
    {'dxcc_country': 'Japan', 'band': '50', 'mode': 'CW', 'call': 'JA1AAA', 'locator': 'PM95'},
    {'dxcc_country': 'Italy', 'band': '144', 'mode': 'SSB', 'call': 'IK1AAA', 'locator': 'JN39'},
]


def _spot_loc(band, mode, loc, pays='Japan', call='JA1ZZZ'):
    return {'call': call, 'band': band, 'mode': mode, 'locator': loc,
            'scoring': {'dx_country': pays}}


def test_carre_vhf_neuf_donne_new_grid(monkeypatch):
    monkeypatch.setattr(aw, 'collect_all_qsos', lambda shared_log=None: list(_LOG_VHF))
    # 6 m CW, entité Japon déjà faite sur ce créneau (DXCC=needed_confirm 200),
    # mais carré JO01 jamais travaillé -> le crédit carré (450) l'emporte.
    s = _spot_loc('50', 'CW', 'JO01')
    aw.annoter_credit([s])
    assert s['credit_classe'] == cp.CLASSE_NEW_GRID
    assert s['credit_score'] == 450


def test_carre_deja_travaille_reste_credit_dxcc(monkeypatch):
    monkeypatch.setattr(aw, 'collect_all_qsos', lambda shared_log=None: list(_LOG_VHF))
    # même créneau, mais carré PM95 déjà au carnet -> pas de new_grid,
    # on garde le crédit DXCC (needed_confirm, 200).
    s = _spot_loc('50', 'CW', 'PM95')
    aw.annoter_credit([s])
    assert s['credit_classe'] == cp.CLASSE_NEEDED_CONFIRM
    assert s['credit_score'] == 200


def test_carre_neuf_mais_bande_hf_pas_de_new_grid(monkeypatch):
    monkeypatch.setattr(aw, 'collect_all_qsos', lambda shared_log=None: list(_LOG_VHF))
    # 20 m (HF) : le crédit carré ne s'applique pas sous 30 MHz.
    s = _spot_loc('14', 'CW', 'JO01')
    aw.annoter_credit([s])
    assert s['credit_classe'] != cp.CLASSE_NEW_GRID


def test_atno_vhf_prime_sur_new_grid(monkeypatch):
    monkeypatch.setattr(aw, 'collect_all_qsos', lambda shared_log=None: list(_LOG_VHF))
    # entité jamais travaillée sur 6 m + carré neuf : ATNO (1000) > new_grid (450).
    s = _spot_loc('50', 'CW', 'JO01', pays='Brazil', call='PY2ZZZ')
    aw.annoter_credit([s])
    assert s['credit_classe'] == cp.CLASSE_ATNO
    assert s['credit_score'] == 1000


def test_locator_factice_ignore(monkeypatch):
    monkeypatch.setattr(aw, 'collect_all_qsos', lambda shared_log=None: list(_LOG_VHF))
    s = _spot_loc('50', 'CW', 'AA00')            # carré factice (repli 0,0)
    aw.annoter_credit([s])
    assert s['credit_classe'] != cp.CLASSE_NEW_GRID


def test_objectif_vucc_desactive_pas_de_new_grid(monkeypatch):
    monkeypatch.setattr(aw, 'collect_all_qsos', lambda shared_log=None: list(_LOG_VHF))
    s = _spot_loc('50', 'CW', 'JO01')
    aw.annoter_credit([s], objectifs={'vucc': False})
    # new_grid score 0 -> ne remonte pas au-dessus du DXCC (needed_confirm 200)
    assert s['credit_classe'] == cp.CLASSE_NEEDED_CONFIRM


def test_un_seul_scan_pour_toute_la_liste(monkeypatch):
    # collect_all_qsos ne doit être appelé qu'UNE fois quel que soit le nb de spots
    n = {'c': 0}
    monkeypatch.setattr(aw, 'collect_all_qsos',
                        lambda shared_log=None: (n.__setitem__('c', n['c'] + 1), list(_LOG))[1])
    spots = [_spot('14', 'CW'), _spot('21', 'CW'), _spot('7', 'CW')]
    aw.annoter_credit(spots)
    assert n['c'] == 1
