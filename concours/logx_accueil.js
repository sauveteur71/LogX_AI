// ─── ACCUEIL PAR ACTIVITÉ ─────────────────────────────────────────────────
// Voir le commentaire en tête de logx_accueil.html pour le contexte complet
// (doctrine, honnêteté de périmètre). Ce fichier ne fait que deux choses :
// décider s'il faut afficher la grille ou rediriger tout de suite (résumé en
// un geste), et poser localStorage.logx_activity au clic.

const _ICO = {
  normal:   '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="2" y1="7" x2="16" y2="7"/><line x1="9" y1="7" x2="9" y2="16"/><circle cx="9" cy="4" r="1.2" fill="currentColor" stroke="none"/></svg>',
  sixm:     '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="2" y1="9" x2="16" y2="9"/><line x1="5" y1="6" x2="5" y2="12"/><line x1="9" y1="5" x2="9" y2="13"/><line x1="13" y1="7" x2="13" y2="11"/></svg>',
  vuhf:     '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="9" y1="16" x2="9" y2="2"/><circle cx="9" cy="4" r="1" fill="currentColor" stroke="none"/><circle cx="9" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="9" cy="12" r="1" fill="currentColor" stroke="none"/></svg>',
  shf:      '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 13a8 4 0 0 1 12 0"/><line x1="9" y1="13" x2="9" y2="4"/><circle cx="9" cy="3" r="1.2" fill="currentColor" stroke="none"/></svg>',
  sat:      '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="9" cy="9" r="2.6"/><ellipse cx="9" cy="9" rx="7.5" ry="3" transform="rotate(-25 9 9)"/></svg>',
  concours: '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="16" x2="4" y2="2"/><path d="M4 3h10l-3 3 3 3H4"/></svg>',
  dxp:      '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="9" cy="9" r="7"/><path d="M2 9h14M9 2c2.3 1.8 2.3 12.2 0 14M9 2c-2.3 1.8-2.3 12.2 0 14"/></svg>',
  special:  '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><polygon points="9,2 11,7 16,7 12,10.5 13.5,16 9,12.5 4.5,16 6,10.5 2,7 7,7"/></svg>',
  iota_pota:'<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 15C4 8 9 3 15 3c0 6-5 11-11 11-1 0-1 0-1-1z"/><line x1="4" y1="15" x2="9" y2="10"/></svg>',
  qrp:      '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"><polygon points="10,2 4,10 8,10 7,16 14,8 10,8"/></svg>',
};

// Périmètre honnête (voir en-tête HTML) : seule 'vuhf' a un vrai filtrage à
// ce stade (marquée pilote:true, mise en avant visuellement). Les autres
// routent vers CONFIG/LOGBOOK SANS filtre supplémentaire -- comportement
// actuel de l'app, pas un leurre.
const ACTIVITIES = [
  {id:'normal',    label:'LOG normal',        hint:'160 m → 10 m, tous modes',        icon:_ICO.normal},
  {id:'6m',        label:'LOG 6 m',           hint:'50 MHz',                          icon:_ICO.sixm},
  {id:'vuhf',      label:'LOG V/UHF',         hint:'2 m · 70 cm · 23 cm…',            icon:_ICO.vuhf, pilote:true},
  {id:'shf',       label:'LOG SHF',           hint:'1,2 GHz et plus',                 icon:_ICO.shf},
  {id:'sat',       label:'LOG Satellites',    hint:'QO-100, LEO…',                    icon:_ICO.sat},
  {id:'concours',  label:'LOG Concours',      hint:'toutes bandes et modes',          icon:_ICO.concours},
  {id:'dxp',       label:'LOG DXp',           hint:'expéditions',                     icon:_ICO.dxp},
  {id:'special',   label:'LOG Call spéciaux', hint:'événements, indicatifs spéciaux', icon:_ICO.special},
  {id:'iota_pota', label:'LOG activation portable', hint:'POTA · SOTA · WWFF · châteaux…', icon:_ICO.iota_pota},
  {id:'qrp',       label:'LOG QRP',           hint:'faible puissance',                icon:_ICO.qrp},
];

// CONFIG si aucun concours actif (premier réglage nécessaire), sinon direct
// au LOGBOOK -- même logique que le geste "reprendre" décrit par F4GLD.
function _pageSuivante(){
  let cfg = {};
  try{ cfg = JSON.parse(localStorage.getItem('logx_config') || '{}'); }catch(e){}
  return cfg.contest ? 'logx_logbook.html' : 'logx_configuration.html';
}

function choisirActivite(id){
  try{ localStorage.setItem('logx_activity', id); }catch(e){}
  // « Activation portable » = carte chapeau (décision F4GLD D1) : au lieu de
  // partir tout de suite, on révèle le sous-choix de rôle (chasse/activer/mixte)
  // DANS le flux de l'activité. Les autres activités partent directement.
  if(id === 'iota_pota'){ _revelerRolesActivation(); return; }
  window.location.href = _pageSuivante();
}

// Révèle le sous-choix de rôle de l'activité activation portable (carte chapeau,
// D1) : rend les 3 tuiles (chasse/activer/mixte) dans #xotaRoleAccueil et défile
// jusqu'à elles. Gardes défensives (classList/scrollIntoView absents en test DOM).
function _revelerRolesActivation(){
  _renderXotaRoleAccueil();
  const el = document.getElementById('xotaRoleAccueil');
  if(!el) return;
  if(el.classList && el.classList.add) el.classList.add('xota-roles-actives');
  if(el.scrollIntoView) el.scrollIntoView({behavior:'smooth', block:'center'});
}

// « Reprendre » : même geste que l'ancienne redirection immédiate, mais en UN
// clic explicite -- l'accueil montre d'abord le cockpit (décision F4GLD 28/08).
function _reprendre(){ window.location.href = _pageSuivante(); }
function _labelActivite(id){ const a = ACTIVITIES.find(x => x.id === id); return a ? a.label : id; }

// `deja` = id de la dernière activité (ou null) : ajoute un bouton « Reprendre »
// et un cockpit (opportunités / progression / état) AVANT la grille d'activités.
function _grille(deja){
  const intro = document.getElementById('intro');
  intro.innerHTML =
    (deja ? '<div class="reprise-wrap"><button type="button" class="reprendre-btn" onclick="_reprendre()">▶ Reprendre : ' + _labelActivite(deja) + '</button><a class="reprise-changer" href="?changer=1">changer</a></div>' : '') +
    '<div class="cockpit" id="cockpit"><div class="ck-col"><h2>🎯 Opportunités</h2><div id="ckOpp"></div></div><div class="ck-col"><h2>📊 Progression</h2><div id="ckProg"></div></div><div class="ck-col"><h2>🩺 État station</h2><div id="ckEtat"></div></div><div class="ck-col"><h2>🎯 Prochaines cibles</h2><div id="ckCibles"></div></div></div>' +
    '<h1>Qu’est-ce que tu fais aujourd’hui ?</h1>' +
    '<p>Choisis ton activité — tu retrouveras toujours l’accès complet ensuite, et ton carnet reste unique quelle que soit la bande ou le mode.</p>' +
    '<div class="activity-grid" id="activityGrid"></div>' +
    '<div id="xotaRoleAccueil"></div>' +
    '<div id="ciblesChasse"></div>';
  // D1 : les rôles ne sont plus rendus d'office ici — ils apparaissent quand on
  // clique la carte « activation portable » (voir _revelerRolesActivation).
  const grid = document.getElementById('activityGrid');
  grid.innerHTML = ACTIVITIES.map(a =>
    '<button type="button" class="activity-card' + (a.pilote ? ' pilote' : '') + '" onclick="choisirActivite(\'' + a.id + '\')">' +
      a.icon +
      '<span class="activity-name">' + a.label + '</span>' +
      '<span class="activity-hint">' + a.hint + '</span>' +
    '</button>'
  ).join('');
  if(window.LogxCockpit) window.LogxCockpit.charger();
  _brancherBandeaux();
}

// Section « Mode SOTA/POTA cette session » : 3 tuiles de rôle (chasse/portable/
// les deux), rôle mémorisé surligné. Clic -> mémorise + ouvre le logbook réglé
// pour ce rôle. Absente si le module n'est pas chargé. Contenu 100% contrôlé.
function _renderXotaRoleAccueil(){
  const el = document.getElementById('xotaRoleAccueil');
  if(!el || !window.LogxXotaRole) return;
  const actuel = LogxXotaRole.getRole();
  el.innerHTML =
    '<h2 class="xota-acc-h">Mode SOTA / POTA cette session</h2>' +
    '<div class="xota-acc-tiles">' +
    LogxXotaRole.ROLES.map(r =>
      '<button type="button" class="xota-acc-tile' + (r.id === actuel ? ' on' : '') +
      '" onclick="_choisirRoleXota(\'' + r.id + '\')" title="' + r.hint + '">' +
      '<span class="xota-acc-ico">' + r.icone + '</span>' +
      '<span class="xota-acc-name">' + r.label + '</span>' +
      '<span class="xota-acc-hint">' + r.hint + '</span></button>'
    ).join('') + '</div>';
}
function _choisirRoleXota(role){
  if(window.LogxXotaRole) LogxXotaRole.setRole(role);
  // Fusion (incr. 4a) : un rôle qui inclut la CHASSE (chasse/mixte) révèle les
  // cibles en direct DANS l'activité, sans naviguer ; « activer » pur part au
  // logbook. Gâté par roleConfig (D1 : les rôles gâtent le contenu chasse).
  var cfg = (window.LogxXotaRole && LogxXotaRole.roleConfig) ? LogxXotaRole.roleConfig(role) : {};
  if(cfg.chasse){ _revelerCiblesChasse(); return; }
  window.location.href = 'logx_logbook.html';
}

// Révèle la need-list « cibles en direct » dans le flux activation (fusion 4a).
// Rendu délégué au module LogxChassePanneaux (réutilise creditBadge/splitBadge/
// PRIO_COLORS). `fetch` gardé (absent en DOM de test) ; la partie synchrone
// (section + entête) reste testable.
// État radio/rotor résolu pour la need-list de l'activité (fusion 4d),
// mémorisé ici pour que enregistrerObjectifs() (4e) puisse re-rendre sans
// re-interroger /rig/state et /rotor/state à chaque changement d'objectif.
var _xotaRigEnabled = false, _xotaRotorEnabled = false;

function _revelerCiblesChasse(){
  var el = document.getElementById('ciblesChasse');
  if(!el) return;
  // Panneaux d'activation POTA/SOTA/WWFF/WCA/DXpéditions (fusion 4b+4c) +
  // need-list cluster avec QSY/rotor (fusion 4d, endpoints /rig/qsy et
  // /rotor/point — AUCUNE émission, juste régler la fréquence/l'antenne) +
  // profil d'objectifs de chasse (fusion 4e, pilote les badges de crédit).
  el.innerHTML =
    '<h2 class="xota-acc-h">Cibles en direct</h2>' +
    '<div class="xota-panneaux">' +
      '<div class="xota-pan"><div class="xota-pan-h">POTA</div><div id="panPota" class="scroll-list"></div></div>' +
      '<div class="xota-pan"><div class="xota-pan-h">SOTA</div><div id="panSota" class="scroll-list"></div></div>' +
      '<div class="xota-pan"><div class="xota-pan-h">WWFF</div><div id="panWwff" class="scroll-list"></div></div>' +
      '<div class="xota-pan"><div class="xota-pan-h">WCA / COTA (annoncé)</div><div id="panWca" class="scroll-list"></div></div>' +
      '<div class="xota-pan"><div class="xota-pan-h">DXpéditions</div><div id="panDx" class="scroll-list"></div></div>' +
    '</div>' +
    '<div class="xota-pan xota-pan-full"><div class="xota-pan-h">🎯 Mes objectifs de chasse</div><div id="objectifsList" class="obj-list"></div></div>' +
    '<div class="xota-pan xota-pan-full"><div class="xota-pan-h">Need list — cluster <span id="xotaQsyStatus" class="xota-qsy-status"></span></div><div id="ckNeedList" class="scroll-list"></div></div>';
  if(typeof fetch !== 'function') return;
  var P = window.LogxChassePanneaux; if(!P) return;
  _chargerPota(); _chargerSota(); _chargerWwff(); _chargerWca(); _chargerDx();
  chargerObjectifs();
  // Rafraîchissement automatique (écart de comportement signalé après la
  // fusion, 12/09/2026 : l'ancienne page CHASSE pollait en continu, la
  // nouvelle ne se rechargeait plus qu'au clic/changement d'objectif).
  // Démarré ICI, SYNCHRONE -- ne dépend pas de la résolution de la promesse
  // rig/rotor juste en dessous : _rafraichirNeedList() relit _xotaRigEnabled/
  // _xotaRotorEnabled à CHAQUE appel (pas une valeur figée à la création du
  // timer), le premier tick du poll (60 s plus tard) verra forcément l'état
  // déjà résolu. Mêmes cadences que l'ancienne implémentation (logx_chasse.
  // html avant fusion, incr. 5c).
  _demarrerPollingChasse();
  // Need-list : lit l'état radio/rotor AVANT de rendre (comme logx_chasse.html)
  // pour savoir si les boutons QSY/rotor doivent apparaître par ligne.
  Promise.all([
    fetch('/rig/state').then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }),
    fetch('/rotor/state').then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; })
  ]).then(function(states){
    _xotaRigEnabled = !!(states[0] && states[0].enabled);
    _xotaRotorEnabled = !!(states[1] && states[1].enabled);
    _rafraichirNeedList();
  });
}

// Re-fetch + re-rend la need-list (extrait de _revelerCiblesChasse pour être
// rejoué après un changement d'objectif, fusion 4e) — pas un simple re-rendu :
// les crédits sont calculés côté SERVEUR à partir du profil d'objectifs, donc
// il faut relire /data/spots_ranked pour que les badges changent (sinon rien
// de visible avant le poll suivant).
function _rafraichirNeedList(){
  if(typeof fetch !== 'function') return;
  var P = window.LogxChassePanneaux; if(!P) return;
  _chargerPan('/data/spots_ranked', 'ckNeedList', function(d){
    return P.renderNeedList((d && d.spots) || [], {max:15, rigEnabled:_xotaRigEnabled, rotorEnabled:_xotaRotorEnabled});
  });
}

// Un loader nommé par panneau (plutôt que les lambdas inline d'avant) : la
// même fonction sert au premier rendu ET à chaque tick du polling ci-dessous.
function _chargerPota(){ var P = window.LogxChassePanneaux; if(P) _chargerPan('/data/pota_spots', 'panPota', function(d){ return P.renderActivationRows((d && d.spots) || [], {place:_placePota, programme:'POTA'}); }); }
function _chargerSota(){ var P = window.LogxChassePanneaux; if(P) _chargerPan('/data/sota_spots', 'panSota', function(d){ return P.renderActivationRows((d && d.spots) || [], {place:_placeSota, programme:'SOTA'}); }); }
function _chargerWwff(){ var P = window.LogxChassePanneaux; if(P) _chargerPan('/data/wwff_spots', 'panWwff', function(d){ return P.renderActivationRows((d && d.spots) || [], {place:_placePota, programme:'WWFF'}); }); } // WWFF : même champ park_name que POTA
function _chargerWca(){ var P = window.LogxChassePanneaux; if(P) _chargerPan('/data/wca_planned', 'panWca', function(d){ return P.renderWcaRows((d && d.items) || [], {max:15}); }); }
function _chargerDx(){ var P = window.LogxChassePanneaux; if(P) _chargerPan('/data/dxpeditions_active', 'panDx', function(d){ return P.renderDxRows((d && d.expeditions) || [], {max:15}); }); }

// Rafraîchissement automatique des panneaux + de la need-list -- mêmes
// cadences que l'ancienne page CHASSE (avant fusion, PR #464-#471) :
// need-list chaque minute, POTA/SOTA/WWFF/DXpéditions selon leur cache
// serveur respectif, WCA (simple flux RSS) toutes les 5 min. Le profil
// d'objectifs (chargerObjectifs) N'EST PAS re-pollé -- l'ancienne page ne
// le faisait pas non plus (« profil d'objectifs : chargé une fois au
// démarrage »), un changement se fait via un geste explicite (case cochée),
// pas par polling. window.rcPoll (logx_statusbar.js) suspend les timers
// quand l'onglet est masqué -- même garde-fou que le reste de l'app.
var _xotaPollingDemarre = false;
function _demarrerPollingChasse(){
  if(_xotaPollingDemarre) return;
  _xotaPollingDemarre = true;
  var poll = window.rcPoll || function(fn, ms){ return setInterval(fn, ms); };
  poll(_rafraichirNeedList, 60 * 1000);
  poll(_chargerPota, 2 * 60 * 1000);
  poll(_chargerSota, 60 * 1000);
  poll(_chargerWwff, 60 * 1000);
  poll(_chargerWca, 5 * 60 * 1000);
  poll(_chargerDx, 2 * 60 * 1000);
}

// ── Profil d'OBJECTIFS opérateur (fusion 4e, port de logx_chasse.html) ─────
// Les clés DOIVENT correspondre EXACTEMENT à logx_operator_goals.CLES côté
// serveur (garde-fou test_accueil_objectifs_ui.py) : sinon cocher/décocher ne
// piloterait aucun crédit.
var OBJECTIFS_DEF = [
  {cle:'dxcc',                       label:'🌟 Nouveaux pays (ATNO)'},
  {cle:'dxcc_new_band',              label:'📻 Nouvelle bande'},
  {cle:'dxcc_new_mode',              label:'🎚 Nouveau mode'},
  {cle:'lotw_confirmation_priority', label:'📩 Confirmations LoTW'},
  {cle:'vucc',                       label:'🗺 Nouveaux carrés (VUCC)'},
];
function construireObjectifs(goals){
  var box = document.getElementById('objectifsList');
  if(!box) return;
  // absent => coché (défaut = objectif actif, comme le serveur)
  box.innerHTML = OBJECTIFS_DEF.map(function(o){
    return '<label class="obj-item"><input type="checkbox" data-cle="' + o.cle + '"' + (goals[o.cle] === false ? '' : ' checked') + '> ' + o.label + '</label>';
  }).join('');
  var inputs = box.querySelectorAll ? box.querySelectorAll('input[data-cle]') : [];
  for(var i=0; i<inputs.length; i++) inputs[i].onchange = enregistrerObjectifs;
}
function lireObjectifs(){
  var out = {};
  var inputs = document.querySelectorAll('#objectifsList input[data-cle]');
  inputs.forEach(function(inp){ out[inp.dataset.cle] = inp.checked; });
  return out;
}
function enregistrerObjectifs(){
  var goals = lireObjectifs();
  fetch('/data/operator_goals', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({goals:goals})})
    .then(function(r){ return r.json(); })
    .then(function(){ _rafraichirNeedList(); })   // re-fetch, pas un simple re-rendu (voir commentaire ci-dessus)
    .catch(function(){});
}
function chargerObjectifs(){
  fetch('/data/operator_goals').then(function(r){ return r.json(); })
    .then(function(d){ construireObjectifs((d && d.goals) || {}); })
    .catch(function(){ construireObjectifs({}); });   // serveur muet -> tout coché (défaut)
}

// ── Stratégie pile-up FT8 (fusion 4f, port de logx_chasse.html) ────────────
// L'IA lit la série des décodages d'UNE DX. Purement CONSULTATIF (aucune
// émission). Job serveur, récupéré par polling ; affiche le verdict ET les
// décodages BRUTS utilisés (transparence).
function ft8Strategy(call){
  call = (call || '').trim().toUpperCase(); if(!call) return;
  openStratModal(call, '<div class="loading">⏳ Analyse de la stratégie…</div>');
  fetch('/wsjtx/strategy', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({call:call})})
    .then(function(r){ return r.json(); })
    .then(function(j){
      if(!j.id){ setStratBody('❌ ' + (j.error || 'erreur')); return; }
      pollStrat(j.id);
    }).catch(function(e){ setStratBody('❌ ' + e.message); });
}
// id de la DERNIÈRE analyse demandée : deux analyses lancées coup sur coup
// créent deux boucles pollStrat() indépendantes — sans ce garde, celle de la
// 1re demande, plus lente, pouvait afficher sa réponse APRÈS que le popup ait
// déjà changé de titre pour la 2e, écrasant le bon résultat avec l'obsolète.
var _stratActiveId = null;
function pollStrat(id){
  _stratActiveId = id;
  var tick = async function(){
    if(id !== _stratActiveId) return;   // une analyse plus récente a pris le relais
    var s;
    try{ var r = await fetch('/wsjtx/strategy/state?id=' + encodeURIComponent(id)); s = await r.json(); }
    catch(e){ setTimeout(tick, 2500); return; }
    if(id !== _stratActiveId) return;
    if(s.status === 'running'){ setTimeout(tick, 1500); return; }
    if(s.status === 'done') renderStrat(s);
    else if(s.status === 'error') setStratBody('❌ ' + (s.error || 'échec'));
    else setStratBody('⚠️ Analyse introuvable (serveur redémarré ?).');
  };
  tick();
}
function renderStrat(s){
  var P = window.LogxChassePanneaux;
  var esc = P ? P.esc : function(v){ return String(v == null ? '' : v); };
  var html = '<div class="strat-verdict">' + esc(s.reply || '').replace(/\n/g, '<br>') + '</div>';
  var dec = s.decodes || [];
  if(dec.length){
    html += '<div class="strat-raw-title">Décodages utilisés</div><div class="strat-raw">' +
      dec.map(function(d){ return 'il y a ' + esc(d.il_y_a_s) + 's · SNR ' + esc(d.snr) + ' dB · ' + esc(d.df) + ' Hz · ' + esc(d.msg); }).join('<br>') + '</div>';
  }
  setStratBody(html);
}
function openStratModal(call, inner){
  var ov = document.getElementById('stratOverlay');
  if(!ov){
    ov = document.createElement('div'); ov.id = 'stratOverlay';
    ov.onclick = function(e){ if(e.target === ov) closeStrat(); };
    ov.innerHTML = '<div class="strat-box"><div class="strat-head"><span id="stratTitle"></span>' +
      '<button onclick="closeStrat()" class="strat-x" aria-label="fermer">✕</button></div><div id="stratBody"></div></div>';
    document.body.appendChild(ov);
  }
  document.getElementById('stratTitle').textContent = '🧠 Stratégie — ' + call;
  setStratBody(inner);
  ov.style.display = 'flex';
}
function setStratBody(html){ var b = document.getElementById('stratBody'); if(b) b.innerHTML = html; }
function closeStrat(){ var ov = document.getElementById('stratOverlay'); if(ov) ov.style.display = 'none'; }

// QSY / pointer l'antenne depuis la need-list de l'activité (port de
// logx_chasse.html, mêmes endpoints — AUCUNE émission, juste régler la
// fréquence/l'antenne). Statut affiché dans #xotaQsyStatus, repli silencieux
// s'il est absent (ex. rôle changé entre-temps).
function _afficherStatutQsy(ok, msg){
  var el = document.getElementById('xotaQsyStatus');
  if(!el) return;
  el.textContent = msg;
  el.style.color = ok ? 'var(--green)' : 'var(--red)';
  setTimeout(function(){ el.style.color = ''; }, 4000);
}
async function qsyTo(freqKhz, call){
  try{
    const r = await fetch('/rig/qsy', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({freq_khz: parseFloat(freqKhz)})
    });
    const d = await r.json();
    _afficherStatutQsy(!!d.ok, d.ok ? ('📻 QSY ' + freqKhz + ' kHz → ' + call) : ('❌ ' + d.error));
  }catch(e){}
}
async function pointTo(az, call, band){
  try{
    const r = await fetch('/rotor/point', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({azimuth: parseFloat(az), bande: band || undefined})
    });
    const d = await r.json();
    _afficherStatutQsy(!!d.ok, d.ok ? ('🧭 Antenne → ' + Math.round(az) + '° vers ' + call) : ('❌ ' + d.error));
  }catch(e){}
}
// Glue fetch->render d'un panneau (le rendu vient du module, testé à part).
function _chargerPan(url, hostId, render){
  fetch(url).then(function(r){ return r.ok ? r.json() : {}; }).catch(function(){ return {}; })
    .then(function(d){ var h = document.getElementById(hostId); if(h) h.innerHTML = render(d); });
}
// Lignes « lieu » par programme (champs vérifiés dans logx_chasse.html).
function _placePota(s){ var P = window.LogxChassePanneaux; return '<span class="sr-ref">' + P.esc(s.reference) + '</span>' + (s.park_name ? ' · ' + P.esc(s.park_name) : ''); }
function _placeSota(s){ var P = window.LogxChassePanneaux; return '<span class="sr-ref">' + P.esc(s.reference) + '</span>' + (s.summit_name ? ' · ' + P.esc(s.summit_name) : '') + (s.alt_m ? ' (' + P.esc(s.alt_m) + 'm, ' + P.esc(s.points) + 'pts)' : ''); }

// Bandeau défilant d'info ambiante (DXpéditions ≤7j + propagation), affiché
// SOUS la grille. Branché SEULEMENT quand la grille est visible (jamais sur une
// redirection immédiate -- « ne pas rallonger le chemin quotidien »). Via le
// driver partagé : récupère les flux, rend les bandeaux ACTIFS, pose le ⚙
// afficher/masquer (comme LOGBOOK). Idempotent : brancher une seule fois même
// si _grille est rejouée (?changer=1).
let _bandeauxBranches = false;
function _brancherBandeaux(){
  if(_bandeauxBranches || !window.LogxBandeauxDriver) return;
  _bandeauxBranches = true;
  window.LogxBandeauxDriver.brancher({
    wrapId: 'bandeaux', activite: 'accueil',
    tags: ['hf'],                              // l'accueil met en avant le DX/propag HF
    ids: ['dxped', 'propag'],
    sources: { dxpeditions: '/data/dxpeditions_active', propagation: '/data/propagation' },
    besoins: { dxped: ['dxpeditions'], propag: ['propagation'] },
    defauts: { accueil: ['dxped', 'propag'] }
  });
}

// ── Entrée directe depuis CHASSE (fusion incr. 5b) ──────────────────────────
// logx_chasse.html redirige ici avec ?chasse=1 (incr. 5c, pas encore fait à
// cette étape) : on doit atterrir DIRECTEMENT sur les cibles en direct, sans
// repasser par « Qu'est-ce que tu fais aujourd'hui ? » ni par les 2 clics
// intermédiaires (carte activité + tuile rôle) — même doctrine « ne pas
// rallonger le chemin quotidien » que le bouton Reprendre. Le rôle mémorisé
// est respecté SAUF 'portable' pur (n'affiche pas la chasse, roleConfig) :
// on le force à 'chasse' plutôt que d'atterrir sur une page vide. 'mixte'
// (défaut) a déjà chasse:true, rien à changer.
function _demarrerDepuisRedirectChasse(){
  try{ localStorage.setItem('logx_activity', 'iota_pota'); }catch(e){}
  if(window.LogxXotaRole && LogxXotaRole.getRole() === 'portable') LogxXotaRole.setRole('chasse');
  const nav = document.getElementById('navChasse');
  if(nav && nav.classList) nav.classList.add('active');
  const intro = document.getElementById('intro');
  intro.innerHTML = '<div id="ciblesChasse"></div>';
  _revelerCiblesChasse();
  _brancherBandeaux();
}

// ?changer=1 force le réaffichage de la grille même si une activité est déjà
// mémorisée -- échappatoire explicite (lien "changer d'activité" ajouté dans
// CONFIG), « masquer ≠ bloquer l'accès ».
(function init(){
  // localStorage peut JETER (navigation privée, stockage désactivé, quota) :
  // hors try/catch, toute l'init plantait et la page restait sur « Chargement… ».
  // Même protection que les autres accès de ce fichier (l.41/46). En cas
  // d'échec, on retombe sur la grille de choix d'activité (repli sûr).
  let deja = null;
  try{ deja = localStorage.getItem('logx_activity'); }catch(e){}
  const params = new URLSearchParams(window.location.search);
  const forcer = params.get('changer') === '1';
  if(params.get('chasse') === '1'){ _demarrerDepuisRedirectChasse(); return; }
  // Décision F4GLD (28/08) : plus de redirection AUTOMATIQUE. On affiche le
  // cockpit + un bouton « Reprendre » (retour en UN clic, aucun allongement du
  // chemin quotidien). `?changer=1` masque le bouton (on vient justement changer).
  _grille(forcer ? null : deja);
})();
