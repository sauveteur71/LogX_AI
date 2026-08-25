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
    p2p = []
    for q in entries:
        calls.add(str(q.get('call', '')).upper())
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
    return {
        'program': program,
        'program_name': spec.get('name', program),
        'my_ref': my_ref,
        'valid_ref': validate_ref(program, my_ref) if my_ref else False,
        'qso_total': total,
        'unique_calls': len(calls),
        'min_qso': min_qso,
        'valid': total >= min_qso,
        'needed': max(0, min_qso - total),
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
