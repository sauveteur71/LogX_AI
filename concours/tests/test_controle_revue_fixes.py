# -*- coding: utf-8 -*-
"""IA-1 — correctifs de revue adversariale (branche feat/ia-controle-log).

#1 (matériel) : le plafond MAX_FINDINGS de validate_log pouvait évincer de
VRAIES erreurs quand les contrôles de cohérence (attention/info) remplissaient
la liste avant — resume_controle annonçait alors ok=True sur un log en erreur.
Correctif : _f ne jette JAMAIS un finding de niveau 'erreur', même au-delà du
plafond.

#2 : controle_rst_mode ignorait le sous-mode (FT4/JS8 logués MODE=MFSK +
SUBMODE=...). Correctif : le sous-mode est pris en compte.
"""
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
os.chdir(BASE)

import logx_validator as v   # noqa: E402
import logx_controles as ctrl  # noqa: E402


def test_resume_ne_ment_pas_ok_quand_erreurs_apres_le_plafond():
    # 210 QSO à cohérence freq/bande douteuse (attention) -> remplissent le
    # plafond (200), PUIS un QSO sans indicatif (erreur). L'erreur ne doit pas
    # être évincée, sinon resume_controle annoncerait ok=True à tort.
    log = [{'call': 'F4A%03d' % i, 'band': '14', 'freq': '7.0', 'mode': 'SSB',
            'date': '20200101', 'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59'}
           for i in range(210)]
    log.append({'call': '', 'band': '14', 'mode': 'SSB', 'date': '20200101',
                'time': '1300', 'rst_sent': '59', 'rst_rcvd': '59'})
    r = v.resume_controle(log, '', {'usage_mode': 'simple'})
    assert r['erreurs'] >= 1, r
    assert r['ok'] is False, r


def test_rst_mode_tient_compte_du_submode():
    # FT4 conforme ADIF : MODE=MFSK + SUBMODE=FT4. Un 599 oublié doit être
    # signalé (le mode effectif est FT4, pas MFSK).
    r = ctrl.controle_rst_mode({'mode': 'MFSK', 'submode': 'FT4',
                                'rst_sent': '599', 'rst_rcvd': '-10'})
    assert r is not None and r[1] == 'rst_incoherent_mode'
    # submode transporté par extra_fields (chemin d'import) : idem
    r2 = ctrl.controle_rst_mode({'mode': 'MFSK', 'extra_fields': {'SUBMODE': 'JS8'},
                                 'rst_sent': '59', 'rst_rcvd': '-10'})
    assert r2 is not None and r2[1] == 'rst_incoherent_mode'
    # MFSK sans sous-mode connu : pas de faux positif
    assert ctrl.controle_rst_mode({'mode': 'MFSK', 'rst_sent': '599'}) is None
