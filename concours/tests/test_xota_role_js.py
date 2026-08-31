# -*- coding: utf-8 -*-
"""Mode de session XOTA (logx_xota_role.js) — chasseur / portable / les deux.

Logique PURE testée en V8 : mémorisation du dernier rôle (localStorage), et
roleConfig(role) qui pilote ce qui s'allume dans le logbook. Le câblage DOM
(tuiles accueil, bascule) est vérifié à part.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_xota_role.js')


def _ctx(initial=None):
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    store = ('{"%s":"%s"}' % ('logx_xota_role', initial)) if initial else '{}'
    # Pas de `window` -> le module s'attache au global réel (this), accès bare
    # LogxXotaRole (patron du dépôt). localStorage en global.
    c.eval("""
      var __ls = %s;
      var localStorage = {
        getItem:function(k){ return (k in __ls) ? __ls[k] : null; },
        setItem:function(k,v){ __ls[k] = String(v); } };
    """ % store)
    with open(JS, encoding='utf-8') as f:
        c.eval(f.read())
    return c


def test_defaut_mixte_sans_choix():
    assert _ctx().eval("LogxXotaRole.getRole()") == 'mixte'


def test_memorise_le_dernier_role():
    c = _ctx()
    c.eval("LogxXotaRole.setRole('chasse')")
    assert c.eval("LogxXotaRole.getRole()") == 'chasse'
    # relire depuis le store persiste (nouvelle lecture)
    assert c.eval("localStorage.getItem('logx_xota_role')") == 'chasse'


def test_role_invalide_retombe_sur_defaut():
    c = _ctx()
    assert c.eval("LogxXotaRole.normaliser('nimportequoi')") is None
    assert c.eval("LogxXotaRole.setRole('xxx')") == 'mixte'   # écrit le défaut


def test_normalisation_casse_et_espaces():
    c = _ctx()
    assert c.eval("LogxXotaRole.normaliser('  PORTABLE ')") == 'portable'


def test_roleconfig_chasse():
    c = _ctx()
    assert c.eval("LogxXotaRole.roleConfig('chasse').chasse") is True
    assert c.eval("LogxXotaRole.roleConfig('chasse').portable") is False


def test_roleconfig_portable():
    c = _ctx()
    assert c.eval("LogxXotaRole.roleConfig('portable').chasse") is False
    assert c.eval("LogxXotaRole.roleConfig('portable').portable") is True


def test_roleconfig_mixte_allume_les_deux():
    c = _ctx()
    assert c.eval("LogxXotaRole.roleConfig('mixte').chasse") is True
    assert c.eval("LogxXotaRole.roleConfig('mixte').portable") is True


def test_getrole_relit_le_choix_precedent():
    # Mémoire entre sessions : un store pré-rempli est respecté.
    assert _ctx('portable').eval("LogxXotaRole.getRole()") == 'portable'


def test_libelle_portable_pas_activateur():
    # Vocabulaire du dépôt : « Portable », jamais « Activateur » en visible.
    c = _ctx()
    labels = c.eval("LogxXotaRole.ROLES.map(function(r){return r.label}).join('|')")
    assert 'Activateur' not in labels and 'Portable' in labels and 'Chasseur' in labels


def _lire(nom):
    return open(os.path.join(CONCOURS, nom), encoding='utf-8').read()


def test_cablage_logbook():
    """Le logbook charge le module, expose la bascule, et chaserModeActif est
    piloté par le rôle (pas seulement l'ancien chaser_mode)."""
    html = _lire('logx_logbook.html')
    assert 'src="logx_xota_role.js"' in html
    assert 'id="xotaRoleSwitch"' in html
    js = _lire('logx_logbook.js')
    # chaserModeActif consulte le rôle XOTA
    i = js.index('function chaserModeActif(')
    corps = js[i:js.index('\n}', i)]
    assert 'LogxXotaRole' in corps and 'roleConfig' in corps
    # bascule 1-geste présente et re-applique la visibilité
    assert 'function basculerRoleXota(' in js and 'renderXotaRoleSwitch(' in js


def test_cablage_accueil():
    """L'accueil charge le module et rend la section de choix de rôle."""
    html = _lire('logx_accueil.html')
    assert 'src="logx_xota_role.js"' in html
    js = _lire('logx_accueil.js')
    assert 'id="xotaRoleAccueil"' in js and '_renderXotaRoleAccueil(' in js
    assert '_choisirRoleXota(' in js
