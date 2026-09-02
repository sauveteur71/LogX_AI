// ─── Nudges du coach → fil IA unifié ─────────────────────────────────────────
// Le coach de trafic (déterministe) émet ÉVÉNEMENTIELLEMENT un nudge d'action
// « maintenant » pendant un concours : entité jamais faite ET spottée (la bande
// est ouverte), effondrement du rythme, ou silence radio prolongé. Ce petit
// module poll /coach/state?nudges=1 et alimente le fil « Ce que l'IA remarque »
// avec ce nudge (5e signal). Hors concours, coach_nudge renvoie None -> rien.
//
// Découplé et non-intrusif : lecture seule, no-op si le fil n'est pas chargé,
// ne touche pas la barre de statut.

(function(global){
  'use strict';

  var _timer = null;

  // Traduit le nudge coach ({level:'action'|'attention', text}) en entrée de fil.
  // Pur (testable). Rien si pas de nudge.
  function _entree(nudge){
    if(!nudge || !nudge.text) return [];
    var action = nudge.level === 'action';
    return [{
      icone: action ? '🎯' : '⏱',
      texte: nudge.text,
      type: action ? 'proposition' : 'attention'
    }];
  }

  function _maj(){
    fetch('/coach/state?nudges=1').then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        if(global.LogxFilIA) global.LogxFilIA.pousser('coach', _entree(d && d.nudge));
      }).catch(function(){});
  }

  function demarrer(){
    if(_timer) return;
    _maj();
    var poll = global.rcPoll || function(fn, ms){ return setInterval(fn, ms); };
    _timer = poll(_maj, 60000);   // même cadence que le coach
  }

  global.LogxCoachFil = { demarrer: demarrer, _entree: _entree, _maj: _maj };

  if(typeof document !== 'undefined' && typeof fetch === 'function'){
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', demarrer);
    else demarrer();
  }

})(typeof window !== 'undefined' ? window : this);
