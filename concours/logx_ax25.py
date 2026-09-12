# -*- coding: utf-8 -*-
"""Parseur d'en-tête AX.25 -- SSDV Phase 2, transport (cadrage
docs/superpowers/specs/2026-09-11-ssdv-phase2-transport-cadrage.md, validé
par F4GLD le 11/09/2026).

Format relu contre ax25_pad.h (dépôt wb2osz/direwolf, GPL-2.0 -- lu pour
COMPRENDRE le format, aucun code copié) le 11/09/2026, pas déduit d'une
note tierce. Ce module prend une trame AX.25 déjà dé-encapsulée par
logx_kiss (sans l'octet de commande KISS) et n'en extrait QUE l'en-tête :
adresses, contrôle, PID. Le champ INFO qu'il isole est transmis tel quel à
logx_ssdv.parser_entete pour la couche SSDV -- ce module ne connaît rien
du format SSDV."""

TAILLE_CHAMP_ADRESSE = 7
NB_CHAMPS_ADRESSE_MAX = 4          # destination + source + 2 répéteurs
CONTROLE_UI = 0x03
PID_PAS_DE_COUCHE_3 = 0xF0


def _decoder_champ_adresse(champ):
    """champ : 7 octets. Renvoie (indicatif, ssid, dernier_champ) --
    indicatif décalé d'1 bit à droite (le format AX.25 stocke chaque
    caractère ASCII << 1) puis dépouillé des espaces de complément, SSID
    extrait des bits 4-1 du 7e octet, dernier_champ = bit d'extension
    (bit 0 du 7e octet) à 1."""
    lettres = bytes((b >> 1) & 0x7F for b in champ[:6])
    indicatif = lettres.decode('ascii', 'replace').strip()
    ssid_octet = champ[6]
    ssid = (ssid_octet & 0x1E) >> 1
    dernier = bool(ssid_octet & 0x01)
    return indicatif, ssid, dernier


def parser_entete(trame):
    """trame : octets AX.25 (après dé-encapsulation KISS). Renvoie
    {'destination':(indicatif,ssid), 'source':(indicatif,ssid),
    'repeteurs':[(indicatif,ssid), ...], 'controle':int, 'pid':int|None,
    'info':bytes}. Lève ValueError si la trame est trop courte, si un
    champ d'adresse est tronqué, ou si le bit d'extension n'apparaît
    jamais (trame corrompue -- éviter une boucle infinie)."""
    if len(trame) < 2 * TAILLE_CHAMP_ADRESSE + 1:
        raise ValueError("trame AX.25 trop courte pour contenir "
                          "destination + source + contrôle")
    champs = []
    i = 0
    while True:
        if i + TAILLE_CHAMP_ADRESSE > len(trame):
            raise ValueError("champ d'adresse AX.25 tronqué")
        indicatif, ssid, dernier = _decoder_champ_adresse(trame[i:i + TAILLE_CHAMP_ADRESSE])
        champs.append((indicatif, ssid))
        i += TAILLE_CHAMP_ADRESSE
        if dernier:
            break
        if len(champs) >= NB_CHAMPS_ADRESSE_MAX:
            raise ValueError("bit d'extension jamais rencontré "
                              "(trop de champs d'adresse, trame corrompue)")
    if len(champs) < 2:
        raise ValueError("trame AX.25 sans source ET destination")
    if i >= len(trame):
        raise ValueError("trame AX.25 sans champ de contrôle")
    controle = trame[i]
    i += 1
    pid = None
    if controle == CONTROLE_UI:
        if i >= len(trame):
            raise ValueError("trame UI sans octet PID")
        pid = trame[i]
        i += 1
    return {
        'destination': champs[0],
        'source': champs[1],
        'repeteurs': champs[2:],
        'controle': controle,
        'pid': pid,
        'info': trame[i:],
    }
