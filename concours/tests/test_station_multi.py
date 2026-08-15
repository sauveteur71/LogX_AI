# -*- coding: utf-8 -*-
"""Plusieurs antennes, plusieurs rotors, plusieurs amplis.

DEMANDE DE F4GLD (01/08/2026) : « certaines stations peuvent avoir plusieurs
antennes HF VHF mono ou directive, pour les rotors c'est pareil… mon ami a
trois pylônes, trois antennes différentes et trois rotors, il faudrait pouvoir
commander les trois rotors, ou plusieurs amplificateurs. »

DEUX CHOIX FAITS PAR L'OPÉRATEUR, et que ces tests figent :
  1. l'antenne porte SON rotor et SON ampli (structure réelle d'un pylône) ;
  2. un clic sur un spot ne fait tourner QUE le rotor de l'antenne active sur
     la bande — les autres pylônes ne bougent pas, sans quoi le multi-opérateur
     serait impraticable.

CE QUI COMPTE LE PLUS ICI : la MIGRATION. Des configurations existent déjà sur
les postes, avec quatre champs texte et un seul rotor. Elles doivent continuer
de fonctionner à l'identique sans que personne ne touche à rien — c'est la
règle du dépôt pour tout changement de schéma.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_station as S   # noqa: E402

TROIS_PYLONES = {
    'antennes': [
        {'nom': 'Yagi 6 él. 20m', 'bandes': ['14', '18', '21'],
         'type': 'directive', 'rotor_id': 'pylone-1', 'ampli_id': 'spe'},
        {'nom': 'Yagi 9 él. 144', 'bandes': ['144'], 'type': 'directive',
         'rotor_id': 'pylone-2'},
        {'nom': 'Parabole 23cm', 'bandes': ['1296'], 'type': 'parabole',
         'rotor_id': 'pylone-3'},
        {'nom': 'Dipôle 80/40', 'bandes': ['3.5', '7'], 'type': 'filaire'},
    ],
    'rotors': [
        {'id': 'pylone-1', 'nom': 'Pylône 1', 'enabled': True,
         'host': '192.168.1.20', 'port': 4533},
        {'id': 'pylone-2', 'nom': 'Pylône 2', 'enabled': True,
         'host': '192.168.1.21', 'port': 4533, 'offset_deg': 12},
        {'id': 'pylone-3', 'nom': 'Pylône 3', 'enabled': True,
         'host': '192.168.1.22', 'port': 4533},
    ],
    'amplis': [{'id': 'spe', 'nom': 'SPE 2K-FA', 'enabled': True,
                'brand': 'spe', 'port': 'COM5'}],
}


# ─── LA MIGRATION : rien ne doit être perdu ─────────────────────────────────

def test_une_ancienne_config_devient_une_liste_d_antennes():
    """Les quatre champs texte historiques deviennent des antennes, avec les
    bandes qu'ils couvraient implicitement."""
    st = S.charger({'ant_hf': 'Vertical 10m', 'ant_144': 'Yagi 9 él.',
                    'ant_432': 'Yagi 21 él.', 'ant_shf': 'Parabole 60cm'})
    noms = [a['nom'] for a in st['antennes']]
    assert noms == ['Vertical 10m', 'Yagi 9 él.', 'Yagi 21 él.', 'Parabole 60cm']
    hf = st['antennes'][0]
    assert '14' in hf['bandes'] and '3.5' in hf['bandes']
    assert '144' not in hf['bandes']
    assert st['antennes'][1]['bandes'] == ['144']


def test_l_ancien_rotor_unique_est_repris_ET_rattache_aux_antennes():
    """Avant, LE rotor tournait pour toutes les antennes. Ne pas le rattacher
    ferait perdre le pointage automatique à ceux qui ne touchent à rien."""
    st = S.charger({'ant_hf': 'Yagi', 'rotor_enabled': True,
                    'rotor_host': '127.0.0.1', 'rotor_port': 4533})
    assert len(st['rotors']) == 1
    assert st['rotors'][0]['enabled'] is True
    assert S.rotor_pour_bande(st, '14') is not None


def test_l_ancien_ampli_unique_est_repris():
    st = S.charger({'ant_hf': 'Yagi', 'amp_enabled': True, 'amp_brand': 'spe',
                    'amp_port': 'COM5'})
    assert len(st['amplis']) == 1
    assert st['amplis'][0]['brand'] == 'spe'
    assert S.ampli_pour_bande(st, '14') is not None


def test_une_config_DEJA_migree_n_est_jamais_ecrasee_par_les_vieux_champs():
    """Le piège de toute migration : ressusciter l'ancien par-dessus le neuf.
    Ici l'opérateur a saisi ses vraies antennes ; `ant_hf` traîne encore dans
    le fichier et ne doit surtout pas revenir."""
    cfg = dict(TROIS_PYLONES)
    cfg['ant_hf'] = 'VIEUX CHAMP À IGNORER'
    st = S.charger(cfg)
    assert 'VIEUX CHAMP À IGNORER' not in [a['nom'] for a in st['antennes']]
    assert len(st['antennes']) == 4


def test_une_config_vide_ne_plante_pas():
    for vide in ({}, None, {'antennes': 'pas une liste'}):
        st = S.charger(vide)
        assert st['antennes'] == [] and st['rotors'] == [] and st['amplis'] == []


# ─── Les trois pylônes ──────────────────────────────────────────────────────

@pytest.mark.parametrize('bande, antenne, rotor, ampli', [
    ('14',   'Yagi 6 él. 20m', 'Pylône 1', 'SPE 2K-FA'),
    ('21',   'Yagi 6 él. 20m', 'Pylône 1', 'SPE 2K-FA'),
    ('144',  'Yagi 9 él. 144', 'Pylône 2', None),
    ('1296', 'Parabole 23cm',  'Pylône 3', None),
    ('7',    'Dipôle 80/40',   None,       None),   # antenne fixe, sans rotor
])
def test_chaque_bande_trouve_SON_pylone(bande, antenne, rotor, ampli):
    st = S.charger(TROIS_PYLONES)
    assert S.antenne_active(st, bande)['nom'] == antenne
    r = S.rotor_pour_bande(st, bande)
    assert (r['nom'] if r else None) == rotor
    m = S.ampli_pour_bande(st, bande)
    assert (m['nom'] if m else None) == ampli


def test_une_bande_non_couverte_ne_fait_RIEN_tourner():
    """Le 50 MHz n'est déclaré nulle part : ne rien désigner vaut mieux que de
    faire tourner un pylône au hasard."""
    st = S.charger(TROIS_PYLONES)
    assert S.antenne_active(st, '50') is None
    assert S.rotor_pour_bande(st, '50') is None
    assert S.ampli_pour_bande(st, '50') is None


def test_le_choix_explicite_de_l_operateur_prime():
    """Deux antennes sur 14 MHz : celle que l'opérateur désigne gagne."""
    cfg = {'antennes': [
        {'id': 'yagi', 'nom': 'Yagi', 'bandes': ['14'], 'rotor_id': 'r1'},
        {'id': 'vert', 'nom': 'Verticale', 'bandes': ['14']}],
        'rotors': [{'id': 'r1', 'nom': 'Pylône', 'host': 'x', 'port': 4533}],
        'amplis': []}
    st = S.charger(cfg)
    assert S.antenne_active(st, '14')['nom'] == 'Yagi'          # défaut : la 1re
    assert S.antenne_active(st, '14', {'14': 'vert'})['nom'] == 'Verticale'
    # ... et le rotor suit le choix : la verticale n'en a pas, rien ne tourne.
    assert S.rotor_pour_bande(st, '14', {'14': 'vert'}) is None


def test_on_ne_peut_pas_forcer_une_antenne_sur_une_bande_qu_elle_ne_couvre_pas():
    """Sinon le logiciel commanderait un pylône pour une bande que l'antenne
    ne rayonne pas — et l'opérateur croirait pointer juste."""
    st = S.charger(TROIS_PYLONES)
    a = S.antenne_active(st, '14', {'14': 'dipole-80-40'})
    assert a['nom'] == 'Yagi 6 él. 20m'


# ─── Le décalage mécanique du rotor ─────────────────────────────────────────

@pytest.mark.parametrize('offset, vrai, envoye', [
    (0, 45, 45.0), (12, 45, 33.0), (-12, 45, 57.0),
    (12, 5, 353.0),        # passage par le nord
    (0, 359.7, 359.7),
])
def test_l_azimut_envoye_tient_compte_du_decalage(offset, vrai, envoye):
    """Un rotor dont le zéro n'est pas au nord fausse TOUT son pointage du même
    angle — une erreur qu'on ne remarque qu'en ratant les DX faibles."""
    assert S.azimut_rotor({'offset_deg': offset}, vrai) == envoye


def test_un_azimut_absurde_ne_commande_rien():
    for mauvais in (None, '', 'nord', float('nan'), float('inf')):
        r = S.azimut_rotor({'offset_deg': 0}, mauvais)
        assert r is None or (0 <= r < 360)


# ─── Les identifiants, et les incohérences qu'on doit dire ──────────────────

def test_les_identifiants_sont_stables_et_uniques():
    """Une antenne est référencée par sa bande et par son rotor : un
    identifiant qui changerait au prochain enregistrement romprait ces liens
    en silence."""
    cfg = {'antennes': [{'nom': 'Yagi'}, {'nom': 'Yagi'}, {'nom': 'Yagi'}],
           'rotors': [], 'amplis': []}
    ids = [a['id'] for a in S.charger(cfg)['antennes']]
    assert len(set(ids)) == 3
    assert S.charger(cfg)['antennes'][0]['id'] == ids[0]   # stable d'un appel à l'autre


def test_une_bande_inventee_est_ecartee():
    """Un fichier édité à la main peut porter « 20m » au lieu de « 14 » : la
    garder ferait croire à une couverture qui n'existe pas."""
    st = S.charger({'antennes': [{'nom': 'X', 'bandes': ['14', '20m', 'zzz']}],
                    'rotors': [], 'amplis': []})
    assert st['antennes'][0]['bandes'] == ['14']


def test_le_resume_signale_les_incoherences():
    """Mieux vaut les dire à la configuration que les découvrir le jour du
    concours."""
    st = S.charger({'antennes': [
        {'nom': 'Sans bande', 'bandes': []},
        {'nom': 'Rotor fantôme', 'bandes': ['14'], 'rotor_id': 'nexistepas'}],
        'rotors': [], 'amplis': []})
    r = S.resume(st)
    assert r['antennes_sans_bande'] == ['Sans bande']
    assert r['antennes_a_rotor_introuvable'] == ['Rotor fantôme']


def test_le_resume_liste_les_bandes_couvertes_dans_l_ordre():
    r = S.resume(S.charger(TROIS_PYLONES))
    assert r['bandes_couvertes'] == ['3.5', '7', '14', '18', '21', '144', '1296']
    assert (r['nb_antennes'], r['nb_rotors'], r['nb_amplis']) == (4, 3, 1)


# ─── Le parc de radios (inventaire, pas de pilotage CAT — 14/08/2026) ──────

def test_une_config_sans_radios_obtient_une_liste_vide_sans_migration():
    """Aucun ancien champ ne décrivait plusieurs radios : rien à reconstruire,
    juste une liste vide — contrairement à antennes/rotors/amplis."""
    st = S.charger({'ant_hf': 'Vertical 10m'})
    assert st['radios'] == []


def test_plusieurs_radios_associees_a_des_antennes():
    """Demande de F4GLD (14/08/2026) : plusieurs postes, chacun associé à une
    ou plusieurs antennes. Deux antennes peuvent partager LA MÊME radio."""
    cfg = {
        'antennes': [
            {'id': 'yagi20', 'nom': 'Yagi 20m', 'bandes': ['14'], 'radio_id': 'shack'},
            {'id': 'vert80', 'nom': 'Vertical 80m', 'bandes': ['3.5'], 'radio_id': 'shack'},
            {'id': 'yagi144', 'nom': 'Yagi 144', 'bandes': ['144'], 'radio_id': 'vhf'},
        ],
        'rotors': [], 'amplis': [],
        'radios': [
            {'id': 'shack', 'nom': 'IC-7300 principal', 'enabled': True,
             'brand': 'icom', 'model': 'IC-7300'},
            {'id': 'vhf', 'nom': 'FT-991A VHF', 'enabled': True,
             'brand': 'yaesu', 'model': 'FT-991A'},
        ],
    }
    st = S.charger(cfg)
    assert len(st['radios']) == 2
    assert S.radio_pour_bande(st, '14')['nom'] == 'IC-7300 principal'
    assert S.radio_pour_bande(st, '3.5')['nom'] == 'IC-7300 principal'
    assert S.radio_pour_bande(st, '144')['nom'] == 'FT-991A VHF'
    assert S.radio_pour_bande(st, '432') is None   # aucune antenne sur cette bande


def test_une_antenne_sans_radio_id_ne_designe_rien():
    """Une antenne fixe sans radio associée reste valide — l'inventaire radio
    est optionnel, jamais requis."""
    st = S.charger({'antennes': [{'nom': 'Dipôle', 'bandes': ['7']}],
                    'rotors': [], 'amplis': [], 'radios': []})
    assert S.radio_pour_bande(st, '7') is None


def test_le_resume_signale_une_radio_introuvable():
    st = S.charger({'antennes': [
        {'nom': 'Radio fantôme', 'bandes': ['14'], 'radio_id': 'nexistepas'}],
        'rotors': [], 'amplis': [], 'radios': []})
    r = S.resume(st)
    assert r['antennes_a_radio_introuvable'] == ['Radio fantôme']
    assert r['nb_radios'] == 0


def test_les_bandes_du_module_suivent_celles_du_logbook():
    """Deux listes de bandes tenues en double divergent — et une antenne
    deviendrait invisible sur sa bande sans le moindre message. Même piège que
    les identifiants de concours."""
    import re
    with open(os.path.join(CONCOURS, 'logx_logbook.js'), encoding='utf-8') as f:
        src = f.read()
    m = re.search(r'const ALL_BANDS = \[(.*?)\]', src, re.S)
    assert m, 'ALL_BANDS a disparu du logbook'
    js = [x.strip().strip("'\"") for x in m.group(1).split(',') if x.strip()]
    assert js == S.BANDES, 'BANDES (Python) et ALL_BANDS (JS) ont divergé'
