# -*- coding: utf-8 -*-
"""dept_from_exchange() ne doit JAMAIS lire un code DOM à 3 chiffres (971-976)
comme un département d'échange.

Règle métier (F4GLD 23/08/2026, Coupe du REF HF / WAE) : les stations DOM/TOM
envoient un PRÉFIXE de contrée (FM, FG, FY, FR, FH, FP, FO, FK, FT), JAMAIS
971-976. Un « 971 » reçu dans un échange est donc un numéro de SÉRIE (station
étrangère / maritime mobile / WAE), pas la Guadeloupe. Avant : un série 971-976
était retourné comme département d'outre-mer, faussant la carte et gonflant le
multiplicateur REF (l'échange prime sur calldb/locator). Un vrai DOM
géographique reste détecté par locator/calldb, jamais par l'échange.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_departments as dep  # noqa: E402


def test_serie_dom_non_lue_comme_departement():
    # « 599 971 » : RST 599 + série 971 -> PAS la Guadeloupe
    assert dep.dept_from_exchange('599 971') != '971'
    assert dep.dept_from_exchange('971') != '971'
    # toute la plage DOM 971-976
    for code in ('971', '972', '973', '974', '975', '976'):
        assert dep.dept_from_exchange(code) != code, code


def test_departement_metropolitain_toujours_lu():
    assert dep.dept_from_exchange('59') == '59'
    assert dep.dept_from_exchange('599 04') == '04'      # RST + dept combiné
    assert dep.dept_from_exchange('2A') == '2A'          # Corse
