# -*- coding: utf-8 -*-
"""Dé-encadrement KISS -- SSDV Phase 2, transport (cadrage
docs/superpowers/specs/2026-09-11-ssdv-phase2-transport-cadrage.md, validé
par F4GLD le 11/09/2026 : Direwolf + client KISS maison, pas de
réutilisation d'un projet tiers en bloc).

Format relu contre la spec KISS faisant autorité (ax25.net) le 11/09/2026,
pas déduit d'une note tierce. Ce module ne connaît RIEN d'AX.25 ni de SSDV
-- une seule responsabilité : convertir un flux d'octets KISS (tel que
Direwolf le publie sur son port TCP) en trames délimitées, et l'inverse.
Voir logx_ax25.py pour la couche suivante."""

FEND = 0xC0
FESC = 0xDB
TFEND = 0xDC
TFESC = 0xDD


def echapper(donnees):
    sortie = bytearray()
    for b in donnees:
        if b == FEND:
            sortie += bytes([FESC, TFEND])
        elif b == FESC:
            sortie += bytes([FESC, TFESC])
        else:
            sortie.append(b)
    return bytes(sortie)


def desechapper(donnees):
    sortie = bytearray()
    i, n = 0, len(donnees)
    while i < n:
        b = donnees[i]
        if b == FESC and i + 1 < n:
            suivant = donnees[i + 1]
            if suivant == TFEND:
                sortie.append(FEND)
                i += 2
                continue
            if suivant == TFESC:
                sortie.append(FESC)
                i += 2
                continue
        sortie.append(b)
        i += 1
    return bytes(sortie)


def encadrer(charge_brute, commande=0x00):
    """Construit une trame KISS complète (FEND + commande + charge + FEND).
    `charge_brute` n'est PAS encore échappée -- l'échappement porte sur
    l'octet de commande ET la charge ensemble (comme le flux réel)."""
    corps = bytes([commande]) + bytes(charge_brute)
    return bytes([FEND]) + echapper(corps) + bytes([FEND])


def extraire_trames(tampon):
    """`tampon` : octets bruts déjà reçus (0, 1 ou plusieurs trames, plus un
    éventuel reliquat incomplet en fin de flux -- lecture socket TCP, pas
    forcément alignée sur les limites de trame).

    Renvoie (trames, reliquat) : `trames` est la liste des corps dé-échappés
    (octet de commande + charge, FEND retirés) des trames COMPLÈTES
    trouvées ; `reliquat` est ce qu'il faut concaténer directement aux
    prochains octets reçus (sans FEND à rajouter -- la complétude d'une
    trame se détermine par la présence d'un FEND dans le flux, pas par un
    marqueur d'état conservé entre deux appels ; vérifié par contre-épreuve
    de mutation que le préfixer ne change aucun résultat).

    Limite acceptée : des octets parasites reçus AVANT le tout premier FEND
    d'une connexion (bruit de ligne au moment de la connexion) sont
    fusionnés dans le segment suivant plutôt que rejetés explicitement --
    la couche AX.25 au-dessus les rejettera de toute façon comme trame mal
    formée. Cas marginal (une seule fois par connexion, jamais en cours de
    flux normal), pas un défaut de dé-encadrement en régime établi."""
    if not tampon:
        return [], b''
    parties = tampon.split(bytes([FEND]))
    if tampon.endswith(bytes([FEND])):
        candidats, reliquat = parties[:-1], b''
    else:
        candidats, reliquat = parties[:-1], parties[-1]
    trames = [desechapper(c) for c in candidats if c]
    return trames, reliquat
