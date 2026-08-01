# -*- coding: utf-8 -*-
"""L'horloge sans internet : la dérive mesurée sur le consensus des stations.

POURQUOI. En expédition, sans NTP, l'horloge du PC dérive de quelques secondes
par jour. Passé environ une seconde, les stations d'en face cessent de décoder
les appels FT8 — et RIEN ne le signale : on croit que la bande est fermée. Une
panne silencieuse qui peut coûter des jours d'expédition.

CE QUI REND LA MESURE POSSIBLE : chaque décodage WSJT-X porte son DT, l'écart
entre le début du signal reçu et le début de la fenêtre de réception locale.
Le consensus de dizaines de stations distinctes est la seule référence de temps
disponible quand il n'y a plus de réseau. Aucun appel réseau, aucune IA.

PIÈGE STRUCTUREL ÉVITÉ ICI : `_decodes` est indexé PAR INDICATIF, donc le
dernier décodage y écrase le précédent — on ne peut pas y lire une série
temporelle. Le DT est capté dans un flux séparé ; ces tests vérifient que ce
flux se remplit VRAIMENT depuis record_decode, et pas seulement que la fonction
de calcul sait faire une médiane.
"""
import os
import sys
import time

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_wsjtx as wsjtx   # noqa: E402


@pytest.fixture(autouse=True)
def _flux_propre():
    wsjtx._dt_echantillons.clear()
    yield
    wsjtx._dt_echantillons.clear()


def _semer(stations, maintenant, dt=0.9):
    for i, call in enumerate(stations):
        wsjtx._note_dt(call, {'dt': dt}, maintenant - i * 30)


STATIONS = ['K1ABC', 'W2DEF', 'JA1XYZ', 'G3AAA', 'DL2BBB', 'EA5CCC',
            'VK3DDD', 'PY2EEE', 'OH6FFF', 'SM7GGG']


# ─── Les trois états, jamais deux ───────────────────────────────────────────

def test_aucun_decodage_n_est_PAS_une_horloge_bonne():
    """Une expédition en CW/SSB ne décode rien : ne pas savoir n'est pas
    « tout va bien ». C'est l'erreur qui rendrait l'indicateur nuisible."""
    d = wsjtx.derive_horloge(maintenant=time.time())
    assert d['etat'] == 'aucune_mesure'
    assert d['secondes'] is None
    assert d['couleur'] == 'inconnu'


def test_trop_peu_de_stations_ne_donne_pas_de_verdict():
    now = time.time()
    _semer(['K1ABC', 'W2DEF'], now)
    d = wsjtx.derive_horloge(maintenant=now)
    assert d['etat'] == 'peu_de_donnees'
    assert d['couleur'] == 'inconnu'


def test_assez_de_stations_donne_une_derive_chiffree():
    now = time.time()
    _semer(STATIONS, now, dt=0.9)
    d = wsjtx.derive_horloge(maintenant=now)
    assert d['etat'] == 'mesuree'
    assert d['stations'] == len(STATIONS)
    assert abs(d['secondes'] - 0.9) < 0.01


@pytest.mark.parametrize('dt, couleur', [
    (0.10, 'verte'), (-0.30, 'verte'),
    (0.80, 'orange'), (-1.10, 'orange'),
    (1.60, 'rouge'), (-2.40, 'rouge'),
])
def test_les_seuils_encadrent_le_seuil_de_decodage_FT8(dt, couleur):
    """Le rouge doit tomber AVANT que les correspondants cessent de décoder,
    pas après — sinon l'indicateur confirme une panne au lieu de la prévenir."""
    now = time.time()
    _semer(STATIONS, now, dt=dt)
    assert wsjtx.derive_horloge(maintenant=now)['couleur'] == couleur


# ─── La robustesse de la mesure ─────────────────────────────────────────────

def test_une_station_bavarde_ne_pese_pas_plus_qu_une_autre():
    """Une station en pile-up décodée 50 fois écraserait la médiane si on
    comptait les échantillons au lieu des stations distinctes."""
    now = time.time()
    _semer(STATIONS, now, dt=0.9)
    for i in range(50):
        wsjtx._note_dt('BAVARDE', {'dt': -4.0}, now - i)
    d = wsjtx.derive_horloge(maintenant=now)
    assert abs(d['secondes'] - 0.9) < 0.2, (
        'la station bavarde a fait dériver la médiane : %s' % d)


@pytest.mark.parametrize('mauvais', [None, 'abc', float('nan'),
                                     float('inf'), 42.0, -99.0])
def test_un_DT_aberrant_n_entre_jamais_dans_la_mesure(mauvais):
    now = time.time()
    wsjtx._note_dt('X', {'dt': mauvais}, now)
    assert wsjtx.derive_horloge(maintenant=now)['etat'] == 'aucune_mesure'


def test_les_vieux_echantillons_sortent_de_la_fenetre():
    now = time.time()
    _semer(STATIONS, now - 6 * 3600)          # il y a 6 h
    assert wsjtx.derive_horloge(fenetre_s=3 * 3600,
                                maintenant=now)['etat'] == 'aucune_mesure'


def test_le_flux_ne_grossit_pas_indefiniment():
    """360 h de FT8 non-stop : la structure doit être bornée, sinon c'est une
    fuite mémoire garantie sur une expédition de quinze jours."""
    now = time.time()
    for i in range(20000):
        wsjtx._note_dt('K%dABC' % i, {'dt': 0.5}, now)
    assert len(wsjtx._dt_echantillons) <= wsjtx._dt_echantillons.maxlen
    assert wsjtx._dt_echantillons.maxlen <= 10000


# ─── LE FIL : record_decode alimente-t-il vraiment le flux ? ────────────────

def test_record_decode_alimente_le_flux_de_DT():
    """Sans ce test, tout ce fichier peut être vert avec la mesure branchée
    sur rien — le motif exact qui a laissé /call/near mort pendant des mois."""
    avant = len(wsjtx._dt_echantillons)
    wsjtx.record_decode({'message': 'CQ K1ABC FN42', 'dt': 0.7,
                         'snr': -12, 'delta_hz': 1200}, my_call='F4GLD')
    assert len(wsjtx._dt_echantillons) > avant, (
        'record_decode ne remplit pas le flux : la dérive serait toujours '
        'calculée sur du vide')
    assert wsjtx._dt_echantillons[-1][2] == pytest.approx(0.7)


def test_un_decodage_sans_DT_ne_casse_pas_record_decode():
    wsjtx.record_decode({'message': 'CQ K1ABC FN42'}, my_call='F4GLD')
    assert wsjtx.derive_horloge(maintenant=time.time())['etat'] == 'aucune_mesure'


def test_le_resultat_est_serialisable_en_JSON():
    import json
    now = time.time()
    _semer(STATIONS, now)
    json.dumps(wsjtx.derive_horloge(maintenant=now), allow_nan=False)
