# -*- coding: utf-8 -*-
"""FT8 : JTDX et MSHV, pas seulement WSJT-X.

DEMANDE DE F4GLD (01/08/2026) : « pour le FT8 prendre en compte MSHV et JTDX ».

CE QUE LA VÉRIFICATION A MONTRÉ : côté protocole, il n'y avait RIEN à faire.
JTDX (fork de WSJT-X) et MSHV émettent sur le même protocole UDP, avec le même
nombre magique, et le module ne filtre pas sur l'identité de l'émetteur — les
trois étaient donc déjà acceptés. Le vrai manque était ailleurs : le logiciel
affichait « WSJT-X » quoi qu'il arrive, si bien qu'un opérateur sous JTDX ou
MSHV n'avait aucun moyen de savoir que sa liaison fonctionnait.

Ces tests figent les deux choses : que les datagrammes des trois logiciels sont
lus à l'identique, et que le nom du logiciel réellement connecté remonte
jusqu'à l'écran.

CE QUI RESTE À VÉRIFIER SUR LE TERRAIN, et que ces tests ne prouvent PAS :
l'identifiant exact qu'envoie MSHV, et s'il honore les messages « Reply » que
LogX peut lui renvoyer (le Wait-and-Pounce). Cela demande le vrai logiciel en
face — les datagrammes ci-dessous sont fabriqués d'après le format, pas
capturés sur une vraie session.
"""
import os
import struct
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_wsjtx as W   # noqa: E402


def _utf8(s):
    b = s.encode('utf-8')
    return struct.pack('>I', len(b)) + b


def _status(soft, dial_hz=14074000, mode='FT8'):
    return (struct.pack('>III', W.MAGIC, 2, 1) + _utf8(soft)
            + struct.pack('>Q', dial_hz) + _utf8(mode) + _utf8('') + _utf8('')
            + _utf8(mode))


def _decode(soft, message='CQ DL2ABC JO31', dt=0.3, snr=-11):
    return (struct.pack('>III', W.MAGIC, 2, 2) + _utf8(soft) + b'\x01'
            + struct.pack('>I', 43200000) + struct.pack('>i', snr)
            + struct.pack('>d', dt) + struct.pack('>I', 1200)
            + _utf8('~') + _utf8(message) + b'\x00' + b'\x00')


# Les identifiants tels qu'ils circulent réellement. MSHV en publie plusieurs
# selon la version — d'où la variante versionnée, pour interdire tout filtrage
# par égalité stricte sur un nom.
LOGICIELS = ['WSJT-X', 'JTDX', 'MSHV', 'MSHV_Ver2.71', 'JS8Call']


@pytest.mark.parametrize('soft', LOGICIELS)
def test_le_message_de_statut_est_lu_quel_que_soit_le_logiciel(soft):
    m = W.parse_message(_status(soft))
    assert m is not None, '%s refusé' % soft
    assert m['type'] == 'status'
    assert m['dial_mhz'] == 14.074 and m['mode'] == 'FT8'
    assert m['wsjtx_id'] == soft


@pytest.mark.parametrize('soft', LOGICIELS)
def test_un_decodage_est_lu_quel_que_soit_le_logiciel(soft):
    m = W.parse_message(_decode(soft))
    assert m is not None, '%s refusé' % soft
    assert m['type'] == 'decode'
    assert m['snr'] == -11
    assert abs(m['dt'] - 0.3) < 1e-9
    assert m['wsjtx_id'] == soft


@pytest.mark.parametrize('soft', LOGICIELS)
def test_un_decodage_MSHV_ou_JTDX_alimente_le_cache_et_l_horloge(soft):
    """Le reste de la chaîne ne doit pas être réservé à WSJT-X : indicatifs
    entendus ET flux de DT (dérive d'horloge) doivent se remplir pareil."""
    W._dt_echantillons.clear()
    calls = W.record_decode(W.parse_message(_decode(soft)), my_call='F4GLD')
    assert calls == ['DL2ABC']
    assert len(W._dt_echantillons) == 1
    W._dt_echantillons.clear()


def test_la_reponse_renvoie_l_identifiant_DE_L_EMETTEUR():
    """Un message « Reply » doit porter l'identifiant du logiciel visé : envoyer
    « WSJT-X » à MSHV le ferait ignorer en silence."""
    d = W.parse_message(_decode('MSHV'))
    trame = W.construire_reply(d, d['wsjtx_id'], d['schema'])
    assert b'MSHV' in trame
    assert trame[:4] == struct.pack('>I', W.MAGIC)


def test_un_logiciel_inconnu_n_est_pas_refuse_par_principe():
    """Le protocole est public : d'autres logiciels l'implémentent. Filtrer sur
    une liste de noms connus serait la même erreur que les listes
    d'identifiants de concours — elle périme."""
    assert W.parse_message(_status('UnFuturLogicielFT8')) is not None


def test_un_datagramme_d_un_AUTRE_protocole_est_ignore():
    """Accepter tout le monde ne veut pas dire accepter n'importe quoi : sans
    le bon nombre magique, ce n'est pas ce protocole."""
    assert W.parse_message(struct.pack('>III', 0x12345678, 2, 1) + _utf8('X')) is None
    assert W.parse_message(b'') is None
    assert W.parse_message(b'trop court') is None


# ─── Ce que l'écran doit dire ───────────────────────────────────────────────

def _lire(nom):
    with open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        return f.read()


def test_l_etat_transporte_le_nom_du_logiciel():
    assert 'soft' in W.status, "l'état doit porter le logiciel connecté"


def test_le_logbook_affiche_le_logiciel_reellement_connecte():
    # EV-7 phase 2 : applyWsjtxState() a rejoint logx_hardware_cat.js.
    js = _lire('logx_hardware_cat.js')
    assert 'd.soft' in js, (
        "le widget affichait « WSJT-X » quoi qu'il arrive : un opérateur sous "
        'JTDX ou MSHV ne pouvait pas savoir que sa liaison fonctionnait')


@pytest.mark.parametrize('mot', ['JTDX', 'MSHV'])
def test_la_page_CONFIG_annonce_les_trois_logiciels(mot):
    """Le support existait déjà mais n'était écrit nulle part — c'est
    précisément ce qui a fait poser la question."""
    assert mot in _lire('logx_configuration.html')
