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
import json
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


# ─── Phase 1 (MVP OmniRig) : natif/OmniRig, OmniRig/OmniRig ─────────────────
# Avant ce lot, seul le couple natif/natif etait teste -- le vrai MVP SO2R
# (ecoute simultanee des 2 radios) suppose au moins une radio en OmniRig, le
# seul backend sans connexion persistante bloquante (voir docs/ETUDE_SO2R.md
# Phase 1). omnirig_rig_num n'est PAS prefixe cat_ (contrairement a
# cat_port/cat_brand...), donc hors de la boucle de remap generique --
# verifie ici a part.

CFG_NATIF_OMNIRIG = {
    'cat_enabled': '1', 'cat_mode': 'native', 'cat_brand': 'icom',
    'cat_port': 'COM3', 'cat_baudrate': 19200, 'omnirig_rig_num': 1,
    'cat2_enabled': '1', 'cat2_mode': 'omnirig', 'cat2_omnirig_rig_num': 2,
}


def test_radio_2_en_omnirig_bascule_le_mode_cat():
    """cat_mode suit deja cat2_mode via la boucle generique -- verifie ici
    que ca marche bien pour la valeur 'omnirig' precisement, la seule que la
    Phase 1 debloque en UI (cat2_mode etait fige a 'native' auparavant)."""
    so2r.basculer({'so2r_enabled': ''}, 2)
    vue = so2r.config_radio_active(CFG_NATIF_OMNIRIG)
    assert vue['cat_mode'] == 'omnirig'


def test_radio_2_en_omnirig_utilise_son_propre_rig_num():
    """Sans ce remap, la radio 2 piloterait le MEME Rig1/Rig2 OmniRig que la
    radio 1 -- deux radios physiques distinctes commandees comme une seule."""
    so2r.basculer({'so2r_enabled': ''}, 2)
    vue = so2r.config_radio_active(CFG_NATIF_OMNIRIG)
    assert vue['omnirig_rig_num'] == 2


def test_radio_1_garde_son_propre_rig_num_omnirig():
    assert so2r.cle_radio_active() == ''
    vue = so2r.config_radio_active(CFG_NATIF_OMNIRIG)
    assert vue['omnirig_rig_num'] == 1


def test_omnirig_omnirig_les_deux_radios_gardent_des_rig_num_distincts():
    cfg = {
        'cat_enabled': '1', 'cat_mode': 'omnirig', 'omnirig_rig_num': 1,
        'cat2_enabled': '1', 'cat2_mode': 'omnirig', 'cat2_omnirig_rig_num': 2,
    }
    vue1 = so2r.config_radio_active(cfg)
    assert vue1['omnirig_rig_num'] == 1
    so2r.basculer({'so2r_enabled': ''}, 2)
    vue2 = so2r.config_radio_active(cfg)
    assert vue2['cat_mode'] == 'omnirig'
    assert vue2['omnirig_rig_num'] == 2


def test_sans_cat2_omnirig_rig_num_le_remap_ne_touche_a_rien():
    """Config partielle (radio 2 pas encore reglee en OmniRig) : ne doit pas
    lever, ni ecraser omnirig_rig_num par une valeur absente."""
    so2r.basculer({'so2r_enabled': ''}, 2)
    vue = so2r.config_radio_active({'omnirig_rig_num': 1})
    assert vue['omnirig_rig_num'] == 1


# ─── Phase 2 : périphérique vocal par radio ──────────────────────────────────
# voicekeyer_device n'est pas préfixé cat_ non plus (comme omnirig_rig_num en
# Phase 1) -- hors de la boucle de remap générique, vérifié à part.

def test_radio_2_utilise_son_propre_peripherique_vocal():
    so2r.basculer({'so2r_enabled': ''}, 2)
    vue = so2r.config_radio_active({'voicekeyer_device': '3', 'voicekeyer_device2': '7'})
    assert vue['voicekeyer_device'] == '7'


def test_radio_1_garde_son_propre_peripherique_vocal():
    assert so2r.cle_radio_active() == ''
    vue = so2r.config_radio_active({'voicekeyer_device': '3', 'voicekeyer_device2': '7'})
    assert vue['voicekeyer_device'] == '3'


def test_sans_voicekeyer_device2_le_remap_ne_touche_a_rien():
    """Radio 2 sans périphérique vocal propre déclaré : garde celui de la
    radio 1 plutôt que de le vider -- comportement voulu, le champ CONFIG dit
    explicitement 'même périphérique que la radio 1' quand vide."""
    so2r.basculer({'so2r_enabled': ''}, 2)
    vue = so2r.config_radio_active({'voicekeyer_device': '3'})
    assert vue['voicekeyer_device'] == '3'


# ─── Paramètre radio= explicite (ferme la fenêtre TOCTOU côté HTTP) ─────────

def test_config_radio_active_avec_radio_explicite_ignore_le_focus_courant():
    """Le paramètre radio= doit primer sur le focus courant -- c'est ce qui
    permet à un appelant HTTP de capturer le focus UNE FOIS et de l'utiliser
    à la fois pour le verrou TX et pour la config, sans seconde lecture."""
    so2r.basculer({'so2r_enabled': ''}, 2)   # focus courant = 2
    cfg = {'cat_port': 'COM3', 'cat2_port': 'COM4'}
    assert so2r.config_radio_active(cfg, radio=1)['cat_port'] == 'COM3'
    assert so2r.config_radio_active(cfg, radio=2)['cat_port'] == 'COM4'
    # Sans radio= explicite, retombe sur le focus courant (comportement inchangé).
    assert so2r.config_radio_active(cfg)['cat_port'] == 'COM4'


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


# ─── RTS/DTR forcés bas à l'ouverture (bug trouvé/corrigé en revue
#     adversariale 03/08/2026, même piège que logx_cat.py:SerialPort) ───────

# ─── Focus câblé sur les 8 endpoints restants (Phase 0, revue ETUDE_SO2R.md) ─
# Avant ce lot, /rig/qsy, /rig/cw, /rig/stop et /rig/ptt suivaient déjà le
# focus -- ces 8-là lisaient encore la config BRUTE (radio 1 systématique)
# après une bascule Ctrl+Espace vers la radio 2 : le CQ vocal automatique
# continuait de parler vers la radio 1, l'état affiché et le panadapter
# restaient ceux de la radio 1 même pilotage réel basculé.

def _source_http():
    with open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8') as f:
        return f.read()


@pytest.mark.parametrize('marqueur', [
    "if path == '/rig/state':",
    "if path == '/rig/scope_available':",
    "if path == '/rig/scope_line':",
    "if path == '/rig/tci_spectrum_available':",
    "if path == '/rig/tci_spectrum_line':",
    "if path == '/hardware/state':",
    "if self.path == '/rig/voice':",
])
def test_endpoint_suit_le_focus_so2r(marqueur):
    src = _source_http()
    bloc = src[src.index(marqueur):]
    bloc = bloc[:600]
    assert 'so2r.config_radio_active' in bloc, (
        '%s ne cable pas so2r.config_radio_active -- affichera/pilotera '
        'toujours la radio 1 apres bascule Ctrl+Espace' % marqueur)


def test_voice_play_suit_le_focus_so2r():
    """/voice/play (message DVK) est niché dans le bloc partagé
    /voice/save|play|delete -- vérifié à part car le marqueur commun ne
    suffit pas à cibler la seule branche 'play'."""
    src = _source_http()
    bloc = src[src.index("if self.path in ('/voice/save', '/voice/play', '/voice/delete'):"):]
    bloc = bloc[:bloc.index("if self.path == '/rig/voice':")]
    assert 'vk.envoyer_message(' in bloc
    assert 'so2r.config_radio_active(self._cfg_snapshot(), radio=radio_active)' in bloc


# ─── Verrou d'exclusivité TX (Phase 0) ───────────────────────────────────────
# Le focus route le PILOTAGE, mais rien n'empêchait jusque-là d'armer un ordre
# d'émission sur la radio 2 pendant que la radio 1 émet encore -- un log avec
# deux porteuses actives en même temps est disqualifiable (CQ WW : "Only one
# transmitted signal is permitted at any time").

def test_verrouiller_tx_accepte_la_premiere_radio():
    assert so2r.verrouiller_tx(1)['ok'] is True


def test_verrouiller_tx_refuse_l_autre_radio_tant_que_le_verrou_tient():
    assert so2r.verrouiller_tx(1)['ok'] is True
    r = so2r.verrouiller_tx(2)
    assert r['ok'] is False
    assert 'Radio 1' in r['error']


def test_verrouiller_tx_reaccepte_la_meme_radio():
    """Une radio qui enchaîne plusieurs macros (F1 puis F2) ne doit pas se
    bloquer elle-même -- seul le verrou d'une AUTRE radio doit refuser."""
    assert so2r.verrouiller_tx(1)['ok'] is True
    assert so2r.verrouiller_tx(1)['ok'] is True


def test_deverrouiller_tx_libere_pour_l_autre_radio():
    so2r.verrouiller_tx(1)
    so2r.deverrouiller_tx(1)
    assert so2r.verrouiller_tx(2)['ok'] is True


def test_deverrouiller_tx_n_efface_pas_le_verrou_d_une_autre_radio():
    """Un relâchement tardif/en échec de la radio 1 ne doit pas effacer un
    verrou fraîchement pris par la radio 2."""
    so2r.verrouiller_tx(1)
    so2r.deverrouiller_tx(1)
    so2r.verrouiller_tx(2)
    so2r.deverrouiller_tx(1)
    assert so2r.verrouiller_tx(2)['ok'] is True
    assert so2r.verrouiller_tx(1)['ok'] is False


def test_verrouiller_tx_expire_apres_le_timeout(monkeypatch):
    """Un verrou 'collé' (radio déconnectée, plantage du keyer) doit se
    libérer tout seul plutôt que bloquer l'opérateur indéfiniment."""
    horloge = [1000.0]
    monkeypatch.setattr(so2r.time, 'monotonic', lambda: horloge[0])
    so2r.verrouiller_tx(1)
    horloge[0] += so2r.TX_LOCK_TIMEOUT_S + 1
    assert so2r.verrouiller_tx(2)['ok'] is True


def test_tx_actif_reflete_l_etat():
    assert so2r.tx_actif()['radio'] is None
    so2r.verrouiller_tx(2)
    assert so2r.tx_actif()['radio'] == 2


def test_reinitialiser_leve_aussi_le_verrou_tx():
    so2r.verrouiller_tx(1)
    so2r.reinitialiser()
    assert so2r.tx_actif()['radio'] is None


# ─── Verrou câblé côté HTTP (PTT radio1 actif -> PTT radio2 refusé) ─────────
#
# Ces 4 tests restent des vérifications structurelles (présence des appels
# dans le bon bloc source) -- utiles pour repérer vite une régression de
# câblage, mais volontairement AVEUGLES au comportement réel : la revue
# adversariale du 07/08/2026 a trouvé un bug critique (verrou jamais relâché
# sur un échec /rig/cw) que ces grep ne pouvaient PAS voir, puisque
# `verrouiller_tx` ET `deverrouiller_tx` apparaissaient bien tous les deux
# dans le bloc -- juste jamais sur le même chemin d'exécution. Les tests
# HTTP de bout en bout plus bas (section suivante) vérifient le VRAI
# comportement, pas juste la présence de texte.

def test_rig_cw_verrouille_avant_denvoyer():
    src = _source_http()
    bloc = src[src.index("if self.path in ('/rig/qsy', '/rig/cw', '/rig/stop')"):]
    # Fenêtre élargie de 2200 à 3000 le 20/08/2026 : l'étiquetage du verrou a
    # ajouté des lignes dans ce bloc et repoussait la cible hors du découpage.
    # 3000 reste DANS le même gestionnaire (/rig/qsy, /rig/cw, /rig/stop sont
    # traités ensemble) — la fenêtre existe pour ne pas valider sur le code
    # d'un AUTRE endpoint, pas pour compter des caractères.
    # Élargie de 3000 à 3600 le 23/08/2026 : le garde-fou d'émission CW
    # (logx_cw_guard) ajoute des lignes AVANT la prise du verrou (un refus ne
    # doit pas prendre le verrou) et repoussait la cible hors fenêtre — même
    # raison que l'élargissement 2200→3000. Reste dans le même gestionnaire.
    bloc = bloc[:3600]
    # Depuis le 20/08/2026 la prise de verrou porte SA SOURCE. Ce test est donc
    # plus strict qu'avant, pas plus laxiste : il ne se contente plus de voir
    # un verrou pris, il exige que ce soit celui du CW. Sans l'étiquette,
    # /rig/stop (donc Échap) ne lèverait plus ce verrou et le coupe-circuit
    # deviendrait inopérant.
    assert "so2r.verrouiller_tx(radio_active, 'cw')" in bloc
    # radio_active est réécrit sur la radio VERROUILLÉE (so2r.tx_actif())
    # avant ce point pour /rig/stop -- voir le correctif du 13/08/2026 : le
    # déverrouillage ET cfg_snap (donc la commande matérielle d'arrêt plus
    # bas) doivent cibler la MÊME radio, jamais une relue indépendamment
    # (même motif que /rig/ptt ci-dessous, déjà sur radio_active).
    # Relâchement RESTREINT au CW : /rig/stop ne doit plus lever le verrou pris
    # par /rig/ptt (le séquenceur FT8 passe par là) — voir
    # tests/test_verrou_tx_source.py pour le défaut complet.
    assert "so2r.deverrouiller_tx(radio_active, 'cw')" in bloc


def test_rig_ptt_verrouille_avant_larmement():
    src = _source_http()
    bloc = src[src.index("if self.path == '/rig/ptt':"):]
    # 2000 : la cible est à ~1400 et l'endpoint SUIVANT commence à 2260 —
    # la fenêtre couvre donc tout /rig/ptt sans jamais déborder ailleurs.
    bloc = bloc[:2000]
    assert "so2r.verrouiller_tx(radio_active, 'ptt')" in bloc
    assert 'so2r.deverrouiller_tx(radio_active)' in bloc


def test_rig_voice_verrouille_avant_denvoyer():
    src = _source_http()
    bloc = src[src.index("if self.path == '/rig/voice':"):]
    # 3100 : depuis l'ajout du garde-fou TX (24/08), deverrouiller_tx est à
    # ~2750 et l'endpoint SUIVANT commence à ~3155 — la fenêtre couvre donc tout
    # /rig/voice sans jamais déborder ailleurs.
    bloc = bloc[:3100]
    assert "so2r.verrouiller_tx(radio_active, 'voix')" in bloc
    assert 'so2r.deverrouiller_tx(radio_active)' in bloc


def test_voice_play_verrouille_avant_denvoyer():
    src = _source_http()
    bloc = src[src.index("if self.path in ('/voice/save', '/voice/play', '/voice/delete'):"):]
    bloc = bloc[:bloc.index("if self.path == '/rig/voice':")]
    assert "so2r.verrouiller_tx(radio_active, 'voix')" in bloc
    assert 'so2r.deverrouiller_tx(radio_active)' in bloc


# ─── Verrou TX : comportement réel, serveur HTTP de bout en bout ────────────
# Même harnais que tests/test_cat_proprietaire_dispatch.py (ThreadingHTTPServer
# sur port éphémère + urllib). Ajoutés après la revue adversariale du
# 07/08/2026, qui a précisément trouvé que les tests structurels ci-dessus ne
# détectaient PAS un verrou jamais relâché sur un chemin d'échec réel.
import http.server as _http_server  # noqa: E402
import threading as _threading  # noqa: E402
import urllib.error as _urllib_error  # noqa: E402
import urllib.request as _urllib_request  # noqa: E402

import logx_http as _httpmod  # noqa: E402


@pytest.fixture
def _server():
    srv = _http_server.ThreadingHTTPServer(('127.0.0.1', 0), _httpmod.Handler)
    port = srv.server_address[1]
    t = _threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield f'http://127.0.0.1:{port}'
    finally:
        srv.shutdown()
        srv.server_close()
        t.join(timeout=5)


def _http_post(base, path, payload):
    body = json.dumps(payload).encode('utf-8') if payload is not None else b''
    req = _urllib_request.Request(
        base + path, data=body, method='POST',
        headers={'Content-Type': 'application/json', 'X-RC-Token': _httpmod.AUTH_TOKEN})
    try:
        with _urllib_request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except _urllib_error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def test_rig_cw_echec_natif_icom_ne_laisse_pas_le_verrou_arme(_server, monkeypatch):
    """Reproduction exacte du bug trouvé en revue adversariale (07/08/2026) :
    radio en CAT natif Icom SANS WinKeyer -- cat.send_cw() refuse toujours le
    CW pour Icom (CI-V ne publie pas cette commande). Avant le correctif, le
    verrou restait armé indéfiniment (jusqu'au timeout de 120s) après ce
    refus, alors qu'aucune émission n'avait réellement eu lieu."""
    monkeypatch.setattr(_httpmod, 'current_config', {
        'cat_enabled': '1', 'cat_mode': 'native', 'cat_brand': 'icom', 'cat_port': 'COM3',
    })
    status, d = _http_post(_server, '/rig/cw', {'text': 'CQ TEST', 'armed': True, 'mode': 'CW'})
    assert status == 400 and d['ok'] is False
    # Le verrou ne doit PAS être resté armé sur cet échec -- la radio 2 doit
    # pouvoir émettre immédiatement, sans attendre le timeout de 120s.
    assert so2r.tx_actif()['radio'] is None
    assert so2r.verrouiller_tx(2)['ok'] is True


def test_rig_cw_echec_cat_desactive_ne_laisse_pas_le_verrou_arme(_server, monkeypatch):
    """Même bug, chemin d'échec différent : radio CAT entièrement désactivée."""
    monkeypatch.setattr(_httpmod, 'current_config', {'cat_enabled': ''})
    status, d = _http_post(_server, '/rig/cw', {'text': 'CQ TEST', 'armed': True, 'mode': 'CW'})
    assert status == 400 and d['ok'] is False
    assert so2r.tx_actif()['radio'] is None
    assert so2r.verrouiller_tx(2)['ok'] is True


def test_rig_cw_succes_natif_laisse_le_verrou_arme(_server, monkeypatch):
    """Contre-test : un envoi CW qui RÉUSSIT doit garder le verrou armé --
    l'émission est réellement en cours (fire-and-forget), la radio 2 ne doit
    PAS pouvoir émettre en même temps."""
    monkeypatch.setattr(_httpmod, 'current_config', {
        'cat_enabled': '1', 'cat_mode': 'native', 'cat_brand': 'elecraft', 'cat_port': 'COM3',
    })
    import logx_cat as cat
    monkeypatch.setattr(cat, 'send_cw', lambda cfg, text: {'ok': True, 'text': text})
    status, d = _http_post(_server, '/rig/cw', {'text': 'CQ TEST', 'armed': True, 'mode': 'CW'})
    assert status == 200 and d['ok'] is True
    assert so2r.tx_actif()['radio'] == 1
    assert so2r.verrouiller_tx(2)['ok'] is False


def test_rig_cw_non_arme_refuse_sans_prendre_le_verrou(_server, monkeypatch):
    """Garde-fou d'émission (logx_cw_guard, keyer CW Phase 1) : une requête
    /rig/cw NON armée est refusée (403) AVANT toute prise de verrou TX — la
    radio 2 doit rester immédiatement disponible."""
    monkeypatch.setattr(_httpmod, 'current_config', {
        'cat_enabled': '1', 'cat_mode': 'native', 'cat_brand': 'elecraft', 'cat_port': 'COM3',
    })
    status, d = _http_post(_server, '/rig/cw', {'text': 'CQ TEST'})   # armed absent
    assert status == 403 and d['ok'] is False and d.get('blocked') is True
    assert so2r.tx_actif()['radio'] is None            # verrou JAMAIS pris
    assert so2r.verrouiller_tx(2)['ok'] is True


def test_rig_stop_libere_le_verrou_meme_apres_bascule_de_focus(_server, monkeypatch):
    """Bug trouvé en revue adversariale (07/08/2026) : /rig/stop relâchait le
    verrou de la radio qui a le focus AU MOMENT du stop, pas celle qui l'a
    réellement armé. Un opérateur qui bascule le focus (Ctrl+Espace) entre un
    CW parti (fire-and-forget) et le clic sur ■ STOP se retrouvait avec un
    verrou orphelin, jamais relâché par le bouton de sécurité prévu à cet
    effet."""
    monkeypatch.setattr(_httpmod, 'current_config', {
        'cat_enabled': '1', 'cat_mode': 'native', 'cat_brand': 'elecraft', 'cat_port': 'COM3',
        'cat2_enabled': '1', 'cat2_mode': 'native', 'cat2_brand': 'elecraft', 'cat2_port': 'COM4',
    })
    import logx_cat as cat
    monkeypatch.setattr(cat, 'send_cw', lambda cfg, text: {'ok': True, 'text': text})
    monkeypatch.setattr(cat, 'stop_cw', lambda cfg: {'ok': True})
    status, d = _http_post(_server, '/rig/cw', {'text': 'CQ TEST', 'armed': True, 'mode': 'CW'})
    assert status == 200 and so2r.tx_actif()['radio'] == 1
    # Bascule de focus AVANT le stop -- le verrou reste sur la radio 1.
    so2r.basculer({'so2r_enabled': ''}, 2)
    status, d = _http_post(_server, '/rig/stop', None)
    assert status == 200
    # Le verrou de la radio 1 doit être levé malgré la bascule -- pas orphelin.
    assert so2r.tx_actif()['radio'] is None


def test_rig_ptt_natif_omnirig_radio2_fonctionne_avec_omnirig_enabled_remappe(_server, monkeypatch):
    """Bug trouvé en revue adversariale (07/08/2026) : config_radio_active()
    remappait cat_mode/omnirig_rig_num pour la radio 2, mais oubliait
    omnirig_enabled -- calculé par le JS UNIQUEMENT depuis cat_enabled/
    cat_mode de la radio 1. Radio 1 native + radio 2 OmniRig (exactement la
    config que l'UI recommande) : tout pilotage OmniRig de la radio 2 échouait
    silencieusement avec 'Pilotage OmniRig désactivé (CONFIG)'."""
    monkeypatch.setattr(_httpmod, 'current_config', {
        'cat_enabled': '1', 'cat_mode': 'native', 'cat_brand': 'elecraft', 'cat_port': 'COM3',
        'omnirig_enabled': False,  # calculé par le JS depuis la radio 1 (native) -- jamais true ici
        'cat2_enabled': '1', 'cat2_mode': 'omnirig', 'cat2_omnirig_rig_num': 2,
    })
    so2r.basculer({'so2r_enabled': ''}, 2)
    import logx_omnirig as omnirig
    # Mock UNIQUEMENT la couche COM (pywin32/Windows non disponible en CI) --
    # PAS omnirig.set_ptt() lui-même, pour que le VRAI garde-fou
    # omnirig_settings(cfg)['enabled'] (celui que ce correctif remappe) soit
    # réellement exercé par ce test.
    monkeypatch.setattr(omnirig, '_com_call', lambda rig_num, func: {'ok': True})
    status, d = _http_post(_server, '/rig/ptt', {'on': True})
    assert status == 200 and d['ok'] is True, (
        'PTT radio 2 (OmniRig) refusé malgré cat2_mode=omnirig -- omnirig_enabled '
        'probablement pas remappé pour la radio 2 : %r' % d)


def test_port_otrsp_force_rts_dtr_bas_a_ouverture(monkeypatch):
    """pyserial.Serial() n'accepte PAS rts=/dtr= comme arguments du
    constructeur (ValueError) — seulement comme propriétés d'instance posées
    AVANT open(). Ce double n'accepte aucun argument positionnel au
    constructeur (comme le vrai serial.Serial()), pour retrouver l'erreur si
    la production régresse vers l'ancien style (kwargs)."""
    if not so2r.HAS_PYSERIAL:
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
    monkeypatch.setattr(so2r._pyserial, 'Serial', lambda: fake)
    so2r.PortOtrsp('COM99')
    assert fake.port == 'COM99'
    assert fake.rts is False
    assert fake.dtr is False
    assert fake.opened is True
