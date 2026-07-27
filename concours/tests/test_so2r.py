# -*- coding: utf-8 -*-
"""SO2R : deux radios, une paire d'oreilles, un manipulateur.

Appeler CQ sur une bande pendant qu'on cherche des multiplicateurs sur l'autre :
c'est ce qui sépare un score honorable d'un score de podium en HF mono-opérateur.

CE QUI EST TESTÉ, ET CE QUI NE PEUT PAS L'ÊTRE. La commutation réelle — quelle
radio émet, ce qu'on entend dans quelle oreille — se fait dans un BOÎTIER
matériel : aucun logiciel ne route de l'audio à la place d'un relais. Le rôle du
logiciel est de DIRE au boîtier quoi commuter, via le protocole OTRSP. Ce sont
donc ces trames, et le routage du pilotage vers la bonne radio, qui sont
vérifiés ici.

RÉSERVE : aucun boîtier OTRSP n'a été branché. Les trames sont conformes à la
spécification et vérifiées octet par octet, mais rien n'a commuté pour de vrai.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_so2r as so2r  # noqa: E402


class FauxBoitier:
    instances = []

    def __init__(self, device, timeout=1.0):
        self.device = device
        self.ecrits = bytearray()
        self.ferme = False
        FauxBoitier.instances.append(self)

    def write(self, data):
        self.ecrits.extend(data)

    def read(self, n=1, timeout=0.3):
        return b''

    def close(self):
        self.ferme = True


@pytest.fixture(autouse=True)
def boitier(monkeypatch):
    FauxBoitier.instances = []
    monkeypatch.setattr(so2r, '_ouvrir_port', FauxBoitier)
    monkeypatch.setattr(so2r, 'HAS_PYSERIAL', True)
    so2r.reinitialiser()
    yield
    so2r.reinitialiser()


CFG = {'so2r_enabled': '1', 'so2r_port': 'COM9', 'so2r_stereo': '1'}


def _trames():
    return bytes(FauxBoitier.instances[0].ecrits).decode('ascii')


# ─── Bascule d'émission ──────────────────────────────────────────────────────

def test_au_depart_l_emission_est_sur_la_radio_1():
    assert so2r.focus()['focus'] == 1


def test_basculer_sans_argument_passe_a_l_autre_radio():
    assert so2r.basculer(CFG)['focus'] == 2
    assert so2r.basculer(CFG)['focus'] == 1


def test_la_commande_TX_part_vers_le_boitier():
    """C'est le boîtier qui commute réellement : sans cette trame, le focus
    ne serait qu'un affichage."""
    so2r.basculer(CFG, 2)
    assert 'TX2\r' in _trames()


@pytest.mark.parametrize('radio', [1, 2, '1', '2'])
def test_on_peut_viser_une_radio_precise(radio):
    assert so2r.basculer(CFG, radio)['focus'] == int(radio)


def test_une_valeur_absurde_bascule_au_lieu_de_planter():
    """L'appel vient du réseau : une valeur inattendue ne doit pas lever."""
    so2r.basculer(CFG, 1)
    assert so2r.basculer(CFG, 'gauche')['focus'] == 2


# ─── Écoute ──────────────────────────────────────────────────────────────────

def test_en_stereo_on_garde_une_oreille_sur_l_autre_radio():
    """Le mode de travail réel du SO2R : on écoute la radio d'émission d'un
    côté et l'autre de l'autre côté. Sans ça, on perd le CQ dès qu'on part
    chercher."""
    r = so2r.basculer(CFG, 2)
    assert r['ecoute'] == 'RX2S'
    assert 'RX2S\r' in _trames()


def test_sans_stereo_l_ecoute_suit_l_emission():
    r = so2r.basculer(dict(CFG, so2r_stereo='0'), 2)
    assert r['ecoute'] == 'RX2'
    assert 'RX2S' not in _trames()


def test_les_deux_commandes_partent_dans_l_ordre():
    """TX avant RX : on veut que l'émission soit routée avant de rebrancher
    l'écoute, pas l'inverse."""
    so2r.basculer(CFG, 2)
    t = _trames()
    assert t.index('TX2') < t.index('RX2S')


# ─── Sans boîtier ────────────────────────────────────────────────────────────

def test_sans_boitier_le_focus_bascule_quand_meme():
    """Le focus sert AUSSI à router le QSY et les macros vers la bonne radio :
    ça a du sens même sans commutateur, casque rebranché à la main."""
    r = so2r.basculer({'so2r_enabled': ''})
    assert r['ok'] and r['focus'] == 2
    assert 'non configure' in r.get('note', '')
    assert FauxBoitier.instances == []


def test_boitier_active_mais_port_absent():
    r = so2r.basculer({'so2r_enabled': '1', 'so2r_port': ''})
    assert r['ok'] and r['focus'] == 2
    assert FauxBoitier.instances == []


class PortQuiRefuse:
    def __init__(self, device, timeout=1.0):
        raise OSError("could not open port '%s'" % device)


def test_un_port_impossible_a_ouvrir_rend_une_erreur_lisible(monkeypatch):
    """Même piège que le WinKeyer, trouvé là sur serveur réel : laisser filer
    l'exception tuerait la connexion HTTP sans réponse."""
    monkeypatch.setattr(so2r, '_ouvrir_port', PortQuiRefuse)
    r = so2r.basculer(CFG, 2)
    assert r['ok'] is False and 'inutilisable' in r['error']
    # Le focus logiciel a quand même changé : le pilotage doit suivre.
    assert so2r.focus()['focus'] == 2


def test_un_boitier_debranche_en_cours_ne_leve_pas(monkeypatch):
    so2r.basculer(CFG, 2)

    def casse(data):
        raise OSError('cable debranche')

    FauxBoitier.instances[0].write = casse
    r = so2r.basculer(CFG, 1)
    assert r['ok'] is False and 'injoignable' in r['error']


# ─── Routage du pilotage vers la radio active ────────────────────────────────

CFG2 = {
    'cat_enabled': '1', 'cat_mode': 'native', 'cat_brand': 'icom',
    'cat_port': 'COM3', 'cat_baudrate': 19200,
    'cat2_enabled': '1', 'cat2_mode': 'native', 'cat2_brand': 'elecraft',
    'cat2_port': 'COM4', 'cat2_baudrate': 38400,
}


def test_sur_la_radio_1_la_config_est_inchangee():
    vue = so2r.config_radio_active(CFG2)
    assert vue['cat_port'] == 'COM3' and vue['cat_brand'] == 'icom'


def test_sur_la_radio_2_la_config_de_la_seconde_prend_la_place():
    """Tout le pilotage existant continue de lire cat_* : il n'a pas à savoir
    qu'il y a deux radios. C'est cette vue qui fait la bascule."""
    so2r.basculer({'so2r_enabled': ''}, 2)
    vue = so2r.config_radio_active(CFG2)
    assert vue['cat_port'] == 'COM4'
    assert vue['cat_brand'] == 'elecraft'
    assert vue['cat_baudrate'] == 38400


def test_les_cles_absentes_de_la_radio_2_gardent_celles_de_la_1():
    """Config partielle : on ne veut pas effacer un réglage faute d'équivalent
    déclaré pour la seconde radio."""
    so2r.basculer({'so2r_enabled': ''}, 2)
    vue = so2r.config_radio_active({'cat_port': 'COM3', 'cat_brand': 'icom',
                                    'cat2_port': 'COM4'})
    assert vue['cat_port'] == 'COM4'
    assert vue['cat_brand'] == 'icom'


def test_la_cle_de_suffixe_a_un_seul_endroit():
    """Si la correspondance radio -> suffixe était reconstruite ailleurs, une
    moitié du code piloterait la radio 1 pendant que l'autre piloterait la 2."""
    assert so2r.cle_radio_active() == ''
    so2r.basculer({'so2r_enabled': ''}, 2)
    assert so2r.cle_radio_active() == '2'


def test_le_pilotage_http_passe_par_la_vue_de_la_radio_active():
    """Garde-fou : /rig/qsy, /rig/cw et /rig/stop doivent viser la radio qui a
    le focus, sinon le SO2R n'est qu'un voyant lumineux."""
    with open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8') as f:
        src = f.read()
    bloc = src[src.index("if self.path in ('/rig/qsy', '/rig/cw', '/rig/stop')"):]
    bloc = bloc[:2000]
    assert 'so2r.config_radio_active' in bloc


# ─── Test du boîtier (bouton CONFIG) ─────────────────────────────────────────

def test_le_test_envoie_une_commande_inoffensive():
    r = so2r.tester(CFG)
    assert r['ok'] and 'TX1\r' in _trames()


def test_le_test_sans_port_refuse():
    assert not so2r.tester({'so2r_enabled': '1'})['ok']


def test_le_bouton_tester_utilise_le_port_SAISI_pas_celui_enregistre():
    """Defaut trouve a la passe de verification, sur serveur reel : /so2r/test
    lisait le port de la config ENREGISTREE et ignorait celui envoye par la
    page. Le bouton « Tester le boitier » ne pouvait donc rien tester tant
    qu'on n'avait pas sauvegarde -- l'inverse de ce qu'on attend d'un bouton de
    test, et la page affichait « port non renseigne » alors qu'il l'etait.
    /winkeyer/test faisait deja les choses correctement."""
    with open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8') as f:
        src = f.read()
    bloc = src[src.index("if self.path in ('/so2r/focus', '/so2r/test')"):]
    bloc = bloc[:bloc.index('if self.path in (\'/bandmap/add\'')]
    assert "payload.get('port')" in bloc, (
        'le port saisi dans la page doit primer sur celui de la config')
    assert "cfg_test['so2r_port']" in bloc
