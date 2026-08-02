# -*- coding: utf-8 -*-
"""Tests du multiplicateur département (concours REF)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_departments as dep
from logx_departments import (dept_from_exchange, department_mult_count,
                                      dept_from_locator, dept_for_qso, DEPARTMENTS)

# 3 rectangles simples (pas de vraies frontières) autour des centres réels des
# locators testés ci-dessous — comme FAKE_GEOJSON dans test_worldmap.py, pour
# ne JAMAIS dépendre du vrai raw.githubusercontent.com dans un test (le fichier
# local france_departements.geojson est gitignored, absent sur un checkout CI
# frais : sans ce mock, dept_from_locator() y fait un vrai fetch réseau).
#
# Centres réels (logx_utils.locator_to_latlon) : JN15XC -> lon 3.958/lat
# 45.104 ; JN25GO -> lon 4.542/lat 45.604 ; IN93RS -> lon -0.542/lat 43.771.
# Les rectangles 43/69 doivent rester DISJOINTS (pas seulement adjacents) :
# dept_from_locator() renvoie le code du PREMIER polygone qui matche dans la
# boucle, donc un chevauchement ferait toujours gagner '43' au détriment de
# '69' pour un point dans la zone commune, même si '69' serait correct.
FAKE_DEPT_GEOJSON = json.dumps({
    'type': 'FeatureCollection',
    'features': [
        {'type': 'Feature', 'properties': {'code': '43'},   # Haute-Loire (JN15XC, centre lon 3.958)
         'geometry': {'type': 'Polygon',
                      'coordinates': [[[3.3, 44.6], [4.2, 44.6], [4.2, 45.5], [3.3, 45.5], [3.3, 44.6]]]}},
        {'type': 'Feature', 'properties': {'code': '69'},   # Rhône (JN25GO, centre lon 4.542)
         'geometry': {'type': 'Polygon',
                      'coordinates': [[[4.3, 45.4], [5.0, 45.4], [5.0, 46.1], [4.3, 46.1], [4.3, 45.4]]]}},
        {'type': 'Feature', 'properties': {'code': '40'},   # Landes (IN93RS, centre lon -0.542)
         'geometry': {'type': 'Polygon',
                      'coordinates': [[[-1.5, 43.4], [0.1, 43.4], [0.1, 44.4], [-1.5, 44.4], [-1.5, 43.4]]]}},
    ],
})


def _mock_dept_geojson(monkeypatch):
    """Force _load_dept_polygons() à reparser FAKE_DEPT_GEOJSON plutôt que le
    cache réel (potentiellement déjà figé par un échec réseau précédent dans
    le même process pytest) ou un vrai fetch réseau.

    _dept_polys_last_try se compare à time.monotonic() (PAS l'epoch Unix) :
    son origine est arbitraire selon la plateforme, souvent proche de 0 sur
    un conteneur CI fraîchement démarré — y poser 0.0 laissait passer le
    garde-fou de grâce (300s) puisque `now - 0.0` pouvait y être < 300,
    ré-empêchant tout appel à load_france_geojson(). Une valeur négative
    garantit un écart > 300 quelle que soit l'origine de l'horloge."""
    monkeypatch.setattr(dep, 'load_france_geojson', lambda: FAKE_DEPT_GEOJSON)
    monkeypatch.setattr(dep, '_dept_polys', None)
    monkeypatch.setattr(dep, '_dept_polys_last_try', -1e6)


def test_rectangles_fictifs_ne_se_chevauchent_pas():
    """Garde-fou de non-régression sur FAKE_DEPT_GEOJSON lui-même :
    dept_from_locator() renvoie le code du PREMIER polygone qui matche dans
    la boucle (voir logx_departments.dept_from_locator) — si deux rectangles
    fictifs se chevauchaient, un point dans la zone commune recevrait
    toujours le même département, à tort pour l'autre (correctif : 43/69 se
    chevauchaient auparavant sur lon[4.2,4.4]xlat[45.4,45.5])."""
    features = json.loads(FAKE_DEPT_GEOJSON)['features']
    boxes = []
    for f in features:
        coords = f['geometry']['coordinates'][0]
        lons = [c[0] for c in coords]
        lats = [c[1] for c in coords]
        boxes.append((f['properties']['code'],
                      min(lons), max(lons), min(lats), max(lats)))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            code_a, a_lon0, a_lon1, a_lat0, a_lat1 = boxes[i]
            code_b, b_lon0, b_lon1, b_lat0, b_lat1 = boxes[j]
            lon_overlap = a_lon0 < b_lon1 and b_lon0 < a_lon1
            lat_overlap = a_lat0 < b_lat1 and b_lat0 < a_lat1
            assert not (lon_overlap and lat_overlap), (
                "rectangles fictifs %s et %s se chevauchent dans "
                "FAKE_DEPT_GEOJSON" % (code_a, code_b))


def test_table_complete():
    assert len(DEPARTMENTS) == 102        # 96 métropole + Corse (2A/2B) + 6 DOM
    assert DEPARTMENTS['43'] == 'Haute-Loire'
    assert DEPARTMENTS['974'] == 'La Réunion'


def test_dept_seul_production():
    """Cas de PRODUCTION : le champ DEPT RCU contient le département SEUL, y
    compris ceux dont le n° ressemble à un RST (13, 33, 44, 59...)."""
    for d in ['33', '59', '13', '44', '31', '35', '43', '54', '57', '75', '06', '90']:
        assert dept_from_exchange(d) == d, f"dept seul {d} perdu"
    assert dept_from_exchange('971') == '971'       # DOM
    assert dept_from_exchange('2A') == '2A'


def test_dept_format_combine():
    """Format combiné « RST dept » (plusieurs tokens) : le RST de tête est retiré."""
    assert dept_from_exchange('59 04') == '04'      # RST 59 + dept 04
    assert dept_from_exchange('599 04') == '04'     # RST CW 599 + dept 04
    assert dept_from_exchange('59 33') == '33'      # RST 59 + Gironde
    assert dept_from_exchange('599 999') == ''      # 999 invalide, pas de dept


def test_corse_et_dom():
    assert dept_from_exchange('2A 015') == '2A'
    assert dept_from_exchange('58 2B') == '2B'
    assert dept_from_exchange('5NN 971') == '971'   # Guadeloupe (DOM)


def test_echange_sans_dept():
    assert dept_from_exchange('abc') == ''
    assert dept_from_exchange('') == ''
    assert dept_from_exchange('599 999') == ''      # 99 n'est pas un département


def test_comptage_distinct():
    # Format de production : département seul dans num_rcvd
    log = [
        {'contest': 'REF_160M', 'num_rcvd': '33'},   # Gironde
        {'contest': 'REF_160M', 'num_rcvd': '33'},   # doublon
        {'contest': 'REF_160M', 'num_rcvd': '59'},   # Nord
        {'contest': 'REF_160M', 'num_rcvd': '2A'},   # Corse-du-Sud
        {'contest': 'AUTRE', 'num_rcvd': '13'},      # autre concours : ignoré
    ]
    depts = department_mult_count(log, 'REF_160M')
    assert depts == {'33', '59', '2A'}


# ─── Détection géographique (concours sans département dans l'échange) ───────

def test_locator_vers_departement(monkeypatch):
    """Point-dans-polygone : le centre du locator donne le département."""
    _mock_dept_geojson(monkeypatch)
    assert dept_from_locator('JN15XC') == '43'   # Chaspinhac, Haute-Loire
    assert dept_from_locator('JN25GO') == '69'   # Rhône (cas réel F1OMQ)
    assert dept_from_locator('JO31AA') == ''     # Allemagne : hors de France
    assert dept_from_locator('') == ''


def test_qso_sans_dept_dans_echange(monkeypatch):
    """Bol d'Or : l'échange est un n° de série — le locator prend le relais,
    mais UNIQUEMENT pour les indicatifs français."""
    _mock_dept_geojson(monkeypatch)
    q = {'call': 'F1OMQ', 'num_rcvd': '001', 'locator': 'JN25GO'}
    assert dept_for_qso(q) == '69'
    # Même locator mais indicatif étranger : jamais de département
    q2 = {'call': 'DL1ABC', 'num_rcvd': '001', 'locator': 'JN25GO'}
    assert dept_for_qso(q2) == ''


def test_echange_prioritaire_sur_locator():
    """Si l'échange contient le département, il prime sur la géographie."""
    q = {'call': 'F5ABC', 'num_rcvd': '33', 'locator': 'JN25GO'}
    assert dept_for_qso(q) == '33'
