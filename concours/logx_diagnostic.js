// ─── Écran « Santé de la station » (diagnostic) ──────────────────────────────
// Une vue d'ensemble, en un coup d'œil, de l'état des sous-systèmes — pour
// répondre tout de suite à « est-ce que tout est prêt ? » (intuitivité, maître
// mot du projet). LECTURE SEULE : agrège des endpoints d'état EXISTANTS
// (/hardware/state, /data/network_status, /tx/audit, /dxcc/status). N'écrit
// rien, ne pilote rien.

(function(global){
  'use strict';

  var INTERVALLE_MS = 5000;
  var _timer = null;
  var _horlogeTimer = null;

  function esc(s){
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // Traduit les états bruts des 4 endpoints en tuiles {id, nom, couleur, detail}.
  // Fonction PURE (testable). Tolère les sections manquantes (état inconnu ->
  // muté), jamais d'exception.
  function construireTuiles(data){
    data = data || {};
    var hw = data.hardware || {};
    var net = data.network || {};
    var tx = data.tx || {};
    var dxcc = data.dxcc || {};
    var t = [];

    var rig = hw.rig || {};
    if(!rig.enabled){
      t.push({id: 'radio', nom: 'Radio (CAT)', couleur: 'muted', detail: 'non configuré'});
    }else if(rig.ok){
      var d = (rig.freq_khz ? rig.freq_khz + ' kHz' : '') + (rig.mode ? ' · ' + rig.mode : '');
      t.push({id: 'radio', nom: 'Radio (CAT)', couleur: 'green', detail: d || 'connectée'});
    }else{
      t.push({id: 'radio', nom: 'Radio (CAT)', couleur: 'red', detail: 'ne répond pas'});
    }

    var rot = hw.rotor || {};
    t.push({id: 'rotor', nom: 'Rotor', couleur: rot.enabled ? 'green' : 'muted',
            detail: rot.enabled ? 'actif' : 'non configuré'});

    var w = hw.wsjtx || {};
    if(!w.enabled){
      t.push({id: 'ft8', nom: 'FT8 / WSJT-X', couleur: 'muted', detail: 'désactivé'});
    }else if(w.connected){
      t.push({id: 'ft8', nom: 'FT8 / WSJT-X', couleur: 'green', detail: 'décodage en cours'});
    }else{
      t.push({id: 'ft8', nom: 'FT8 / WSJT-X', couleur: 'yellow', detail: 'aucun décodage récent'});
    }

    var cb = net.callbook || {};
    t.push({id: 'callbook', nom: 'Callbook', couleur: cb.open ? 'yellow' : 'green',
            detail: cb.open ? 'en pause (hors-ligne)' : 'disponible'});

    var cs = net.cloudsync || {};
    if(!cs.enabled){
      t.push({id: 'cloud', nom: 'Synchro Cloud', couleur: 'muted', detail: 'désactivée'});
    }else{
      t.push({id: 'cloud', nom: 'Synchro Cloud', couleur: cs.last_error ? 'yellow' : 'green',
              detail: cs.last_error ? 'erreur récente' : 'active'});
    }

    var ms = net.mysql_sync || {};
    if(!ms.enabled){
      t.push({id: 'mysql', nom: 'Synchro MySQL', couleur: 'muted', detail: 'désactivée'});
    }else{
      t.push({id: 'mysql', nom: 'Synchro MySQL', couleur: ms.last_error ? 'yellow' : 'green',
              detail: ms.last_error ? 'erreur récente' : 'active'});
    }

    t.push({id: 'dxcc', nom: 'Base DXCC (cty.dat)', couleur: dxcc.available ? 'green' : 'red',
            detail: dxcc.available ? 'chargée' : 'indisponible'});

    t.push({id: 'tx', nom: 'Émission (consentement)', couleur: tx.tx_locked ? 'red' : 'green',
            detail: tx.tx_locked ? 'verrouillé — réarmement requis' : 'prêt (aucun verrou)'});

    return t;
  }

  function _rendre(tuiles){
    var box = document.getElementById('diagTuiles');
    if(!box) return;
    box.innerHTML = (tuiles || []).map(function(t){
      return '<div class="diag-tuile">' +
        '<span class="diag-dot" data-c="' + esc(t.couleur) + '"></span>' +
        '<span class="diag-nom">' + esc(t.nom) + '</span>' +
        '<span class="diag-detail">' + esc(t.detail) + '</span>' +
        '</div>';
    }).join('');
  }

  function _maj(){
    function grab(u){
      return fetch(u).then(function(r){ return r.ok ? r.json() : {}; }).catch(function(){ return {}; });
    }
    Promise.all([grab('/hardware/state'), grab('/data/network_status'),
                 grab('/tx/audit'), grab('/dxcc/status')])
      .then(function(v){
        _rendre(construireTuiles({hardware: v[0], network: v[1], tx: v[2], dxcc: v[3]}));
      });
  }

  // Horloge UTC (côté client — le serveur n'expose pas d'heure).
  function _horloge(){
    var el = document.getElementById('diagHorloge');
    if(!el) return;
    var d = new Date();
    el.textContent = d.toISOString().slice(11, 19) + ' UTC';
  }

  function demarrer(){
    if(_timer) return;
    _maj();
    _horloge();
    var poll = global.rcPoll || function(fn, ms){ return setInterval(fn, ms); };
    _timer = poll(_maj, INTERVALLE_MS);
    _horlogeTimer = setInterval(_horloge, 1000);
  }

  global.LogxDiagnostic = {
    demarrer: demarrer, construireTuiles: construireTuiles, _rendre: _rendre
  };

  // Démarrage auto (VRAI navigateur uniquement — fetch présent).
  if(typeof document !== 'undefined' && typeof fetch === 'function'){
    if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', demarrer);
    else demarrer();
  }

})(typeof window !== 'undefined' ? window : this);
