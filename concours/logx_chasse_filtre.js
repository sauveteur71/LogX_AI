// ─── Filtre « Ce que je chasse » : CW / Phonie / Data + bandes ───────────────
// Demande F4GLD (28/10/2026) : sur la page CHASSE, choisir la famille de mode
// et les bandes sur lesquelles on veut des propositions.
//
// UNE seule vérité pour classer un spot : le SERVEUR (logx_chasse_filtre.py)
// annote `mode_cat` ('cw' | 'phonie' | 'data' | '') sur chaque spot de la
// need-list, de POTA, SOTA et WWFF. Ce module ne fait que COMPARER cette
// étiquette et la clé de bande (`band`, MHz, logx_scoring._band_from_freq) au
// choix de l'opérateur — aucune table de modes recopiée ici.
//
// Choix mémorisé dans le navigateur (confort par poste ; jamais bloquant :
// stockage indisponible -> « tout », la page fonctionne). Rien n'est désactivé
// côté serveur : masquer ≠ bloquer.

(function(global){
  'use strict';

  var CLE = 'logx_chasse_filtre';
  var CATS = [['cw', 'CW'], ['phonie', 'Phonie'], ['data', 'Data']];
  // Clés de bande telles que les produit logx_scoring._band_from_freq (seule
  // source des `band` reçus) ; le libellé en mètres vient de LogxBandeaux
  // (table LIB_BANDES, logx_bandeaux_defs.js) quand il est chargé.
  var BANDES = ['1.8', '3.5', '5', '7', '10.1', '14', '18', '21', '24', '28',
                '50', '70', '144', '432'];

  var _etat = {bandes: [], cats: []};
  var _hote = null, _surChange = null;

  function _lire(){
    try{
      var v = JSON.parse(global.localStorage.getItem(CLE) || 'null');
      if(v && Array.isArray(v.bandes) && Array.isArray(v.cats)){
        _etat = {bandes: v.bandes.filter(function(b){ return BANDES.indexOf(b) >= 0; }),
                 cats: v.cats.filter(function(c){ return CATS.some(function(x){ return x[0] === c; }); })};
      }
    }catch(e){}
    return _etat;
  }
  function _ecrire(){ try{ global.localStorage.setItem(CLE, JSON.stringify(_etat)); }catch(e){} }

  function libBande(b){
    var LB = global.LogxBandeaux;
    if(LB && typeof LB.libBande === 'function') return LB.libBande(b);
    return b + ' MHz';
  }

  // Le spot correspond-il au choix ? (choix vide = pas de filtre). Un spot de
  // famille inconnue est écarté dès qu'une famille est choisie — même règle
  // que le serveur (logx_chasse_filtre.garder).
  function garder(s, etat){
    etat = etat || _etat;
    if(!s) return false;
    if(etat.bandes.length && etat.bandes.indexOf(String(s.band == null ? '' : s.band)) < 0) return false;
    if(etat.cats.length && etat.cats.indexOf(s.mode_cat || '') < 0) return false;
    return true;
  }
  function filtrer(spots, etat){
    return (spots || []).filter(function(s){ return garder(s, etat); });
  }
  // Paramètres pour /data/spots_ranked (filtré AVANT la coupe côté serveur).
  function requete(etat){
    etat = etat || _etat;
    var p = [];
    if(etat.bandes.length) p.push('bands=' + encodeURIComponent(etat.bandes.join(',')));
    if(etat.cats.length) p.push('modes=' + encodeURIComponent(etat.cats.join(',')));
    return p.length ? '?' + p.join('&') : '';
  }
  function actif(){ return !!(_etat.bandes.length || _etat.cats.length); }

  function _puce(groupe, val, lib, on){
    return '<button type="button" class="cf-puce' + (on ? ' on' : '') + '" aria-pressed="' + (on ? 'true' : 'false') +
           '" data-g="' + groupe + '" data-v="' + val + '">' + lib + '</button>';
  }
  function _rendre(){
    if(!_hote) return;
    var toutMode = !_etat.cats.length, toutBande = !_etat.bandes.length;
    _hote.innerHTML =
      '<div class="cf-ligne"><span class="cf-lbl">MODE</span>' +
        _puce('cat', '*', 'Tous', toutMode) +
        CATS.map(function(c){ return _puce('cat', c[0], c[1], _etat.cats.indexOf(c[0]) >= 0); }).join('') +
      '</div>' +
      '<div class="cf-ligne"><span class="cf-lbl">BANDES</span>' +
        _puce('bande', '*', 'Toutes', toutBande) +
        BANDES.map(function(b){ return _puce('bande', b, libBande(b), _etat.bandes.indexOf(b) >= 0); }).join('') +
      '</div>' +
      '<div class="cf-note">' + (actif()
        ? 'Filtre actif sur la need-list, POTA, SOTA et WWFF. Les annonces WCA/COTA et les DXpéditions ne sont pas filtrées (pas de fréquence).'
        : 'Plusieurs choix possibles. Rien de coché = tout est proposé.') + '</div>';
  }

  // Clic sur une puce : bascule la valeur ; « Tous/Toutes » vide le groupe.
  function _clic(ev){
    var t = ev.target && ev.target.closest ? ev.target.closest('.cf-puce') : null;
    if(!t) return;
    var g = t.getAttribute('data-g'), v = t.getAttribute('data-v');
    var liste = (g === 'cat') ? _etat.cats : _etat.bandes;
    if(v === '*') liste.length = 0;
    else {
      var i = liste.indexOf(v);
      if(i >= 0) liste.splice(i, 1); else liste.push(v);
    }
    _ecrire(); _rendre();
    if(typeof _surChange === 'function') _surChange(_etat);
  }

  function monter(hote, surChange){
    _hote = hote; _surChange = surChange;
    _lire(); _rendre();
    if(hote && hote.addEventListener) hote.addEventListener('click', _clic);
  }

  global.LogxChasseFiltre = {
    monter: monter, garder: garder, filtrer: filtrer, requete: requete,
    actif: actif, etat: function(){ return _etat; }, _lire: _lire, _clic: _clic,
    BANDES: BANDES
  };
})(typeof window !== 'undefined' ? window : this);
