# -*- coding: utf-8 -*-
"""Moteur de score des Rencontres UFT (CW HF) — règlement UFT (sourcé F4GLD,
01/09/2026, https://www.uft.net/activites-et-concours/rencontres-uft/).

Barème par QSO :
    F8UFT (station officielle)         : 20 pts
    Membre UFT même continent          :  5 pts
    Membre UFT DX (autre continent)    : 10 pts
    Non-membre (NM) même continent     :  1 pt
    Non-membre (NM) DX                 :  2 pts
Une station n'est contactable qu'une fois PAR BANDE (dupe clé = (indicatif, bande)).
Multiplicateur : chaque membre UFT contacté compte 1 multi PAR BANDE (F8UFT inclus).
    score final = total des points × nombre de (membre, bande) distincts

MODULE PUR (pas de réseau ni d'état). Le statut membre vient de l'ÉCHANGE REÇU
(numérique = membre / « NM » = non-membre) — voir classifier_echange ; une base
de membres UFT peut affiner/vérifier, mais n'est pas nécessaire au calcul.
Le continent (DX ou non) est fourni par l'appelant (le dépôt le tire du DXCC).
"""
from dataclasses import dataclass


def classifier_echange(echange):
    """Échange reçu -> statut : 'membre' (n° UFT numérique), 'non_membre' (NM),
    'inconnu' sinon. Le règlement ne demande pas d'indicatif spécial : c'est
    l'échange qui tranche."""
    v = str(echange or '').strip().upper()
    if v == 'NM':
        return 'non_membre'
    if v.isdigit():
        return 'membre'
    return 'inconnu'


@dataclass
class UftQso:
    call: str
    band: str
    dx: bool                      # True si autre continent que le mien
    is_member: bool               # membre UFT (déduit de l'échange reçu)
    is_f8uft: bool = False


def qso_points(qso):
    """Points d'un QSO selon le type de station et DX/non-DX."""
    if qso.is_f8uft:
        return 20
    if qso.is_member:
        return 10 if qso.dx else 5
    return 2 if qso.dx else 1


def calculer_score_uft(qsos):
    """total des points × nb de (membre, bande) distincts. Dédoublonne par
    (indicatif, bande) — un même correspondant ne compte qu'une fois par bande."""
    vus = set()
    doublons = 0
    points_total = 0
    multis = set()                # (indicatif, bande) des membres/F8UFT
    valides = 0
    for q in qsos:
        cle = (str(q.call).upper(), str(q.band).upper())
        if cle in vus:
            doublons += 1
            continue
        vus.add(cle)
        points_total += qso_points(q)
        valides += 1
        if q.is_f8uft or q.is_member:
            multis.add(cle)
    mult = len(multis)
    return {
        'valid_qso_count': valides,
        'duplicate_count': doublons,
        'points_total': points_total,
        'multiplier': mult,
        'final_score': points_total * mult,
    }
