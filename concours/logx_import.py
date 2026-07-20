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
import time

from logx_qsl import _parse_adif_records, _band_from_record


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
        qsos.append({
            'call': call,
            'band': band,
            'mode': (rec.get('MODE') or 'SSB').upper().strip(),
            'date': (rec.get('QSO_DATE') or '').strip(),
            'time': _adif_time(rec),
            'rst_sent': rec.get('RST_SENT') or '',
            'rst_rcvd': rec.get('RST_RCVD') or '',
            'num_sent': rec.get('STX_STRING') or rec.get('STX') or '',
            'num_rcvd': rec.get('SRX_STRING') or rec.get('SRX') or '',
            'locator': (rec.get('GRIDSQUARE') or '').upper().strip(),
            'my_locator': (rec.get('MY_GRIDSQUARE') or '').upper().strip(),
            'operator': (rec.get('OPERATOR') or rec.get('STATION_CALLSIGN') or '').upper().strip(),
            'contest': (rec.get('CONTEST_ID') or ''),
            'my_sig': rec.get('MY_SIG') or '', 'my_sig_info': rec.get('MY_SIG_INFO') or '',
            'sig': rec.get('SIG') or '', 'sig_info': rec.get('SIG_INFO') or '',
            'points': 0,     # un import historique n'est pas noté dans un concours actif
            'source': 'adif_import',
        })
    return qsos, errors


def preview_import(adif_text, existing_log):
    """Analyse SANS RIEN ÉCRIRE : compte nouveaux/doublons, donne un
    échantillon. `existing_log` : snapshot de shared_log (liste de dicts)."""
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
