# -*- coding: utf-8 -*-
"""Énumérations officielles ADIF 3.1.7 (Band, Mode/Submode) — recopiées en dur
depuis www.adif.org/317/ADIF_317.htm plutôt que téléchargées à l'exécution
(le projet est offline-first : cette validation doit fonctionner sans réseau,
et le standard ADIF évolue rarement — voir PRD EV-1.1).

Sert de FILET pour l'import ADIF (logx_qsl._band_from_record,
logx_import.parse_adif_to_qsos) : couvre bien plus de bandes/modes que les
listes internes de l'app (ADIF_BAND dans logx_export.py, ~19 bandes utiles
aux concours gérés), pour ne plus rejeter à tort un record ADIF valide mais
rare (60m, 2190m, un mode numérique récent...).
"""

# {libellé ADIF: (fréq. basse MHz, fréq. haute MHz)} — table complète, ordre
# de la spec officielle.
ADIF_BANDS = {
    '2190m': (0.1357, 0.1378), '630m': (0.472, 0.479), '560m': (0.501, 0.504),
    '160m': (1.8, 2.0), '80m': (3.5, 4.0), '60m': (5.06, 5.45),
    '40m': (7.0, 7.3), '30m': (10.1, 10.15), '20m': (14.0, 14.35),
    '17m': (18.068, 18.168), '15m': (21.0, 21.45), '12m': (24.890, 24.99),
    '10m': (28.0, 29.7), '8m': (40, 45), '6m': (50, 54),
    '5m': (54.000001, 69.9), '4m': (70, 71), '2m': (144, 148),
    '1.25m': (222, 225), '70cm': (420, 450), '33cm': (902, 928),
    '23cm': (1240, 1300), '13cm': (2300, 2450), '9cm': (3300, 3500),
    '6cm': (5650, 5925), '3cm': (10000, 10500), '1.25cm': (24000, 24250),
    '6mm': (47000, 47200), '4mm': (75500, 81000), '2.5mm': (119980, 123000),
    '2mm': (134000, 149000), '1mm': (241000, 250000),
    'submm': (300000, 7500000),
}


def band_from_freq(freq):
    """Fréquence ADIF (toujours en MHz, cf. spec ADIF §FREQ — seul appelant
    réel : logx_qsl._band_from_record via l'alias _band_from_freq_adif) →
    libellé de bande ADIF officiel, '' si hors de toute bande reconnue.
    Repli utilisé quand le champ BAND est absent d'un record ADIF mais FREQ
    est présent."""
    try:
        mhz = float(str(freq).replace(',', '.'))
    except (ValueError, TypeError):
        return ''
    # Les intervalles sont FERMÉS (lo <= f <= hi) pour préserver le classement
    # des fréquences situées exactement sur une borne SUPÉRIEURE de bande non
    # suivie d'une bande contiguë (ex. 14,35 MHz doit rester « 20m »). Ne PAS
    # passer en intervalles semi-ouverts globaux : ça ferait disparaître ces
    # fréquences-bornes. Le seul chevauchement possible (6m/5m à 54 MHz) est
    # évité par le seuil 54.000001 de la table ADIF_BANDS : 54,000000 → 6m,
    # 54,000001 → 5m ; le trou théorique de 1 Hz est négligeable en pratique.
    for band, (lo, hi) in ADIF_BANDS.items():
        if lo <= mhz <= hi:
            return band
    return ''


# {Mode racine: (submodes...)} — table complète de la spec officielle.
ADIF_MODES = {
    'AM': (), 'ARDOP': (), 'ATV': (),
    'CHIP': ('CHIP64', 'CHIP128'),
    'CLO': (), 'CONTESTI': (),
    'CW': ('PCW',),
    'DIGITALVOICE': ('C4FM', 'DMR', 'DSTAR', 'FREEDV', 'M17'),
    'DOMINO': ('DOM-M', 'DOM4', 'DOM5', 'DOM8', 'DOM11', 'DOM16', 'DOM22',
               'DOM44', 'DOM88', 'DOMINOEX', 'DOMINOF'),
    'DYNAMIC': ('FREEDATA', 'VARA HF', 'VARA SATELLITE', 'VARA FM 1200', 'VARA FM 9600'),
    'FAX': (), 'FM': (), 'FSK441': (),
    'FSK': ('SCAMP_FAST', 'SCAMP_SLOW', 'SCAMP_VSLOW'),
    'FT8': (),
    'HELL': ('FMHELL', 'FSKH105', 'FSKH245', 'FSKHELL', 'HELL80', 'HELLX5',
              'HELLX9', 'HFSK', 'PSKHELL', 'SLOWHELL'),
    'ISCAT': ('ISCAT-A', 'ISCAT-B'),
    'JT4': ('JT4A', 'JT4B', 'JT4C', 'JT4D', 'JT4E', 'JT4F', 'JT4G'),
    'JT6M': (), 'JT44': (),
    'JT9': ('JT9-1', 'JT9-2', 'JT9-5', 'JT9-10', 'JT9-30', 'JT9A', 'JT9B',
            'JT9C', 'JT9D', 'JT9E', 'JT9E FAST', 'JT9F', 'JT9F FAST', 'JT9G',
            'JT9G FAST', 'JT9H', 'JT9H FAST'),
    'JT65': ('JT65A', 'JT65B', 'JT65B2', 'JT65C', 'JT65C2'),
    'MFSK': ('FSQCALL', 'FST4', 'FST4W', 'FT2', 'FT4', 'JS8', 'JTMS', 'MFSK4',
             'MFSK8', 'MFSK11', 'MFSK16', 'MFSK22', 'MFSK31', 'MFSK32',
             'MFSK64', 'MFSK64L', 'MFSK128', 'MFSK128L', 'Q65'),
    'MSK144': (),
    'MTONE': ('SCAMP_OO', 'SCAMP_OO_SLW'),
    'MT63': (),
    'OFDM': ('RIBBIT_PIX', 'RIBBIT_SMS'),
    'OLIVIA': ('OLIVIA 4/125', 'OLIVIA 4/250', 'OLIVIA 8/250', 'OLIVIA 8/500',
               'OLIVIA 16/500', 'OLIVIA 16/1000', 'OLIVIA 32/1000'),
    'OPERA': ('OPERA-BEACON', 'OPERA-QSO'),
    'PAC': ('PAC2', 'PAC3', 'PAC4'),
    'PAX': ('PAX2',), 'PKT': (),
    'PSK': ('8PSK125', '8PSK125F', '8PSK125FL', '8PSK250', '8PSK250F',
            '8PSK250FL', '8PSK500', '8PSK500F', '8PSK1000', '8PSK1000F',
            '8PSK1200F', 'FSK31', 'PSK10', 'PSK31', 'PSK63', 'PSK63F',
            'PSK63RC4', 'PSK63RC5', 'PSK63RC10', 'PSK63RC20', 'PSK63RC32',
            'PSK125', 'PSK125C12', 'PSK125R', 'PSK125RC10', 'PSK125RC12',
            'PSK125RC16', 'PSK125RC4', 'PSK125RC5', 'PSK250', 'PSK250C6',
            'PSK250R', 'PSK250RC2', 'PSK250RC3', 'PSK250RC5', 'PSK250RC6',
            'PSK250RC7', 'PSK500', 'PSK500C2', 'PSK500C4', 'PSK500R',
            'PSK500RC2', 'PSK500RC3', 'PSK500RC4', 'PSK800C2', 'PSK800RC2',
            'PSK1000', 'PSK1000C2', 'PSK1000R', 'PSK1000RC2', 'PSKAM10',
            'PSKAM31', 'PSKAM50', 'PSKFEC31', 'QPSK31', 'QPSK63', 'QPSK125',
            'QPSK250', 'QPSK500', 'SIM31'),
    'PSK2K': (), 'Q15': (),
    'QRA64': ('QRA64A', 'QRA64B', 'QRA64C', 'QRA64D', 'QRA64E'),
    'ROS': ('ROS-EME', 'ROS-HF', 'ROS-MF'),
    'RTTY': ('ASCI',), 'RTTYM': (),
    'SSB': ('LSB', 'USB'),
    'SSTV': (), 'T10': (),
    'THOR': ('THOR-M', 'THOR4', 'THOR5', 'THOR8', 'THOR11', 'THOR16',
              'THOR22', 'THOR25X4', 'THOR50X1', 'THOR50X2', 'THOR100'),
    'THRB': ('THRBX', 'THRBX1', 'THRBX2', 'THRBX4', 'THROB1', 'THROB2', 'THROB4'),
    'TOR': ('AMTORFEC', 'GTOR', 'NAVTEX', 'SITORB'),
    'V4': (), 'VOI': (), 'WINMOR': (), 'WSPR': (),
}

# Aplati (modes racine + submodes), pour une vérification d'appartenance
# simple — un ADIF réel place parfois un submode directement dans MODE
# (ex. MODE=FT4 au lieu de MODE=MFSK;SUBMODE=FT4), cas fréquent avec WSJT-X.
ADIF_MODES_FLAT = frozenset(ADIF_MODES) | frozenset(
    sm for subs in ADIF_MODES.values() for sm in subs)


def is_known_mode(mode):
    """True si `mode` (déjà normalisé, ex. upper()) est un Mode ou Submode
    ADIF 3.1.7 officiel — pas de distinction Mode/Submode ici (voir
    ADIF_MODES_FLAT), pour tolérer les ADIF réels qui ne respectent pas
    toujours strictement la distinction."""
    return str(mode or '').strip().upper() in ADIF_MODES_FLAT
