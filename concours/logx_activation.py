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
PROGRAM_SPECS = {
    'POTA': {'name': 'Parks on the Air',        'sig': 'POTA',
             'ref_re': r'^[A-Z0-9]{1,4}-\d{3,5}$', 'min_qso': 10,
             'p2p': 'Park-to-Park', 'example': 'FR-0123'},
    'SOTA': {'name': 'Summits on the Air',      'sig': 'SOTA',
             'ref_re': r'^[A-Z0-9]{1,3}/[A-Z]{2}-\d{3}$', 'min_qso': 4,
             'p2p': 'Summit-to-Summit', 'example': 'F/AB-001'},
    'IOTA': {'name': 'Islands on the Air',      'sig': 'IOTA',
             'ref_re': r'^(AF|AN|AS|EU|NA|OC|SA)-\d{3}$', 'min_qso': 1,
             'p2p': 'Island-to-Island', 'example': 'EU-064'},
    'WWFF': {'name': 'World Wide Flora & Fauna', 'sig': 'WWFF',
             'ref_re': r'^[A-Z0-9]{1,3}FF-\d{4}$', 'min_qso': 44,
             'p2p': 'Flora-to-Flora', 'example': 'FFF-0123'},
    'ARLHS': {'name': 'Amateur Radio Lighthouse Society', 'sig': 'ARLHS',
              'ref_re': r'^[A-Z]{2,3}-\d{3,4}[A-Z]?$', 'min_qso': 2,
              'p2p': 'Light-to-Light', 'example': 'FRA-113'},
    'WCA': {'name': 'World Castles Award',      'sig': 'WCA',
            'ref_re': r'^[A-Z]{1,3}-\d{5}$', 'min_qso': 50,
            'p2p': 'Castle-to-Castle', 'example': 'DL-00001'},
}


def normalize_ref(ref):
    return (ref or '').strip().upper().replace(' ', '')


def validate_ref(program, ref):
    """La référence respecte-t-elle le format du programme ?"""
    spec = PROGRAM_SPECS.get((program or '').upper())
    if not spec:
        return False
    return bool(re.match(spec['ref_re'], normalize_ref(ref)))


def activation_state(shared_log, program, my_ref, now=None):
    """Avancement d'une activation : total QSO, uniques, P2P, validité, par
    bande/mode, QSO restants pour valider."""
    program = (program or '').upper()
    my_ref = normalize_ref(my_ref)
    spec = PROGRAM_SPECS.get(program, {})
    min_qso = spec.get('min_qso', 10)

    # QSO de CETTE activation : ceux portant ma référence. (Les QSO d'un autre
    # concours / d'une autre activation présents dans le log commun ne comptent
    # pas — on active FR-0123, pas le reste.)
    entries = [q for q in (shared_log or [])
               if normalize_ref(q.get('my_sig_info', '')) == my_ref]

    calls, per_band, per_mode = set(), {}, {}
    p2p = []
    for q in entries:
        calls.add(str(q.get('call', '')).upper())
        b = str(q.get('band', '?'))
        m = str(q.get('mode', '?')).upper()
        per_band[b] = per_band.get(b, 0) + 1
        per_mode[m] = per_mode.get(m, 0) + 1
        their = normalize_ref(q.get('sig_info', ''))
        if their:
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
