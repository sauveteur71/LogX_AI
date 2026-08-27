# -*- coding: utf-8 -*-
"""Accessibilité de la barre de navigation principale (skill mgifford/navigation).

Audit du 27/08/2026, 2 défauts corrigés ici (ARIA pur, aucun visuel changé) :
- **Sérieux** : l'onglet actif n'avait que `class="active"` (repère purement
  visuel) — sans `aria-current="page"`, un lecteur d'écran ne dit pas sur quelle
  page on est. On l'ajoute sur le lien actif.
- **Modéré** : `<nav class="app-nav">` n'avait pas de nom accessible. La skill
  navigation impose « always wrap navigation in <nav> with a unique aria-label ».
  On ajoute `aria-label="Navigation principale"`.

Le `<main>` landmark manquant (Modéré) est un suivi structurel séparé.
"""
import glob
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Pages qui portent la nav principale (partagée).
PAGES = [os.path.basename(p) for p in glob.glob(os.path.join(CONCOURS, 'logx_*.html'))
         if '<nav class="app-nav"' in open(p, encoding='utf-8').read()]


def _html(page):
    return open(os.path.join(CONCOURS, page), encoding='utf-8').read()


def test_il_y_a_bien_des_pages_a_verifier():
    """Garde-fou : si le sélecteur de pages casse, ne pas passer vide (vacant)."""
    assert len(PAGES) >= 10, f'trop peu de pages nav trouvées : {PAGES}'


@pytest.mark.parametrize('page', PAGES)
def test_nav_a_un_nom_accessible(page):
    assert re.search(r'<nav class="app-nav"[^>]*\baria-label="[^"]+"', _html(page)), \
        f'{page} : <nav class="app-nav"> sans aria-label'


@pytest.mark.parametrize('page', PAGES)
def test_lien_actif_a_aria_current(page):
    """Tout lien nav marqué class="active" doit porter aria-current="page".
    (Les pages sans lien actif — ft8/rtty/sstv détachées — n'ont rien à vérifier
    ici, l'assertion passe à vide, ce qui est correct.)"""
    html = _html(page)
    for tag in re.findall(r'<a\b[^>]*\bclass="active"[^>]*>', html):
        assert 'aria-current="page"' in tag, \
            f'{page} : lien actif sans aria-current="page" -> {tag[:80]}'
