// ─── SECOND ÉCRAN (fenêtres détachables) + SELF-SPOT (EV-7, docs/LogX_AI_PRD.md) ─
// 5e incrément du refactor EV-7 : extrait tel quel de logx_logbook.js (aucune
// restructuration nécessaire). Ouverture de fenêtres multi-moniteur (bandscope,
// panadapter, écran mural, bandes multiples) + publication de son propre spot
// sur le cluster DX / l'API POTA / SOTAwatch3.
//
// Dépend de globals restés dans logx_logbook.js (portée globale partagée via
// <script> classique, voir logx_logbook.html) : currentBand, currentMode,
// currentContest, myCall, myLocator, activationProgram, myActivationRef,
// _currentVisibleBands, BAND_FREQ, rigState, notify(), trF(), trT().
// Aucune fonction de ce fichier n'est appelée depuis le cœur (renderLog(),
// la sauvegarde d'un QSO, l'init de page) : toutes ne sont déclenchées que
// par un clic bouton (onclick HTML) ou, pour popoutWall/popoutBandes, par le
// menu ÉCRANS de logx_statusbar.js (fichier lui-même optionnel, invocation
// défensive via window[fn] — dépendance optionnel→optionnel).
function popoutScope(){
  // NOM DE FENÊTRE PAR BANDE. Avec le nom fixe « rc_scope », détacher le
  // bandscope sur une 2e bande ne créait pas de fenêtre : window.open()
  // réutilise celle qui porte déjà ce nom, donc la première changeait de bande
  // en silence. Surveiller 20 m et 2 m côte à côte était impossible sans que
  // rien ne l'explique.
  const b = String(currentBand || '144');
  window.open('/logx_scope.html?band=' + encodeURIComponent(b),
    'rc_scope_' + b.replace(/\./g, '_'),
    'width=1100,height=560,menubar=no,toolbar=no,location=no');
}
function popoutPanadapter(){
  // Fenêtre unique (nom fixe) : pas de sens d'en ouvrir deux, contrairement au
  // bandscope par bande — une seule entrée audio est branchée sur le poste.
  window.open('/logx_panadapter.html', 'rc_panadapter',
    'width=900,height=560,menubar=no,toolbar=no,location=no');
}
function popoutWall(){
  window.open('/logx_wall.html', 'rc_wall',
    'width=1280,height=720,menubar=no,toolbar=no,location=no');
}

// Surveillance simultanée de toutes les bandes : une fenêtre par bande, comme
// on le fait avec un logiciel de bureau à fenêtres multiples — sauf qu'ici ce
// sont des pages web, donc déplaçables sur un 2e écran ou même un autre poste.
//
// LES BANDES VIENNENT DE _currentVisibleBands — celles du concours, filtrées
// par les cases de CONFIG, exactement la liste des boutons BANDE affichés.
// Une liste en dur ouvrirait une fenêtre 50 MHz à quelqu'un qui ne fait que du
// HF, et oublierait les bandes ajoutées depuis (WARC).
//
// PAS DE REPLI SILENCIEUX si la liste est vide : mieux vaut le dire que
// d'ouvrir six fenêtres sur des bandes que l'opérateur n'utilise pas. (Premier
// jet de cette fonction : je visais une variable `activeBands` qui n'existe
// pas, et le garde `typeof` retombait TOUJOURS sur la liste en dur — sans que
// rien ne le signale.)
function popoutBandes(){
  const bandes = (typeof _currentVisibleBands !== 'undefined' && _currentVisibleBands)
    ? _currentVisibleBands.slice() : [];
  if(!bandes.length){
    notify("Aucune bande active : choisis un concours ou coche des bandes dans CONFIG");
    return;
  }
  if(bandes.length > 12){
    // Garde-fou : douze fenêtres, c'est déjà tout un écran. Au-delà, le
    // navigateur bloque en général l'ouverture et l'utilisateur ne comprend
    // pas pourquoi seules les premières sont apparues.
    notify('Trop de bandes actives (' + bandes.length + ') : ouvre-les au besoin depuis ce bouton bande par bande');
    return;
  }
  // Décalage en cascade : superposées, elles seraient indiscernables.
  bandes.forEach((b, i) => {
    const x = 40 + i * 40, y = 40 + i * 30;
    window.open('/logx_bande.html?band=' + encodeURIComponent(b),
      'rc_bande_' + String(b).replace('.', '_'),
      `width=420,height=520,left=${x},top=${y},menubar=no,toolbar=no,location=no`);
  });
}

// ─── SELF-SPOT (publier son spot sur le cluster DX avec sa fréquence) ─────────
async function selfSpot(){
  // Fréquence : champ saisi > radio (CAT) > fréquence d'appel de la bande
  let mhz = parseFloat(document.getElementById('inputFreq')?.value);
  if(!isFinite(mhz) || mhz <= 0){
    if(typeof rigState === 'object' && rigState && rigState.freq_khz > 0) mhz = rigState.freq_khz / 1000;
    else mhz = parseFloat(BAND_FREQ[currentBand] || '0');
  }
  if(!isFinite(mhz) || mhz <= 0){ notify('Fréquence inconnue — saisis-la dans le champ FRÉQUENCE.'); return; }
  const freq_khz = Math.round(mhz * 1000 * 10) / 10;   // MHz → kHz (commande DX Spider)
  if(!(await _confirmDupBanner(trF('Publier ce spot sur le cluster DX ?\n\n{call}   {mhz} MHz   {mode}\n\n⚠️ Vérifie que l\'auto-spot est autorisé par le règlement du concours.',
              {call: myCall, mhz: mhz.toFixed(3), mode: currentMode || ''}), 'Publier', 'Annuler'))) return;
  const btn = document.getElementById('selfSpotBtn');
  const orig = btn ? btn.textContent : '';
  if(btn){ btn.disabled = true; btn.textContent = '📡 …'; }
  try{
    const r = await fetch('/cluster/spot', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({freq_khz, comment: 'CQ ' + ((currentContest||'').replace(/_/g,' '))})});
    const d = await r.json();
    if(d.ok && d.confirmed) notify(trF('📡 Spot publié et confirmé : {call}  {mhz} MHz', {call: myCall, mhz: mhz.toFixed(3)}));
    else if(d.ok) notify(trF('📡 Spot envoyé (non confirmé par le nœud) : {call}  {mhz} MHz\nVérifie sur le cluster qu\'il apparaît.', {call: myCall, mhz: mhz.toFixed(3)}));
    else notify(trF('❌ Self-spot : {err}', {err: d.error || trT('échec')}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
  finally{ if(btn){ btn.disabled = false; btn.textContent = orig || '📡 SELF-SPOT'; } }
}

// ─── SELF-SPOT POTA (publier son activation sur l'API publique api.pota.app) ─
async function selfSpotPota(){
  if(activationProgram !== 'POTA' || !myActivationRef) return;
  // Même repli fréquence que selfSpot() : champ saisi > radio (CAT).
  let mhz = parseFloat(document.getElementById('inputFreq')?.value);
  if(!isFinite(mhz) || mhz <= 0){
    if(typeof rigState === 'object' && rigState && rigState.freq_khz > 0) mhz = rigState.freq_khz / 1000;
  }
  if(!isFinite(mhz) || mhz <= 0){ notify('Fréquence inconnue — saisis-la dans le champ FRÉQUENCE.'); return; }
  const freq_khz = Math.round(mhz * 1000 * 10) / 10;
  if(!(await _confirmDupBanner(trF('Publier ce spot sur l\'API publique POTA (api.pota.app) ?\n\n{call}   {ref}   {mhz} MHz   {mode}\n\nVisible immédiatement par tous les chasseurs, sans authentification.',
              {call: myCall, ref: myActivationRef, mhz: mhz.toFixed(3), mode: currentMode || ''}), 'Publier', 'Annuler'))) return;
  const btn = document.getElementById('actSpotBtn');
  const orig = btn ? btn.textContent : '';
  if(btn){ btn.disabled = true; btn.textContent = '📡 …'; }
  try{
    const r = await fetch('/pota/spot', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({reference: myActivationRef, freq_khz, mode: currentMode || ''})});
    const d = await r.json();
    if(d.ok) notify(trF('📡 Spot POTA publié : {call}  {ref}  {mhz} MHz', {call: myCall, ref: myActivationRef, mhz: mhz.toFixed(3)}));
    else notify(trF('❌ Self-spot POTA : {err}', {err: d.error || trT('échec')}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
  finally{ if(btn){ btn.disabled = false; btn.textContent = orig || '📡 SE SPOTTER'; } }
}

// Le bouton SE SPOTTER est partagé entre programmes d'activation — un seul
// point d'entrée qui redirige vers l'implémentation du programme actif.
function selfSpotActivation(){
  if(activationProgram === 'POTA') return selfSpotPota();
  if(activationProgram === 'SOTA') return selfSpotSota();
}

// ─── SELF-SPOT SOTA (publier son activation sur SOTAwatch3, cf.
// logx_sota_spot.post_spot) — reste INACTIF tant que le clientId SOTA et
// l'accord préalable de l'équipe SOTA n'ont pas été configurés dans CONFIG
// (le serveur renvoie alors un message d'erreur explicite, voir post_spot). ─
async function selfSpotSota(){
  if(activationProgram !== 'SOTA' || !myActivationRef) return;
  let mhz = parseFloat(document.getElementById('inputFreq')?.value);
  if(!isFinite(mhz) || mhz <= 0){
    if(typeof rigState === 'object' && rigState && rigState.freq_khz > 0) mhz = rigState.freq_khz / 1000;
  }
  if(!isFinite(mhz) || mhz <= 0){ notify('Fréquence inconnue — saisis-la dans le champ FRÉQUENCE.'); return; }
  const freq_khz = Math.round(mhz * 1000 * 10) / 10;
  if(!(await _confirmDupBanner(trF('Publier ce spot sur SOTAwatch3 ?\n\n{call}   {ref}   {mhz} MHz   {mode}\n\nNécessite une connexion SOTA configurée dans CONFIG → EXPÉDITION/PORTABLE.',
              {call: myCall, ref: myActivationRef, mhz: mhz.toFixed(3), mode: currentMode || ''}), 'Publier', 'Annuler'))) return;
  const btn = document.getElementById('actSpotBtn');
  const orig = btn ? btn.textContent : '';
  if(btn){ btn.disabled = true; btn.textContent = '📡 …'; }
  try{
    const r = await fetch('/sota/spot', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({reference: myActivationRef, freq_khz, mode: currentMode || ''})});
    const d = await r.json();
    if(d.ok) notify(trF('📡 Spot SOTA publié : {call}  {ref}  {mhz} MHz', {call: myCall, ref: myActivationRef, mhz: mhz.toFixed(3)}));
    else notify(trF('❌ Self-spot SOTA : {err}', {err: d.error || trT('échec')}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
  finally{ if(btn){ btn.disabled = false; btn.textContent = orig || '📡 SE SPOTTER'; } }
}
