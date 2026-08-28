// ─── HUD « OPPORTUNITÉS » du LOGBOOK (copilote IA, roadmap F4GLD) ─────────────
// La question « cette station vaut-elle un appel ? » a UNE SEULE vérité dans le
// programme : le moteur logx_chasse_priorite + logx_awards.annoter_credit, déjà
// exposé par /data/spots_ranked (score + « pourquoi », profil d'objectifs). Ce
// module NE RECALCULE RIEN — il ne fait que REMONTER ce classement dans le
// LOGBOOK (là où l'opérateur passe son temps, pas seulement dans CHASSE) et
// ajouter la seule vraie nouveauté : la séparation visuelle explicite des trois
// couches d'une opportunité —
//   FAIT       : données sourcées (cty.dat / spot)  — rien d'inventé ;
//   CALCUL     : la raison + le score du moteur déterministe ;
//   PROPOSITION: une action que L'OPÉRATEUR déclenche (jamais l'IA).
//
// GARDE-FOUS (doctrine F4GLD « l'IA prépare, l'humain déclenche ») : lecture
// seule sur le log, non-modal (repli natif <details>, ne vole pas le focus de la
// saisie), AUCUNE émission. « Appeler » = pré-remplir l'indicatif TOUJOURS, et
// QSY (réglage VFO, pas une émission) SEULEMENT si le CAT est branché.

(function(global){
  'use strict';

  var TOP_N = 5;
  var INTERVALLE_MS = 60000;   // même cadence que la NEED LIST de CHASSE
  var _timer = null;
  var _rig = false;            // CAT branché ? (dernier /rig/state connu)

  // Emoji de classe = MÊMES libellés que le badge crédit de CHASSE (cohérence
  // visuelle ; la classe/score, elle, vient du serveur — une seule vérité).
  var CLASSE_EMOJI = {
    atno: '🌟', new_band: '📻', new_mode: '🎚', new_grid: '🗺', needed_confirm: '📩'
  };

  function esc(s){
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  // Argument sûr pour un onclick="...('X')" : on ne garde que ce qui compose un
  // indicatif (un guillemet survivrait au décodage d'entité et casserait la
  // chaîne — piège XSS déjà documenté côté CHASSE via jsCall).
  function jsCall(v){ return String(v == null ? '' : v).replace(/[^A-Za-z0-9/]/g, ''); }

  // Ne garde que ce qui apporte quelque chose (credit_score > 0 : le doublon
  // confirmé a un score négatif, l'objectif désactivé un score 0 — tous deux
  // écartés du HUD), trie par score décroissant, coupe à TOP_N.
  function _filtrer(spots){
    return (spots || [])
      .filter(function(s){ return s && s.credit_score > 0; })
      .sort(function(a, b){ return b.credit_score - a.credit_score; })
      .slice(0, TOP_N);
  }

  // Une opportunité = un <details> (repli natif, accessible, 0 JS pour ouvrir) :
  // le <summary> montre emoji+indicatif+score, la fiche déplie les 3 couches.
  function _fiche(s){
    var cl = s.credit_classe || 'inconnu';
    var emoji = CLASSE_EMOJI[cl] || '•';
    var score = s.credit_score || 0;
    var fait = [s.dx_country, (s.band ? s.band + ' m' : ''), s.mode]
      .filter(function(x){ return x; }).map(esc).join(' · ');
    var calcul = esc(s.credit_raison || '') + ' → ' + esc(score);
    var freq = Number(s.freq) || 0;
    return '<details class="opp-row">' +
        '<summary class="opp-sum">' +
          '<span class="opp-emoji">' + emoji + '</span>' +
          '<span class="opp-call">' + esc(s.call) + '</span>' +
          '<span class="opp-score">' + esc(score) + '</span>' +
        '</summary>' +
        '<div class="opp-body">' +
          '<div class="opp-fait"><span class="opp-tag">FAIT</span>' + (fait || '—') + '</div>' +
          '<div class="opp-calc"><span class="opp-tag">CALCUL</span>' + calcul + '</div>' +
          '<div class="opp-prop"><span class="opp-tag">PROPOSITION</span>' +
            '<button type="button" class="opp-appeler" ' +
              "onclick=\"LogxOpportunites.appeler('" + jsCall(s.call) + "'," + freq + ')">' +
              '▶ Appeler</button>' +
          '</div>' +
        '</div>' +
      '</details>';
  }

  // Remplit le HUD. rigEnabled est mémorisé pour l'action « Appeler » (le QSY
  // n'est proposé QUE si le CAT est branché). Repli explicite si rien à montrer
  // (pas de vide muet — « masquer ≠ bande morte »).
  function _rendre(spots, rigEnabled){
    _rig = !!rigEnabled;
    var box = document.getElementById('opportunitesCorps');
    var top = _filtrer(spots);
    _pousserFil(top);                       // alimente le fil IA unifié (si présent)
    if(!box) return;
    if(!top.length){
      box.innerHTML = '<div class="opp-vide">Pas d\'opportunité en direct.</div>';
      return;
    }
    box.innerHTML = top.map(_fiche).join('');
  }

  // Alimente le fil IA unifié « Ce que l'IA remarque » avec le top 3 des
  // opportunités (proposition, action ▶ Appeler). Gardé : no-op si le fil n'est
  // pas chargé. Ne remplace pas ce panneau — il le complète.
  function _pousserFil(top){
    if(!global.LogxFilIA) return;
    var entrees = (top || []).slice(0, 3).map(function(s){
      var freq = Number(s.freq) || 0;
      return {icone: CLASSE_EMOJI[s.credit_classe] || '•',
              texte: (s.call || '') + ' — ' + (s.credit_raison || 'à travailler'),
              type: 'proposition',
              onclick: "LogxOpportunites.appeler('" + jsCall(s.call) + "'," + freq + ')'};
    });
    global.LogxFilIA.pousser('opportunites', entrees);
  }

  // Action « un clic utile » : pré-remplit TOUJOURS l'indicatif dans la saisie
  // QSO (et déclenche l'enrichissement existant via l'événement input), puis
  // QSY SEULEMENT si le CAT est branché. Jamais d'émission, jamais d'armement.
  function appeler(call, freqKhz){
    var inp = document.getElementById('inputCall');
    if(inp){
      inp.value = call;
      try{ if(inp.dispatchEvent) inp.dispatchEvent(new global.Event('input')); }catch(e){}
      if(inp.focus) inp.focus();
    }
    if(_rig && freqKhz){
      fetch('/rig/qsy', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({freq_khz: parseFloat(freqKhz)})
      }).catch(function(){});
    }
  }

  // Relit le classement (même endpoint que CHASSE) + l'état CAT, puis rend.
  function _maj(){
    var rig = fetch('/rig/state').then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){ return !!(d && d.enabled); }).catch(function(){ return false; });
    var spots = fetch('/data/spots_ranked').then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){ return (d && d.spots) || []; }).catch(function(){ return []; });
    Promise.all([spots, rig]).then(function(v){ _rendre(v[0], v[1]); });
  }

  function demarrer(){
    if(_timer) return;
    _maj();
    var poll = global.rcPoll || function(fn, ms){ return setInterval(fn, ms); };
    _timer = poll(_maj, INTERVALLE_MS);
  }

  // Masquer ≠ bloquer : on replie le CORPS (le poll continue en fond, la liste
  // se remontre au ré-affichage). L'en-tête reste visible pour pouvoir rouvrir.
  // Rien n'est désactivé.
  function basculer(){
    var c = document.getElementById('opportunitesCorps');
    if(c) c.hidden = !c.hidden;
  }

  global.LogxOpportunites = {
    demarrer: demarrer, appeler: appeler, basculer: basculer,
    _filtrer: _filtrer, _rendre: _rendre
  };

  // Démarrage auto au chargement du LOGBOOK. Conditionné à un VRAI navigateur
  // (fetch présent) pour ne pas lancer de poll dans les harnais de test V8/node.
  if(typeof document !== 'undefined' && typeof fetch === 'function'){
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', demarrer);
    else demarrer();
  }

})(typeof window !== 'undefined' ? window : this);
