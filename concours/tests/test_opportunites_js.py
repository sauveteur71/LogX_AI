# -*- coding: utf-8 -*-
"""HUD « Opportunités » du LOGBOOK (logx_opportunites.js) — testé en V8.

Le SCORE et le « pourquoi » sont calculés côté serveur (logx_chasse_priorite /
logx_awards.annoter_credit, exposés par /data/spots_ranked, testés ailleurs) :
ici on ne teste QUE la couche présentation propre à cette brique —
  - le tri/coupe (top-N par credit_score positif, doublon confirmé exclu) ;
  - la fiche au clic à trois couches FAIT / CALCUL / PROPOSITION ;
  - l'action « Appeler » : pré-remplit TOUJOURS l'indicatif, QSY SEULEMENT si CAT.
Aucun démarrage auto dans le harnais (pas de fetch) -> le module ne poll pas.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_opportunites.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var window = {};
      window.__filPush = [];
      window.LogxFilIA = { pousser: function(s, e){ window.__filPush.push({source: s, n: (e||[]).length}); } };
      var __hud = { innerHTML: '', hidden: false };
      var __call = { value: '', _focus: 0, focus: function(){ this._focus++; },
                     dispatchEvent: function(){ __call._dispatched = (__call._dispatched||0)+1; return true; } };
      var __fetches = [];
      function setInterval(){ return 0; }   // V8 n'a pas de boucle d'événements
      function Event(t){ this.type = t; }
      // Enregistre l'appel SYNCHRONE (avant de rendre la promesse) et retourne
      // une vraie Promise pour que le démarrage auto ne casse pas au chargement.
      function fetch(url, opts){ __fetches.push({url: url, opts: opts}); return Promise.resolve({ ok: true, json: function(){ return Promise.resolve(null); } }); }
      var document = { getElementById: function(id){
          if(id === 'opportunitesCorps') return __hud;
          if(id === 'inputCall') return __call;
          return null; },
        readyState: 'complete' };
    """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_filtre_trie_desc_et_coupe_a_cinq():
    ctx = _ctx()
    # Six positifs -> on garde les 5 plus forts, triés décroissant.
    ctx.eval("""window.__r = window.LogxOpportunites._filtrer([
      {call:'A', credit_score:600}, {call:'C', credit_score:1000},
      {call:'E', credit_score:450}, {call:'F', credit_score:500},
      {call:'G', credit_score:200}, {call:'H', credit_score:300}
    ]);""")
    scores = ctx.eval("window.__r.map(function(s){return s.credit_score;}).join(',')")
    assert scores == '1000,600,500,450,300'      # 5 max, tri desc, le 200 tombe


def test_filtre_ecarte_score_nul_et_negatif_meme_si_place():
    ctx = _ctx()
    # SEULEMENT 2 positifs, plus un score 0 (objectif désactivé) et un négatif
    # (doublon confirmé). La coupe à 5 ne les masque PAS ici : c'est bien le
    # FILTRE qui doit les écarter, sinon on afficherait un doublon comme une
    # opportunité. Contraint la propriété indépendamment du tri/coupe.
    ctx.eval("""window.__r = window.LogxOpportunites._filtrer([
      {call:'B', credit_score:0}, {call:'A', credit_score:600},
      {call:'D', credit_score:-900}, {call:'C', credit_score:1000}
    ]);""")
    calls = ctx.eval("window.__r.map(function(s){return s.call;}).join(',')")
    assert calls == 'C,A'                          # exactement les 2 positifs
    assert 'B' not in calls and 'D' not in calls   # 0 et doublon confirmé jamais montrés


def test_rendu_fiche_a_trois_couches():
    ctx = _ctx()
    ctx.eval("""window.LogxOpportunites._rendre([
      {call:'JA1XYZ', freq:14074, band:'20', mode:'FT8', dx_country:'Japan',
       credit_classe:'atno', credit_score:1000, credit_raison:'nouveau DXCC'}
    ], true);""")
    html = ctx.eval("__hud.innerHTML")
    # Les trois couches sont présentes et étiquetées
    assert 'FAIT' in html and 'CALCUL' in html and 'PROPOSITION' in html
    # FAIT = données sourcées (pays / bande / mode), rien d'inventé
    assert 'Japan' in html and '20' in html and 'FT8' in html
    # CALCUL = raison + score du moteur déterministe
    assert 'nouveau DXCC' in html and '1000' in html
    # PROPOSITION = bouton d'action qui appelle la brique (pas d'émission)
    assert 'LogxOpportunites.appeler' in html and 'JA1XYZ' in html


def test_rendu_vide_donne_un_repli():
    ctx = _ctx()
    ctx.eval("window.LogxOpportunites._rendre([], true);")
    assert 'opportunit' in ctx.eval("__hud.innerHTML").lower()  # message de repli, pas de vide brut


def test_rendu_echappe_le_call_xss():
    ctx = _ctx()
    ctx.eval("""window.LogxOpportunites._rendre([
      {call:'<img src=x onerror=1>', freq:0, band:'20', mode:'CW', dx_country:'X',
       credit_classe:'new_band', credit_score:600, credit_raison:'r'}], true);""")
    html = ctx.eval("__hud.innerHTML")
    assert '<img' not in html and '&lt;img' in html


def test_appeler_prefill_toujours_et_qsy_si_cat():
    ctx = _ctx()
    # CAT branché -> pré-remplit ET QSY
    ctx.eval("window.LogxOpportunites._rendre([{call:'F6ABC', freq:14074, band:'20', mode:'FT8', dx_country:'France', credit_classe:'new_mode', credit_score:500, credit_raison:'r'}], true);")
    ctx.eval("__fetches.length = 0;")   # ignore les fetch du démarrage auto
    ctx.eval("window.LogxOpportunites.appeler('F6ABC', 14074);")
    assert ctx.eval("__call.value") == 'F6ABC'
    fetches = ctx.eval("__fetches.map(function(f){return f.url;}).join('|')")
    assert '/rig/qsy' in fetches


def test_appeler_sans_cat_prefill_mais_pas_de_qsy():
    ctx = _ctx()
    # CAT NON branché -> pré-remplit SEULEMENT, aucune action radio
    ctx.eval("window.LogxOpportunites._rendre([{call:'F6ABC', freq:14074, band:'20', mode:'FT8', dx_country:'France', credit_classe:'new_mode', credit_score:500, credit_raison:'r'}], false);")
    ctx.eval("__fetches.length = 0;")   # ignore les fetch du démarrage auto
    ctx.eval("window.LogxOpportunites.appeler('F6ABC', 14074);")
    assert ctx.eval("__call.value") == 'F6ABC'          # indicatif saisi quand même
    assert ctx.eval("__fetches.length") == 0            # mais AUCUN /rig/qsy


def test_alimente_le_fil_ia():
    ctx = _ctx()
    ctx.eval("""window.LogxOpportunites._rendre([
      {call:'JA1XYZ', freq:14074, band:'20', mode:'FT8', dx_country:'Japon',
       credit_classe:'atno', credit_score:1000, credit_raison:'nouveau DXCC'}], true);""")
    # le module a poussé la source 'opportunites' au fil IA unifié
    poussees = ctx.eval("window.__filPush.filter(function(p){return p.source==='opportunites';}).length")
    assert poussees >= 1
    assert ctx.eval("window.__filPush[window.__filPush.length-1].n") >= 1


def test_basculer_replie_puis_reaffiche_le_corps():
    ctx = _ctx()
    assert ctx.eval("__hud.hidden") is False
    ctx.eval("window.LogxOpportunites.basculer();")
    assert ctx.eval("__hud.hidden") is True       # corps replié (mais rien désactivé)
    ctx.eval("window.LogxOpportunites.basculer();")
    assert ctx.eval("__hud.hidden") is False       # ré-affiché


def test_cablage_logbook():
    with open(os.path.join(CONCOURS, 'logx_logbook.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_opportunites.js"' in h
    assert 'id="opportunitesCorps"' in h
    assert 'LogxOpportunites' in h
