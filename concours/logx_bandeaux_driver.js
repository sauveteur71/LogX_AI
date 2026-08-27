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

  // Ouvre le panneau de chips vers le HAUT si la barre est près du bas de
  // l'écran (sinon le menu sortirait sous le viewport — cas de l'accueil, barre
  // en bas de page). Sinon vers le bas (défaut, barres en haut : logbook/chasse).
  function _placerPanneau(wrap, chips){
    if(!chips || typeof global.innerHeight !== 'number') return;
    var r = wrap.getBoundingClientRect();
    chips.classList.toggle('rcb-chips-haut', (global.innerHeight - r.bottom) < 160);
  }

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
    var ids = opts.ids || [];
    var defauts = opts.defauts || {};
    var interval = opts.intervalleMs || 120000;

    function panneauOuvert(){
      var c = wrap.querySelector('.rcb-chips');
      return !!(c && !c.hidden);
    }
    function ouvrirPanneau(){
      var g = wrap.querySelector('.rcb-gear'), c = wrap.querySelector('.rcb-chips');
      if(g && c){ c.hidden = false; g.setAttribute('aria-expanded', 'true'); _placerPanneau(wrap, c); }
    }

    function rendre(){
      var reouvrir = panneauOuvert();   // préserve l'ouverture à travers un re-rendu
      // Activité COURANTE, résolue à CHAQUE rendu : opts.activite peut être une
      // FONCTION -> le contexte évolue en cours de session (ex. un concours qui
      // démarre bascule en 'concours' même en activité VHF, faisant apparaître
      // le bandeau MULTS ; il disparaît quand le concours s'arrête).
      var act = (typeof opts.activite === 'function') ? (opts.activite() || 'defaut') : (opts.activite || 'defaut');
      // Contexte de DISPONIBILITÉ (tags : classe de bande hf/vhf + 'concours'),
      // DISTINCT de la clé de config `act`. opts.tags peut être une FONCTION
      // (contexte évolutif : concours qui démarre, changement de bande). Sans
      // tags -> [act] (rétro-compat : le contexte est l'activité elle-même).
      var tags = (typeof opts.tags === 'function') ? opts.tags() : opts.tags;
      if(!tags) tags = [act];
      // ADAPTATION : ne garder que les bandeaux qui ONT UN SENS pour ce contexte
      // (leur `contextes`). Un bandeau hors-contexte ne s'affiche pas et n'est
      // pas proposé dans le ⚙ (ex. propag HF en VHF, MULTS hors concours).
      var dispo = LB.bandeauxAffichables(ids, tags);
      var actifs = LB.bandeauxActifs(act, defauts);
      var aff = dispo.filter(function(id){ return actifs.indexOf(id) >= 0; });
      // Ne récupère QUE les flux nécessaires aux bandeaux AFFICHÉS : un bandeau
      // masqué ne doit pas déclencher son fetch (ex. /data/spots_ranked, lourd).
      // besoins = {id:[clesSource]} ; sans déclaration -> tous les flux (rétro-compat).
      var sources = opts.sources || {};
      var aFetch = sources;
      if(opts.besoins){
        aFetch = {};
        aff.forEach(function(id){
          (opts.besoins[id] || []).forEach(function(k){ if(sources[k]) aFetch[k] = sources[k]; });
        });
      }
      _fetchSources(aFetch).then(function(donnees){
        // ADAPTATION bande/mode : la page fournit sa bande/mode COURANTS via une
        // fonction (valeurs fraîches à chaque rendu). Protégé : une page sans
        // contexte, ou une globale pas encore prête, ne casse rien.
        var extra = {};
        try { if(typeof opts.contexte === 'function') extra = opts.contexte() || {}; } catch(e){}
        var reglage = _reglageHtml(dispo, act, defauts);   // chips = bandeaux de l'activité courante
        if(aff.length === 0){
          // aff vide : strip ⚙ de réactivation SEULEMENT si l'opérateur RÈGLE
          // (panneau ouvert) ou a EXPLICITEMENT tout masqué (config persistée),
          // ET qu'il reste des bandeaux à réactiver. Sinon (vide par DÉFAUT ou
          // par CONTEXTE — ex. VHF hors concours : rien de dispo/actif) -> cacher,
          // pas de strip « Bandeaux masqués » parasite.
          if(dispo.length && (reouvrir || LB.aReglageActivite(act))){
            wrap.innerHTML = reglage + '<div class="rcb-vide">' + LB.esc('Bandeaux masqués') + '</div>';
            wrap.hidden = false;
          } else {
            wrap.innerHTML = ''; wrap.hidden = true;
          }
        } else {
          var html = LB.rendreTicker(aff, { activite: act, maintenant: Date.now(), band: extra.band, mode: extra.mode }, donnees);
          if(html){ wrap.innerHTML = reglage + html; wrap.hidden = false; }
          else if(reouvrir){
            // Opérateur EN TRAIN DE RÉGLER (panneau ⚙ ouvert) : garder le ⚙
            // accessible même si les bandeaux actifs n'ont rien de live —
            // sinon la barre disparaîtrait et il ne pourrait plus rien
            // réactiver (piège : ⚙ inatteignable).
            wrap.innerHTML = reglage + '<div class="rcb-vide">' + LB.esc('Aucune info en direct') + '</div>';
            wrap.hidden = false;
          }
          else { wrap.innerHTML = ''; wrap.hidden = true; }   // ON mais rien de live, pas en réglage -> pas de bande morte
        }
        if(!wrap.hidden){
          _wire(wrap, act, defauts, rendre);
          if(reouvrir) ouvrirPanneau();
        }
      });
    }

    // Fermeture du panneau (posée UNE fois pour la page) : clic en dehors, ET
    // Échap qui ferme + rend le focus au ⚙ (motif disclosure accessible du dépôt).
    if(!wrap._rcbOutside){
      wrap._rcbOutside = true;
      function _fermer(rendreFocus){
        var c = wrap.querySelector('.rcb-chips');
        if(c && !c.hidden){
          c.hidden = true;
          var g = wrap.querySelector('.rcb-gear');
          if(g){ g.setAttribute('aria-expanded', 'false'); if(rendreFocus) g.focus(); }
        }
      }
      document.addEventListener('click', function(e){
        if(!(e.target.closest && e.target.closest('.rcb-reglage'))) _fermer(false);
      });
      document.addEventListener('keydown', function(e){
        if(e.key === 'Escape') _fermer(true);
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
        if(!open) _placerPanneau(wrap, chips);   // sens d'ouverture selon la place
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
