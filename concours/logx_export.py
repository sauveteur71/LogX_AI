# -*- coding: utf-8 -*-
"""Exports du log partagé : Cabrillo v3 et ADIF 3.

Fonctions PURES (testables) : build_cabrillo(qsos, cdef, cfg) et
build_adif(qsos, cfg). Les en-têtes s'appuient sur la définition du concours
(CONTEST_DEFINITIONS) et la config client (callsign, locator, opérateurs).
"""
import datetime

# Bande interne (MHz, chaîne) → fréquence Cabrillo (kHz nominal en HF,
# désignateur de bande au-delà — spécification Cabrillo v3).
CABRILLO_FREQ = {
    '1.8': '1800', '3.5': '3500', '7': '7000', '10.1': '10100', '14': '14000',
    '18': '18100', '21': '21000', '24': '24900', '28': '28000', '50': '50',
    '70': '70', '144': '144', '432': '432', '1296': '1.2G', '2320': '2.3G',
    '3400': '3.4G', '5760': '5.7G', '10368': '10G',
    '24048': '24G', '47088': '47G',
}
CABRILLO_MODE = {'SSB': 'PH', 'USB': 'PH', 'LSB': 'PH', 'FM': 'FM',
                 'CW': 'CW', 'RTTY': 'RY', 'DIGI': 'DG', 'FT8': 'DG', 'FT4': 'DG'}

# Bande interne → bande ADIF
ADIF_BAND = {
    '1.8': '160m', '3.5': '80m', '7': '40m', '10.1': '30m', '14': '20m',
    '18': '17m', '21': '15m', '24': '12m', '28': '10m', '50': '6m', '70': '4m',
    '144': '2m', '432': '70cm', '1296': '23cm', '2320': '13cm', '3400': '9cm',
    '5760': '6cm', '10368': '3cm', '24048': '1.25cm', '47088': '6mm',
}


def _norm_band(qso):
    return str(qso.get('band', '')).strip()


def _norm_mode(qso):
    return str(qso.get('mode', 'SSB')).upper().strip() or 'SSB'


def _qso_datetime(qso):
    """(AAAAMMJJ, HHMM) à partir des champs du log partagé."""
    date = str(qso.get('date', '')).replace('-', '')[:8]
    time = str(qso.get('time', '')).replace(':', '')[:4]
    return date or '19000101', (time or '0000').ljust(4, '0')


# ─── CABRILLO ────────────────────────────────────────────────────────────────

def _cabrillo_exchange(qso, sent=True):
    """Échange envoyé/reçu : RST + numéro (+ locator si présent) — colle au
    format déclaré par la plupart des concours HF/VHF européens."""
    if sent:
        rst = qso.get('rst_sent', '59')
        num = qso.get('num_sent', '')
        loc = qso.get('my_locator', '')
    else:
        rst = qso.get('rst_rcvd', '59')
        num = qso.get('num_rcvd', '')
        loc = qso.get('locator', '')
    parts = [str(rst or '59')]
    if num:
        parts.append(str(num))
    if loc:
        parts.append(str(loc))
    return ' '.join(parts)


def build_cabrillo(qsos, cdef=None, cfg=None):
    """Log partagé → Cabrillo v3 (texte). cdef : définition du concours actif."""
    cdef = cdef or {}
    cfg = cfg or {}
    callsign = (cfg.get('callsign_contest') or cfg.get('callsign', '')).upper()
    claimed = sum(q.get('points', 0) or 0 for q in qsos)
    operators = ' '.join(sorted({str(q.get('operator', '')).strip()
                                 for q in qsos if q.get('operator')})) or callsign

    lines = [
        'START-OF-LOG: 3.0',
        f"CONTEST: {cdef.get('cabrillo_name', cfg.get('contest', 'UNKNOWN'))}",
        f"CALLSIGN: {callsign}",
        'CATEGORY-OPERATOR: ' + ('MULTI-OP' if len(operators.split()) > 1 else 'SINGLE-OP'),
        'CATEGORY-TRANSMITTER: ONE',
        # Les paliers QRP10/QRP15 (finesse propre à LogX AI) se déclarent tous
        # comme la catégorie standard Cabrillo « QRP », qui ne connaît que HIGH/LOW/QRP.
        f"CATEGORY-POWER: {('QRP' if str(cfg.get('power_class', 'LOW')).upper().startswith('QRP') else str(cfg.get('power_class', 'LOW')).upper())}",
        f"CLAIMED-SCORE: {claimed}",
        f"OPERATORS: {operators}",
        f"GRID-LOCATOR: {cfg.get('locator', '')}",
        f"NAME: {cfg.get('op_name', '')}",
        f"EMAIL: {cfg.get('email', '')}",
        f"CLUB: {cfg.get('club', '')}",
        f"CREATED-BY: LogX AI",
        f"SOAPBOX: Exporte le {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
    ]
    for q in qsos:
        band = _norm_band(q)
        freq = CABRILLO_FREQ.get(band, band or '?')
        mode = CABRILLO_MODE.get(_norm_mode(q), 'PH')
        date, time = _qso_datetime(q)
        date_fmt = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        sent = _cabrillo_exchange(q, sent=True)
        rcvd = _cabrillo_exchange(q, sent=False)
        dx = str(q.get('call', '')).upper()
        lines.append(f"QSO: {freq:>5} {mode} {date_fmt} {time} "
                     f"{callsign:<13} {sent:<17} {dx:<13} {rcvd}")
    lines.append('END-OF-LOG:')
    return '\n'.join(lines) + '\n'


# ─── ADIF ────────────────────────────────────────────────────────────────────

def _adif_field(name, value):
    value = str(value)
    return f"<{name}:{len(value)}>{value}" if value else ''


def build_adif(qsos, cfg=None):
    """Log partagé → ADIF 3 (texte). Le programme lisait déjà l'ADIF,
    il sait maintenant l'écrire."""
    cfg = cfg or {}
    callsign = (cfg.get('callsign_contest') or cfg.get('callsign', '')).upper()
    header = (f"Log LogX AI — {callsign}\n"
              + _adif_field('adif_ver', '3.1.4')
              + _adif_field('programid', 'LogX AI')
              + '<EOH>\n')
    records = []
    for q in qsos:
        date, time = _qso_datetime(q)
        fields = [
            _adif_field('call', str(q.get('call', '')).upper()),
            _adif_field('qso_date', date),
            _adif_field('time_on', time),
            _adif_field('band', ADIF_BAND.get(_norm_band(q), '')),
            _adif_field('freq', str(q.get('freq', '') or '')),
            _adif_field('mode', _norm_mode(q)),
            _adif_field('rst_sent', q.get('rst_sent', '')),
            _adif_field('rst_rcvd', q.get('rst_rcvd', '')),
            _adif_field('stx_string', q.get('num_sent', '')),
            _adif_field('srx_string', q.get('num_rcvd', '')),
            _adif_field('gridsquare', q.get('locator', '')),
            _adif_field('my_gridsquare', q.get('my_locator', cfg.get('locator', ''))),
            _adif_field('contest_id', q.get('contest', '')),
            _adif_field('operator', q.get('operator', '')),
            _adif_field('distance', q.get('dist', '')),
            # Activation POTA/SOTA/IOTA/WWFF : ma référence (MY_SIG) + réf. du
            # correspondant (SIG) pour les Park-to-Park / Summit-to-Summit.
            _adif_field('my_sig', q.get('my_sig', '')),
            _adif_field('my_sig_info', q.get('my_sig_info', '')),
            _adif_field('sig', q.get('sig', '')),
            _adif_field('sig_info', q.get('sig_info', '')),
        ]
        records.append(''.join(f for f in fields if f) + '<EOR>')
    return header + '\n'.join(records) + '\n'
