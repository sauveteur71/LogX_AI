# -*- coding: utf-8 -*-
"""Départements français — multiplicateur des concours REF (hors ligne).

Un indicatif métropolitain N'ENCODE PAS le département : il est transmis dans
l'ÉCHANGE (ex. « 59 042 » → dept 042). L'outre-mer, lui, est dérivable du
préfixe (et déjà distingué par cty.dat comme entités DXCC séparées).

Ce module fournit :
- DEPARTMENTS : n° → nom (métropole + Corse + DOM), pour valider/afficher ;
- dept_from_exchange() : extrait le n° de département d'un échange reçu ;
- department_mult_count() : compte les départements DISTINCTS reçus (le vrai
  multiplicateur des concours REF « dept_dxcc », inconnaissable au spot).
"""
import re
from logx_storage import qso_scope_id

# Départements métropolitains 01-95 + Corse (2A/2B) + Île-de-France + DOM 971-976
DEPARTMENTS = {
    '01': 'Ain', '02': 'Aisne', '03': 'Allier', '04': 'Alpes-de-Hte-Provence',
    '05': 'Hautes-Alpes', '06': 'Alpes-Maritimes', '07': 'Ardèche', '08': 'Ardennes',
    '09': 'Ariège', '10': 'Aube', '11': 'Aude', '12': 'Aveyron',
    '13': 'Bouches-du-Rhône', '14': 'Calvados', '15': 'Cantal', '16': 'Charente',
    '17': 'Charente-Maritime', '18': 'Cher', '19': 'Corrèze', '2A': 'Corse-du-Sud',
    '2B': 'Haute-Corse', '21': "Côte-d'Or", '22': "Côtes-d'Armor", '23': 'Creuse',
    '24': 'Dordogne', '25': 'Doubs', '26': 'Drôme', '27': 'Eure', '28': 'Eure-et-Loir',
    '29': 'Finistère', '30': 'Gard', '31': 'Haute-Garonne', '32': 'Gers', '33': 'Gironde',
    '34': 'Hérault', '35': 'Ille-et-Vilaine', '36': 'Indre', '37': 'Indre-et-Loire',
    '38': 'Isère', '39': 'Jura', '40': 'Landes', '41': 'Loir-et-Cher', '42': 'Loire',
    '43': 'Haute-Loire', '44': 'Loire-Atlantique', '45': 'Loiret', '46': 'Lot',
    '47': 'Lot-et-Garonne', '48': 'Lozère', '49': 'Maine-et-Loire', '50': 'Manche',
    '51': 'Marne', '52': 'Haute-Marne', '53': 'Mayenne', '54': 'Meurthe-et-Moselle',
    '55': 'Meuse', '56': 'Morbihan', '57': 'Moselle', '58': 'Nièvre', '59': 'Nord',
    '60': 'Oise', '61': 'Orne', '62': 'Pas-de-Calais', '63': 'Puy-de-Dôme',
    '64': 'Pyrénées-Atlantiques', '65': 'Hautes-Pyrénées', '66': 'Pyrénées-Orientales',
    '67': 'Bas-Rhin', '68': 'Haut-Rhin', '69': 'Rhône', '70': 'Haute-Saône',
    '71': 'Saône-et-Loire', '72': 'Sarthe', '73': 'Savoie', '74': 'Haute-Savoie',
    '75': 'Paris', '76': 'Seine-Maritime', '77': 'Seine-et-Marne', '78': 'Yvelines',
    '79': 'Deux-Sèvres', '80': 'Somme', '81': 'Tarn', '82': 'Tarn-et-Garonne',
    '83': 'Var', '84': 'Vaucluse', '85': 'Vendée', '86': 'Vienne', '87': 'Haute-Vienne',
    '88': 'Vosges', '89': 'Yonne', '90': 'Territoire de Belfort', '91': 'Essonne',
    '92': 'Hauts-de-Seine', '93': 'Seine-St-Denis', '94': 'Val-de-Marne', '95': "Val-d'Oise",
    '971': 'Guadeloupe', '972': 'Martinique', '973': 'Guyane', '974': 'La Réunion',
    '975': 'St-Pierre-et-Miquelon', '976': 'Mayotte',
}


def _is_rst(tok):
    """Un token ressemble-t-il à un RST ('59', '599', '55'...) ? readability
    1-5, strength 1-9, tonalité 9 optionnelle. Sert à ne pas prendre le '59'
    d'un RST pour le département Nord."""
    return bool(re.fullmatch(r'[1-5][1-9]9?', tok))


def dept_from_exchange(num_rcvd):
    """Extrait le n° de département d'un échange reçu.
    En PRODUCTION le champ « DEPT RCU » contient le département SEUL (le RST
    est un champ séparé) : un token unique EST le département ('33' → 33,
    '43' → 43, '971' → DOM). Le format combiné « RST dept » (plusieurs tokens,
    ex. '59 04') est aussi géré défensivement : on retire alors le RST de tête
    pour lever l'ambiguïté (le RST '599' contient '59'). '' si rien de fiable."""
    s = str(num_rcvd or '').upper()
    m = re.search(r'\b(2[AB])\b', s)
    if m and m.group(1) in DEPARTMENTS:
        return m.group(1)
    toks = re.findall(r'\d{2,3}', s)
    if not toks:
        return ''
    # Plusieurs tokens = format combiné « RST dept » → jette le RST de tête.
    # Un seul token = le département lui-même (cas de production) : ne rien jeter.
    if len(toks) > 1 and _is_rst(toks[0]):
        toks = toks[1:]
    for tok in toks:
        # Un token de 2 chiffres (01-95) ou un DOM à 3 chiffres (971-976) est
        # accepté tel quel. On NE tronque PLUS un token de 3 chiffres à ses 2
        # premiers : un numéro de série du Bol d'Or ('042', '590') n'est pas le
        # département '04'/'59' — ce court-circuit verdissait la carte à tort et
        # gonflait le multiplicateur REF (l'échange prime sur calldb/locator).
        if tok in DEPARTMENTS:
            return tok
    return ''


def department_mult_count(shared_log, contest_id=''):
    """Nombre de départements français DISTINCTS reçus dans les échanges du log
    — le vrai multiplicateur « dept » des concours REF. Retourne un set de n°.
    `contest_id` est une PORTÉE (voir logx_storage.active_scope_id), pas le nom
    brut du concours — un QSO non tagué ne compte jamais pour une portée précise."""
    depts = set()
    for q in shared_log or []:
        if contest_id and qso_scope_id(q) != contest_id:
            continue
        d = dept_from_exchange(q.get('num_rcvd', ''))
        if d:
            depts.add(d)
    return depts


# ─── TABLEAU DE CHASSE (carte de France à verdir) ────────────────────────────
# 96 métropolitains (01-95 + 2A/2B) : la cible du « verdir toute la France ».
# Les DOM sont un bonus, comptés à part (hors carte métropolitaine).
METRO = [c for c in DEPARTMENTS if c not in ('971', '972', '973', '974', '975', '976')]
DOM = ['971', '972', '973', '974', '975', '976']

GEOJSON_FILE = 'france_departements.geojson'
GEOJSON_URL = ('https://raw.githubusercontent.com/gregoiredavid/france-geojson/'
               'master/departements-version-simplifiee.geojson')


# ─── LOCATOR → DÉPARTEMENT (point dans polygone) ─────────────────────────────
# Beaucoup de concours REF n'échangent PAS le département (Bol d'Or : n° de
# série) : on retrouve alors le département par la GÉOGRAPHIE — le centre du
# locator testé contre les polygones du GeoJSON. Réservé aux indicatifs
# français (F/TM/TK... via cty.dat) pour ne pas verdir un voisin frontalier.
_dept_polys = None   # [(code, [anneaux de (lon, lat)])], mémorisé seulement
                      # une fois le chargement RÉUSSI (fichier local ou
                      # téléchargement) — un échec n'est jamais figé.
_dept_polys_last_try = 0.0   # horodatage (monotonic) du dernier échec, pour
                              # éviter de retenter un fetch bloquant à CHAQUE
                              # QSO réenrichi tant que le réseau reste
                              # indisponible.


def _load_dept_polygons():
    global _dept_polys, _dept_polys_last_try
    if _dept_polys is not None:
        return _dept_polys
    import json
    import time
    now = time.monotonic()
    if now - _dept_polys_last_try < 300:
        # Échec récent (< 5 min) : pas de nouvelle tentative bloquante
        # maintenant. Le prochain appel après le délai de grâce retentera
        # normalement load_france_geojson().
        return []
    _dept_polys_last_try = now
    polys = []
    raw = load_france_geojson()
    if raw:
        try:
            for ft in json.loads(raw).get('features', []):
                code = ft['properties'].get('code', '')
                geom = ft.get('geometry', {})
                rings = []
                if geom.get('type') == 'Polygon':
                    rings = [geom['coordinates'][0]]
                elif geom.get('type') == 'MultiPolygon':
                    rings = [p[0] for p in geom['coordinates']]
                if code and rings:
                    polys.append((code, rings))
        except Exception:
            polys = []
    if polys:
        _dept_polys = polys   # ne mémorise (et ne fige) que le succès ; un
                               # échec reste retenté après le délai de grâce
    return polys


def _point_in_ring(lon, lat, ring):
    """Ray casting classique."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > lat) != (yj > lat)) and \
                (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def dept_from_locator(locator):
    """Locator Maidenhead → n° de département (centre du carré testé contre
    les polygones). '' si hors de France ou GeoJSON indisponible."""
    from logx_utils import locator_to_latlon
    lat, lon = locator_to_latlon(locator or '')
    if lat is None:
        return ''
    # Cadre France métropolitaine rapide avant les polygones
    if not (41.0 <= lat <= 51.5 and -5.5 <= lon <= 10.0):
        return ''
    for code, rings in _load_dept_polygons():
        for ring in rings:
            if _point_in_ring(lon, lat, ring):
                return code
    return ''


def _is_french_call(call):
    try:
        import logx_dxcc as dxcc
        r = dxcc.lookup(call)
        return bool(r) and r['country'] in ('France', 'Corsica')
    except Exception:
        return str(call or '').upper().startswith(('F', 'TM', 'TK'))


def dept_for_qso(qso, calldb=None):
    """Département d'un QSO, du plus fiable au moins fiable :
    1. l'échange reçu (concours à département),
    2. la base d'indicatifs locale (calldb.json, champ dept),
    3. la géographie du locator (point dans polygone, indicatifs français)."""
    d = dept_from_exchange(qso.get('num_rcvd', ''))
    if d:
        return d
    call = str(qso.get('call', '')).split('/')[0].upper()
    if not _is_french_call(call):
        return ''
    if calldb:
        d = str((calldb.get(call, {}) or {}).get('dept', '')).strip()
        if d in DEPARTMENTS:
            return d
    return dept_from_locator(qso.get('locator', ''))


# Cache mémoire de calldb.json invalidé par la signature (mtime, taille) du
# fichier : departments_progress() est appelée à CHAQUE poll de l'onglet Cartes
# et re-parsait sinon un fichier de plusieurs milliers d'indicatifs à chaque
# fois. La réécriture du fichier (lookup HamQTH, /calldb/update) change le mtime
# et recharge automatiquement.
_calldb_cache = {'sig': None, 'calls': {}}


def _load_calldb():
    import json, os
    try:
        if os.path.exists('calldb.json'):
            st = os.stat('calldb.json')
            sig = (st.st_mtime, st.st_size)
            if _calldb_cache['sig'] == sig:
                return _calldb_cache['calls']
            with open('calldb.json', encoding='utf-8') as f:
                calls = json.load(f).get('calls', {})
            _calldb_cache['sig'] = sig
            _calldb_cache['calls'] = calls
            return calls
    except Exception:
        pass
    return {}


def departments_progress(shared_log, contest_id=''):
    """Tableau de chasse : départements contactés vs total, pour la carte et
    la grille. { worked:[...], metro_total, metro_done, dom_done, all:{code:nom} }.
    Détection à 3 niveaux (échange > calldb > locator) : fonctionne aussi pour
    les concours REF sans département dans l'échange (Bol d'Or...).
    `contest_id` est une PORTÉE (voir logx_storage.active_scope_id), pas le nom
    brut du concours — un QSO non tagué ne compte jamais pour une portée précise."""
    calldb = _load_calldb()
    worked = set()
    for q in shared_log or []:
        if contest_id and qso_scope_id(q) != contest_id:
            continue
        d = dept_for_qso(q, calldb)
        if d:
            worked.add(d)
    metro_done = sorted(w for w in worked if w in METRO)
    dom_done = sorted(w for w in worked if w in DOM)
    return {
        'worked': sorted(worked),
        'metro': METRO,
        'metro_total': len(METRO),
        'metro_done': len(metro_done),
        'dom': DOM,
        'dom_done': len(dom_done),
        'all': DEPARTMENTS,
    }


# Lookup callbook en direct pour les indicatifs spottés jamais croisés
# nulle part (ni QSO, ni calldb, ni archives) : sans ça, une station spottée
# EN CE MOMENT dans un département manquant n'apparaît jamais comme cible tant
# qu'aucun QSO ou lookup manuel n'a été fait pour elle — le pire moment, car
# c'est en tout DÉBUT de concours (log vide) que cette fonctionnalité serait
# la plus utile. Échecs mis en petit cache local (15 min) pour ne pas marteler
# QRZ/HamQTH/HamDB à chaque poll (60 s) pour un indicatif qui ne résoudra
# jamais (le cache 24h de logx_callbook ne mémorise que les succès).
_live_fail_cache = {}   # CALL -> timestamp du dernier échec
LIVE_FAIL_RETRY_S = 15 * 60
LIVE_LOOKUP_CAP = 5     # plafond de lookups réseau par appel (borne la latence)


def _resolve_spotted_live(spotted, known_calls, cfg):
    """{call: dept} pour les indicatifs spottés français, inconnus localement,
    résolus via un lookup callbook en direct (grid -> dept_from_locator)."""
    import time
    if cfg is None or not spotted:
        return {}
    import logx_callbook as callbook
    now = time.time()
    resolved = {}
    attempts = 0
    for call in spotted:
        if call in known_calls or not _is_french_call(call):
            continue
        last_fail = _live_fail_cache.get(call)
        if last_fail and now - last_fail < LIVE_FAIL_RETRY_S:
            continue
        if attempts >= LIVE_LOOKUP_CAP:
            break
        attempts += 1
        try:
            r = callbook.lookup(call, cfg)
        except Exception:
            r = {'ok': False}
        d = dept_from_locator(r.get('grid', '')) if r.get('ok') else ''
        if d in DEPARTMENTS:
            resolved[call] = d
        else:
            _live_fail_cache[call] = now
    return resolved


def department_targets(shared_log, contest_id='', spots_by_label=None, max_calls=5, cfg=None):
    """CHASSE AUX DÉPARTEMENTS : pour chaque département métropolitain
    MANQUANT, les stations connues de ce département (historique complet :
    calldb + archives + log) et celles actuellement SPOTTÉES sur le cluster
    (avec leur fréquence — prêtes à être appelées). Les indicatifs français
    spottés mais jamais croisés nulle part sont en plus résolus par un lookup
    callbook en direct (cf. _resolve_spotted_live) si `cfg` est fourni.
    Tri : départements avec une station spottée d'abord."""
    prog = departments_progress(shared_log, contest_id)
    worked = set(prog['worked'])
    missing = [c for c in METRO if c not in worked]

    # Historique complet inversé : département -> stations connues
    from logx_callhistory import build_index
    idx = build_index(shared_log)
    by_dept = {}
    for call, e in idx.items():
        d = e.get('dept')
        if d in DEPARTMENTS:
            by_dept.setdefault(d, []).append((call, e['qso_count']))

    # Spots cluster actuels : indicatif -> {freq, band} (formats hétérogènes)
    spotted = {}
    for label, spots in (spots_by_label or {}).items():
        for sp in spots or []:
            if isinstance(sp, dict):
                c = str(sp.get('dx') or sp.get('call') or '')
                freq = sp.get('freq', '')
            else:
                c = str(sp[0]) if sp else ''
                freq = sp[1] if len(sp) > 1 else ''
            c = c.strip().upper()
            base = c.split('/')[0] if '/' in c and len(c.split('/')[0]) >= 3 else c
            if len(base) >= 3:
                spotted[base] = {'freq': freq, 'band': label}

    known_calls = {c for calls in by_dept.values() for c, _ in calls}
    live_resolved = _resolve_spotted_live(spotted, known_calls, cfg)

    targets = []
    for d in missing:
        calls = sorted(by_dept.get(d, []), key=lambda ce: (-ce[1], ce[0]))
        sp_here = [{'call': c, **spotted[c]} for c, _ in calls if c in spotted][:3]
        already = {t['call'] for t in sp_here}
        for call, cd in live_resolved.items():
            if cd == d and call not in already and len(sp_here) < 3:
                sp_here.append({'call': call, **spotted[call]})
        targets.append({
            'dept': d,
            'name': DEPARTMENTS.get(d, ''),
            'spotted': sp_here,
            'known': [c for c, _ in calls[:max_calls]],
        })
    targets.sort(key=lambda t: (0 if t['spotted'] else 1, t['dept']))
    return {'missing_total': len(missing), 'worked_total': len(worked),
            'targets': targets}


def load_france_geojson():
    """Contenu du GeoJSON des départements (cache disque, re-téléchargé s'il
    manque). Retourne le texte JSON ou '' si indisponible hors ligne."""
    import os
    if os.path.exists(GEOJSON_FILE):
        try:
            with open(GEOJSON_FILE, encoding='utf-8') as f:
                return f.read()
        except Exception:
            pass
    from logx_utils import fetch_url
    data = fetch_url(GEOJSON_URL, timeout=30)
    if data and len(data) > 100000 and 'FeatureCollection' in data:
        try:
            with open(GEOJSON_FILE, 'w', encoding='utf-8', newline='') as f:
                f.write(data)
        except Exception:
            pass
        return data
    return ''
