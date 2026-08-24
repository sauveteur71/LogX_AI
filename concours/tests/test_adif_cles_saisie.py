# -*- coding: utf-8 -*-
"""Sous-chantier B, lot 2 — les clés posées par la refonte de saisie (A) sont
émises en ADIF par les deux générateurs (serveur build_adif, client
buildAdifText). Sans ça, la donnée était stockée mais absente du fichier remis.
operating_location n'a pas de tag ADIF standard -> APP_LOGX_OPERATING."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_export as export

NOUVELLES = ['TX_PWR', 'FREQ_RX', 'CQZ', 'ITUZ', 'CNTY', 'EMAIL', 'QSL_VIA',
             'ANT_AZ', 'TIME_OFF', 'QSL_SENT', 'LOTW_QSL_SENT', 'EQSL_QSL_SENT',
             'APP_LOGX_OPERATING']


def test_build_adif_serveur_emet_les_cles_de_saisie():
    q = {'call': 'F4ABC', 'date': '20260824', 'time': '1215', 'band': '20',
         'mode': 'SSB', 'rst_sent': '59', 'rst_rcvd': '59',
         'tx_pwr': 20, 'freq_rx': '14.075', 'cqz': '14', 'ituz': '27',
         'cnty': 'Rhone', 'email': 'a@b.fr', 'qsl_via': 'BUREAU', 'ant_az': 92,
         'time_off': '121545', 'qsl_sent': 'Y', 'lotw_qsl_sent': 'N',
         'eqsl_qsl_sent': 'Y', 'operating_location': 'PORTABLE'}
    adif = export.build_adif([q], {}).upper()   # ADIF insensible à la casse
    for tag in NOUVELLES:
        assert ('<%s:' % tag) in adif, tag


def test_build_adif_omet_une_cle_absente():
    # champ absent -> tag absent (pas de <TX_PWR:0> parasite).
    q = {'call': 'F4ABC', 'date': '20260824', 'time': '1215', 'band': '20', 'mode': 'SSB'}
    adif = export.build_adif([q], {}).upper()
    assert '<TX_PWR:' not in adif and '<EMAIL:' not in adif


def test_buildadiftext_client_emet_les_cles():
    js = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'logx_export_adif.js'), encoding='utf-8').read()
    i = js.index('function buildAdifText')
    body = js[i:js.index('\n}', i)]
    for tag in NOUVELLES:
        assert ("adifField('%s'" % tag) in body, tag
