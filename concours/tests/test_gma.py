# -*- coding: utf-8 -*-
"""GMA (logx_gma) : lookup PAR RÉFÉRENCE via l'API cqgma.org/api/ref/?REF.
Réseau simulé (aucun appel réel). On vérifie le mapping JSON, le cache mémoire,
et la distinction corps-vide (absent, caché) / erreur-réseau (non caché)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_gma as gma       # noqa: E402
import logx_utils           # noqa: E402

# Réponse RÉELLE (structure vérifiée en direct sur DA/NI-096), tronquée.
_SUMMIT = json.dumps({
    'ref': 'DA/NI-096', 'height': '158', 'sota_points': '0',
    'longitude': '8.13162000', 'latitude': '52.39064000', 'name': 'Venner Berg',
    'deleted': '0', 'region_name': 'Lower Saxony', 'act_count': '24',
    'wwff': 'DLFF-0125'})


def _reseau(monkeypatch, reponses):
    """reponses : dict url_suffix -> texte (ou None pour erreur réseau)."""
    monkeypatch.setattr(gma, '_cache', {})
    appels = {'n': 0}

    def fake(url, timeout=10, log_url=True, user_agent=None):
        appels['n'] += 1
        for suf, val in reponses.items():
            if url.endswith(suf):
                return val
        return ''
    monkeypatch.setattr(logx_utils, 'fetch_url', fake)
    return appels


def test_get_mappe_le_json(monkeypatch):
    _reseau(monkeypatch, {'DA/NI-096': _SUMMIT})
    e = gma.get('DA/NI-096')
    assert e['code'] == 'DA/NI-096' and e['name'] == 'Venner Berg'
    assert e['alt_m'] == 158 and e['region'] == 'Lower Saxony'
    assert e['lat'] == 52.39064 and e['lon'] == 8.13162
    assert e['wwff'] == 'DLFF-0125'


def test_get_normalise_et_cache(monkeypatch):
    appels = _reseau(monkeypatch, {'DA/NI-096': _SUMMIT})
    assert gma.get('da/ni-096')['name'] == 'Venner Berg'   # minuscules -> normalisées
    gma.get('DA/NI-096')                                    # 2e appel : cache, pas de réseau
    assert appels['n'] == 1


def test_reference_absente_corps_vide(monkeypatch):
    appels = _reseau(monkeypatch, {'ZZ/ZZ-999': ''})       # 200 corps vide
    assert gma.get('ZZ/ZZ-999') is None
    gma.get('ZZ/ZZ-999')                                   # None définitif -> caché
    assert appels['n'] == 1


def test_erreur_reseau_non_cachee(monkeypatch):
    """fetch_url -> None (erreur réseau) : NON mémorisé, réessayé au prochain appel."""
    appels = _reseau(monkeypatch, {'DA/NI-096': None})
    assert gma.get('DA/NI-096') is None
    gma.get('DA/NI-096')                                   # doit re-tenter le réseau
    assert appels['n'] == 2


def test_sommet_supprime_ignore(monkeypatch):
    supprime = json.dumps({'ref': 'DA/NI-000', 'name': 'Ancien', 'height': '100',
                           'deleted': '1', 'latitude': '50', 'longitude': '8'})
    _reseau(monkeypatch, {'DA/NI-000': supprime})
    assert gma.get('DA/NI-000') is None                    # deleted=1 -> None


def test_json_invalide_rend_none(monkeypatch):
    _reseau(monkeypatch, {'DA/NI-096': 'pas du json {{{'})
    assert gma.get('DA/NI-096') is None


def test_search_vide_et_status(monkeypatch):
    _reseau(monkeypatch, {'DA/NI-096': _SUMMIT})
    assert gma.search('venner') == []                      # pas de recherche par nom
    gma.get('DA/NI-096')
    st = gma.status()
    assert st['ready'] is True and st['count'] == 1 and st['mode'] == 'api_par_reference'
