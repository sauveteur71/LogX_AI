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

import logx_storage as storage
from logx_qsl import _parse_adif_records, _band_from_record

# Indicatif valide : lettres/chiffres/'/' uniquement. Rejette au passage tout
# record dont le champ CALL contiendrait du HTML (ex. <img src=x onerror=...>)
# — défense en profondeur au point d'ingestion, en plus de l'échappement à
# l'affichage. Couvre les préfixes/suffixes /P, /MM, F/DL1AA, etc.
_CALL_RE = re.compile(r'^[A-Z0-9/]{2,15}$')

# Tags ADIF explicitement mappés vers un champ interne ci-dessous — tout le
# reste d'un record (ex. MY_RIG, COMMENT, un tag propriétaire d'un autre
# logiciel) est préservé tel quel dans extra_fields plutôt que perdu en
# silence, pour un aller-retour import/export fidèle (voir editQSO/
# buildAdifText côté client, qui lisent/écrivent le même extra_fields).
_TAGS_MAPPES = {
    'CALL', 'BAND', 'MODE', 'QSO_DATE', 'TIME_ON', 'TIME_OFF', 'RST_SENT',
    'RST_RCVD', 'STX_STRING', 'STX', 'SRX_STRING', 'SRX', 'GRIDSQUARE',
    'STATE', 'SAT_NAME', 'MY_GRIDSQUARE', 'OPERATOR', 'STATION_CALLSIGN',
    'CONTEST_ID', 'MY_SIG', 'MY_SIG_INFO', 'SIG', 'SIG_INFO',
    'ADIF_VER', 'PROGRAMID',
    # FREQ n'est PAS mappé par ce parseur (pré-existant, hors scope de ce
    # correctif) : exclu volontairement de cet ensemble pour qu'un FREQ
    # importé atterrisse dans extra_fields plutôt que d'être perdu.
}


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
            # État US : indispensable au WAS, et IMPOSSIBLE à déduire autrement
            # (un W6 peut habiter n'importe quel état depuis la fin du découpage
            # géographique des préfixes). Un ADIF LoTW/ClubLog le porte.
            'state': _clean_text((rec.get('STATE') or '').upper()),
            # SATELLITE : relu à l'import pour qu'un aller-retour ADIF ne
            # DÉGRADE pas un QSO satellite en contact terrestre. Un carnet
            # réimporté depuis LoTW ou depuis un autre logiciel porte SAT_NAME ;
            # le perdre ici reviendrait à effacer silencieusement le seul champ
            # qui rend le QSO créditable en satellite.
            'sat_name': _clean_text((rec.get('SAT_NAME') or '').upper()),
            'my_locator': _clean_text((rec.get('MY_GRIDSQUARE') or '').upper()),
            'operator': _clean_text((rec.get('OPERATOR') or rec.get('STATION_CALLSIGN') or '').upper()),
            'contest': _clean_text(rec.get('CONTEST_ID')),
            'my_sig': _clean_text(rec.get('MY_SIG')), 'my_sig_info': _clean_text(rec.get('MY_SIG_INFO')),
            'sig': _clean_text(rec.get('SIG')), 'sig_info': _clean_text(rec.get('SIG_INFO')),
            'points': 0,     # un import historique n'est pas noté dans un concours actif
            'source': 'adif_import',
        })
        # Tout tag du record qui n'est PAS explicitement mappé ci-dessus est
        # préservé dans extra_fields plutôt que perdu en silence — même
        # convention que l'éditeur de champs personnalisés côté client
        # (logx_logbook.js:editQSO/buildAdifText).
        extras = {k: _clean_text(v) for k, v in rec.items()
                  if k not in _TAGS_MAPPES and _clean_text(v)}
        if extras:
            qsos[-1]['extra_fields'] = extras
    return qsos, errors


def etats_depuis_adif(adif_text):
    """{INDICATIF: 'XX'} — les états US portés par un ADIF (LoTW, ClubLog…).

    Indexé par INDICATIF et non par QSO, à dessein : l'état est une propriété
    de la STATION, pas du contact. Un seul record W1ABC/STATE=MA suffit donc à
    renseigner TOUS les QSO déjà faits avec W1ABC, y compris sur d'autres
    bandes et à d'autres dates — là où une correspondance QSO par QSO exigerait
    que le rapport couvre exactement les mêmes contacts.

    LIMITE ASSUMÉE : si un opérateur a déménagé d'un état à l'autre entre deux
    QSO, tous ses contacts reçoivent le dernier état connu. Pour le WAS c'est
    sans conséquence dans l'immense majorité des cas, et de toute façon seule
    une confirmation LoTW fait foi devant l'ARRL.
    """
    etats = {}
    try:
        records = _parse_adif_records(adif_text)
    except Exception:
        return etats
    for rec in records:
        call = (rec.get('CALL') or '').upper().strip()
        st = (rec.get('STATE') or '').upper().strip()
        if call and len(st) == 2 and st.isalpha():
            etats[call] = st
    return etats


def appliquer_etats(log, etats):
    """Pose l'état sur les QSO qui n'en ont pas. Retourne (qso_remplis, calls).

    N'ÉCRASE JAMAIS un état déjà présent : une valeur saisie ou confirmée vaut
    mieux qu'une valeur d'annuaire, et un import ne doit pas pouvoir dégrader
    une donnée existante. Ne crée aucun QSO non plus — c'est le rôle de
    commit_import ; ici on ne fait qu'enrichir l'existant.
    """
    remplis, calls = 0, set()
    for q in log:
        if q.get('state'):
            continue
        st = etats.get(str(q.get('call', '')).upper().strip())
        if st:
            q['state'] = st
            remplis += 1
            calls.add(q['call'])
    return remplis, calls


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
    # Numérotation AU-DESSUS du plus grand id déjà présent dans le log, jamais
    # à partir de la seule horloge : `int(now*1000) + i` consommait une
    # milliseconde d'espace d'id PAR QSO IMPORTÉ, donc N/1000 SECONDES d'id
    # FUTURS — 17 000 QSO importés volaient leur id à tout QSO saisi dans les
    # 17 s suivantes, et deux imports rapprochés se recouvraient massivement.
    # Or l'id est la clé d'identité de /log/delete (qui efface TOUS ses
    # porteurs), de /log/update (qui corrige le PREMIER porteur) et de la
    # fusion multi-poste logx_cloudsync. Voir logx_storage.next_free_qso_id.
    # Numérotation DENSE (len(new_qsos) et non l'indice de boucle) : les
    # doublons ignorés ne doivent pas laisser de trous d'id derrière eux.
    base_id = storage.next_free_qso_id((q.get('id') for q in existing_log),
                                       int(now * 1000))
    for q in qsos:
        if _dedup_key(q) in existing_keys:
            continue
        q['id'] = base_id + len(new_qsos)
        q['server_time'] = now
        new_qsos.append(q)
        existing_keys.add(_dedup_key(q))   # le fichier importé peut contenir ses propres doublons
    return new_qsos, errors
