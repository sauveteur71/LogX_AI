# -*- coding: utf-8 -*-
"""Référentiel PARTIEL DFCF (logx_dfcf) : parse de la page des validations
dfcf.fr/valide.html (ISO-8859-1, lignes <br>, champs tabulés), recherche par
référence/nom, normalisation du format. Réseau simulé (pas d'appel réel)."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_dfcf as dfcf       # noqa: E402
import logx_utils             # noqa: E402

# Fragment RÉEL (structure vérifiée en direct) : REF<tab>NOM<tab>DATE<tab>CALL
# <tab>(COMMUNE<tab>CP). 3e ligne SANS commune. Accents latin-1 seulement.
_PAGE = (
    '<b><div style="text-align: center">Mois de janvier 2026</div></b>\t \t\n'
    '11-104\tGl\xe9on Berty\t02/01/2026\tF5NLX/P\t(Marcorignan\t11120)<br>\n'
    '34-002\td\'Aumelas\t15/03/2026\tF4ABC\t(Aumelas\t34230)<br>\n'
    '49-0010\tde Montsabert\t20/04/2026\tF5XYZ/P<br>\n'      # sans commune
)


def _preparer(monkeypatch, page=_PAGE):
    # cache vide + réseau simulé (bytes latin-1, comme la vraie page)
    monkeypatch.setattr(dfcf, '_cache', {'by_code': {}, 'list': [], 'ts': 0, 'error': None})
    monkeypatch.setattr(logx_utils, 'fetch_url_binary',
                        lambda url, timeout=10: page.encode('iso-8859-1'))


def test_get_reference_validee(monkeypatch):
    _preparer(monkeypatch)
    r = dfcf.get('11-104')
    assert r and r['name'] == 'Gl\xe9on Berty'
    assert r['commune'] == 'Marcorignan' and r['cp'] == '11120'
    assert r['status'] == 'official_validated'


def test_get_normalise_le_prefixe_dfcf(monkeypatch):
    _preparer(monkeypatch)
    # DFCF49-0010 / dfcf-49-0010 doivent retrouver la même fiche que 49-0010.
    assert dfcf.get('DFCF49-0010')['name'] == 'de Montsabert'
    assert dfcf.get('dfcf-49-0010')['name'] == 'de Montsabert'


def test_ligne_sans_commune(monkeypatch):
    _preparer(monkeypatch)
    r = dfcf.get('49-0010')
    assert r['name'] == 'de Montsabert' and r['commune'] == ''


def test_recherche_par_nom(monkeypatch):
    _preparer(monkeypatch)
    res = dfcf.search('montsabert')
    assert len(res) == 1 and res[0]['code'] == '49-0010'


def test_reference_absente_rend_none(monkeypatch):
    _preparer(monkeypatch)
    assert dfcf.get('99-999') is None      # absente ≠ invalide (hors période publiée)


def test_status_partiel(monkeypatch):
    _preparer(monkeypatch)
    st = dfcf.status()
    assert st['ready'] is True and st['count'] == 3
    assert st['partiel'] is True           # liste des validés, pas le catalogue complet


def test_reseau_ko_ne_casse_pas(monkeypatch):
    _preparer(monkeypatch)
    dfcf.get('11-104')                     # remplit le cache
    monkeypatch.setattr(logx_utils, 'fetch_url_binary', lambda url, timeout=10: None)
    dfcf._cache['ts'] = 0                  # force un rechargement
    dfcf.get('11-104')                     # réseau KO -> garde l'ancien cache, pas de crash
    assert dfcf._cache['list']             # non vidé


def test_nom_nettoye_du_html(monkeypatch):
    # Certains noms de la vraie page portent des balises inline (réactivation).
    page = '41-005\t<b>(r\xe9activation)</b> de Chambord\t10/02/2026\tF5ABC\t(Chambord\t41250)<br>\n'
    _preparer(monkeypatch, page)
    r = dfcf.get('41-005')
    assert '<b>' not in r['name'] and '</b>' not in r['name']
    assert 'Chambord' in r['name']


def test_normaliser_code():
    assert dfcf._normaliser_code('DFCF49-0010') == '49-0010'
    assert dfcf._normaliser_code('11-104') == '11-104'
    assert dfcf._normaliser_code(' dfcf-11-104 ') == '11-104'
