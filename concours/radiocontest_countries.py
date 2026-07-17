# -*- coding: utf-8 -*-
"""Chasse aux PAYS (DXCC) — variante « internationale » de la chasse aux
départements. Pour les concours DXCC (CQ WW, WPX, ARRL DX, REF HF côté DX…),
l'onglet montre les pays contactés / manquants au lieu des départements.

Déterministe, hors-ligne (cty.dat via radiocontest_dxcc + drapeaux via
radiocontest_flags). Modelé sur radiocontest_departments.
"""

CONTINENT_NAMES = {
    'EU': 'Europe', 'NA': 'Amérique du Nord', 'SA': 'Amérique du Sud',
    'AF': 'Afrique', 'AS': 'Asie', 'OC': 'Océanie', 'AN': 'Antarctique',
}
CONTINENT_ORDER = ['EU', 'NA', 'SA', 'AS', 'AF', 'OC', 'AN']


def _worked_keys(shared_log, contest_id=''):
    """Ensemble des clés-pays (préfixe principal DXCC) contactées."""
    import radiocontest_dxcc as dxcc
    worked = set()
    for q in shared_log or []:
        if contest_id and q.get('contest', '') not in ('', contest_id):
            continue
        call = str(q.get('call', ''))
        if dxcc.lookup(call):                 # filtre les indicatifs inconnus
            worked.add(dxcc.country_key(call))
    return worked


def countries_progress(shared_log, contest_id=''):
    """Pays DXCC contactés vs total, groupés par continent (pour la grille).
    { worked:[prefixes], total, done, by_continent:{EU:[{prefix,country,flag,
      worked}], ...} }."""
    import radiocontest_dxcc as dxcc
    import radiocontest_flags as flags
    worked = _worked_keys(shared_log, contest_id)
    entities = dxcc.list_entities()

    by_cont = {}
    total = 0
    for e in entities:
        prefix = e['prefix']
        total += 1
        fc = flags.flag_for_prefix(prefix)
        cont = e.get('continent') or 'ZZ'
        by_cont.setdefault(cont, []).append({
            'prefix': prefix,
            'country': fc['country'] or e['country'],   # FR si connu, sinon EN
            'flag': fc['flag'],
            'worked': prefix in worked,
        })
    # Ordonner les continents + trier chaque groupe (contactés d'abord, puis nom)
    ordered = {}
    for cont in CONTINENT_ORDER + [c for c in by_cont if c not in CONTINENT_ORDER]:
        if cont in by_cont:
            ordered[cont] = sorted(by_cont[cont],
                                   key=lambda x: (not x['worked'], x['country']))
    return {
        'worked': sorted(worked),
        'total': total,
        'done': len([1 for grp in by_cont.values() for x in grp if x['worked']]),
        'continent_names': CONTINENT_NAMES,
        'by_continent': ordered,
    }


def country_targets(shared_log, contest_id='', spots_by_label=None, max_calls=6):
    """CHASSE AUX PAYS : stations actuellement SPOTTÉES sur le cluster dont le
    PAYS n'est pas encore contacté (nouveau multiplicateur), + stations connues
    de l'historique par pays manquant. Tri : nouveau pays spotté d'abord."""
    import radiocontest_dxcc as dxcc
    import radiocontest_flags as flags
    worked = _worked_keys(shared_log, contest_id)

    # Spots cluster actuels : indicatif -> {freq, band}
    spotted_new = []
    seen_calls = set()
    for label, spots in (spots_by_label or {}).items():
        for sp in spots or []:
            if isinstance(sp, dict):
                c = str(sp.get('dx') or sp.get('call') or '')
                freq = sp.get('freq', '')
            else:
                c = str(sp[0]) if sp else ''
                freq = sp[1] if len(sp) > 1 else ''
            c = c.strip().upper()
            if len(c) < 3 or c in seen_calls:
                continue
            look = dxcc.lookup(c)
            if not look:
                continue
            key = dxcc.country_key(c)
            if key in worked:
                continue                       # pays déjà fait -> pas un mult neuf
            seen_calls.add(c)
            fc = flags.flag_for_prefix(key)
            spotted_new.append({
                'call': c, 'freq': freq, 'band': label,
                'prefix': key, 'flag': fc['flag'],
                'country': fc['country'] or look.get('country', ''),
            })

    # Stations connues (historique) par pays manquant
    from radiocontest_callhistory import build_index
    idx = build_index(shared_log)
    known_by_country = {}
    for call in idx:
        look = dxcc.lookup(call)
        if not look:
            continue
        key = dxcc.country_key(call)
        if key in worked:
            continue
        known_by_country.setdefault(key, []).append(call)

    missing = [e['prefix'] for e in dxcc.list_entities()
               if e['prefix'] not in worked]
    spotted_new.sort(key=lambda t: (t['country'] or 'zzz'))
    return {
        'worked_total': len(worked),
        'missing_total': len(missing),
        'spotted': spotted_new[:40],
        'known_sample': {k: v[:max_calls] for k, v in list(known_by_country.items())[:30]},
    }
