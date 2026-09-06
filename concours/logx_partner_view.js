// EV-7 46e increment : VUE PARTNER (saisie en direct, lecture seule) -- extrait
// de logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script> classique dans
// logx_logbook.html, AVANT logx_logbook.js -- portee globale partagee.
//
// Contient : _isMultiOp (aussi utilise par logx_statusbar.js/logx_chat.js),
// _sendTyping/broadcastTyping (le runner diffuse sa saisie via /chat, appele sur
// le chemin onCallInput du coeur) et renderPartnerTyping (affiche la frappe
// distante ; appelle _reserveBottomSpace reste dans le coeur). Non top-level.

// ─── VUE PARTNER (saisie en direct, lecture seule) ───────────────────────────
// Un second opérateur (radioclub/expédition) voit ce que le runner tape dans
// le champ INDICATIF, en quasi temps réel. Réutilise le poll /chat/list déjà
// en place (adaptivePoll 3-15s, cf. startChat) plutôt qu'un nouveau
// mécanisme — pas de WebSocket, juste un état éphémère côté serveur (jamais
// persisté, contrairement aux messages de chat). Lecture seule : cette 1re
// version ne permet pas de « pousser » un indicatif corrigé vers le runner.
// Diffusion (côté runner) uniquement en multi-op — sur un poste solo, cette
// info n'intéresse personne et ne vaut pas le trafic réseau supplémentaire.
function _isMultiOp(){
  // Même définition que isMultiOp() dans logx_statusbar.js (exposée en
  // window.rcIsMultiOp) — on la réutilise pour ne pas faire vivre deux
  // implémentations séparées. Le repli ci-dessous (dupliqué intentionnellement)
  // ne sert que si ce fichier tournait sans logx_statusbar.js chargé — ce qui
  // n'arrive pas sur logx_logbook.html (statusbar inclus avant), mais évite
  // une dépendance dure entre les deux fichiers.
  if(typeof window.rcIsMultiOp === 'function') return window.rcIsMultiOp();
  try{
    const cfg = JSON.parse(localStorage.getItem('logx_config') || '{}');
    return cfg.usage_mode !== 'simple' && (cfg.operators || []).length > 1;
  }catch(e){ return false; }
}

let _typingTimer = null;
let _typingLastSent = 0;
const TYPING_MIN_INTERVAL_MS = 300;   // throttle (pas un debounce) : la frappe reste visible pendant la saisie, pas seulement à la pause

function _sendTyping(text){
  const opLbl = (document.getElementById('opCurrentLabel') || {}).textContent || myOp;
  fetch('/chat/typing', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ op: myOp, label: opLbl, band: currentBand, mode: currentMode, text })
  }).catch(()=>{});
}

function broadcastTyping(text){
  if(!_isMultiOp()) return;
  const now = Date.now();
  const elapsed = now - _typingLastSent;
  clearTimeout(_typingTimer);
  if(elapsed >= TYPING_MIN_INTERVAL_MS){
    _typingLastSent = now;
    _sendTyping(text);
  } else {
    _typingTimer = setTimeout(() => { _typingLastSent = Date.now(); _sendTyping(text); },
                              TYPING_MIN_INTERVAL_MS - elapsed);
  }
}

// Affiche la saisie des AUTRES opérateurs (jamais la sienne), visible même
// panneau CHAT fermé (bandeau discret au-dessus du corps du chat) — repéré
// d'un coup d'œil sans avoir à ouvrir le panneau pendant un pile-up.
function renderPartnerTyping(list){
  const box = document.getElementById('partnerTyping');
  if(!box) return;
  const others = (list || []).filter(t => t && t.op !== myOp && t.text);
  if(!others.length){
    box.style.display = 'none';
    box.innerHTML = '';
  } else {
    box.style.display = 'flex';
    box.innerHTML = others.map(t =>
      `<div class="partner-row"><span class="partner-op">${escHtml(t.label || t.op)}</span>`
      + `<span class="partner-ctx">${escHtml(t.band||'')}${t.band?' MHz':''}${t.mode?' · '+escHtml(t.mode):''}</span>`
      + `<span class="partner-text">${escHtml(t.text)}</span></div>`
    ).join('');
  }
  // Le bandeau change de hauteur avec son contenu — et il est VISIBLE (donc
  // occupe de la place dans .chat-panel, position:fixed) que le panneau CHAT
  // soit ouvert ou fermé : c'est même l'intérêt de la vue Partner (repérer la
  // saisie du runner sans ouvrir le chat). Recalculer la marge réservée à
  // CHAQUE changement de contenu, sans condition sur .open — sinon panneau
  // fermé, le bandeau grandit (jusqu'à ~110px) sans jamais agrandir l'espace
  // réservé sous le tableau, et chevauche les dernières lignes du log.
  const panel = document.getElementById('chatPanel');
  _reserveBottomSpace(panel, document.querySelector('.log-table-wrap'));
}
