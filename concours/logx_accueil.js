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
  {id:'iota_pota', label:'LOG IOTA / POTA',   hint:'activations terrain',             icon:_ICO.iota_pota},
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
  window.location.href = _pageSuivante();
}

function _grille(){
  const intro = document.getElementById('intro');
  intro.innerHTML =
    '<h1>Qu’est-ce que tu fais aujourd’hui ?</h1>' +
    '<p>Choisis ton activité — tu retrouveras toujours l’accès complet ensuite, et ton carnet reste unique quelle que soit la bande ou le mode.</p>' +
    '<div class="activity-grid" id="activityGrid"></div>';
  const grid = document.getElementById('activityGrid');
  grid.innerHTML = ACTIVITIES.map(a =>
    '<button type="button" class="activity-card' + (a.pilote ? ' pilote' : '') + '" onclick="choisirActivite(\'' + a.id + '\')">' +
      a.icon +
      '<span class="activity-name">' + a.label + '</span>' +
      '<span class="activity-hint">' + a.hint + '</span>' +
    '</button>'
  ).join('');
  _brancherBandeaux();
}

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
  if (deja && !forcer){
    window.location.href = _pageSuivante();
    return;
  }
  _grille();
})();
