# -*- coding: utf-8 -*-
"""Manipulateur WinKeyer K1EL — standard de fait du concours CW.

Pourquoi ce module alors que la commande KY existe déjà : elle ne couvre que
Kenwood et Elecraft. **Icom ne publie aucune commande CI-V d'envoi de texte
CW**, et la commande Yaesu homonyme n'a pas la même signification selon les
modèles. Le WinKeyer est leur SEULE voie de manipulation. Et même sur les
radios qui acceptent KY, il reste préférable : son propre port et son propre
processeur, donc une cadence qui ne dépend pas du trafic CAT.

Ces tests pilotent un faux port série et vérifient les OCTETS réellement émis,
protocole K1EL en main.

RÉSERVE : aucun WinKeyer n'a été branché. Les trames sont conformes à la
documentation du protocole et vérifiées octet par octet, mais le premier essai
sur un boîtier réel reste à faire.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_winkeyer as wk  # noqa: E402


class FauxWinKeyer:
    """Faux boîtier : note tout ce qu'on lui écrit, répond une version."""

    instances = []

    def __init__(self, device, timeout=1.0, version=0x17, muet=False):
        self.device = device
        self.ecrits = bytearray()
        self.version = version
        self.muet = muet          # simule un port sans WinKeyer au bout
        self.ferme = False
        self._a_repondre = bytearray()
        FauxWinKeyer.instances.append(self)

    def write(self, data):
        self.ecrits.extend(data)
        # L'ouverture de session est la seule commande qui répond.
        if bytes(data) == bytes([wk.ADMIN, wk.ADMIN_HOST_OPEN]) and not self.muet:
            self._a_repondre.append(self.version)

    def read(self, n=1, timeout=1.0):
        out = bytes(self._a_repondre[:n])
        del self._a_repondre[:n]
        return out

    def close(self):
        self.ferme = True


@pytest.fixture(autouse=True)
def faux_port(monkeypatch):
    FauxWinKeyer.instances = []
    monkeypatch.setattr(wk, '_ouvrir_port', FauxWinKeyer)
    monkeypatch.setattr(wk, 'HAS_PYSERIAL', True)
    monkeypatch.setattr(wk, '_port', None)
    monkeypatch.setattr(wk, '_port_nom', None)
    monkeypatch.setattr(wk, '_version', None)
    yield
    wk.fermer()


CFG = {'winkeyer_enabled': '1', 'winkeyer_port': 'COM5', 'winkeyer_wpm': 28}


def _octets():
    return bytes(FauxWinKeyer.instances[0].ecrits)


# ─── Ouverture de session ────────────────────────────────────────────────────

def test_l_ouverture_envoie_la_sequence_host_open():
    assert wk.envoyer(CFG, 'CQ')['ok']
    assert _octets().startswith(bytes([0x00, 0x02]))


def test_la_vitesse_est_transmise_au_boitier():
    """La vitesse se règle depuis le logiciel, pas sur la radio : c'est le
    manipulateur qui cadence."""
    wk.envoyer(CFG, 'CQ')
    assert bytes([wk.CMD_SET_WPM, 28]) in _octets()


def test_le_texte_part_apres_l_ouverture():
    wk.envoyer(CFG, 'CQ TEST')
    o = _octets()
    assert o.index(b'CQ TEST') > o.index(bytes([0x00, 0x02]))


def test_un_port_sans_winkeyer_est_detecte():
    """Sans la lecture de version, un simple adaptateur USB passerait pour un
    manipulateur et les macros partiraient dans le vide, sans message."""
    class Muet(FauxWinKeyer):
        def __init__(self, device, timeout=1.0):
            super().__init__(device, timeout, muet=True)

    wk._ouvrir_port = Muet
    res = wk.envoyer(CFG, 'CQ')
    assert not res['ok'] and 'aucune réponse' in res['error'].lower()


def test_la_connexion_est_reutilisee_entre_deux_macros():
    """Ouvrir/fermer à chaque macro coûterait ~1 s et couperait le début du
    message — inacceptable en run."""
    wk.envoyer(CFG, 'CQ')
    wk.envoyer(CFG, 'TU')
    assert len(FauxWinKeyer.instances) == 1
    assert _octets().count(bytes([0x00, 0x02])) == 1


def test_changer_de_port_rouvre():
    wk.envoyer(CFG, 'CQ')
    wk.envoyer(dict(CFG, winkeyer_port='COM7'), 'CQ')
    assert len(FauxWinKeyer.instances) == 2
    assert FauxWinKeyer.instances[0].ferme is True


# ─── Filtrage du texte ───────────────────────────────────────────────────────

def test_le_texte_est_mis_en_majuscules():
    wk.envoyer(CFG, 'cq de f4gld')
    assert b'CQ DE F4GLD' in _octets()


def test_les_caracteres_non_manipulables_sont_ecartes():
    wk.envoyer(CFG, 'CQ\x00 «TEST»\n')
    assert b'CQ TEST' in _octets()


def test_les_caracteres_de_service_passent():
    """« / », « ? » et « = » sont courants en concours : les filtrer casserait
    des macros usuelles."""
    wk.envoyer(CFG, 'F4GLD/P ? = 599')
    assert b'F4GLD/P ? = 599' in _octets()


@pytest.mark.parametrize('texte', ['', None, '   ', '«»\x01'])
def test_texte_vide_apres_filtrage_refuse(texte):
    res = wk.envoyer(CFG, texte)
    assert not res['ok']
    assert FauxWinKeyer.instances == [], "rien ne doit être ouvert pour un texte vide"


# ─── Vitesse ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('demande,attendu', [
    (28, 28), (3, wk.WPM_MIN), (150, wk.WPM_MAX), ('abc', 25), (None, 25),
])
def test_la_vitesse_est_bornee(demande, attendu):
    """Un octet de vitesse hors plage ferait interpréter n'importe quoi au
    boîtier : la valeur est bornée AVANT d'être envoyée."""
    assert wk.parametres(dict(CFG, winkeyer_wpm=demande))['wpm'] == attendu


# ─── Arrêt ───────────────────────────────────────────────────────────────────

def test_l_arret_vide_le_tampon():
    wk.envoyer(CFG, 'CQ CQ CQ DE F4GLD F4GLD')
    avant = len(_octets())
    assert wk.arreter(CFG)['ok']
    assert _octets()[avant:] == bytes([wk.CMD_CLEAR_BUFFER])


def test_l_arret_sans_rien_en_cours_n_ouvre_pas_le_port():
    """Demander l'arrêt d'un manipulateur qui ne manipule pas n'a pas à ouvrir
    un port ni à remonter une erreur."""
    res = wk.arreter(CFG)
    assert res['ok'] and FauxWinKeyer.instances == []


# ─── Désactivation et erreurs ────────────────────────────────────────────────

def test_desactive_ne_touche_a_rien():
    res = wk.envoyer({'winkeyer_enabled': ''}, 'CQ')
    assert not res['ok'] and 'désactivé' in res['error'].lower()
    assert FauxWinKeyer.instances == []


def test_port_non_renseigne():
    res = wk.envoyer({'winkeyer_enabled': '1'}, 'CQ')
    assert not res['ok'] and 'port' in res['error'].lower()


def test_un_boitier_debranche_en_cours_ne_leve_pas():
    """Cet appel vient du handler HTTP : il doit toujours rendre un dict."""
    wk.envoyer(CFG, 'CQ')

    def casse(data):
        raise OSError('port ferme')

    FauxWinKeyer.instances[0].write = casse
    res = wk.envoyer(CFG, 'TU')
    assert res['ok'] is False and 'injoignable' in res['error']


def test_la_fermeture_previent_le_boitier():
    """Sans Host Close, le WinKeyer resterait en mode piloté et ne répondrait
    plus à ses propres palettes."""
    wk.envoyer(CFG, 'CQ')
    boitier = FauxWinKeyer.instances[0]
    wk.fermer()
    assert bytes(boitier.ecrits).endswith(bytes([0x00, 0x03]))
    assert boitier.ferme is True


# ─── Test de présence (bouton CONFIG) ────────────────────────────────────────

def test_le_test_rend_la_version_lisible():
    res = wk.tester(dict(CFG, winkeyer_port='COM5'))
    assert res['ok'] and res['version'] == 0x17
    assert res['version_texte'] == 'WinKeyer v2.3'


def test_le_test_sans_port_refuse():
    assert not wk.tester({'winkeyer_enabled': '1'})['ok']


# ─── Le port lui-même peut refuser de s'ouvrir ───────────────────────────────
# Trouvé SUR SERVEUR RÉEL, pas ici : le faux boîtier ne lève jamais à la
# construction, alors que pyserial lève sur un port inexistant, déjà pris par
# un autre logiciel, ou sans droits. L'exception remontait jusqu'au handler
# HTTP, qui fermait la connexion SANS RÉPONSE — le navigateur affichait un
# échec réseau au lieu de « port introuvable ».

class PortQuiRefuse:
    def __init__(self, device, timeout=1.0):
        raise OSError("could not open port '%s'" % device)


def test_un_port_impossible_a_ouvrir_rend_une_erreur_lisible(monkeypatch):
    monkeypatch.setattr(wk, '_ouvrir_port', PortQuiRefuse)
    res = wk.envoyer(CFG, 'CQ')
    assert res['ok'] is False
    assert 'COM5' in res['error'] and 'inutilisable' in res['error']


def test_le_test_sur_un_port_impossible_ne_leve_pas(monkeypatch):
    monkeypatch.setattr(wk, '_ouvrir_port', PortQuiRefuse)
    res = wk.tester(CFG)
    assert res['ok'] is False and 'inutilisable' in res['error']


def test_un_boitier_qui_lache_pendant_l_ouverture_ne_leve_pas(monkeypatch):
    class MuetQuiCasse(FauxWinKeyer):
        def __init__(self, device, timeout=1.0):
            super().__init__(device, timeout)

        def write(self, data):
            raise OSError('cable debranche')

    monkeypatch.setattr(wk, '_ouvrir_port', MuetQuiCasse)
    res = wk.envoyer(CFG, 'CQ')
    assert res['ok'] is False and 'injoignable' in res['error']


# ─── Priorité dans le serveur ────────────────────────────────────────────────

def test_le_winkeyer_passe_avant_les_backends_cat():
    """C'est tout l'intérêt : il doit prendre la main quelle que soit la marque
    de radio, sinon Icom et Yaesu restent sans manipulation."""
    with open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8') as f:
        src = f.read()
    bloc = src[src.index("if self.path in ('/rig/qsy', '/rig/cw', '/rig/stop')"):]
    bloc = bloc[:bloc.index('elif native')]
    assert 'logx_winkeyer' in bloc
    assert bloc.index('logx_winkeyer') < bloc.index('cat_settings'), \
        "le WinKeyer doit être consulté AVANT le dispatch CAT"


# ─── RTS/DTR forcés bas à l'ouverture (bug trouvé/corrigé en revue
#     adversariale 03/08/2026, même piège que logx_cat.py:SerialPort) ───────

def test_port_winkeyer_force_rts_dtr_bas_a_ouverture(monkeypatch):
    """pyserial.Serial() n'accepte PAS rts=/dtr= comme arguments du
    constructeur (ValueError) — seulement comme propriétés d'instance posées
    AVANT open(). Ce double n'accepte aucun argument positionnel au
    constructeur (comme le vrai serial.Serial()), pour retrouver l'erreur si
    la production régresse vers l'ancien style (kwargs)."""
    if not wk.HAS_PYSERIAL:
        import pytest
        pytest.skip("pyserial non installé dans cet environnement")

    class _FakeUnderlyingSerial:
        def __init__(self):
            self.port = None
            self.rts = None
            self.dtr = None
            self.opened = False

        def open(self):
            self.opened = True

        def close(self):
            pass

    fake = _FakeUnderlyingSerial()
    monkeypatch.setattr(wk._pyserial, 'Serial', lambda: fake)
    wk.PortWinKeyer('COM99')
    assert fake.port == 'COM99'
    assert fake.rts is False
    assert fake.dtr is False
    assert fake.opened is True
