# -*- coding: utf-8 -*-
"""Wait-and-Pounce niveau 2 : « armer le coup », sans jamais émettre tout seul.

CE QUE FAIT CE NIVEAU. Un clic sur un indicatif entendu demande à WSJT-X de
PRÉPARER la réponse — indicatif rempli, décalage audio calé — exactement comme
un double-clic sur la ligne du waterfall. C'est ENSUITE l'opérateur qui appuie
sur Enable TX. LogX ne fabrique aucun signal radio et ne déclenche aucune
émission : cette frontière est le sujet du niveau 3, pas de celui-ci.

CE QUI MANQUAIT, et qui était jeté par l'écouteur : l'adresse d'où parle
WSJT-X. Il n'annonce nulle part son port d'écoute — la seule façon de le
connaître est de regarder d'où viennent ses datagrammes. On répond depuis LA
SOCKET D'ÉCOUTE, pas une socket neuve : le port source changerait, ce que
WSJT-X et les pare-feu n'aiment ni l'un ni l'autre.

CHAQUE REFUS DIT POURQUOI. « Rien ne se passe » après un clic est le retour le
plus décourageant qui soit : on ne sait pas si le logiciel est en panne, si la
station n'est plus là, ou si on a mal cliqué. Les quatre causes possibles sont
donc distinguées et testées une par une.
"""
import os
import sys
import time

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_wsjtx as w   # noqa: E402


class _SocketFactice:
    """Retient ce qui est envoyé, au lieu de l'envoyer."""

    def __init__(self, casse=False):
        self.envois = []
        self.casse = casse

    def sendto(self, data, peer):
        if self.casse:
            raise OSError('reseau injoignable')
        self.envois.append((data, peer))


@pytest.fixture(autouse=True)
def liaison_propre(monkeypatch):
    """Chaque test repart d'un état vierge : le cache de décodages et la
    liaison sont des variables de module, donc partagées entre tests."""
    monkeypatch.setattr(w, '_decodes', {})
    monkeypatch.setattr(w, '_liaison',
                        {'sock': None, 'peer': None, 'wsjtx_id': '', 'schema': 2})
    return None


def _entendre(call='DL1ABC', message='CQ DL1ABC JO40', age=0.0, complet=True):
    """Place un décodage dans le cache, comme l'aurait fait record_decode."""
    e = {'band': '14', 'freq_mhz': 14.074, 'mode': 'FT8',
         'last_seen': time.time() - age, 'grid': 'JO40'}
    if complet:
        e.update({'time_ms': 45296000, 'snr': -7, 'dt': 0.32, 'delta_hz': 1502,
                  'message': message, 'wsjtx_id': 'WSJT-X', 'schema': 2})
    w._decodes[call] = e
    return e


def _liaison_ok(casse=False):
    s = _SocketFactice(casse)
    w._liaison.update({'sock': s, 'peer': ('127.0.0.1', 2237),
                       'wsjtx_id': 'WSJT-X', 'schema': 2})
    return s


# ─── Le cas nominal ──────────────────────────────────────────────────────────

def test_armer_envoie_un_REPLY_a_la_bonne_adresse():
    _entendre()
    s = _liaison_ok()
    res = w.repondre_a('DL1ABC')
    assert res['ok'] is True and res['call'] == 'DL1ABC'
    (data, peer), = s.envois
    assert peer == ('127.0.0.1', 2237)
    r = w._Reader(data)
    assert r.u32() == w.MAGIC
    r.u32()
    assert r.u32() == w.TYPE_REPLY


def test_le_reply_renvoie_le_decodage_visé_a_l_identique():
    """C'est par ces champs que WSJT-X retrouve la ligne. Approximer l'un
    d'eux, c'est un clic qui ne fait rien — sans erreur."""
    _entendre(message='CQ DL1ABC JO40')
    s = _liaison_ok()
    w.repondre_a('DL1ABC')
    r = w._Reader(s.envois[0][0])
    r.u32(); r.u32(); r.u32(); r.utf8()          # en-tête
    assert r.u32() == 45296000                    # heure
    assert r.i32() == -7                          # SNR
    assert r.f64() == pytest.approx(0.32)         # delta temps
    assert r.u32() == 1502                        # delta Hz
    assert r.utf8() == 'FT8'
    assert r.utf8() == 'CQ DL1ABC JO40'


def test_l_indicatif_est_normalise():
    _entendre()
    _liaison_ok()
    assert w.repondre_a(' dl1abc ')['ok'] is True


# ─── Les quatre refus, chacun avec SA raison ─────────────────────────────────

def test_refus_indicatif_vide():
    _liaison_ok()
    for vide in ('', '   ', None):
        res = w.repondre_a(vide)
        assert res['ok'] is False and 'manquant' in res['error'].lower()


def test_refus_station_jamais_entendue():
    _liaison_ok()
    res = w.repondre_a('ZZ9ZZZ')
    assert res['ok'] is False and 'pas entendu' in res['error']


def test_REFUS_DECODAGE_PERIME_plutot_qu_un_clic_sans_effet():
    """Un décodage de plus de deux minutes ne désigne plus rien pour WSJT-X :
    les cycles FT8 durent 15 s. Envoyer quand même ne provoque AUCUNE erreur —
    simplement rien ne se passe, ce qui est le pire des retours."""
    _entendre(age=w.AGE_MAX_REPONSE_S + 10)
    s = _liaison_ok()
    res = w.repondre_a('DL1ABC')
    assert res['ok'] is False and 'ne le connait plus' in res['error']
    assert s.envois == [], 'rien ne doit partir sur un decodage perime'


def test_refus_liaison_absente_avec_le_reglage_a_verifier():
    """Sans datagramme reçu, on ignore à quelle adresse parler. Le message doit
    pointer le réglage exact plutôt que de dire « erreur »."""
    _entendre()
    res = w.repondre_a('DL1ABC')
    assert res['ok'] is False
    assert 'Reglages' in res['error'] and 'Rapports' in res['error']


def test_refus_decodage_sans_les_champs_bruts():
    """Décodage mémorisé avant que les champs soient conservés : on ne peut pas
    fabriquer un Reply qui désigne quoi que ce soit."""
    _entendre(complet=False)
    s = _liaison_ok()
    res = w.repondre_a('DL1ABC')
    assert res['ok'] is False and 'trop ancien' in res['error']
    assert s.envois == []


def test_une_panne_reseau_est_rapportee_pas_avalee():
    _entendre()
    _liaison_ok(casse=True)
    res = w.repondre_a('DL1ABC')
    assert res['ok'] is False and 'Envoi impossible' in res['error']


# ─── Le coupe-circuit ────────────────────────────────────────────────────────

def test_couper_envoie_un_HALT_TX():
    s = _liaison_ok()
    assert w.couper_emission()['ok'] is True
    r = w._Reader(s.envois[0][0])
    r.u32(); r.u32()
    assert r.u32() == w.TYPE_HALT_TX


def test_couper_fonctionne_MEME_sans_decodage_en_cache():
    """Le coupe-circuit ne doit dépendre de rien : il sert précisément quand le
    reste ne va pas."""
    s = _liaison_ok()
    assert w._decodes == {}
    assert w.couper_emission()['ok'] is True and len(s.envois) == 1


def test_couper_sans_liaison_le_dit_au_lieu_de_pretendre():
    res = w.couper_emission()
    assert res['ok'] is False and 'liaison' in res['error'].lower()


# ─── L'invariant du niveau 2 ─────────────────────────────────────────────────

def test_LE_NIVEAU_2_N_EMET_JAMAIS_DE_LUI_MEME():
    """L'invariant de ce niveau, verrouillé sur la source : recevoir un
    décodage ne doit RIEN envoyer. Seul un geste explicite — repondre_a — le
    fait. Le jour où record_decode appellera repondre_a, ce sera le niveau 3,
    et ce test devra être révisé sciemment, pas contourné."""
    src = open(os.path.join(CONCOURS, 'logx_wsjtx.py'), encoding='utf-8').read()
    bloc = src[src.index('def record_decode'):src.index('# ─── NIVEAU 2')]
    assert 'repondre_a' not in bloc
    assert 'sendto' not in bloc


def test_la_liaison_se_note_a_la_reception():
    """C'est le seul moyen de connaître l'adresse de WSJT-X : il n'annonce
    jamais son port d'écoute."""
    assert w.liaison_prete() is False
    w._noter_liaison('SOCKET', ('192.168.1.9', 2237),
                     {'wsjtx_id': 'WSJT-X-2', 'schema': 3})
    assert w.liaison_prete() is True
    assert w._liaison['wsjtx_id'] == 'WSJT-X-2' and w._liaison['schema'] == 3
