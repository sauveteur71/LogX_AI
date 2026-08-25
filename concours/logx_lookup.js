// EV-7 phase 2, 17e increment (docs/LogX_AI_PRD.md) -- resolution
// d'indicatif : lookup HamQTH distant, cache cluster (telnet DX cluster),
// base locale calldb, autocomplete indicatif -- extrait tel quel de
// logx_logbook.js (extraction MECANIQUE). Charge en <script> classique
// dans logx_logbook.html, AVANT logx_logbook.js (portee globale partagee).
//
// 6 variables d'etat privees au bloc (grep exhaustif sur tout le depot) :
// clusterCache, clusterLastRefresh, callLookupTimer, callDB, acResults,
// acSelected -- SAUF callDB, lue (jamais ecrite) depuis logx_verif_panel.js
// (deja un fichier EV-7 extrait, corps de fonction uniquement, sans risque
// d'ordre de <script>) et callLookupTimer, utilisee depuis onCallInput()/
// clearForm() dans logx_logbook.js (corps de fonction uniquement).
//
// 13 fonctions : remoteCallLookup/refreshCluster/loadCallDB/lookupCall/
// lookupCluster/searchCalls/showAC/hideAC/highlightAC/selectAC/
// onCallKeydown/applyCallData/updateCallDB. Appelees depuis onCallInput()
// (L2737 de logx_logbook.js) et submitQSO() (updateCallDB, via
// "if(loc) updateCallDB(call, loc, null);") -- toutes en corps de fonction.
//
// Point de vigilance documente par l'inventaire du 08/08/2026 : le
// commentaire d'en-tete de logx_verif_panel.js mentionnait callDB comme
// venant de logx_logbook.js -- mis a jour dans le meme commit.

// ─── LOOKUP DISTANT HAMQTH (debounce 600 ms) ─────────────────────────────────
async function remoteCallLookup(call){
  if(call.length < 4) return;
  const locEl  = document.getElementById('inputLocator');
  const nameEl = document.getElementById('inputName');
  // Rien à chercher si locator ET prénom sont DÉJÀ remplis (le prénom, appris
  // d'un QSO précédent, peut manquer même quand le locator est connu).
  if((locEl && locEl.value) && (nameEl && nameEl.value)) return;
  try{
    const res = await fetch(`/calldb/lookup/${encodeURIComponent(call)}`);
    if(!res.ok) return;
    const d = await res.json();
    // Indicatif changé entre-temps → ignorer
    if(document.getElementById('inputCall').value.toUpperCase() !== call) return;
    // Prénom (base interne) : rempli si vide, TOUJOURS corrigeable.
    if(d.name && nameEl && !nameEl.value){
      nameEl.value = d.name;
      callDB[call] = callDB[call] || {}; callDB[call].name = d.name;
    }
    if(d.locator){
      callDB[call] = callDB[call] || {};
      callDB[call].locator = d.locator;
      if(locEl && locEl.value) return;
      applyCallData({locator: d.locator, name: d.name}, null, null);
      // Correction du label source → HamQTH
      const hint = document.getElementById('locHint');
      if(hint && hint.style.display !== 'none')
        hint.textContent = hint.textContent.replace('[🗂️ base]','[🌐 HamQTH]');
    }
  } catch(e){}
}

// ─── CACHE CLUSTER ────────────────────────────────────────────────────────────
// callsign → { locator, freq, band, time, spotter, source }
let clusterCache = {};
let callLookupTimer = null;

async function refreshCluster(){
  // Récupère les spots cluster depuis le serveur et alimente clusterCache
  try{
    const res = await fetch('/log/status');
    if(!res.ok) return;
    const data = await res.json();
    const spots = data.spots || {};
    const cache = {};
    Object.keys(spots).forEach(band=>{
      const list = spots[band] || [];
      list.forEach(s=>{
        const call = (s.call||'').toUpperCase().split('/')[0];
        if(!call) return;
        cache[call] = {
          locator: s.locator||'',
          freq:    s.freq||'',
          band:    String(band).replace(/[^0-9.]/g,'') || band,
          time:    s.time||'',
          spotter: s.spotter||'',
          source:  s.source||'cluster',
        };
      });
    });
    clusterCache = cache;
    // Même réponse /log/status : on en profite pour rafraîchir le badge de
    // vérification de version multi-op (voir updateVersionStatus()) sans
    // ajouter un second cycle de polling dédié.
    updateVersionStatus(data);
  }catch(e){ /* serveur hors ligne : on conserve le cache existant */ }
}

// ─── BASE D'INDICATIFS (calldb.json) ─────────────────────────────────────────
let callDB = {};

async function loadCallDB(){
  // Index FUSIONNÉ serveur (/call/index = calldb + archives + anciens concours,
  // enrichi de worked/qso_count) ; repli sur calldb.json brut si indisponible.
  // Plusieurs tentatives rapprochées : la 1ère requête « à froid » peut échouer
  for(let attempt=1; attempt<=6; attempt++){
    try{
      let res = await fetch('/call/index');
      if(!res.ok) res = await fetch('/calldb.json', {cache:'force-cache'});
      if(!res.ok) throw new Error('HTTP '+res.status);
      const data = await res.json();
      callDB = data.calls || {};
      return;
    }catch(e){
      if(attempt === 6){ console.warn('base indicatifs indisponible :', e.message); }
      else { await new Promise(r=>setTimeout(r, 150)); }
    }
  }
}

function lookupCall(call){
  if(!call) return null;
  const c = call.toUpperCase().split('/')[0];
  return callDB[c] || callDB[call.toUpperCase()] || null;
}

function lookupCluster(call){
  if(!call) return null;
  const c = call.toUpperCase().split('/')[0];
  return clusterCache[c] || null;
}

// ─── AUTOCOMPLETE INDICATIF ───────────────────────────────────────────────────
let acResults = [];
let acSelected = -1;

function searchCalls(prefix){
  prefix = prefix.toUpperCase();
  const seen = new Set();
  const out  = [];

  // 1. Appels déjà travaillés dans le log courant (source la plus précieuse)
  for(const q of qsoLog){
    if(q.call && q.call.startsWith(prefix) && !seen.has(q.call)){
      seen.add(q.call);
      out.push({call:q.call, src:'log', locator:q.locator, dup: usageMode !== 'simple' && isDup(q.call,currentBand)});
      if(out.length >= 10) break;
    }
  }

  // 2. Base fusionnée (calldb + archives + anciens concours) — SUPER CHECK
  //    PARTIAL : préfixe d'abord, puis FRAGMENT n'importe où dans l'indicatif
  //    (dès 3 caractères, comme N1MM). Les stations déjà travaillées dans un
  //    concours passé remontent en tête.
  if(out.length < 10){
    const starts = [], contains = [];
    for(const call in callDB){
      if(seen.has(call)) continue;
      if(call.startsWith(prefix)) starts.push(call);
      else if(prefix.length >= 3 && call.includes(prefix)) contains.push(call);
    }
    const rank = c => ((callDB[c]||{}).worked ? 0 : 1);
    const byRank = (a,b) => rank(a)-rank(b) || a.localeCompare(b);
    starts.sort(byRank);
    contains.sort(byRank);
    for(const call of starts.concat(contains)){
      const d = callDB[call] || {};
      out.push({call, src: d.worked ? 'hist' : 'db',
                locator:d.locator, dept:d.dept, dup: usageMode !== 'simple' && isDup(call,currentBand)});
      if(out.length >= 10) break;
    }
  }
  return out;
}

function showAC(results, call){
  const box = document.getElementById('acBox');
  acResults = results || [];
  acSelected = -1;
  if(!acResults.length){ hideAC(); return; }
  box.innerHTML = acResults.map(item=>{
    const c     = typeof item === 'string' ? item : item.call;
    const src   = item.src  || 'db';
    const loc   = item.locator || (callDB[c]||{}).locator || '';
    const dept  = item.dept  || (callDB[c]||{}).dept  || '';
    const dup   = item.dup   || false;
    const dxcc  = lookupDXCC(c);
    const flag  = dxcc ? dxcc.flag : '';
    const cname = dxcc ? dxcc.c    : '';
    const srcTag = src==='log'
      ? `<span style="color:var(--green);font-size:13px;font-weight:700">📋 LOG</span>`
      : src==='hist'
      ? `<span style="color:var(--green);font-size:13px;font-weight:700">✓ DÉJÀ VU</span>`
      : `<span style="color:var(--muted);font-size:14px">🗂️</span>`;
    const dupTag = dup
      ? `<span style="color:var(--red);font-size:14px;font-weight:800">DUPE</span>`
      : '';
    // c/loc/dept viennent de callDB (indicatifs importés d'ADIF, historique) —
    // données potentiellement non maîtrisées, échappées avant insertion. Pour
    // l'argument JS de onmousedown, on restreint l'indicatif aux caractères valides.
    const jsC = String(c || '').replace(/[^A-Za-z0-9/]/g, '');
    const locStr = loc ? `<span style="color:var(--accent2);font-size:14px;font-weight:700">${escHtml(loc)}</span>` : '';
    const deptStr = dept ? `<span style="color:var(--yellow);font-size:14px;font-weight:700">dpt${escHtml(dept)}</span>` : '';
    const cStr  = cname ? `<span style="color:var(--muted);font-size:14px">${escHtml(cname)}</span>` : '';
    return `<div class="ac-item${dup?' dupe-item':''}" data-call="${escHtml(c)}" onmousedown="selectAC('${jsC}')">`
      + `<span style="font-size:16px">${flag}</span>`
      + `<b class="ac-call${dup?' dupe-call':''}" style="${dup?'color:var(--red)':'color:var(--green)'}">${escHtml(c)}</b>`
      + `<span style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;flex:1">${locStr}${deptStr}${cStr}${dupTag}</span>`
      + srcTag
      + `</div>`;
  }).join('');
  box.style.display = 'block';
}

function hideAC(){
  const box = document.getElementById('acBox');
  if(box) box.style.display = 'none';
  acSelected = -1;
}

function highlightAC(){
  document.querySelectorAll('#acBox .ac-item')
    .forEach((it,i)=> it.classList.toggle('selected', i===acSelected));
}

function selectAC(call){
  document.getElementById('inputCall').value = call;
  hideAC();

  // ── Vérification doublon (hors concours : recontacter la même station sur
  // la même bande au fil des années est normal, pas un doublon à signaler) ──
  const warn  = document.getElementById('dupWarn');
  const input = document.getElementById('inputCall');
  if(usageMode !== 'simple' && isDup(call, currentBand)){
    warn.style.background  = 'rgba(255,45,85,.15)';
    warn.style.borderColor = 'var(--red)';
    warn.style.color       = 'var(--red)';
    warn.textContent       = `⚠️ DOUBLON — ${call} déjà dans le log sur ${currentBand} MHz !`;
    warn.classList.add('show');
    input.classList.add('error');
    input.classList.remove('ok');
    // Bip d'erreur (deux bips courts)
    if(bipEnabled){
      playBeep(880, 0.12, 'square', 0.3);
      setTimeout(()=>playBeep(880, 0.12, 'square', 0.3), 200);
    }
  } else {
    warn.classList.remove('show');
    input.classList.remove('error');
    input.classList.add('ok');
  }

  // ── Préremplissage locator ────────────────────────────────────────────────
  const locField = document.getElementById('inputLocator');
  locField.value = '';
  const db  = lookupCall(call);
  const cl  = lookupCluster(call);
  const log = qsoLog.slice().reverse().find(q => q.call === call && q.locator && q.locator.length === 6);
  if(db || cl || log) applyCallData(db, cl, log);

  // ── Alerte double-bande ───────────────────────────────────────────────────
  crossBandAlert(call, currentBand);
  // ── Focus : RST si locator connu, sinon locator ───────────────────────────
  const locVal = document.getElementById('inputLocator').value;
  if(locVal && validateLocator(locVal)){
    focusNext('inputRSTsent');
  } else {
    focusNext('inputLocator');
  }
}

function onCallKeydown(e){
  const box = document.getElementById('acBox');
  const open = box && box.style.display !== 'none' && acResults.length;
  if(e.key === 'ArrowDown' && open){
    e.preventDefault();
    acSelected = Math.min(acSelected+1, acResults.length-1);
    highlightAC();
  } else if(e.key === 'ArrowUp' && open){
    e.preventDefault();
    acSelected = Math.max(acSelected-1, 0);
    highlightAC();
  } else if(e.key === 'Enter'){
    if(open && acSelected >= 0){
      e.preventDefault();
      const item = acResults[acSelected];
      selectAC(typeof item === 'string' ? item : item.call);
    } else {
      hideAC();
      e.preventDefault();
      // ESM : Entrée enchaîne appel CQ → échange (sinon valide le QSO).
      if(esmHandleEnter()) return;
      submitQSO();
    }
  } else if(e.key === 'Escape'){
    hideAC();
  }
}

// ─── APPLICATION DES DONNÉES D'UN INDICATIF CONNU ─────────────────────────────
function applyCallData(dbData, clusterData, logEntry){
  const callField = document.getElementById('inputCall');
  const locField  = document.getElementById('inputLocator');
  const hint      = document.getElementById('locHint');

  // Priorité : cluster (temps réel) > log courant > calldb
  const clLoc  = clusterData && clusterData.locator;
  const logLoc = logEntry    && logEntry.locator;
  const dbLoc  = dbData      && dbData.locator;
  const loc    = clLoc || logLoc || dbLoc || '';

  // Remplir le locator si :
  //  - la source est le cluster (temps réel → toujours prioritaire)
  //  - OU le champ est vide / invalide
  const existingLoc = locField.value;
  const existingValid = existingLoc && validateLocator(existingLoc);
  if(loc && (clLoc || !existingValid)){
    locField.value = loc;
    hideLocAC();
    onLocatorInput(); // calcule distance + cap → compas + hint
    const src = clLoc ? '📡 cluster' : logLoc ? '📋 log' : '🗂️ base';
    if(hint && hint.style.display !== 'none'){
      hint.textContent += `  [${src}]`;
    } else if(hint){
      hint.style.display = 'block';
      hint.style.color   = 'var(--accent2)';
      hint.textContent   = `Locator : ${src}`;
    }
  }

  // ── Département attendu (concours REF HF : l'échange EST le département) ──
  // Pré-rempli seulement si le champ est vide — l'opérateur reste maître de
  // ce qu'il a réellement reçu.
  if((currentExchange.label_r || '').includes('DEPT')){
    const numR = document.getElementById('inputNumRcvd');
    const dept = (dbData && dbData.dept) || (logEntry && logEntry.num_rcvd) || '';
    if(numR && !numR.value && dept){
      numR.value = dept;
      numR.classList.add('ok');
    }
  }
  // ── Prénom du correspondant : base interne (dbData) > log > cluster ──
  // Pré-rempli seulement si le champ est VIDE — l'opérateur reste maître de ce
  // qu'il corrige. Nom PROPRE, jamais mis en majuscules.
  const nameField = document.getElementById('inputName');
  const nm = (dbData && dbData.name) || (logEntry && logEntry.name)
          || (clusterData && clusterData.name) || '';
  if(nameField && nm && !nameField.value){ nameField.value = nm; }

  if(callField) callField.classList.add('ok');
  // Copilote CW/SSB : l'indicatif est RÉSOLU (enrichi) -> PRÉPARER l'échange
  // dans la barre de consentement (propose-only, opt-in, jamais d'émission
  // seule). typeof : le module/câblage vit dans logx_macros.js (chargé après).
  if(typeof proposerEchangeCopilote === 'function') proposerEchangeCopilote();
}

// ─── MISE À JOUR DE LA BASE D'INDICATIFS ──────────────────────────────────────
function updateCallDB(call, locator, dept, name){
  call = (call||'').toUpperCase().split('/')[0];
  if(!call) return;
  const entry = callDB[call] || {};
  let changed = false;
  if(locator && entry.locator !== locator){ entry.locator = locator; changed = true; }
  if(dept && entry.dept !== dept){ entry.dept = dept; changed = true; }
  // Prénom : enrichit la base interne (source de prénom hors QRZ). Nom PROPRE,
  // pas de majuscules. La correction manuelle de l'opérateur remonte ici.
  if(name && entry.name !== name){ entry.name = name; changed = true; }
  if(changed){
    callDB[call] = entry;
    fetch('/calldb/update', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({call, locator: locator||'', dept: dept||'', name: name||''})
    }).catch(()=>{});
  }
}

// Amorçage unique : importe dans la base interne les prénoms/locators déjà
// presents dans le JOURNAL, pour que l'auto-remplissage du prénom marche tout
// de suite (et hors ligne) pour les correspondants déjà contactés. Bouton
// expert-only sous le champ prénom (plomberie de station). Ne touche pas le log.
async function enrichirNomsDepuisJournal(){
  const btn = document.getElementById('enrichNomsBtn');
  if(btn) btn.disabled = true;
  try{
    const r = await fetch('/calldb/enrich_from_log', {method:'POST'});
    const d = await r.json();
    const msg = (d && d.ok)
      ? '✅ ' + (d.updated||0) + ' prénom(s)/locator(s) importé(s) depuis le journal ('
        + (d.scanned||0) + ' QSO parcourus).'
      : '❌ Import impossible' + (d && d.error ? ' : ' + d.error : '') + '.';
    if(typeof notify === 'function') notify(msg);
  }catch(e){
    if(typeof notify === 'function') notify('❌ Serveur injoignable.');
  }finally{
    if(btn) btn.disabled = false;
  }
}

// Amorçage AUTOMATIQUE une seule fois (premier chargement du LOGBOOK) : le
// prénom marche tout de suite pour les correspondants déjà au journal, SANS
// aucun geste — « le meilleur réglage est celui qu'on n'a pas à faire »
// (intuitivité). Le drapeau localStorage est posé AVANT l'appel pour ne jamais
// re-scanner le journal à chaque chargement ; le bouton reste pour re-lancer.
document.addEventListener('DOMContentLoaded', function(){
  try{
    if(localStorage.getItem('rc_calldb_enriched_v1')) return;
    localStorage.setItem('rc_calldb_enriched_v1', '1');
    fetch('/calldb/enrich_from_log', {method:'POST'})
      .then(function(r){ return r.json(); })
      .then(function(d){
        if(d && d.ok && d.updated > 0 && typeof notify === 'function')
          notify('✅ ' + d.updated + ' prénom(s)/locator(s) importé(s) de ton journal.');
      }).catch(function(){});
  }catch(e){}
});
