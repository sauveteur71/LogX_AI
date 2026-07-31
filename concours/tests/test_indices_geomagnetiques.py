# -*- coding: utf-8 -*-
"""Indices géomagnétiques : ce qu'on modélise, et ce qu'on refuse de modéliser.

DÉFAUT CORRIGÉ, ET IL SE CONTREDISAIT LUI-MÊME. `_band_score` portait
`if k >= 5: sfi_factor *= 0.6`, appliqué aux seules bandes HAUTES — or HIGH
contient '50'. Mesuré : à K=6 le score du 6 m tombait de 8 à 5, PENDANT que
`es_aurora_forecast()` annonçait sur cette même bande « orage géomagnétique,
aurora possible, pointe au nord ». Le logiciel se trompait de signe sur 6 m et
se contredisait dans la même seconde.

POURQUOI CE COEFFICIENT NE POUVAIT PAS ÊTRE « CORRIGÉ », seulement retiré :
  - l'échelle G du NOAA est définie sur Kp (G1 = Kp 5) et son libellé HF est
    LATITUDINAL — affaiblissement aux hautes latitudes, coupure sur les trajets
    polaires — jamais « bandes hautes » ;
  - ITU-R P.533-14 et VOACAP, les deux modèles de référence, sont pilotés par
    R12 et n'ingèrent PAS Kp ;
  - une tempête ionosphérique a une phase POSITIVE (foF2 en hausse) autant que
    négative, et le modèle de référence (STORM, intégré à IRI) dépend de la
    latitude, de la saison et de l'heure locale.

Le bon axe n'est pas la bande : c'est (latitude géomagnétique du trajet,
saison, heure locale, phase de la tempête). Deux voies honnêtes existaient —
implémenter STORM (Araujo-Pradere, Fuller-Rowell & Codrescu, Radio Science
37(5), 1070, 2002 : entrée = historique 33 h de ap, sortie = correction de
foF2), ou ne pas modéliser la tempête et afficher K et Ap bruts. C'est la
seconde, faute des tables de coefficients.

L'INDICE A EST DÉSORMAIS SERVI. Ap est la moyenne sur 24 h des huit ak
trihoraires (table de Bartels) : il n'apporte aucune information physique
nouvelle par rapport à la série des K, il apporte l'HISTORIQUE — précisément
la variable que la littérature utilise. Il était récupéré, affiché, et jeté.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_paths as paths     # noqa: E402
import logx_coach as coach     # noqa: E402


def _score(band, k, sfi=120, muf=20.0):
    return paths._band_score(band, 30, 30, muf, sfi, k, False)


# ─── Le coefficient inventé a disparu ────────────────────────────────────────

@pytest.mark.parametrize('band', ['1.8', '3.5', '7', '14', '21', '24', '28', '50'])
@pytest.mark.parametrize('k', [0, 2, 4, 5, 6, 7, 9])
def test_l_indice_K_ne_pondere_AUCUNE_bande(band, k):
    """Il n'existe pas de norme donnant une dégradation par bande en fonction
    de K. Tout chiffre de ce type est une heuristique inventée."""
    assert _score(band, k) == _score(band, 0), (band, k)


def test_LE_6m_N_EST_PLUS_PENALISE_PENDANT_UNE_AURORA():
    """LE défaut, dans sa forme observable : à K=6 le score du 6 m tombait de
    8 à 5 alors que le coach annonçait l'aurora sur cette même bande."""
    assert _score('50', 6) == _score('50', 2)


def test_et_le_coach_annonce_toujours_l_aurora():
    """La suppression ne doit pas emporter ce qui EST sourçable : l'échelle G
    du NOAA (G1 = Kp 5) et l'ouverture VHF qui va avec."""
    av = coach.es_aurora_forecast({'bands': ['50', '144']}, None, k_index=6)
    assert any(a['kind'] == 'aurora' for a in av), av


def test_le_coach_se_tait_quand_le_champ_est_calme():
    av = coach.es_aurora_forecast({'bands': ['50', '144']}, None, k_index=2)
    assert not any(a['kind'] == 'aurora' for a in av), av


# ─── Ce qui reste modélisé, parce que c'est étayé ────────────────────────────

def test_le_flux_solaire_pondere_TOUJOURS_les_bandes_hautes():
    """L'ionisation F2 croît avec le flux 10,7 cm : c'est une médiane, pas un
    événement, et ça reste légitime."""
    assert _score('28', 0, sfi=180) > _score('28', 0, sfi=70)


def test_le_flux_ne_touche_pas_les_bandes_basses():
    assert _score('3.5', 0, sfi=180) == _score('3.5', 0, sfi=70)


def test_la_MUF_reste_le_facteur_dominant():
    assert _score('28', 0, muf=35.0) > _score('28', 0, muf=10.0)


# ─── L'indice A est servi ────────────────────────────────────────────────────

@pytest.mark.parametrize('cle', ['a_index', 'aindex', 'ap', 'a'])
def test_l_indice_A_est_lu_quelle_que_soit_la_cle_de_la_source(cle):
    """Les sources ne s'accordent pas sur le nom du champ."""
    assert paths._a_index({cle: 42}) == 42.0
    assert paths._a_index({'solar': {cle: 42}}) == 42.0


@pytest.mark.parametrize('valeur', [None, '', 'abc'])
def test_une_valeur_A_illisible_donne_None_pas_zero(valeur):
    """Zéro voudrait dire « champ très calme » — un mensonge. None dit
    « inconnu »."""
    assert paths._a_index({'a_index': valeur}) is None


def test_A_absent_ne_leve_pas():
    assert paths._a_index({}) is None
    assert paths._a_index(None) is None


def test_l_indice_A_ARRIVE_bien_jusqu_au_client():
    """Il était récupéré depuis NOAA, affiché, et n'entrait dans aucun calcul
    ni dans aucune réponse. Ce test vérifie le CÂBLAGE — c'est le troisième
    défaut de la journée à être né d'une valeur calculée que personne ne lisait."""
    d = paths.path_openings(45.1, 3.95, list(paths.REGIONS)[0],
                            solar={'sfi': 130, 'k_index': 3, 'a_index': 27})
    assert 'a_index' in d
    assert d['a_index'] == 27.0


def test_A_reste_present_meme_quand_la_source_ne_le_donne_pas():
    """Une clé qui apparaît et disparaît oblige chaque appelant à se défendre."""
    d = paths.path_openings(45.1, 3.95, list(paths.REGIONS)[0],
                            solar={'sfi': 130, 'k_index': 3})
    assert 'a_index' in d and d['a_index'] is None
