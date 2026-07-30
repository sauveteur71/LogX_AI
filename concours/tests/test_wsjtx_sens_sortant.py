# -*- coding: utf-8 -*-
"""Liaison WSJT-X : le sens SORTANT, sans lequel rien de Wait-and-Pounce n'existe.

La liaison était en écoute seule. Or les quatre niveaux demandés par
l'utilisateur — signaler, armer, appeler seul, tourner sans personne devant la
radio — reposent tous sur UN seul message : « Reply » (type 4), qui demande à
WSJT-X de répondre à un décodage précis. C'est l'équivalent exact d'un
double-clic sur la ligne du waterfall : LogX ne fabrique jamais de signal
radio, WSJT-X reste maître de ce qui part sur l'air.

LE PIÈGE DE FORMAT, silencieux par nature. Qt sérialise en DOUBLE précision :
un champ déclaré `float` dans WSJT-X occupe HUIT octets sur le fil. Écrire
quatre octets décale tout ce qui suit, et WSJT-X jette le datagramme sans le
moindre message d'erreur — on croirait simplement que « ça ne marche pas ».
D'où la façon de tester ci-dessous : plutôt que de faire confiance à une
documentation, on ÉCRIT un message avec _Writer puis on le relit avec le
parseur DÉJÀ EN PRODUCTION du projet. S'ils ne s'accordent pas, un test tombe.

CE QUE LE PARSEUR JETAIT. Heure, SNR et delta temps du décodage étaient lus
puis abandonnés. WSJT-X s'en sert pour retrouver la ligne visée : sans eux,
aucun Reply ne peut désigner quoi que ce soit. Les conserver était le vrai
prérequis, plus encore que l'encodeur.
"""
import os
import struct
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_wsjtx as w   # noqa: E402


def _decode_brut(time_ms=42123456 % 86400000, snr=-11, dt=0.24, delta_hz=1234,
                 mode='FT8', message='CQ F4GLD JN15', wsjtx_id='WSJT-X',
                 schema=2, neuf=1):
    """Fabrique un datagramme « Decode » (type 2) avec l'écriteur du projet."""
    e = w._Writer()
    e.u32(w.MAGIC).u32(schema).u32(2).utf8(wsjtx_id)
    e.u8(neuf).u32(time_ms).i32(snr).f64(dt).u32(delta_hz)
    e.utf8(mode).utf8(message)
    return e.octets()


# ─── L'écriteur et le lecteur parlent-ils la MÊME langue ? ───────────────────

def test_ECRIRE_PUIS_RELIRE_avec_le_parseur_de_production():
    """La vérification qui compte. Si _Writer et _Reader divergeaient d'un seul
    octet, ce test tomberait — alors qu'en production la panne serait muette."""
    data = _decode_brut(time_ms=45296000, snr=-7, dt=0.32, delta_hz=1502,
                        mode='FT4', message='F4GLD DL1ABC JO40')
    msg = w.parse_message(data)
    assert msg['type'] == 'decode'
    assert msg['time_ms'] == 45296000
    assert msg['snr'] == -7
    assert msg['dt'] == pytest.approx(0.32)
    assert msg['delta_hz'] == 1502
    assert msg['mode'] == 'FT4'
    assert msg['message'] == 'F4GLD DL1ABC JO40'


def test_LE_DELTA_TEMPS_TIENT_SUR_HUIT_OCTETS():
    """Verrouille le piège Qt. Un `float` déclaré côté WSJT-X est sérialisé en
    DOUBLE : huit octets. Si quelqu'un « optimisait » en 4 octets, tout ce qui
    suit se décalerait et WSJT-X jetterait nos messages en silence."""
    huit = w._Writer().f64(0.25).octets()
    assert len(huit) == 8
    assert struct.unpack('>d', huit)[0] == 0.25


def test_l_identifiant_d_instance_est_desormais_remonte():
    """Il était lu puis jeté. WSJT-X ignore tout message qui ne porte pas SON
    identifiant : sans lui, on ne peut répondre à personne."""
    msg = w.parse_message(_decode_brut(wsjtx_id='WSJT-X -- station 2'))
    assert msg['wsjtx_id'] == 'WSJT-X -- station 2'
    assert msg['schema'] == 2


def test_le_schema_annonce_par_WSJT_X_est_conserve():
    assert w.parse_message(_decode_brut(schema=3))['schema'] == 3


# ─── Le message Reply ────────────────────────────────────────────────────────

def _relire_reply(data):
    """Relit un Reply selon sa disposition documentée, avec le lecteur du
    projet — donc avec les mêmes primitives que celles qui l'ont écrit."""
    r = w._Reader(data)
    entete = {'magic': r.u32(), 'schema': r.u32(), 'type': r.u32(), 'id': r.utf8()}
    return entete, {'time_ms': r.u32(), 'snr': r.i32(), 'dt': r.f64(),
                    'delta_hz': r.u32(), 'mode': r.utf8(), 'message': r.utf8(),
                    'low_confidence': r.u8(), 'modifiers': r.u8()}


def test_UN_REPLY_RENVOIE_LE_DECODAGE_A_L_IDENTIQUE():
    """WSJT-X retrouve la ligne visée par ces champs. Une heure arrondie ou un
    delta approximatif, et il ne reconnaît rien — sans erreur visible."""
    d = w.parse_message(_decode_brut(time_ms=45296000, snr=-7, dt=0.32,
                                     delta_hz=1502, mode='FT4',
                                     message='F4GLD DL1ABC JO40'))
    entete, champs = _relire_reply(w.construire_reply(d, d['wsjtx_id'], d['schema']))
    assert entete == {'magic': w.MAGIC, 'schema': 2, 'type': 4, 'id': 'WSJT-X'}
    assert champs['time_ms'] == 45296000
    assert champs['snr'] == -7
    assert champs['dt'] == pytest.approx(0.32)
    assert champs['delta_hz'] == 1502
    assert champs['mode'] == 'FT4'
    assert champs['message'] == 'F4GLD DL1ABC JO40'


def test_le_reply_porte_l_identifiant_de_L_INSTANCE_visee():
    """En multi-instance (deux WSJT-X sur le même PC), répondre à la mauvaise
    reviendrait à faire émettre la mauvaise radio."""
    d = w.parse_message(_decode_brut(wsjtx_id='WSJT-X-2'))
    entete, _ = _relire_reply(w.construire_reply(d, d['wsjtx_id'], d['schema']))
    assert entete['id'] == 'WSJT-X-2'


def test_un_decodage_incomplet_ne_fait_pas_lever():
    """Le décodage peut venir d'un cache ancien, d'avant que les champs soient
    conservés. On veut un message par défaut, pas une exception dans le thread
    UDP — ce thread mort, tout l'auto-log s'arrête."""
    entete, champs = _relire_reply(w.construire_reply({}, 'WSJT-X'))
    assert entete['type'] == 4
    assert champs['time_ms'] == 0 and champs['snr'] == 0
    assert champs['mode'] == '' and champs['message'] == ''


@pytest.mark.parametrize('msg', ['CQ F4GLD JN15', 'F4GLD ØN4ABC -12', '',
                                 'A' * 60, 'CQ DX 4U1ITU/P'])
def test_les_messages_traversent_sans_alteration(msg):
    d = w.parse_message(_decode_brut(message=msg))
    _, champs = _relire_reply(w.construire_reply(d, 'WSJT-X'))
    assert champs['message'] == msg


# ─── Le coupe-circuit ────────────────────────────────────────────────────────

@pytest.mark.parametrize('auto_seulement,attendu', [(True, 1), (False, 0)])
def test_halt_tx_porte_bien_son_drapeau(auto_seulement, attendu):
    """Les deux formes sont nécessaires : désarmer l'automatique en laissant
    finir la séquence, ou couper net quand l'opérateur reprend la main."""
    data = w.construire_halt_tx('WSJT-X', auto_seulement)
    r = w._Reader(data)
    assert r.u32() == w.MAGIC
    r.u32()
    assert r.u32() == 8
    assert r.utf8() == 'WSJT-X'
    assert r.u8() == attendu


def test_les_constantes_de_type_sont_celles_du_protocole():
    """4 et 8 ne sont pas des choix : ce sont les numéros du protocole WSJT-X.
    Les changer romprait toute communication, sans message d'erreur."""
    assert (w.TYPE_REPLY, w.TYPE_HALT_TX) == (4, 8)


# ─── Non-régression du sens ENTRANT ──────────────────────────────────────────

def test_le_status_et_le_qso_logged_lisent_toujours_pareil():
    """L'en-tête a changé (l'id est désormais conservé) : les autres types de
    messages ne doivent pas en souffrir."""
    e = w._Writer()
    e.u32(w.MAGIC).u32(2).u32(1).utf8('WSJT-X')
    e.parts.append(struct.pack('>Q', 14074000))     # dial Hz (u64)
    e.utf8('FT8').utf8('DL1ABC').utf8('-10').utf8('FT8')
    msg = w.parse_message(e.octets())
    assert msg['type'] == 'status'
    assert msg['dial_mhz'] == pytest.approx(14.074)
    assert msg['mode'] == 'FT8' and msg['wsjtx_id'] == 'WSJT-X'


def test_un_datagramme_tronque_rend_None_sans_lever():
    """Défaut déjà corrigé une fois : une exception ici TUE le thread d'écoute
    et l'auto-log s'arrête jusqu'au redémarrage."""
    complet = _decode_brut()
    for n in range(0, len(complet), 7):
        # Ce qui est vérifié ici est l'ABSENCE D'EXCEPTION : la valeur rendue
        # importe peu (None, ou un dict incomplet pour une troncature tardive).
        # Écrire un assert dessus donnerait un test qui a l'air de contrôler
        # quelque chose sans rien contrôler.
        w.parse_message(complet[:n])
    assert w.parse_message(b'') is None
    assert w.parse_message(b'\x00' * 12) is None
