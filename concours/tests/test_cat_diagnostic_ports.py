# -*- coding: utf-8 -*-
"""« Aucune radio détectée sur COM4 » ne disait pas ce qu'était COM4.

LE DÉFAUT. Quand `autodetect_scan()` échouait, son message renvoyait
l'opérateur vérifier « le câble/port » — c'est-à-dire précisément la partie de
la chaîne dont le logiciel venait de prouver qu'elle fonctionnait, puisque le
port s'était OUVERT (un port absent ou pris sort bien plus tôt, par
`_friendly_open_error`). Et il ne nommait ni le port visé, ni les autres ports
présents, alors que `list_ports()` les connaît tous les deux.

POURQUOI ÇA COMPTE. « COM Port number mismatch » est la deuxième cause de
panne CAT listée par la notice du boîtier XGGComms USB Digimode-4. C'est une
cause qu'un message peut écarter tout seul : il suffit de dire ce que le
serveur sait déjà. Cas réel du 20/08/2026 — un opérateur avec un FT-991
derrière un Digimode-4 a dû ouvrir le Gestionnaire de périphériques Windows
pour apprendre que COM4 était bien son interface FTDI, information que le
serveur avait en mémoire au moment même où il affichait son message.

CE QUE CES TESTS NE PROUVENT PAS : qu'une radio réelle réponde. Ils portent
uniquement sur l'HONNÊTETÉ du diagnostic rendu quand elle ne répond pas.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_cat as cat  # noqa: E402


# ─── Doubles ────────────────────────────────────────────────────────────────

FTDI = {'device': 'COM4', 'description': 'USB Serial Port',
        'vid': 0x0403, 'pid': 0x6001, 'serial_number': 'A50285BI',
        'product': 'USB Serial Port'}
BT7 = {'device': 'COM7', 'description': 'Standard Serial over Bluetooth link',
       'vid': None, 'pid': None, 'serial_number': None, 'product': None}
BT10 = {'device': 'COM10', 'description': 'Standard Serial over Bluetooth link',
        'vid': None, 'pid': None, 'serial_number': None, 'product': None}


class _PortMuet:
    """Un port qui s'ouvre parfaitement et ne répond jamais — exactement le
    cas que l'ancien message décrivait à tort comme un problème de câble."""

    def transceive(self, *a, **k):
        return b''

    def write(self, *a, **k):
        pass

    def read_until(self, *a, **k):
        return b''

    def close(self):
        pass


def _scan(ports, port='COM4', ouvrir=None, bauds=(19200, 4800)):
    """Exécute le VRAI autodetect_scan() contre une machine simulée.

    Aucune réimplémentation : un banc qui recopierait la construction du
    message ne contraindrait que sa propre copie (piège arrivé trois fois
    dans ce dépôt)."""
    o_list, o_open, o_sleep = cat.list_ports, cat._open_serial, cat._retry_sleep
    cat.list_ports = lambda: list(ports)
    cat._open_serial = ouvrir or (lambda p, baudrate=19200: _PortMuet())
    cat._retry_sleep = lambda s: None
    try:
        return cat.autodetect_scan(port, bauds=bauds)
    finally:
        cat.list_ports, cat._open_serial, cat._retry_sleep = o_list, o_open, o_sleep


# ─── Le port muet est identifié ─────────────────────────────────────────────

def test_le_port_muet_est_nomme_avec_ce_que_le_pc_en_dit():
    """LE DÉFAUT dans sa forme exacte : le message parlait de « COM4 » sans
    jamais dire ce qu'était COM4, alors que le serveur le savait."""
    msg = _scan([FTDI, BT7])['error']
    assert 'COM4' in msg
    assert 'USB Serial Port' in msg, (
        "le message doit dire ce qu'est le port visé, pas seulement son "
        'numéro : %r' % msg)


def test_les_autres_ports_sont_enumeres():
    """Le cœur du correctif. Se tromper de port est la 2e cause de panne de
    la notice ; on ne peut la vérifier que si on voit les autres candidats."""
    msg = _scan([FTDI, BT7, BT10])['error']
    assert 'COM7' in msg and 'COM10' in msg, (
        'les autres ports présents doivent être nommés : %r' % msg)


def test_le_port_vise_n_est_pas_recompte_parmi_les_autres():
    """Garde-fou de construction : COM4 ne doit apparaître que comme cible."""
    msg = _scan([FTDI, BT7])['error']
    assert msg.count('COM4') == 1, (
        'le port visé ne doit pas être répété dans la liste des autres : %r'
        % msg)


def test_l_absence_d_autre_port_est_DITE_pas_passee_sous_silence():
    """Omettre la phrase quand il n'y a rien d'autre laisserait croire que le
    logiciel n'a pas regardé. Un diagnostic doit distinguer « rien trouvé »
    de « pas cherché »."""
    msg = _scan([FTDI])['error']
    assert 'aucun autre port' in msg.lower(), (
        "quand il n'existe aucun autre port, le message doit le dire : %r"
        % msg)


def test_on_ne_renvoie_plus_verifier_ce_qui_vient_de_fonctionner():
    """Le vrai défaut n'était pas l'absence d'information, c'était une
    information FAUSSE : conseiller de vérifier le câble USB et le port au
    moment précis où l'on vient de les ouvrir avec succès."""
    msg = _scan([FTDI, BT7])['error']
    assert 'vérifie le câble/port' not in msg, (
        "ancien conseil trompeur réintroduit — le port s'est ouvert : %r" % msg)
    assert "s'OUVRE" in msg, (
        "le message doit établir que le port s'ouvre, c'est ce qui oriente "
        "la recherche vers l'aval : %r" % msg)


def test_la_comparaison_de_port_ignore_la_casse():
    """Une config qui contient « com4 » désigne le même port que « COM4 » ;
    sans ça le port visé serait déclaré ABSENT tout en étant listé juste
    après parmi les autres — un message qui se contredit lui-même.

    ⚠️ PREMIÈRE VERSION DE CE TEST : VACANTE, trouvée par contre-épreuve.
    Elle vérifiait « USB Serial Port » et « pas de mention d'absence
    d'autres ports » — deux assertions que la version CASSÉE satisfait
    parfaitement, puisque COM4 se retrouve alors dans la liste des AUTRES
    ports (avec sa description) et qu'il y a bien d'autres ports. Le test
    passait au vert sur le défaut exact qu'il prétendait couvrir. Il faut
    des assertions qui distinguent les DEUX BRANCHES du message, pas la
    présence d'un mot qui existe dans les deux."""
    msg = _scan([FTDI, BT7], port='com4')['error']
    assert "n'est plus présent" not in msg, (
        'le port visé a été pris pour un port absent à cause de la casse : %r'
        % msg)
    assert "s'OUVRE" in msg, (
        'seule la branche « port trouvé » établit que le port s\'ouvre : %r'
        % msg)
    assert msg.count('COM4') + msg.count('com4') == 1, (
        'le port ne doit apparaître qu\'une fois, comme cible : %r' % msg)


# ─── Identification du port ─────────────────────────────────────────────────

def test_un_boitier_reconnu_prime_sur_la_description_generique():
    """« USB Serial Port » ne distingue pas un boîtier CAT d'un adaptateur
    quelconque ; le VID:PID dédié, lui, le fait (guess_from_usb_signature)."""
    microham = dict(FTDI, pid=0xEEEA)
    libelle = cat.libelle_port(microham)
    assert 'microHAM' in libelle, libelle


def test_le_port_usb_d_un_poste_icom_est_signale_comme_tel():
    """Icom inscrit le modèle dans le numéro de série USB — savoir que le
    port EST la radio change complètement le diagnostic."""
    icom = {'device': 'COM9', 'description': 'Silicon Labs CP210x',
            'vid': 0x10C4, 'pid': 0xEA60,
            'serial_number': 'IC-7300 03000000', 'product': None}
    libelle = cat.libelle_port(icom)
    assert 'IC-7300' in libelle, libelle


def test_un_port_sans_description_reste_affichable():
    """Repli : jamais de guillemets vides ni de « None » à l'écran."""
    nu = {'device': 'COM2', 'description': '', 'vid': None, 'pid': None,
          'serial_number': None, 'product': None}
    assert cat.libelle_port(nu) == 'COM2'


# ─── Robustesse : le diagnostic ne doit jamais masquer l'erreur ─────────────

def test_etat_des_ports_ne_leve_jamais_meme_si_l_enumeration_echoue():
    """Un diagnostic qui plante remplacerait l'erreur utile par une trace
    Python. Il doit se taire, pas exploser."""
    o_list = cat.list_ports

    def _casse():
        raise OSError('énumération indisponible')

    cat.list_ports = _casse
    try:
        vise, autres = cat.etat_des_ports('COM4')
    finally:
        cat.list_ports = o_list
    assert vise is None and autres == ''


def test_le_scan_reste_exploitable_si_l_enumeration_echoue():
    """Même situation, vue de bout en bout : on perd l'enrichissement, pas
    le message."""
    def _casse():
        raise OSError('énumération indisponible')

    r = _scan(None, ouvrir=lambda p, baudrate=19200: _PortMuet())
    assert not r['ok']
    o_list = cat.list_ports
    cat.list_ports = _casse
    try:
        r2 = cat.autodetect_scan('COM4', bauds=(19200,))
    finally:
        cat.list_ports = o_list
    assert not r2['ok'] and 'COM4' in r2['error']


# ─── Port absent : l'autre chemin de message ────────────────────────────────

def test_un_port_absent_liste_quand_meme_ceux_qui_existent():
    """C'est LE cas « je me suis trompé de numéro de port » : le message
    doit contenir le bon numéro à choisir, sans aller le lire ailleurs."""
    o_list = cat.list_ports
    cat.list_ports = lambda: [FTDI, BT7]
    try:
        msg = cat._friendly_open_error(
            'COM3', FileNotFoundError(2, 'The system cannot find the file specified.'))
    finally:
        cat.list_ports = o_list
    assert 'COM4' in msg and 'USB Serial Port' in msg, msg
    assert 'détail technique' in msg, (
        'le détail technique brut ne doit jamais disparaître : %r' % msg)


def test_un_port_pris_par_un_autre_logiciel_garde_son_message_propre():
    """Non-régression : ce chemin-là avait déjà un bon message (retour
    bêta-testeur microHAM du 02/08/2026), il ne doit pas être noyé."""
    o_list = cat.list_ports
    cat.list_ports = lambda: [FTDI, BT7]
    try:
        msg = cat._friendly_open_error(
            'COM4', PermissionError(13, 'Access is denied.'))
    finally:
        cat.list_ports = o_list
    assert 'déjà utilisé' in msg, msg


def test_le_message_port_pris_explique_le_serveur_fantome():
    """Amélioration F4GLD 03/09 : « COM4 occupé alors que je n'ai que LogX ».
    Deux serveurs LogX ne peuvent pas tenir le port HTTP -> la cause n'est pas
    « un 2e LogX » mais un serveur python.exe d'une session PRÉCÉDENTE (fermer
    l'onglet ne l'arrête pas) ou un autre logiciel. Le message doit nommer ce
    piège ET son remède (Gestionnaire des tâches)."""
    msg = cat._friendly_open_error('COM4', PermissionError(13, 'Access is denied.'))
    assert 'python.exe' in msg, msg
    assert 'Gestionnaire des t' in msg, msg
    assert "N'ARRÊTE PAS le serveur" in msg, msg
