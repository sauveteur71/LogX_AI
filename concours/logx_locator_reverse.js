// EV-7 phase 2 (docs/LogX_AI_PRD.md) -- 21e increment : REVERSE LOOKUP
// LOCATOR -> INDICATIFS + COMPAS INLINE, extrait tel quel de logx_logbook.js.
// Charge en <script> classique dans logx_logbook.html AVANT logx_logbook.js,
// portee globale partagee (meme convention que les 20 increments precedents).
//
// Contenu : locAcResults/locAcSelected (etat autocomplete locator),
// searchByLocator(), showLocAC()/hideLocAC()/selectLocAC(),
// onLocatorKeydown() ; _lastCompassDeg (etat compas), showCompassInline(),
// pointAntennaFromCompass(), hideCompassInline().
//
// Grep exhaustif fait AVANT extraction (methode validee aux 19e/20e
// increments, voir memoire projet piege-appel-top-level-casse-tests-hote-
// entier) : AUCUN appel top-level restant dans logx_logbook.js vers un
// symbole de ce fichier -- les 4 sites qui appellent hideCompassInline()
// depuis logx_logbook.js (onCallInput(), clearForm()) sont tous a
// l'interieur d'un corps de fonction. Donc PAS de risque du style
// renderVoiceDynPanel()/voiceRefreshSlots() cette fois : aucun fichier de
// test supplementaire a corriger pour un chargement de logx_logbook.js
// seul.
//
// Dependance coeur->optionnel (sens autorise) deja documentee par
// logx_daynight.js (18e increment, section Reverse Lookup Locator alors
// "pas encore extraite") : onLocatorInput() (logx_daynight.js) appelle
// searchByLocator()/showLocAC()/hideLocAC()/showCompassInline()/
// hideCompassInline() -- toujours a l'interieur du corps de la fonction,
// jamais au chargement, donc sans risque malgre le nombre de dependances.
// logx_lookup.js (applyCallData()) appelle aussi hideLocAC() de la meme
// facon.
//
// Dependance optionnel->coeur (sens autorise, fonctions seulement) :
// qsoLog, callDB (logx_lookup.js), usageMode, isDup, currentBand,
// lookupDXCC() (logx_dxcc_lookup.js), escHtml, onCallInput, onLocatorInput,
// submitQSO, cardinalDir() (reste dans logx_logbook.js), rotorState,
// notify, trF, fetch.

// ─── REVERSE LOOKUP LOCATOR → INDICATIFS ─────────────────────────────────────
let locAcResults = [];
let locAcSelected = -1;

function searchByLocator(prefix){
  prefix = prefix.toUpperCase();
  const seen = new Set();
  const out  = [];

  // 1. Log courant : stations vues à ce locator
  for(const q of qsoLog){
    if(q.locator && q.locator.toUpperCase().startsWith(prefix) && !seen.has(q.call)){
      seen.add(q.call);
      out.push({call:q.call, locator:q.locator, src:'log', dup: usageMode !== 'simple' && isDup(q.call,currentBand)});
      if(out.length >= 12) return out;
    }
  }

  // 2. Base callDB
  for(const call in callDB){
    const d = callDB[call];
    if(d.locator && d.locator.toUpperCase().startsWith(prefix) && !seen.has(call)){
      seen.add(call);
      out.push({call, locator:d.locator, dept:d.dept||'', src:'db', dup: usageMode !== 'simple' && isDup(call,currentBand)});
      if(out.length >= 12) return out;
    }
  }
  return out;
}

function showLocAC(results){
  const box = document.getElementById('locAcBox');
  if(!box) return;
  locAcResults = results || [];
  locAcSelected = -1;
  if(!locAcResults.length){ hideLocAC(); return; }
  box.innerHTML = locAcResults.map((item, idx) => {
    const dup     = item.dup || false;
    const dxcc    = lookupDXCC(item.call);
    const flag    = dxcc ? dxcc.flag : '';
    const srcTag  = item.src === 'log'
      ? `<span style="color:var(--green);font-size:13px;font-weight:700">📋 LOG</span>`
      : `<span style="color:var(--muted);font-size:14px">🗂️</span>`;
    const dupTag  = dup ? `<span style="color:var(--red);font-size:14px;font-weight:800">DUPE</span>` : '';
    const deptStr = item.dept ? `<span style="color:var(--yellow);font-size:14px;font-weight:700">dpt${escHtml(item.dept)}</span>` : '';
    const locStr  = `<span style="color:var(--accent2);font-size:14px;font-weight:800">${escHtml(item.locator)}</span>`;
    return `<div class="ac-item${dup?' dupe-item':''}" data-idx="${idx}" onmousedown="selectLocAC(${idx})">`
      + `<span style="font-size:16px">${flag}</span>`
      + `<b style="font-size:19px;font-weight:900;min-width:110px;letter-spacing:1px;${dup?'color:var(--red)':'color:var(--green)'}">${escHtml(item.call)}</b>`
      + `<span style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;flex:1">${locStr}${deptStr}${dupTag}</span>`
      + srcTag
      + `</div>`;
  }).join('');
  box.style.display = 'block';
}

function hideLocAC(){
  const box = document.getElementById('locAcBox');
  if(box) box.style.display = 'none';
  locAcSelected = -1;
}

function selectLocAC(idx){
  const item = locAcResults[idx];
  if(!item) return;
  hideLocAC();
  // Remplir l'indicatif
  const callField = document.getElementById('inputCall');
  if(callField && !callField.value){
    callField.value = item.call;
    onCallInput();
  }
  // Confirmer le locator exact
  const locField = document.getElementById('inputLocator');
  if(locField) locField.value = item.locator;
  onLocatorInput();
}

function onLocatorKeydown(e){
  const box = document.getElementById('locAcBox');
  const open = box && box.style.display !== 'none' && locAcResults.length;
  if(e.key === 'ArrowDown' && open){
    e.preventDefault();
    locAcSelected = Math.min(locAcSelected + 1, locAcResults.length - 1);
    document.querySelectorAll('#locAcBox .ac-item').forEach((it,i) => it.classList.toggle('selected', i === locAcSelected));
  } else if(e.key === 'ArrowUp' && open){
    e.preventDefault();
    locAcSelected = Math.max(locAcSelected - 1, 0);
    document.querySelectorAll('#locAcBox .ac-item').forEach((it,i) => it.classList.toggle('selected', i === locAcSelected));
  } else if(e.key === 'Enter' && open && locAcSelected >= 0){
    e.preventDefault();
    selectLocAC(locAcSelected);
  } else if(e.key === 'Escape'){
    hideLocAC();
  } else if(e.key === 'Enter' && !open){
    e.preventDefault();
    submitQSO();
  }
}

// ─── COMPAS INLINE ────────────────────────────────────────────────────────────
let _lastCompassDeg = null;   // cap courant, pour le bouton « pointer »

function showCompassInline(deg, distKm, pts){
  const el      = document.getElementById('compassInline');
  const needle  = document.getElementById('compassNeedle');
  const degEl   = document.getElementById('compassDeg');
  const cardEl  = document.getElementById('compassCard');
  const distEl  = document.getElementById('compassDist');
  const ptsEl   = document.getElementById('compassPts');
  if(!el || !needle) return;
  needle.setAttribute('transform', `rotate(${deg},30,30)`);
  if(degEl)  degEl.textContent  = `${deg}°`;
  if(cardEl) cardEl.textContent = cardinalDir(deg);
  if(distEl) distEl.textContent = `${Math.round(distKm)} km`;
  if(ptsEl)  ptsEl.textContent  = `${pts} pts`;
  el.classList.add('show');
  // Bouton « pointer » : visible seulement si le rotor est piloté
  _lastCompassDeg = deg;
  const pb = document.getElementById('pointAntennaBtn');
  if(pb) pb.style.display = (typeof rotorState !== 'undefined' && rotorState.enabled) ? '' : 'none';
}

function pointAntennaFromCompass(){
  if(_lastCompassDeg == null) return;
  // La BANDE courante part avec la consigne : le serveur tourne alors le rotor
  // de l'antenne active sur cette bande — et lui seul — avec son décalage
  // mécanique. Sans elle, une station à trois pylônes voyait toujours tourner
  // le même (revue 01/08/2026).
  fetch('/rotor/point', {method:'POST', headers:{'Content-Type':'application/json'},
                         body: JSON.stringify({azimuth: _lastCompassDeg,
                           bande: (typeof currentBand !== 'undefined') ? currentBand : undefined})})
    .then(r=>r.json()).then(d=>{
      notify(d.ok ? trF('🧭 Antenne pointée sur {deg}°', {deg: _lastCompassDeg}) : trF('❌ {err}', {err: d.error}));
    }).catch(()=>notify('Rotor injoignable.'));
}
function hideCompassInline(){
  const el = document.getElementById('compassInline');
  if(el) el.classList.remove('show');
}
