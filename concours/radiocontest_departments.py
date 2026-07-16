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
        if tok in DEPARTMENTS:       # DOM 971-976 (3 chiffres)
            return tok
        d2 = tok[:2]
        if d2 in DEPARTMENTS:
            return d2
    return ''


def department_mult_count(shared_log, contest_id=''):
    """Nombre de départements français DISTINCTS reçus dans les échanges du log
    — le vrai multiplicateur « dept » des concours REF. Retourne un set de n°."""
    depts = set()
    for q in shared_log or []:
        if contest_id and q.get('contest', '') not in ('', contest_id):
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
_dept_polys = None   # [(code, [anneaux de (lon, lat)])], chargé une fois


def _load_dept_polygons():
    global _dept_polys
    if _dept_polys is not None:
        return _dept_polys
    import json
    _dept_polys = []
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
                    _dept_polys.append((code, rings))
        except Exception:
            _dept_polys = []
    return _dept_polys


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
    from radiocontest_utils import locator_to_latlon
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
        import radiocontest_dxcc as dxcc
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


def _load_calldb():
    import json, os
    try:
        if os.path.exists('calldb.json'):
            with open('calldb.json', encoding='utf-8') as f:
                return json.load(f).get('calls', {})
    except Exception:
        pass
    return {}


def departments_progress(shared_log, contest_id=''):
    """Tableau de chasse : départements contactés vs total, pour la carte et
    la grille. { worked:[...], metro_total, metro_done, dom_done, all:{code:nom} }.
    Détection à 3 niveaux (échange > calldb > locator) : fonctionne aussi pour
    les concours REF sans département dans l'échange (Bol d'Or...)."""
    calldb = _load_calldb()
    worked = set()
    for q in shared_log or []:
        if contest_id and q.get('contest', '') not in ('', contest_id):
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
    from radiocontest_utils import fetch_url
    data = fetch_url(GEOJSON_URL, timeout=30)
    if data and len(data) > 100000 and 'FeatureCollection' in data:
        try:
            with open(GEOJSON_FILE, 'w', encoding='utf-8', newline='') as f:
                f.write(data)
        except Exception:
            pass
        return data
    return ''
