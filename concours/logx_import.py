# -*- coding: utf-8 -*-
"""Import ADIF dans le log partagé — vers un vrai logger généraliste.

Corrige un import ADIF PRÉ-EXISTANT côté client (logx_logbook.js
:importADIF) qui ne persistait jamais réellement : il poussait les QSO dans
la variable JS locale `qsoLog` sans jamais informer le serveur, et le
polling `fetchLog()` (toutes les 5 s) écrasait ce tableau avec le
`shared_log` du serveur — inchangé — faisant disparaître les QSO importés
en quelques secondes.

Réutilise le parseur ADIF déjà écrit pour les confirmations QSL
(logx_qsl._parse_adif_records — gère correctement le format
`<NOM:longueur>valeur`, y compris les balises de contrôle EOR/EOH sans
longueur) plutôt que d'en réécrire un.

Fonctions PURES (testables sans I/O) : parse_adif_to_qsos() et
preview_import(). Seul commit_import() touche le log partagé, et encore,
en une SEULE écriture disque (pas un save_log_to_disk() par QSO importé).
"""
import re
import time

from logx_qsl import _parse_adif_records, _band_from_record

# Indicatif valide : lettres/chiffres/'/' uniquement. Rejette au passage tout
# record dont le champ CALL contiendrait du HTML (ex. <img src=x onerror=...>)
# — défense en profondeur au point d'ingestion, en plus de l'échappement à
# l'affichage. Couvre les préfixes/suffixes /P, /MM, F/DL1AA, etc.
_CALL_RE = re.compile(r'^[A-Z0-9/]{2,15}$')


def _clean_text(v):
    """Nettoie un champ texte libre d'un ADIF externe : retire les caractères
    de contrôle et les chevrons (< >) pour qu'aucun fragment HTML ne soit
    stocké dans le log partagé, puis rogné à une longueur raisonnable."""
    s = str(v or '')
    s = ''.join(c for c in s if ord(c) >= 0x20 or c in '\t')
    return s.replace('<', '').replace('>', '').strip()[:64]


def _clean_date(v):
    """QSO_DATE -> 8 chiffres (AAAAMMJJ) ou '' si absent/malformé : évite les
    dates tronquées qui corrompaient ensuite l'export Cabrillo/ADIF."""
    d = re.sub(r'\D', '', str(v or ''))
    return d if len(d) == 8 else ''


def _adif_time(rec):
    """'HHMM' depuis TIME_ON (HHMMSS ou HHMM)."""
    t = (rec.get('TIME_ON') or '').strip()
    return (t + '0000')[:4] if t else '0000'


def _dedup_key(qso):
    """Clé de doublon : indicatif + bande + mode + date + heure. Volontairement
    plus stricte que celle d'add_qso_to_log (call+band+mode+contest) — un
    import historique doit pouvoir coexister avec un QSO de concours en
    cours sur le même indicatif/bande, seule une correspondance EXACTE
    (même instant) est un vrai doublon d'import."""
    return (str(qso.get('call', '')).upper().strip(),
            str(qso.get('band', '')),
            str(qso.get('mode', '')).upper().strip(),
            str(qso.get('date', '')),
            str(qso.get('time', '')))


def parse_adif_to_qsos(adif_text):
    """ADIF (texte) -> (qsos, erreurs). `qsos` au format interne du log
    partagé (mêmes clés que shared_log : call/band/mode/date/time/...).
    Un record sans indicatif ou sans bande reconnaissable est compté en
    erreur plutôt que silencieusement ignoré."""
    qsos, errors = [], []
    try:
        records = _parse_adif_records(adif_text)
    except Exception as e:
        return [], [f"ADIF illisible : {e}"]
    for i, rec in enumerate(records):
        call = (rec.get('CALL') or '').upper().strip()
        band = _band_from_record(rec)
        if not call or not band:
            errors.append(f"Record {i + 1} ignoré (indicatif ou bande manquant/non reconnu)")
            continue
        if not _CALL_RE.match(call):
            errors.append(f"Record {i + 1} ignoré (indicatif invalide : « {call[:20]} »)")
            continue
        qsos.append({
            'call': call,
            'band': band,
            'mode': _clean_text((rec.get('MODE') or 'SSB').upper()) or 'SSB',
            'date': _clean_date(rec.get('QSO_DATE')),
            'time': _adif_time(rec),
            'rst_sent': _clean_text(rec.get('RST_SENT')),
            'rst_rcvd': _clean_text(rec.get('RST_RCVD')),
            'num_sent': _clean_text(rec.get('STX_STRING') or rec.get('STX')),
            'num_rcvd': _clean_text(rec.get('SRX_STRING') or rec.get('SRX')),
            'locator': _clean_text((rec.get('GRIDSQUARE') or '').upper()),
            'my_locator': _clean_text((rec.get('MY_GRIDSQUARE') or '').upper()),
            'operator': _clean_text((rec.get('OPERATOR') or rec.get('STATION_CALLSIGN') or '').upper()),
            'contest': _clean_text(rec.get('CONTEST_ID')),
            'my_sig': _clean_text(rec.get('MY_SIG')), 'my_sig_info': _clean_text(rec.get('MY_SIG_INFO')),
            'sig': _clean_text(rec.get('SIG')), 'sig_info': _clean_text(rec.get('SIG_INFO')),
            'points': 0,     # un import historique n'est pas noté dans un concours actif
            'source': 'adif_import',
        })
    return qsos, errors


def _mode_warnings(qsos):
    """Modes qui ne correspondent à aucun Mode/Submode ADIF 3.1.7 officiel
    (logx_adif_enums) — jamais bloquant (contrairement à l'indicatif/bande) :
    l'ADIF évolue, un mode récent ou une coquille ne doit pas empêcher
    l'import, juste être signalé pour vérification."""
    from logx_adif_enums import is_known_mode
    seen = set()
    warnings = []
    for q in qsos:
        mode = q.get('mode', '')
        if mode and mode not in seen and not is_known_mode(mode):
            seen.add(mode)
            warnings.append(f"Mode « {mode} » non reconnu dans l'énumération ADIF 3.1.7 "
                            "officielle (importé quand même — vérifier la casse/l'orthographe)")
    return warnings


def preview_import(adif_text, existing_log):
    """Analyse SANS RIEN ÉCRIRE : compte nouveaux/doublons, donne un
    échantillon. `existing_log` : snapshot de shared_log (liste de dicts).
    `mode_warnings` : modes non standards détectés — INFORMATIF seulement,
    n'affecte pas `new`/`duplicates` (ces QSO sont importables normalement)."""
    qsos, errors = parse_adif_to_qsos(adif_text)
    existing_keys = {_dedup_key(q) for q in existing_log}
    new_qsos = [q for q in qsos if _dedup_key(q) not in existing_keys]
    duplicates = len(qsos) - len(new_qsos)
    return {
        'ok': True,
        'total_in_file': len(qsos),
        'new': len(new_qsos),
        'duplicates': duplicates,
        'errors': errors,
        'mode_warnings': _mode_warnings(qsos),
        'sample': new_qsos[:5],
    }


def commit_import(adif_text, existing_log):
    """Ré-analyse et retourne la liste des QSO NEUFS à ajouter au log
    (l'appelant fait l'ajout + la sauvegarde sous log_lock — ce module ne
    connaît pas shared_log, pour rester testable sans le serveur)."""
    qsos, errors = parse_adif_to_qsos(adif_text)
    existing_keys = {_dedup_key(q) for q in existing_log}
    new_qsos = []
    now = time.time()
    for i, q in enumerate(qsos):
        if _dedup_key(q) in existing_keys:
            continue
        q['id'] = int(now * 1000) + i
        q['server_time'] = now
        new_qsos.append(q)
        existing_keys.add(_dedup_key(q))   # le fichier importé peut contenir ses propres doublons
    return new_qsos, errors
