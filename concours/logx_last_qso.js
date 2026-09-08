// logx_last_qso.js — Panneau « DERNIERS QSO SAISIS » du LOGBOOK
// Extrait de logx_logbook.js (campagne EV-7, 54e increment, 2026-09-08).
// updateLastQso(q) empile un QSO dans le panneau ; toggleLastQso() le replie
// (meme schema que toggleSoapbox). Depend de escHtml() et _resolveOperatorCallsign()
// du coeur, appeles a l'execution — chargement classique AVANT logx_logbook.js
// (portee globale partagee, pas de module ES).

function updateLastQso(q){
  const list = document.getElementById('lastQsoList');
  const div = document.createElement('div');
  div.className = 'last-qso-item';
  div.innerHTML = `
    <span class="lqi-call">${escHtml(q.call)}</span>
    <span class="lqi-loc">${escHtml(q.locator)||'—'}</span>
    <span class="lqi-pts">${escHtml(q.points)||0} pts</span>
    <span class="lqi-op">${escHtml(_resolveOperatorCallsign(q.operator))}</span>
  `;
  list.insertBefore(div, list.firstChild);
  if(list.children.length > 5) list.removeChild(list.lastChild);
}

// Replié par défaut (le tableau du log liste déjà tout) — même schéma que
// toggleSoapbox() : classe .collapsed sur le titre + .hidden sur le contenu.
function toggleLastQso(){
  const title = document.getElementById('lastQsoToggle');
  const list  = document.getElementById('lastQsoList');
  if(!title || !list) return;
  const collapsed = title.classList.toggle('collapsed');
  list.classList.toggle('hidden', collapsed);
}
