// ─── Provenance par champ ────────────────────────────────────────────────────
// Pour la confiance : d'où vient chaque donnée enrichie de l'indicatif en cours
// de saisie. Un petit relevé (Pays · cty.dat, Distance · calculé…) sous la zone
// d'enrichissement. LECTURE SEULE, non-intrusif : écoute la frappe de l'indicatif
// (débounce), ne touche NI aux champs de saisie NI au chemin critique.

(function(global){
  'use strict';

  var _deb = null;

  function esc(s){
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  function _rendre(rows){
    var el = document.getElementById('provenancePanel');
    if(!el) return;
    rows = rows || [];
    if(!rows.length){ el.hidden = true; el.innerHTML = ''; return; }
    el.hidden = false;
    el.innerHTML = '<div class="prov-h">Provenance</div>' + rows.map(function(r){
      return '<div class="prov-row">' +
        '<span class="prov-c">' + esc(r.champ) + '</span>' +
        '<span class="prov-v">' + esc(r.valeur) + '</span>' +
        '<span class="prov-s">' + esc(r.source) + '</span>' +
        '</div>';
    }).join('');
  }

  function _maj(call){
    call = String(call || '').trim();
    if(call.length < 3){ _rendre([]); return; }   // trop court pour résoudre
    fetch('/calldb/provenance?call=' + encodeURIComponent(call))
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){ _rendre(d && d.rows); })
      .catch(function(){});
  }

  // S'attache À SA PROPRE écoute de l'indicatif (n'altère pas les gestionnaires
  // existants). Débounce pour ne pas interroger à chaque touche.
  function _brancher(){
    var inp = document.getElementById('inputCall');
    if(!inp) return;
    inp.addEventListener('input', function(){
      if(_deb) clearTimeout(_deb);
      var v = inp.value;
      _deb = setTimeout(function(){ _maj(v); }, 500);
    });
  }

  global.LogxProvenance = { _rendre: _rendre, _maj: _maj, _brancher: _brancher };

  if(typeof document !== 'undefined' && typeof fetch === 'function'){
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _brancher);
    else _brancher();
  }

})(typeof window !== 'undefined' ? window : this);
