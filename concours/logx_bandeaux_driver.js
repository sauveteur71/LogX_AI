// ─── DRIVER des bandeaux défilants : branchement page + ⚙ afficher/masquer ───
// Le framework (logx_bandeaux.js) = mécanique PURE (registre, rendu, config).
// Les DEFS (logx_bandeaux_defs.js) = contenu. CE FICHIER branche une page :
// récupère les flux réels, rend les bandeaux ACTIFS (choix opérateur persisté),
// et pose un ⚙ « afficher/masquer » (chips par bandeau). Réutilisable : chaque
// page appelle LogxBandeauxDriver.brancher({...}). Une seule fonction publique.
//
// GARDE-FOUS (règles du dépôt) :
//  - Rien du chemin critique ici (bandeau = info AMBIANTE, secondaire).
//  - « masquer ≠ bloquer » : le ⚙ ne masque QUE l'affichage, les endpoints et
//    la config restent intacts (basculerBandeau ne touche que rc_bandeaux).
//  - « pas de bande morte » : bandeaux ACTIFS mais sans info live -> barre
//    CACHÉE. En revanche, si l'opérateur a TOUT masqué lui-même, un fin strip
//    ⚙ reste visible pour pouvoir réafficher (choix délibéré, pas une absence
//    de données) — les deux cas sont distincts.
//  - rcPoll (si présent) suspend le rafraîchissement sur onglet masqué.

(function(global){
  'use strict';

  function _LB(){ return global.LogxBandeaux; }

  // Récupère tous les flux déclarés (sources = {cleDonnees: url}) -> {cle: json}.
  // Un flux HS -> ce bandeau restera simplement vide, jamais de plantage.
  function _fetchSources(sources){
    var donnees = {};
    var cles = Object.keys(sources || {});
    return Promise.all(cles.map(function(cle){
      return fetch(sources[cle]).then(function(r){ return r.json(); })
        .then(function(j){ donnees[cle] = j; })
        .catch(function(){});
    })).then(function(){ return donnees; });
  }

  // HTML du ⚙ + panneau de chips (un bouton-bascule par bandeau DISPONIBLE sur
  // la page). L'état on/off vient de la config persistée (bandeauxActifs).
  function _reglageHtml(ids, activite, defauts){
    var LB = _LB();
    var actifs = LB.bandeauxActifs(activite, defauts);
    var esc = LB.esc;
    var chips = (ids || []).map(function(id){
      var def = LB.REGISTRE[id] || {};
      var on = actifs.indexOf(id) >= 0;
      return '<button type="button" class="rcb-chip' + (on ? ' on' : '') + '" data-bandeau="'
        + esc(id) + '" aria-pressed="' + (on ? 'true' : 'false') + '">'
        + esc(def.cat || id) + '</button>';
    }).join('');
    return '<div class="rcb-reglage">'
      + '<button type="button" class="rcb-gear" aria-label="Choisir les bandeaux à afficher"'
      + ' aria-expanded="false" title="Afficher / masquer les bandeaux">⚙</button>'
      + '<div class="rcb-chips" hidden>' + chips + '</div></div>';
  }

  function brancher(opts){
    opts = opts || {};
    var LB = _LB();
    var wrap = document.getElementById(opts.wrapId || 'bandeaux');
    if(!LB || !wrap) return;
    var activite = opts.activite || 'defaut';
    var ids = opts.ids || [];
    var defauts = opts.defauts || {};
    var interval = opts.intervalleMs || 120000;

    function panneauOuvert(){
      var c = wrap.querySelector('.rcb-chips');
      return !!(c && !c.hidden);
    }
    function ouvrirPanneau(){
      var g = wrap.querySelector('.rcb-gear'), c = wrap.querySelector('.rcb-chips');
      if(g && c){ c.hidden = false; g.setAttribute('aria-expanded', 'true'); }
    }

    function rendre(){
      var reouvrir = panneauOuvert();   // préserve l'ouverture à travers un re-rendu
      _fetchSources(opts.sources).then(function(donnees){
        var actifs = LB.bandeauxActifs(activite, defauts);
        var aff = ids.filter(function(id){ return actifs.indexOf(id) >= 0; });
        var reglage = _reglageHtml(ids, activite, defauts);
        if(aff.length === 0){
          // tout masqué par l'opérateur -> strip ⚙ (réactivation), pas de bande morte
          wrap.innerHTML = reglage + '<div class="rcb-vide">' + LB.esc('Bandeaux masqués') + '</div>';
          wrap.hidden = false;
        } else {
          var html = LB.rendreTicker(aff, { activite: activite, maintenant: Date.now() }, donnees);
          if(html){ wrap.innerHTML = reglage + html; wrap.hidden = false; }
          else { wrap.innerHTML = ''; wrap.hidden = true; }   // ON mais rien de live -> pas de bande morte
        }
        if(!wrap.hidden){
          _wire(wrap, activite, defauts, rendre);
          if(reouvrir) ouvrirPanneau();
        }
      });
    }

    // Fermeture du panneau au clic en dehors (posé UNE fois pour la page).
    if(!wrap._rcbOutside){
      wrap._rcbOutside = true;
      document.addEventListener('click', function(e){
        var c = wrap.querySelector('.rcb-chips');
        if(c && !c.hidden && !(e.target.closest && e.target.closest('.rcb-reglage'))){
          c.hidden = true;
          var g = wrap.querySelector('.rcb-gear'); if(g) g.setAttribute('aria-expanded', 'false');
        }
      });
    }

    rendre();
    var poll = global.rcPoll || function(fn, ms){ return setInterval(fn, ms); };
    poll(rendre, interval);
  }

  // (Re)câble le ⚙ et les chips. Appelé à chaque rendu : les nœuds sont recréés
  // (innerHTML réécrit), donc les écouteurs ne s'accumulent pas.
  function _wire(wrap, activite, defauts, rendre){
    var LB = _LB();
    var gear = wrap.querySelector('.rcb-gear');
    var chips = wrap.querySelector('.rcb-chips');
    if(gear && chips){
      gear.addEventListener('click', function(e){
        e.stopPropagation();
        var open = !chips.hidden;
        chips.hidden = open;
        gear.setAttribute('aria-expanded', String(!open));
      });
    }
    wrap.querySelectorAll('.rcb-chip').forEach(function(btn){
      btn.addEventListener('click', function(e){
        e.stopPropagation();
        LB.basculerBandeau(activite, btn.getAttribute('data-bandeau'), defauts);
        rendre();   // re-rend avec la nouvelle config (panneau ré-ouvert automatiquement)
      });
    });
  }

  global.LogxBandeauxDriver = { brancher: brancher };
  if(typeof module !== 'undefined' && module.exports) module.exports = global.LogxBandeauxDriver;

})(typeof window !== 'undefined' ? window : this);
