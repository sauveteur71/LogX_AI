# -*- coding: utf-8 -*-
"""Moteur de score du Challenge THF (REF) — règlement sourcé F4GLD (01/09/2026,
reg_challengethf_fr_20251209.pdf).

Activité annuelle, 144 MHz → 47 GHz, décompte TRIMESTRIEL. Une même station est
contactable UNE fois par MOIS et par BANDE. Score PAR BANDE :

    T = P × (D + G) × C

    P = nb de « nouvelles stations par mois » = (indicatif, mois) distincts
    D = nb de départements distincts
    G = nb de grands carrés locator distincts (carré à 4 caractères)
    C = coefficient de bande : 144=1 · 432=3 · 1296=5 · 2320 et au-dessus=10

Exemple du règlement (144 MHz) : 450 × (50 dép + 40 QTH) × 1 = 40 500.
Score total = somme des scores par bande.

MODULE PUR (pas de réseau ni d'état). Le département et le carré du correspondant
viennent des données loggées (échange REF HF / locator reçu) ; le mois de
`date` (YYYYMMDD -> YYYYMM). Clé de dédoublonnage métier : (indicatif, bande, mois).
"""
from dataclasses import dataclass


def coefficient_bande(band):
    """Coefficient de bande du Challenge THF. 144=1, 432=3, 1296=5 ; tout le
    reste (2320 et au-dessus) = 10 — les bandes du Challenge vont de 144 MHz à
    47 GHz, seules 144/432/1296 ont un coefficient propre."""
    return {'144': 1, '432': 3, '1296': 5}.get(str(band).strip(), 10)


@dataclass
class ChallengeThfQso:
    call: str
    band: str
    date: str                 # 'YYYYMMDD' UTC (le mois = date[:6])
    department: str = ''      # département du correspondant (multiplicateur)
    grid: str = ''            # locator reçu (grand carré = 4 premiers car.)


def _mois(qso):
    return str(qso.date or '')[:6]


def score_bande(qsos, band):
    """Score d'UNE bande : P × (D + G) × C, avec dédoublonnage (indicatif, mois)."""
    de_la_bande = [q for q in qsos if str(q.band).strip() == str(band).strip()]
    stations_mois = {(str(q.call).upper(), _mois(q)) for q in de_la_bande}
    departements = {q.department.upper() for q in de_la_bande if q.department}
    carres = {q.grid[:4].upper() for q in de_la_bande if q.grid and len(q.grid) >= 4}
    P = len(stations_mois)
    D = len(departements)
    G = len(carres)
    C = coefficient_bande(band)
    return {
        'band': str(band).strip(),
        'points': P,
        'departments': D,
        'large_locators': G,
        'coefficient': C,
        'score': P * (D + G) * C,
    }


def calculer_score_challenge_thf(qsos):
    """Score total = somme des scores par bande, + le détail par bande."""
    bandes = sorted({str(q.band).strip() for q in qsos},
                    key=lambda b: float(b) if b.replace('.', '', 1).isdigit() else 1e9)
    par_bande = [score_bande(qsos, b) for b in bandes]
    return {
        'total': sum(x['score'] for x in par_bande),
        'per_band': par_bande,
        'qso_count': len(qsos),
    }
