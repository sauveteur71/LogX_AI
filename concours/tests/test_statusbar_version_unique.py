# -*- coding: utf-8 -*-
"""Refonte barre cockpit — LOT 1 : dédup de la version.

Retour F4GLD (27/08/2026) : « le tag v1.2-beta1 apparaît à la fois tout en haut
ET au milieu de la barre de sous-menus ». Le tag de version installée
(`#rcsbVersionItem`, « 🏷️ v… ») encombrait la sous-barre au milieu des
actions. On le retire : la version reste découvrable via le popup « mise à jour »
(`version actuelle`), le rapport de bug (version auto-incluse) et l'en-tête
LOGBOOK — voir spec docs/superpowers/specs/2026-08-27-refonte-barre-statut-cockpit-design.md.

À NE PAS confondre avec `#rcsbUpdateItem` (le popup « nouvelle version
disponible ») que F4GLD veut GARDER (capture #1) — d'où le garde-fou explicite
ci-dessous qui vérifie qu'il est toujours là.

Assertions STRUCTURELLES ciblant l'attribut `id="…"` / la clé `id:'…'` du
registre, pas une présence de chaîne brute — un commentaire mentionnant le nom
ne les satisfait donc pas.
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(BASE, 'logx_statusbar.js')


def _src():
    with open(JS, encoding='utf-8') as f:
        return f.read()


def test_item_version_installee_retire_de_la_barre():
    src = _src()
    assert not re.search(r'id="rcsbVersionItem"', src), \
        "l'item version installée doit être retiré de la sous-barre"
    # L'élément de valeur associé disparaît aussi (plus d'orphelin dans le HTML).
    assert not re.search(r'id="rcsbVersion"', src), \
        "le span de valeur de version doit être retiré du HTML de la barre"


def test_entree_du_menu_affichage_retiree():
    src = _src()
    assert not re.search(r"id:\s*'rcsbVersionItem'", src), \
        "l'entrée AFFICHAGE de la version installée doit être retirée du registre"


def test_le_popup_mise_a_jour_est_conserve():
    """Garde-fou : NE PAS retirer le popup « nouvelle version disponible »
    (#rcsbUpdateItem), que F4GLD veut garder (capture #1)."""
    src = _src()
    assert re.search(r'id="rcsbUpdateItem"', src), \
        "le popup de mise à jour doit rester présent"
