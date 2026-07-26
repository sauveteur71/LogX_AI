# -*- coding: utf-8 -*-
"""Transverters : la radio affiche la FI, le log doit porter la fréquence RÉELLE.

Au-dessus de 1296 MHz on passe par un transverter : la radio lit 144,100 MHz
alors que le signal part à 1296,100. Sans conversion, la bande déduite, le QSO
loggué, le filtre du band map, le QSY et le fichier EDI sont faux au même
moment — donc un log invalide pour le Rallye des Points Hauts, le National THF
ou le Challenge THF.

Le piège principal, trouvé en écrivant ces tests : le décalage ne se déduit
PAS des bords d'allocation. La bande 23 cm commence à 1240 MHz, mais un
transverter 144 → 1296 a son oscillateur à 1152 MHz et fait correspondre
144,000 à 1296,000. Partir de 1240 plaçait tout le trafic 56 MHz trop bas —
dans la bonne bande, donc sans erreur visible, mais avec une fréquence fausse
partout.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_transverter as tv  # noqa: E402


CFG = {'transverters': [
    {'if': '144', 'rf': '1296', 'enabled': True},
    {'if': '432', 'rf': '10368', 'enabled': True},
]}


# ─── Conversion en lecture (radio → réel) ────────────────────────────────────

@pytest.mark.parametrize('fi_hz,reel_hz,bande', [
    (144_000_000, 1_296_000_000, '1296'),   # bas de bande : les nominales coïncident
    (144_100_000, 1_296_100_000, '1296'),   # fréquence d'appel 23 cm
    (145_500_000, 1_297_500_000, '1296'),
    (432_200_000, 10_368_200_000, '10368'),  # 3 cm depuis une FI 432
    (432_000_000, 10_368_000_000, '10368'),
])
def test_la_frequence_lue_devient_la_frequence_reelle(fi_hz, reel_hz, bande):
    assert tv.rf_depuis_fi(fi_hz, CFG) == reel_hz
    assert tv.bande_depuis_hz(reel_hz) == bande


def test_le_decalage_vient_des_frequences_nominales_pas_des_bords_de_bande():
    """Garde-fou sur le piège : la bande 23 cm est allouée à partir de
    1240 MHz, mais un transverter 144 → 1296 place 144,000 sur 1296,000.
    Déduire 1240 - 144 donnerait 1096 MHz de décalage et un log faux de
    56 MHz — dans la bonne bande, donc invisible à l'œil."""
    (t,) = tv.transverters({'transverters': [{'if': '144', 'rf': '1296'}]})
    assert t['lo_mhz'] == 1152, "l'oscillateur d'un 144→1296 est à 1152 MHz"
    assert tv.rf_depuis_fi(144_000_000, CFG) == 1_296_000_000


def test_une_frequence_hors_fi_ne_bouge_pas():
    """La même station peut trafiquer en HF ou sur la bande FI elle-même :
    rien ne doit être décalé dans ce cas."""
    assert tv.rf_depuis_fi(14_200_000, CFG) == 14_200_000
    assert tv.rf_depuis_fi(50_150_000, CFG) == 50_150_000


def test_sans_transverter_configure_rien_ne_change():
    for cfg in ({}, {'transverters': []}, {'transverters': None}, None):
        assert tv.rf_depuis_fi(144_100_000, cfg) == 144_100_000
        assert tv.fi_depuis_rf(144_100_000, cfg) == 144_100_000


def test_un_transverter_desactive_ne_convertit_pas():
    cfg = {'transverters': [{'if': '144', 'rf': '1296', 'enabled': False}]}
    assert tv.rf_depuis_fi(144_100_000, cfg) == 144_100_000


# ─── Conversion en écriture (QSY) ────────────────────────────────────────────

@pytest.mark.parametrize('reel_hz,fi_hz', [
    (1_296_200_000, 144_200_000),
    (10_368_100_000, 432_100_000),
])
def test_le_qsy_renvoie_la_radio_sur_sa_fi(reel_hz, fi_hz):
    """Sans cette conversion inverse, on demanderait 1296,200 MHz à une radio
    qui ne monte pas si haut : refus, ou déplacement silencieux en bord de
    bande."""
    assert tv.fi_depuis_rf(reel_hz, CFG) == fi_hz


def test_le_qsy_hors_couverture_transverter_est_laisse_tel_quel():
    assert tv.fi_depuis_rf(14_200_000, CFG) == 14_200_000


@pytest.mark.parametrize('fi_hz', range(144_000_000, 148_000_001, 500_000))
def test_aller_retour_sans_perte(fi_hz):
    """Lire puis re-viser doit retomber exactement sur la même fréquence :
    un arrondi ici décalerait le QSO à chaque QSY."""
    assert tv.fi_depuis_rf(tv.rf_depuis_fi(fi_hz, CFG), CFG) == fi_hz


# ─── Validation de la configuration ──────────────────────────────────────────

def test_deux_transverters_sur_la_meme_fi_sont_refuses():
    """144,100 MHz voudrait dire 1296,100 OU 2320,100 : aucune règle de
    départage ne serait honnête. Physiquement un seul est branché."""
    msgs = tv.erreurs_config([{'if': '144', 'rf': '1296', 'enabled': True},
                              {'if': '144', 'rf': '2320', 'enabled': True}])
    assert msgs and 'ambigu' in msgs[0].lower()


def test_deux_transverters_sur_des_fi_differentes_sont_acceptes():
    """Un 1296 en FI 144 et un 10 GHz en FI 432 cohabitent sans ambiguïté."""
    assert tv.erreurs_config([{'if': '144', 'rf': '1296', 'enabled': True},
                              {'if': '432', 'rf': '10368', 'enabled': True}]) == []


def test_un_transverter_desactive_ne_cree_pas_d_ambiguite():
    """On doit pouvoir GARDER la config de ses deux transverters et n'en
    activer qu'un — sinon il faudrait en ressaisir un à chaque changement."""
    assert tv.erreurs_config([{'if': '144', 'rf': '1296', 'enabled': True},
                              {'if': '144', 'rf': '2320', 'enabled': False}]) == []


def test_bande_inconnue_signalee():
    msgs = tv.erreurs_config([{'if': '144', 'rf': '9999', 'enabled': True}])
    assert msgs and 'inconnue' in msgs[0].lower()


def test_rf_sous_la_fi_est_refusee():
    msgs = tv.erreurs_config([{'if': '432', 'rf': '144', 'enabled': True}])
    assert msgs and 'positif' in msgs[0].lower()


def test_oscillateur_explicite_prioritaire():
    """Tous les montages ne font pas coïncider les fréquences nominales.
    Un oscillateur déclaré à la main doit primer sur la déduction."""
    cfg = {'transverters': [{'if': '144', 'rf': '10368', 'lo_mhz': 10224, 'enabled': True}]}
    assert tv.rf_depuis_fi(144_000_000, cfg) == 10_368_000_000
    cfg2 = {'transverters': [{'if': '144', 'rf': '10368', 'lo_mhz': 10225, 'enabled': True}]}
    assert tv.rf_depuis_fi(144_000_000, cfg2) == 10_369_000_000


def test_entrees_malformees_ignorees_sans_lever():
    """Config ancienne ou éditée à la main : on ne doit pas planter le
    sondage de l'état radio, qui tourne toutes les 3 secondes."""
    cfg = {'transverters': ['pas un dict', None, {}, {'if': '144'}, 42]}
    assert tv.transverters(cfg) == []
    assert tv.rf_depuis_fi(144_100_000, cfg) == 144_100_000
