"""Sélection de la source des décodages EME dans _eme_cockpit_dict :
WSJT-X (pont UDP, comportement historique) ou décodeur natif Q65 (logx_q65_natif),
pilotée par cfg.eme.source ('wsjtx' par défaut, ou 'natif')."""
import os, sys
CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)
import logx_http, logx_wsjtx, logx_q65_natif  # noqa: E402


def test_source_defaut_wsjtx(monkeypatch):
    monkeypatch.setattr(logx_wsjtx, 'eme_decodes', lambda *a, **k: [{'call': 'UDP'}])
    monkeypatch.setattr(logx_q65_natif, 'decodes_natifs', lambda *a, **k: [{'call': 'NATIF'}])
    d = logx_http._eme_cockpit_dict({'locator': '', 'eme': {}}, '2m')
    assert [x['call'] for x in d['decodes']] == ['UDP']


def test_source_natif_si_configuree(monkeypatch):
    monkeypatch.setattr(logx_wsjtx, 'eme_decodes', lambda *a, **k: [{'call': 'UDP'}])
    monkeypatch.setattr(logx_q65_natif, 'decodes_natifs', lambda *a, **k: [{'call': 'NATIF'}])
    d = logx_http._eme_cockpit_dict({'locator': '', 'eme': {'source': 'natif'}}, '2m')
    assert [x['call'] for x in d['decodes']] == ['NATIF']


def test_dict_expose_source_defaut_wsjtx(monkeypatch):
    # Finding C1 : le cockpit (page logx_eme.html) doit pouvoir distinguer le
    # mode natif du mode wsjtx pour savoir s'il doit afficher « WSJT-X non
    # relié » ou les décodages natifs. La clé 'source' doit donc être exposée
    # telle quelle dans le dict retourné par _eme_cockpit_dict.
    monkeypatch.setattr(logx_wsjtx, 'eme_decodes', lambda *a, **k: [])
    monkeypatch.setattr(logx_q65_natif, 'decodes_natifs', lambda *a, **k: [])
    d = logx_http._eme_cockpit_dict({'locator': '', 'eme': {}}, '2m')
    assert d['source'] == 'wsjtx'


def test_dict_expose_source_natif(monkeypatch):
    monkeypatch.setattr(logx_wsjtx, 'eme_decodes', lambda *a, **k: [])
    monkeypatch.setattr(logx_q65_natif, 'decodes_natifs', lambda *a, **k: [])
    d = logx_http._eme_cockpit_dict({'locator': '', 'eme': {'source': 'natif'}}, '2m')
    assert d['source'] == 'natif'
