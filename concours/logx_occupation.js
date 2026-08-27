// ─── Carte d'occupation des bandes multi-postes (frontend) ───────────────────
// Log partagé (radioclub / expédition / activation spéciale type TM6KJS) : qui
// est sur quelle bande/mode, et alerte si deux postes se recouvrent (même bande
// + même mode). S'appuie sur le backend logx_occupancy (transport-agnostique :
// LAN instantané + Cloud/MySQL pour le distant, priorité locale).
//
// Deux rôles quand la carte est ACTIVE :
//   1. HEARTBEAT — CE poste déclare sa bande/mode courantes (POST, cookie
//      rc_token comme /log/add) pour que les autres le voient.
//   2. RENDU — lit /data/occupancy et affiche la carte + les conflits.
//
// Opt-in : rien ne tourne tant que la carte n'est pas ouverte (pas de POST
// parasite pour un opérateur solo).

(function(global){
  'use strict';

  var _timer = null;
  var _actif = false;
  var INTERVALLE_MS = 20000;   // heartbeat + rafraîchissement toutes les 20 s

  function _band(){ return (typeof currentBand !== 'undefined' && currentBand != null) ? String(currentBand) : ''; }
  function _mode(){ return (typeof currentMode !== 'undefined' && currentMode != null) ? String(currentMode) : ''; }
  function _esc(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function _heartbeat(){
    // Même motif que /log/add : POST JSON, auth par cookie rc_token (même origine).
    fetch('/occupancy/heartbeat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ band: _band(), mode: _mode() })
    }).catch(function(){});
  }

  function _rendre(vue){
    var corps = document.getElementById('occupationCorps');
    if(!corps) return;
    var stations = (vue && vue.stations) || [];
    var conflits = (vue && vue.conflits) || [];
    // couples bande+mode en conflit, pour surligner les lignes concernées
    var enConflit = {};
    conflits.forEach(function(c){ enConflit[c.band + '|' + c.mode] = true; });

    if(!stations.length){
      corps.innerHTML = '<div class="occ-vide">' + _esc('En attente des postes…') + '</div>';
      return;
    }
    var lignes = stations.map(function(s){
      var cle = (s.band || '') + '|' + (s.mode || '');
      var conflit = !!enConflit[cle];
      return '<tr class="' + (conflit ? 'occ-conflit' : '') + '">'
        + '<td class="occ-call">' + _esc(s.call || '?') + '</td>'
        + '<td class="occ-band">' + _esc(s.band || '—') + (s.band ? ' m' : '') + '</td>'
        + '<td class="occ-mode">' + _esc(s.mode || '—') + '</td>'
        + '<td class="occ-flag">' + (conflit ? '⚠️ recouvrement' : '') + '</td>'
        + '</tr>';
    }).join('');
    var alerte = conflits.length
      ? '<div class="occ-alerte">⚠️ ' + conflits.length + ' recouvrement(s) : deux postes sur la même bande ET le même mode.</div>'
      : '';
    corps.innerHTML = alerte
      + '<table class="occ-table"><thead><tr><th>Poste</th><th>Bande</th><th>Mode</th><th></th></tr></thead>'
      + '<tbody>' + lignes + '</tbody></table>';
  }

  function _cycle(){
    _heartbeat();
    fetch('/data/occupancy').then(function(r){ return r.json(); })
      .then(_rendre).catch(function(){});
  }

  function demarrer(){
    if(_actif) return;
    _actif = true;
    var p = document.getElementById('occupationPanel');
    if(p) p.hidden = false;
    _cycle();
    // rcPoll suspend sur onglet masqué si dispo, sinon setInterval.
    var poll = global.rcPoll || function(fn, ms){ return setInterval(fn, ms); };
    _timer = poll(_cycle, INTERVALLE_MS);
  }

  function arreter(){
    _actif = false;
    var p = document.getElementById('occupationPanel');
    if(p) p.hidden = true;
    if(_timer && typeof _timer === 'number'){ clearInterval(_timer); }
    _timer = null;
  }

  function basculer(){ _actif ? arreter() : demarrer(); }

  global.LogxOccupation = {
    demarrer: demarrer, arreter: arreter, basculer: basculer,
    _rendre: _rendre, estActif: function(){ return _actif; }
  };

})(typeof window !== 'undefined' ? window : this);
