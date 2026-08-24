# -*- coding: utf-8 -*-
"""Sous-chantier B, lot 5 — symétriser l'IMPORT ADIF avec l'export.

L'export (lots 1-3) écrit NAME/QTH/COMMENT/DISTANCE/PROP_MODE/FREQ/TIME_OFF, les
clés de la refonte de saisie (TX_PWR/FREQ_RX/CQZ…) et les tags multi-références
(MY_SOTA_REF/POTA_REF…). Le parseur d'import ne mappait PAS ces tags vers les
clés internes : ils atterrissaient dans extra_fields, MAIS l'export les liste
désormais dans _ADIF_STD_TAGS (anti-duplication) donc il les SAUTAIT à la
réexportation tout en lisant une clé interne restée vide -> perte au 2e export.

Correctif : l'import mappe ces tags vers les clés internes (name/qth/comment/
dist/prop_mode/freq/time_off/tx_pwr/…) et reconstruit my_refs/refs depuis les
tags dédiés + le générique SIG. Aller-retour fidèle.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_export as export        # noqa: E402
import logx_import as imp            # noqa: E402


def _un(adif_text):
    qsos, errors = imp.parse_adif_to_qsos(adif_text)
    assert not errors, errors
    assert len(qsos) == 1, qsos
    return qsos[0]


# ─── Scalaires : tag ADIF -> clé interne (plus dans extra_fields) ────────────

def test_scalaires_mappes_vers_cles_internes():
    adif = ("<CALL:5>F4ABC<BAND:3>20m<MODE:3>SSB<QSO_DATE:8>20260824<TIME_ON:4>1215"
            "<NAME:4>Jean<QTH:4>Lyon<COMMENT:5>merci<DISTANCE:3>412<PROP_MODE:2>TR"
            "<FREQ:6>14.075<TIME_OFF:6>121545<EOR>")
    q = _un(adif)
    assert q['name'] == 'Jean'
    assert q['qth'] == 'Lyon'
    assert q['comment'] == 'merci'
    assert q['dist'] == '412'
    assert q['prop_mode'] == 'TR'
    assert q['freq'] == '14.075'
    assert q['time_off'] == '121545'
    # et PAS restés dans extra_fields (sinon double émission / clé interne vide)
    extra = q.get('extra_fields', {})
    for tag in ('NAME', 'QTH', 'COMMENT', 'DISTANCE', 'PROP_MODE', 'FREQ', 'TIME_OFF'):
        assert tag not in extra, tag


def test_cles_saisie_lot2_mappees():
    adif = ("<CALL:5>F4ABC<BAND:3>20m<MODE:3>SSB<QSO_DATE:8>20260824<TIME_ON:4>1215"
            "<TX_PWR:2>20<FREQ_RX:6>14.080<CQZ:2>14<ITUZ:2>27<CNTY:5>Rhone"
            "<EMAIL:6>a@b.fr<QSL_VIA:6>BUREAU<ANT_AZ:2>92<EOR>")
    q = _un(adif)
    assert q['tx_pwr'] == '20'
    assert q['freq_rx'] == '14.080'
    assert q['cqz'] == '14'
    assert q['ituz'] == '27'
    assert q['cnty'] == 'Rhone'
    assert q['email'] == 'a@b.fr'
    assert q['qsl_via'] == 'BUREAU'
    assert q['ant_az'] == '92'


# ─── Multi-références reconstruites ──────────────────────────────────────────

def test_two_fer_reconstruit_my_refs():
    adif = ("<CALL:5>F4ABC<BAND:3>20m<MODE:3>SSB<QSO_DATE:8>20260824<TIME_ON:4>1215"
            "<MY_SIG:4>SOTA<MY_SIG_INFO:8>F/AB-123"
            "<MY_SOTA_REF:8>F/AB-123<MY_POTA_REF:7>FR-0123<EOR>")
    q = _un(adif)
    progs = {r['program']: r['ref'] for r in q.get('my_refs', [])}
    assert progs.get('SOTA') == 'F/AB-123'
    assert progs.get('POTA') == 'FR-0123'


def test_ref_correspondant_reconstruit_refs():
    adif = ("<CALL:5>F4ABC<BAND:3>20m<MODE:3>SSB<QSO_DATE:8>20260824<TIME_ON:4>1215"
            "<POTA_REF:7>FR-0456<EOR>")
    q = _un(adif)
    progs = {r['program']: r['ref'] for r in q.get('refs', [])}
    assert progs.get('POTA') == 'FR-0456'


def test_sig_generique_sans_tag_dedie_reconstruit():
    # WCA n'a pas de tag dédié : il arrive via MY_SIG=WCA -> my_refs le porte.
    adif = ("<CALL:5>F4ABC<BAND:3>20m<MODE:3>SSB<QSO_DATE:8>20260824<TIME_ON:4>1215"
            "<MY_SIG:3>WCA<MY_SIG_INFO:8>DL-00001<EOR>")
    q = _un(adif)
    progs = {r['program']: r['ref'] for r in q.get('my_refs', [])}
    assert progs.get('WCA') == 'DL-00001'


# ─── Aller-retour complet (la vraie preuve de symétrie) ──────────────────────

def test_aller_retour_export_import_export_stable():
    q0 = {'call': 'F4ABC', 'band': '20', 'mode': 'SSB', 'date': '20260824',
          'time': '1215', 'rst_sent': '59', 'rst_rcvd': '59',
          'name': 'Jean', 'qth': 'Lyon', 'comment': 'merci', 'dist': '412',
          'freq': '14.075', 'time_off': '121545', 'tx_pwr': '20',
          'my_refs': [{'program': 'SOTA', 'ref': 'F/AB-123'},
                      {'program': 'POTA', 'ref': 'FR-0123'}]}
    adif1 = export.build_adif([q0], {})
    q1 = _un(adif1)
    # les champs ont survécu à l'import
    assert q1['name'] == 'Jean' and q1['comment'] == 'merci' and q1['dist'] == '412'
    assert q1['tx_pwr'] == '20' and q1['time_off'] == '121545'
    progs = {r['program']: r['ref'] for r in q1.get('my_refs', [])}
    assert progs.get('SOTA') == 'F/AB-123' and progs.get('POTA') == 'FR-0123'
    # 2e export : les mêmes tags ressortent (rien perdu au passage extra_fields)
    adif2 = export.build_adif([q1], {}).upper()
    assert '<NAME:4>JEAN' in adif2
    assert '<MY_SOTA_REF:8>F/AB-123' in adif2
    assert '<MY_POTA_REF:7>FR-0123' in adif2
