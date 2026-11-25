// ─── CHAMPS PRÉ-REMPLIS : ILS APPARTIENNENT À UN INDICATIF ───────────────────
// Défaut mesuré (audit F4GLD du 25/11/2026) : le locator, le prénom et le
// département pré-remplis pour un correspondant RESTAIENT dans la saisie quand
// on tapait l'indicatif suivant — les remplisseurs n'écrivent que dans un
// champ vide, et rien ne le vidait. Le QSO suivant partait avec le locator ou
// le prénom d'une autre station, et le prénom était même recopié dans la base
// interne pour ce nouvel indicatif. Constaté dans le vrai carnet : EA7IXM
// enregistré en JN61SR (le locator d'IQ2AAH, loggé juste avant), « Björn
// Bieske » attribué à quatre indicatifs différents.
//
// RÈGLE : une valeur posée AUTOMATIQUEMENT est marquée avec l'indicatif pour
// lequel elle a été posée et la valeur posée. Quand l'indicatif change, elle
// est retirée — SEULEMENT si le champ contient toujours exactement cette
// valeur. Ce que l'opérateur a tapé ou corrigé lui-même n'est jamais effacé
// (même principe que logx_zone_auto.js pour la zone CQ).
//
// Hors chemin critique : sans ce fichier, la saisie fonctionne comme avant.

(function(global){
  'use strict';

  var CHAMPS = ['inputLocator', 'inputName', 'inputNumRcvd'];

  function _norm(call){ return String(call || '').trim().toUpperCase(); }

  // Pose une valeur automatique dans un champ et la rattache à `call`.
  function poser(el, valeur, call){
    if(!el) return;
    el.value = valeur;
    el.dataset.autoPour = _norm(call);
    el.dataset.autoValeur = String(el.value);   // tel qu'affiché (casse comprise)
  }

  // Le champ contient-il encore la valeur posée automatiquement ?
  function estAuto(el){
    return !!(el && el.dataset.autoValeur != null && String(el.value) === el.dataset.autoValeur);
  }

  function _oublier(el){
    delete el.dataset.autoPour;
    delete el.dataset.autoValeur;
  }

  // Indicatif courant = `call`. Retire les valeurs automatiques posées pour un
  // AUTRE indicatif. Renvoie la liste des champs vidés (pour les tests et pour
  // recalculer distance/cap quand le locator a été vidé).
  function purger(call){
    var c = _norm(call), vides = [];
    CHAMPS.forEach(function(id){
      var el = document.getElementById(id);
      if(!el || el.dataset.autoPour == null) return;
      if(el.dataset.autoPour === c) return;
      if(estAuto(el)){ el.value = ''; vides.push(id); }
      _oublier(el);              // valeur retouchée par l'opérateur : elle devient la sienne
    });
    if(vides.indexOf('inputLocator') >= 0 && typeof global.onLocatorInput === 'function'){
      try{ global.onLocatorInput(); }catch(e){}   // efface distance, cap, indice « [base] »
    }
    return vides;
  }

  global.LogxChampsAuto = {poser: poser, estAuto: estAuto, purger: purger, CHAMPS: CHAMPS};
})(typeof window !== 'undefined' ? window : this);
