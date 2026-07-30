# -*- coding: utf-8 -*-
"""Carte des carrés QRA travaillés (VUCC) + locators par défaut.

DEMANDE UTILISATEUR : « une carte pour les collectionneurs de carrés locators,
et y'en a un paquet pour le VUCC ».

DÉFAUT DE DONNÉES TROUVÉ EN CONSTRUISANT CETTE CARTE, dans le log réel de la
station : `JJ00AA` y figure 300 fois, `AA00AA` quelques autres — 305 QSO au
total, soit 3,2 % du carnet. Ce sont des chaînes Maidenhead PARFAITEMENT
VALIDES, d'où le fait que rien ne les signalait, mais elles ne décrivent aucune
position : JJ00 est à 0° N, 0° E, en plein golfe de Guinée. Conséquences
mesurées : une distance moyenne de 5 032 km calculée pour ces contacts (une
station japonaise annoncée à 5 032 km au lieu de ~9 500) et un carré fantôme au
milieu de l'océan sur la carte.

CE QUE J'AI RENONCÉ À FAIRE, ET POURQUOI. J'allais généraliser en règle : « le
locator est suspect s'il est loin du centroïde du pays de l'indicatif ».
Mesuré sur les 9 347 QSO localisables, les plus gros écarts ne sont PAS des
erreurs :
    17 417 km  VK2ZK/P4  FK52LC  « Australia »  -> opère depuis Aruba
    14 378 km  HF0WOSP   GC07VX  « Poland »     -> station polaire polonaise
Un filtre par distance supprimerait donc de VRAIS carrés. Le gros écart révèle
surtout la faiblesse de la résolution DXCC sur les préfixes portables, pas un
mauvais locator. D'où une liste de valeurs par défaut exactes — moins maligne,
mais correcte.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_awards as aw   # noqa: E402

CARTE = os.path.join(CONCOURS, 'logx_carte.html')


def _qso(call, band='14', loc='JN18AA', time='1200'):
    return {'call': call, 'band': band, 'mode': 'SSB',
            'date': '2026-01-01', 'time': time, 'locator': loc}


@pytest.fixture
def sans_fichiers(monkeypatch):
    monkeypatch.setattr(aw, '_read_archives', lambda: [])
    monkeypatch.setattr(aw, '_read_qso_archive', lambda: [])
    monkeypatch.setattr(aw, '_load_confirmations', lambda: {})
    aw.invalidate()


# ─── Les locators par défaut ─────────────────────────────────────────────────

@pytest.mark.parametrize('faux', ['JJ00AA', 'AA00AA', 'jj00aa', ' JJ00AA '])
def test_un_locator_par_defaut_ne_fait_pas_un_carre(faux, sans_fichiers):
    r = aw.carres_travailles([_qso('W1ABC', loc=faux)])
    assert r['total'] == 0
    assert r['locators_factices'] == 1


def test_ils_sont_SIGNALES_pas_caches(sans_fichiers):
    """Sans ce compte, l'opérateur verrait un nombre de carrés inférieur à ce
    qu'il attend sans jamais comprendre pourquoi."""
    log = [_qso('W1ABC', loc='JJ00AA'), _qso('K5XYZ', loc='JN18AA', time='1300')]
    r = aw.carres_travailles(log)
    assert r['total'] == 1 and r['locators_factices'] == 1


def test_le_QSO_reste_au_carnet(sans_fichiers):
    """On écarte la POSITION, jamais le contact : c'est un vrai QSO, seul son
    locator est faux. Le supprimer ferait perdre un pays, une bande, un point."""
    log = [_qso('W1ABC', loc='JJ00AA')]
    aw.carres_travailles(log)
    assert len(log) == 1 and log[0]['locator'] == 'JJ00AA'


def test_un_vrai_carre_proche_n_est_pas_confondu(sans_fichiers):
    """JJ00AA est écarté, mais JJ11 ou JJ00BL restent des locators comme les
    autres : la liste vise des valeurs EXACTES, pas un champ entier."""
    r = aw.carres_travailles([_qso('W1ABC', loc='JJ11AA'),
                              _qso('K5XYZ', loc='JJ00BL', time='1300')])
    assert r['total'] == 2
    assert r['locators_factices'] == 0


def test_les_diplomes_de_carres_les_ecartent_aussi(sans_fichiers):
    """Le panneau Diplômes et la carte doivent compter PAREIL — sinon
    l'opérateur voit deux chiffres différents pour la même chose."""
    log = [_qso('W1ABC', loc='JJ00AA')]
    a = aw.award_summary(log)
    assert a['vucc']['worked'] == 0
    assert a['dx_field']['worked'] == 0


# ─── Le contenu de la carte ──────────────────────────────────────────────────

def test_chaque_carre_porte_son_nombre_de_QSO(sans_fichiers):
    """Sur la carte, un carré touché une fois et un carré travaillé cinquante
    fois se ressemblent. Pour un collectionneur, le premier est le plus
    fragile : c'est celui dont la confirmation manque le plus souvent."""
    log = [_qso('W1ABC', loc='JN18AA'), _qso('K5XYZ', loc='JN18BB', time='1300'),
           _qso('F6ABC', loc='JN19AA', time='1400')]
    r = aw.carres_travailles(log)
    par_g = {c['g']: c for c in r['squares']}
    assert par_g['JN18']['n'] == 2 and par_g['JN19']['n'] == 1


def test_chaque_carre_liste_ses_bandes(sans_fichiers):
    log = [_qso('W1ABC', band='144', loc='JN18AA'),
           _qso('W1ABC', band='50', loc='JN18AA', time='1300')]
    r = aw.carres_travailles(log)
    assert r['squares'][0]['bands'] == ['50', '144']


def test_le_filtre_par_bande_isole_le_VUCC(sans_fichiers):
    """Le VUCC s'obtient bande par bande (100 carrés en 6 m, en 2 m…) : une
    carte toutes bandes confondues ne correspondrait à aucun diplôme réel."""
    log = [_qso('W1ABC', band='144', loc='JN18AA'),
           _qso('K5XYZ', band='14', loc='JN19AA', time='1300')]
    assert aw.carres_travailles(log, '144')['total'] == 1
    assert aw.carres_travailles(log, '14')['total'] == 1
    assert aw.carres_travailles(log)['total'] == 2


def test_le_confirme_est_distingue(sans_fichiers, monkeypatch):
    """Pour un diplôme, seul le confirmé compte : la carte doit pouvoir le
    montrer sans qu'on ait à cliquer."""
    monkeypatch.setattr(aw, '_load_confirmations',
                        lambda: {'W1ABC|14|SSB': {'lotw': True}})
    aw.invalidate()
    log = [_qso('W1ABC', loc='JN18AA'), _qso('K5XYZ', loc='JN19AA', time='1300')]
    r = aw.carres_travailles(log)
    assert r['confirmed'] == 1
    assert {c['g']: c['conf'] for c in r['squares']} == {'JN18': True, 'JN19': False}


def test_un_locator_trop_court_ne_fabrique_rien(sans_fichiers):
    r = aw.carres_travailles([_qso('W1ABC', loc='JN'), _qso('K5XYZ', loc='', time='1300')])
    assert r['total'] == 0 and r['locators_factices'] == 0


# ─── La géométrie du dessin ──────────────────────────────────────────────────

def test_un_carre_maidenhead_n_est_PAS_un_carre():
    """2° de longitude sur 1° de latitude : un rectangle deux fois plus large
    que haut. Dessiner un carré centré sur le point serait faux partout sauf à
    l'équateur — vérifié dans la page : lat+1, lon+2."""
    with open(CARTE, encoding='utf-8') as f:
        src = f.read()
    bloc = src[src.index('function carreVersBornes'):]
    bloc = bloc[:bloc.index('\n}')]
    assert '* 20 - 180' in bloc and '* 2' in bloc, 'longitude : champ 20 deg, carre 2 deg'
    assert '* 10 - 90' in bloc and '* 1' in bloc, 'latitude : champ 10 deg, carre 1 deg'
    assert 'lat + 1, lon + 2' in bloc


def test_la_carte_signale_les_locators_par_defaut():
    with open(CARTE, encoding='utf-8') as f:
        src = f.read()
    assert 'locators_factices' in src
    assert 'locator par défaut' in src


def test_la_carte_propose_le_filtre_par_bande():
    with open(CARTE, encoding='utf-8') as f:
        src = f.read()
    assert 'carresBand' in src and "value=\"144\"" in src
