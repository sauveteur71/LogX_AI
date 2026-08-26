# -*- coding: utf-8 -*-
"""Band map — rafraîchir un spot doit rendre la réponse COHÉRENTE avec l'état
stocké (audit STRATE-3 logx_bandmap.py:124). _cle identifie un spot au kHz
près : renoter DL1ABC à 14025,4 alors qu'il était noté à 14025,1 tombe sur le
même spot et rafraîchit son horodatage — mais l'ancien code laissait
s['freq_khz']=14025,1 tout en RENVOYANT freq_khz=14025,4. La liste affichait
donc l'ancienne fréquence pendant que la réponse annonçait la nouvelle."""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_bandmap as bm  # noqa: E402


@pytest.fixture(autouse=True)
def dossier_isole(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(bm, '_spots', [])
    monkeypatch.setattr(bm, '_charge', False)
    return tmp_path


def _spot(call, maintenant):
    for s in bm.spots(maintenant=maintenant):
        if s.get('call') == call:
            return s
    return None


def test_le_rafraichissement_met_a_jour_la_frequence_stockee():
    bm.ajouter('DL1ABC', 14025.1, maintenant=1000)
    r = bm.ajouter('DL1ABC', 14025.4, maintenant=1001)   # même kHz -> rafraîchit
    assert r['rafraichi'] is True
    # La fréquence renvoyée par la réponse DOIT être celle stockée/affichée.
    assert r['freq_khz'] == _spot('DL1ABC', 1001)['freq_khz'], \
        "réponse incohérente : freq renvoyée != freq stockée"


def test_pas_de_ligne_en_double_apres_rafraichissement():
    bm.ajouter('DL1ABC', 14025.1, maintenant=1000)
    bm.ajouter('DL1ABC', 14025.4, maintenant=1001)
    calls = [s for s in bm.spots(maintenant=1001) if s.get('call') == 'DL1ABC']
    assert len(calls) == 1, "le rafraîchissement a créé un doublon au lieu de fusionner"
