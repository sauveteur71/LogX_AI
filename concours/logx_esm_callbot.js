// EV-7 phase 2, 19e increment (docs/LogX_AI_PRD.md) -- CALLBOT (macros
// vocales DYNAMIQUES : synthese + PTT + emission radio) + ESM (Enter Sends
// Message) -- extrait tel quel de logx_logbook.js (extraction MECANIQUE,
// 2 mini-systemes voisins par theme -- emission vocale pendant la saisie --
// pas une dependance bidirectionnelle bloquante). Charge en <script>
// classique dans logx_logbook.html, AVANT logx_logbook.js (portee globale
// partagee).
//
// Etat prive au bloc (grep exhaustif sur tout le depot) : esmMode,
// esmExchanged -- lus/ecrits depuis logx_logbook.js (submitQSO()/
// clearForm()) uniquement en corps de fonction.
//
// Depend de fonctions definies PLUS LOIN dans logx_logbook.js (trT, trF,
// notify) et de rigState (logx_hardware_cat.js, deja extrait, via
// typeof rigState!=='undefined') -- uniquement a l'interieur de corps de
// fonction, jamais au chargement, motif deja eprouve.
//
// EV-7 32e increment : copyMacro() a ete extraite vers logx_macros.js (deja
// gardee par typeof copyMacro==='function' plus bas, motif conserve tel
// quel -- ce fichier (19e increment) charge AVANT logx_macros.js (32e), mais
// l'appel ne se produit qu'a l'interieur d'esmSend(), jamais au chargement.
//
// esmHandleEnter() est appelee depuis logx_lookup.js (onCallKeydown(),
// 17e increment) et logx_logbook.js (handler keydown du champ indicatif,
// pas encore extrait), toutes deux en corps de fonction.
//
// Seul appel TOP-LEVEL externe au bloc, juste apres dans logx_logbook.js :
// renderVoiceDynPanel(); -- sur au chargement uniquement parce que ce
// fichier est charge AVANT logx_logbook.js (convention EV-7).

// ─── CALLBOT (macros vocales DYNAMIQUES : synthèse + PTT + émission radio) ───
// Contrairement aux macros CW ({CALL} = TA propre station, jamais celle du
// correspondant — pas besoin en CW de re-taper l'indicatif de l'autre), ici
// {CALL} = LE CORRESPONDANT actuellement tapé dans la saisie (l'usage typique
// en phonie : confirmer qui on appelle avant le report), {MYCALL} = ta station.
const VOICE_MACRO_DEFAULT = [
  {key:'B1', label:'CQ', text:'CQ Contest, {MYCALL}'},
  {key:'B2', label:'RÉPONSE', text:'{CALL}'},
  {key:'B3', label:'REPORT', text:'{RST_SENT}, {MYCALL}'},
  {key:'B4', label:'73 + MERCI', text:'{TNX}, {MYCALL}'},
];
// Rend une COPIE du défaut (jamais la RÉFÉRENCE de la const) : editVoiceDynMacro
// fait `macros[idx]={...}` et corromprait sinon VOICE_MACRO_DEFAULT en place —
// les valeurs d'usine (et le repli si localStorage devient illisible) seraient
// perdues pour toute la session.
function getVoiceDynMacros(){ try{ const s=localStorage.getItem('logx_voice_macros'); return s?JSON.parse(s):VOICE_MACRO_DEFAULT.map(m=>({...m})); }catch(e){ return VOICE_MACRO_DEFAULT.map(m=>({...m})); } }
function saveVoiceDynMacros(m){ localStorage.setItem('logx_voice_macros', JSON.stringify(m)); }

function renderVoiceDynPanel(){
  const btns = document.getElementById('voiceDynBtns');
  if(!btns) return;
  const macros = getVoiceDynMacros();
  btns.innerHTML = '';
  macros.forEach((m, idx) => {
    const btn = document.createElement('button');
    btn.className = 'macro-btn';
    btn.title = m.text;
    btn.innerHTML = `<span class="mk">${m.key}</span><span class="mt">${m.label}</span>`;
    btn.onclick    = e => { e.stopPropagation(); sendVoiceDynMacro(idx); };
    btn.ondblclick = e => { e.stopPropagation(); editVoiceDynMacro(idx); };
    btns.appendChild(btn);
  });
}

async function sendVoiceDynMacro(idx){
  const m = getVoiceDynMacros()[idx]; if(!m) return;
  const cfg = JSON.parse(localStorage.getItem('logx_config')||'{}');
  const rstRcvdEl = document.getElementById('inputRSTrcvd');
  const numSentEl = document.getElementById('inputNumSent');
  const payload = {
    template: m.text,
    call: document.getElementById('inputCall').value.trim(),
    mycall: cfg.callsign_contest || cfg.callsign || myCall || '',
    rst_sent: document.getElementById('inputRSTsent').value.trim() || '59',
    rst_rcvd: rstRcvdEl ? rstRcvdEl.value.trim() : '',
    nr: numSentEl ? numSentEl.value.trim() : '',
  };
  const out = document.getElementById('voiceDynResult');
  if(out) out.textContent = '⏳…';
  try{
    const r = await fetch('/rig/voice', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)});
    const d = await r.json();
    if(out) out.textContent = d.ok ? `📻 « ${d.text} »` : `❌ ${d.error}`;
  }catch(e){
    if(out) out.textContent = '❌ ' + e.message;
  }
}

function editVoiceDynMacro(idx){
  const macros = getVoiceDynMacros();
  const m = macros[idx];
  const newLabel = prompt(trF('Label pour {k} :', {k: m.key}), m.label);
  if(newLabel === null) return;
  const newText = prompt(trT('Message ({CALL}=correspondant · {MYCALL}=toi · {RST_SENT}/{RST_RCVD}/{NR} en toutes lettres · {TNX}=73+merci selon le pays) :'), m.text);
  if(newText === null) return;
  macros[idx] = {...m, label:newLabel.trim()||m.label, text:newText.trim()||m.text};
  saveVoiceDynMacros(macros); renderVoiceDynPanel();
}

// ─── ESM (Enter Sends Message) ───────────────────────────────────────────────
// Entrée enchaîne : (champ vide) appel CQ → (indicatif saisi) échange → (Entrée
// dans le N° reçu) log + « merci ». Utilise le keyer CW (macros) ou vocal (WAV)
// selon le mode. À la N1MM.
let esmMode = false, esmExchanged = false;

function toggleEsm(){
  esmMode = !esmMode;
  const b = document.getElementById('esmBtn');
  if(b){ b.textContent = 'ESM '+(esmMode?'●':'○'); b.style.color = esmMode?'var(--green)':'var(--muted)';
    b.style.borderColor = esmMode?'var(--green)':'var(--border)'; }
  notify(esmMode ? trT('⏎ ESM activé : Entrée enchaîne appel → échange → log') : trT('ESM désactivé'));
}

function esmSend(role){
  // Même repli que updateKeyerPanels() juste plus bas : le mode réel du QSO
  // (rigState.mode si le CAT est connecté, sinon currentMode) décide, JAMAIS
  // rigState.enabled. Avant ce correctif, exiger .enabled faisait passer un
  // opérateur en CW MANUEL (clé/manip externe, pas de CAT) par la voix — un
  // message vocal réel joué au lieu du CW attendu, pas une simple dégradation
  // d'affichage (trouvé le 08/08/2026 pendant l'extraction EV-7 du bloc
  // RADIO CAT, corrigé séparément sur demande explicite de F4GLD).
  const mode = (typeof rigState!=='undefined' && rigState.mode) || currentMode || '';
  const cw = /CW/i.test(mode);
  if(cw){
    // Macros CW par convention : F1=CQ, F2=échange/report, F3=merci
    const idx = {cq:0, exchange:1, tu:2}[role] ?? 0;
    if(typeof copyMacro==='function') copyMacro(idx);
  }else{
    const slot = {cq:'V1', exchange:'V3', tu:'V4'}[role] || 'V1';
    voicePlay(slot);
  }
}

// Appelée par la touche Entrée du champ indicatif quand ESM est actif.
// Retourne true si ESM a « consommé » l'Entrée (pas de log immédiat).
function esmHandleEnter(){
  if(!esmMode) return false;
  const call = document.getElementById('inputCall').value.trim();
  if(!call){ esmSend('cq'); return true; }
  if(!esmExchanged){
    esmSend('exchange'); esmExchanged = true;
    const nr = document.getElementById('inputNumRcvd') || document.getElementById('inputRSTrcvd');
    if(nr) nr.focus();
    return true;
  }
  return false;   // échange déjà envoyé → laisser submitQSO() logguer
}
