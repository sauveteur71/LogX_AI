# -*- coding: utf-8 -*-
"""ARLHS (logx_arlhs) : lookup PAR RÉFÉRENCE d'un phare via la base WLOL
(cqgma/wlol.arlhs.com). Réseau simulé. HTML de résultat RÉEL (capturé en direct
sur FRA-113), pour verrouiller le parseur contre un changement silencieux de la
page. Coordonnées converties DMS -> décimal (signe pour W/S)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_arlhs as arlhs       # noqa: E402
import logx_utils               # noqa: E402

# Ligne résultat RÉELLE capturée sur wlol.arlhs.com (FRA-113 = Aber Ildut).
_ROW = (
    '<table><tr><th>Lat</th><th>Long</th><th>Map</th></tr>\n'
    '<tr bgcolor="lightgreen"><td><a href="/lighthouse/FRA113.html">Aber Ildut</a></td>'
    '<td nowrap><a href="/lighthouse/FRA113.html">FRA 113</a></td>'
    '<td nowrap align="center">- -</td><td align="center">-</td>'
    '<td nowrap align="center">48° 28.0\' N</td>'
    '<td nowrap align="center">004° 46.0\' W</td>'
    '<td nowrap align="center"><a href="https://tools.wmflabs.org/geohack/geohack.php?'
    'params=48_28_00_N_004_46_00_W" target="_blank">Map</a></td>'
    '<td>IN78ol</td><td nowrap align="center">-</td><td align="right">2</td></tr>\n'
    '</table>')
# Page « rien trouvé » : formulaire sans ligne lightgreen.
_VIDE = '<html><body><form>...</form>Aucun résultat</body></html>'


def _reseau(monkeypatch, reponse):
    monkeypatch.setattr(arlhs, '_cache', {})
    appels = {'n': 0}

    def fake(url, timeout=10, log_url=True, user_agent=None):
        appels['n'] += 1
        return reponse
    monkeypatch.setattr(logx_utils, 'fetch_url', fake)
    return appels


def test_get_parse_la_fiche(monkeypatch):
    _reseau(monkeypatch, _ROW)
    e = arlhs.get('FRA-113')
    assert e['code'] == 'FRA-113' and e['name'] == 'Aber Ildut'
    assert e['locator'] == 'IN78ol' and e['act_count'] == '2'
    # 48°28' N -> +48.4667 ; 004°46' W -> -4.7667 (signe W)
    assert abs(e['lat'] - 48.4667) < 0.001
    assert abs(e['lon'] - (-4.7667)) < 0.001


def test_get_normalise_et_cache(monkeypatch):
    appels = _reseau(monkeypatch, _ROW)
    assert arlhs.get('fra113')['code'] == 'FRA-113'    # minuscules + sans tiret
    arlhs.get('FRA-113')                               # 2e : cache, pas de réseau
    assert appels['n'] == 1


def test_reference_absente(monkeypatch):
    appels = _reseau(monkeypatch, _VIDE)
    assert arlhs.get('FRA-9999') is None
    arlhs.get('FRA-9999')                              # None définitif -> caché
    assert appels['n'] == 1


def test_erreur_reseau_non_cachee(monkeypatch):
    appels = _reseau(monkeypatch, None)                # fetch_url -> None (réseau KO)
    assert arlhs.get('FRA-113') is None
    arlhs.get('FRA-113')                               # doit re-tenter
    assert appels['n'] == 2


def test_ref_invalide(monkeypatch):
    _reseau(monkeypatch, _ROW)
    assert arlhs.get('xxx') is None
    assert arlhs.get('') is None


def test_search_vide_et_status(monkeypatch):
    _reseau(monkeypatch, _ROW)
    assert arlhs.search('aber') == []
    arlhs.get('FRA-113')
    st = arlhs.status()
    assert st['ready'] is True and st['count'] == 1
