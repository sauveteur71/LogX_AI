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
