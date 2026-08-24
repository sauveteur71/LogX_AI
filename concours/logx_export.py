# -*- coding: utf-8 -*-
"""Exports du log partagé : Cabrillo v3 et ADIF 3.

Fonctions PURES (testables) : build_cabrillo(qsos, cdef, cfg) et
build_adif(qsos, cfg). Les en-têtes s'appuient sur la définition du concours
(CONTEST_DEFINITIONS) et la config client (callsign, locator, opérateurs).
"""
import re

from logx_utils import utcnow
# A10 (docs/FEUILLE_DE_ROUTE.md) : calc_total_score() applique le compte de
# multiplicateurs au CLAIMED-SCORE — sans quoi le score soumis au comité du
# concours était juste la somme des points par QSO, sans jamais la
# multiplier (faux pour tout concours à multiplicateur : CQ WW, WPX, ARRL
# DX, IARU HF, REF...).
from logx_scoring import calc_total_score
# Sous-chantier B (lot 3) : tags ADIF dédiés par programme d'activation
# (SOTA_REF, POTA_REF…). Source unique = logx_activation (qui les dérive de
# PROGRAM_SPECS). logx_activation n'importe que `re` : pas de cycle d'import.
from logx_activation import ADIF_PROGRAM_TAGS

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
                 'CW': 'CW', 'RTTY': 'RY', 'DIGI': 'DG', 'FT8': 'DG', 'FT4': 'DG',
                 'FT2': 'DG', 'PSK': 'DG'}
# CATEGORY-BAND : vocabulaire Cabrillo v3, en LONGUEUR D'ONDE et non en
# fréquence — « 20M », pas « 14 ». Un log mono-bande déclaré ALL concourt dans
# la mauvaise catégorie.
# Valeurs vérifiées contre la spec officielle WWROF (successeur ARRL du
# format Cabrillo v3, https://wwrof.org/cabrillo/cabrillo-v3-header/,
# section CATEGORY-BAND) : au-delà de 432 (bare, PAS « 70CM »), les bandes
# micro-ondes utilisent un désignateur EN GHz — « 1.2G »/« 2.3G »/« 3.4G »/
# « 5.7G »/« 10G »/« 24G »/« 47G » — jamais un libellé « xxCM » façon ADIF.
# Un constat d'audit avait signalé « 24048 »/« 47088 » (contests THF REF
# jusqu'à 47 GHz, voir logx_definitions REF_NAT_THF/REF_F8TD/REF_IARU_UHF)
# absents de la table : ajoutés ici. Un fil ARRL-Contesting confirme aussi
# que les anciens libellés 119G/142G ont été corrigés en 122G/134G — LogX AI
# n'exporte jamais ces deux bandes (au-delà de 47 GHz), gardé pour mémoire
# seulement dans ce commentaire, pas dans la table.
CABRILLO_CATEGORY_BAND = {
    '1.8': '160M', '3.5': '80M', '7': '40M', '10.1': '30M', '14': '20M',
    '18': '17M', '21': '15M', '24': '12M', '28': '10M', '50': '6M',
    '70': '4M', '144': '2M', '432': '432', '1296': '1.2G',
    '2320': '2.3G', '3400': '3.4G', '5760': '5.7G', '10368': '10G',
    '24048': '24G', '47088': '47G',
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
    # zfill (PAS ljust) : '930' saisi doit devenir '0930', pas '9300' — ljust
    # ajoute les zéros à droite, zfill les ajoute à gauche (même correctif
    # que _cabrillo_qtc_lines() un peu plus bas dans ce fichier).
    return date or '19000101', (time or '0000').zfill(4)


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
        # Jamais la valeur BRUTE de band en repli (voir build_cabrillo un peu
        # plus bas) : une bande non reconnue tombe sur '?', comme CABRILLO_MODE
        # tombe déjà sur 'PH' — 'freq' explicite reste un repli légitime, ce
        # n'est pas le champ à risque ici.
        freq = CABRILLO_FREQ.get(band, str(s.get('freq', '')).strip() or '?')
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


def build_cabrillo(qsos, cdef=None, cfg=None, qtc_series=None, claimed_override=None):
    """Log partagé → Cabrillo v3 (texte). cdef : définition du concours actif.
    claimed_override : impose le CLAIMED-SCORE plutôt que de le calculer
    (logx_archive.import_external_log : le score d'un log EXTERNE importé
    est une valeur déclarée/connue, à préserver telle quelle — pas un total
    recalculable depuis des QSO reconstruits sans toutes leurs données
    d'origine, voir calc_total_score).
    qtc_series : séries QTC (WAE) associées à la portée exportée, voir
    logx_storage.qtc_log — ignoré (silencieusement) pour tout concours sans QTC."""
    cdef = cdef or {}
    cfg = cfg or {}
    callsign = (cfg.get('callsign_contest') or cfg.get('callsign', '')).upper()
    # + points QTC (WAE) : cette fonction affirmait déjà dans sa propre
    # docstring (voir _cabrillo_qtc_lines ci-dessus) qu'ils "restent comptés
    # dans le score", mais CLAIMED-SCORE ne les ajoutait pas — comptage
    # identique à logx_storage.qtc_total(), directement sur qtc_series (déjà
    # filtrée sur la bonne portée par l'appelant). No-op hors WAE.
    # Les QTC entrent AVANT la multiplication par les multiplicateurs (règle
    # WAE : score = (QSO + QTC) × multiplicateurs), via extra_points plutôt
    # qu'une addition après coup.
    qtc_points = sum(s.get('count', 0) or 0 for s in (qtc_series or []))
    claimed = claimed_override if claimed_override is not None \
        else calc_total_score(qsos, cdef, extra_points=qtc_points)
    # Créneaux BRUTS ('OP1', 'OP2'...) : sert uniquement à décider SINGLE-OP vs
    # MULTI-OP — deux créneaux distincts restent deux opérateurs même sans
    # config operators[] permettant de les résoudre en indicatifs réels (sans
    # quoi, sans cette config, la résolution renverrait le même indicatif de
    # station pour les deux et ferait dégénérer à tort en SINGLE-OP).
    raw_ops = {str(q.get('operator', '')).strip() for q in qsos if q.get('operator')}
    # Indicatifs RÉELS pour la ligne humaine OPERATORS: — jamais l'ID de
    # créneau brut ('OP1') dans un fichier soumis à l'organisateur.
    operators = ' '.join(sorted({resolve_operator_callsign(op, cfg) for op in raw_ops})) or callsign

    # Bandes et modes RÉELLEMENT présents dans le log : c'est ce qui détermine
    # la catégorie déclarée, pas ce qui était coché en config avant le concours.
    bandes = {_norm_band(q) for q in qsos if _norm_band(q)}
    modes = {CABRILLO_MODE.get(_norm_mode(q), 'PH') for q in qsos}
    cat_band = CABRILLO_CATEGORY_BAND.get(next(iter(bandes)), 'ALL') if len(bandes) == 1 else 'ALL'
    if modes == {'CW'}:
        cat_mode = 'CW'
    elif modes == {'PH'}:
        cat_mode = 'SSB'
    elif modes == {'FM'}:
        # FM est une valeur CATEGORY-MODE à part entière dans la spec Cabrillo
        # v3 (CW/DIGI/FM/RTTY/SSB/MIXED) — un log 100% FM (ex. concours THF en
        # FM) retombait sur MIXED faute d'être testé, alors qu'aucun autre
        # mode n'était présent.
        cat_mode = 'FM'
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
    cabrillo_name = str(cdef.get('cabrillo_name', ''))

    lines = [
        'START-OF-LOG: 3.0',
        f"CONTEST: {cdef.get('cabrillo_name', cfg.get('contest', 'UNKNOWN'))}",
        f"CALLSIGN: {callsign}",
        'CATEGORY-OPERATOR: ' + ('MULTI-OP' if len(raw_ops) > 1 else 'SINGLE-OP'),
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
    ]
    # LOCATION : la spec WWROF (section LOCATION) le dit REQUIS pour l'IARU-HF
    # et « tous les concours ARRL et CQ », avec deux valeurs possibles : la
    # section ARRL (stations US/VE) ou « DX » (stations étrangères). LogX AI
    # ne modélise aucune section ARRL (logiciel français, pensé pour un
    # indicatif F) : DX est donc toujours la valeur correcte pour les
    # concours dont le nom Cabrillo officiel commence par CQ- ou ARRL-.
    # L'audit à l'origine de ce correctif ne visait que l'« ARRL DX » ; la
    # spec est en réalité plus large (aussi CQ WW/WPX) — portée élargie en
    # conséquence. Absent pour REF/WAEDC (concours REF français ou DARC, non
    # concernés par la LOCATION ARRL/CQ).
    if cabrillo_name.startswith(('CQ-', 'ARRL-')):
        lines.append('LOCATION: DX')
    lines.extend([
        f"NAME: {cfg.get('op_name', '')}",
        f"EMAIL: {cfg.get('email', '')}",
        f"CLUB: {cfg.get('club', '')}",
        "CREATED-BY: LogX AI",
        f"SOAPBOX: Exporte le {utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
    ])
    for q in qsos:
        band = _norm_band(q)
        # Jamais la valeur BRUTE de band en repli : une bande importée hors
        # table (voir CABRILLO_FREQ) tombe sur '?', exactement comme
        # CABRILLO_MODE tombe déjà sur 'PH' — band non assainie pourrait sinon
        # injecter un saut de ligne (donc une fausse ligne 'QSO:') dans le
        # Cabrillo exporté. Défense en profondeur : logx_import assainit déjà
        # band à l'import, mais une autre source (saisie manuelle, sync
        # multi-poste) pourrait ne pas passer par ce chemin.
        freq = CABRILLO_FREQ.get(band, '?')
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


# Tags ADIF déjà émis explicitement par build_adif() ci-dessous — sert à ne
# pas dupliquer/contredire un tag standard si un champ personnalisé porte
# malencontreusement le même nom (ex. l'opérateur entre "CALL" comme nom de
# champ). Jumeau de ADIF_STD_TAGS (logx_export_adif.js) : cette liste-ci est
# la référence, plus complète (elle couvre STATE/NAME/QTH/COMMENT/DISTANCE/
# PROP_MODE/SAT_NAME/MY_SIG*/SIG* que le JS n'exporte pas encore) — un
# correctif de l'une doit se refléter dans l'autre.
_ADIF_STD_TAGS = {
    'CALL', 'QSO_DATE', 'TIME_ON', 'BAND', 'FREQ', 'MODE', 'RST_SENT',
    'RST_RCVD', 'STX_STRING', 'SRX_STRING', 'GRIDSQUARE', 'STATE', 'NAME',
    'QTH', 'COMMENT', 'MY_GRIDSQUARE', 'CONTEST_ID', 'STATION_CALLSIGN',
    'OPERATOR', 'DISTANCE', 'PROP_MODE', 'SAT_NAME', 'MY_SIG', 'MY_SIG_INFO',
    'SIG', 'SIG_INFO', 'ADIF_VER', 'PROGRAMID',
    # Sous-chantier B (lot 2) : clés de la refonte de saisie (A).
    'TX_PWR', 'FREQ_RX', 'CQZ', 'ITUZ', 'CNTY', 'EMAIL', 'QSL_VIA', 'ANT_AZ',
    'TIME_OFF', 'QSL_SENT', 'LOTW_QSL_SENT', 'EQSL_QSL_SENT', 'APP_LOGX_OPERATING',
    'SUBMODE',
    # Sous-chantier B (lot 3) : tags dédiés multi-références (two-fer).
    'SOTA_REF', 'MY_SOTA_REF', 'POTA_REF', 'MY_POTA_REF',
    'WWFF_REF', 'MY_WWFF_REF', 'IOTA', 'MY_IOTA',
}


def _refs_pour_export(q, cle_liste, cle_sig, cle_info):
    """Références (programme, ref) à émettre en tags ADIF dédiés. Préfère la
    LISTE multi-références posée par la refonte de saisie A (two-fer SOTA+POTA,
    my_refs/refs) ; à défaut retombe sur la paire mono-valuée SIG/SIG_INFO
    (QSO anciens ou stockés côté serveur sans liste). Les couples au programme
    vide ou sans référence sont écartés à l'émission (voir appelant)."""
    liste = q.get(cle_liste)
    if isinstance(liste, list) and liste:
        return [(str(r.get('program', '')).upper().strip(), str(r.get('ref', '')).strip())
                for r in liste if isinstance(r, dict)]
    prog = str(q.get(cle_sig, '')).upper().strip()
    if prog:
        return [(prog, str(q.get(cle_info, '')).strip())]
    return []

_OP_SLOT_RE = re.compile(r'^OP(\d+)$', re.IGNORECASE | re.ASCII)


def resolve_operator_callsign(op_id, cfg, station_fallback=True):
    """Indicatif réel d'un opérateur depuis son ID de créneau ('OP1', 'OP2'…)
    — miroir de _resolveOperatorCallsign() côté JS (logx_logbook.js). Les
    enregistrements QSO stockent l'ID brut (nécessaire aux stats par
    opérateur/couleur côté client), jamais l'indicatif : à résoudre ici, à
    l'export, pas à la source. Signalement F4GLD (08/08/2026) : un ADIF qui
    exporte 'OP1' comme OPERATOR n'a de sens pour aucun logiciel tiers.

    station_fallback : repli sur l'indicatif de la STATION si aucun opérateur
    du créneau n'est configuré — adapté à un champ qui doit toujours porter
    UNE identité (ADIF OPERATOR, Cabrillo OPERATORS:). Mettre à False pour un
    usage de RÉPARTITION PAR OPÉRATEUR (écran mural) : y collapser plusieurs
    créneaux distincts vers la même valeur fusionnerait à tort leurs comptes —
    garder l'ID de créneau brut, encore distinguable, vaut mieux qu'un
    doublon silencieux."""
    raw = str(op_id or '').strip()
    m = _OP_SLOT_RE.match(raw)
    if not m:
        return raw
    operators = cfg.get('operators') or []
    if not isinstance(operators, list):
        operators = []
    idx = int(m.group(1)) - 1
    op = operators[idx] if 0 <= idx < len(operators) else {}
    if not isinstance(op, dict):
        op = {}
    resolved = str(op.get('call') or op.get('callsign') or '').strip()
    if resolved:
        return resolved
    return (cfg.get('callsign_contest') or cfg.get('callsign') or raw) if station_fallback else raw


def _adif_mode(q):
    """Champ(s) ADIF de mode. FT2 = sous-mode EXPÉRIMENTAL de MFSK : WSJT-X ne
    liste pas FT2 -> MODE=MFSK + SUBMODE=FT2, JAMAIS MODE=FT2 (terrain FT2
    Phase 1, jumeau de logx_export_adif.js). Aucune émission concernée."""
    if str(q.get('mode', '')).strip().upper() == 'FT2':
        return _adif_field('mode', 'MFSK') + _adif_field('submode', 'FT2')
    return _adif_field('mode', _norm_mode(q))


def build_adif(qsos, cfg=None):
    """Log partagé → ADIF 3 (texte). Le programme lisait déjà l'ADIF,
    il sait maintenant l'écrire."""
    cfg = cfg or {}
    callsign = (cfg.get('callsign_contest') or cfg.get('callsign', '')).upper()
    # ADIF_VER : '3.1.4' était codé en dur alors que le reste du logiciel
    # (logx_adif_enums, logx_import, doc) cible déjà la 3.1.7 — vérifié
    # comme version stable actuellement publiée sur adif.org (« Released
    # ADIF Version 3.1.7 », mise à jour 2026-03-22, aucune 3.1.8 publiée).
    header = (f"Log LogX AI — {callsign}\n"
              + _adif_field('adif_ver', '3.1.7')
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
            _adif_mode(q),
            _adif_field('rst_sent', q.get('rst_sent', '')),
            _adif_field('rst_rcvd', q.get('rst_rcvd', '')),
            _adif_field('stx_string', q.get('num_sent', '')),
            _adif_field('srx_string', q.get('num_rcvd', '')),
            _adif_field('gridsquare', q.get('locator', '')),
            # État US : porté par l'ADIF pour que le WAS reste calculable après
            # un export/réimport, ou dans le logiciel du correspondant.
            _adif_field('state', q.get('state', '')),
            # Nom, QTH et commentaire — le contenu d'un carnet de TRAFIC
            # COURANT, par opposition à un log de concours. Ils étaient jetés
            # à la saisie ; maintenant qu'ils sont capturés (nom/QTH depuis
            # l'annuaire, commentaire saisi), ils doivent AUSSI ressortir :
            # stockés mais absents de l'export, ils n'auraient tenu qu'à
            # moitié la promesse « même si vous abandonnez LogX AI, votre log
            # reste exploitable ».
            # Noms de champs ADIF 3.1.x standard (adif.org) : NAME, QTH,
            # COMMENT — donc relus tels quels par tout autre logiciel.
            _adif_field('name', q.get('name', '')),
            _adif_field('qth', q.get('qth', '')),
            _adif_field('comment', q.get('comment', '')),
            _adif_field('my_gridsquare', q.get('my_locator', cfg.get('locator', ''))),
            _adif_field('contest_id', q.get('contest', '')),
            # STATION_CALLSIGN (la station) et OPERATOR (la personne au clavier)
            # sont deux champs ADIF distincts — jamais confondre les deux,
            # jamais exporter l'ID de créneau brut ('OP1') comme OPERATOR.
            # Indicatif utilisé AU MOMENT du QSO (q.my_call, ex. suffixe /P) en
            # priorité — même repli que MY_GRIDSQUARE ci-dessus et que
            # buildAdifText() côté JS (logx_logbook.js) — sinon un changement
            # d'indicatif en cours de concours réétiquetterait rétroactivement
            # tous les anciens QSO au prochain export serveur (backup/archive).
            _adif_field('station_callsign', str(q.get('my_call') or callsign).upper()),
            _adif_field('operator', resolve_operator_callsign(q.get('operator', ''), cfg)),
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
            # Sous-chantier B (lot 2) : clés posées par la refonte de saisie (A).
            # Tags de l'énumération/spec ADIF (citables) ; operating_location n'a
            # pas de tag ADIF standard -> champ d'appli APP_LOGX_OPERATING (préfixe
            # APP_, jamais rejeté par un lecteur ADIF conforme).
            _adif_field('tx_pwr', q.get('tx_pwr', '')),
            _adif_field('freq_rx', q.get('freq_rx', '')),
            _adif_field('cqz', q.get('cqz', '')),
            _adif_field('ituz', q.get('ituz', '')),
            _adif_field('cnty', q.get('cnty', '')),
            _adif_field('email', q.get('email', '')),
            _adif_field('qsl_via', q.get('qsl_via', '')),
            _adif_field('ant_az', q.get('ant_az', '')),
            _adif_field('time_off', q.get('time_off', '')),
            _adif_field('qsl_sent', q.get('qsl_sent', '')),
            _adif_field('lotw_qsl_sent', q.get('lotw_qsl_sent', '')),
            _adif_field('eqsl_qsl_sent', q.get('eqsl_qsl_sent', '')),
            _adif_field('app_logx_operating', q.get('operating_location', '')),
        ]
        # Sous-chantier B (lot 3) : tags ADIF DÉDIÉS par programme, émis DEPUIS
        # la liste multi-références (my_refs/refs) pour ne pas perdre le 2e
        # programme d'un two-fer SOTA+POTA — MY_SIG/SIG ci-dessus ne portent
        # qu'UNE référence. MY_ + tag côté station, tag nu côté correspondant.
        # Un programme sans tag dédié (ARLHS/WCA) reste sur le générique SIG.
        for prog, ref in _refs_pour_export(q, 'my_refs', 'my_sig', 'my_sig_info'):
            tag = ADIF_PROGRAM_TAGS.get(prog)
            if tag and ref:
                fields.append(_adif_field('my_' + tag.lower(), ref))
        for prog, ref in _refs_pour_export(q, 'refs', 'sig', 'sig_info'):
            tag = ADIF_PROGRAM_TAGS.get(prog)
            if tag and ref:
                fields.append(_adif_field(tag.lower(), ref))
        # Champs ADIF personnalisés saisis par l'opérateur (editQSO,
        # q['extra_fields'] côté client) — jusqu'ici exportés par le générateur
        # JS (logx_export_adif.js) mais PAS par cet export serveur, alors que
        # les deux prétendent à la même promesse : « même si vous abandonnez
        # LogX AI, votre log reste exploitable » (voir commentaire plus haut).
        extra_fields = q.get('extra_fields')
        if isinstance(extra_fields, dict):
            # minuscules : même convention que tous les autres appels
            # _adif_field() de cette fonction (ADIF est insensible à la casse
            # des tags, mais un fichier cohérent est plus facile à relire).
            fields += [_adif_field(str(name).lower(), value) for name, value in extra_fields.items()
                       if str(name).upper() not in _ADIF_STD_TAGS]
        records.append(''.join(f for f in fields if f) + '<EOR>')
    return header + '\n'.join(records) + '\n'
