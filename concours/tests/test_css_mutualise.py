# -*- coding: utf-8 -*-
"""Mutualisation CSS — les tokens du noyau (« graphite & cuivre ») vivent dans
UN SEUL fichier partagé logx_theme.css, plus dupliqués dans chaque page. Ce
test verrouille : chaque page HTML (1) charge logx_theme.css dans <head>, (2) ne
redéfinit plus les tokens du noyau dans son :root/body.day-mode. Sans ce garde,
une page pourrait ré-introduire une palette locale divergente (le défaut que la
mutualisation a corrigé)."""
import glob
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Tokens du noyau, désormais SEULEMENT dans logx_theme.css.
NOYAU = ['--bg', '--accent', '--accent2', '--border', '--muted', '--text',
         '--green', '--red', '--yellow']

PAGES = sorted(glob.glob(os.path.join(CONCOURS, 'logx_*.html')))


def _tete(txt):
    return txt[:txt.index('</head>')] if '</head>' in txt else txt


def test_le_fichier_theme_existe_et_definit_le_noyau():
    theme = open(os.path.join(CONCOURS, 'logx_theme.css'), encoding='utf-8').read()
    assert ':root' in theme and 'body.day-mode' in theme
    for t in NOYAU:
        assert t + ':' in theme, 'token %s absent du thème partagé' % t


def test_chaque_page_charge_le_theme_partage():
    for p in PAGES:
        txt = open(p, encoding='utf-8').read()
        assert 'logx_theme.css' in _tete(txt), \
            '%s ne charge pas logx_theme.css dans <head>' % os.path.basename(p)


def test_aucune_page_ne_reduplique_les_tokens_du_noyau():
    for p in PAGES:
        txt = open(p, encoding='utf-8').read()
        # bloc :root local (extras autorisés) : ne doit PAS contenir de token du noyau.
        for m in re.finditer(r':root\s*\{', txt):
            i = txt.index('{', m.start())
            prof = 0
            for k in range(i, len(txt)):
                if txt[k] == '{':
                    prof += 1
                elif txt[k] == '}':
                    prof -= 1
                    if prof == 0:
                        corps = txt[i + 1:k]
                        for t in NOYAU:
                            assert not re.search(re.escape(t) + r'\s*:', corps), \
                                '%s redéfinit %s dans son :root (doit venir du thème)' \
                                % (os.path.basename(p), t)
                        break
            break
