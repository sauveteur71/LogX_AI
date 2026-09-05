// EV-7 40e increment : CHAT MULTI-OPERATEUR -- extrait de logx_logbook.js
// (docs/LogX_AI_PRD.md). Charge en <script> classique dans logx_logbook.html,
// AVANT logx_logbook.js -- portee globale partagee (comme tous les fichiers EV-7).
//
// Contient : chatLastId, startChat, pollChat (poll /chat/list, reutilise aussi
// par la VUE PARTNER restee dans le coeur), renderChatMsg, sendChat. AUCUNE n'est
// appelee au TOP-LEVEL de logbook.js. Dependance runtime : notify() (coeur) --
// appel a l'usage, ordre de <script> indifferent.

// ─── CHAT MULTI-OPÉRATEUR ─────────────────────────────────────────────────────
let chatLastId = 0;

function startChat(){
  // Poll adaptatif : rapide (3s) quand le panneau chat est ouvert, ralenti
  // (15s) sinon — le point rouge de notification (renderChatMsg) continue de
  // fonctionner panneau fermé, juste avec une latence un peu plus longue.
  // Avant ce correctif : setInterval(pollChat, 3000) tournait à vie dès le
  // chargement de la page, panneau ouvert ou non — la requête la plus
  // fréquente du fichier avec rig/amp, même sur un poste où personne ne
  // regarde jamais le chat.
  // Reste aussi en cadence rapide en multi-op MÊME panneau fermé : c'est
  // justement l'état dans lequel la vue Partner doit rester réactive (bandeau
  // visible sans ouvrir le chat pendant un pile-up) — sans _isMultiOp() ici,
  // la saisie de l'autre opérateur ne se rafraîchirait qu'à 15s.
  adaptivePoll(pollChat, 3000, 15000, ()=>{
    const panel = document.getElementById('chatPanel');
    return !!(panel && panel.classList.contains('open')) || _isMultiOp();
  });
}

async function pollChat(){
  try{
    const r = await fetch('/chat/list?since=' + chatLastId);
    if(!r.ok) return;
    const d = await r.json();
    (d.messages || []).forEach(renderChatMsg);
    if(typeof d.last_id === 'number') chatLastId = d.last_id;
    renderPartnerTyping(d.typing || []);
  }catch(e){ /* serveur injoignable : on réessaiera */ }
}

function renderChatMsg(m){
  // Le conteneur des messages s'appelle chatBody dans l'HTML (pas chatBox —
  // ancien nom, l'id n'a jamais existé : le chat n'affichait rien du tout).
  const box = document.getElementById('chatBody');
  if(!box) return;
  const mine = (m.op === myOp);
  const div = document.createElement('div');
  div.className = 'chatmsg' + (mine ? ' mine' : '');
  const meta = document.createElement('span');
  meta.className = 'chatmeta';
  meta.textContent = `${m.time} ${m.op}${m.call ? ' · ' + m.call : ''}`;
  const txt = document.createElement('div');
  txt.className = 'chattext';
  txt.textContent = m.text;
  div.appendChild(meta); div.appendChild(txt);
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  // Badge « non lus » sur l'en-tête si le panneau est fermé et que ce n'est
  // pas mon message (id chatUnread dans l'HTML — compteur, pas simple point).
  const panel = document.getElementById('chatPanel');
  const unread = document.getElementById('chatUnread');
  if(unread && panel && !panel.classList.contains('open') && !mine){
    unread.textContent = String((parseInt(unread.textContent, 10) || 0) + 1);
    unread.style.display = 'inline-block';
  }
}

async function sendChat(){
  const inp = document.getElementById('chatInput');
  const text = inp.value.trim();
  if(!text) return;
  inp.value = '';
  try{
    await fetch('/chat/send', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ op: myOp, call: myCall, text })
    });
    pollChat();
  }catch(e){
    inp.value = text;
    notify('Chat : serveur injoignable, message non envoyé.');
  }
}
