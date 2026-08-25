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
from logx_utils import CALL_RE as _CALL_RE, clean_text as _clean_text
# Sous-chantier B (lot 5) : tags ADIF dédiés par programme (SOTA_REF…), pour
# reconstruire my_refs/refs à l'import — même source que l'export (lot 3).
from logx_activation import ADIF_PROGRAM_TAGS

# Synonymes de mode qu'un export ADIF d'un AUTRE logiciel peut porter sans
# que ce soit un mode ADIF 3.1.7 officiel — "PH" (phonie) est la convention
# Cabrillo, reprise telle quelle par certains exports Win-Test ; le reste de
# LogX AI (filtres bande/mode, scoring, logx_export.CABRILLO_MODE qui fait
# le trajet INVERSE SSB/USB/LSB/FM->PH pour l'export) suppose un mode ADIF
# canonique en interne — laisser "PH" tel quel romprait ce filtrage sans
# qu'aucune erreur ne le signale. Volontairement minimal : seule une
# correspondance non ambiguë et documentée, pas une déduction hasardeuse.
_MODE_SYNONYMES = {'PH': 'SSB'}


def _lire_mode(rec):
    """Mode interne depuis un record ADIF. FT2 = sous-mode EXPÉRIMENTAL de MFSK :
    MODE=MFSK + SUBMODE=FT2 -> 'FT2' (miroir exact de l'export). Terrain FT2
    Phase 1 (F4GLD) — aucune émission, seul l'aller-retour ADIF est concerné."""
    mode = _clean_text((rec.get('MODE') or 'SSB').upper()) or 'SSB'
    submode = _clean_text((rec.get('SUBMODE') or '').upper())
    if mode == 'MFSK' and submode == 'FT2':
        return 'FT2'
    return _MODE_SYNONYMES.get(mode, mode)

# Tags ADIF explicitement mappés vers un champ interne ci-dessous — tout le
# reste d'un record (ex. MY_RIG, COMMENT, un tag propriétaire d'un autre
# logiciel) est préservé tel quel dans extra_fields plutôt que perdu en
# silence, pour un aller-retour import/export fidèle (voir editQSO/
# buildAdifText côté client, qui lisent/écrivent le même extra_fields).
# Sous-chantier B (lot 5) : tag ADIF -> clé interne du log. Symétrique de
# l'export (build_adif lit ces mêmes clés internes). Sans ce mapping, ces tags
# atterrissaient dans extra_fields ; or l'export les liste dans _ADIF_STD_TAGS
# (anti-duplication) et les saute donc à la réexportation tout en lisant une
# clé interne restée vide -> perte au 2e export. FREQ/TIME_OFF étaient de plus
# explicitement non mappés (commentaire historique retiré) : désormais relus.
_ADIF_VERS_INTERNE = {
    'NAME': 'name', 'QTH': 'qth', 'COMMENT': 'comment', 'DISTANCE': 'dist',
    'PROP_MODE': 'prop_mode', 'FREQ': 'freq', 'TIME_OFF': 'time_off',
    'TX_PWR': 'tx_pwr', 'FREQ_RX': 'freq_rx', 'CQZ': 'cqz', 'ITUZ': 'ituz',
    'CNTY': 'cnty', 'EMAIL': 'email', 'QSL_VIA': 'qsl_via', 'ANT_AZ': 'ant_az',
    'QSL_SENT': 'qsl_sent', 'LOTW_QSL_SENT': 'lotw_qsl_sent',
    'EQSL_QSL_SENT': 'eqsl_qsl_sent', 'APP_LOGX_OPERATING': 'operating_location',
    # IA-2 (lot 5) : pays/continent/zones -> clés internes, symétrique de
    # l'émission (build_adif). Sans ça, un COUNTRY importé dormirait dans
    # extra_fields et serait sauté au re-export (leçon de la revue B).
    'COUNTRY': 'dxcc_country', 'CONT': 'continent',
    'MY_COUNTRY': 'my_dxcc_country', 'MY_CQ_ZONE': 'my_cqz',
    'MY_ITU_ZONE': 'my_ituz',
}

_TAGS_MAPPES = {
    'CALL', 'BAND', 'MODE', 'QSO_DATE', 'TIME_ON', 'RST_SENT',
    'RST_RCVD', 'STX_STRING', 'STX', 'SRX_STRING', 'SRX', 'GRIDSQUARE',
    'STATE', 'SAT_NAME', 'MY_GRIDSQUARE', 'OPERATOR', 'STATION_CALLSIGN',
    'CONTEST_ID', 'MY_SIG', 'MY_SIG_INFO', 'SIG', 'SIG_INFO',
    'ADIF_VER', 'PROGRAMID',
    # Lot 5 : les scalaires désormais mappés vers une clé interne (ci-dessus)…
    *_ADIF_VERS_INTERNE,
    # …et les tags multi-références dédiés, consommés vers my_refs/refs (le
    # générique MY_SIG/SIG l'est déjà). MY_ + tag côté station, tag nu côté
    # correspondant.
    *(t for tag in ADIF_PROGRAM_TAGS.values() for t in (tag, 'MY_' + tag)),
}


def _refs_depuis_record(rec, prefixe):
    """Reconstruit une liste [{program, ref}] depuis les tags dédiés du record
    (SOTA_REF/MY_SOTA_REF…) PLUS le générique SIG/SIG_INFO quand son programme
    n'a pas de tag dédié. `prefixe` = '' (correspondant) ou 'MY_' (ma station).
    Symétrique de logx_export._refs_pour_export (lot 3)."""
    out, vus = [], set()
    for prog, tag in ADIF_PROGRAM_TAGS.items():
        val = _clean_text(rec.get(prefixe + tag))
        if val:
            out.append({'program': prog, 'ref': val})
            vus.add(prog)
    sig = _clean_text(rec.get(prefixe + 'SIG')).upper()
    if sig and sig not in vus:
        out.append({'program': sig, 'ref': _clean_text(rec.get(prefixe + 'SIG_INFO'))})
    return out


def _clean_date(v):
    """QSO_DATE -> 8 chiffres (AAAAMMJJ) ou '' si absent/malformé : évite les
    dates tronquées qui corrompaient ensuite l'export Cabrillo/ADIF."""
    d = re.sub(r'\D', '', str(v or ''))
    return d if len(d) == 8 else ''


def _adif_time(rec):
    """'HHMM' depuis TIME_ON (HHMMSS ou HHMM)."""
    t = (rec.get('TIME_ON') or '').strip()
    return t.zfill(4)[:4] if t else '0000'


def _dedup_key(qso):
    """Clé de doublon : indicatif + bande + mode + date + heure. Volontairement
    plus stricte que celle d'add_qso_to_log (call+band+mode+contest) — un
    import historique doit pouvoir coexister avec un QSO de concours en
    cours sur le même indicatif/bande, seule une correspondance EXACTE
    (même instant) est un vrai doublon d'import.

    Renvoie None quand la DATE est vide (absente/malformée) : sans date, le QSO
    n'a pas d'identité fiable — deux contacts réels distincts produiraient sinon
    la même clé ('', '0000') et le second serait PERDU en silence à l'import.
    Une clé None n'est jamais considérée comme un doublon (mieux vaut un doublon
    à trier qu'un QSO perdu)."""
    date = str(qso.get('date', ''))
    if not date:
        return None
    return (str(qso.get('call', '')).upper().strip(),
            str(qso.get('band', '')),
            str(qso.get('mode', '')).upper().strip(),
            date,
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
        # Assaini comme tout autre champ texte importé (voir rst_sent/locator/
        # mode ci-dessous) : _band_from_record() peut renvoyer la valeur BRUTE
        # du tag ADIF <BAND> telle quelle quand elle ne correspond à aucune
        # bande connue (repli documenté dans _band_from_record) — sans
        # clean_text, un octet de contrôle (retour à la ligne...) injecté dans
        # ce tag survivrait jusqu'à l'export Cabrillo/ADIF.
        band = _clean_text(_band_from_record(rec))
        if not call or not band:
            errors.append(f"Record {i + 1} ignoré (indicatif ou bande manquant/non reconnu)")
            continue
        if not _CALL_RE.match(call):
            errors.append(f"Record {i + 1} ignoré (indicatif invalide : « {call[:20]} »)")
            continue
        qsos.append({
            'call': call,
            'band': band,
            'mode': _lire_mode(rec),
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
        # Lot 5 : scalaires ADIF -> clés internes (aller-retour fidèle). Une
        # valeur vide n'écrase rien (pas de clé interne vide parasite).
        q_new = qsos[-1]
        for tag, cle in _ADIF_VERS_INTERNE.items():
            val = _clean_text(rec.get(tag))
            if val:
                q_new[cle] = val
        # Lot 5 : reconstruction des références multiples (two-fer SOTA+POTA)
        # depuis les tags dédiés + le générique SIG. Listes posées seulement si
        # non vides — un QSO ordinaire ne porte pas de my_refs/refs vides.
        my_refs = _refs_depuis_record(rec, 'MY_')
        if my_refs:
            q_new['my_refs'] = my_refs
        their_refs = _refs_depuis_record(rec, '')
        if their_refs:
            q_new['refs'] = their_refs
        # Tout tag du record qui n'est PAS explicitement mappé ci-dessus est
        # préservé dans extra_fields plutôt que perdu en silence — même
        # convention que l'éditeur de champs personnalisés côté client
        # (logx_logbook.js:editQSO/buildAdifText).
        # SUBMODE=FT2 est déjà consommé en mode='FT2' : ne pas le laisser dans
        # extra_fields (sinon il serait ré-écrit en double à l'export). Les
        # AUTRES sous-modes (JS8, etc.) restent préservés dans extra_fields.
        _est_ft2 = qsos[-1].get('mode') == 'FT2'
        extras = {k: _clean_text(v) for k, v in rec.items()
                  if k not in _TAGS_MAPPES and _clean_text(v)
                  and not (_est_ft2 and k == 'SUBMODE')}
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


def preview_import(adif_text, existing_log, activite=''):
    """Analyse SANS RIEN ÉCRIRE : compte nouveaux/doublons, donne un
    échantillon. `existing_log` : snapshot de shared_log (liste de dicts).
    `mode_warnings` : modes non standards détectés — INFORMATIF seulement,
    n'affecte pas `new`/`duplicates` (ces QSO sont importables normalement).

    `activite` : si fourni, `to_tag` indique combien de QSO NEUFS recevront ce
    tag d'activité au commit (ceux sans CONTEST_ID propre), pour l'afficher
    avant confirmation. Voir commit_import()."""
    activite = str(activite or '').strip()
    qsos, errors = parse_adif_to_qsos(adif_text)
    existing_keys = {k for q in existing_log if (k := _dedup_key(q)) is not None}
    new_qsos = [q for q in qsos
                if (k := _dedup_key(q)) is None or k not in existing_keys]
    duplicates = len(qsos) - len(new_qsos)
    to_tag = (sum(1 for q in new_qsos if not str(q.get('contest', '') or '').strip())
              if activite else 0)
    return {
        'ok': True,
        'total_in_file': len(qsos),
        'new': len(new_qsos),
        'duplicates': duplicates,
        'errors': errors,
        'mode_warnings': _mode_warnings(qsos),
        'sample': new_qsos[:5],
        'to_tag': to_tag,
    }


def commit_import(adif_text, existing_log, activite=''):
    """Ré-analyse et retourne la liste des QSO NEUFS à ajouter au log
    (l'appelant fait l'ajout + la sauvegarde sous log_lock — ce module ne
    connaît pas shared_log, pour rester testable sans le serveur).

    `activite` (F4GLD 23/08) : identifiant d'activité saisi par l'opérateur au
    moment de l'import (ex. 'TM6KJS'). Un log externe d'événement spécial porte
    souvent l'indicatif en STATION_CALLSIGN SANS CONTEST_ID -> il arriverait non
    tagué et l'export par activité ne le retrouverait pas. Si `activite` est
    fourni, on l'attribue (champ 'contest') aux QSO neufs qui n'ont PAS déjà leur
    propre tag concours : un CONTEST_ID présent dans l'ADIF n'est JAMAIS écrasé.
    N'affecte pas la dédup (_dedup_key ignore 'contest')."""
    activite = str(activite or '').strip()
    qsos, errors = parse_adif_to_qsos(adif_text)
    existing_keys = {k for q in existing_log if (k := _dedup_key(q)) is not None}
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
        k = _dedup_key(q)
        if k is not None and k in existing_keys:
            continue
        q['id'] = base_id + len(new_qsos)
        q['server_time'] = now
        if activite and not str(q.get('contest', '') or '').strip():
            q['contest'] = activite
        new_qsos.append(q)
        if k is not None:
            existing_keys.add(k)   # le fichier importé peut contenir ses propres doublons
    return new_qsos, errors
