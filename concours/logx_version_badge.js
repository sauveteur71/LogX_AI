// EV-7 phase 2, 35e increment : BADGE VERSION RESEAU + MISE A JOUR VIA
// PASSERELLE/PAIR -- extrait de logx_logbook.js (docs/LogX_AI_PRD.md). Charge
// en <script> classique dans logx_logbook.html, AVANT logx_logbook.js --
// portee globale partagee (comme tous les fichiers EV-7).
//
// Contient : _versionMismatches(), updateVersionStatus(),
// findNetworkUpdatePath(), _renderNetworkUpdatePath(), startNetworkUpdate(),
// _pollNetworkUpdateStatus(), installNetworkUpdate(),
// _pollServerBackUpAfterNetworkUpdate().
//
// IMPORTANT -- contrairement a la plupart des increments EV-7, l'ETAT
// (_myVersion, _lastServerVersion, _lastPeerList) reste DELIBEREMENT dans le
// coeur (logx_logbook.js) : _myVersion est ecrite par initShareLink() (coeur),
// figee UNE SEULE FOIS depuis /network/info → app_version, et lue par
// fetchLog() (parametre ?ver= de chaque poll /log/list) -- deux sites du
// coeur totalement en dehors de ce bloc. Seules les FONCTIONS qui operent
// sur cet etat ont ete extraites ici ; _lastServerVersion/_lastPeerList sont
// ecrites par updateVersionStatus() (dans ce fichier, alimentee par
// /log/status via refreshCluster()) et lues par findNetworkUpdatePath()
// (aussi dans ce fichier), donc sans risque d'ordre entre elles.
//
// Dependances croisees verifiees sures :
// - Aucun appel top-level : les 8 fonctions ne sont invoquees qu'en corps de
//   fonction (jamais au chargement direct du script).
// - logx_lookup.js (deja extrait, charge AVANT ce fichier) appelle
//   updateVersionStatus(data) en corps de refreshCluster() -- direction
//   inhabituelle deja rencontree (MACROS 32e increment, FILTRE SPOTS 33e
//   increment) : sans risque tant que l'appel reste en corps de fonction.
// - logx_verif_panel.js (deja extrait, charge AVANT ce fichier) appelle
//   _versionMismatches(_lastServerVersion, _myVersion, _lastPeerList) en
//   corps de showChecklist() -- meme motif, meme raisonnement.
// - logx_logbook.html reference findNetworkUpdatePath() via un attribut
//   onclick (resolu au clic, jamais au chargement).
// - Hors chemin critique (verifie explicitement, 4e inventaire EV-7).

// Liste les postes (soi-même inclus) dont la version déclarée diffère de la
// version SERVEUR actuelle (référence unique — voir logx_http.APP_VERSION).
// Partagée entre le badge de la barre réseau et l'item CHECKLIST pour ne
// jamais faire diverger les deux affichages.
function _versionMismatches(serverVer, myVer, peerList){
  const out = [];
  if(myVer && serverVer && myVer !== serverVer) out.push({ip: 'ce poste', version: myVer});
  (peerList || []).forEach(p => {
    if(p.version && serverVer && p.version !== serverVer) out.push({ip: p.ip, version: p.version});
  });
  return out;
}

// Met à jour le badge "⚠️ versions différentes" de la barre réseau + le
// détail (tooltip) de "Postes connectés". Un écart n'est JAMAIS bloquant :
// c'est un indicateur visuel, l'opérateur décide quoi en faire (recharger
// la page, prévenir l'hôte...).
function updateVersionStatus(data){
  const serverVer = data.app_version || null;
  const peerList  = data.peer_list || [];
  _lastServerVersion = serverVer;
  _lastPeerList = peerList;
  const warnEl  = document.getElementById('netVersionWarn');
  const peersEl = document.getElementById('netPeers');
  if(!serverVer) return;
  const mismatches = _versionMismatches(serverVer, _myVersion, peerList);
  if(warnEl){
    if(mismatches.length){
      warnEl.style.display = 'inline-flex';
      warnEl.title = 'Versions différentes détectées (recharge la page pour te mettre à jour) :\n'
        + mismatches.map(m => `${m.ip} : v${m.version}`).join('\n')
        + `\nRéférence serveur : v${serverVer}`;
    } else {
      warnEl.style.display = 'none';
      warnEl.title = '';
    }
  }
  if(peersEl && peerList.length){
    peersEl.title = 'Postes connectés :\n' + peerList.map(p => {
      const flag = (p.version && p.version !== serverVer) ? ' ⚠️' : '';
      return `${p.ip} — v${p.version || '?'}${flag}`;
    }).join('\n');
  }
  // Bouton "🌐 màj réseau" (voir findNetworkUpdatePath ci-dessous) : affiché
  // uniquement quand CE poste (pas un autre pair) tourne une version
  // différente de celle du serveur — c'est le seul cas où CE poste a besoin
  // de récupérer un exécutable plus récent via le réseau local.
  const pathBtn = document.getElementById('netUpdatePathBtn');
  if(pathBtn){
    const myMismatch = !!(_myVersion && serverVer && _myVersion !== serverVer);
    pathBtn.style.display = myMismatch ? 'inline-block' : 'none';
    if(!myMismatch){
      const resEl = document.getElementById('netUpdatePathResult');
      if(resEl) resEl.textContent = '';
    }
  }
}

// ── Mise à jour réseau (relais B / pair-à-pair C secours) ────────────────────
// Complète le badge de version ci-dessus : quand CE poste tourne une version
// différente de celle du serveur ET n'a lui-même pas d'accès internet direct
// ou dégradé (cas DXpédition/contest — voir docstring de logx_update.py),
// permet de récupérer l'exécutable via un AUTRE poste du réseau local au
// lieu de GitHub directement. TOUJOURS 3 clics explicites distincts —
// jamais de sondage ni de téléchargement automatique en tâche de fond :
//   1) "🌐 màj réseau" → découverte seule (ne télécharge rien)
//   2) "mettre à jour via…" → déclenche le vrai transfert vérifié
//   3) "installer et redémarrer" → applique (comme le chemin GitHub direct)
// Chemin (B) passerelle proposé EN PRIORITÉ (bouton bleu/accent2) ; le
// chemin (C) pair-à-pair n'apparaît QUE si aucune passerelle n'a été
// trouvée, et reste étiqueté "secours" (bouton jaune, libellé explicite)
// pour que l'opérateur voie tout de suite qu'il s'agit d'un repli, pas du
// chemin habituel.
async function findNetworkUpdatePath(){
  const resEl = document.getElementById('netUpdatePathResult');
  if(!resEl) return;
  const ips = (_lastPeerList || []).map(p => p.ip).filter(Boolean);
  if(!ips.length){
    resEl.textContent = "aucun autre poste détecté sur le réseau pour l'instant.";
    return;
  }
  resEl.textContent = 'recherche sur le réseau…';
  try{
    const r = await fetch('/app/update_network_scan', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ips})
    });
    const d = await r.json();
    _renderNetworkUpdatePath(d);
  }catch(e){
    resEl.textContent = 'recherche impossible.';
  }
}

function _renderNetworkUpdatePath(d){
  const resEl = document.getElementById('netUpdatePathResult');
  if(!resEl) return;
  if(d.gateways && d.gateways.length){
    const ip = d.gateways[0];
    resEl.innerHTML = 'passerelle trouvée : ' + escHtml(ip)
      + `<button class="net-upd-gateway" data-mode="gateway" data-ip="${escHtml(ip)}">mettre à jour via cette passerelle</button>`;
  } else if(d.peers && d.peers.length){
    const ip = d.peers[0];
    resEl.innerHTML = 'aucune passerelle — SECOURS, pair vérifié trouvé : ' + escHtml(ip)
      + `<button class="net-upd-peer" data-mode="peer" data-ip="${escHtml(ip)}">mettre à jour via ce pair (secours, vérifié)</button>`;
  } else {
    resEl.textContent = 'aucune passerelle ni pair disponible sur le réseau pour le moment.';
    return;
  }
  const btn = resEl.querySelector('button[data-mode]');
  if(btn) btn.addEventListener('click', () => startNetworkUpdate(btn.dataset.mode, btn.dataset.ip));
}

async function startNetworkUpdate(mode, ip){
  const resEl = document.getElementById('netUpdatePathResult');
  if(resEl) resEl.textContent = (mode === 'gateway'
    ? 'téléchargement via la passerelle ' : 'téléchargement (SECOURS) via le pair ') + ip + '…';
  try{
    const r = await fetch('/app/update_download_via_network', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({mode, ips: [ip]})
    });
    const d = await r.json();
    if(!d.ok){
      if(resEl) resEl.textContent = 'échec : ' + (d.error || '?');
      return;
    }
    _pollNetworkUpdateStatus();
  }catch(e){
    if(resEl) resEl.textContent = 'échec réseau.';
  }
}

function _pollNetworkUpdateStatus(){
  fetch('/app/update_status').then(r => r.ok ? r.json() : null).then(d => {
    const resEl = document.getElementById('netUpdatePathResult');
    if(!d || !resEl) return;
    if(d.status === 'downloading'){
      resEl.textContent = `téléchargement… ${d.pct || 0}%`;
      setTimeout(_pollNetworkUpdateStatus, 800);
    } else if(d.status === 'done' && d.verified){
      const via = d.via === 'peer' ? 'pair — SECOURS, vérifié' : 'passerelle';
      resEl.innerHTML = `✅ v${d.version} vérifiée (via ${via}${d.via_peer ? ' ' + d.via_peer : ''}) `
        + `<button class="net-upd-gateway" onclick="installNetworkUpdate()">installer et redémarrer</button>`;
    } else if(d.status === 'error'){
      resEl.textContent = 'échec : ' + (d.error || '?');
    }
  }).catch(()=>{});
}

function installNetworkUpdate(){
  const resEl = document.getElementById('netUpdatePathResult');
  if(resEl) resEl.textContent = 'redémarrage…';
  fetch('/app/update_install', {method: 'POST', headers: {'Content-Type': 'application/json'}})
    .then(()=> setTimeout(_pollServerBackUpAfterNetworkUpdate, 2500));
}

function _pollServerBackUpAfterNetworkUpdate(){
  // Même mécanisme que pollServerBackUp() de logx_statusbar.js (le serveur
  // coupe volontairement le processus après /app/update_install pour que le
  // script auxiliaire remplace l'exécutable) — dupliqué ici volontairement :
  // logx_statusbar.js est une IIFE qui n'expose pas cette fonction.
  fetch('/data/rules_status', {cache: 'no-store'}).then(r => {
    if(r.ok) location.reload();
    else setTimeout(_pollServerBackUpAfterNetworkUpdate, 2000);
  }).catch(()=> setTimeout(_pollServerBackUpAfterNetworkUpdate, 2000));
}
