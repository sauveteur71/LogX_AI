// EV-7 47e increment : HORLOGE + COMPTE A REBOURS (affichage) -- extrait de
// logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script> classique dans
// logx_logbook.html, AVANT logx_logbook.js -- portee globale partagee.
//
// Contient : l'etat prive contestEndAlertShown / _cdPhase, setCountdownLabel()
// et updateClockAndCountdown() (horloge UTC/local + compte a rebours de phase).
// getContestEndUTC/getContestStartUTC et l'etat contestStartUTC/contestEndUTC
// restent dans le coeur (lus par le scoring et logx_alertes_rappels.js) ; le
// cablage setInterval reste aussi dans logx_logbook.js. Lecture runtime de
// contestStartUTC/contestEndUTC/CONTEST_SCHEDULE/isSetupDone (coeur) -- a l'usage.

let contestEndAlertShown = false;

// Le libellé du compte à rebours n'est écrit que lorsqu'il CHANGE de phase
// (pas chaque seconde) : évite de réécrire du texte en continu — donc évite le
// clignotement quand une langue ≠ français re-traduit le libellé. On re-traduit
// une seule fois, au changement.
let _cdPhase = '';
function setCountdownLabel(phase, text){
  const lbl = document.getElementById('sbCountdownLbl');
  if(!lbl || _cdPhase === phase) return;
  _cdPhase = phase;
  lbl.textContent = text;
  if(window.rcTranslate) window.rcTranslate();
}

function updateClockAndCountdown(){
  const n = new Date();
  const utcStr = `${String(n.getUTCHours()).padStart(2,'0')}:${String(n.getUTCMinutes()).padStart(2,'0')}:${String(n.getUTCSeconds()).padStart(2,'0')}`;
  const localStr = `${String(n.getHours()).padStart(2,'0')}:${String(n.getMinutes()).padStart(2,'0')}:${String(n.getSeconds()).padStart(2,'0')}`;
  const clockEl = document.getElementById('clock');
  if(clockEl) clockEl.textContent = `${utcStr} UTC · ${localStr} local`;

  const cd  = document.getElementById('sbCountdown');
  const lbl = document.getElementById('sbCountdownLbl');
  const box = document.getElementById('sbCountdownItem');
  if(!cd) return;

  // ── Phase 1 : concours pas encore commencé ──────────────────────────────
  // Si contestStartUTC non dispo en localStorage, essayer CONTEST_SCHEDULE
  let effStartUTC = contestStartUTC;
  if(!effStartUTC && typeof CONTEST_SCHEDULE !== 'undefined'){
    try{
      const _cfg = JSON.parse(localStorage.getItem('logx_config')||'{}');
      const _s = CONTEST_SCHEDULE[_cfg.contest];
      if(_s && _s.start) effStartUTC = new Date(_s.start);
    }catch(_e){}
  }
  if(effStartUTC && n < effStartUTC){
    const diff = effStartUTC - n;
    const totalSec = Math.floor(diff / 1000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    setCountdownLabel('before', '🟢 DÉBUTE DANS');
    cd.textContent = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    cd.style.color = '#34C759';
    if(box) box.style.borderLeftColor = '#34C759';
    return;
  }

  // ── Phase 2bis : date de fin inconnue (concours sans dates configurées) ──
  // État neutre explicite : ne JAMAIS afficher un compte à rebours calculé
  // sur la date d'un autre concours (cf. getContestEndUTC()).
  if(!contestEndUTC){
    setCountdownLabel('unknown', '❔ DATES NON CONFIGURÉES');
    cd.textContent = '—:—:—';
    cd.style.color = 'var(--muted)';
    if(box) box.style.borderLeftColor = 'var(--muted)';
    return;
  }

  // ── Phase 2 : concours en cours ─────────────────────────────────────────
  setCountdownLabel('run', '⏱ TEMPS RESTANT');
  if(box) box.style.borderLeftColor = 'var(--red)';

  const diff = contestEndUTC - n;
  if(diff <= 0){
    cd.textContent = '🏁 TERMINÉ';
    cd.style.color = '#4A5080';
    if(!contestEndAlertShown && isSetupDone){
      contestEndAlertShown = true;
      setTimeout(()=>notify('🏁 CONCOURS TERMINÉ !\n\nPense à exporter ton log maintenant :\n📥 EDI / ADIF dans la barre d\'outils du logbook.'), 300);
    }
    return;
  }
  const totalSec = Math.floor(diff / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  cd.textContent = `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  if(h < 1)       cd.style.color = '#FF2D55';
  else if(h < 4)  cd.style.color = '#FFD60A';
  else             cd.style.color = '#FF5030';
}

// EV-7 48e increment : getContestEndUTC/getContestStartUTC (calcul des bornes
// de concours, appelees par le cablage du coeur) -- rejoignent ce module clock.
function getContestEndUTC(){
  let cfg = {};
  try{ cfg = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}
  if(cfg.contest_end_date && cfg.contest_end_utc){
    return new Date(`${cfg.contest_end_date}T${cfg.contest_end_utc}Z`);
  }
  // Repli RPH dynamique UNIQUEMENT si le concours réellement configuré est
  // REF_RPH (ou qu'aucun concours n'est encore sélectionné, ex. tout premier
  // chargement) : plusieurs concours du sélecteur (CS_DATA) n'ont PAS
  // d'entrée dans CONTEST_SCHEDULE (ex. REF_CHALLENGE_THF, REF_CCD_JAN1...),
  // donc contest_end_date n'est jamais renseigné pour eux — sans ce garde,
  // on retombait sur une date RPH sans aucun rapport avec le concours choisi.
  if(!cfg.contest || cfg.contest === 'REF_RPH'){
    return nextRPHWeekendUTC().end;
  }
  return null; // état neutre explicite : pas de date de fin connue pour ce concours
}
function getContestStartUTC(){
  try{
    const cfg = JSON.parse(localStorage.getItem('logx_config')||'{}');
    if(cfg.contest_start_date && cfg.contest_start_utc){
      return new Date(`${cfg.contest_start_date}T${cfg.contest_start_utc}Z`);
    }
  }catch(e){}
  return null; // pas de date de début configurée
}
