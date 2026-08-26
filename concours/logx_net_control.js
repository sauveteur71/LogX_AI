// ─── CONTRÔLE DE RÉSEAU (net control) — page, tranche 2 ──────────────────────
// Branche la maquette validée (#306) sur les endpoints serveur (tranche 1,
// #308) : GET /data/nets + POST /nets/{create,delete,roster/add,roster/remove}.
// La FILE de passage du micro (session) est tenue CÔTÉ CLIENT le temps du
// réseau ; le log réel des QSO dans le carnet UNIQUE = tranche 3.
//
// Doctrine du dépôt : le carnet reste UNIQUE — un réseau est une VUE, jamais un
// second carnet. « Intuitif » : une seule action évidente (loguer & suivant).
//
// La logique de session est PURE et exposée sur window.NetControl (testée en
// V8, mêmes règles que le serveur logx_net_control.py). Aucun effet DOM au
// chargement du fichier : l'init est déclenchée par DOMContentLoaded.

(function(global){
  'use strict';

  // ── Logique de session PURE (miroir du serveur) ─────────────────────────
  function _norm(call){ return String(call == null ? '' : call).trim().toUpperCase(); }
  function _sess(s){
    s = s || {};
    return { on_air: (s.on_air || []).slice(), logged: (s.logged || []).slice() };
  }
  function mettreALAir(session, call){
    var s = _sess(session), c = _norm(call);
    if(c && s.on_air.indexOf(c) < 0) s.on_air.push(c);
    return s;
  }
  function retirerDeLAir(session, call){
    var s = _sess(session), c = _norm(call);
    s.on_air = s.on_air.filter(function(x){ return x !== c; });
    return s;
  }
  function passerAuSuivant(session){
    var s = _sess(session);
    if(s.on_air.length > 1) s.on_air.push(s.on_air.shift());
    return s;
  }
  function loguerCourant(session){
    var s = _sess(session);
    if(s.on_air.length) s.logged.push(s.on_air.shift());
    return s;
  }

  // Liste canonique de bandes (miroir de logx_logbook.js ALL_BANDS) pour le
  // <select> de création de réseau — valeurs SOURCÉES, pas inventées.
  var BANDES = ['1.8','3.5','7','10.1','14','18','21','24','28','50','70',
                '144','432','1296','2320','3400','5760','10368','24048','47088'];

  // Une station au micro -> un VRAI QSO pour le carnet UNIQUE. Bande/mode/fréq
  // viennent du réseau ; RST par défaut (report de courtoisie 59) ; commentaire
  // tagué. date/heure sont estampillées côté serveur (add_qso_to_log). PUR et
  // testable : le POST /log/add est fait par la couche navigateur.
  function construireQso(call, net){
    net = net || {};
    return {
      call: _norm(call),
      band: net.bande || '',
      mode: net.mode || 'SSB',        // un réseau est phonie par défaut
      freq: net.freq || '',
      rst_sent: '59', rst_rcvd: '59',
      comment: 'Réseau' + (net.nom ? ' ' + net.nom : ''),
    };
  }

  var NetControl = {
    mettreALAir: mettreALAir, retirerDeLAir: retirerDeLAir,
    passerAuSuivant: passerAuSuivant, loguerCourant: loguerCourant,
    construireQso: construireQso, BANDES: BANDES,
  };
  global.NetControl = NetControl;
  if(typeof module !== 'undefined' && module.exports) module.exports = NetControl;

  // ── Au-delà d'ici : couche navigateur (fetch + rendu). Ignorée en V8. ───
  if(typeof document === 'undefined' || !document.getElementById) return;

  var _nets = [];          // réseaux + répertoires (GET /data/nets)
  var _netId = null;       // réseau sélectionné
  var _session = { on_air: [], logged: [] };

  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function netCourant(){ return _nets.filter(function(n){ return n.id === _netId; })[0] || null; }

  // ── Appels serveur (même origine -> cookie d'auth envoyé automatiquement) ─
  function _post(path, payload){
    return fetch(path, {method:'POST', headers:{'Content-Type':'application/json'},
                        body: JSON.stringify(payload || {})}).then(function(r){ return r.json(); });
  }
  function chargerNets(){
    return fetch('/data/nets').then(function(r){ return r.json(); }).then(function(d){
      _nets = (d && d.nets) || [];
      if(_netId == null && _nets.length) _netId = _nets[0].id;
      rendre();
    }).catch(function(){});
  }
  function creerNet(champs){
    return _post('/nets/create', champs).then(function(d){
      if(d && d.net){ _netId = d.net.id; } return chargerNets();
    });
  }
  function supprimerNet(id){
    return _post('/nets/delete', {id:id}).then(function(){
      if(_netId === id){ _netId = null; _session = {on_air:[],logged:[]}; }
      return chargerNets();
    });
  }
  function ajouterMembre(membre){
    if(_netId == null) return Promise.resolve();
    return _post('/nets/roster/add', {net_id:_netId, membre:membre}).then(function(){ return chargerNets(); });
  }
  function retirerMembre(call){
    if(_netId == null) return Promise.resolve();
    return _post('/nets/roster/remove', {net_id:_netId, call:call}).then(function(){ return chargerNets(); });
  }

  // ── Notification légère (barre d'état) ──────────────────────────────────
  function notify(msg, kind){
    var el = document.getElementById('netStatus');
    if(!el) return;
    el.textContent = msg;
    el.className = 'net-status' + (kind ? ' ' + kind : '');
  }

  // ── Actions session (client) ────────────────────────────────────────────
  function alAir(call){ _session = mettreALAir(_session, call); rendre(); }
  function passer(){ _session = passerAuSuivant(_session); rendre(); }

  // Enregistre UNE station dans le carnet UNIQUE via /log/add (même chemin que
  // la saisie normale : dédup, ids, portée, persistance). Résout à true si le
  // QSO est entré (ok OU déjà présent = 409), false sur vraie erreur.
  function _loguerQso(call){
    var net = netCourant();
    return _post('/log/add', construireQso(call, net)).then(function(r){
      return !!(r && (r.ok || r.duplicate));
    }).catch(function(){ return false; });
  }

  // Loguer la station AU MICRO puis passer au suivant — le geste central.
  function loguerEtSuivant(){
    var call = _session.on_air[0];
    if(!call) return;
    notify('Enregistrement de ' + call + '…');
    _loguerQso(call).then(function(ok){
      _session = loguerCourant(_session);      // sort de la file quoi qu'il arrive
      rendre();
      notify(ok ? (call + ' logué au carnet ✓') : ('⚠ ' + call + ' non logué (erreur serveur)'),
             ok ? 'ok' : 'err');
    });
  }

  // Loguer TOUTES les stations à l'air d'un coup (fin de tour de réseau).
  function loguerTout(){
    var calls = _session.on_air.slice();
    if(!calls.length){ notify('Personne à l\'air.'); return; }
    notify('Enregistrement de ' + calls.length + ' station(s)…');
    var faits = 0;
    var suite = calls.reduce(function(p, c){
      return p.then(function(){ return _loguerQso(c).then(function(ok){ if(ok) faits++; }); });
    }, Promise.resolve());
    suite.then(function(){
      calls.forEach(function(c){ _session = loguerCourant(_session); });
      rendre();
      notify(faits + '/' + calls.length + ' station(s) loguée(s) au carnet ✓', 'ok');
    });
  }

  // ── Rendu ───────────────────────────────────────────────────────────────
  function _set(id, html){ var el = document.getElementById(id); if(el) el.innerHTML = html; }

  function rendreSelecteur(){
    var sel = document.getElementById('netSelect');
    if(!sel) return;
    sel.innerHTML = _nets.map(function(n){
      return '<option value="' + n.id + '"' + (n.id === _netId ? ' selected' : '') + '>'
           + esc(n.nom || ('Réseau ' + n.id))
           + (n.freq ? ' · ' + esc(n.freq) + ' MHz' : '') + '</option>';
    }).join('') || '<option value="">— aucun réseau —</option>';
  }

  function rendreRepertoire(){
    var net = netCourant();
    var roster = (net && net.roster) || [];
    _set('roster', roster.map(function(m){
      return '<div class="member" onclick="NetControl.alAir(\'' + esc(m.call) + '\')" title="Mettre à l\'air">'
           + '<div><div class="call">' + esc(m.call) + '</div>'
           + '<div class="who">' + esc([m.nom, m.qth].filter(Boolean).join(' · ')) + '</div></div>'
           + '<button class="rm" onclick="event.stopPropagation();NetControl.retirerMembre(\'' + esc(m.call) + '\')" title="Retirer du répertoire">✕</button>'
           + '</div>';
    }).join('') || '<div class="vide">Répertoire vide — ajoute un indicatif ci-dessus.</div>');
    var ct = document.getElementById('rosterCount');
    if(ct) ct.textContent = roster.length + ' station' + (roster.length > 1 ? 's' : '');
  }

  function rendreMic(){
    var m = _session.on_air[0], next = _session.on_air[1];
    if(!m){ _set('micWrap', '<div class="mic vide">File vide — mets une station à l\'air depuis le répertoire.</div>'); return; }
    _set('micWrap',
      '<div class="mic"><div class="lbl"><span class="live"></span>AU MICRO MAINTENANT</div>'
      + '<div class="call">' + esc(m) + '</div>'
      + '<div class="row"><button class="big-btn" onclick="NetControl.loguerEtSuivant()">✔ Loguer &amp; passer au suivant</button>'
      + '<button class="ghost-btn" onclick="NetControl.passer()" title="Passer sans loguer">▶</button></div>'
      + '<div class="hint">' + (next ? 'Ensuite : <b>' + esc(next) + '</b>' : 'Dernière station de la file') + '</div></div>');
  }

  function rendreFile(){
    _set('queue', _session.on_air.slice(1).map(function(c, i){
      return '<div class="q-item"><span class="num">' + (i + 2) + '</span><span class="call">' + esc(c) + '</span></div>';
    }).join('') || '<div class="vide">Personne d\'autre en attente.</div>');
    _set('loggedList', _session.logged.slice().reverse().map(function(c){
      return '<div class="lrow"><span class="ok">✔</span><span class="call">' + esc(c) + '</span></div>';
    }).join('') || '<div class="vide">Aucun QSO logué pour l\'instant.</div>');
  }

  function rendre(){ rendreSelecteur(); rendreRepertoire(); rendreMic(); rendreFile(); }

  // ── Actions UI exposées inline ──────────────────────────────────────────
  NetControl.alAir = alAir;
  NetControl.loguerEtSuivant = loguerEtSuivant;
  NetControl.loguerTout = loguerTout;
  NetControl.passer = passer;
  NetControl.retirerMembre = retirerMembre;
  NetControl.creerNet = creerNet;
  NetControl.supprimerNet = supprimerNet;

  NetControl.onSelectNet = function(v){ _netId = parseInt(v, 10); _session = {on_air:[],logged:[]}; rendre(); };

  // Création via un petit FORMULAIRE (nom + bande + mode + fréq) plutôt que des
  // prompts : le réseau porte alors bande/mode, indispensables pour loguer un
  // vrai QSO (tranche 3). La bande vient d'un <select> peuplé de BANDES.
  function _peuplerFormBande(){
    var sel = document.getElementById('netBande');
    if(!sel || sel.options.length) return;
    sel.innerHTML = BANDES.map(function(b){ return '<option value="' + b + '">' + b + ' MHz</option>'; }).join('');
  }
  NetControl.ouvrirFormNet = function(){
    _peuplerFormBande();
    var f = document.getElementById('netForm'); if(f) f.style.display = 'flex';
    var n = document.getElementById('netNom'); if(n) n.focus();
  };
  NetControl.fermerFormNet = function(){ var f = document.getElementById('netForm'); if(f) f.style.display = 'none'; };
  NetControl.creerDepuisForm = function(){
    var g = function(id){ var e = document.getElementById(id); return e ? e.value : ''; };
    var nom = (g('netNom') || '').trim();
    if(!nom){ notify('Donne un nom au réseau.'); return; }
    creerNet({nom: nom, bande: g('netBande'), mode: g('netMode'), freq: (g('netFreq') || '').trim()})
      .then(function(){ NetControl.fermerFormNet(); notify('Réseau « ' + nom + ' » créé.', 'ok'); });
  };
  NetControl.ajouterDepuisChamp = function(){
    var inp = document.getElementById('rosterInput');
    if(!inp || !inp.value.trim()) return;
    ajouterMembre({call: inp.value}); inp.value = '';
  };

  document.addEventListener('DOMContentLoaded', chargerNets);

})(typeof window !== 'undefined' ? window : this);
