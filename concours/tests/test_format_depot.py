# -*- coding: utf-8 -*-
"""Le format de dépôt vient du RÈGLEMENT, plus d'une liste écrite à la main.

LE DÉFAUT, mesuré sur la base livrée le 01/08/2026. Le logbook routait l'export
sur `HF_CONTESTS`, DOUZE identifiants codés en dur, alors que VINGT-SIX
définitions déclarent `log_format: 'CABRILLO'`. Conséquence : dix-sept concours
Cabrillo tombaient dans la branche EDI et l'opérateur n'obtenait AUCUN fichier,
juste « Aucun QSO VHF/UHF à exporter » — au moment du dépôt, veille de date
limite. Parmi eux : WAEDC CW/SSB/RTTY, ARRL 10 m et 160 m, Russian DX, EU HF
Championship, All Asian, Stew Perry, UBA, SP, HA, REF 160 m, les deux UFT
Challenge. Trois identifiants de cette liste n'existaient même pas
(IARU_HF, WAE_CW, WAE_SSB — les vrais sont WAEDC_*).

MÊME DÉFAUT, MÊME FICHIER, pour l'affichage des statistiques : `VHF_CONTESTS`
comptait neuf identifiants dont CINQ inexistants, et en oubliait sept bien
réels — dont REF_CDF_THF, le Championnat de France THF, et IARU_MARCONI. Un
opérateur du CDF THF voyait des statistiques HF pendant tout le concours.

CE QUE CES TESTS EMPÊCHENT : qu'une liste d'identifiants réapparaisse dans le
client. La règle est que le format vient de la définition du concours, servie
par /data/calendar, et que le repli se déduit des bandes RÉELLEMENT présentes
dans le log — jamais d'un identifiant à tenir à jour.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

from logx_definitions import CONTEST_DEFINITIONS   # noqa: E402

JS = os.path.join(CONCOURS, 'logx_logbook.js')
with open(JS, encoding='utf-8') as f:
    SRC = f.read()

# Les identifiants des deux listes fautives, tels qu'ils étaient écrits.
ANCIENNE_LISTE_HF = ['ARRL_DX_SSB', 'CQ_WW_SSB', 'CQ_WPX_CW', 'REF_CDF_HF_SSB']
ANCIENNE_LISTE_VHF = ['REF_RPH', 'IARU_VHF', 'DARC_VHF']


def _code_sans_commentaires():
    """Les commentaires CITENT les anciennes listes pour expliquer le défaut :
    il faut donc chercher dans le code seul, sinon le test se déclenche sur sa
    propre documentation."""
    out = []
    for ligne in SRC.splitlines():
        nu = ligne.strip()
        if nu.startswith('//') or nu.startswith('*') or nu.startswith('/*'):
            continue
        out.append(ligne.split('//')[0])
    return '\n'.join(out)


def test_aucune_liste_d_identifiants_de_concours_ne_pilote_l_export():
    code = _code_sans_commentaires()
    for interdit in ('HF_CONTESTS', 'VHF_CONTESTS'):
        assert interdit not in code, (
            '%s est de retour dans le code : une liste d\'identifiants tenue '
            'à la main se périme et a déjà fait perdre son fichier de dépôt à '
            'dix-sept concours' % interdit)


def test_le_format_est_lu_dans_la_definition_du_concours():
    code = _code_sans_commentaires()
    assert 'contestDepotDefs' in code
    assert 'function formatDepot(' in code
    assert 'log_format' in code, (
        'le champ qui porte le format du règlement doit être lu')


def test_le_repli_se_deduit_des_bandes_du_log_pas_d_un_identifiant():
    code = _code_sans_commentaires()
    assert 'function estConcoursThf(' in code
    assert 'BANDES_THF' in code
    assert 'estConcoursThf()' in code


def test_les_statistiques_ne_dependent_plus_d_un_identifiant():
    code = _code_sans_commentaires()
    assert 'const isVHF = estConcoursThf()' in code, (
        "l'affichage 144/432 doit suivre le log, pas une liste de concours")


# ─── Les données qui ont révélé le défaut, figées pour qu'il ne revienne pas ──

def test_la_base_declare_bien_plus_de_cabrillo_que_l_ancienne_liste():
    """Si un jour ce compte retombe à douze, c'est que quelqu'un a supprimé
    des définitions — pas que le défaut était imaginaire."""
    cab = [k for k, d in CONTEST_DEFINITIONS.items()
           if d.get('log_format') == 'CABRILLO']
    assert len(cab) >= 26, (
        '%d concours Cabrillo ; l\'ancienne liste codée en dur en connaissait '
        'douze' % len(cab))


@pytest.mark.parametrize('cid', [
    'WAEDC_CW', 'WAEDC_SSB', 'WAEDC_RTTY', 'ARRL_10M', 'ARRL_160M',
    'RUSSIAN_DX', 'EU_HF_CHAMP', 'ALL_ASIAN_CW', 'STEW_PERRY', 'REF_160M',
])
def test_les_concours_qui_n_obtenaient_aucun_fichier_sont_bien_en_cabrillo(cid):
    """Ces dix-là faisaient partie des dix-sept oubliés. Le test vérifie que
    la définition dit bien Cabrillo — donc que le nouveau routage, qui la lit,
    leur donnera leur fichier."""
    d = CONTEST_DEFINITIONS.get(cid)
    assert d is not None, '%s a disparu de la base' % cid
    assert d.get('log_format') == 'CABRILLO'


@pytest.mark.parametrize('fantome', ['IARU_HF', 'WAE_CW', 'WAE_SSB',
                                     'DARC_VHF', 'REF_CCD', 'EU_VHF',
                                     'OARC_VHF', 'REF_VHF_UHF_FR'])
def test_les_identifiants_fantomes_n_existent_toujours_pas(fantome):
    """Huit identifiants des deux listes ne correspondaient à AUCUN concours.
    C'est le symptôme le plus net d'une liste tenue à la main : elle diverge
    dans les deux sens à la fois."""
    assert fantome not in CONTEST_DEFINITIONS


@pytest.mark.parametrize('cid', ['REF_CDF_THF', 'REF_NAT_THF', 'IARU_MARCONI'])
def test_les_concours_THF_oublies_ont_bien_des_bandes_THF(cid):
    """Ils étaient absents de VHF_CONTESTS et affichaient donc des statistiques
    HF. La déduction par les bandes du log les couvre désormais."""
    d = CONTEST_DEFINITIONS.get(cid)
    assert d is not None, '%s a disparu de la base' % cid
    bandes = {str(b) for b in d.get('bands', [])}
    assert bandes & {'144', '432', '1296', '2320', '5760', '10368'}
