# -*- coding: utf-8 -*-
"""Tâche #92 (15/08/2026) : à l'étape « 5. RADIO (PILOTAGE CAT) » de CONFIG,
proposer les postes déjà déclarés dans « 1. IDENTITÉ » (parc RADIOS, PR #86)
plutôt que de forcer une nouvelle saisie manuelle marque/modèle.

Vérifications statiques (regex sur le HTML+JS réels, même patron que
test_cat_proprietaire_dispatch.py) : la fonction de rendu des suggestions
existe, les deux conteneurs (radio 1 et radio 2/SO2R) sont bien dans le HTML,
l'ouverture de la section 'radio' les rafraîchit, et l'ensemble des marques
considérées « pilotables en CAT natif » reste synchronisé avec les marques
réellement proposées par cat_brand (icom/yaesu/kenwood/elecraft/xiegu) — si
une marque est ajoutée d'un côté sans l'autre, ce test doit casser plutôt que
laisser une incohérence silencieuse passer inaperçue."""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_HTML = os.path.join(BASE, 'logx_configuration.html')
CONFIG_JS = os.path.join(BASE, 'logx_configuration.js')


def _lire(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def _source_combinee():
    return _lire(CONFIG_HTML) + '\n' + _lire(CONFIG_JS)


def test_conteneurs_suggestions_presents_dans_le_html():
    html = _lire(CONFIG_HTML)
    assert 'id="catRadioSuggestions"' in html, (
        "Conteneur des suggestions pour la radio 1 introuvable dans catNativeFields")
    assert 'id="cat2RadioSuggestions"' in html, (
        "Conteneur des suggestions pour la radio 2 (SO2R) introuvable dans cat2NativeFields")


def test_ouverture_section_radio_rafraichit_les_suggestions():
    js = _lire(CONFIG_JS)
    m = re.search(r"function openCategoryPopup\(cat\)\{.*?\n\}", js, re.S)
    assert m, "openCategoryPopup() introuvable"
    assert "renderCatRadioSuggestions()" in m.group(0), (
        "openCategoryPopup() ne rafraîchit pas les suggestions à l'ouverture de la section radio")


def test_render_et_apply_definis_et_cohérents_avec_radiosrows():
    js = _lire(CONFIG_JS)
    assert 'function renderCatRadioSuggestions()' in js
    assert 'function applyRadioFromParc(radioId, target)' in js
    # Les deux fonctions doivent lire radiosRows (source de vérité du parc,
    # déjà utilisée par renderParcStation()) -- pas une copie locale qui
    # divergerait silencieusement si le parc change sans rechargement.
    m = re.search(r"function renderCatRadioSuggestions\(\)\{(.*?)\n\}", js, re.S)
    assert m and 'radiosRows' in m.group(1)
    m2 = re.search(r"function applyRadioFromParc\(radioId, target\)\{(.*?)\n\}", js, re.S)
    assert m2 and 'radiosRows' in m2.group(1)


def test_marques_cat_natives_synchronisees_avec_cat_brand():
    """CAT_NATIVE_BRANDS (utilisé pour décider quel poste du parc est
    cliquable) doit exactement couvrir les marques du <select id="cat_brand">
    -- sinon un poste réellement pilotable en CAT natif se retrouverait
    affiché comme non-cliquable (ou l'inverse : un clic sur une marque non
    supportée par cat_brand ne ferait rien de silencieusement cassé)."""
    src = _source_combinee()
    m_html = re.search(r'<select id="cat_brand"[^>]*>(.*?)</select>', src, re.S)
    assert m_html, "select cat_brand introuvable"
    marques_cat_brand = set(re.findall(r'<option value="([a-z]+)">', m_html.group(1)))

    m_js = re.search(r"const CAT_NATIVE_BRANDS = new Set\(\[(.*?)\]\)", src)
    assert m_js, "CAT_NATIVE_BRANDS introuvable dans logx_configuration.js"
    marques_natives = set(re.findall(r"'([a-z]+)'", m_js.group(1)))

    assert marques_natives == marques_cat_brand, (
        f"CAT_NATIVE_BRANDS ({marques_natives}) doit correspondre exactement "
        f"aux options de cat_brand ({marques_cat_brand})")


def test_marques_parc_non_natives_ont_une_explication():
    """PARC_MARQUES_RADIO contient 'flex'/'autre', absentes de CAT_NATIVE_BRANDS
    -- renderCatRadioSuggestions() doit expliquer pourquoi ces postes ne sont
    pas cliquables (pas de bouton muet)."""
    js = _lire(CONFIG_JS)
    m = re.search(r"function renderCatRadioSuggestions\(\)\{(.*?)\n\}", js, re.S)
    assert m
    corps = m.group(1)
    assert 'flex' in corps and 'raison' in corps, (
        "Le cas flex/autre (non pilotable en CAT natif) doit être expliqué, pas juste ignoré")
