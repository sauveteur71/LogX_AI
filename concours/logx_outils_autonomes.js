// ─── OUTILS AUTONOMES (EV-7, docs/LogX_AI_PRD.md) ────────────────────────────
// 8e incrément du refactor EV-7 : PREMIÈRE extraction en plusieurs points non
// contigus de logx_logbook.js (pas un seul bloc coupé d'un trait) — les blocs
// contigus restants sont soit déjà extraits (7 incréments précédents), soit
// entremêlés avec le cœur (voir la liste des candidats écartés dans les
// mémoires de chantier EV-7). Cinq petites fonctionnalités autonomes,
// vérifiées une par une sans aucun appelant depuis un dispatcher cœur :
//   - ÉCOUTER SUR UN WEBSDR (ecouterSpot/sEcouter)
//   - GARDE-FOU « MULT FANTÔME » : zone CQ reçue vs cty.dat (checkExchangeZone/
//     clearExchWarn/askExchangePlausible) — corrigerBusted(), fonctionnalité
//     voisine mais distincte (pastille indicatif « busted »), RESTE dans
//     logx_logbook.js.
//   - MÉTÉO DU POINT HAUT (refreshWeather)
//   - RESET LOG (archiveLog/resetLog)
//   - GPS → LOCATOR MAIDENHEAD (latLonToMaidenhead/getGPSLocator)
//
// Dépend de globals restés dans logx_logbook.js (portée globale partagée via
// <script> classique, voir logx_logbook.html) : escHtml(), notify(), trF(),
// trT(), currentExchange, currentMode, qsoLog, resetLogRenderWindow(),
// renderLog(), updateStats(), updateSerialDisplay(), fetchLog(), rcLangDirective
// (logx_i18n.js, chargé encore avant), rigState.

// ─── ÉCOUTER SUR UN WEBSDR : le serveur choisit le récepteur ─────────────────
// Deux gestes, un seul endpoint (/data/websdr/ecouter, annuaire en cache) :
//   - ecouterSpot(khz, lat, lon, mode) : récepteur PROCHE DU DX — entendre à
//     peu près ce que le DX entend avant de l'appeler ;
//   - sEcouter() : récepteur proche de CHEZ MOI, sur la fréquence radio —
//     contrôle de modulation instantané. La page WEBSDR fait le tour complet.
async function ecouterSpot(khz, lat, lon, mode, loc){
  try{
    const p = new URLSearchParams();
    if(khz) p.set('khz', khz);
    if(mode) p.set('mode', mode);
    if(lat != null && lon != null){ p.set('lat', lat); p.set('lon', lon); }
    else if(loc) p.set('loc', loc);   // le serveur situe le DX par sa grille
    const r = await fetch('/data/websdr/ecouter?' + p.toString());
    const d = await r.json();
    if(!d.ok || !d.url){
      alert(trT('Aucun récepteur WebSDR en ligne assez près (rayon 1500 km).'));
      return;
    }
    window.open(d.url, '_blank', 'noopener');
  }catch(e){ /* serveur injoignable : geste optionnel, pas d'erreur bloquante */ }
}

function sEcouter(){
  const rig = (typeof rigState !== 'undefined') ? rigState : {};
  // Sans CAT, pas de fréquence à transmettre : le récepteur s'ouvre sur sa
  // fréquence par défaut, l'opérateur règle à la main (mieux que rien).
  const khz = (rig.enabled && rig.freq_khz) ? rig.freq_khz : null;
  // Le mode RÉEL de la radio prime sur celui du logiciel : c'est celui-là
  // qu'il faut écouter pour juger sa propre modulation (même choix qu'au
  // décodeur CW et au keyer, plus haut dans ce fichier).
  ecouterSpot(khz, null, null, rig.mode || currentMode || '');
}

// ─── GARDE-FOU « MULT FANTÔME » : zone CQ reçue vs cty.dat ───────────────────
// À la saisie de la zone reçue (CQ WW), on la compare à ce que cty.dat attend
// pour l'indicatif — désaccord = candidat multiplicateur FANTÔME (compté comme
// mult, retiré au checking : pénalité nette). Le contrôle est DÉTERMINISTE et
// instantané (/exchange/check, aucun LLM) ; l'IA ne tranche l'ambigu (portable,
// /MM, pays à cheval sur plusieurs zones) QU'À LA DEMANDE, via /proxy/ai.
let _exchAI = null;
async function checkExchangeZone(){
  if(!currentExchange || currentExchange.check !== 'cq_zone') return clearExchWarn();
  const call = (document.getElementById('inputCall').value || '').trim().toUpperCase();
  const value = (document.getElementById('inputNumRcvd').value || '').trim();
  if(!call || !value) return clearExchWarn();
  try{
    const r = await fetch('/exchange/check?kind=cq_zone&call='+encodeURIComponent(call)+'&value='+encodeURIComponent(value));
    const d = await r.json();
    if(!d || d.match !== false) return clearExchWarn();   // correspond, ou indicatif inconnu : rien
    _exchAI = {call, value, expected: d.expected, entity: d.entity || ''};
    const zone = document.getElementById('exchWarn');
    if(!zone) return;
    const info = d.entity ? trF('{e} → zone {z} attendue', {e: d.entity, z: d.expected})
                          : trF('zone {z} attendue', {z: d.expected});
    zone.innerHTML =
        `<span class="ew-txt">⚠️ ${escHtml(trF('zone {v} pour {c} ?', {v: value, c: call}))}</span>`
      + `<span class="ew-info">${escHtml(info)}</span>`
      + `<button class="ew-ai" onclick="askExchangePlausible()">🤖 ${escHtml(trT('plausible ?'))}</button>`
      + `<button class="ew-x" onclick="clearExchWarn()">${escHtml(trT('ignorer'))}</button>`;
    zone.style.display = 'flex';
  }catch(e){ /* garde-fou optionnel : jamais d'erreur visible pour l'opérateur */ }
}
function clearExchWarn(){
  const zone = document.getElementById('exchWarn');
  if(zone){ zone.style.display = 'none'; zone.innerHTML = ''; }
  _exchAI = null;
}
async function askExchangePlausible(){
  const ctx = _exchAI; if(!ctx) return;
  const info = document.querySelector('#exchWarn .ew-info');
  if(info) info.textContent = '…';
  const prompt = `En concours CQ WW, la station ${ctx.call} (${ctx.entity||'entité inconnue'}, `
    + `zone CQ attendue ${ctx.expected} d'après cty.dat) a passé la zone ${ctx.value}. `
    + `Est-ce PLAUSIBLE (station portable /P dans une autre zone, maritime mobile /MM, ou pays `
    + `à cheval sur plusieurs zones CQ : USA 3-5, Russie 16-23, Canada 1-5, Australie 29-30) `
    + `ou probablement une ERREUR de copie ? Réponds en UNE phrase courte.`;
  try{
    const dir = (typeof rcLangDirective === 'function') ? rcLangDirective() : '';
    const body = {messages:[{role:'user', content:prompt}], max_tokens:200};
    if(dir) body.system = dir;
    const r = await fetch('/proxy/ai', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const d = await r.json();
    const txt = (d && d.content && d.content[0] && d.content[0].text) ? d.content[0].text.trim() : '';
    if(info) info.textContent = txt || trT('pas de réponse IA');
  }catch(e){
    if(info) info.textContent = trT('IA injoignable (hors-ligne) — vérifie la zone à la main.');
  }
}

// ─── MÉTÉO DU POINT HAUT (sécurité matériel /P) ──────────────────────────────
function refreshWeather(){
  fetch('/data/weather').then(r=>r.ok?r.json():null).then(d=>{
    const el = document.getElementById('weatherWidget');
    if(!el || !d || !d.ok){ if(el) el.style.display='none'; return; }
    el.style.display = '';
    el.innerHTML = `${d.icon} ${d.temp}°C · 💨 ${d.wind}` +
      (d.gust >= d.wind + 10 ? `/${d.gust}` : '') + ` km/h` +
      (d.precip > 0 ? ` · 🌧️ ${d.precip}mm` : '') +
      (d.warn ? ` <b style="color:var(--red)">${d.warn}</b>` : '');
    el.style.color = d.warn ? 'var(--red)' : 'var(--muted)';
  }).catch(()=>{});
}
refreshWeather();
setInterval(refreshWeather, 10 * 60 * 1000);   // cache serveur 10 min

// ─── RESET LOG ───────────────────────────────────────────────────────────────
// Archive le concours actif dans un dossier permanent (log + Cabrillo + ADIF
// + résumé). Optionnellement, vide ensuite ce concours du log actif.
async function archiveLog(){
  try{
    const clear = confirm(trT('📦 ARCHIVER CE CONCOURS') + '\n\n' +
      'Le log du concours actif va être conservé dans un dossier permanent\n' +
      '(log.json + Cabrillo + ADIF + résumé), qui restera même si tu changes\n' +
      'de concours.\n\n' +
      'OK  = archiver ET vider ce concours du log actif (repartir à neuf)\n' +
      'Annuler = archiver SANS rien effacer');
    const res = await fetch('/log/archive', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({clear: clear})
    });
    const d = await res.json();
    if(d.ok){
      const clearedNote = d.cleared ? trT(' — log vidé, prêt pour la suite.') : trT(' — log conservé.');
      notify(trF('📦 Archivé : {n} QSO dans « {name} »{note}', {n: d.qso_count, name: d.name, note: clearedNote}));
      if(d.cleared){ qsoLog = qsoLog.filter(q => false); resetLogRenderWindow(); renderLog(); updateStats(); }
      else { fetchLog(); }
    } else {
      notify(trF('Archivage : {err}', {err: d.error || trT('échec')}));
    }
  }catch(e){ notify('Serveur injoignable — archivage impossible.'); }
}

async function resetLog(){
  const n = qsoLog.length;
  if(!confirm(trF('⚠️ NOUVEAU LOG\n\nSupprime {n} QSO du log ACTIF.\nⓘ Ils sont d\'abord ARCHIVÉS dans un dossier permanent (par concours),\ndonc rien n\'est perdu — tu les retrouveras dans archives/.\n\nTape OK pour continuer.', {n}))) return;
  const confirmation = prompt(trT('Tape RESET pour confirmer la suppression complète du log :'));
  if(confirmation !== 'RESET'){
    notify('Annulé — le log est inchangé.');
    return;
  }
  try{
    const res = await fetch('/log/reset',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({confirm:'RESET'})
    });
    if(res.ok){
      const d = await res.json().catch(()=>({}));
      qsoLog = [];
      serialByBand = {};
      resetLogRenderWindow();
      renderLog();
      updateStats();
      updateSerialDisplay();
      const nb = (d.folders || []).length;
      const folderNote = nb ? trF(' ({nb} dossier{plural})', {nb, plural: nb>1?'s':''}) : '';
      notify(trF('✅ Log archivé{note} puis réinitialisé — prêt pour le concours !', {note: folderNote}));
    } else {
      notify('Erreur serveur lors de la réinitialisation.');
    }
  } catch(e){
    notify(trF('Impossible de contacter le serveur : {err}', {err: e.message}));
  }
}

// ─── GPS → LOCATOR MAIDENHEAD ────────────────────────────────────────────────
function latLonToMaidenhead(lat, lon){
  lon += 180; lat += 90;
  const L = 'ABCDEFGHIJKLMNOPQRSTUVWX';
  let loc = '';
  loc += L[Math.floor(lon/20)];
  loc += L[Math.floor(lat/10)];
  loc += Math.floor((lon%20)/2).toString();
  loc += Math.floor(lat%10).toString();
  loc += L[Math.floor(((lon%20)%2)*12)];
  loc += L[Math.floor((lat%1)*24)];
  return loc.toUpperCase();
}

function getGPSLocator(){
  if(!navigator.geolocation){ notify('Géolocalisation non disponible dans ce navigateur.'); return; }
  const btn = document.querySelector('.gps-btn');
  if(btn) btn.textContent = '⏳…';
  navigator.geolocation.getCurrentPosition(pos=>{
    const loc = latLonToMaidenhead(pos.coords.latitude, pos.coords.longitude);
    const el = document.getElementById('setupLocator');
    if(el) el.value = loc;
    if(btn) btn.textContent = '📍 GPS';
    notify(trF('Locator GPS : {loc}\n({lat}°N, {lon}°E)',
      {loc, lat: pos.coords.latitude.toFixed(4), lon: pos.coords.longitude.toFixed(4)}));
  }, err=>{
    if(btn) btn.textContent = '📍 GPS';
    notify(trF('Erreur GPS : {err}', {err: err.message || err.code}));
  }, {timeout:10000, enableHighAccuracy:true});
}
