# -*- coding: utf-8 -*-
"""Exports du log partagé : Cabrillo v3 et ADIF 3.

Fonctions PURES (testables) : build_cabrillo(qsos, cdef, cfg) et
build_adif(qsos, cfg). Les en-têtes s'appuient sur la définition du concours
(CONTEST_DEFINITIONS) et la config client (callsign, locator, opérateurs).
"""
from logx_utils import utcnow

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
# CATEGORY-BAND : vocabulaire Cabrillo v3, en LONGUEUR D'ONDE et non en
# fréquence — « 20M », pas « 14 ». Un log mono-bande déclaré ALL concourt dans
# la mauvaise catégorie.
CABRILLO_CATEGORY_BAND = {
    '1.8': '160M', '3.5': '80M', '7': '40M', '10.1': '30M', '14': '20M',
    '18': '17M', '21': '15M', '24': '12M', '28': '10M', '50': '6M',
    '70': '4M', '144': '2M', '432': '70CM', '1296': '23CM',
}

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

def _cabrillo_exchange(qso, sent=True, cdef=None):
    """Échange envoyé/reçu, au format EXIGÉ PAR LE CONCOURS.

    La composition vient de `cabrillo_exchange` dans la définition du concours,
    une liste de jetons parmi :
        'rst'     le compte-rendu ;
        'exch'    le champ N° tel que l'opérateur l'a saisi — il porte selon le
                  concours la zone CQ (CQ WW), le n° de série (WPX, WAE), l'état
                  ou la puissance (ARRL DX), la classe et la section (Field Day) ;
        'locator' le locator, pour les concours qui l'échangent réellement.

    Sans cette clé, on retombe sur l'ancien comportement (RST + N° + locator
    s'il est présent), qui convient aux concours VHF/THF européens.

    Le locator était auparavant ajouté DÈS QU'IL ÉTAIT CONNU, donc y compris en
    HF où aucun règlement ne le demande : un CQ WW partait avec « 59 14 JN18CX »
    au lieu de « 59 14 ». Les robots de réception refusent ou déclassent.
    Et le Field Day n'échange PAS de RST : y en ajouter un est tout aussi faux.
    """
    if sent:
        rst = qso.get('rst_sent', '59')
        num = qso.get('num_sent', '')
        loc = qso.get('my_locator', '')
    else:
        rst = qso.get('rst_rcvd', '59')
        num = qso.get('num_rcvd', '')
        loc = qso.get('locator', '')

    jetons = (cdef or {}).get('cabrillo_exchange')
    if not jetons:
        parts = [str(rst or '59')]
        if num:
            parts.append(str(num))
        if loc:
            parts.append(str(loc))
        return ' '.join(parts)

    valeurs = {'rst': str(rst or '59'), 'exch': str(num or ''), 'locator': str(loc or '')}
    return ' '.join(v for v in (valeurs.get(j, '') for j in jetons) if v)


def _cabrillo_qtc_lines(qtc_series, callsign):
    """Lignes 'QTC:' (format WAE-QTC officiel, vérifié auprès des règles
    publiques DARC/WAEDC et des gabarits Cabrillo publiés) :
        QTC: QRG MODE DATE TIME CALL-RX QTC-GRP CALL-TX TIME-QSO CALL-QSO NR-QSO
    Une ligne par QTC individuel (pas par série) — QTC-GRP porte le numéro de
    série ET son nombre total de QTC (ex. '3/7'). CALL-RX/CALL-TX désignent la
    station qui a reçu/transmis CETTE série ; l'une des deux est toujours notre
    propre indicatif selon `direction` ('sent' ou 'recv').
    Les séries sans détail (`entries`, format d'avant cette fonctionnalité —
    simple comptage) sont ignorées : impossible de reconstituer heure/
    indicatif/n° a posteriori, mais elles restent comptées dans le score
    (voir logx_storage.qtc_total)."""
    lines = []
    for s in (qtc_series or []):
        entries = s.get('entries') or []
        if not entries:
            continue
        partner = str(s.get('call', '')).upper().strip()
        direction = s.get('direction', 'sent')
        band = str(s.get('band', '')).strip()
        freq = CABRILLO_FREQ.get(band, str(s.get('freq', '')).strip() or band or '?')
        mode = CABRILLO_MODE.get(str(s.get('mode', 'CW')).upper().strip(), 'CW')
        date, time = _qso_datetime(s)
        date_fmt = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        grp = f"{s.get('series_number', 1)}/{len(entries)}"
        call_rx = callsign if direction == 'recv' else partner
        call_tx = partner if direction == 'recv' else callsign
        for e in entries:
            # zfill (PAS ljust) : '930' saisi doit devenir '0930', pas '9300' —
            # ljust ajoute les zéros à droite, zfill les ajoute à gauche.
            qtime = (str(e.get('time', '')).replace(':', '')[:4] or '0000').zfill(4)
            qcall = str(e.get('call', '')).upper()
            qnr = str(e.get('nr', ''))
            lines.append(f"QTC: {freq:>5} {mode:<2} {date_fmt} {time} "
                         f"{call_rx:<13} {grp:<6} {call_tx:<13} {qtime} {qcall:<13} {qnr}")
    return lines


def build_cabrillo(qsos, cdef=None, cfg=None, qtc_series=None):
    """Log partagé → Cabrillo v3 (texte). cdef : définition du concours actif.
    qtc_series : séries QTC (WAE) associées à la portée exportée, voir
    logx_storage.qtc_log — ignoré (silencieusement) pour tout concours sans QTC."""
    cdef = cdef or {}
    cfg = cfg or {}
    callsign = (cfg.get('callsign_contest') or cfg.get('callsign', '')).upper()
    claimed = sum(q.get('points', 0) or 0 for q in qsos)
    operators = ' '.join(sorted({str(q.get('operator', '')).strip()
                                 for q in qsos if q.get('operator')})) or callsign

    # Bandes et modes RÉELLEMENT présents dans le log : c'est ce qui détermine
    # la catégorie déclarée, pas ce qui était coché en config avant le concours.
    bandes = {_norm_band(q) for q in qsos if _norm_band(q)}
    modes = {CABRILLO_MODE.get(_norm_mode(q), 'PH') for q in qsos}
    cat_band = CABRILLO_CATEGORY_BAND.get(next(iter(bandes)), 'ALL') if len(bandes) == 1 else 'ALL'
    if modes == {'CW'}:
        cat_mode = 'CW'
    elif modes == {'PH'}:
        cat_mode = 'SSB'
    elif modes == {'RY'} or modes == {'DG'}:
        cat_mode = 'RTTY' if modes == {'RY'} else 'DIGI'
    else:
        cat_mode = 'MIXED'
    # ASSISTED : utiliser le cluster DX fait basculer de catégorie dans TOUS les
    # grands règlements. LogX AI intègre le cluster, le RBN et PSK Reporter :
    # déclarer NON-ASSISTED par défaut serait une fausse déclaration. On suit
    # donc l'état réel de la config plutôt qu'une valeur figée.
    assiste = any(str(cfg.get(k, '')).strip() not in ('', '0', 'False', 'false')
                  for k in ('cluster_spot_enabled', 'rbn_enabled'))

    lines = [
        'START-OF-LOG: 3.0',
        f"CONTEST: {cdef.get('cabrillo_name', cfg.get('contest', 'UNKNOWN'))}",
        f"CALLSIGN: {callsign}",
        'CATEGORY-OPERATOR: ' + ('MULTI-OP' if len(operators.split()) > 1 else 'SINGLE-OP'),
        f"CATEGORY-ASSISTED: {'ASSISTED' if assiste else 'NON-ASSISTED'}",
        f"CATEGORY-BAND: {cat_band}",
        f"CATEGORY-MODE: {cat_mode}",
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
        f"SOAPBOX: Exporte le {utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
    ]
    for q in qsos:
        band = _norm_band(q)
        freq = CABRILLO_FREQ.get(band, band or '?')
        mode = CABRILLO_MODE.get(_norm_mode(q), 'PH')
        date, time = _qso_datetime(q)
        date_fmt = f"{date[:4]}-{date[4:6]}-{date[6:8]}"
        sent = _cabrillo_exchange(q, sent=True, cdef=cdef)
        rcvd = _cabrillo_exchange(q, sent=False, cdef=cdef)
        dx = str(q.get('call', '')).upper()
        lines.append(f"QSO: {freq:>5} {mode} {date_fmt} {time} "
                     f"{callsign:<13} {sent:<17} {dx:<13} {rcvd}")
    lines.extend(_cabrillo_qtc_lines(qtc_series, callsign))
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
    import logx_satellites as sat
    records = []
    for q in qsos:
        date, time = _qso_datetime(q)
        # Calculé UNE fois : les deux champs satellite vont ensemble ou pas du
        # tout (voir logx_satellites.champs_adif).
        sat_q = sat.champs_adif(q)
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
            # État US : porté par l'ADIF pour que le WAS reste calculable après
            # un export/réimport, ou dans le logiciel du correspondant.
            _adif_field('state', q.get('state', '')),
            _adif_field('my_gridsquare', q.get('my_locator', cfg.get('locator', ''))),
            _adif_field('contest_id', q.get('contest', '')),
            _adif_field('operator', q.get('operator', '')),
            _adif_field('distance', q.get('dist', '')),
            # SATELLITE : les DEUX champs sans lesquels LoTW crédite le QSO
            # comme un contact TERRESTRE ordinaire. PROP_MODE=SAT est ce qui le
            # range dans la catégorie satellite (DXCC, WAS, VUCC et mentions
            # associées), SAT_NAME dit lequel. Voir logx_satellites : le nom
            # doit être orthographié exactement comme LoTW l'attend, sans quoi
            # c'est le fichier ENTIER qui est rejeté au téléversement.
            _adif_field('prop_mode', sat_q.get('prop_mode', '')),
            _adif_field('sat_name', sat_q.get('sat_name', '')),
            # Activation POTA/SOTA/IOTA/WWFF : ma référence (MY_SIG) + réf. du
            # correspondant (SIG) pour les Park-to-Park / Summit-to-Summit.
            _adif_field('my_sig', q.get('my_sig', '')),
            _adif_field('my_sig_info', q.get('my_sig_info', '')),
            _adif_field('sig', q.get('sig', '')),
            _adif_field('sig_info', q.get('sig_info', '')),
        ]
        records.append(''.join(f for f in fields if f) + '<EOR>')
    return header + '\n'.join(records) + '\n'
