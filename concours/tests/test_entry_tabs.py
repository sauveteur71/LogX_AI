import os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()
JS = open(os.path.join(BASE, 'logx_entry_tabs.js'), encoding='utf-8').read()

def _entry_zone():
    i = HTML.index('id="inputCall"')
    return HTML[i:i+8000]

def test_les_quatre_onglets_existent():
    for t in ('data-tab="qso"', 'data-tab="corr"', 'data-tab="mystation"', 'data-tab="qsl"'):
        assert t in HTML, t

def test_chemin_critique_hors_onglet():
    # inputCall/RST/submit ne sont pas dans un conteneur .entry-tabpane, ni expert-only
    z = HTML[HTML.index('id="inputCall"')-400:HTML.index('id="inputCall"')]
    assert 'entry-tabpane' not in z
    assert 'expert-only' not in z

def test_init_et_select_definis():
    assert 'function entryTabsInit(' in JS
    assert 'function entryTabSelect(' in JS
    assert "localStorage" in JS and 'logx_entry_tab' in JS
