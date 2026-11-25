// ─── « Passer en FT8 ? » — mode du spot ≠ mode de saisie ─────────────────────
// Demande F4GLD (28/10/2026) : un clic sur un spot FT8 (band map, Opportunités)
// alors qu'on est en SSB doit PROPOSER le changement — « voulez-vous passer en
// FT8 ? » — au lieu de laisser le carnet en SSB (QSO loggé faux) ou de basculer
// la radio sans rien dire.
//
// Règles :
//   - seul un mode ANNONCÉ par le spot déclenche la question (jamais un mode
//     déduit du plan de bande, cf. mode_deduit de /data/spots_ranked) ;
//   - « DIGITAL »/« DATA » sans précision ne déclenche rien : on ne sait pas
//     lequel proposer, mieux vaut se taire que deviner ;
//   - non modal (pas de confirm() bloquant), disparaît seul ; rien ne change
//     tant que l'opérateur n'a pas cliqué « Passer en … » ;
//   - « Oui » change le mode du CARNET et celui de la RADIO, à la fréquence du
//     spot (règle la radio, N'ÉMET RIEN).

(function(global){
  'use strict';

  var PHONIE = {SSB: 1, USB: 1, LSB: 1, PHONE: 1, PHONIE: 1};

  // Mode annoncé -> mode du sélecteur du carnet ('' = pas de proposition).
  function normaliser(m){
    m = String(m || '').toUpperCase().trim();
    if(!m) return '';
    if(PHONIE[m]) return 'SSB';
    if(m === 'CW' || m === 'CW-R') return 'CW';
    if(m === 'DIGITAL' || m === 'DATA' || m === 'DIGI') return '';
    if(/^PSK/.test(m)) return 'PSK';
    if(/^[A-Z0-9-]{2,8}$/.test(m)) return m;     // FT8, FT4, RTTY, FM, AM…
    return '';
  }

  function _el(){
    var d = document.getElementById('modeSpotOffer');
    if(d) return d;
    d = document.createElement('div');
    d.id = 'modeSpotOffer';
    d.className = 'shortcut-offer mode-spot-offer';
    d.setAttribute('role', 'dialog');
    d.setAttribute('aria-live', 'polite');
    document.body.appendChild(d);
    return d;
  }
  function fermer(){
    var d = document.getElementById('modeSpotOffer');
    if(d) d.classList.remove('show');
    clearTimeout(fermer._tm);
  }

  var _attente = null;   // {mode, freqHz} de la proposition affichée

  // Affiche la proposition si le mode annoncé diffère du mode de saisie.
  // Renvoie true si une question a été posée.
  function proposer(modeSpot, freqHz, call){
    var m = normaliser(modeSpot);
    var courant = (typeof global.currentMode !== 'undefined') ? global.currentMode
                : (typeof currentMode !== 'undefined' ? currentMode : '');
    if(!m || !courant || m === normaliser(courant)) return false;
    _attente = {mode: m, freqHz: Math.round(Number(freqHz) || 0), call: String(call || '')};
    var d = _el();
    var esc = function(s){ return String(s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); };
    d.innerHTML =
      '<div class="shortcut-offer-title">Station en ' + esc(m) + '</div>' +
      '<div class="shortcut-offer-text">' + esc(_attente.call || 'Ce spot') + ' est spotté en <b>' + esc(m) +
        '</b>, tu es en ' + esc(courant) + '. Passer en ' + esc(m) + ' ?</div>' +
      '<div class="shortcut-offer-row">' +
        '<button type="button" class="shortcut-offer-yes" onclick="LogxModeSpot.accepter()">Passer en ' + esc(m) + '</button>' +
        '<button type="button" class="shortcut-offer-no" onclick="LogxModeSpot.fermer()">Rester en ' + esc(courant) + '</button>' +
      '</div>';
    d.classList.add('show');
    clearTimeout(fermer._tm);
    fermer._tm = setTimeout(fermer, 20000);
    return true;
  }

  // « Oui » : carnet ET radio passent dans le mode du spot.
  function accepter(){
    var a = _attente; fermer();
    if(!a) return;
    // fromRig:true -> pickMode ne repousse PAS l'ancienne fréquence du champ
    // vers la radio (elle n'est pas forcément encore à jour) : le QSY part
    // ci-dessous, avec la fréquence du spot.
    if(typeof global.pickMode === 'function') global.pickMode(a.mode, {fromRig: true});
    var note = function(msg){ if(typeof global.notify === 'function') global.notify(msg); };
    var rig = (typeof global.rigState !== 'undefined') ? global.rigState
            : (typeof rigState !== 'undefined' ? rigState : null);
    var suite = /^FT[48]$/.test(a.mode) ? ' — décodage : Outils › MODE NUMÉRIQUE (ou WSJT-X)' : '';
    if(!(rig && rig.enabled) || !a.freqHz){ note('Mode du carnet : ' + a.mode + suite); return; }
    fetch('/rig/qsy', {method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({freq_hz: a.freqHz, mode: a.mode})})
      .then(function(r){ return r.json().catch(function(){ return {ok: false}; }); })
      .then(function(d){
        note(d && d.ok ? ('📻 Radio et carnet en ' + a.mode + suite)
                       : ('❌ Carnet en ' + a.mode + ', radio non basculée : ' + ((d && d.error) || 'pas de réponse')));
      })
      .catch(function(){ note('❌ Carnet en ' + a.mode + ', radio non basculée : serveur injoignable'); });
  }

  global.LogxModeSpot = {normaliser: normaliser, proposer: proposer, accepter: accepter, fermer: fermer};
})(typeof window !== 'undefined' ? window : this);
