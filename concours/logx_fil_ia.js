// ─── Fil IA unifié : « Ce que l'IA remarque » ────────────────────────────────
// Un SEUL endroit qui agrège les observations de l'IA jusque-là éparpillées :
// opportunités à travailler, QSO à vérifier, gains du dernier QSO, indicatif
// peut-être busté. Chaque signal reste aussi affiché par son widget d'origine
// (v1 COMPLÈTE, ne remplace pas — réversible) ; ici on rassemble.
//
// Découplé : les modules sources APPELLENT LogxFilIA.pousser('source', entrées)
// quand ils recalculent leur état ; le fil fusionne, priorise et rend. Chaque
// entrée = { icone, texte, type: 'attention'|'proposition'|'info', onclick? }.
//
// GARDE-FOUS (doctrine F4GLD) : lecture seule, non-modal, caché si vide (zéro
// bruit) ; les actions réutilisent les fonctions existantes (propose-only,
// jamais d'émission) ; jamais sur le chemin critique.

(function(global){
  'use strict';

  var MAX = 6;
  var PRIO = {attention: 0, proposition: 1, info: 2};
  var _sources = {};

  function esc(s){
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Fusionne toutes les sources en une liste priorisée (attention → proposition
  // → info), plafonnée. Pur (testable).
  function _construire(){
    var all = [];
    for(var s in _sources){
      if(_sources.hasOwnProperty(s)){
        (_sources[s] || []).forEach(function(e){ if(e) all.push(e); });
      }
    }
    all.sort(function(a, b){
      var pa = PRIO[a.type]; var pb = PRIO[b.type];
      return (pa == null ? 9 : pa) - (pb == null ? 9 : pb);
    });
    return all.slice(0, MAX);
  }

  function _rendre(entrees){
    var panel = document.getElementById('filIaPanel');
    var corps = document.getElementById('filIaCorps');
    if(!corps) return;
    if(!entrees || !entrees.length){
      corps.innerHTML = '';
      if(panel) panel.hidden = true;         // caché si rien à dire (zéro bruit)
      return;
    }
    if(panel) panel.hidden = false;
    corps.innerHTML = entrees.map(function(e){
      // onclick vient d'un module SOURCE (de confiance) ; le texte, lui, est
      // toujours échappé.
      var oc = e.onclick ? (' onclick="' + e.onclick + '"') : '';
      var role = e.onclick ? ' role="button" tabindex="0"' : '';
      return '<div class="fil-item fil-' + esc(e.type || 'info') + '"' + oc + role + '>' +
        '<span class="fil-dot"></span>' +
        '<span class="fil-ico">' + (e.icone || '') + '</span>' +
        '<span class="fil-txt">' + esc(e.texte || '') + '</span>' +
        '</div>';
    }).join('');
  }

  // Une source dépose (ou remplace) ses entrées, puis on re-rend tout le fil.
  function pousser(source, entrees){
    if(!source) return;
    _sources[source] = entrees || [];
    _rendre(_construire());
  }

  // Masquer ≠ bloquer : replie le corps (les sources continuent d'alimenter).
  function basculer(){
    var c = document.getElementById('filIaCorps');
    if(c) c.hidden = !c.hidden;
  }

  global.LogxFilIA = {
    pousser: pousser, basculer: basculer, _construire: _construire, _rendre: _rendre
  };

})(typeof window !== 'undefined' ? window : this);
