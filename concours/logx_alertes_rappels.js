// EV-7 44e increment : ALERTE DOUBLE-BANDE + RAPPEL PERIODIQUE ON4KST -- extrait
// de logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script> classique dans
// logx_logbook.html, AVANT logx_logbook.js -- portee globale partagee.
//
// Contient : crossBandAlert() (indice "deja contacte sur une autre bande",
// appele aussi par logx_lookup.js) et le rappel ON4KST (on4kstReminderTimer,
// hideON4KSTReminder / startON4KSTReminder). Non appelees au TOP-LEVEL.

// ─── ALERTE DOUBLE-BANDE ──────────────────────────────────────────────────────
function crossBandAlert(call, band){
  const hint = document.getElementById('crossBandHint');
  if(!hint) return;
  if(!call || call.length < 3 || !band){ hint.classList.remove('show'); return; }
  const hasOnOther  = qsoLog.some(q => q.call === call && q.band !== band);
  const hasOnCurrent = qsoLog.some(q => q.call === call && q.band === band);
  if(hasOnOther && !hasOnCurrent){
    const worked = [...new Set(qsoLog.filter(q=>q.call===call&&q.band!==band).map(q=>BAND_LABELS[q.band]||q.band+' MHz'))];
    hint.textContent = `📡 Double-bande possible — déjà loggé en ${worked.join(', ')} !`;
    hint.classList.add('show');
  } else {
    hint.classList.remove('show');
  }
}

// ─── RAPPEL PÉRIODIQUE ON4KST ─────────────────────────────────────────────────
let on4kstReminderTimer = null;
function hideON4KSTReminder(){
  const el = document.getElementById('on4kstReminder');
  if(el) el.classList.remove('show');
}
function startON4KSTReminder(){
  if(on4kstReminderTimer) return; // déjà démarré
  on4kstReminderTimer = setInterval(()=>{
    const n = new Date();
    const contestActive = contestStartUTC ? (n >= contestStartUTC && n < contestEndUTC) : (n < contestEndUTC);
    if(!contestActive) return;
    const el = document.getElementById('on4kstReminder');
    if(!el) return;
    el.classList.add('show');
    setTimeout(()=>el.classList.remove('show'), 20000); // auto-masquage après 20s
  }, 10 * 60 * 1000); // toutes les 10 minutes
}
