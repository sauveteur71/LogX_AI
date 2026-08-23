# -*- coding: utf-8 -*-
"""Intégrité des données à l'import ADIF (axe « carnet perdu »).

1. TIME_OFF était listé dans _TAGS_MAPPES (donc exclu de extra_fields) SANS
   qu'aucune clé interne ne le reçoive -> détruit en silence, contredisant
   l'aller-retour import/export fidèle. Correctif : sort de _TAGS_MAPPES ->
   préservé dans extra_fields (comme FREQ).

2. _dedup_key incluait date+heure, mais _clean_date rend '' pour une date
   absente/malformée et _adif_time rend '0000' sans TIME_ON : deux QSO réels
   DISTINCTS de même call/band/mode mais sans date produisaient une clé
   identique -> le 2e était compté doublon et PERDU en silence à l'import.
   Correctif : clé None quand la date est vide -> jamais considéré doublon.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_import as imp  # noqa: E402


def test_time_off_preserve_dans_extra_fields():
    adif = ("<CALL:5>F5ABC <BAND:3>20m <MODE:2>CW <QSO_DATE:8>20260101 "
            "<TIME_ON:6>101500 <TIME_OFF:6>103000 <EOR>")
    qsos, errors = imp.parse_adif_to_qsos(adif)
    assert len(qsos) == 1, (qsos, errors)
    assert qsos[0].get('extra_fields', {}).get('TIME_OFF') == '103000', qsos[0]


def test_deux_qso_sans_date_ne_fusionnent_pas():
    # deux records de même call/band/mode SANS QSO_DATE ni TIME_ON
    adif = ("<CALL:5>F5ABC <BAND:3>20m <MODE:2>CW <EOR>"
            "<CALL:5>F5ABC <BAND:3>20m <MODE:2>CW <EOR>")
    qsos, errors = imp.parse_adif_to_qsos(adif)
    assert len(qsos) == 2, (qsos, errors)
    new, _ = imp.commit_import(adif, [])
    assert len(new) == 2, "deux QSO 'date inconnue' distincts ne doivent pas être fusionnés"
    prev = imp.preview_import(adif, [])
    assert prev['new'] == 2 and prev['duplicates'] == 0, prev


def test_vrai_doublon_date_connue_toujours_dedupe():
    # avec une date connue, le dédoublonnage normal fonctionne toujours
    adif = ("<CALL:5>F5ABC <BAND:3>20m <MODE:2>CW <QSO_DATE:8>20260101 <TIME_ON:4>1015 <EOR>"
            "<CALL:5>F5ABC <BAND:3>20m <MODE:2>CW <QSO_DATE:8>20260101 <TIME_ON:4>1015 <EOR>")
    new, _ = imp.commit_import(adif, [])
    assert len(new) == 1, "deux QSO identiques à date/heure connues restent un doublon"
