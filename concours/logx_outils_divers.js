// EV-7 phase 2, 36e increment : OUTILS DIVERS (SO2R bascule d'emission,
// sauvegarde immediate, QSO TIMER, bip audio confirmation) -- 4 candidats
// FAIBLE regroupes dans un seul fichier (meme motif que le combo du 8e
// increment), extraits de logx_logbook.js (docs/LogX_AI_PRD.md). Charge en
// <script> classique dans logx_logbook.html, AVANT logx_logbook.js --
// portee globale partagee (comme tous les fichiers EV-7).
//
// Contient : updateQsoTimer() [+ son setInterval], so2rBasculer()/
// so2rAfficher()/so2rRafraichir()/_so2rFocus, backupNow(), bipEnabled/
// initBipBtn()/toggleBip().
//
// Dependances croisees verifiees sures :
// - updateQsoTimer() lit lastQsoTime (coeur, ecrite par submitQSO() a 3
//   sites de succes + un site d'initialisation) -- RESTEE dans le coeur,
//   seule la fonction qui la lit a migre (meme motif que _myVersion au
//   35e increment).
// - bipEnabled/initBipBtn()/toggleBip() migrent EN BLOC (declaration +
//   IIFE + toggle) -- meme patron deja en production pour esmMode
//   (declare dans logx_esm_callbot.js, lu par playBeep() dans le coeur).
//   playBeep() (coeur, appelee par submitQSO()) et logx_lookup.js (deja
//   extrait) continuent de lire bipEnabled sans risque d'ordre : ce
//   fichier charge TOUJOURS avant logx_logbook.js, et logx_lookup.js lit
//   bipEnabled en corps de fonction uniquement.
// - initBipBtn() est une IIFE executee immediatement au chargement du
//   script (top-level) -- sans risque : elle ne touche que son etat local
//   et un element DOM par id, deja present au moment ou tous les <script>
//   de fin de page s'executent (meme convention que tout le reste EV-7).
// - _so2rFocus n'a aucun lecteur/ecrivain hors de ce bloc -- migre en bloc
//   sans risque.
// - backupNow() est une action pure (aucun etat partage).
// - Hors chemin critique (verifie explicitement, 5e inventaire EV-7) :
//   aucune des fonctions de ce fichier n'est appelee par setupDone(),
//   clearForm(), submitQSO(), pickBand(), onFreqInput() ou
//   prefillSetupFromConfig().

function updateQsoTimer(){
  const el = document.getElementById('sbQsoTimer');
  if(!el) return;
  if(!lastQsoTime || !qsoLog.length){
    el.textContent = '—';
    el.style.color = 'var(--muted)';
    return;
  }
  const sec = Math.floor((Date.now() - lastQsoTime) / 1000);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  el.textContent = m > 0 ? `${m}m ${s}s` : `${s}s`;
  // Couleur selon l'urgence
  el.style.color = m >= 5 ? 'var(--red)' : m >= 2 ? 'var(--yellow)' : 'var(--green)';
}
setInterval(updateQsoTimer, 1000);

// ─── SO2R : bascule d'émission ───────────────────────────────────────────────
// L'état vit CÔTÉ SERVEUR : le band map, la barre de statut et toute page
// ouverte doivent voir la même radio en émission. Le tenir dans le navigateur
// ferait diverger deux écrans du même poste.
let _so2rFocus = 1;

async function so2rBasculer(radio){
  try{
    const res = await fetch('/so2r/focus', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(radio ? {radio} : {})}).then(r => r.json());
    if(res.focus){ _so2rFocus = res.focus; so2rAfficher(res); }
    if(!res.ok) notify(trF('❌ SO2R : {err}', {err: res.error || 'échec'}));
    else notify(trF('🎚 Émission → radio {n}', {n: res.focus}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}

function so2rAfficher(etat){
  const el = document.getElementById('so2rIndicateur');
  if(!el) return;
  // L'indicateur n'apparaît QUE si une seconde radio est déclarée : sur une
  // station mono-radio, un voyant « RADIO 1 » permanent serait du bruit.
  if(!etat || !etat.configure){ el.style.display = 'none'; return; }
  el.style.display = '';
  el.textContent = '🎚 TX R' + (etat.focus || 1) + (etat.ecoute ? ' · ' + etat.ecoute : '');
}

async function so2rRafraichir(){
  try{
    const etat = await fetch('/so2r/state').then(r => r.json());
    if(etat && etat.focus){ _so2rFocus = etat.focus; }
    so2rAfficher(etat);
  }catch(e){ /* serveur injoignable : on garde le dernier état connu */ }
}

// ─── SAUVEGARDE IMMÉDIATE (dossier cloud/NAS) ────────────────────────────────
async function backupNow(){
  try{
    const r = await fetch('/backup/now', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const d = await r.json();
    if(d.ok) notify(trF('💾 Sauvegarde OK → {folder} ({n} fichiers)', {folder: d.folder, n: d.files.length}));
    else notify(trF('❌ {err} — configure le dossier dans CONFIG', {err: d.error || trT('sauvegarde impossible')}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}

// ─── AUDIO BIP CONFIRMATION QSO ──────────────────────────────────────────────
let bipEnabled = (localStorage.getItem('rc_bip') !== 'off');
(function initBipBtn(){
  const btn = document.getElementById('bipToggle');
  if(btn) btn.textContent = bipEnabled ? '🔔' : '🔕';
})();

function toggleBip(){
  bipEnabled = !bipEnabled;
  localStorage.setItem('rc_bip', bipEnabled ? 'on' : 'off');
  const btn = document.getElementById('bipToggle');
  if(btn) btn.textContent = bipEnabled ? '🔔' : '🔕';
}
