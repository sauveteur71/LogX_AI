# -*- coding: utf-8 -*-
"""Cabrillo v3 réellement soumissible.

C'est l'argument le plus cité en faveur de N1MM : « un log presque toujours
parfait et prêt à envoyer ». Les robots de réception (CQ WW, WPX, ARRL, IARU)
refusent ou déclassent en *checklog* un fichier dont l'en-tête ou l'échange ne
colle pas — un week-end entier de trafic perdu pour une ligne.

Trois défauts corrigés, tous silencieux :

1. `CONTEST:` portait l'identifiant INTERNE (`REF_CDF_HF_SSB`) parce que la clé
   `cabrillo_name` lue par l'exportateur n'existait dans aucune des 40
   définitions de concours. Le nom officiel n'était connu que du générateur
   JAVASCRIPT, une seconde implémentation divergente aujourd'hui supprimée.
2. Le locator était ajouté à l'échange DÈS QU'IL ÉTAIT CONNU, donc aussi en HF
   où aucun règlement ne le demande : « 59 14 JN18CX » au lieu de « 59 14 ».
3. Les lignes CATEGORY-* n'étaient émises qu'en partie.
"""
import os
import re
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_export as export                          # noqa: E402
from logx_definitions import CONTEST_DEFINITIONS as C  # noqa: E402


def _qso(**kw):
    base = {'call': 'K1ABC', 'band': '14', 'mode': 'SSB',
            'date': '20261024', 'time': '1305',
            'rst_sent': '59', 'num_sent': '14',
            'rst_rcvd': '59', 'num_rcvd': '05',
            'my_locator': 'JN18CX', 'locator': 'FN42',
            'points': 3, 'operator': 'F4GLD'}
    base.update(kw)
    return base


CFG = {'callsign': 'F4GLD', 'locator': 'JN18CX', 'power_class': 'LOW'}


def _construire(contest, qsos=None, cfg=None):
    return export.build_cabrillo(qsos or [_qso()], C.get(contest, {}),
                                 dict(CFG, contest=contest, **(cfg or {})))


def _entete(texte, cle):
    m = re.search(r'^%s: (.*)$' % re.escape(cle), texte, re.M)
    return m.group(1).strip() if m else None


def _ligne_qso(texte):
    return next(l for l in texte.splitlines() if l.startswith('QSO:'))


# ─── CONTEST: le nom officiel, pas l'identifiant interne ─────────────────────

@pytest.mark.parametrize('contest,officiel', [
    ('CQ_WW_SSB', 'CQ-WW-SSB'), ('CQ_WW_CW', 'CQ-WW-CW'),
    ('CQ_WPX_SSB', 'CQ-WPX-SSB'), ('CQ_WPX_CW', 'CQ-WPX-CW'),
    ('ARRL_DX_SSB', 'ARRL-DX-SSB'), ('ARRL_DX_CW', 'ARRL-DX-CW'),
    ('ARRL_FD', 'ARRL-FD'),
    ('REF_CDF_HF_SSB', 'REF-SSB'), ('REF_CDF_HF_CW', 'REF-CW'),
    ('WAEDC_SSB', 'DARC-WAEDC-SSB'), ('WAEDC_RTTY', 'DARC-WAEDC-RTTY'),
    ('ARRL_10M', 'ARRL-10'), ('ARRL_160M', 'ARRL-160'),
])
def test_le_nom_de_concours_est_celui_attendu_par_le_robot(contest, officiel):
    assert _entete(_construire(contest), 'CONTEST') == officiel


def test_la_cle_existe_bien_dans_les_definitions():
    """L'exportateur lisait `cabrillo_name` depuis toujours ; la clé n'était
    définie nulle part. Le repli sur l'identifiant interne passait donc
    inaperçu — il ne se voyait qu'à la réception du log."""
    manquants = [c for c in ('CQ_WW_SSB', 'CQ_WPX_CW', 'ARRL_DX_SSB', 'ARRL_FD',
                             'REF_CDF_HF_SSB')
                 if not C.get(c, {}).get('cabrillo_name')]
    assert manquants == [], 'sans nom Cabrillo officiel : %s' % manquants


# ─── L'échange, au format du concours ────────────────────────────────────────

def test_le_locator_ne_part_plus_en_hf():
    """Le cœur du défaut : un CQ WW attend « 59 14 ». Le locator, connu parce
    que la station en a un, n'a rien à faire dans l'échange."""
    ligne = _ligne_qso(_construire('CQ_WW_SSB'))
    assert 'JN18CX' not in ligne and 'FN42' not in ligne
    assert '59 14' in ligne and '59 05' in ligne


def test_le_field_day_n_echange_pas_de_report():
    """Le Field Day échange classe + section, sans RST. En ajouter un est
    aussi faux que d'oublier le reste de l'échange."""
    ligne = _ligne_qso(_construire('ARRL_FD', [_qso(num_sent='3A EMA', num_rcvd='4A WNY')]))
    assert '3A EMA' in ligne and '4A WNY' in ligne
    corps = ligne.split('F4GLD', 1)[1]
    assert '59' not in corps, "le Field Day ne doit pas porter de RST : " + ligne


def test_un_concours_sans_format_declare_garde_l_ancien_comportement():
    """Les concours THF français se soumettent en EDI, pas en Cabrillo. Leur
    export d'archive ne doit pas changer sous prétexte qu'on corrige la HF."""
    ligne = _ligne_qso(_construire('REF_RPH'))
    assert 'JN18CX' in ligne and 'FN42' in ligne


def test_un_jeton_vide_ne_laisse_pas_d_espace_dans_l_echange():
    """Un numéro non saisi ne doit pas produire « 59  » : on teste l'échange
    lui-même, pas la ligne QSO — les espaces qu'on y voit sont l'alignement en
    colonnes de Cabrillo, qui est normal."""
    cdef = C['CQ_WPX_SSB']
    ech = export._cabrillo_exchange(_qso(num_sent=''), sent=True, cdef=cdef)
    assert ech == '59'
    ech2 = export._cabrillo_exchange(_qso(num_sent='001'), sent=True, cdef=cdef)
    assert ech2 == '59 001'


# ─── Les lignes CATEGORY-* ───────────────────────────────────────────────────

@pytest.mark.parametrize('cle', [
    'CATEGORY-OPERATOR', 'CATEGORY-ASSISTED', 'CATEGORY-BAND',
    'CATEGORY-MODE', 'CATEGORY-POWER', 'CATEGORY-TRANSMITTER',
])
def test_toutes_les_categories_sont_declarees(cle):
    """Elles n'étaient émises qu'en partie ; une catégorie absente fait
    classer le log d'office dans une catégorie par défaut."""
    assert _entete(_construire('CQ_WW_SSB'), cle) is not None


def test_categorie_bande_en_longueur_d_onde():
    """Vocabulaire Cabrillo : « 20M », jamais « 14 »."""
    assert _entete(_construire('CQ_WW_SSB'), 'CATEGORY-BAND') == '20M'


def test_categorie_bande_ALL_si_plusieurs_bandes():
    txt = _construire('CQ_WW_SSB', [_qso(), _qso(band='21')])
    assert _entete(txt, 'CATEGORY-BAND') == 'ALL'


@pytest.mark.parametrize('band,attendu', [
    # Vérifié contre la spec officielle WWROF (cabrillo-v3-header, section
    # CATEGORY-BAND) : au-delà de 432 (bare — jamais « 70CM »), les bandes
    # micro-ondes portent un désignateur en GHz, jamais un libellé façon ADIF
    # (« 23CM »). 24048/47088 (24G/47G) : concours THF REF (REF_NAT_THF,
    # REF_F8TD, REF_IARU_UHF) qui montent jusqu'à 47 GHz.
    ('432', '432'), ('1296', '1.2G'), ('2320', '2.3G'), ('3400', '3.4G'),
    ('5760', '5.7G'), ('10368', '10G'), ('24048', '24G'), ('47088', '47G'),
])
def test_categorie_bande_micro_ondes_format_officiel(band, attendu):
    txt = _construire('CQ_WW_SSB', [_qso(band=band)])
    assert _entete(txt, 'CATEGORY-BAND') == attendu


@pytest.mark.parametrize('modes,attendu', [
    (['SSB'], 'SSB'), (['CW'], 'CW'), (['SSB', 'CW'], 'MIXED'),
    (['FM'], 'FM'),
])
def test_categorie_mode_suit_le_log_reel(modes, attendu):
    """La catégorie doit refléter ce qui a été RÉELLEMENT trafiqué, pas ce
    qui était coché en config avant le concours. FM est une valeur
    CATEGORY-MODE Cabrillo à part entière (CW/DIGI/FM/RTTY/SSB/MIXED) : un
    log 100% FM ne doit pas retomber sur MIXED."""
    txt = _construire('CQ_WW_SSB', [_qso(mode=m) for m in modes])
    assert _entete(txt, 'CATEGORY-MODE') == attendu


# ─── LOCATION : requis pour l'IARU-HF et « tous les concours ARRL et CQ »
# (spec WWROF, section LOCATION) — DX pour toute station hors USA/Canada,
# jamais modélisé pour les concours REF/DARC ────────────────────────────────

@pytest.mark.parametrize('contest', [
    'CQ_WW_SSB', 'CQ_WW_CW', 'CQ_WPX_SSB', 'CQ_WPX_CW',
    'ARRL_DX_SSB', 'ARRL_DX_CW', 'ARRL_FD', 'ARRL_10M', 'ARRL_160M',
])
def test_location_dx_sur_les_concours_arrl_et_cq(contest):
    assert _entete(_construire(contest), 'LOCATION') == 'DX'


@pytest.mark.parametrize('contest', ['REF_CDF_HF_SSB', 'REF_CDF_HF_CW',
                                     'WAEDC_SSB', 'WAEDC_RTTY'])
def test_location_absente_hors_arrl_cq(contest):
    """REF (France) et WAEDC (DARC) : la spec ne les cite pas parmi les
    concours exigeant LOCATION — LogX AI ne modélise d'ailleurs aucune
    section ARRL, rien de fiable à y mettre."""
    assert _entete(_construire(contest), 'LOCATION') is None


def test_assisted_declare_selon_l_usage_reel_du_cluster():
    """Utiliser le cluster fait basculer de catégorie dans tous les grands
    règlements. LogX AI intègre cluster et RBN : déclarer NON-ASSISTED en dur
    serait une fausse déclaration."""
    assert _entete(_construire('CQ_WW_SSB', cfg={'cluster_spot_enabled': '1'}),
                   'CATEGORY-ASSISTED') == 'ASSISTED'
    assert _entete(_construire('CQ_WW_SSB', cfg={'rbn_enabled': '1'}),
                   'CATEGORY-ASSISTED') == 'ASSISTED'
    assert _entete(_construire('CQ_WW_SSB', cfg={'cluster_spot_enabled': '',
                                                 'rbn_enabled': '0'}),
                   'CATEGORY-ASSISTED') == 'NON-ASSISTED'


def test_multi_op_detecte_sur_les_operateurs_du_log():
    txt = _construire('CQ_WW_SSB', [_qso(operator='F4GLD'), _qso(operator='F6BC')])
    assert _entete(txt, 'CATEGORY-OPERATOR') == 'MULTI-OP'


# ─── Structure ───────────────────────────────────────────────────────────────

def test_debut_et_fin_de_log():
    txt = _construire('CQ_WW_SSB')
    assert txt.startswith('START-OF-LOG: 3.0')
    assert txt.rstrip().endswith('END-OF-LOG:')


def test_le_score_declare_est_la_somme_des_points():
    txt = _construire('CQ_WW_SSB', [_qso(points=3), _qso(points=2)])
    assert _entete(txt, 'CLAIMED-SCORE') == '5'


def test_il_ne_reste_qu_un_seul_generateur_cabrillo():
    """Le générateur JavaScript détenait seul les noms officiels mais écrivait
    l'échange sans RST et n'appliquait pas le filtrage de portée. Deux
    générateurs pour un même fichier, c'est une divergence garantie : celui du
    navigateur doit rester supprimé."""
    # EV-7 25e incrément : exportCabrillo() a été extraite vers ce fichier --
    # doit y être lue désormais, plus dans logx_logbook.js.
    with open(os.path.join(CONCOURS, 'logx_export_edi.js'), encoding='utf-8') as f:
        js = f.read()
    debut = js.index('function exportCabrillo(')
    corps = js[debut:js.index('\n}', debut)]
    assert 'START-OF-LOG' not in corps, \
        "une seconde implémentation Cabrillo est réapparue côté navigateur"
    assert '/log/export/cabrillo' in corps, \
        "le navigateur doit demander le fichier au serveur"
