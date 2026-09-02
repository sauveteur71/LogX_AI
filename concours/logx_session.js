// ─── Planificateur de session (CONSULTATIF) ──────────────────────────────────
// L'opérateur saisit ses contraintes (durée, objectif, mode, bandes, puissance)
// et l'IA propose un PLAN par créneaux avec des critères d'arrêt. C'est un
// CONSEIL : rien n'est déclenché, l'opérateur garde le contrôle de chaque QSY et
// de chaque émission. Le plan est affiché en texte (aucune action cliquable qui
// piloterait la radio).

(function(global){
  'use strict';

  function _num(v){ var n = parseFloat(v); return isFinite(n) ? n : undefined; }

  function _val(id){ var e = document.getElementById(id); return e ? String(e.value || '') : ''; }

  // Construit le payload envoyé au serveur depuis le formulaire. Pur (testable).
  function _payload(){
    var p = {};
    var d = _num(_val('sessDuree')); if(d) p.duree_min = d;
    var o = _val('sessObjectif').trim(); if(o) p.objectif = o;
    var m = _val('sessMode').trim(); if(m) p.mode = m;
    var b = _val('sessBandes').trim(); if(b) p.bandes = b;
    var pw = _num(_val('sessPuissance')); if(pw) p.puissance_w = pw;
    var cx = document.getElementById('sessContexte');
    p.avec_contexte = !!(cx && cx.checked);   // tenir compte des conditions réelles
    return p;
  }

  // Affiche le plan (texte, white-space:pre-wrap) ou un message d'erreur discret.
  // textContent -> jamais d'injection HTML.
  function _rendre(data){
    var el = document.getElementById('sessPlan');
    if(!el) return;
    if(data && data.plan){
      el.textContent = data.plan;
      if(el.classList) el.classList.remove('sess-err');
      return;
    }
    el.textContent = '⚠️ ' + ((data && data.error) || 'Plan indisponible.');
    if(el.classList) el.classList.add('sess-err');
  }

  var CLE = 'logx_session_prefs';
  var CHAMPS = ['sessDuree', 'sessObjectif', 'sessMode', 'sessBandes', 'sessPuissance'];

  // Mémorise les dernières contraintes (localStorage) pour ne pas les retaper.
  function _sauver(){
    try{
      if(!global.localStorage) return;
      var p = {};
      CHAMPS.forEach(function(id){ var e = document.getElementById(id); if(e) p[id] = e.value; });
      var cx = document.getElementById('sessContexte'); if(cx) p.sessContexte = !!cx.checked;
      global.localStorage.setItem(CLE, JSON.stringify(p));
    }catch(e){}
  }

  function _restaurer(){
    try{
      if(!global.localStorage) return;
      var raw = global.localStorage.getItem(CLE); if(!raw) return;
      var p = JSON.parse(raw) || {};
      CHAMPS.forEach(function(id){ var e = document.getElementById(id); if(e && p[id] != null) e.value = p[id]; });
      var cx = document.getElementById('sessContexte'); if(cx && p.sessContexte != null) cx.checked = !!p.sessContexte;
    }catch(e){}
  }

  function generer(){
    _sauver();
    var el = document.getElementById('sessPlan');
    if(el){ el.textContent = '⏳ Génération du plan…'; if(el.classList) el.classList.remove('sess-err'); }
    fetch('/session/plan', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(_payload())
    }).then(function(r){ return r.json(); }).then(_rendre)
      .catch(function(){ _rendre({error: 'Réseau indisponible.'}); });
  }

  global.LogxSession = { generer: generer, _payload: _payload, _rendre: _rendre,
                         _sauver: _sauver, _restaurer: _restaurer };

  // Restaure les dernières contraintes au chargement (vrai navigateur avec
  // localStorage ; le harnais de test V8 ne définit pas localStorage -> no-op).
  if(typeof document !== 'undefined' && global.localStorage){
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _restaurer);
    else _restaurer();
  }

})(typeof window !== 'undefined' ? window : this);
