// ─── Info sommet/parc au moment où l'opérateur tape une référence ─────────────
// Quand une réf d'activité (SOTA/POTA/WWFF/IOTA) est saisie — la sienne (MES
// RÉFÉRENCES) OU celle du correspondant qu'on chasse — on affiche DISCRÈTEMENT
// les infos de la base locale : « Scafell Pike · Lake District · 978 m · 10 pts ».
//
// GARDE-FOUS : lecture seule, hors-ligne (base bundlée, endpoint /activation_db/
// lookup), débounce, discret si réf inconnue ou base pas prête. Ne touche jamais
// à la saisie ni au chemin critique.

(function(global){
  'use strict';

  // Programmes disposant d'une base interrogeable par référence exacte.
  var PROGRAMMES = {SOTA: 1, POTA: 1, WWFF: 1, IOTA: 1, DFCF: 1};
  var _cache = {};   // program|ref -> entry (ou null), évite de re-interroger

  // Formate l'entrée en une ligne lisible. Pur (testable). Champs absents omis.
  function _fmt(entry){
    if(!entry) return '';
    var parts = [];
    if(entry.name) parts.push(entry.name);
    if(entry.region) parts.push(entry.region);
    if(entry.alt_m != null && entry.alt_m !== '') parts.push(entry.alt_m + ' m');
    if(entry.points != null && entry.points !== '') parts.push(entry.points + ' pts');
    return parts.join(' · ');
  }

  // Réf -> détails (Promise -> entry|null). Cache + tolérant réseau/base pas prête.
  function lookup(program, ref){
    program = (program || '').toUpperCase();
    ref = (ref || '').trim().toUpperCase();
    if(!ref || !PROGRAMMES[program]) return Promise.resolve(null);
    var key = program + '|' + ref;
    if(Object.prototype.hasOwnProperty.call(_cache, key)) return Promise.resolve(_cache[key]);
    return fetch('/activation_db/lookup?program=' + encodeURIComponent(program) +
                 '&ref=' + encodeURIComponent(ref))
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){ var e = (d && d.entry) || null; _cache[key] = e; return e; })
      .catch(function(){ return null; });
  }

  // Attache l'affichage à un champ de réf. getProgram : fonction -> code programme
  // (ex. la valeur d'un <select> voisin) ou chaîne fixe. infoEl : la cible à
  // remplir (masquée si rien). Débounce pour ne pas interroger à chaque touche.
  function attacher(inputEl, getProgram, infoEl){
    if(!inputEl || !infoEl) return;
    var deb = null;
    function maj(){
      var prog = (typeof getProgram === 'function') ? getProgram() : getProgram;
      lookup(prog, inputEl.value).then(function(e){
        var txt = _fmt(e);
        infoEl.textContent = txt;
        infoEl.hidden = !txt;
      });
    }
    inputEl.addEventListener('input', function(){
      if(deb) clearTimeout(deb);
      deb = setTimeout(maj, 450);
    });
    inputEl.addEventListener('change', maj);
    maj();   // état initial (si le champ est déjà rempli)
  }

  global.LogxRefInfo = { lookup: lookup, attacher: attacher, _fmt: _fmt };

})(typeof window !== 'undefined' ? window : this);
