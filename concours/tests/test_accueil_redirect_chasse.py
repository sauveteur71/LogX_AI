# -*- coding: utf-8 -*-
"""Entrée directe depuis CHASSE (fusion incr. 5b, 11/09/2026) : quand
logx_accueil.html est chargée avec ?chasse=1 (destination prévue du futur
redirect de logx_chasse.html, incr. 5c — pas encore fait), elle doit
atterrir DIRECTEMENT sur les cibles en direct, sans passer par la grille
« Qu'est-ce que tu fais aujourd'hui ? » ni par les clics intermédiaires
(carte activité + tuile rôle) — doctrine « ne pas rallonger le chemin
quotidien ». Exécute le VRAI logx_accueil.js en V8 (py_mini_racer)."""
import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_accueil_activite import _make_ctx


def test_chasse_1_n_affiche_pas_la_grille_dactivite():
    ctx = _make_ctx(search='?chasse=1')
    html = ctx.eval("document.getElementById('intro').innerHTML")
    assert 'activity-grid' not in html
    assert 'Qu’est-ce que tu fais' not in html


def test_chasse_1_pose_lactivite_iota_pota():
    ctx = _make_ctx(search='?chasse=1')
    assert ctx.eval("localStorage.getItem('logx_activity')") == 'iota_pota'


def test_chasse_1_ne_redirige_pas():
    ctx = _make_ctx(search='?chasse=1')
    assert ctx.eval('__redirected') is None


def test_chasse_1_monte_les_panneaux_dactivation():
    """_revelerCiblesChasse() doit bien avoir tourné : mêmes conteneurs que
    le chemin _choisirRoleXota('chasse') (test_accueil_panneaux_4b)."""
    ctx = _make_ctx(search='?chasse=1')
    html = ctx.eval("document.getElementById('ciblesChasse').innerHTML")
    for cid in ('panPota', 'panSota', 'panWwff', 'panWca', 'panDx',
                'ckNeedList', 'xotaQsyStatus', 'objectifsList'):
        assert cid in html, cid


def test_chasse_1_force_le_role_portable_pur_vers_chasse():
    """Un rôle 'portable' pur (roleConfig.chasse == false) laisserait la
    need-list structurellement vide si on ne le corrigeait pas — vérifié en
    posant le rôle AVANT le chargement du script (comme localStorage
    préexistant d'une session précédente), nécessite de le poser AVANT le
    chargement du script -> contexte manuel plutôt que _make_ctx()."""
    import py_mini_racer as pmr
    from test_accueil_activite import _DOM_PREAMBLE, JS_PATH
    ctx2 = pmr.MiniRacer()
    ctx2.eval(_DOM_PREAMBLE)
    ctx2.eval("location.search = '?chasse=1';")
    ctx2.eval("localStorage.setItem('logx_xota_role', 'portable');")
    # Stub minimal de LogxXotaRole (le vrai module n'est pas chargé par ce
    # harnais V8 nu, comme les autres tests de ce fichier — cf. STUB_ROLE
    # dans test_accueil_panneaux_4b.py).
    ctx2.eval("""
        var _role = 'portable';
        var LogxXotaRole = {
            getRole: function(){ return _role; },
            setRole: function(r){ _role = r; localStorage.setItem('logx_xota_role', r); return r; },
            roleConfig: function(r){ return {chasse:(r==='chasse'||r==='mixte'), portable:(r==='portable'||r==='mixte')}; }
        };
        window.LogxXotaRole = LogxXotaRole;
    """)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx2.eval(f.read())
    assert ctx2.eval("window.LogxXotaRole.getRole()") == 'chasse'


def test_chasse_1_laisse_le_role_mixte_inchange():
    import py_mini_racer as pmr
    from test_accueil_activite import _DOM_PREAMBLE, JS_PATH
    ctx2 = pmr.MiniRacer()
    ctx2.eval(_DOM_PREAMBLE)
    ctx2.eval("location.search = '?chasse=1';")
    ctx2.eval("""
        var _role = 'mixte';
        var LogxXotaRole = {
            getRole: function(){ return _role; },
            setRole: function(r){ _role = r; return r; },
            roleConfig: function(r){ return {chasse:(r==='chasse'||r==='mixte'), portable:(r==='portable'||r==='mixte')}; }
        };
        window.LogxXotaRole = LogxXotaRole;
    """)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx2.eval(f.read())
    assert ctx2.eval("window.LogxXotaRole.getRole()") == 'mixte'


def test_expose_demarrer_depuis_redirect_chasse():
    ctx = _make_ctx()
    assert ctx.eval('typeof _demarrerDepuisRedirectChasse') == 'function'
