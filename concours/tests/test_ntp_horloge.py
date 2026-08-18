# -*- coding: utf-8 -*-
"""Mesure d'horloge SNTP (logx_ntp.py) + son intégration dans la page FT8.

Demandée par F4GLD le 18/08/2026 après « est-ce possible d'intégrer NetTime
directement dans le programme ? ». Réponse retenue : non — Windows, macOS et
Linux ont déjà un client NTP, embarquer un binaire tiers serait Windows-only,
et régler l'horloge système demande les droits administrateur. En revanche
MESURER l'écart et le DIRE ne demande rien de tout ça.

Ce que ces tests protègent en priorité, dans l'ordre :
  1. les contraintes PRODUIT (optionnel, aucun service tiers obligatoire,
     aucune donnée personnelle émise) — elles ne se voient pas à l'exécution,
     donc seul un test les tient dans la durée ;
  2. le décodage de la trame et le calcul d'écart, sur des octets construits
     à la main d'après la RFC ;
  3. le fait qu'une panne réseau ne lève jamais.

Les trames sont fabriquées ici SANS passer par le module testé — sinon on le
vérifierait avec lui-même. Piège déjà rencontré dans ce dépôt avec le
simulateur CI-V, qui répondait comme le code l'attendait et masquait un vrai
défaut pendant des mois.
"""
import os
import re
import struct
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_ntp  # noqa: E402

FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')
HTTP_PY = os.path.join(CONCOURS, 'logx_http.py')

# RFC 5905 §6 : secondes entre le 1er janvier 1900 et le 1er janvier 1970.
ERE = 2208988800


def _horodatage(secondes_posix):
    """Secondes POSIX -> horodatage NTP 64 bits (32.32), à la main."""
    total = secondes_posix + ERE
    entier = int(total)
    fraction = int((total - entier) * 2 ** 32)
    return struct.pack('!II', entier, fraction)


def _reponse_serveur(t2, t3, mode=4, strate=2, ref=b'\x00\x00\x00\x00'):
    """Trame de 48 octets telle qu'un serveur NTP la renvoie (RFC 5905 §7.3)."""
    paquet = bytearray(48)
    paquet[0] = (0 << 6) | (4 << 3) | mode
    paquet[1] = strate
    paquet[12:16] = ref
    paquet[32:40] = _horodatage(t2)
    paquet[40:48] = _horodatage(t3)
    return bytes(paquet)


class FauxSocket:
    """Remplace socket.socket : rend la trame voulue, ou lève l'erreur voulue."""

    def __init__(self, reponse=None, erreur=None, sur_envoi=None):
        self.reponse = reponse
        self.erreur = erreur
        self.sur_envoi = sur_envoi   # appelé avec les octets envoyés
        self.ferme = False

    def settimeout(self, t):
        pass

    def sendto(self, data, addr):
        if self.sur_envoi:
            self.sur_envoi(data)
        if self.erreur:
            raise self.erreur

    def recvfrom(self, n):
        if self.erreur:
            raise self.erreur
        return self.reponse, ('127.0.0.1', 123)

    def close(self):
        self.ferme = True


@pytest.fixture
def poser_socket(monkeypatch):
    def _poser(faux):
        monkeypatch.setattr(logx_ntp.socket, 'socket', lambda *a, **k: faux)
        return faux
    return _poser


# ─── Contraintes produit — ce qui ne se voit pas à l'exécution ──────────────

def test_aucune_donnee_personnelle_n_est_emise(poser_socket):
    """Une requête SNTP client est un paquet de 48 octets dont seul le premier
    est renseigné. Aucun indicatif, aucune position, aucun identifiant : c'est
    la requête réseau la plus anodine du logiciel, et ce test l'y maintient."""
    envoye = []
    faux = FauxSocket(reponse=_reponse_serveur(1000.0, 1000.01),
                      sur_envoi=envoye.append)
    poser_socket(faux)
    logx_ntp.interroger('exemple.test')
    assert len(envoye) == 1
    paquet = envoye[0]
    assert len(paquet) == 48
    # Premier octet : LI=0, VN=4, Mode=3 (client) — RFC 5905 §7.3.
    assert paquet[0] == 0b00_100_011
    assert paquet[1:] == b'\x00' * 47, 'aucun octet ne doit porter de donnée'


def test_la_mesure_est_desactivee_par_defaut():
    """Contrainte d'autonomie : aucun service tiers OBLIGATOIRE. L'endpoint
    doit refuser tant que l'opérateur n'a pas activé la mesure, et le refus
    doit dire où l'activer plutôt que d'échouer sèchement."""
    with open(HTTP_PY, encoding='utf-8') as f:
        src = f.read()
    bloc = src[src.index("if path == '/data/horloge':"):]
    bloc = bloc[:bloc.index('\n        # ', 10)]
    assert "cfg_snap.get('ntp_enabled')" in bloc, \
        'la mesure doit être conditionnée à un réglage explicite'
    assert 'CONFIG' in bloc, 'le refus doit indiquer où activer'
    # L'import ne doit se faire QU'APRÈS le contrôle : pas de module réseau
    # chargé pour rien chez quelqu'un qui n'en veut pas.
    assert bloc.index("cfg_snap.get('ntp_enabled')") < bloc.index('import logx_ntp')


def test_le_serveur_est_remplacable():
    """Un radio-club derrière un pare-feu strict doit pouvoir pointer son
    propre serveur : aucune adresse ne doit être codée en dur sans échappatoire."""
    with open(HTTP_PY, encoding='utf-8') as f:
        src = f.read()
    assert "cfg_snap.get('ntp_server'" in src


# ─── Décodage et calcul ─────────────────────────────────────────────────────

def test_une_horloge_juste_donne_un_ecart_nul(poser_socket):
    """Serveur et client d'accord : l'écart doit être ~0, quelle que soit la
    durée du trajet (c'est tout l'intérêt de la demi-somme de la RFC §8)."""
    import time
    maintenant = time.time()
    poser_socket(FauxSocket(reponse=_reponse_serveur(maintenant, maintenant)))
    r = logx_ntp.interroger('exemple.test')
    assert r['ok'] is True
    assert abs(r['ecart_s']) < 0.5


def test_une_horloge_en_retard_donne_un_ecart_positif(poser_socket):
    """Convention explicite du module : ecart_s > 0 = l'horloge LOCALE est en
    retard, il faut l'avancer. C'est l'INVERSE du DT de la page FT8 — les deux
    ont déjà été confondus une fois ce jour-là, d'où ce test."""
    import time
    # Le serveur est 5 s devant nous : notre horloge retarde de 5 s.
    t = time.time() + 5.0
    poser_socket(FauxSocket(reponse=_reponse_serveur(t, t)))
    r = logx_ntp.interroger('exemple.test')
    assert r['ok'] is True
    assert 4.0 < r['ecart_s'] < 6.0, r['ecart_s']


def test_une_horloge_en_avance_donne_un_ecart_negatif(poser_socket):
    import time
    t = time.time() - 5.0
    poser_socket(FauxSocket(reponse=_reponse_serveur(t, t)))
    r = logx_ntp.interroger('exemple.test')
    assert r['ok'] is True
    assert -6.0 < r['ecart_s'] < -4.0, r['ecart_s']


# ─── Refus et pannes : jamais d'exception, jamais de silence ────────────────

def test_un_kiss_of_death_est_refuse(poser_socket):
    """Strate 0 = le serveur refuse de nous servir (RFC 5905 §7.4). Lire des
    octets au hasard comme un horodatage donnerait une heure absurde."""
    poser_socket(FauxSocket(reponse=_reponse_serveur(1000, 1000, strate=0, ref=b'RATE')))
    r = logx_ntp.interroger('exemple.test')
    assert r['ok'] is False
    assert 'RATE' in r['error']


def test_une_reponse_qui_n_est_pas_du_mode_serveur_est_refusee(poser_socket):
    poser_socket(FauxSocket(reponse=_reponse_serveur(1000, 1000, mode=3)))
    r = logx_ntp.interroger('exemple.test')
    assert r['ok'] is False


def test_une_trame_tronquee_est_refusee(poser_socket):
    poser_socket(FauxSocket(reponse=b'\x24' + b'\x00' * 20))
    r = logx_ntp.interroger('exemple.test')
    assert r['ok'] is False
    assert 'tronqu' in r['error'].lower()


@pytest.mark.parametrize('erreur,attendu', [
    (__import__('socket').timeout(), 'pare-feu'),
    (__import__('socket').gaierror(), 'introuvable'),
    (OSError('réseau coupé'), 'Échec réseau'),
])
def test_aucune_panne_reseau_ne_leve(poser_socket, erreur, attendu):
    """Une mesure d'horloge indisponible ne doit sous aucun prétexte
    interrompre le trafic. Et le message doit ORIENTER : « pas de réponse »
    tout court n'aide personne à comprendre que le port 123 est bloqué."""
    poser_socket(FauxSocket(erreur=erreur))
    r = logx_ntp.interroger('exemple.test')
    assert r['ok'] is False
    assert attendu.lower() in r['error'].lower(), r['error']


def test_la_socket_est_toujours_fermee(poser_socket):
    faux = poser_socket(FauxSocket(erreur=OSError('bim')))
    logx_ntp.interroger('exemple.test')
    assert faux.ferme is True


# ─── Intégration page FT8 : ne plus accuser une horloge qu'on n'a pas mesurée ─

def _lire_ft8():
    with open(FT8_HTML, encoding='utf-8') as f:
        return f.read()


def test_le_bandeau_ne_designe_l_horloge_qu_apres_mesure():
    """Le 18/08/2026 j'ai affirmé à F4GLD que son horloge était en cause au vu
    d'un DT de +0,85 s. La mesure SNTP a ensuite rendu +0,009 s : son horloge
    était juste, mon diagnostic était faux, et le bandeau l'aurait affirmé à
    l'écran. Sans mesure, le texte doit donc rester au constat et proposer les
    DEUX causes possibles."""
    src = _lire_ft8()
    bloc = src[src.index('function majAlerteHorloge'):src.index('function affinerAlerteHorloge')]
    assert 'chaîne audio' in bloc, \
        "sans mesure, la chaîne audio doit être citée comme cause possible"
    assert 'CONFIG' in bloc, 'le texte doit dire comment faire trancher le logiciel'


def test_une_horloge_mesuree_saine_disculpe_l_horloge():
    src = _lire_ft8()
    bloc = src[src.index('function affinerAlerteHorloge'):]
    bloc = bloc[:bloc.index('\n  }')]
    assert 'HORLOGE_SAINE_S' in bloc
    assert 'est juste' in bloc, "le texte doit DISCULPER l'horloge quand elle est bonne"


def test_la_mesure_est_mise_en_cache():
    """Une horloge ne dérive pas en une minute : interroger un serveur public
    à chaque créneau de 15 s serait un abus, et le pool NTP répond alors par un
    kiss-of-death (c'est le sens du code RATE)."""
    src = _lire_ft8()
    assert 'MESURE_HORLOGE_VALIDITE_MS' in src
    m = re.search(r'MESURE_HORLOGE_VALIDITE_MS\s*=\s*(\d+)', src)
    assert m and int(m.group(1)) >= 60000, 'cache d\'au moins une minute attendu'


# ─── Double-clic = préparer ET envoyer ──────────────────────────────────────

def test_le_double_clic_n_emet_jamais_sans_emission_armee():
    """Demande de F4GLD : « un double clic sur une station en CQ devrait lancer
    automatiquement la réponse ». La promesse d'en-tête de la page reste tenue :
    le geste explicite qui autorise l'émission reste la case « Activer
    l'émission ». Un double-clic accidentel ne doit RIEN pouvoir émettre."""
    src = _lire_ft8()
    bloc = src[src.index('function repondreEtEnvoyer'):]
    bloc = bloc[:bloc.index('\n  }')]
    assert 'if(!txArmed)' in bloc, 'le double-clic doit refuser si l\'émission n\'est pas armée'
    assert bloc.index('if(!txArmed)') < bloc.index('envoyerMessage()'), \
        'le contrôle doit précéder l\'envoi'


def test_le_double_clic_explique_pourquoi_rien_ne_part():
    """Le silence serait le vrai défaut : le champ se remplit, rien ne part, et
    l'opérateur ne sait pas pourquoi."""
    src = _lire_ft8()
    bloc = src[src.index('function repondreEtEnvoyer'):]
    bloc = bloc[:bloc.index('\n  }')]
    assert 'txStatus' in bloc and 'Activer' in bloc


def test_le_double_clic_est_cable_sur_les_deux_listes():
    """Les décodages ET le panneau CQ ENTENDUS : c'est ce dernier que F4GLD
    désignait (« une station en CQ »), mais les deux doivent se comporter
    pareil, sans quoi le geste marche à un endroit et pas à l'autre."""
    src = _lire_ft8()
    assert src.count("addEventListener('dblclick'") >= 2


def test_l_intro_ne_promet_plus_l_absence_d_envoi_par_clic():
    """L'en-tête promettait « rien ne part sur l'air sans un clic explicite :
    Activer l'émission arme SEULEMENT le bouton Envoyer ». Avec le double-clic
    cette phrase devenait fausse — un texte d'interface qui ment sur la sûreté
    d'émission est pire que pas de texte du tout."""
    src = _lire_ft8()
    intro = src[src.index('class="intro"'):src.index('</p>', src.index('class="intro"'))]
    assert 'double-clic' in intro.lower(), "l'intro doit mentionner le double-clic"
    assert 'séquenceur' in intro, 'la garantie « pas de séquenceur » doit rester'


# ─── Le guide de réglage du poste ───────────────────────────────────────────

def test_le_guide_de_reglage_du_poste_existe_et_reste_visible_en_debutant():
    """Constat de F4GLD, 18/08/2026 : « je n'ai fait aucun réglage sur mon
    poste [...] le programme ne m'a pas du tout orienté sur ces réglages ».
    Une page qui décode le FT8 nativement mais laisse deviner le câblage n'est
    pas finie. Et c'est le débutant qui en a le plus besoin : jamais
    expert-only."""
    src = _lire_ft8()
    m = re.search(r'<details class="aide-poste">', src)
    assert m, 'panneau de réglages du poste absent'
    bloc = src[m.start():src.index('</details>', m.start())]
    assert 'expert-only' not in bloc
    for attendu in ('vitesse', 'adresse CI-V', 'ALC', 'USB-D'):
        assert attendu in bloc, f'{attendu} devrait être mentionné'


def test_le_guide_renvoie_au_manuel_pour_les_valeurs_chiffrees():
    """Règle de sourcing du projet : les pourcentages de menu varient d'un
    modèle à l'autre et je n'ai pas de source pour les valider. Le guide doit
    le DIRE au lieu d'avancer des chiffres invérifiables."""
    src = _lire_ft8()
    bloc = src[src.index('<details class="aide-poste">'):src.index('</details>')]
    assert 'manuel du constructeur fait foi' in bloc
