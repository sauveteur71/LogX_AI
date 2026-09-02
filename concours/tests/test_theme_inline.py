# -*- coding: utf-8 -*-
"""Thème INCORPORÉ dans le HTML au service (contournement Web Shield antivirus).

logx_theme.css est un fichier séparé -> 2e requête que l'antivirus (Avast Web
Shield) peut bloquer/tronquer sans toucher au HTML -> page sans thème. Le serveur
remplace donc, à la volée, le <link> par le CSS INLINE : plus de requête séparée
à bloquer, et UNE seule source (le fichier reste l'original). On teste les
helpers sur le VRAI logx_theme.css."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_http as httpmod   # noqa: E402

import http.server            # noqa: E402
import threading              # noqa: E402
import urllib.request         # noqa: E402

import pytest                 # noqa: E402


def test_le_link_est_remplace_par_le_style_avec_les_tokens():
    html = (b'<head><title>x</title>'
            + httpmod._THEME_LINK.encode('utf-8')
            + b'<script src="logx_theme_guard.js"></script></head>')
    out = httpmod._inline_theme_in_html(html)
    # plus de <link> vers le .css (donc plus de requête séparée à bloquer)
    assert httpmod._THEME_LINK.encode('utf-8') not in out
    # remplacé par un <style> inline
    assert b'<style id="logx-theme-inline">' in out
    # les tokens de thème sont bien présents (sinon l'inlining ne servirait à rien)
    assert b'--accent' in out and b'--bg' in out
    # le garde-fou reste chargé (dernier recours)
    assert b'logx_theme_guard.js' in out


def test_noop_si_pas_de_link():
    html = b'<head>aucune feuille de theme ici</head>'
    assert httpmod._inline_theme_in_html(html) == html


def test_le_style_ne_peut_pas_etre_ferme_par_le_css():
    style = httpmod._theme_css_inline_style()
    assert style.startswith('<style id="logx-theme-inline">')
    assert style.rstrip().endswith('</style>')
    # exactement UNE balise de fermeture (aucun </style> parasite injecté par le CSS)
    assert style.count('</style>') == 1


def test_cache_relit_si_le_fichier_change(tmp_path, monkeypatch):
    """Le cache mémoire doit suivre une modification du fichier (dev qui édite
    la palette) — sinon on servirait un thème périmé jusqu'au redémarrage."""
    faux = tmp_path / 'logx_theme.css'
    faux.write_text(':root{--accent:#111}', encoding='utf-8')
    monkeypatch.setattr(httpmod, '_THEME_CSS_PATH', str(faux))
    monkeypatch.setattr(httpmod, '_theme_inline_cache', {'mtime': None, 'style': ''})
    s1 = httpmod._theme_css_inline_style()
    assert '#111' in s1
    faux.write_text(':root{--accent:#222}', encoding='utf-8')
    os.utime(faux, (faux.stat().st_atime, faux.stat().st_mtime + 5))
    s2 = httpmod._theme_css_inline_style()
    assert '#222' in s2 and '#111' not in s2


@pytest.fixture
def serveur():
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), httpmod.Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        yield 'http://127.0.0.1:%d' % port
    finally:
        srv.shutdown(); srv.server_close(); t.join(timeout=5)


def test_page_reellement_servie_a_le_theme_incorpore(serveur):
    """La vraie preuve : une page HTML servie par le serveur n'a PLUS de <link>
    séparé vers logx_theme.css (rien à bloquer pour l'antivirus) mais porte le
    thème inline avec ses tokens."""
    req = urllib.request.Request(serveur + '/logx_ft8.html',
                                 headers={'X-RC-Token': httpmod.AUTH_TOKEN})
    with urllib.request.urlopen(req, timeout=5) as r:
        body = r.read()
    assert httpmod._THEME_LINK.encode('utf-8') not in body, (
        'le <link> vers logx_theme.css subsiste -> requête séparée bloquable')
    assert b'<style id="logx-theme-inline">' in body
    assert b'--accent' in body


def test_logx_spec_embarque_les_css():
    """Garde-fou de régression : logx.spec DOIT embarquer les .css, sinon l'exe
    gelé rend des pages sans thème (logx_theme.css absent de _MEIPASS -> ni
    servi ni inlinable). Bug réel remonté par un utilisateur de l'exe (02/09)."""
    import os
    spec = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logx.spec')
    with open(spec, encoding='utf-8') as f:
        txt = f.read()
    assert "glob.glob('*.css')" in txt or 'glob.glob("*.css")' in txt, \
        "logx.spec doit globber les *.css dans _datas (sinon theme absent de l'exe)"
