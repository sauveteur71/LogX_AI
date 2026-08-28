// ─── Validation LIVE et discrète du log (copilote IA, roadmap F4GLD) ──────────
// Le log a déjà un validateur DÉTERMINISTE riche (logx_validator.py : doublons,
// indicatif/cty.dat, locator/distance, département REF, cohérence freq/bande/
// date/RST/mode) exposé par /log/validate, et un panneau VÉRIFIER (showValidation).
// Mais tout était À LA DEMANDE. Ce module passe au « copilote vivant » : il
// repasse le log au crible après chaque QSO + en veille légère, et signale
// DISCRÈTEMENT (un badge dans l'en-tête, caché si tout est propre) le nombre de
// QSO à vérifier — cliquable pour ouvrir VÉRIFIER dessus.
//
// GARDE-FOUS (vision F4GLD « l'IA propose, l'opérateur décide ») : lecture seule,
// JAMAIS de correction automatique ; non-intrusif (aucun popup, badge caché quand
// rien à signaler) ; réutilise le validateur existant (aucune règle réinventée).

(function(global){
  'use strict';

  var _timer = null;
  var _debounce = null;
  var INTERVALLE_MS = 60000;   // veille légère (le validateur tourne aussi après chaque QSO)

  // Met à jour le badge depuis les compteurs de /log/validate. Caché si aucune
  // erreur NI attention (pas de bruit sur un log propre).
  // Alimente le fil IA unifié (si présent) : « N QSO à vérifier » (attention),
  // clic -> ouvre VÉRIFIER. Vide -> retire l'entrée. No-op si le fil est absent.
  function _pousserFil(n){
    if(!global.LogxFilIA) return;
    var entrees = n ? [{icone: '⚠️', texte: n + ' QSO à vérifier', type: 'attention',
                        onclick: 'LogxValidationLive.ouvrir()'}] : [];
    global.LogxFilIA.pousser('validation', entrees);
  }

  function _rendre(counts){
    var e = (counts && counts.erreur) || 0;
    var a = (counts && counts.attention) || 0;
    _pousserFil(e + a);
    var b = document.getElementById('validationBadge');
    if(!b) return;
    if(!e && !a){ b.hidden = true; return; }
    b.hidden = false;
    b.classList.toggle('vl-erreur', e > 0);   // rouge si vraie erreur, sinon jaune (attention)
    var n = e + a;
    b.textContent = '⚠️ ' + n + ' à vérifier';
    b.setAttribute('title', e + ' erreur(s) · ' + a + ' à vérifier — cliquer pour ouvrir VÉRIFIER');
  }

  function _maj(){
    fetch('/log/validate').then(function(r){ return r.json(); })
      .then(function(d){ _rendre(d && d.counts); }).catch(function(){});
  }

  // Après une rafale de QSO, une SEULE validation (debounce).
  function rafraichir(){
    if(_debounce) clearTimeout(_debounce);
    _debounce = setTimeout(_maj, 800);
  }

  function demarrer(){
    if(_timer) return;
    _maj();
    var poll = global.rcPoll || function(fn, ms){ return setInterval(fn, ms); };
    _timer = poll(_maj, INTERVALLE_MS);
  }

  // Clic sur le badge -> ouvre le panneau VÉRIFIER existant (aucune correction
  // auto : l'opérateur voit et décide).
  function ouvrir(){
    if(typeof global.showValidation === 'function') global.showValidation();
  }

  global.LogxValidationLive = {
    rafraichir: rafraichir, demarrer: demarrer, ouvrir: ouvrir, _rendre: _rendre
  };

  // Démarrage auto au chargement du LOGBOOK (veille légère). Badge caché tant
  // que rien à signaler -> zéro bruit pour un log propre. Conditionné à un VRAI
  // navigateur (fetch présent) pour ne pas casser les harnais de test V8/node.
  if(typeof document !== 'undefined' && typeof fetch === 'function'){
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', demarrer);
    else demarrer();
  }

})(typeof window !== 'undefined' ? window : this);
