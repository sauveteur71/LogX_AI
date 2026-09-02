# -*- coding: utf-8 -*-
"""fetch_dxwatch_hf : quand l'API DXWatch :8010 renvoie du vide ou du HTML
(endpoint dégradé, constaté 02/09/2026), on ne doit PAS émettre de « parse
error » trompeur — juste 0 spot, silencieusement. Aucun socket ici : fetch_url
est monkeypatché."""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_clusters as clusters   # noqa: E402


def test_contenu_html_ne_crie_pas_parse_error(monkeypatch, capsys):
    monkeypatch.setattr(clusters, 'fetch_url',
                        lambda *a, **k: '<html><body>error</body></html>')
    spots = clusters.fetch_dxwatch_hf()
    assert spots == []
    assert 'parse error' not in capsys.readouterr().out


def test_contenu_vide_ne_crie_pas_parse_error(monkeypatch, capsys):
    monkeypatch.setattr(clusters, 'fetch_url', lambda *a, **k: '')
    spots = clusters.fetch_dxwatch_hf()
    assert spots == []
    assert 'parse error' not in capsys.readouterr().out


def test_json_valide_est_toujours_parse(monkeypatch, capsys):
    # Régression inverse : un vrai JSON de spots reste décodé (le garde-fou ne
    # doit pas jeter le bébé avec l'eau du bain).
    # Ce parser de repli filtre en MHz (1.8–54) : fréquence dans la plage.
    payload = '[["F5ABC", "14.074", "DL1XYZ", "", "FT8", "1230"]]'
    monkeypatch.setattr(clusters, 'fetch_url', lambda *a, **k: payload)
    spots = clusters.fetch_dxwatch_hf(filter_digital=False)
    assert any(s['dx'] == 'DL1XYZ' for s in spots), spots
