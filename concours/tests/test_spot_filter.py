# -*- coding: utf-8 -*-
"""Filtrage des spots par concours (bandes/modes/distance plausible) —
cas réels du Bol d'Or QRP 18/07/2026 : spots 50 MHz/HF proposés à l'agent,
FT8 144.174 en concours NO-DIGI, FK8HA « à 17 014 km en 144 MHz »."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from radiocontest_scoring import (filter_spots_for_contest, _is_digital_freq,
                                  _MAX_PLAUSIBLE_KM)


def _spot(band, freq='', dist=500, call='F1ABC'):
    return {'call': call, 'band': band, 'freq': freq, 'dist_km': dist}


def test_bandes_hors_concours_ecartees():
    """REF_QRP (144/432/...) : les spots 50 MHz et HF ne passent pas."""
    spots = [_spot('144'), _spot('50'), _spot('14'), _spot('432'), _spot('28')]
    kept, dropped = filter_spots_for_contest(spots, 'REF_QRP')
    assert [s['band'] for s in kept] == ['144', '432']
    assert dropped['hors_bande'] == 3


def test_ft8_ecarte_si_concours_sans_numerique():
    """REF_QRP = SSB/CW : un spot dans la fenêtre FT8 144.174 est écarté."""
    spots = [_spot('144', freq='144174'), _spot('144', freq='144300')]
    kept, dropped = filter_spots_for_contest(spots, 'REF_QRP')
    assert len(kept) == 1 and kept[0]['freq'] == '144300'
    assert dropped['numerique'] == 1


def test_ft8_garde_si_concours_accepte_numerique():
    """Un concours 'all modes' (SOTA) garde les spots FT8."""
    spots = [_spot('144', freq='144174')]
    kept, dropped = filter_spots_for_contest(spots, 'SOTA')
    assert len(kept) == 1
    assert dropped['numerique'] == 0


def test_distance_impossible_ecartee():
    """FK8HA à 17 014 km ne peut pas être un contact 144 MHz terrestre."""
    spots = [_spot('144', dist=17014, call='FK8HA'),
             _spot('144', dist=900, call='DL1AB')]
    kept, dropped = filter_spots_for_contest(spots, 'REF_QRP')
    assert [s['call'] for s in kept] == ['DL1AB']
    assert dropped['distance'] == 1


def test_distance_zero_conservee():
    """dist_km=0 (position inconnue) n'est pas un motif d'exclusion."""
    kept, _ = filter_spots_for_contest([_spot('144', dist=0)], 'REF_QRP')
    assert len(kept) == 1


def test_concours_inconnu_ne_filtre_pas_les_bandes():
    """Concours hors base (CUSTOM) : pas de définition → tout passe."""
    spots = [_spot('144'), _spot('14', dist=8000)]
    kept, dropped = filter_spots_for_contest(spots, 'CUSTOM')
    assert len(kept) == 2 and sum(dropped.values()) == 0


def test_fenetres_digitales():
    assert _is_digital_freq('144174')
    assert _is_digital_freq('14074')
    assert _is_digital_freq('144.176')      # MHz
    assert not _is_digital_freq('144300')   # SSB 2m
    assert not _is_digital_freq('14032')    # CW 20m
    assert not _is_digital_freq('')


def test_caps_couvrent_les_bandes_vhf_plus():
    for b in ('50', '144', '432', '1296'):
        assert b in _MAX_PLAUSIBLE_KM


def test_coherence_frequence_bande():
    """Un spot 50.125 MHz étiqueté « 144 » est un déchet de parsing — écarté
    (cas réel : il apparaissait sur 144 ET 432 au Bol d'Or QRP)."""
    spots = [_spot('144', freq='50.125'),   # freq dit 50 → incohérent
             _spot('432', freq='50.125'),   # même déchet dupliqué
             _spot('144', freq='144300'),   # cohérent
             _spot('144', freq='')]         # pas de freq → pas de contrôle
    kept, dropped = filter_spots_for_contest(spots, 'REF_QRP')
    assert len(kept) == 2
    assert dropped['freq_bande'] == 2
