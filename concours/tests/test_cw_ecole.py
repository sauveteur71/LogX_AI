# -*- coding: utf-8 -*-
"""L'école de CW branchée sur la bande de ce soir.

CE QUI LA DISTINGUE d'un entraîneur morse ordinaire : la matière vient du
poste. Les indicatifs sont ceux de l'index de l'opérateur (log, archives, base
d'indicatifs, MASTER.SCP s'il l'a importé) et l'échange est celui que le
concours choisi demande VRAIMENT. Ces tests vérifient donc surtout la
JUSTESSE DE L'ÉCHANGE : s'entraîner sur un échange plus court que le vrai est
pire que ne pas s'entraîner du tout.

DÉFAUT TROUVÉ EN VÉRIFIANT SUR LA VRAIE BASE, avant toute mise en service :
la première version testait `exchange_wants(cdef)['num']` — or cette fonction
ne renvoie QUE `dept` et `locator`, elle n'a jamais porté de clé `num`. Le
test était donc toujours faux et le numéro de série n'était JAMAIS envoyé,
pour les vingt-quatre concours qui en demandent un, dont le Championnat de
France THF. Le numéro se lit dans le texte de l'échange, seule source qui le
mentionne.
"""
import os
import random
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_cw_ecole as ec                        # noqa: E402
from logx_definitions import CONTEST_DEFINITIONS  # noqa: E402

INDEX = {
    'F4GLD':   {'qso_count': 12}, 'DL2ABC': {'qso_count': 5},
    'G3XYZ':   {'qso_count': 3},  'K1ABC':  {'qso_count': 1},
    'JA1QRS':  {'qso_count': 0},  'VK3DEF': {'qso_count': 0},
    'EA5TUV':  {'qso_count': 0},  'F6KOP/P': {'qso_count': 2},
    'PAS_UN_INDICATIF': {'qso_count': 9}, '': {'qso_count': 1},
    '12345':   {'qso_count': 4},
}


# ─── L'échange : le cœur de l'affaire ───────────────────────────────────────

@pytest.mark.parametrize('cid, attendu', [
    ('REF_CDF_THF',   '599 007 JN15XC'),   # report + n° série + locator
    ('REF_RPH',       '599 007 JN15XC'),
    ('REF_CDF_HF_CW', '599 007 43'),       # report + n° série + département
    ('CQ_WPX_CW',     '599 007'),          # report + n° série seul
    ('CQ_WW_SSB',     '599 14'),           # report + zone CQ
])
def test_l_echange_est_celui_que_le_concours_demande(cid, attendu):
    cdef = CONTEST_DEFINITIONS.get(cid)
    assert cdef is not None, '%s a disparu de la base' % cid
    assert ec.echange_attendu(cdef, 7, 'JN15XC', '43', 14) == attendu


def test_le_numero_de_serie_n_est_PAS_oublie_sur_la_vraie_base():
    """Le défaut d'origine. Si ce compte tombe à zéro, c'est que la détection
    du numéro est de nouveau cassée — et l'entraînement redeviendrait plus
    facile que la réalité, ce qui est le pire des services à rendre."""
    n = sum(1 for d in CONTEST_DEFINITIONS.values() if ec._demande_un_numero(d))
    assert n >= 23, '%d concours avec numéro de série détectés' % n


def test_un_concours_sans_echange_formel_rend_le_report_seul():
    """L'UFT Challenge n'a pas d'échange de concours : inventer un numéro
    entraînerait à envoyer quelque chose qui ne se dit pas."""
    cdef = CONTEST_DEFINITIONS.get('UFT_CHALLENGE_ETE')
    assert ec.echange_attendu(cdef, 7, 'JN15XC', '43') == '599'


def test_sans_definition_de_concours_on_ne_plante_pas():
    assert ec.echange_attendu(None, 1) == '599'
    assert ec.echange_attendu({}, 1) == '599'


# ─── Le tirage des indicatifs ───────────────────────────────────────────────

def test_seuls_de_VRAIS_indicatifs_sont_tires():
    tires = ec.indicatifs_realistes(INDEX, limite=50, alea=random.Random(1))
    for c in ('PAS_UN_INDICATIF', '', '12345'):
        assert c not in tires, c
    assert 'F6KOP/P' in tires, 'les indicatifs à barre oblique doivent rester'


def test_les_deja_travailles_sont_privilegies():
    """Ce sont ceux qu'on réentendra, et leur présence dans le log prouve
    qu'ils existent."""
    tires = ec.indicatifs_realistes(INDEX, limite=6, alea=random.Random(2))
    travailles = {c for c in tires if INDEX.get(c, {}).get('qso_count', 0) > 0}
    assert len(travailles) >= 4, tires


def test_un_index_vide_ne_produit_pas_de_serie_bidon():
    assert ec.serie({}, None, n=10) == []
    assert ec.serie(None, None, n=10) == []


def test_la_serie_a_la_bonne_taille_et_des_echanges():
    s = ec.serie(INDEX, CONTEST_DEFINITIONS.get('REF_CDF_THF'), n=12,
                 locators=['JN15XC'], alea=random.Random(3))
    assert len(s) == 12
    assert all(x['call'] and x['echange'] for x in s)
    # Le numéro de série progresse d'une station à l'autre, comme en concours.
    nums = [x['echange'].split()[1] for x in s]
    assert nums == ['%03d' % i for i in range(1, 13)]


# ─── La correction : ce qu'elle APPREND à l'opérateur ───────────────────────

def test_une_serie_parfaite_donne_cent_pour_cent():
    s = ec.serie(INDEX, None, n=5, alea=random.Random(4))
    b = ec.corriger(s, [x['call'] for x in s])
    assert b['justes'] == 5 and b['taux'] == 100.0
    assert b['par_caractere'] == [] and b['confusions'] == []


def test_le_bilan_dit_QUELS_caracteres_sont_rates():
    """« tu rates le 5 et le 0 » est actionnable ; « 72 % » ne l'est pas."""
    s = [{'call': 'F5ABC'}, {'call': 'F5DEF'}, {'call': 'K0XYZ'}]
    b = ec.corriger(s, ['F4ABC', 'F4DEF', 'K9XYZ'])
    rates = dict(b['par_caractere'])
    assert rates.get('5') == 2
    assert rates.get('0') == 1
    assert b['justes'] == 0


def test_les_confusions_CW_connues_sont_nommees():
    """5 entendu 4, ou 0 entendu 9 : des motifs qui ne diffèrent que d'un
    élément. Les distinguer d'une faute de frappe quelconque est ce qui rend
    le bilan utile."""
    b = ec.corriger([{'call': 'F5ABC'}], ['F4ABC'])
    assert ('5→4', 1) in b['confusions']


def test_une_faute_qui_n_est_PAS_une_confusion_CW_n_est_pas_annoncee_comme_telle():
    b = ec.corriger([{'call': 'F5ABC'}], ['FZABC'])
    assert b['confusions'] == []
    assert dict(b['par_caractere']).get('5') == 1


def test_une_reponse_trop_courte_ou_vide_compte_les_manquants():
    b = ec.corriger([{'call': 'F5ABC'}], ['F5A'])
    assert b['justes'] == 0
    assert dict(b['par_caractere']) == {'B': 1, 'C': 1}
    assert ec.corriger([{'call': 'F5ABC'}], [''])['justes'] == 0
    assert ec.corriger([{'call': 'F5ABC'}], [None])['justes'] == 0


def test_la_casse_et_les_espaces_ne_comptent_pas_comme_des_fautes():
    assert ec.corriger([{'call': 'F5ABC'}], ['  f5abc '])['justes'] == 1


def test_corriger_supporte_une_serie_vide():
    b = ec.corriger([], [])
    assert b['total'] == 0 and b['taux'] == 0.0


# ─── La vitesse monte seule ─────────────────────────────────────────────────

@pytest.mark.parametrize('wpm, taux, attendu', [
    (20, 100, 22), (20, 90, 22),     # acquis : on accélère
    (20, 80, 21),                    # bon : on pousse d'un cran
    (20, 65, 20),                    # zone de travail : on ne bouge pas
    (20, 40, 18),                    # subi : on ralentit
])
def test_la_vitesse_suit_la_reussite(wpm, taux, attendu):
    assert ec.vitesse_suivante(wpm, taux) == attendu


def test_la_vitesse_reste_dans_des_bornes_praticables():
    assert ec.vitesse_suivante(12, 0) == 12       # jamais sous le plancher
    assert ec.vitesse_suivante(40, 100) == 40     # jamais au-delà du plafond
    assert ec.vitesse_suivante(None, 100) >= 12


# ─── Sur les données RÉELLES du poste ───────────────────────────────────────

def test_une_serie_tiree_de_l_index_REEL_du_poste_tient_debout(monkeypatch):
    """Le piège maison : une fonction vérifiée sur des données inventées et
    qui s'écroule sur les vraies.

    PIÈGE D'ORDRE D'EXÉCUTION, vu à la première suite complète : ce test
    passait SEUL et se mettait en SKIP dans la suite. L'index d'indicatifs est
    chargé en chemins RELATIFS et gardé en cache ; d'autres tests
    (test_archive.py) font `monkeypatch.chdir(tmp_path)`, et une reconstruction
    déclenchée là-bas ne trouve plus rien. Un test qui saute ne vérifie rien —
    on se replace donc dans le dépôt et on force la reconstruction."""
    import logx_callhistory as ch
    monkeypatch.chdir(CONCOURS)
    idx = ch.build_index([], force=True)
    if len(idx) < 50:
        pytest.skip('index local trop maigre sur ce poste')
    s = ec.serie(idx, CONTEST_DEFINITIONS.get('REF_CDF_THF'), n=20,
                 locators=['JN15XC'], alea=random.Random(7))
    assert len(s) == 20
    assert len({x['call'] for x in s}) >= 15, 'la série se répète trop'
    for x in s:
        assert x['echange'].startswith('599 ')
