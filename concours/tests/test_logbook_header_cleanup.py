# -*- coding: utf-8 -*-
"""Nettoyage de l'en-tête LOGBOOK (retour terrain F4GLD, 24/08).

- La barre d'état (.net-status) tient sur UNE ligne (flex-wrap:nowrap + scroll).
- Météo et pont WSJT-X « en attente » masqués (inutiles hors SOTA/expédition et
  hors mode numérique) ; soapbox EDI retirée de l'écran. Masquage CSS pur
  (« masquer ≠ bloquer » — le JS partagé et les endpoints ne sont pas touchés).
- Version déplacée dans l'en-tête (compacte « V: ») à côté du logo, plus dans
  la barre d'état. Les ids restent UNIQUES (déplacement, pas duplication).

Vérification VISUELLE des 2 thèmes = navigateur (côté F4GLD) — un test
structurel ne juge pas le rendu, seulement le câblage.
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()


def test_barre_etat_sur_une_ligne():
    i = HTML.index('.net-status{')
    regle = HTML[i:HTML.index('}', i)]
    assert 'flex-wrap:nowrap' in regle and 'overflow-x:auto' in regle


def test_meteo_wsjtx_soapbox_masques():
    assert '#weatherWidget,#wsjtxWidget{display:none!important}' in HTML
    assert '#soapboxPanel{display:none!important}' in HTML


def test_version_dans_le_header_pas_dans_la_barre():
    # la version compacte est dans l'en-tête, juste après le libellé LOGBOOK
    hdr = HTML.index('id="hdrContest"')
    vpos = HTML.index('class="hdr-version"')
    assert 0 < vpos - hdr < 400, "la version doit être dans l'en-tête, à côté du logo"
    assert 'V: <span class="net-version" id="netVersion">' in HTML
    # plus de libellé « Version : » verbeux dans la barre d'état
    assert 'Version : <span class="net-version"' not in HTML


def test_ids_uniques():
    for ident in ('netVersion', 'netVersionWarn', 'netUpdatePathBtn', 'netUpdatePathResult'):
        assert HTML.count('id="%s"' % ident) == 1, "id dupliqué : %s" % ident


def test_terminal_cw_visible_seulement_en_mode_cw():
    # Le terminal CW suit le mode CW dans updateKeyerPanels (comme les macros),
    # au lieu de rester `expert-only` visible en SSB.
    js = open(os.path.join(BASE, 'logx_logbook.js'), encoding='utf-8').read()
    i = js.index('function updateKeyerPanels')
    corps = js[i:i + 3000]
    assert "getElementById('cwTerminalPanel')" in corps, "le terminal CW doit être piloté par updateKeyerPanels"
    assert "cwTerm.style.display = cw ? '' : 'none'" in corps, "le terminal CW doit suivre le mode CW"
