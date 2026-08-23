# -*- coding: utf-8 -*-
"""FT2 Phase 3 — table de fréquences Decodium 4.0 (profil SÉPARÉ, expérimental).

Valeurs SOURCÉES : manuel Decodium 4.0 (fournies par F4GLD 23/08). Ce sont des
conventions du projet, PAS un plan de bande IARU — jamais mêlées à la table QSY
réglementaire, et avec avertissements obligatoires.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_frequences as f


def test_metadonnees_du_profil():
    p = f.ft2_decodium()
    assert p['id'] == 'ft2_decodium_4_0'
    assert p['mode'] == 'MFSK' and p['submode'] == 'FT2'
    assert p['protocol_variant'] == 'FT2_DECODIUM'
    assert p['status'] == 'experimental'
    assert p['regulatory_status'] == 'no_dedicated_iaru_segment'
    assert p['tx_confirmation_required'] is True


def test_les_9_frequences_exactes():
    par_bande = {e['band']: e['dial_hz'] for e in f.ft2_decodium()['frequencies']}
    assert par_bande == {
        '80m': 3580000, '40m': 7080000, '30m': 10137000, '20m': 14080000,
        '17m': 18105000, '15m': 21080000, '12m': 24920000, '10m': 28180000,
        '6m': 50318000,
    }


def test_anciennes_frequences_communautaires_absentes():
    # 7.052 / 14.084 = listes FT2 concurrentes, HORS table Decodium 4.0
    hz = {e['dial_hz'] for e in f.ft2_decodium()['frequencies']}
    assert 7052000 not in hz and 14084000 not in hz


def test_avertissement_renforce_sur_17m_et_6m():
    par_bande = {e['band']: e for e in f.ft2_decodium()['frequencies']}
    assert par_bande['17m'].get('warning_fort') is True
    assert par_bande['6m'].get('warning_fort') is True


def test_avertissements_presents():
    av = f.ft2_decodium()['avertissements']
    assert isinstance(av, list) and len(av) >= 4
    assert any('expérimental' in a.lower() for a in av)
    assert any('automatique' in a.lower() for a in av)   # « aucune émission automatique »


def test_endpoint_freq_ft2_cable():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'logx_http.py'), encoding='utf-8').read()
    assert re.search(r"path == '/freq/ft2'", src)
    assert 'freqdb.ft2_decodium()' in src
