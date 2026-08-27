# -*- coding: utf-8 -*-
"""Pilote bandeau défilant sur CHASSE — câblage page (structure, pas mannequin).

Le MOTEUR (rendreTicker, dxped/propag) est déjà testé en V8 (test_bandeaux*.py).
Ici on vérifie que la page CHASSE est réellement BRANCHÉE dessus : framework +
defs chargés AVANT le script de page, conteneur présent, et un driver dédié qui
rend dxped+propag depuis les DEUX endpoints live. Une régression silencieuse
(script retiré, appel supprimé) doit rougir.
"""
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_chasse.html')


def _lire():
    with open(HTML, encoding='utf-8') as f:
        return f.read()


def test_charge_framework_et_defs_avant_le_script_de_page():
    h = _lire()
    i_fw = h.find('src="logx_bandeaux.js"')
    i_defs = h.find('src="logx_bandeaux_defs.js"')
    assert i_fw != -1 and i_defs != -1        # framework + defs présents
    # Le driver vit dans le <script> inline de fin de page : les includes des
    # scripts externes doivent le précéder (window.LogxBandeaux défini avant usage).
    i_inline = h.rfind('<script>')
    assert i_inline != -1
    assert i_fw < i_inline and i_defs < i_inline


def test_a_le_conteneur_bandeau():
    assert re.search(r'id="bandeaux"', _lire())


def test_driver_rend_dxped_et_propag_depuis_les_deux_flux():
    h = _lire()
    m = re.search(r'function _chargerBandeauxChasse\(\).*?\n\}', h, re.S)
    assert m, "driver _chargerBandeauxChasse introuvable"
    corps = m.group(0)
    assert 'rendreTicker' in corps                          # rend via le framework
    assert "'dxped'" in corps and "'propag'" in corps       # les 2 bandeaux universels
    assert '/data/dxpeditions_active' in corps              # alimenté par les 2 vrais flux
    assert '/data/propagation' in corps


def test_clic_item_actif_ouvre_une_fiche():
    """Un item ACTIF du bandeau (data-fiche) ouvre une fiche popup au clic :
    handler de clic DÉLÉGUÉ sur #bandeaux + openFicheModal agrégeant l'info
    live du cluster, le nom (/calldb/lookup) et un lien direct QRZ.com."""
    h = _lire()
    assert 'function openFicheModal' in h
    assert "addEventListener('click'" in h                  # clic délégué (pas d'onclick inline par item)
    assert 'rcb-item' in h and 'data-fiche' in h            # cible les items actifs cliquables
    assert 'closest' in h                                   # remonte au <a> depuis la cible du clic
    assert 'qrz.com/db/' in h                               # « toutes les infos QRZ.com »
    assert '/calldb/lookup/' in h                           # nom de l'opérateur
    assert 'closeFiche' in h                                # fermeture du popup


def test_driver_est_reellement_appele():
    """Défini ne suffit pas : le driver doit être INVOQUÉ (poll rcPollOr ou
    appel direct), sinon le bandeau ne s'affiche jamais bien que tout existe."""
    h = _lire()
    # une invocation hors de sa propre définition (rcPollOr(_chargerBandeauxChasse
    # ...) ou _chargerBandeauxChasse();)
    sans_def = re.sub(r'function _chargerBandeauxChasse\(\).*?\n\}', '', h, flags=re.S)
    assert '_chargerBandeauxChasse' in sans_def, \
        "_chargerBandeauxChasse doit être appelé quelque part, pas seulement défini"
