# -*- coding: utf-8 -*-
"""Chasse aux PAYS (DXCC) — variante « internationale » de la chasse aux
départements. Pour les concours DXCC (CQ WW, WPX, ARRL DX, REF HF côté DX…),
l'onglet montre les pays contactés / manquants au lieu des départements.

Déterministe, hors-ligne (cty.dat via radiocontest_dxcc + drapeaux via
radiocontest_flags). Modelé sur radiocontest_departments.
"""
import re

CONTINENT_NAMES = {
    'EU': 'Europe', 'NA': 'Amérique du Nord', 'SA': 'Amérique du Sud',
    'AF': 'Afrique', 'AS': 'Asie', 'OC': 'Océanie', 'AN': 'Antarctique',
}
CONTINENT_ORDER = ['EU', 'NA', 'SA', 'AS', 'AF', 'OC', 'AN']


def _worked_keys(shared_log, contest_id=''):
    """Ensemble des pays DXCC contactés (toutes bandes confondues)."""
    import radiocontest_dxcc as dxcc
    worked = set()
    for q in shared_log or []:
        if contest_id and q.get('contest', '') not in ('', contest_id):
            continue
        call = str(q.get('call', ''))
        if dxcc.lookup(call):                 # filtre les indicatifs inconnus
            worked.add(dxcc.dxcc_entity_key(call))
    return worked


def _worked_pairs(shared_log, contest_id=''):
    """Ensemble des couples (pays, bande) contactés — pour les concours dont le
    multiplicateur DXCC est PAR BANDE (CQ WW, ARRL DX…) : un pays déjà fait sur
    20 m reste un multiplicateur neuf sur 15 m."""
    import radiocontest_dxcc as dxcc
    pairs = set()
    for q in shared_log or []:
        if contest_id and q.get('contest', '') not in ('', contest_id):
            continue
        call = str(q.get('call', ''))
        if dxcc.lookup(call):
            pairs.add((dxcc.dxcc_entity_key(call), str(q.get('band', ''))))
    return pairs


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
    # (worked contient déjà les clés repliées WAE -> parent, cohérent avec la
    #  liste d'entités qui exclut les entités WAE.)
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


def country_targets(shared_log, contest_id='', spots_by_label=None):
    """CHASSE AUX PAYS : stations SPOTTÉES sur le cluster dont le pays (sur CETTE
    bande) n'est pas encore contacté = nouveau multiplicateur DXCC. Le suivi est
    PAR BANDE (CQ WW / ARRL DX : un pays fait sur 20 m reste neuf sur 15 m).
    Tri : nouveau pays spotté d'abord."""
    import radiocontest_dxcc as dxcc
    import radiocontest_flags as flags
    from radiocontest_scoring import _band_from_freq
    worked = _worked_keys(shared_log, contest_id)          # global (pour le total)
    worked_pairs = _worked_pairs(shared_log, contest_id)   # (pays, bande)

    spotted_new = []
    seen = set()
    for label, spots in (spots_by_label or {}).items():
        for sp in spots or []:
            if isinstance(sp, dict):
                c = str(sp.get('dx') or sp.get('call') or '')
                freq = sp.get('freq', '')
            else:
                c = str(sp[0]) if sp else ''
                freq = sp[1] if len(sp) > 1 else ''
            c = re.sub(r'[^A-Z0-9/]', '', c.strip().upper())   # anti-injection
            if len(c) < 3 or not dxcc.lookup(c):
                continue
            key = dxcc.dxcc_entity_key(c)
            band = str(_band_from_freq(freq) or '') if freq else ''
            if (key, band) in worked_pairs or (not band and key in worked):
                continue                       # pays déjà fait sur cette bande
            dedup = (c, band)
            if dedup in seen:
                continue
            seen.add(dedup)
            fc = flags.flag_for_prefix(key)
            look = dxcc.lookup(c) or {}
            spotted_new.append({
                'call': c, 'freq': freq, 'band': label,
                'prefix': key, 'flag': fc['flag'],
                'country': fc['country'] or look.get('country', ''),
            })

    missing = [e['prefix'] for e in dxcc.list_entities()
               if e['prefix'] not in worked]
    spotted_new.sort(key=lambda t: (t['country'] or 'zzz'))
    return {
        'worked_total': len(worked),
        'missing_total': len(missing),
        'spotted': spotted_new[:40],
    }
