# -*- coding: utf-8 -*-
"""CI-V : une ÉCRITURE est accusée par FB/FA, jamais par un écho de commande.

Bug signalé en trafic réel par F4GLD le 18/08/2026 : « PTT refusé — vérifie le
pilotage radio (CONFIG) » affiché à l'écran ALORS QUE le poste passait bel et
bien en émission. Les deux à la fois, ce n'est pas contradictoire : le poste
exécutait la commande, et le logiciel ne savait pas la lire.

CAUSE
Les trois commandes SET du pilote Icom (05 fréquence, 06 mode, 1C 00 PTT)
passaient par CivRadio._query(), qui vérifie que la réponse RÉÉCHOTE cmd/sub.
C'est le bon contrôle pour une LECTURE — et il est là pour une bonne raison
(bus CI-V partagé entre plusieurs logiciels, voir son commentaire). Mais un
poste Icom n'accuse JAMAIS une écriture ainsi : il répond
`FE FE E0 <addr> FB FD` (FB = OK) ou `... FA FD` (FA = NG), sans cmd ni sub.
Source : manuel « CI-V Reference » Icom (fait foi).

_query() rendait donc None sur TOUTE écriture, et set_freq/set_mode/set_ptt
rendaient {'ok': False} en permanence.

POURQUOI LA SUITE ÉTAIT VERTE
Le simulateur FakeCivRadio (tests/test_cat.py) répondait aux écritures en
RENVOYANT LA COMMANDE — exactement ce que _query() attendait. Il avait été
écrit pour correspondre au CODE, pas au PROTOCOLE. Rendu conforme au manuel,
il fait tomber 11 tests d'un coup.

C'est la 3e fois dans ce dépôt qu'un simulateur écrit d'après le code masque
un défaut réel. Ces tests-ci construisent donc les trames à la main, octet par
octet, d'après le manuel — sans passer par le moindre helper du module testé.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_cat as cat  # noqa: E402

ADDR = 0x94   # IC-7300 (adresse CI-V d'usine)
CTRL = 0xE0   # adresse contrôleur (PC), convention Icom

# Trames écrites À LA MAIN d'après le manuel « CI-V Reference » — surtout PAS
# via civ_build_frame(), sinon on retesterait le code avec lui-même.
ACCUSE_OK = bytes([0xFE, 0xFE, CTRL, ADDR, 0xFB, 0xFD])
ACCUSE_NG = bytes([0xFE, 0xFE, CTRL, ADDR, 0xFA, 0xFD])


class PosteIcom:
    """Poste Icom réduit à ce qui compte ici : il ACCUSE les écritures.

    `reponse` permet de simuler un poste qui ne répond rien (câble débranché)
    ou qui refuse (FA)."""

    def __init__(self, reponse=ACCUSE_OK):
        self.reponse = reponse
        self.recu = []
        self._pending = b''

    def write(self, data):
        self.recu.append(data)
        self._pending = self.reponse

    def read_until(self, terminator, timeout=1.0):
        r, self._pending = self._pending, b''
        return r

    def close(self):
        pass


def _radio(reponse=ACCUSE_OK):
    poste = PosteIcom(reponse)
    return poste, cat.CivRadio(poste, ADDR)


# ─── PTT — la commande qui a déclenché tout ceci ────────────────────────────

@pytest.mark.parametrize('on,octet_attendu', [(True, 0x01), (False, 0x00)])
def test_le_ptt_est_accepte_sur_un_accuse_fb(on, octet_attendu):
    """Un poste qui répond FB a exécuté la commande : le logiciel doit dire
    OUI. Avant correctif il disait NON, et l'opérateur voyait « PTT refusé »
    pendant que son poste émettait."""
    poste, radio = _radio()
    res = radio.set_ptt(on)
    assert res['ok'] is True, res
    # Trame émise conforme au manuel : FE FE 94 E0 1C 00 <00|01> FD
    assert poste.recu[-1] == bytes([0xFE, 0xFE, ADDR, CTRL, 0x1C, 0x00, octet_attendu, 0xFD])


def test_le_ptt_est_refuse_sur_un_accuse_fa():
    """FA = NG. Le poste a REFUSÉ (déjà en émission par une autre source,
    verrouillage façade...). Le logiciel doit le dire — et c'est le seul cas
    où « PTT refusé » est le bon message."""
    _, radio = _radio(ACCUSE_NG)
    res = radio.set_ptt(True)
    assert res['ok'] is False
    assert res.get('error'), 'un échec doit toujours porter un message'


def test_le_ptt_est_refuse_si_le_poste_ne_repond_rien():
    """Câble débranché, mauvais port, mauvaise adresse CI-V : pas d'accusé du
    tout. Échec, avec message."""
    _, radio = _radio(b'')
    res = radio.set_ptt(True)
    assert res['ok'] is False
    assert res.get('error')


def test_un_echo_de_notre_propre_trame_ne_vaut_pas_accuse():
    """Câble bouclé, adaptateur en écho local, poste absent : on relit
    exactement ce qu'on a écrit. TO/FROM sont alors inversés par rapport à une
    vraie réponse — ça ne doit jamais compter comme un succès, sinon le
    logiciel annonce une émission qui n'a jamais eu lieu."""
    echo = bytes([0xFE, 0xFE, ADDR, CTRL, 0x1C, 0x00, 0x01, 0xFD])
    _, radio = _radio(echo)
    assert radio.set_ptt(True)['ok'] is False


# ─── Même protocole pour les deux autres écritures ──────────────────────────

def test_la_frequence_est_acceptee_sur_un_accuse_fb():
    """set_freq souffrait du même défaut : le QSY partait bien vers le poste,
    et le logiciel annonçait un échec."""
    poste, radio = _radio()
    assert radio.set_freq(14074000)['ok'] is True
    trame = poste.recu[-1]
    assert trame[:5] == bytes([0xFE, 0xFE, ADDR, CTRL, 0x05])


def test_la_frequence_est_refusee_sur_un_accuse_fa():
    _, radio = _radio(ACCUSE_NG)
    res = radio.set_freq(14074000)
    assert res['ok'] is False and res.get('error')


def test_le_mode_est_accepte_sur_un_accuse_fb():
    poste, radio = _radio()
    assert radio.set_mode('USB')['ok'] is True
    assert any(t[4] == 0x06 for t in poste.recu if len(t) > 4), \
        'la commande 06 (mode) doit avoir été envoyée'


def test_le_mode_est_refuse_sur_un_accuse_fa():
    _, radio = _radio(ACCUSE_NG)
    res = radio.set_mode('USB')
    assert res['ok'] is False and res.get('error')


# ─── Les LECTURES gardent leur contrôle strict ──────────────────────────────

def test_une_lecture_exige_toujours_le_reecho_de_la_commande():
    """Le correctif ne doit PAS relâcher le contrôle des lectures : sur un bus
    CI-V partagé (LogX + WSJT-X + N1MM via un séparateur), tous les logiciels
    utilisent l'adresse contrôleur E0. Sans vérifier cmd/sub, get_ptt()
    pourrait lire la réponse d'un AUTRE logiciel à SA propre requête — des
    octets de fréquence BCD pris pour un booléen PTT. Un accusé FB ne doit
    donc jamais satisfaire une lecture."""
    _, radio = _radio(ACCUSE_OK)
    res = radio.get_ptt()
    assert res['ok'] is False, 'un accusé FB ne répond pas à une LECTURE'


def test_une_lecture_valide_est_toujours_acceptee():
    """Contrôle en sens inverse : une vraie réponse de lecture (qui rééchote
    bien 1C 00 avec la donnée) reste acceptée — le correctif n'a pas cassé le
    chemin GET."""
    reponse = bytes([0xFE, 0xFE, CTRL, ADDR, 0x1C, 0x00, 0x01, 0xFD])
    _, radio = _radio(reponse)
    assert radio.get_ptt() == {'ok': True, 'ptt': True}


# ─── L'échec ne doit jamais être muet ───────────────────────────────────────

def test_aucun_echec_d_ecriture_n_est_muet():
    """L'endpoint /rig/ptt renvoyait littéralement {"ok": false} — sans la
    moindre explication. Constaté en interrogeant l'instance en service :
    impossible pour l'opérateur, comme pour qui dépanne, de savoir si le poste
    a refusé, s'il est débranché ou si l'adresse CI-V est fausse."""
    for reponse in (ACCUSE_NG, b'', b'\xFE\xFE\xFF\xFF\xFD'):
        _, radio = _radio(reponse)
        for res in (radio.set_ptt(True), radio.set_freq(14074000), radio.set_mode('USB')):
            assert res['ok'] is False
            assert res.get('error'), f'échec muet pour la réponse {reponse!r}'
