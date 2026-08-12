# -*- coding: utf-8 -*-
"""Drapeau + nom de pays (français) à partir d'un indicatif.

Le module logx_dxcc (cty.dat) donne le pays en anglais et le préfixe
principal mais AUCUN drapeau. Ici on associe le préfixe principal DXCC
(logx_dxcc.country_key) à un code ISO-3166 alpha-2 + un nom FR, puis on
dérive l'emoji drapeau à partir de l'ISO2 (indicateurs régionaux Unicode).

Sert l'écran mural (pays + drapeau) et tout affichage voulant un rendu « joli »
d'un indicatif. Déterministe, hors-ligne, aucune dépendance réseau.
"""

# Préfixe principal DXCC (country_key) -> (ISO2, nom FR).
# Couverture : Europe complète + grandes entités DX (contest). Les entités non
# listées retombent sur le nom anglais de cty.dat, sans drapeau.
PREFIX_INFO = {
    # --- France & territoires ---
    'F': ('FR', 'France'), 'TK': ('FR', 'Corse'),
    'FG': ('GP', 'Guadeloupe'), 'FM': ('MQ', 'Martinique'),
    'FR': ('RE', 'La Réunion'), 'FY': ('GF', 'Guyane'),
    'FO': ('PF', 'Polynésie fr.'), 'FK': ('NC', 'Nouvelle-Calédonie'),
    'TO': ('FR', 'DOM-TOM'), 'FH': ('YT', 'Mayotte'), 'FP': ('PM', 'St-Pierre-et-M.'),
    # --- Europe ---
    'DL': ('DE', 'Allemagne'), 'G': ('GB', 'Angleterre'), 'GM': ('GB', 'Écosse'),
    'GW': ('GB', 'Pays de Galles'), 'GI': ('GB', 'Irlande du Nord'),
    'GD': ('IM', 'Île de Man'), 'GJ': ('JE', 'Jersey'), 'GU': ('GG', 'Guernesey'),
    'EI': ('IE', 'Irlande'), 'ON': ('BE', 'Belgique'), 'PA': ('NL', 'Pays-Bas'),
    'LX': ('LU', 'Luxembourg'), 'HB': ('CH', 'Suisse'), 'HB0': ('LI', 'Liechtenstein'),
    'OE': ('AT', 'Autriche'), 'I': ('IT', 'Italie'), 'IS': ('IT', 'Sardaigne'),
    'EA': ('ES', 'Espagne'), 'EA6': ('ES', 'Baléares'), 'EA8': ('ES', 'Canaries'),
    'EA9': ('ES', 'Ceuta et Melilla'), 'CT': ('PT', 'Portugal'),
    'CT3': ('PT', 'Madère'), 'CU': ('PT', 'Açores'),
    'OK': ('CZ', 'Rép. tchèque'), 'OM': ('SK', 'Slovaquie'), 'SP': ('PL', 'Pologne'),
    'HA': ('HU', 'Hongrie'), 'YO': ('RO', 'Roumanie'), 'LZ': ('BG', 'Bulgarie'),
    'YU': ('RS', 'Serbie'), 'E7': ('BA', 'Bosnie-Herz.'), '9A': ('HR', 'Croatie'),
    'S5': ('SI', 'Slovénie'), 'Z3': ('MK', 'Macédoine du N.'), 'ZA': ('AL', 'Albanie'),
    'SV': ('GR', 'Grèce'), 'SV5': ('GR', 'Dodécanèse'), 'SV9': ('GR', 'Crète'),
    'ZB': ('GI', 'Gibraltar'), '9H': ('MT', 'Malte'), '5B': ('CY', 'Chypre'),
    'OH': ('FI', 'Finlande'), 'OH0': ('AX', 'Åland'), 'SM': ('SE', 'Suède'),
    'LA': ('NO', 'Norvège'), 'OZ': ('DK', 'Danemark'), 'TF': ('IS', 'Islande'),
    'ES': ('EE', 'Estonie'), 'YL': ('LV', 'Lettonie'), 'LY': ('LT', 'Lituanie'),
    'UR': ('UA', 'Ukraine'), 'EW': ('BY', 'Biélorussie'), 'ER': ('MD', 'Moldavie'),
    'UA': ('RU', 'Russie'), 'UA2': ('RU', 'Kaliningrad'), 'UA9': ('RU', 'Russie asiat.'),
    'T7': ('SM', 'St-Marin'), '4U1V': ('AT', 'Vienne ONU'), 'HV': ('VA', 'Vatican'),
    '3A': ('MC', 'Monaco'), 'C3': ('AD', 'Andorre'), '4O': ('ME', 'Monténégro'),
    'TA': ('TR', 'Turquie'), '4X': ('IL', 'Israël'), 'JW': ('SJ', 'Svalbard'),
    # --- Amériques ---
    'K': ('US', 'États-Unis'), 'KH6': ('US', 'Hawaï'), 'KL': ('US', 'Alaska'),
    'VE': ('CA', 'Canada'), 'XE': ('MX', 'Mexique'), 'PY': ('BR', 'Brésil'),
    'LU': ('AR', 'Argentine'), 'CE': ('CL', 'Chili'), 'CX': ('UY', 'Uruguay'),
    'HK': ('CO', 'Colombie'), 'YV': ('VE', 'Venezuela'), 'OA': ('PE', 'Pérou'),
    'CP': ('BO', 'Bolivie'), 'HC': ('EC', 'Équateur'), 'ZP': ('PY', 'Paraguay'),
    'PJ2': ('CW', 'Curaçao'), 'CO': ('CU', 'Cuba'), 'HI': ('DO', 'Rép. dominicaine'),
    'KP4': ('PR', 'Porto Rico'), 'TG': ('GT', 'Guatemala'), 'HP': ('PA', 'Panama'),
    'TI': ('CR', 'Costa Rica'), 'V3': ('BZ', 'Belize'), 'FG5': ('GP', 'Guadeloupe'),
    # --- Asie / Pacifique ---
    'JA': ('JP', 'Japon'), 'BY': ('CN', 'Chine'), 'BV': ('TW', 'Taïwan'),
    'HL': ('KR', 'Corée du Sud'), 'VR': ('HK', 'Hong Kong'), 'DU': ('PH', 'Philippines'),
    'HS': ('TH', 'Thaïlande'), 'YB': ('ID', 'Indonésie'), '9M': ('MY', 'Malaisie'),
    '9V': ('SG', 'Singapour'), 'XV': ('VN', 'Viêt Nam'), 'VU': ('IN', 'Inde'),
    'AP': ('PK', 'Pakistan'), 'EP': ('IR', 'Iran'), 'A4': ('OM', 'Oman'),
    'A6': ('AE', 'Émirats A. U.'), 'A7': ('QA', 'Qatar'), 'A9': ('BH', 'Bahreïn'),
    'HZ': ('SA', 'Arabie saoudite'), '9K': ('KW', 'Koweït'), 'YK': ('SY', 'Syrie'),
    'OD': ('LB', 'Liban'), 'JY': ('JO', 'Jordanie'), 'UN': ('KZ', 'Kazakhstan'),
    'VK': ('AU', 'Australie'), 'ZL': ('NZ', 'Nouvelle-Zélande'),
    # --- Afrique ---
    'CN': ('MA', 'Maroc'), '7X': ('DZ', 'Algérie'), '3V': ('TN', 'Tunisie'),
    'SU': ('EG', 'Égypte'), '5A': ('LY', 'Libye'), 'ZS': ('ZA', 'Afrique du Sud'),
    '5N': ('NG', 'Nigéria'), '5T': ('MR', 'Mauritanie'), '6W': ('SN', 'Sénégal'),
    'TR': ('GA', 'Gabon'), 'TU': ('CI', "Côte d'Ivoire"), '9G': ('GH', 'Ghana'),
    'ET': ('ET', 'Éthiopie'), '5Z': ('KE', 'Kenya'), '5H': ('TZ', 'Tanzanie'),
    '3B8': ('MU', 'Maurice'), '5R': ('MG', 'Madagascar'),
}

# Alias : certains country_key possibles -> clé PREFIX_INFO canonique
_ALIAS = {'W': 'K', 'N': 'K', 'AA': 'K', 'M': 'G', '2E': 'G', 'R': 'UA'}


def flag_emoji(iso2):
    """ISO-3166 alpha-2 -> emoji drapeau (indicateurs régionaux Unicode)."""
    iso2 = (iso2 or '').upper()
    if len(iso2) != 2 or not iso2.isalpha():
        return ''
    return ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in iso2)


def flag_for_prefix(prefix):
    """Préfixe principal DXCC -> {'flag', 'country'(FR)}. '' si inconnu.
    Sert à énumérer les entités (chasse aux pays)."""
    info = PREFIX_INFO.get(_ALIAS.get(prefix, prefix))
    if info:
        return {'flag': flag_emoji(info[0]), 'country': info[1]}
    return {'flag': '', 'country': ''}


def flag_and_country(call):
    """Indicatif -> {'flag': emoji, 'country': nom FR, 'prefix': clé DXCC}.

    Repli propre : si le préfixe n'est pas dans PREFIX_INFO, on garde le nom
    anglais de cty.dat et un drapeau vide. Jamais d'exception."""
    try:
        import logx_dxcc as dxcc
    except Exception:
        return {'flag': '', 'country': '', 'prefix': ''}
    try:
        key = dxcc.country_key(call) or ''
    except Exception:
        key = ''
    key = _ALIAS.get(key, key)
    info = PREFIX_INFO.get(key)
    if info:
        return {'flag': flag_emoji(info[0]), 'country': info[1], 'prefix': key}
    # Repli : nom anglais cty.dat
    try:
        look = dxcc.lookup(call) or {}
    except Exception:
        look = {}
    return {'flag': '', 'country': look.get('country', '') or '', 'prefix': key}
