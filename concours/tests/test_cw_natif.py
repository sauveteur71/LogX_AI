# -*- coding: utf-8 -*-
"""Manipulation CW en mode natif (commande KY, Kenwood et Elecraft).

Le mode « Natif (recommandé) » est celui que la page CONFIG pousse par défaut
pour Icom, Yaesu, Kenwood, Elecraft et Xiegu. Il refusait pourtant TOUT envoi
CW : « Envoi CW non disponible en mode Natif ». Concrètement, un opérateur CW
dans la configuration recommandée n'avait aucune manipulation — ESM se
contentait de copier le texte dans le presse-papier. Sans manipulation, il n'y
a pas de concours CW possible : Coupe du REF CW, IARU, Marconi, CQ WW CW.

Ces tests pilotent un transport factice et vérifient les OCTETS réellement
envoyés à la radio. Ils ne remplacent pas un essai sur un poste réel : aucune
radio n'a été branchée ici.
"""
import os
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_cat as cat  # noqa: E402


class FauxTransport:
    """Note tout ce qui part vers la radio."""

    def __init__(self):
        self.ecrits = []

    def write(self, data):
        self.ecrits.append(data.decode('ascii'))

    def read_until(self, sep, timeout=1.0):
        return b';'

    def commandes(self):
        return ''.join(self.ecrits)


def _radio(brand):
    t = FauxTransport()
    return cat.AsciiRadio(t, brand), t


# ─── Envoi ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize('brand', ['kenwood', 'elecraft'])
def test_le_texte_part_dans_une_commande_KY(brand):
    r, t = _radio(brand)
    res = r.send_cw('CQ TEST F4GLD')
    assert res['ok']
    assert t.commandes() == 'KY CQ TEST F4GLD;'


@pytest.mark.parametrize('brand', ['yaesu', 'icom'])
def test_les_marques_non_couvertes_refusent_explicitement(brand):
    """Yaesu est volontairement absent : la commande existe sur certains
    modèles avec une sémantique différente (mémoires du keyer), et se tromper
    enverrait n'importe quoi sur l'air."""
    r, t = _radio(brand)
    res = r.send_cw('CQ')
    assert not res['ok']
    assert 'WinKeyer' in res['error'] or 'rigctld' in res['error']
    assert t.ecrits == [], "rien ne doit partir vers une radio non couverte"


def test_le_texte_est_mis_en_majuscules():
    r, t = _radio('kenwood')
    r.send_cw('cq de f4gld')
    assert t.commandes() == 'KY CQ DE F4GLD;'


def test_les_caracteres_non_manipulables_sont_ecartes():
    """Un caractère refusé peut faire ignorer la commande ENTIÈRE par la
    radio, donc perdre tout le message : on filtre plutôt que d'envoyer."""
    r, t = _radio('kenwood')
    res = r.send_cw('CQ\x00 TEST\n «F4GLD»')
    assert res['ok']
    assert t.commandes() == 'KY CQ TEST F4GLD;'


def test_les_espaces_multiples_sont_reduits():
    r, t = _radio('elecraft')
    r.send_cw('CQ    TEST')
    assert t.commandes() == 'KY CQ TEST;'


def test_un_texte_vide_apres_filtrage_est_refuse():
    r, t = _radio('kenwood')
    res = r.send_cw('«»\x01')
    assert not res['ok']
    assert t.ecrits == []


@pytest.mark.parametrize('texte', ['', None, '   '])
def test_texte_absent(texte):
    r, t = _radio('kenwood')
    assert not r.send_cw(texte)['ok']
    assert t.ecrits == []


def test_un_message_long_est_decoupe_a_la_taille_du_tampon():
    """Le tampon KY accepte 24 caractères : au-delà, la radio tronque ou
    refuse. Le découpage doit être fait ici."""
    r, t = _radio('kenwood')
    texte = 'A' * 60
    res = r.send_cw(texte)
    assert res['ok']
    envois = [c for c in t.commandes().split(';') if c]
    assert len(envois) == 3
    assert all(len(c) - len('KY ') <= cat.AsciiRadio.CW_CHUNK for c in envois)
    assert ''.join(c[len('KY '):] for c in envois) == texte


def test_les_caracteres_de_service_du_trafic_passent():
    """« / » (portable), « ? » (répétition) et « = » (BT) sont courants en
    concours : les filtrer casserait des macros usuelles."""
    r, t = _radio('kenwood')
    r.send_cw('F4GLD/P ? = 599')
    assert t.commandes() == 'KY F4GLD/P ? = 599;'


# ─── Arrêt ───────────────────────────────────────────────────────────────────

def test_l_arret_vide_le_tampon_et_repasse_en_reception():
    """Sans le RX final, une radio dont le tampon était déjà vide pourrait
    rester en émission."""
    r, t = _radio('elecraft')
    assert r.stop_cw()['ok']
    assert t.commandes() == 'KY0;RX;'


def test_l_arret_refuse_sur_une_marque_non_couverte():
    r, t = _radio('yaesu')
    assert not r.stop_cw()['ok']
    assert t.ecrits == []


# ─── Dispatch au niveau module ───────────────────────────────────────────────

def test_envoi_refuse_si_le_pilotage_natif_est_inactif():
    res = cat.send_cw({}, 'CQ')
    assert not res['ok'] and 'natif' in res['error'].lower()


def test_icom_nomme_la_cause_et_la_solution(monkeypatch):
    """CI-V ne publie pas de commande d'envoi de texte CW. Le refus doit le
    dire, sinon l'utilisateur cherche une panne qui n'existe pas."""
    class CivSansCw:
        pass

    monkeypatch.setattr(cat, 'cat_settings',
                        lambda cfg: {'enabled': True, 'mode': 'native'})
    monkeypatch.setattr(cat, '_ensure_connected', lambda s: (CivSansCw(), None))
    res = cat.send_cw({}, 'CQ')
    assert not res['ok']
    assert 'CI-V' in res['error'] and 'WinKeyer' in res['error']


def test_une_radio_injoignable_ne_leve_pas(monkeypatch):
    """Cet appel vient du handler HTTP : il doit toujours rendre un dict."""
    class RadioCassee:
        def send_cw(self, text):
            raise OSError('port ferme')

    monkeypatch.setattr(cat, 'cat_settings',
                        lambda cfg: {'enabled': True, 'mode': 'native'})
    monkeypatch.setattr(cat, '_ensure_connected', lambda s: (RadioCassee(), None))
    monkeypatch.setattr(cat, 'disconnect_persistent', lambda: None)
    res = cat.send_cw({}, 'CQ')
    assert res['ok'] is False and 'injoignable' in res['error']


def test_le_serveur_ne_refuse_plus_le_cw_en_natif():
    """Garde-fou : le refus en dur a été remplacé par un vrai dispatch."""
    with open(os.path.join(CONCOURS, 'logx_http.py'), encoding='utf-8') as f:
        src = f.read()
    assert 'Envoi CW non disponible en mode "Natif"' not in src, \
        "le refus inconditionnel du CW en mode natif est revenu"
    assert 'cat.send_cw(' in src
