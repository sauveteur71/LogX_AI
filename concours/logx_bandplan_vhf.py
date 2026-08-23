# -*- coding: utf-8 -*-
"""Plan de bandes IARU Région 1 au-dessus de 440 MHz, et contraintes 23 cm.

POURQUOI CE MODULE EXISTE À PART. La table de logx_awards découpe les bandes en
trois catégories d'affichage (CW / numérique / phonie) : c'est ce qu'il faut
pour colorer une réglette et deviner le mode d'un spot. Le plan IARU, lui, est
beaucoup plus riche — ATV, satellite, balises exclusives, largeur de bande
maximale, segments dont le statut dépend du pays. L'écraser dans trois
catégories perdrait tout ce qui compte au-dessus du 70 cm.

═══ PROVENANCE, ET TROIS RÉSERVES À LIRE AVANT LES CHIFFRES ═══════════════════

Les segments viennent du document « IARU Region 1 VHF/UHF and Microwave Band
Plans », récupéré le 31/07/2026.

  1. LE NOM DU FICHIER MENT. Il annonce « 2021 » ; l'en-tête interne et le pied
     de page de chaque page disent 2017 IARU Region 1 General Conference,
     Landshut, Germany. L'édition retenue ici est donc 2017 / LANDSHUT.

  2. CE N'EST PAS LA SOURCE PRIMAIRE. C'est une republication par la SARL, la
     société nationale sud-africaine. Le document précise lui-même que ces
     plans sont GÉNÉRIQUES pour tous les États membres de la région 1 et
     peuvent être plus détaillés au niveau national. À confronter à
     iaru-r1.org avant d'en faire une autorité.

  3. LE 23 cm DE CE PLAN EST ANTÉRIEUR À LA CMR-23. Voir CONTRAINTES_23CM plus
     bas : la décision ECC/DEC/(25)01 impose depuis des limites de puissance
     que le plan de 2017 ignore.

═══ QUATRE PIÈGES DE MODÉLISATION, ET COMMENT ILS SONT TRAITÉS ════════════════

  a) LARGEUR DE BANDE NULLABLE. Au-dessus de 1,3 GHz, beaucoup de lignes
     renvoient à la réglementation nationale au lieu de fixer une valeur.
     `bw_hz = None` signifie « fixée au niveau national », PAS « illimitée ».

  b) « Sub-Regional / national band planning » N'EST PAS UN MODE, c'est un
     STATUT de segment. Le ranger dans l'énumération des modes produirait un
     mode fantôme qu'aucun filtre ne saurait traiter. D'où le champ `statut`,
     distinct de `mode`.

  c) LES SEGMENTS À BANDE ÉTROITE ALTERNATIFS SONT CONDITIONNELS AU PAYS. Une
     bande peut en avoir deux ou trois selon que le principal est attribué ou
     non. Une table plate (bande, début, fin, mode) ne peut pas représenter
     ça : voir ALTERNATIVES_NB.

  d) LA COLONNE « USAGE » N'EST PAS NORMATIVE. Le document dit explicitement
     qu'aucun droit à une fréquence réservée n'en découle — SAUF là où
     « exclusive » apparaît (les balises, notamment). Les centres d'activité
     indicatifs sont donc dans CENTRES_ACTIVITE, séparés des segments, et le
     champ `exclusif` marque les rares cas normatifs.
"""

# ─── Provenance, par source ──────────────────────────────────────────────────

PROVENANCE = {
    'iaru_r1_2017': {
        'document': 'IARU Region 1 VHF/UHF and Microwave Band Plans',
        'edition': '2017',
        'conference': 'IARU R1 General Conference, Landshut (Allemagne), 2017',
        'obtenu_le': '2026-07-31',
        'via': 'republication SARL (société nationale sud-africaine)',
        'reserve': ("Le nom du fichier annonce 2021, l'en-tête interne dit 2017. "
                    "Republication, pas source primaire. Plans GÉNÉRIQUES région 1 : "
                    "un plan national peut être plus détaillé. À confronter à "
                    "iaru-r1.org avant de figer."),
        'normatif': False,
    },
    'ecc_dec_25_01': {
        'document': 'ECC Decision (25)01',
        'titre': ("Technical and operational measures for the use of the frequency "
                  "band 1258-1300 MHz by the amateur and amateur-satellite services "
                  "in order to protect the radionavigation-satellite service"),
        'approuve_le': '2025-06-27',
        'en_vigueur_le': '2025-06-27',
        'implementation_nationale_souhaitee': '2025-12-27',
        'obtenu_le': '2026-07-31',
        'reserve': ("S'applique aux administrations CEPT qui autorisent l'amateur "
                    "sur tout ou partie de 1258-1300 MHz. Une période transitoire "
                    "nationale allant jusqu'à TROIS ANS est prévue pour les "
                    "installations déjà autorisées entre 1258 et 1296 MHz : la date "
                    "d'application réelle dépend donc du pays."),
        'normatif': True,
    },
}

# ─── Vocabulaire ─────────────────────────────────────────────────────────────
# MGM = Machine Generated Mode dans le document IARU, c'est-à-dire les modes
# numériques. On garde le vocabulaire de la source plutôt que de le traduire
# vers le nôtre : la correspondance se fait à l'affichage, pas dans la table.

MODES = ('CW', 'CW/MGM', 'CW/SSB/MGM', 'SSB/CW/MGM', 'FM/DV', 'MGM',
         'ATV/DATV', 'SAT', 'ALL')

# `statut` — voir piège (b) : ce n'est PAS un mode.
STATUT_NORMATIF = 'normatif'
STATUT_NATIONAL = 'planification_nationale'   # « Sub-Regional / national band planning »

_S = 'iaru_r1_2017'


def _seg(bande, lo, hi, bw, mode, note='', exclusif=False,
         statut=STATUT_NORMATIF, src=_S):
    """Un segment. `bw` en Hz, ou None = fixée par la réglementation NATIONALE
    (piège (a)) — jamais « illimitée »."""
    return {'bande': bande, 'lo_mhz': lo, 'hi_mhz': hi, 'bw_hz': bw,
            'mode': mode, 'note': note, 'exclusif': exclusif,
            'statut': statut, 'source': src}


# ─── 23 cm — 1240-1300 MHz — ⚠ voir CONTRAINTES_23CM ─────────────────────────
_23CM = [
    _seg('1296', 1240.000, 1240.500, 2700, 'ALL', 'réservé usage futur'),
    _seg('1296', 1240.500, 1240.750, 500, 'CW/MGM', 'balises, réservé usage futur'),
    _seg('1296', 1240.750, 1241.000, 20000, 'FM/DV', 'réservé usage futur'),
    _seg('1296', 1241.000, 1243.250, 20000, 'ALL'),
    _seg('1296', 1243.250, 1260.000, None, 'ATV/DATV'),
    _seg('1296', 1260.000, 1270.000, None, 'SAT', 'service amateur par satellite'),
    _seg('1296', 1270.000, 1272.000, 20000, 'ALL'),
    _seg('1296', 1272.000, 1290.994, None, 'ATV/DATV'),
    _seg('1296', 1290.994, 1291.481, 20000, 'FM/DV', 'entrée relais'),
    _seg('1296', 1291.494, 1296.000, None, 'ALL'),
    _seg('1296', 1296.000, 1296.150, 500, 'CW/MGM', 'EME 1296,000-1296,025'),
    _seg('1296', 1296.150, 1296.800, 2700, 'CW/SSB/MGM'),
    _seg('1296', 1296.800, 1296.994, 500, 'CW/MGM', 'balises', exclusif=True),
    _seg('1296', 1296.994, 1297.481, 20000, 'FM/DV', 'sortie relais'),
    _seg('1296', 1297.494, 1297.981, 20000, 'FM/DV', 'simplex'),
    _seg('1296', 1298.000, 1299.000, 20000, 'ALL'),
    _seg('1296', 1299.000, 1299.750, 150000, 'ALL', 'données haut débit, 5 canaux'),
    _seg('1296', 1299.750, 1300.000, 20000, 'ALL', '8 canaux de 25 kHz'),
]

# ─── 13 cm — 2300-2450 MHz ───────────────────────────────────────────────────
_13CM = [
    _seg('2320', 2300.000, 2320.000, 20000, 'ALL', '', statut=STATUT_NATIONAL),
    _seg('2320', 2320.000, 2320.150, 500, 'CW', 'EME 2320,000-2320,025', exclusif=True),
    _seg('2320', 2320.150, 2320.800, 2700, 'CW/SSB/MGM'),
    _seg('2320', 2320.800, 2321.000, None, 'CW/MGM', 'balises', exclusif=True),
    _seg('2320', 2321.000, 2322.000, 20000, 'FM/DV'),
    _seg('2320', 2322.000, 2400.000, None, 'ALL'),
    _seg('2320', 2400.000, 2450.000, None, 'SAT', 'service amateur par satellite'),
]

# ─── 9 cm — 3400-3475 MHz ────────────────────────────────────────────────────
_9CM = [
    _seg('3400', 3400.000, 3400.800, 500, 'CW/MGM', 'activité + EME à 3400,100'),
    _seg('3400', 3400.800, 3400.995, None, 'CW/MGM', 'balises', exclusif=True),
    _seg('3400', 3401.000, 3402.000, 2700, 'ALL'),
    _seg('3400', 3402.000, 3410.000, None, 'ALL', 'descentes satellite'),
    _seg('3400', 3410.000, 3475.000, None, 'ALL'),
]

# ─── 6 cm — 5650-5850 MHz ────────────────────────────────────────────────────
_6CM = [
    _seg('5760', 5650.000, 5668.000, 2700, 'ALL', 'satellite (montée)'),
    _seg('5760', 5668.000, 5670.000, 2700, 'ALL', 'bande étroite, satellite (montée)'),
    _seg('5760', 5670.000, 5700.000, None, 'MGM'),
    _seg('5760', 5700.000, 5720.000, None, 'ATV/DATV'),
    _seg('5760', 5720.000, 5760.000, None, 'ALL'),
    _seg('5760', 5760.000, 5760.800, 2700, 'ALL', 'bande étroite'),
    _seg('5760', 5760.800, 5760.990, None, 'CW/MGM', 'balises', exclusif=True),
    _seg('5760', 5761.000, 5762.000, None, 'ALL'),
    _seg('5760', 5762.000, 5830.000, None, 'ALL'),
    _seg('5760', 5830.000, 5850.000, None, 'ALL', 'satellite (descente)'),
]

# ─── 3 cm — 10,0-10,5 GHz ────────────────────────────────────────────────────
_3CM = [
    _seg('10368', 10000.0, 10150.0, None, 'MGM'),
    _seg('10368', 10150.0, 10250.0, None, 'ALL'),
    _seg('10368', 10250.0, 10350.0, None, 'MGM'),
    _seg('10368', 10350.0, 10368.0, None, 'ALL'),
    _seg('10368', 10368.0, 10368.8, 2700, 'ALL', 'bande étroite'),
    _seg('10368', 10368.8, 10368.99, None, 'CW/MGM', 'balises', exclusif=True),
    _seg('10368', 10369.0, 10370.0, 2700, 'ALL'),
    _seg('10368', 10370.0, 10450.0, None, 'ALL'),
    _seg('10368', 10450.0, 10500.0, None, 'ALL', 'satellite'),
]

# ─── Bandes millimétriques ───────────────────────────────────────────────────
_MM = [
    _seg('24048', 24000.0, 24048.0, None, 'ALL', 'centre large bande 24,025 GHz'),
    _seg('24048', 24048.0, 24048.8, 2700, 'ALL', 'bande étroite + satellite'),
    _seg('24048', 24048.8, 24048.995, None, 'CW/MGM', 'balises', exclusif=True),
    _seg('24048', 24049.0, 24050.0, 2700, 'ALL', 'satellite + bande étroite'),
    _seg('24048', 24050.0, 24250.0, None, 'ALL'),

    _seg('47088', 47000.0, 47088.0, None, 'ALL'),
    _seg('47088', 47088.0, 47090.0, 2700, 'ALL', 'bande étroite + satellite'),
    _seg('47088', 47090.0, 47200.0, None, 'ALL'),

    _seg('76032', 75500.0, 76000.0, 2700, 'ALL', 'satellite préféré, NB 75976,2 MHz'),
    _seg('76032', 76000.0, 77500.0, None, 'ALL', 'NB 76032,2 MHz (segment non préféré)'),
    _seg('76032', 77500.0, 77501.0, 2700, 'ALL', 'bande étroite hors zone CEPT + satellite'),
    _seg('76032', 77501.0, 78000.0, None, 'ALL', 'segment préféré'),
    _seg('76032', 78000.0, 81500.0, None, 'ALL', 'segment non préféré'),

    _seg('122250', 122250.0, 122251.0, 2700, 'ALL', 'bande étroite'),
    _seg('122250', 122251.0, 123000.0, None, 'ALL'),

    _seg('134000', 134000.0, 134928.0, None, 'ALL', 'satellite'),
    _seg('134000', 134928.0, 134930.0, 2700, 'ALL', 'bande étroite'),
    _seg('134000', 134930.0, 136000.0, None, 'ALL'),
    _seg('134000', 136000.0, 141000.0, None, 'ALL', 'segment non préféré'),

    _seg('241000', 241000.0, 248000.0, None, 'ALL', 'segment non préféré'),
    _seg('241000', 248000.0, 248001.0, None, 'ALL', 'satellite + bande étroite'),
    _seg('241000', 248001.0, 250000.0, None, 'ALL', 'segment préféré'),
]

SEGMENTS = _23CM + _13CM + _9CM + _6CM + _3CM + _MM

# ─── Piège (c) : les segments NB alternatifs dépendent du PAYS ───────────────
# Une bande peut avoir deux ou trois segments à bande étroite selon que le
# principal est attribué ou non dans le pays. Impossible à exprimer dans la
# table plate ci-dessus — d'où cette structure séparée.
ALTERNATIVES_NB = {
    '2320': {
        'principal': (2320.000, 2322.000),
        'alternatives': [(2304.0, 2306.0), (2308.0, 2310.0), (2400.0, 2402.0)],
        'condition': "utilisés là où 2320-2322 MHz n'est pas attribué",
    },
    '10368': {
        'principal': (10368.0, 10370.0),
        'alternatives': [(10450.0, 10452.0)],
        'condition': 'bande étroite alternative',
    },
}

# ─── Piège (d) : centres d'activité — INDICATIFS, pas normatifs ──────────────
# Le document est explicite : aucun droit à une fréquence réservée ne découle
# d'une mention dans la colonne « Usage ». Ils sont donc hors des segments.
CENTRES_ACTIVITE = [
    {'bande': '1296', 'mhz': 1296.200, 'quoi': 'bande étroite'},
    {'bande': '2320', 'mhz': 2320.200, 'quoi': 'bande étroite'},
    {'bande': '3400', 'mhz': 3400.100, 'quoi': 'EME'},
    {'bande': '5760', 'mhz': 5760.200, 'quoi': 'bande étroite'},
    {'bande': '10368', 'mhz': 10368.200, 'quoi': 'bande étroite'},
    {'bande': '24048', 'mhz': 24048.200, 'quoi': 'bande étroite'},
    {'bande': '24048', 'mhz': 24025.000, 'quoi': 'large bande'},
    {'bande': '47088', 'mhz': 47088.200, 'quoi': 'bande étroite'},
    {'bande': '76032', 'mhz': 75976.200, 'quoi': 'bande étroite (préféré)'},
    {'bande': '76032', 'mhz': 76032.200, 'quoi': 'bande étroite (non préféré)'},
    {'bande': '134000', 'mhz': 134930.000, 'quoi': 'bande étroite'},
]

# ─── 23 cm : ce que la CMR-23 a changé ───────────────────────────────────────
#
# CETTE COUCHE EST NORMATIVE, contrairement au plan IARU. Elle ne redécoupe pas
# la bande : elle PLAFONNE LA PUISSANCE par sous-bande, pour protéger les
# récepteurs Galileo (RNSS) — ce qui est une contrainte d'un tout autre ordre
# qu'un segment de mode, d'où sa structure propre.
#
# e.i.r.p. = puissance rayonnée ; « puissance émetteur » = PEP ou porteuse
# délivrée à l'antenne. Les deux ne se comparent pas sans connaître le gain
# d'antenne : le champ `grandeur` le dit, il ne faut pas les confondre.
CONTRAINTES_23CM = {
    'source': 'ecc_dec_25_01',
    'bande': (1258.0, 1300.0),
    'bande_etroite': [
        {'lo': 1258.0, 'hi': 1296.0, 'grandeur': 'eirp', 'max_dbw': -17.0},
        {'lo': 1296.0, 'hi': 1298.0, 'grandeur': 'puissance_emetteur', 'max_dbw': 17.0},
        {'lo': 1298.0, 'hi': 1300.0, 'grandeur': 'puissance_emetteur', 'max_dbw': 22.0},
    ],
    # Dérogation EME, et elle est CONDITIONNELLE : antenne symétrique à hautes
    # performances (gain axial ≥ 30 dBi) pointée à 15° au moins au-dessus de
    # l'horizontale. Sans ces deux conditions, la limite ordinaire s'applique.
    'eme': {'lo': 1298.0, 'hi': 1300.0, 'grandeur': 'puissance_emetteur',
            'max_dbw': 27.0,
            'conditions': 'antenne symétrique gain ≥ 30 dBi, pointée ≥ 15° '
                          'au-dessus de l\'horizontale'},
    'satellite_montee': [
        {'lo': 1260.0, 'hi': 1262.0, 'grandeur': 'eirp', 'par_elevation': [
            {'el_min': 0, 'el_max': 15, 'max_dbw': -3.0},
            {'el_min': 15, 'el_max': 55, 'max_dbw': 17.0},
            {'el_min': 55, 'el_max': 90, 'max_dbw': 26.8},
        ]},
        {'lo': 1262.0, 'hi': 1270.0, 'grandeur': 'eirp', 'max_dbw': -17.0},
    ],
    'large_bande': [
        {'lo': 1258.0, 'hi': 1300.0, 'grandeur': 'eirp', 'max_dbw_par_mhz': -17.0,
         'note': 'bande passante > 150 kHz, ATV comprise'},
    ],
    'seuil_bande_etroite_hz': 150000,
    'note': ("Période transitoire nationale possible, jusqu'à TROIS ANS, pour "
             "les installations déjà autorisées entre 1258 et 1296 MHz."),
}

BANDES = tuple(sorted({s['bande'] for s in SEGMENTS}, key=float))


# ─── Interrogation ───────────────────────────────────────────────────────────

def segments(bande):
    """Segments d'une bande, dans l'ordre des fréquences. [] si inconnue."""
    b = str(bande or '').strip()
    return [dict(s) for s in SEGMENTS if s['bande'] == b]


def bornes(bande):
    """(basse, haute) en MHz, ou None."""
    seg = segments(bande)
    return (seg[0]['lo_mhz'], seg[-1]['hi_mhz']) if seg else None


def segment_a(bande, mhz):
    """Le segment contenant cette fréquence, ou None."""
    try:
        f = float(mhz)
    except (TypeError, ValueError):
        return None
    for s in segments(bande):
        if s['lo_mhz'] <= f < s['hi_mhz']:
            return dict(s)
    return None


def centres_activite(bande=None):
    """Centres d'activité INDICATIFS — voir piège (d). Ils ne confèrent aucun
    droit à une fréquence : ne jamais les présenter comme une règle."""
    if bande is None:
        return [dict(c) for c in CENTRES_ACTIVITE]
    b = str(bande).strip()
    return [dict(c) for c in CENTRES_ACTIVITE if c['bande'] == b]


def alternatives_nb(bande):
    """Segments à bande étroite alternatifs, CONDITIONNELS AU PAYS — piège (c).
    Retourne None si la bande n'en a pas."""
    a = ALTERNATIVES_NB.get(str(bande or '').strip())
    if not a:
        return None
    # Copie PROFONDE de la liste mutable 'alternatives' : un dict(a) de surface
    # la partagerait par référence avec le global (un appelant qui la modifie
    # corromprait la table du module). Les tuples internes sont immuables.
    out = dict(a)
    out['alternatives'] = list(out.get('alternatives', []))
    return out


def contraintes_puissance(mhz, large_bande=False):
    """Limites de puissance applicables à cette fréquence, ou None.

    Aujourd'hui seul le 23 cm en a (ECC/DEC/(25)01). Retourne un dict décrivant
    la limite ET la GRANDEUR mesurée : e.i.r.p. et puissance émetteur ne se
    comparent pas sans le gain d'antenne, les confondre donnerait un chiffre
    faux de plusieurs dizaines de dB.
    """
    try:
        f = float(mhz)
    except (TypeError, ValueError):
        return None
    lo, hi = CONTRAINTES_23CM['bande']
    if not (lo <= f <= hi):
        return None
    table = (CONTRAINTES_23CM['large_bande'] if large_bande
             else CONTRAINTES_23CM['bande_etroite'])
    for c in table:
        if c['lo'] <= f < c['hi']:
            # `note_generale` et PAS `note` : le premier jet écrasait la note
            # propre du palier (« bande passante > 150 kHz, ATV comprise ») par
            # la note générale sur la période transitoire. On perdait la seule
            # information qui dit à quoi le palier s'applique.
            return dict(c, source=CONTRAINTES_23CM['source'],
                        note_generale=CONTRAINTES_23CM['note'])
    return None


def provenance(cle):
    """Fiche de provenance d'une source. Toute donnée servie doit pouvoir dire
    d'où elle vient et ce qu'elle vaut."""
    p = PROVENANCE.get(cle)
    return dict(p) if p else None


# ─── Passerelle vers l'affichage ─────────────────────────────────────────────
# La réglette ne sait colorer que trois catégories. Cette correspondance est
# une PERTE assumée : elle sert à dessiner, jamais à décider. Un segment ATV ou
# satellite n'a pas d'équivalent dans les trois — on le laisse sans catégorie
# plutôt que de le ranger de force dans « phonie ».
_VERS_AFFICHAGE = {
    'CW': 'CW', 'CW/MGM': 'CW', 'CW/SSB/MGM': 'CW', 'SSB/CW/MGM': 'CW',
    'MGM': 'DIGITAL', 'FM/DV': 'PHONE', 'ALL': 'PHONE',
    'ATV/DATV': None, 'SAT': None,
}


def categorie_affichage(mode):
    """CW / DIGITAL / PHONE, ou None si le mode n'a pas d'équivalent."""
    return _VERS_AFFICHAGE.get(mode)
