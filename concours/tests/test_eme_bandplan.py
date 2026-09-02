# -*- coding: utf-8 -*-
"""Le plan de bandes EME : bandes attendues, RF plausibles, transverter cohérent."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_eme_bandplan as bp   # noqa: E402

BANDES = ['50', '144', '432', '1296', '2320', '3400', '5760', '10368', '24048', '47088']


def test_toutes_les_bandes_EME_sont_couvertes():
    for b in BANDES:
        assert b in bp.EME_ACTIVITE, b
        assert bp.centre_rf_mhz(b) is not None


def test_la_RF_est_dans_la_bande():
    # La RF d'activité tombe dans ±20 % de la fréquence nominale de la bande.
    for b in BANDES:
        rf = bp.centre_rf_mhz(b)
        nominal = float(b)
        assert 0.8 * nominal <= rf <= 1.2 * nominal, (b, rf)


def test_au_dessus_de_1296_c_est_du_transverter():
    for b in ['2320', '3400', '5760', '10368', '24048', '47088']:
        assert bp.est_transverter(b) is True, b
    assert bp.est_transverter('144') is False
    assert bp.est_transverter('432') is False


def test_bande_inconnue_rend_None():
    assert bp.centre_rf_mhz('7') is None
    assert bp.est_transverter('7') is False
