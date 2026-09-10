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
function _revelerCiblesChasse(){
  var el = document.getElementById('ciblesChasse');
  if(!el) return;
  // Panneaux d'activation POTA/SOTA/WWFF/WCA/DXpéditions (fusion 4b+4c) +
  // need-list cluster avec QSY/rotor (fusion 4d, endpoints /rig/qsy et
  // /rotor/point — AUCUNE émission, juste régler la fréquence/l'antenne).
  el.innerHTML =
    '<h2 class="xota-acc-h">Cibles en direct</h2>' +
    '<div class="xota-panneaux">' +
      '<div class="xota-pan"><div class="xota-pan-h">POTA</div><div id="panPota" class="scroll-list"></div></div>' +
      '<div class="xota-pan"><div class="xota-pan-h">SOTA</div><div id="panSota" class="scroll-list"></div></div>' +
      '<div class="xota-pan"><div class="xota-pan-h">WWFF</div><div id="panWwff" class="scroll-list"></div></div>' +
      '<div class="xota-pan"><div class="xota-pan-h">WCA / COTA (annoncé)</div><div id="panWca" class="scroll-list"></div></div>' +
      '<div class="xota-pan"><div class="xota-pan-h">DXpéditions</div><div id="panDx" class="scroll-list"></div></div>' +
    '</div>' +
    '<div class="xota-pan xota-pan-full"><div class="xota-pan-h">Need list — cluster <span id="xotaQsyStatus" class="xota-qsy-status"></span></div><div id="ckNeedList" class="scroll-list"></div></div>';
  if(typeof fetch !== 'function') return;
  var P = window.LogxChassePanneaux; if(!P) return;
  _chargerPan('/data/pota_spots', 'panPota', function(d){ return P.renderActivationRows((d && d.spots) || [], {place:_placePota}); });
  _chargerPan('/data/sota_spots', 'panSota', function(d){ return P.renderActivationRows((d && d.spots) || [], {place:_placeSota}); });
  _chargerPan('/data/wwff_spots', 'panWwff', function(d){ return P.renderActivationRows((d && d.spots) || [], {place:_placePota}); }); // WWFF : même champ park_name que POTA
  _chargerPan('/data/wca_planned', 'panWca', function(d){ return P.renderWcaRows((d && d.items) || [], {max:15}); });
  _chargerPan('/data/dxpeditions_active', 'panDx', function(d){ return P.renderDxRows((d && d.expeditions) || [], {max:15}); });
  // Need-list : lit l'état radio/rotor AVANT de rendre (comme logx_chasse.html)
  // pour savoir si les boutons QSY/rotor doivent apparaître par ligne.
  Promise.all([
    fetch('/rig/state').then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; }),
    fetch('/rotor/state').then(function(r){ return r.ok ? r.json() : null; }).catch(function(){ return null; })
  ]).then(function(states){
    var rigEnabled = !!(states[0] && states[0].enabled);
    var rotorEnabled = !!(states[1] && states[1].enabled);
    _chargerPan('/data/spots_ranked', 'ckNeedList', function(d){
      return P.renderNeedList((d && d.spots) || [], {max:15, rigEnabled:rigEnabled, rotorEnabled:rotorEnabled});
    });
  });
}

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
  const forcer = new URLSearchParams(window.location.search).get('changer') === '1';
  // Décision F4GLD (28/08) : plus de redirection AUTOMATIQUE. On affiche le
  // cockpit + un bouton « Reprendre » (retour en UN clic, aucun allongement du
  // chemin quotidien). `?changer=1` masque le bouton (on vient justement changer).
  _grille(forcer ? null : deja);
})();
