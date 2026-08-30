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

  function _rendre(d){
    d = d || {};
    // SAISI = QSO tapés dans LogX (actionnables « ici, maintenant ») ; IMPORTÉ =
    // hérités d'un autre logiciel (source:'adif_import'), historique à revoir
    // sans urgence. Le serveur ventile ; repli sur les compteurs globaux pour un
    // serveur ancien (tout compté comme « saisi », importe = 0).
    var cs = d.counts_saisi || d.counts || {};
    var es = cs.erreur || 0, as = cs.attention || 0;
    var ns = (typeof d.qso_a_verifier_saisi === 'number') ? d.qso_a_verifier_saisi
           : ((typeof d.qso_a_verifier === 'number') ? d.qso_a_verifier : (es + as));
    var ni = (typeof d.qso_a_verifier_importe === 'number') ? d.qso_a_verifier_importe : 0;
    // Le fil IA ne pousse que l'ACTIONNABLE (saisis) — l'historique importé ne
    // doit pas le remplir.
    _pousserFil(ns);
    var b = document.getElementById('validationBadge');
    if(!b) return;
    if(!ns && !ni){ b.hidden = true; return; }   // rien nulle part
    b.hidden = false;
    if(ns){
      // Alarme sur les QSO SAISIS : rouge si vraie erreur, sinon jaune.
      b.classList.remove('vl-importe');
      b.classList.toggle('vl-erreur', es > 0);
      b.textContent = '⚠️ ' + ns + ' à vérifier' + (ni ? ' (+' + ni + ' importés)' : '');
      b.setAttribute('title', es + ' erreur(s) · ' + as + ' attention — ' + ns
        + ' QSO saisis à vérifier' + (ni ? ' · ' + ni + ' QSO importés à revoir (historique)' : '')
        + ' · cliquer pour ouvrir VÉRIFIER');
    } else {
      // Uniquement des importés : PAS d'alarme, rappel discret et neutre.
      b.classList.remove('vl-erreur');
      b.classList.add('vl-importe');
      b.textContent = ni + ' importés à revoir';
      b.setAttribute('title', ni + ' QSO importés portent un constat (historique) — cliquer pour ouvrir VÉRIFIER');
    }
  }

  function _maj(){
    fetch('/log/validate').then(function(r){ return r.json(); })
      .then(function(d){ _rendre(d); }).catch(function(){});
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
