# -*- coding: utf-8 -*-
"""Détecteur de « crédit » (ce qu'une station apporte de NOUVEAU) + score de
priorité pour l'onglet CHASSE.

Ce module ne recalcule AUCUN statut : il COMPOSE les primitives déjà sourcées
de `logx_awards` — en particulier la grille bande×mode de `lotw_grid()`
(`{bande: {mode: 'confirmed'|'worked'|'none'}}`, mode ∈ {CW, PHONE, DIGITAL}) —
pour classer un créneau (bande, mode) et l'expliquer.

Grille de priorité et poids issus de la doc F4GLD (25/08/2026). **Aucune valeur
de domaine inventée** : les poids sont un DÉFAUT configurable (profil d'objectifs
opérateur), pas une vérité universelle — la doc insiste : « ne donnez pas une
priorité universelle ». Un objectif désactivé annule le crédit correspondant.
"""

# ── Classes de crédit (ce qu'un créneau bande×mode apporte pour une entité) ──
CLASSE_ATNO = 'atno'                    # entité jamais travaillée (All Time New One)
CLASSE_NEW_BAND = 'new_band'            # entité déjà faite, jamais sur CETTE bande
CLASSE_NEW_MODE = 'new_mode'            # déjà sur cette bande, jamais dans CE mode
CLASSE_NEEDED_CONFIRM = 'needed_confirm'  # ce créneau travaillé mais pas confirmé LoTW
CLASSE_NEW_GRID = 'new_grid'            # carré Maidenhead VHF/UHF jamais travaillé
CLASSE_CONFIRMED = 'confirmed'          # ce créneau déjà confirmé (doublon confirmé)
CLASSE_INCONNU = 'inconnu'             # entité DXCC non résolue

# Poids par défaut (doc F4GLD). Reproduits fidèlement ; surchargeable par
# l'appelant (profil opérateur). Les crédits « non-DXCC » (grid VHF, mult
# concours, préfixe) sont ici pour un score unifié même s'ils sont calculés
# ailleurs — le détecteur DXCC de ce module ne renvoie que les classes DXCC.
POIDS_DEFAUT = {
    'atno': 1000,           # nouvelle entité DXCC totale
    'rare': 800,            # DXpedition / entité rare (posé par l'appelant)
    'new_band': 600,        # nouvelle entité sur une bande
    'new_band_mode': 550,   # nouvelle bande + nouveau mode (double intérêt)
    'new_mode': 500,        # nouvelle entité dans un mode
    'new_grid': 450,        # nouveau grid VHF/UHF
    'contest_mult': 400,    # multiplicateur de concours manquant
    'new_park': 350,        # nouveau parc POTA
    'new_summit': 350,      # nouveau sommet SOTA
    'new_zone': 300,        # nouvelle zone CQ / ITU
    'new_iota': 250,        # nouvelle île IOTA
    'needed_confirm': 200,  # entité travaillée mais non confirmée
    'new_prefix': 150,      # nouveau préfixe
    'new_band_mode_combo': 100,  # nouveau QSO sur combinaison bande+mode
    'confirmed': -900,      # doublon deja confirme sur bande ET mode
    'inconnu': 0,
}

# Classe de crédit -> clé du profil d'objectifs qui l'active. Si l'objectif est
# désactivé, le crédit ne compte pas (score 0 pour cette classe). Une classe
# absente de cette table est toujours comptée.
_OBJECTIF_POUR_CLASSE = {
    CLASSE_ATNO: 'dxcc',
    CLASSE_NEW_BAND: 'dxcc_new_band',
    CLASSE_NEW_MODE: 'dxcc_new_mode',
    CLASSE_NEEDED_CONFIRM: 'lotw_confirmation_priority',
    CLASSE_NEW_GRID: 'vucc',            # chasse aux carrés VHF/UHF (award VUCC)
}

_RAISON = {
    CLASSE_ATNO: "Nouvelle entité DXCC (jamais contactée)",
    CLASSE_NEW_BAND: "Entité déjà faite, mais nouvelle sur cette bande",
    CLASSE_NEW_MODE: "Entité déjà faite sur cette bande, mais nouveau mode",
    CLASSE_NEEDED_CONFIRM: "Déjà contactée sur ce créneau, mais pas confirmée LoTW",
    CLASSE_NEW_GRID: "Nouveau carré Maidenhead (VHF/UHF, jamais travaillé)",
    CLASSE_CONFIRMED: "Déjà confirmée sur cette bande et ce mode (doublon)",
    CLASSE_INCONNU: "Entité DXCC inconnue",
}

_ETATS_TRAVAILLES = ('worked', 'confirmed')


def classer_dxcc(grille_lotw, band, mode_cat):
    """Classe un créneau (band, mode_cat) pour l'entité décrite par la sortie de
    `logx_awards.lotw_grid()`. `band` doit être une clé de la grille (libellé de
    CHALLENGE_BANDS) ; `mode_cat` ∈ {CW, PHONE, DIGITAL}. PURE.

    - créneau 'confirmed' -> CONFIRMED (doublon confirmé) ;
    - créneau 'worked'    -> NEEDED_CONFIRM ;
    - créneau 'none' :
        * entité jamais travaillée nulle part -> ATNO ;
        * bande jamais travaillée (autres modes non plus) -> NEW_BAND ;
        * bande travaillée dans un autre mode -> NEW_MODE.
    """
    if not grille_lotw or not grille_lotw.get('active'):
        return CLASSE_INCONNU
    grid = grille_lotw.get('grid', {}) or {}
    statut_ici = (grid.get(band, {}) or {}).get(mode_cat, 'none')
    if statut_ici == 'confirmed':
        return CLASSE_CONFIRMED
    if statut_ici == 'worked':
        return CLASSE_NEEDED_CONFIRM
    # 'none' (ou bande/mode hors grille) : que sait-on de l'entité ?
    travaille_partout = any(
        s in _ETATS_TRAVAILLES
        for modes in grid.values() for s in (modes or {}).values())
    if not travaille_partout:
        return CLASSE_ATNO
    bande_travaillee = any(
        s in _ETATS_TRAVAILLES for s in (grid.get(band, {}) or {}).values())
    return CLASSE_NEW_MODE if bande_travaillee else CLASSE_NEW_BAND


def _objectif_actif(classe, objectifs):
    """Un crédit ne compte que si son objectif est actif (défaut : actif)."""
    if not objectifs:
        return True
    cle = _OBJECTIF_POUR_CLASSE.get(classe)
    if cle is None:
        return True
    return bool(objectifs.get(cle, True))


def score_classe(classe, poids=None, objectifs=None):
    """Score numérique d'une classe. `poids` surcharge POIDS_DEFAUT ; `objectifs`
    (profil on/off) annule le crédit d'un objectif désactivé (sauf le malus de
    doublon, toujours appliqué)."""
    table = dict(POIDS_DEFAUT)
    if poids:
        table.update(poids)
    base = table.get(classe, 0)
    if base < 0:                       # malus (doublon) : jamais neutralisé
        return base
    return base if _objectif_actif(classe, objectifs) else 0


def raison(classe):
    """Explication FR courte d'une classe (le « pourquoi » à afficher)."""
    return _RAISON.get(classe, "")


def evaluer(grille_lotw, band, mode_cat, poids=None, objectifs=None):
    """Raccourci : classe + score + raison d'un créneau. Renvoie
    {'classe', 'score', 'raison'}."""
    classe = classer_dxcc(grille_lotw, band, mode_cat)
    return {'classe': classe,
            'score': score_classe(classe, poids, objectifs),
            'raison': raison(classe)}


def evaluer_grid(neuf_a_vie, poids=None, objectifs=None):
    """Crédit d'un carré VHF/UHF entendu : {'classe', 'score', 'raison'} si le
    carré est neuf à vie ET l'objectif 'vucc' actif, sinon None. PURE — le test
    « neuf » est fait par l'appelant (logx_awards, qui tient l'index des carrés
    du carnet).

    Renvoie None (pas un dict à score 0) quand l'objectif est désactivé : sinon
    la fusion par max de l'appelant (0 > -900) écraserait une classification
    DXCC légitime — un doublon CONFIRMÉ passerait de -900 à 0. Contrat du
    module : « un objectif désactivé annule le crédit correspondant »."""
    if not neuf_a_vie:
        return None
    score = score_classe(CLASSE_NEW_GRID, poids, objectifs)
    if score <= 0:                     # objectif 'vucc' désactivé (ou poids nul)
        return None
    return {'classe': CLASSE_NEW_GRID,
            'score': score,
            'raison': raison(CLASSE_NEW_GRID)}
