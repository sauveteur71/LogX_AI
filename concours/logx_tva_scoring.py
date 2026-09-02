# -*- coding: utf-8 -*-
"""Moteur de score TVA (National TVA, IARU R1 TVA, Championnat de France TVA).

Modèle PARAMÉTRABLE (conception validée par F4GLD 01/09/2026, sur les règlements
REF), pas une succession de cas particuliers. Un point TVA dépend de :
- la BANDE (classée 70 cm / 23 cm / au-dessus de 23 cm),
- la SECTION (1 = émission/réception, 2 = réception seule),
- le TYPE DE LIAISON (bilatérale / unilatérale / réception seule),
- la DISTANCE (km, depuis les locators échangés).

Barème (règlement National/IARU TVA) :
    70 cm  : 2 pts/km (section 1) · 1 pt/km (section 2)
    23 cm  : 4 pts/km (section 1) · 2 pts/km (section 2)
    > 23 cm: 10 pts/km (section 1) · 5 pts/km (section 2)
En section 1, une liaison UNILATÉRALE voit ses points divisés par deux.

MODULE PUR (pas de réseau, pas d'état) : le câblage LIVE (saisie de la section et
du type de liaison par QSO, définitions CONTEST_DEFINITIONS, enum du schéma) est
un chantier SÉPARÉ — il change le modèle de saisie et doit être relu par F4GLD.
"""
from dataclasses import dataclass
from enum import Enum


class TvaSection(str, Enum):
    SECTION_1 = 'section_1'   # émission/réception
    SECTION_2 = 'section_2'   # réception seule


class TvaLinkType(str, Enum):
    BILATERAL = 'bilateral'
    UNILATERAL = 'unilateral'
    RECEIVE_ONLY = 'receive_only'


# Coefficients pts/km par classe de bande × section (règlement TVA).
TVA_COEFFICIENTS = {
    '70CM':       {'section_1': 2.0, 'section_2': 1.0},
    '23CM':       {'section_1': 4.0, 'section_2': 2.0},
    'ABOVE_23CM': {'section_1': 10.0, 'section_2': 5.0},
}


def tva_band_class(band):
    """Bande (clé interne du dépôt '432'/'1296'/… OU libellé '70cm'/'23cm') ->
    classe de barème. Tout ce qui n'est ni 70 cm ni 23 cm est « au-dessus »."""
    n = str(band or '').upper().replace(' ', '').replace('MHZ', '')
    if n in ('432', '70CM'):
        return '70CM'
    if n in ('1296', '23CM'):
        return '23CM'
    return 'ABOVE_23CM'


@dataclass
class TvaQso:
    band: str
    section: TvaSection
    link_type: TvaLinkType
    distance_km: float
    qso_number: int = 0
    video_code: str = None


def tva_qso_points(qso):
    """Points d'UN QSO TVA. Section 1 + liaison unilatérale -> ÷2."""
    coeff = TVA_COEFFICIENTS[tva_band_class(qso.band)][qso.section.value]
    points = float(qso.distance_km) * coeff
    if qso.section == TvaSection.SECTION_1 and qso.link_type == TvaLinkType.UNILATERAL:
        points /= 2
    return points


def score_tva(qsos):
    """Total + détail par bande + nombre de QSO."""
    per_band = {}
    total = 0.0
    for q in qsos:
        p = tva_qso_points(q)
        per_band[q.band] = per_band.get(q.band, 0.0) + p
        total += p
    return {
        'total': round(total, 1),
        'per_band': {b: round(p, 1) for b, p in per_band.items()},
        'qso_count': len(qsos),
    }


def distance_km_depuis_locators(locator_sent, locator_received):
    """Distance (km) entre deux locators Maidenhead échangés. Réutilise les
    helpers du dépôt (locator_to_latlon + haversine). None si un locator est
    illisible — le règlement exige le LOCATOR ÉCHANGÉ, pas une adresse saisie."""
    from logx_utils import locator_to_latlon, haversine
    a = locator_to_latlon(locator_sent)
    b = locator_to_latlon(locator_received)
    # locator_to_latlon rend (None, None) — un tuple TRUTHY — pour un locator
    # illisible : tester les composantes, pas la vérité du tuple.
    if not a or not b or a[0] is None or b[0] is None:
        return None
    return haversine(a[0], a[1], b[0], b[1])


def validate_video_code(code, previous_codes=(), non_consecutive=False):
    """Code vidéo TVA : 4 chiffres tous DIFFÉRENTS, unique par bande (donc
    différent des `previous_codes` déjà utilisés). Pour l'IARU TVA, ajouter la
    contrainte de non-consécutivité (`non_consecutive=True`). Renvoie la liste
    des erreurs (vide = valide)."""
    errors = []
    s = str(code or '')
    if not s.isdigit() or len(s) != 4:
        return ['Le code vidéo doit contenir quatre chiffres.']
    if len(set(s)) != 4:
        errors.append('Les quatre chiffres doivent être différents.')
    if non_consecutive and any(int(s[i + 1]) - int(s[i]) == 1 for i in range(3)):
        errors.append('Les chiffres ne doivent pas être consécutifs.')
    if s in set(previous_codes):
        errors.append('Le code vidéo doit être différent pour chaque bande.')
    return errors
