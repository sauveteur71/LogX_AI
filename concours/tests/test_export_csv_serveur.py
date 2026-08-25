# -*- coding: utf-8 -*-
"""Export CSV SERVEUR (build_csv) — jumeau du CSV client (logx_export_adif.js
_csvBaseRow/_CSV_HEADER). Jusqu'ici seuls ADIF et Cabrillo existaient côté
serveur ; le CSV n'était que client (bouton). build_csv complète l'export
serveur (archive/endpoint), avec échappement RFC 4180."""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_export as export   # noqa: E402


def test_entete_et_une_ligne_par_qso():
    qsos = [{'call': 'f4abc', 'date': '20260101', 'time': '1200', 'band': '14',
             'mode': 'SSB', 'rst_sent': '59', 'rst_rcvd': '59', 'num_sent': '001',
             'num_rcvd': '014', 'locator': 'JN18DT', 'dist': 412, 'points': 3,
             'operator': ''},
            {'call': 'lz2lp', 'date': '20260101', 'time': '1205', 'band': '14',
             'mode': 'CW', 'rst_sent': '599', 'rst_rcvd': '599'}]
    csv = export.build_csv(qsos, {})
    lignes = csv.strip().split('\n')
    assert lignes[0].startswith('N°,Date,Heure,Indicatif,Bande,Mode')
    assert len(lignes) == 3                         # entête + 2 QSO
    assert lignes[1].startswith('1,20260101,1200,F4ABC,14,SSB')  # call en MAJ, n° 1
    assert lignes[2].startswith('2,20260101,1205,LZ2LP,14,CW')


def test_echappement_rfc4180():
    # un champ contenant une virgule/guillemet est entouré de guillemets
    # (guillemets internes doublés) -> ne décale pas les colonnes.
    qsos = [{'call': 'F4ABC', 'date': '20260101', 'time': '1200', 'band': '14',
             'mode': 'SSB', 'operator': 'JEAN, "JO"'}]
    csv = export.build_csv(qsos, {})
    assert '"JEAN, ""JO"""' in csv, csv


def test_qso_vide_ne_plante_pas():
    csv = export.build_csv([{}], {})
    assert csv.count('\n') >= 2                      # entête + 1 ligne
