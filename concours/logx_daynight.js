// EV-7 phase 2, 18e increment (docs/LogX_AI_PRD.md) -- widget TIME OF DAY
// (jour/nuit HOME vs DX) + saisie/validation du champ locator (distance,
// cap, points) -- extrait tel quel de logx_logbook.js (extraction
// MECANIQUE). Charge en <script> classique dans logx_logbook.html, AVANT
// logx_logbook.js (portee globale partagee).
//
// 2 variables d'etat privees au bloc (grep exhaustif sur tout le depot) :
// _todTimer, _todSeq.
//
// onLocatorInput() est appelee depuis 3 sites externes (tous en corps de
// fonction, jamais au niveau top-level) : logx_callbook.js (lookupQRZ()),
// logx_lookup.js (applyCallData()), et logx_logbook.js (selectLocAC(),
// Reverse Lookup Locator, pas encore extrait) + l'attribut HTML
// oninput="onLocatorInput()" du champ #inputLocator (logx_logbook.html).
//
// Depend de 5 fonctions definies PLUS LOIN dans logx_logbook.js
// (searchByLocator/showLocAC/hideLocAC/showCompassInline/hideCompassInline,
// section Reverse Lookup Locator) -- uniquement a l'interieur du corps de
// onLocatorInput(), jamais au chargement, donc sans risque d'ordre malgre
// le nombre de dependances "en avant" superieur a la moyenne des
// incrementes precedents.

// ─── WIDGET TIME OF DAY (jour/nuit HOME vs DX) ───────────────────────────────
let _todTimer = null, _todSeq = 0;

function refreshTimeOfDay(dxLocator){
  clearTimeout(_todTimer);
  const el = document.getElementById('todWidget');
  if(!el) return;
  if(!dxLocator){ el.style.display = 'none'; return; }
  const seq = ++_todSeq;
  _todTimer = setTimeout(async () => {
    try{
      const r = await fetch('/data/timeofday?dx=' + encodeURIComponent(dxLocator));
      if(!r.ok || seq !== _todSeq) return;
      const d = await r.json();
      if(!d.home){ el.style.display = 'none'; return; }
      const side = (label, s) => {
        if(!s) return '';
        const icon = s.is_day ? '☀️' : '🌙';
        return `<span>${icon} ${label} ${String(Math.floor(s.local_hour)).padStart(2,'0')}h${String(Math.round((s.local_hour%1)*60)).padStart(2,'0')}</span>`;
      };
      const bits = [side('CHEZ TOI', d.home)];
      if(d.dx) bits.push(side('DX', d.dx));
      el.innerHTML = bits.filter(Boolean).join('');
      el.style.display = bits.some(Boolean) ? 'flex' : 'none';
    }catch(e){ /* réseau indispo : widget inchangé */ }
  }, 400);
}

function onLocatorInput(){
  const loc = document.getElementById('inputLocator').value.toUpperCase();
  document.getElementById('inputLocator').value = loc;
  const field = document.getElementById('inputLocator');
  const hint = document.getElementById('locHint');

  if(loc.length === 0){
    field.classList.remove('ok','error');
    hint.style.display = 'none';
    hideCompassInline();
    hideLocAC();
    refreshTimeOfDay('');
    return;
  }
  if(loc.length < 6){
    field.classList.remove('ok','error');
    hint.style.display = 'none';
    hideCompassInline();
    // Reverse lookup : dès 4 caractères, proposer des indicatifs de ce carré
    if(loc.length >= 4){
      const matches = searchByLocator(loc);
      if(matches.length) showLocAC(matches);
      else hideLocAC();
    } else {
      hideLocAC();
    }
    return;
  }
  hideLocAC(); // locator complet → on cache la suggestion
  if(loc.length === 6){
    if(!validateLocator(loc)){
      field.classList.add('error');
      field.classList.remove('ok');
      hint.textContent = '⚠️ Format invalide — attendu : AA00AA (ex: JN03QQ)';
      hint.style.color = 'var(--red)';
      hint.style.display = 'block';
      return;
    }
    field.classList.add('ok');
    field.classList.remove('error');
    refreshTimeOfDay(loc);
    const dist = calcDist(loc);
    const callInput = document.getElementById('inputCall')?.value?.toUpperCase()||'';
    const modeInput = currentMode||'SSB';   // le mode vit dans le picker (plus de champ inputMode)
    const pts = calcPoints(loc, currentBand, callInput, modeInput);
    const locAlreadyUsed = qsoLog.some(q => q.locator === loc);
    if(dist > 0){
      const cap = bearing(loc);
      const card = cap !== null ? cardinalDir(cap) : '';
      const capStr = cap !== null ? `🧭 ${cap}° ${card}` : '';
      const dupNote = locAlreadyUsed ? '  ⚠️ Locator déjà loggué' : '';
      hint.textContent = `📏 ${dist} km  ${capStr}  → 🏆 ${pts} pts${dupNote}`;
      hint.style.color = locAlreadyUsed ? 'var(--yellow)' : 'var(--accent)';
      hint.style.display = 'block';
      if(cap !== null) showCompassInline(cap, dist, pts);
      else hideCompassInline();
    } else {
      if(locAlreadyUsed){
        hint.textContent = '⚠️ Locator déjà loggué';
        hint.style.color = 'var(--yellow)';
        hint.style.display = 'block';
      }
      hideCompassInline();
    }
  }
}
