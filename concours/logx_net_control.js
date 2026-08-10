// ─── CONTRÔLE DE NET (EV-7, docs/LogX_AI_PRD.md) ─────────────────────────────
// Extrait hors du monolithe logx_logbook.js (chantier EV-7, même logique que
// logx_filter_builder.js/logx_dup_finder.js/logx_bulk_resolve.js à côté).
// Roster (liste des participants habituels) + session active (l'appel de ce
// soir). Roster en localStorage — par poste, pas synchronisé réseau, comme
// les préréglages de filtre (logx_filter_builder.js) : c'est la préférence
// de l'opérateur qui anime le net, pas un réglage de station partagé.
const NET_ROSTER_KEY = 'rc_net_roster';
const NET_SESSION_KEY = 'rc_net_session';

// Compteur monotone, PAS Date.now() seul : plusieurs ajouts dans la même
// milliseconde (saisie rapide, script) recevaient sinon le même id — trouvé
// en vérification navigateur (3 ajouts synchrones = 3 entrées avec un id
// identique), pas en écrivant le code.
let _netUidCounter = 0;
function netUid(){ return Date.now() + '_' + (_netUidCounter++); }

function netLoadRoster(){
  try{ return JSON.parse(localStorage.getItem(NET_ROSTER_KEY) || '[]'); }
  catch(e){ return []; }
}
function netSaveRoster(list){ localStorage.setItem(NET_ROSTER_KEY, JSON.stringify(list)); }

function netLoadSession(){
  try{ return JSON.parse(localStorage.getItem(NET_SESSION_KEY) || 'null'); }
  catch(e){ return null; }
}
function netSaveSession(session){
  if(session) localStorage.setItem(NET_SESSION_KEY, JSON.stringify(session));
  else localStorage.removeItem(NET_SESSION_KEY);
}

function openNetControl(){
  document.getElementById('netOverlay').classList.add('show');
  netRenderList();
}

function closeNetControl(){
  document.getElementById('netOverlay').classList.remove('show');
}

function netRosterAdd(){
  const callInput = document.getElementById('netAddCall');
  const nameInput = document.getElementById('netAddName');
  const call = callInput.value.trim().toUpperCase();
  if(!call) return;
  const name = nameInput.value.trim();
  const roster = netLoadRoster();
  const id = 'n' + netUid();
  roster.push({id, call, name});
  netSaveRoster(roster);
  // Un ajout en cours de session est un check-in tardif : la station rejoint
  // l'appel EN COURS, pas seulement le roster pour la prochaine fois.
  const session = netLoadSession();
  if(session){
    session.entries.push({id: 'e' + netUid(), call, name, checked: true, contacted: false});
    netSaveSession(session);
  }
  callInput.value = ''; nameInput.value = '';
  netRenderList();
}

function netRosterRemove(id){
  netSaveRoster(netLoadRoster().filter(r => r.id !== id));
  netRenderList();
}

function netStartSession(){
  const roster = netLoadRoster();
  if(!roster.length){ notify('Ajoute au moins une station au roster.'); return; }
  const session = {
    startedAt: Date.now(),
    entries: roster.map(r => ({id: 'e' + r.id, call: r.call, name: r.name, checked: true, contacted: false})),
  };
  netSaveSession(session);
  netRenderList();
}

async function netEndSession(){
  if(!(await _confirmDupBanner(trT('Terminer la session de net ? (le roster reste enregistré pour la prochaine fois)'), 'Terminer', 'Annuler'))) return;
  netSaveSession(null);
  netRenderList();
}

function netToggleChecked(entryId){
  const session = netLoadSession();
  if(!session) return;
  const e = session.entries.find(x => x.id === entryId);
  if(e) e.checked = !e.checked;
  netSaveSession(session);
  netRenderList();
}

function netBuildQso(call){
  return {
    id: Date.now() + Math.floor(Math.random() * 1000),
    date: nowDateUTC(), time: nowUTC(),
    call, band: currentBand, mode: currentMode,
    freq: (document.getElementById('inputFreq')?.value || '').trim(),
    rst_sent: '59', num_sent: '',
    rst_rcvd: '59', num_rcvd: '',
    locator: '', dist: 0, points: 0,
    operator: myOp, my_call: myCall, my_locator: myLocator,
    contest: currentContest,
  };
}

async function netLogQso(qso){
  try{
    const res = await fetch('/log/add', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(qso)});
    if(res.ok){
      qsoLog.push(qso);
      bcBroadcast('add', qso);
      return true;
    }
  }catch(e){}
  return false;
}

async function netLogOne(entryId){
  const session = netLoadSession();
  if(!session) return;
  const e = session.entries.find(x => x.id === entryId);
  if(!e || e.contacted) return;
  const qso = netBuildQso(e.call);
  if(await netLogQso(qso)){
    e.contacted = true;
    e.qsoId = qso.id;
    netSaveSession(session);
    renderLog(); updateStats();
    netRenderList();
  }
}

async function netLogAllChecked(){
  const session = netLoadSession();
  if(!session) return;
  const targets = session.entries.filter(e => e.checked && !e.contacted);
  if(!targets.length){ notify('Aucune station cochée à logger.'); return; }
  if(!(await _confirmDupBanner(trF('Logger {n} station(s) à {band} MHz / {mode} ?', {n: targets.length, band: currentBand, mode: currentMode}), 'Logger', 'Annuler'))) return;
  for(const e of targets){
    const qso = netBuildQso(e.call);
    if(await netLogQso(qso)){
      e.contacted = true;
      e.qsoId = qso.id;
    }
  }
  netSaveSession(session);
  renderLog(); updateStats();
  netRenderList();
}

// Glisser-déposer : réordonne le ROSTER (mode sans session) ou les entrées
// de la SESSION active (mode session) — l'ordre pilote qui est "en attente"
// ensuite (première ligne cochée non contactée).
let _netDragId = null;
function netDragStart(id){ _netDragId = id; }
function netDragOver(ev){ ev.preventDefault(); }
function netDrop(ev, targetId){
  ev.preventDefault();
  if(_netDragId == null || _netDragId === targetId) return;
  const session = netLoadSession();
  if(session){
    const list = session.entries;
    const from = list.findIndex(x => x.id === _netDragId);
    const to = list.findIndex(x => x.id === targetId);
    if(from < 0 || to < 0) return;
    list.splice(to, 0, list.splice(from, 1)[0]);
    netSaveSession(session);
  } else {
    const list = netLoadRoster();
    const from = list.findIndex(x => x.id === _netDragId);
    const to = list.findIndex(x => x.id === targetId);
    if(from < 0 || to < 0) return;
    list.splice(to, 0, list.splice(from, 1)[0]);
    netSaveRoster(list);
  }
  _netDragId = null;
  netRenderList();
}

function netRenderList(){
  const wrap = document.getElementById('netList');
  if(!wrap) return;
  const esc = s => String(s==null?'':s).replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const session = netLoadSession();
  document.getElementById('netStartBtn').style.display = session ? 'none' : 'inline-block';
  document.getElementById('netEndBtn').style.display = session ? 'inline-block' : 'none';
  document.getElementById('netLogAllBtn').style.display = session ? 'inline-block' : 'none';
  document.getElementById('netSessionInfo').textContent = session
    ? trF('Session en cours — {c} contacté(s) / {t}', {
        c: session.entries.filter(e=>e.contacted).length, t: session.entries.length})
    : trT('Session non démarrée');

  if(!session){
    const roster = netLoadRoster();
    document.getElementById('netCount').textContent = trF('{n} station(s) au roster', {n: roster.length});
    wrap.innerHTML = roster.length ? roster.map(r => `
      <div class="net-row" draggable="true" ondragstart="netDragStart('${r.id}')" ondragover="netDragOver(event)" ondrop="netDrop(event,'${r.id}')">
        <span>⠿</span><span></span>
        <span><span class="net-call">${esc(r.call)}</span>${r.name?` <span class="net-name">${esc(r.name)}</span>`:''}</span>
        <span></span><span></span>
        <span class="net-del" onclick="netRosterRemove('${r.id}')" title="Retirer du roster">✕</span>
      </div>`).join('') : '<div class="net-empty">Roster vide — ajoute des stations ci-dessus.</div>';
    return;
  }

  const currentId = (session.entries.find(e => e.checked && !e.contacted) || {}).id;
  document.getElementById('netCount').textContent = trF('{n} station(s) dans la session', {n: session.entries.length});
  wrap.innerHTML = session.entries.map(e => `
    <div class="net-row${e.id===currentId?' current':''}${e.contacted?' contacted':''}" draggable="true"
         ondragstart="netDragStart('${e.id}')" ondragover="netDragOver(event)" ondrop="netDrop(event,'${e.id}')">
      <span>⠿</span>
      <span><input type="checkbox" ${e.checked?'checked':''} ${e.contacted?'disabled':''} onchange="netToggleChecked('${e.id}')"></span>
      <span><span class="net-call">${esc(e.call)}</span>${e.name?` <span class="net-name">${esc(e.name)}</span>`:''}</span>
      <span class="net-name">${e.contacted?'✓ contacté':''}</span>
      <span>${e.contacted?'':`<button class="net-log-btn" onclick="netLogOne('${e.id}')">LOGGER</button>`}</span>
      <span></span>
    </div>`).join('');
}
