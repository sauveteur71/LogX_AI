# -*- coding: utf-8 -*-
"""Activations POTA / SOTA / IOTA / WWFF — le portable « parcs & sommets ».

Quand l'opérateur ACTIVE une référence (parc POTA, sommet SOTA, île IOTA,
réserve WWFF), chaque QSO porte SA référence (my_sig_info) et éventuellement
celle du correspondant (sig_info) → détection Park-to-Park / Summit-to-Summit.
Une activation est VALIDE au-delà d'un minimum de QSO (POTA 10, SOTA 4, IOTA 1,
WWFF 44). Ce module valide les références et calcule l'avancement en direct.

Déterministe, hors-ligne. Alimente GET /activation/state et l'export ADIF
(champs SIG / SIG_INFO / MY_SIG / MY_SIG_INFO, lus par POTA/SOTA/WWFF).
"""
import re

# min_qso : QSO nécessaires pour valider l'activation (règles officielles).
# ref_re  : format de référence (validation de saisie).
#
# ARLHS et WCA vérifiés directement sur les règles/bases officielles (pas de
# supposition) : ARLHS Activator Award Rules (arlhs.com) — « Two stations
# must be worked from each light activated » (min_qso=2), format du World
# List of Lights (wlol.arlhs.com) = préfixe pays 2-3 lettres + tiret + numéro
# 3-4 chiffres, parfois suivi d'une lettre pour les phares déplacés/historiques
# (ex. USA-129H). WCA Rules (wcagroup.org) — « not less than 50 QSO » pour
# qu'une activation compte dans les diplômes WCA-50/WCA-100 (min_qso=50),
# format = préfixe indicatif pays + tiret + numéro sur 5 chiffres (ex. DL-00001).
# adif_tag : tag ADIF DÉDIÉ du programme, côté correspondant (le côté « ma
# station » est toujours 'MY_' + adif_tag). Présent UNIQUEMENT pour les
# programmes que la spec ADIF 3.1.5 dote d'un champ propre (adif.org/315,
# section Fields) : SOTA_REF/MY_SOTA_REF, POTA_REF/MY_POTA_REF,
# WWFF_REF/MY_WWFF_REF, IOTA/MY_IOTA (IOTA n'a PAS de suffixe _REF dans la
# norme). ARLHS et WCA n'ont AUCUN champ ADIF dédié -> pas de clé adif_tag :
# ils passent par le mécanisme générique SIG/SIG_INFO (une seule référence,
# my_refs[0]) — ne jamais inventer un MY_WCA_REF/MY_ARLHS_REF qui n'existe pas.
PROGRAM_SPECS = {
    'POTA': {'name': 'Parks on the Air',        'sig': 'POTA',
             'ref_re': r'^[A-Z0-9]{1,4}-\d{3,5}$', 'min_qso': 10,
             'p2p': 'Park-to-Park', 'example': 'FR-0123', 'adif_tag': 'POTA_REF'},
    'SOTA': {'name': 'Summits on the Air',      'sig': 'SOTA',
             'ref_re': r'^[A-Z0-9]{1,3}/[A-Z]{2}-\d{3}$', 'min_qso': 4,
             'p2p': 'Summit-to-Summit', 'example': 'F/AB-001', 'adif_tag': 'SOTA_REF'},
    'IOTA': {'name': 'Islands on the Air',      'sig': 'IOTA',
             'ref_re': r'^(AF|AN|AS|EU|NA|OC|SA)-\d{3}$', 'min_qso': 1,
             'p2p': 'Island-to-Island', 'example': 'EU-064', 'adif_tag': 'IOTA'},
    'WWFF': {'name': 'World Wide Flora & Fauna', 'sig': 'WWFF',
             'ref_re': r'^[A-Z0-9]{1,3}FF-\d{4}$', 'min_qso': 44,
             'p2p': 'Flora-to-Flora', 'example': 'FFF-0123', 'adif_tag': 'WWFF_REF'},
    'ARLHS': {'name': 'Amateur Radio Lighthouse Society', 'sig': 'ARLHS',
              'ref_re': r'^[A-Z]{2,3}-\d{3,4}[A-Z]?$', 'min_qso': 2,
              'p2p': 'Light-to-Light', 'example': 'FRA-113'},
    'WCA': {'name': 'World Castles Award',      'sig': 'WCA',
            'ref_re': r'^[A-Z0-9]{1,4}-\d{4,5}$', 'min_qso': 50,
            'p2p': 'Castle-to-Castle', 'example': 'DL-00001'},
    # WWBOTA (World Wide Bunkers on the Air) — vérifié sur wwbota.net : réf
    # « B/<code pays>-nnnn » (le code pays fait 1 à 3 caractères : G, US, E7…),
    # activation HF valide à 25 QSO (10 en VHF, non modélisé ici — seuil HF
    # retenu, comme POTA=10). Pas de champ ADIF dédié aux bunkers -> mécanisme
    # générique SIG/SIG_INFO, comme ARLHS et WCA.
    'WWBOTA': {'name': 'World Wide Bunkers on the Air', 'sig': 'WWBOTA',
               'ref_re': r'^B/[A-Z0-9]{1,3}-\d{4}$', 'min_qso': 25,
               'p2p': 'Bunker-to-Bunker', 'example': 'B/G-0001'},
    # ILLW (International Lighthouse & Lightship Weekend) — ÉVÉNEMENT week-end,
    # PAS un diplôme à seuil : aucune activation minimale officielle -> min_qso=1
    # (toujours « valide »). Numérotation officielle illw.net « XX-nnnn » (code
    # pays 2 lettres + 4 chiffres, ex. IT-0005). Distinct d'ARLHS (société de
    # phares, min 2 QSO). Pas de champ ADIF phares dédié -> générique SIG.
    'ILLW': {'name': 'International Lighthouse Lightship Weekend', 'sig': 'ILLW',
             'ref_re': r'^[A-Z]{2}-\d{4}$', 'min_qso': 1,
             'p2p': 'Light-to-Light', 'example': 'IT-0005'},
    # GMA (Global Mountain Activity) — programme de sommets HIÉRARCHIQUE
    # (association > région > sommet). Vérifié sur cqgma.org / gma.rocks :
    # activation de sommet valide à 4 QSO avec des stations DIFFÉRENTES (comme
    # SOTA). « SOTA references are generally also valid for GMA » -> même schéma
    # de référence que SOTA (association 1-3 car / région 2 lettres - n° 3 chiffres,
    # ex. DL/BE-055). Les sommets GMA-only suivent le même schéma ; d'éventuelles
    # variantes de format GMA-only ne sont pas entièrement sourcées -> élargir le
    # regex si un cas réel légitime échoue. Pas de tag ADIF dédié -> SIG générique.
    'GMA': {'name': 'Global Mountain Activity', 'sig': 'GMA',
            'ref_re': r'^[A-Z0-9]{1,3}/[A-Z]{2}-\d{3}$', 'min_qso': 4,
            'p2p': 'Summit-to-Summit', 'example': 'DL/BE-055'},
    # DFCF (Diplôme des Forts et Châteaux de France) — patrimoine FR, hébergé REF.
    # Vérifié sur dfcf.fr/reglement.html (31/08/2026) : réf. « DFCF-<dept 2 ch>
    # <n° 3 ch> » (ex. DFCF-01001 = château du département 01, n° 001).
    # Activation valide = 100 liaisons HF (50 en réactivation ; 25 VHF / 15 UHF)
    # -> seuil « première activation HF » retenu comme min_qso. Rayon 1000 m
    # (maj 01/01/2026) et modes CW+SSB seulement : NON modélisés (LogX n'a pas de
    # champ rayon/modes-autorisés par programme, seulement réf + seuil QSO).
    # Aucun champ ADIF dédié aux châteaux -> SIG/SIG_INFO générique (comme
    # ARLHS/WCA). Corse 2A/2B couverte ; DOM (dept 3 ch) à élargir si un cas
    # réel légitime échoue.
    'DFCF': {'name': 'Diplôme des Forts et Châteaux de France', 'sig': 'DFCF',
             'ref_re': r'^DFCF-(?:\d{2}|2[AB])\d{3}$', 'min_qso': 100,
             'p2p': 'Château-to-Château', 'example': 'DFCF-01001'},
    # DMF (Diplôme des Moulins de France) — patrimoine FR, hébergé REF
    # (dmf.r-e-f.org). Format « DMF<dept>.<n°> » (ex. DMF01.001, moulins du dépt
    # 01 n° 001), activation valide = 100 QSO HF (50 réactivation ; 25 VHF).
    # ⚠️ FORMAT PROVISOIRE — source dmf.r-e-f.org indisponible (HTTP 503) au
    # moment du code. Regex TOLÉRANT (décision F4GLD 31/08) : on ne rejette PAS
    # une référence réelle qui ne suit pas exactement ce format — séparateur . ou
    # -, espace/tiret optionnel après DMF, Corse 2A/2B. À resserrer quand le
    # règlement officiel sera reconfirmé. Pas de champ ADIF dédié -> SIG générique.
    'DMF': {'name': 'Diplôme des Moulins de France', 'sig': 'DMF',
            'ref_re': r'^DMF[- ]?(?:\d{1,4}|2[AB])[-.]\d{1,6}$', 'min_qso': 100,
            'p2p': 'Moulin-to-Moulin', 'example': 'DMF01.001', 'format_provisoire': True},
}

# Table dérivée programme -> tag ADIF dédié (source unique pour l'export ; le
# jumeau JS REF_ADIF_TAGS de logx_export_adif.js est comparé à celle-ci par
# tests/test_adif_refs_multiples.py::test_parite_mapping_js_python).
ADIF_PROGRAM_TAGS = {prog: spec['adif_tag']
                     for prog, spec in PROGRAM_SPECS.items() if 'adif_tag' in spec}


def normalize_ref(ref):
    return (ref or '').strip().upper().replace(' ', '')


def _same_utc_day(entries):
    """Ne garde que les QSO du jour UTC le plus RÉCENT parmi `entries` (champ
    ADIF 'date', format YYYYMMDD -> comparaison lexicographique valide). Sans
    champ 'date' (log sans horodatage, ou tests), toutes les entrées valent
    la même chaîne vide et rien n'est filtré : rétro-compatible."""
    if not entries:
        return entries
    today = max(str(q.get('date', '')) for q in entries)
    return [q for q in entries if str(q.get('date', '')) == today]


def validate_ref(program, ref):
    """La référence respecte-t-elle le format du programme ?"""
    spec = PROGRAM_SPECS.get((program or '').upper())
    if not spec:
        return False
    return bool(re.match(spec['ref_re'], normalize_ref(ref)))


def activation_qsos(shared_log, program, my_ref):
    """QSO appartenant à CETTE activation (ceux portant ma référence, filtrés
    à la fenêtre officielle du programme) — factorisé hors de activation_state()
    pour être réutilisé tel quel par l'export ADIF prêt-à-téléverser (même
    ensemble de QSO que celui qui fait foi pour la validité de l'activation,
    jamais une 2e définition divergente)."""
    program = (program or '').upper()
    my_ref = normalize_ref(my_ref)

    # QSO de CETTE activation : ceux portant ma référence. (Les QSO d'un autre
    # concours / d'une autre activation présents dans le log commun ne comptent
    # pas — on active FR-0123, pas le reste.) Sans référence configurée, il n'y
    # a PAS d'activation en cours : ne pas confondre avec les QSO "hors
    # activation" du log commun, dont my_sig_info est lui aussi vide —
    # normalize_ref('') == normalize_ref('') les ferait sinon tous matcher.
    entries = []
    if my_ref:
        entries = [q for q in (shared_log or [])
                   if normalize_ref(q.get('my_sig_info', '')) == my_ref]

    # POTA : le seuil de 10 QSO doit être atteint en une SEULE journée
    # calendaire UTC, pas cumulé sur plusieurs sorties sur le terrain — règle
    # officielle vérifiée sur docs.pota.app/docs/rules.html (14/08/2026) :
    # « a minimum of 10 QSOs from a park ... within a single UTC day (Zulu
    # day) ». On ne garde donc que les QSO du jour UTC le plus récent parmi
    # ceux de cette activation. À l'inverse, WWFF autorise explicitement le
    # cumul multi-activations vers son seuil de 44 QSO — vérifié sur
    # wwff.co/rules-faq/how-to-activate-a-wwff-reference/ : « you do NOT need
    # to achieve 44 QSOs in a single day ... you can combine multiple
    # visits » — donc PAS de filtrage par jour pour WWFF (ni les autres
    # programmes, dont aucune règle officielle trouvée n'exige une fenêtre
    # d'une journée unique).
    if program == 'POTA':
        entries = _same_utc_day(entries)

    return entries


def activation_state(shared_log, program, my_ref):
    """Avancement d'une activation : total QSO, uniques, P2P, validité, par
    bande/mode, QSO restants pour valider."""
    program = (program or '').upper()
    my_ref = normalize_ref(my_ref)
    spec = PROGRAM_SPECS.get(program, {})
    min_qso = spec.get('min_qso', 10)

    entries = activation_qsos(shared_log, program, my_ref)

    calls, per_band, per_mode = set(), {}, {}
    # Compteur d'ÉLIGIBILITÉ (décision F4GLD ④) : pour le seuil d'activation,
    # un même indicatif recontacté sur la MÊME bande + MÊME mode + MÊME jour UTC
    # ne compte qu'une fois (POTA ET WWFF). On garde à part le total BRUT (toutes
    # les lignes enregistrées) : la liste exportée n'est JAMAIS dédupliquée, seul
    # le compteur d'éligibilité exclut les doublons. Bande/mode/date absents
    # (log sans horodatage) → chaîne vide : rétro-compatible, deux indicatifs
    # distincts restent distincts.
    eligible = set()
    p2p = []
    for q in entries:
        call_u = str(q.get('call', '')).upper().strip()
        calls.add(call_u)
        if call_u:
            eligible.add((call_u,
                          str(q.get('band', '')).strip().lower(),
                          str(q.get('mode', '')).upper().strip(),
                          str(q.get('date', '')).strip()))
        b = str(q.get('band', '?'))
        m = str(q.get('mode', '?')).upper()
        per_band[b] = per_band.get(b, 0) + 1
        per_mode[m] = per_mode.get(m, 0) + 1
        their = normalize_ref(q.get('sig_info', ''))
        their_prog = str(q.get('sig', '')).strip().upper()
        # P2P uniquement si le correspondant est dans le MÊME programme (champ
        # ADIF 'sig'). Un 'sig' ABSENT est toléré (beaucoup d'ADIF ne
        # remplissent que sig_info — cas courant) ; mais un 'sig' présent et
        # DIFFÉRENT (ex. un SOTA travaillé pendant une activation POTA) n'est
        # PAS un contact parc-à-parc.
        if their and (not their_prog or their_prog == program):
            p2p.append({'call': str(q.get('call', '')).upper(),
                        'ref': their, 'band': b, 'mode': m})

    total = len(entries)
    qso_eligible = len(eligible)
    return {
        'program': program,
        'program_name': spec.get('name', program),
        'my_ref': my_ref,
        'valid_ref': validate_ref(program, my_ref) if my_ref else False,
        'qso_total': total,                       # lignes brutes enregistrées
        'qso_eligible': qso_eligible,             # uniques (call+band+mode+jour)
        'doublons': max(0, total - qso_eligible),
        'unique_calls': len(calls),
        'min_qso': min_qso,
        'valid': qso_eligible >= min_qso,         # le seuil se juge sur l'éligible
        'needed': max(0, min_qso - qso_eligible),
        'p2p_label': spec.get('p2p', 'P2P'),
        'p2p_count': len(p2p),
        'p2p': p2p[-25:],
        'per_band': dict(sorted(per_band.items(), key=lambda kv: -kv[1])),
        'per_mode': dict(sorted(per_mode.items(), key=lambda kv: -kv[1])),
    }


def programs_meta():
    """Métadonnées des programmes pour l'UI (nom, exemple, min, label P2P)."""
    return {k: {'name': v['name'], 'example': v['example'],
                'min_qso': v['min_qso'], 'p2p': v['p2p']}
            for k, v in PROGRAM_SPECS.items()}


def activation_summary(shared_log):
    """Résumé À VIE, par programme d'activation (POTA/SOTA/IOTA/WWFF/...), du
    nombre de références UNIQUES que l'opérateur a ACTIVÉES (champ ADIF
    my_sig_info : c'est MA référence) et CHASSÉES (champ sig_info : la référence
    de l'activateur d'en face que j'ai contacté).

    Agrégation PURE du log commun — aucune confirmation externe requise (à la
    différence des diplômes DXCC/WAS). Complète le tableau des diplômes pour les
    programmes d'activation, jusque-là suivis seulement pour l'activation EN
    COURS (activation_state), pas sur la durée de vie de la station.

    Retour : {PROGRAMME: {'activated': N, 'hunted': M}} pour les seuls
    programmes ayant au moins une référence (activée ou chassée)."""
    prog_keys = set(PROGRAM_SPECS)
    activated = {p: set() for p in prog_keys}
    hunted = {p: set() for p in prog_keys}
    for q in (shared_log or []):
        if not isinstance(q, dict):
            continue
        msig = str(q.get('my_sig', '')).upper().strip()
        if msig in prog_keys:
            ref = normalize_ref(q.get('my_sig_info', ''))
            if ref:
                activated[msig].add(ref)
        sig = str(q.get('sig', '')).upper().strip()
        if sig in prog_keys:
            ref = normalize_ref(q.get('sig_info', ''))
            if ref:
                hunted[sig].add(ref)
    out = {}
    for p in prog_keys:
        if activated[p] or hunted[p]:
            out[p] = {'activated': len(activated[p]), 'hunted': len(hunted[p]),
                      'activated_refs': sorted(activated[p]),
                      'hunted_refs': sorted(hunted[p])}
    return out
