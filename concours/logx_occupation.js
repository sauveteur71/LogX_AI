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

  // ── Assistant de session « Activer un log partagé » ────────────────────────
  // Porte d'entrée : choisir le TYPE d'opération partagée préconfigure le sync
  // conseillé et ouvre la carte. Les 3 types partagent la même mécanique (log
  // fusionné + occupation) ; ils ne changent QUE la recommandation de canal et
  // le vocabulaire — la vraie config du sync (dossier / MySQL / LAN) reste dans
  // CONFIG, vers laquelle l'assistant renvoie.
  var SCENARIOS = {
    radioclub: {
      titre: '🏛 Radioclub',
      resume: 'Plusieurs opérateurs partagent le log, souvent en temps réel (concours).',
      sync: 'MySQL (temps réel) si vous avez un serveur, sinon dossier partagé (Cloud Sync).'
    },
    expedition: {
      titre: '🏝 Expédition',
      resume: 'Équipe répartie à distance, ou plusieurs postes sur le site.',
      sync: 'Dossier partagé (Cloud Sync) à distance ; LAN (auto) quand les postes sont sur place.'
    },
    activation: {
      titre: '📻 Activation spéciale',
      resume: 'Un indicatif spécial (ex. TM6KJS) opéré depuis plusieurs stations.',
      sync: 'LAN (auto) si même lieu ; dossier partagé (Cloud Sync) si réseaux internet différents.'
    }
  };
  var CLE_TYPE = 'rc_log_partage_type';

  function _typePersiste(){
    try { return localStorage.getItem(CLE_TYPE) || ''; } catch(e){ return ''; }
  }

  // HTML du détail d'un scénario (testable) : rappel + sync conseillé + actions.
  function _detailScenario(type){
    var sc = SCENARIOS[type];
    if(!sc) return '';
    return '<div class="lp-detail-titre">' + _esc(sc.titre) + '</div>'
      + '<p class="lp-resume">' + _esc(sc.resume) + '</p>'
      + '<div class="lp-sync"><b>Sync conseillé :</b> ' + _esc(sc.sync) + '</div>'
      + '<p class="lp-rappel">Tous les postes doivent utiliser le <b>même indicatif</b> '
      + 'et le <b>même sync</b>. La carte prend automatiquement le canal actif '
      + '(LAN instantané en local, sinon Cloud/MySQL).</p>'
      + '<div class="lp-actions">'
      + '<a class="lp-btn" href="logx_configuration.html">⚙ Configurer le sync</a>'
      + '<button type="button" class="lp-btn lp-btn-primaire" onclick="LogxOccupation.ouvrirCarte()">📻 Afficher la carte</button>'
      + '</div>';
  }

  function choisirScenario(type){
    if(!SCENARIOS[type]) return;
    try { localStorage.setItem(CLE_TYPE, type); } catch(e){}
    var d = document.getElementById('lpDetail');
    var c = document.getElementById('lpChoix');
    if(d){ d.innerHTML = _detailScenario(type); d.hidden = false; }
    if(c) c.hidden = true;
  }

  function ouvrirAssistant(){
    var ov = document.getElementById('logPartageOverlay');
    if(!ov) return;
    var d = document.getElementById('lpDetail'), c = document.getElementById('lpChoix');
    var t = _typePersiste();
    if(t && d && c){ d.innerHTML = _detailScenario(t); d.hidden = false; c.hidden = true; }
    else if(d && c){ d.hidden = true; c.hidden = false; }
    ov.hidden = false;
  }
  function fermerAssistant(){
    var ov = document.getElementById('logPartageOverlay'); if(ov) ov.hidden = true;
  }
  // Depuis l'assistant : fermer + ouvrir la carte.
  function ouvrirCarte(){ fermerAssistant(); demarrer(); }

  // Le bouton « Occupation » : 1re fois (aucun type choisi) -> assistant ;
  // ensuite -> bascule directe de la carte.
  function basculer(){
    if(_actif){ arreter(); return; }
    if(_typePersiste()) demarrer(); else ouvrirAssistant();
  }

  global.LogxOccupation = {
    demarrer: demarrer, arreter: arreter, basculer: basculer,
    ouvrirAssistant: ouvrirAssistant, fermerAssistant: fermerAssistant,
    choisirScenario: choisirScenario, ouvrirCarte: ouvrirCarte,
    _rendre: _rendre, _detailScenario: _detailScenario, estActif: function(){ return _actif; }
  };

})(typeof window !== 'undefined' ? window : this);
