// ─── Terminal CW (typewriter) — keyer CW Phase 1b (F4GLD 23/08/2026) ──────────
// Panneau repliable dans le LOGBOOK : saisie clavier immédiate → CW, journal des
// envois (texte + heure UTC), Échap coupe-circuit. RÉUTILISE le chemin unique et
// gardé cwEnvoyerTexte() (logx_macros.js → refus serveur logx_cw_guard si TX
// désarmé ou mode ≠ CW) et l'interrupteur maître cwTxArme (logx_hardware_cat.js).
// N'ajoute AUCUN nouveau chemin d'émission : tout repasse par le garde-fou.
//
// <script> classique (pas de module) : fonctions globales, appelées depuis le
// HTML (onclick/onkeydown). Gardes typeof pour les dépendances d'autres fichiers.

function cwTermToggle(){
  const body = document.getElementById('cwTerminalBody');
  const btn = document.getElementById('cwTermToggleBtn');
  if(!body) return;
  const ouvert = body.style.display !== 'none';
  body.style.display = ouvert ? 'none' : 'block';
  if(btn) btn.setAttribute('aria-expanded', ouvert ? 'false' : 'true');
  if(!ouvert){ const inp = document.getElementById('cwTermInput'); if(inp) inp.focus(); }
}

// Journal TX côté client : texte réellement accepté par le serveur + heure UTC.
// (Le journal structuré serveur — fréquence, backend — viendra en Phase 1c.)
function _cwTermLog(txt, refuse){
  const log = document.getElementById('cwTermLog');
  if(!log) return;
  const t = new Date().toISOString().slice(11, 19);   // HH:MM:SS UTC
  const row = document.createElement('div');
  row.className = 'cw-term-row' + (refuse ? ' cw-term-refuse' : '');
  row.textContent = t + '  ' + txt;
  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
}

// Entrée = envoyer la ligne au keyer ; Échap = vider la saisie + STOP CW
// (coupe-circuit, rigStopCW — logx_theme_shortcuts.js).
function cwTermKey(ev){
  if(ev.key === 'Escape'){
    ev.preventDefault();
    const inp = document.getElementById('cwTermInput'); if(inp) inp.value = '';
    if(typeof rigStopCW === 'function') rigStopCW();
    return;
  }
  if(ev.key === 'Enter'){
    ev.preventDefault();
    cwTermSend();
  }
}

function cwTermSend(){
  const inp = document.getElementById('cwTermInput');
  if(!inp) return;
  const txt = String(inp.value || '').trim();
  if(!txt) return;
  if(typeof cwEnvoyerTexte !== 'function') return;   // chemin gardé indisponible
  cwEnvoyerTexte(txt).then(d => {
    if(d && d.ok){ _cwTermLog(txt, false); inp.value = ''; }
    else { _cwTermLog('⛔ ' + ((d && d.error) || 'refusé') + '  « ' + txt + ' »', true); }
    _cwTermSyncWpm(d);
  }).catch(() => {});
}

// Témoin WPM : la vitesse réelle est renvoyée par le keyer à chaque envoi
// accepté (logx_winkeyer.envoyer → res.wpm). Affiché tel quel, jamais deviné.
function _cwTermSyncWpm(d){
  const w = document.getElementById('cwTermWpm');
  if(w && d && d.wpm) w.textContent = d.wpm + ' mots/min';
}
