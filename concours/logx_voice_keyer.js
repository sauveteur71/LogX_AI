// EV-7 phase 2 (docs/LogX_AI_PRD.md) -- 20e increment : KEYER VOCAL (phonie,
// slots DVK cote serveur) extrait tel quel de logx_logbook.js. Charge en
// <script> classique dans logx_logbook.html AVANT logx_logbook.js, portee
// globale partagee (meme convention que les 19 increments precedents).
//
// Contenu : VOICE_SLOTS (const), _mediaRec/_recSlot/_recChunks (etat REC du
// keyer vocal -- a ne pas confondre avec _vkStream/_recMediaRec de
// l'ENREGISTREUR AUDIO PAR QSO, feature voisine mais distincte restee dans
// logx_logbook.js), voiceSlots (etat serveur), voiceRefreshSlots(),
// _voiceMigrationFaite + voiceMigrerAnciens(), renderVoicePanel(),
// voiceRecord(), _blobToBase64(), voicePlay().
//
// Piege deja rencontre au 19e increment (voir logx_esm_callbot.js) et
// documente dans la memoire projet -- APPLIQUE ICI DES LE DEPART : un appel
// TOP-LEVEL restant dans logx_logbook.js, `voiceRefreshSlots();` (ligne
// ~2020, juste a cote de `renderVoiceDynPanel();`), depend desormais de ce
// fichier. Comme pour renderVoiceDynPanel(), ceci casse au PARSE (pas
// seulement a l'appel) tout test qui evalue logx_logbook.js en entier via
// V8/py_mini_racer sans charger ce fichier en premier -- les 14 fichiers de
// tests deja identifies au 19e increment (ceux qui chargent
// ESM_CALLBOT_JS_PATH) ont tous ete mis a jour pour charger aussi ce fichier
// avant logx_logbook.js.
//
// Dependance optionnel->coeur (sens autorise, fonctions seulement, jamais
// top-level dans CE fichier) : notify(), trF(), fetch, window.AudioContext/
// webkitAudioContext, _audioCtx (global reste dans logx_logbook.js, partage
// avec plusieurs features audio dont l'enregistreur QSO), _floatChannelsToWav()
// (reste dans logx_logbook.js, definie plus bas, reference dans une fonction
// -- resolution tardive, sure).
//
// Dependance coeur->optionnel : voicePlay() est appelee par
// logx_esm_callbot.js (esmSend(), role vocal) -- sans consequence car cet
// appel se produit lui aussi a l'interieur d'une fonction (jamais au
// chargement), et les DEUX fichiers sont de toute facon charges avant
// logx_logbook.js.

// ─── KEYER VOCAL (phonie) ────────────────────────────────────────────────────
// Enregistre de courts messages WAV (CQ, réponse, report, merci) et les rejoue
// d'un clic — l'équivalent phonie des macros CW. Stockés en base64 (localStorage).
const VOICE_SLOTS = [
  {key:'V1', label:'CQ'}, {key:'V2', label:'RÉPONSE'},
  {key:'V3', label:'REPORT'}, {key:'V4', label:'MERCI'},
];
let _mediaRec = null, _recSlot = null, _recChunks = [], _vkStream = null;

// Emplacements DVK réellement enregistrés, tels que le SERVEUR les connaît.
// Ils y sont stockés (et non plus en localStorage) pour deux raisons : ils sont
// joués par le serveur vers la radio, et ils doivent suivre l'opérateur d'un
// poste à l'autre — c'est tout l'intérêt du multi-poste.
let voiceSlots = {};
async function voiceRefreshSlots(){
  try{
    const d = await fetch('/voice/slots').then(r => r.json());
    voiceSlots = d.slots || {};
  }catch(e){ /* serveur injoignable : on garde le dernier état connu */ }
  renderVoicePanel();
  voiceMigrerAnciens();
}

// Reprise des messages enregistrés AVANT que le stockage passe côté serveur.
// Ils dormaient en localStorage au format WebM. Les abandonner sans rien dire
// serait une perte de données silencieuse — même si, tels quels, ils ne
// partaient de toute façon pas sur l'air.
// Une seule tentative : en cas d'échec de conversion on laisse la clé en place
// plutôt que de la détruire, et on n'insiste pas à chaque chargement de page.
let _voiceMigrationFaite = false;
async function voiceMigrerAnciens(){
  if(_voiceMigrationFaite) return;
  _voiceMigrationFaite = true;
  let anciens = {};
  try{ anciens = JSON.parse(localStorage.getItem('rc_voice') || '{}'); }catch(e){ return; }
  const aReprendre = Object.keys(anciens).filter(k => voiceSlots[k] === undefined && anciens[k]);
  if(!aReprendre.length) return;
  let repris = 0;
  for(const cle of aReprendre){
    try{
      const blob = await (await fetch(anciens[cle])).blob();   // data URL -> Blob
      const ctx = _audioCtx || (_audioCtx = new (window.AudioContext || window.webkitAudioContext)());
      const buf = await ctx.decodeAudioData(await blob.arrayBuffer());
      const canaux = [];
      for(let c = 0; c < buf.numberOfChannels; c++) canaux.push(buf.getChannelData(c));
      const b64 = await _blobToBase64(_floatChannelsToWav(canaux, buf.sampleRate));
      const res = await fetch('/voice/save', {method:'POST', headers:{'Content-Type':'application/json'},
                                              body: JSON.stringify({slot: cle, wav_base64: b64})}).then(r=>r.json());
      if(res.ok){ delete anciens[cle]; repris++; }
    }catch(e){ /* enregistrement illisible : on le laisse où il est */ }
  }
  if(repris){
    try{ localStorage.setItem('rc_voice', JSON.stringify(anciens)); }catch(e){}
    const d = await fetch('/voice/slots').then(r => r.json()).catch(()=>null);
    if(d && d.slots){ voiceSlots = d.slots; renderVoicePanel(); }
    notify(trF('🎙 {n} message(s) vocal(aux) repris depuis ce navigateur', {n: repris}));
  }
}

function renderVoicePanel(){
  const box = document.getElementById('voiceBtns');
  if(!box) return;
  // flex:1 1 300px (pas width:100%) : chaque ligne PEUT s'étaler sur toute
  // la largeur d'une colonne étroite (ancien emplacement, .saisie-secondary),
  // mais dans .keyer-dock (bandeau plein largeur, 04/08/2026) plusieurs
  // lignes se rangent maintenant côte à côte au lieu de s'empiler une par
  // une — c'est tout l'intérêt du bandeau large : moins de hauteur prise
  // pour le même nombre de messages.
  box.innerHTML = VOICE_SLOTS.map(s => {
    const dur = voiceSlots[s.key];
    const has = dur !== undefined;
    const lbl = has ? `${s.label} <span style="color:var(--muted)">${dur}s</span>` : s.label;
    return `<div style="display:flex;gap:4px;margin:3px 0;flex:1 1 300px;box-sizing:border-box">
      <button class="macro-btn" style="flex:1;min-width:0;max-width:none;text-align:left;${has?'':'opacity:.5'}" onclick="voicePlay('${s.key}')" ${has?'':'disabled'}>▶ ${lbl}</button>
      <button class="macro-btn" style="flex:0 0 36px;min-width:0;max-width:none" onclick="voiceRecord('${s.key}')" id="rec_${s.key}" title="Enregistrer ${s.label}">⏺</button>
      ${has?`<button class="macro-btn" style="flex:0 0 36px;min-width:0;max-width:none" onclick="voiceDelete('${s.key}')" title="Effacer ${s.label}">🗑</button>`:''}
    </div>`;
  }).join('');
}

async function voiceRecord(key){
  const btn = document.getElementById('rec_'+key);
  if(_mediaRec && _recSlot === key){   // 2e clic = stop
    _mediaRec.stop();
    return;
  }
  if(_mediaRec){
    // Un AUTRE slot enregistre encore (clic REC ailleurs sans avoir arrêté) :
    // on l'abandonne PROPREMENT avant d'en ouvrir un nouveau. Sinon son flux
    // micro restait ouvert (fuite) et ses chunks se mélangeaient au nouveau
    // slot. On neutralise son onstop pour qu'il ne fasse QUE fermer son propre
    // flux -- surtout PAS remettre à zéro _mediaRec/_recSlot/_recChunks, qui
    // vont appartenir au nouvel enregistrement (l'onstop est asynchrone et se
    // déclencherait APRÈS qu'on a installé le nouveau : il écraserait son état).
    const ancienStream = _vkStream;
    const ancienBtn = document.getElementById('rec_' + _recSlot);
    _mediaRec.ondataavailable = null;
    _mediaRec.onstop = () => { if(ancienStream) ancienStream.getTracks().forEach(t=>t.stop()); };
    try{ _mediaRec.stop(); }catch(_){}
    if(ancienBtn){ ancienBtn.textContent = '⏺'; ancienBtn.style.color=''; }
    _mediaRec = null; _recSlot = null; _vkStream = null;
  }
  try{
    const stream = await navigator.mediaDevices.getUserMedia({audio:true});
    _recChunks = []; _recSlot = key; _vkStream = stream;
    _mediaRec = new MediaRecorder(stream);
    _mediaRec.ondataavailable = e => { if(e.data.size) _recChunks.push(e.data); };
    _mediaRec.onstop = async () => {
      stream.getTracks().forEach(t=>t.stop());
      const blob = new Blob(_recChunks, {type: _mediaRec.mimeType||'audio/webm'});
      _mediaRec = null; _recSlot = null; _vkStream = null;
      if(btn){ btn.textContent = '⏺'; btn.style.color=''; }
      // Réencodage en WAV AVANT l'envoi : le navigateur enregistre en WebM/Opus,
      // que le serveur ne sait pas jouer (wave.open). On réutilise l'encodeur
      // déjà écrit pour les clips de QSO plutôt que d'en poser un second.
      try{
        const ctx = _audioCtx || (_audioCtx = new (window.AudioContext || window.webkitAudioContext)());
        const buf = await ctx.decodeAudioData(await blob.arrayBuffer());
        const canaux = [];
        for(let c = 0; c < buf.numberOfChannels; c++) canaux.push(buf.getChannelData(c));
        const wav = _floatChannelsToWav(canaux, buf.sampleRate);
        const b64 = await _blobToBase64(wav);
        const res = await fetch('/voice/save', {method:'POST', headers:{'Content-Type':'application/json'},
                                                body: JSON.stringify({slot: key, wav_base64: b64})}).then(r=>r.json());
        if(res.ok){ await voiceRefreshSlots();
so2rRafraichir(); notify(trF('🎙 Message {key} enregistré', {key})); }
        else       notify(trF('❌ {err}', {err: res.error || 'enregistrement refusé'}));
      }catch(e){ notify(trF('❌ Réencodage impossible : {err}', {err: e.message})); }
    };
    _mediaRec.start();
    if(btn){ btn.textContent = '■'; btn.style.color='var(--red)'; }
    notify('🎙 Enregistrement… reclique ⏺ pour arrêter');
  }catch(e){ notify(trF('❌ Micro indisponible : {err}', {err: e.message})); }
}

// Base64 d'un Blob, sans concaténation manuelle (un message de plusieurs
// secondes dépasse la taille d'argument de String.fromCharCode(...tableau)).
function _blobToBase64(blob){
  return new Promise((resolve, reject) => {
    const rd = new FileReader();
    rd.onload = () => resolve(String(rd.result).split(',', 2)[1] || '');
    rd.onerror = () => reject(rd.error || new Error('lecture impossible'));
    rd.readAsDataURL(blob);
  });
}

// Le message part par la RADIO, pas par les enceintes : le serveur lève le PTT,
// joue le WAV vers le périphérique de sortie choisi en CONFIG (câble vers
// l'entrée micro de la radio) puis relâche le PTT en vérifiant qu'il est bien
// retombé. `new Audio().play()` ne faisait aucune des trois choses.
async function voicePlay(key){
  if(voiceSlots[key] === undefined) return;
  try{
    // Interrupteur maître + mode + fréquence (txArmePayload) : sans ces champs,
    // le garde-fou TX serveur (logx_tx_guard) refuse la voix (403). Une station
    // désarmée n'émet pas — même règle que le CW.
    const res = await fetch('/voice/play', {method:'POST', headers:{'Content-Type':'application/json'},
                                            body: JSON.stringify(Object.assign({slot: key},
                                              (typeof txArmePayload === 'function' ? txArmePayload() : {})))}).then(r=>r.json());
    if(!res.ok) notify(trF('❌ {err}', {err: res.error || 'émission impossible'}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}

async function voiceDelete(key){
  if(voiceSlots[key] === undefined) return;
  try{
    const res = await fetch('/voice/delete', {method:'POST', headers:{'Content-Type':'application/json'},
                                              body: JSON.stringify({slot: key})}).then(r=>r.json());
    if(res.ok) await voiceRefreshSlots();
    else       notify(trF('❌ {err}', {err: res.error || 'suppression refusée'}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}
