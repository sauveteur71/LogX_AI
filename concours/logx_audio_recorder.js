// EV-7 37e increment : ENREGISTREUR AUDIO PAR QSO -- extrait de
// logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script> classique dans
// logx_logbook.html, AVANT logx_logbook.js et logx_cw_panel2_audio.js --
// portee globale partagee (comme tous les fichiers EV-7).
//
// Contient : les constantes REC_* (segment / tampon glissant / clip), l'etat
// du recorder (recEnabled, _recStream, _recMediaRec, _recRestartTimer,
// _recSegments, _recDirHandle) et les 22 fonctions du tampon glissant :
// _recMimeType/_recPruneSegments/_recStartSegment/_recFinishCurrentSegment/
// _recRestartSegment/_updateRecToggleBtn/_updateRecDirLabel/startAudioRecorder/
// stopAudioRecorder/toggleAudioRecorder/onRecDeviceChange/_recIdbOpen/
// _recIdbGet/_recIdbSet/chooseRecDir/_recAutoStartAllowed/initAudioRecorderPanel/
// _encodeWavFromBuffers/_floatChannelsToWav/_recClipName/_recSaveClip/
// captureQsoAudioClip. Depend au RUNTIME de loadAudioInputDevices()/
// loadAudioOutputDevices() (logx_cw_panel2_audio.js) : appel a l'usage, donc
// l'ordre relatif des deux <script> est indifferent.

// ─── ENREGISTREUR AUDIO PAR QSO (tampon glissant) ────────────────────────────
// Principe : le flux micro/entrée choisi est enregistré en petits segments
// AUTONOMES (redémarrage périodique du MediaRecorder) plutôt qu'en flux
// continu — un WebM/Ogg découpé en plein milieu n'est pas rejouable (seul le
// tout premier fragment contient l'en-tête du conteneur). Un segment complet,
// lui, EST rejouable seul, donc décodable indépendamment via Web Audio.
// Au log d'un QSO : on clôt le segment en cours (capture jusqu'à MAINTENANT),
// on décode les derniers segments couvrant REC_CLIP_SECONDS, on les recolle
// en PCM brut puis on réencode en WAV (format simple, universellement
// lisible) — pas de recollage naïf de plusieurs fichiers WebM bout à bout,
// que la plupart des lecteurs ne rejouent que jusqu'au premier morceau.
const REC_SEGMENT_MS   = 5000;    // durée d'un segment avant redémarrage
const REC_BUFFER_MS    = 130000;  // tampon glissant conservé (~2 min + marge)
const REC_CLIP_SECONDS = 20;      // durée du clip découpé au moment du log

let recEnabled = (localStorage.getItem('logx_rec_enabled') === 'on');
let _recStream = null, _recMediaRec = null, _recRestartTimer = null;
let _recSegments = [];      // [{blob, start, end}] du plus ancien au plus récent
let _recDirHandle = null;   // FileSystemDirectoryHandle (API File System Access), si choisi

function _recMimeType(){
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus', 'audio/mp4'];
  for(const c of candidates){
    if(window.MediaRecorder && MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(c)) return c;
  }
  return '';
}

function _recPruneSegments(){
  const cutoff = Date.now() - REC_BUFFER_MS;
  while(_recSegments.length && _recSegments[0].end < cutoff) _recSegments.shift();
}

// Démarre UN segment autonome sur le flux déjà ouvert (_recStream). Chaque
// segment ferme son propre tableau de chunks (pas de variable partagée) :
// sinon un redémarrage juste après stop() risquerait de mélanger les données
// du segment sortant avec celles du segment entrant (l'événement
// dataavailable/stop du premier arrive de façon asynchrone, APRÈS que le
// second ait déjà commencé à écrire).
function _recStartSegment(){
  if(!_recStream) return;
  const start = Date.now();
  const chunks = [];
  const mime = _recMimeType();
  let rec;
  try{ rec = mime ? new MediaRecorder(_recStream, {mimeType: mime}) : new MediaRecorder(_recStream); }
  catch(e){ rec = new MediaRecorder(_recStream); }
  rec.ondataavailable = e => { if(e.data && e.data.size) chunks.push(e.data); };
  rec.onstop = () => {
    if(chunks.length){
      _recSegments.push({blob: new Blob(chunks, {type: rec.mimeType || mime || 'audio/webm'}), start, end: Date.now()});
      _recPruneSegments();
    }
  };
  rec.start();
  _recMediaRec = rec;
}

// Clôt le segment EN COURS et attend que son onstop (poussée dans
// _recSegments) soit passé, avant de relancer un nouveau segment — utilisé
// au moment du log pour capturer l'audio jusqu'à l'instant présent au lieu
// de s'arrêter au dernier redémarrage périodique (jusqu'à REC_SEGMENT_MS de
// retard sinon).
function _recFinishCurrentSegment(){
  return new Promise(resolve => {
    if(!_recMediaRec || _recMediaRec.state === 'inactive'){ resolve(); return; }
    const rec = _recMediaRec;
    const prevOnStop = rec.onstop;
    rec.onstop = ev => { try{ if(prevOnStop) prevOnStop(ev); } finally { resolve(); } };
    try{ rec.stop(); }catch(e){ resolve(); }
  });
}

function _recRestartSegment(){
  if(!recEnabled || !_recMediaRec || _recMediaRec.state === 'inactive') return;
  _recMediaRec.stop();     // pousse le segment sortant dans _recSegments (via son propre onstop)
  _recStartSegment();      // enchaîne aussitôt (léger trou possible, best effort)
}

function _updateRecToggleBtn(){
  const on = !!_recStream;
  const b = document.getElementById('qsoRecToggleBtn');
  if(b){
    b.textContent = on ? '● actif' : '○ désactivé';
    b.style.color = on ? 'var(--red)' : 'var(--muted)';
    b.style.borderColor = on ? 'var(--red)' : 'var(--border)';
  }
  // Indicateur TOUJOURS visible (en dehors du panneau .expert-only) : quel
  // que soit le mode UI (débutant/expert), un enregistrement micro actif ne
  // doit jamais rester invisible — le bouton ci-dessus, lui, est masqué avec
  // tout le panneau en mode simple.
  let ind = document.getElementById('qsoRecIndicator');
  if(on){
    if(!ind){
      ind = document.createElement('div');
      ind.id = 'qsoRecIndicator';
      ind.title = 'Enregistrement micro actif (enregistreur QSO)';
      ind.style.cssText = 'position:fixed;top:8px;right:8px;z-index:99999;background:var(--red);color:#fff;font-family:var(--font-mono);font-size:11px;padding:3px 9px;border-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,.4)';
      ind.textContent = '● REC';
      document.body.appendChild(ind);
    }
  } else if(ind){
    ind.remove();
  }
}

function _updateRecDirLabel(){
  const el = document.getElementById('qsoRecDirLabel');
  if(el) el.textContent = _recDirHandle ? ('dossier : ' + _recDirHandle.name) : 'téléchargement direct';
}

async function startAudioRecorder(){
  try{
    const deviceId = localStorage.getItem('logx_rec_device') || '';
    const constraints = {audio: deviceId ? {deviceId: {exact: deviceId}} : true};
    _recStream = await navigator.mediaDevices.getUserMedia(constraints);
    _recSegments = [];
    _recStartSegment();
    _recRestartTimer = setInterval(_recRestartSegment, REC_SEGMENT_MS);
    await loadAudioInputDevices('qsoRecDevice', true);   // true : le flux ci-dessus a déjà obtenu la permission, pas un second getUserMedia
    const sel = document.getElementById('qsoRecDevice');
    if(sel && deviceId) sel.value = deviceId;
    _updateRecToggleBtn();
    notify(trF('🎙️ Enregistreur QSO actif (tampon {s}s)', {s: Math.round(REC_BUFFER_MS/1000)}));
    return true;
  }catch(e){
    notify(trF('❌ Micro indisponible pour l\'enregistreur QSO : {err}', {err: e.message}));
    _recStream = null;
    _updateRecToggleBtn();
    return false;
  }
}

function stopAudioRecorder(){
  if(_recRestartTimer){ clearInterval(_recRestartTimer); _recRestartTimer = null; }
  if(_recMediaRec && _recMediaRec.state !== 'inactive'){
    _recMediaRec.onstop = null;   // désactivation volontaire : ce dernier segment partiel ne sert plus
    try{ _recMediaRec.stop(); }catch(e){}
  }
  _recMediaRec = null;
  if(_recStream){ _recStream.getTracks().forEach(t => t.stop()); _recStream = null; }
  _recSegments = [];
  _updateRecToggleBtn();
}

async function toggleAudioRecorder(){
  if(_recStream){
    stopAudioRecorder();
    recEnabled = false;
  } else {
    recEnabled = await startAudioRecorder();
  }
  localStorage.setItem('logx_rec_enabled', recEnabled ? 'on' : 'off');
}

async function onRecDeviceChange(){
  const val = document.getElementById('qsoRecDevice').value || '';
  localStorage.setItem('logx_rec_device', val);
  if(_recStream){   // changement à chaud : redémarre le flux sur le nouveau périphérique
    stopAudioRecorder();
    await startAudioRecorder();
  }
}

// ─── Choix du dossier de sauvegarde (File System Access API) ────────────────
// Optionnel : sans dossier choisi (ou navigateur non compatible — Firefox et
// Safari n'implémentent pas showDirectoryPicker), chaque clip est simplement
// proposé en téléchargement.
function _recIdbOpen(){
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('logx_audio_rec', 1);
    req.onupgradeneeded = () => { if(!req.result.objectStoreNames.contains('kv')) req.result.createObjectStore('kv'); };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}
async function _recIdbGet(key){
  try{
    const db = await _recIdbOpen();
    return await new Promise((resolve, reject) => {
      const r = db.transaction('kv', 'readonly').objectStore('kv').get(key);
      r.onsuccess = () => resolve(r.result || null);
      r.onerror = () => reject(r.error);
    });
  }catch(e){ return null; }
}
async function _recIdbSet(key, val){
  try{
    const db = await _recIdbOpen();
    await new Promise((resolve, reject) => {
      const tx = db.transaction('kv', 'readwrite');
      tx.objectStore('kv').put(val, key);
      tx.oncomplete = resolve; tx.onerror = () => reject(tx.error);
    });
  }catch(e){}
}

async function chooseRecDir(){
  if(!('showDirectoryPicker' in window)){
    notify('❌ Ce navigateur ne propose pas le choix de dossier (Chrome/Edge requis) — repli sur le téléchargement.');
    return;
  }
  try{
    _recDirHandle = await window.showDirectoryPicker({id: 'logx-audio-rec', mode: 'readwrite'});
    await _recIdbSet('dirHandle', _recDirHandle);
    _updateRecDirLabel();
    notify(trF('📁 Dossier des clips QSO : {name}', {name: _recDirHandle.name}));
  }catch(e){ /* sélection annulée par l'utilisateur */ }
}

// Décide si l'auto-démarrage au chargement de page est autorisé. Isolée en
// fonction pure (aucun I/O) pour rester testable indépendamment du DOM/micro
// réel : ne JAMAIS démarrer automatiquement l'enregistreur en mode UI
// « simple » (débutant, cf. logx_statusbar.js) — le panneau #qsoRecPanel qui
// porte le bouton marche/arrêt est masqué par .expert-only dans ce mode, donc
// injoignable ; un démarrage silencieux y serait un enregistrement micro sans
// AUCUN contrôle visible pour l'utilisateur (problème de confidentialité).
function _recAutoStartAllowed(){
  return recEnabled && localStorage.getItem('rc_ui_mode') !== 'simple';
}

// Restaure au chargement le dossier choisi lors d'une session précédente, si
// la permission est encore valable — queryPermission() ne montre jamais de
// popup (contrairement à requestPermission(), qui exige un geste utilisateur,
// d'où le bouton « Dossier… » pour la reconnexion si la permission a expiré).
async function initAudioRecorderPanel(){
  try{
    const handle = await _recIdbGet('dirHandle');
    if(handle && (await handle.queryPermission({mode: 'readwrite'})) === 'granted'){
      _recDirHandle = handle;
    }
  }catch(e){}
  _updateRecDirLabel();
  if(recEnabled && !_recAutoStartAllowed()){
    // Mode UI simple : on refuse l'auto-démarrage ET on resynchronise l'état
    // persisté (sinon 'logx_rec_enabled' resterait 'on' en localStorage alors
    // que rien n'enregistre réellement — incohérence au prochain passage en
    // mode expert, qui redémarrerait le micro sans que l'utilisateur l'ait
    // redemandé cette fois-là).
    recEnabled = false;
    localStorage.setItem('logx_rec_enabled', 'off');
  } else if(recEnabled){
    const ok = await startAudioRecorder();
    if(!ok){
      // Permission refusée/périphérique disparu depuis : ne pas rester dans
      // un état incohérent — corriger AUSSI localStorage, pas seulement la
      // variable JS locale (sinon un rechargement de page retenterait
      // indéfiniment le même auto-démarrage voué à l'échec).
      recEnabled = false;
      localStorage.setItem('logx_rec_enabled', 'off');
    }
  }
  _updateRecToggleBtn();
}

// ─── Encodage WAV (PCM 16 bits) à partir de plusieurs AudioBuffer ───────────
// Concatène les canaux en ne gardant que les `maxSeconds` dernières secondes
// (les segments les plus anciens fournis peuvent dépasser la fenêtre voulue :
// seule leur QUEUE est conservée).
function _encodeWavFromBuffers(buffers, maxSeconds){
  const sampleRate = buffers[buffers.length-1].sampleRate;
  const numChannels = buffers[buffers.length-1].numberOfChannels || 1;
  const maxSamples = Math.round(maxSeconds * sampleRate);
  let totalLen = 0;
  buffers.forEach(b => totalLen += b.length);
  const keepLen = Math.min(totalLen, maxSamples);

  const channels = [];
  for(let ch = 0; ch < numChannels; ch++){
    const out = new Float32Array(keepLen);
    let writePos = keepLen;   // rempli depuis la fin vers le début
    for(let i = buffers.length - 1; i >= 0 && writePos > 0; i--){
      const b = buffers[i];
      const data = ch < b.numberOfChannels ? b.getChannelData(ch) : b.getChannelData(0);
      const take = Math.min(data.length, writePos);
      out.set(data.subarray(data.length - take), writePos - take);
      writePos -= take;
    }
    channels.push(out);
  }
  return _floatChannelsToWav(channels, sampleRate);
}

function _floatChannelsToWav(channels, sampleRate){
  const numChannels = channels.length;
  const numFrames = channels[0].length;
  const blockAlign = numChannels * 2;   // PCM 16 bits = 2 octets/échantillon
  const dataSize = numFrames * blockAlign;
  const buf = new ArrayBuffer(44 + dataSize);
  const view = new DataView(buf);
  const writeStr = (off, s) => { for(let i=0;i<s.length;i++) view.setUint8(off+i, s.charCodeAt(i)); };
  writeStr(0, 'RIFF'); view.setUint32(4, 36 + dataSize, true); writeStr(8, 'WAVE');
  writeStr(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);   // PCM
  view.setUint16(22, numChannels, true); view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * blockAlign, true); view.setUint16(32, blockAlign, true); view.setUint16(34, 16, true);
  writeStr(36, 'data'); view.setUint32(40, dataSize, true);
  let off = 44;
  for(let i = 0; i < numFrames; i++){
    for(let ch = 0; ch < numChannels; ch++){
      const s = Math.max(-1, Math.min(1, channels[ch][i]));
      view.setInt16(off, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      off += 2;
    }
  }
  return new Blob([buf], {type: 'audio/wav'});
}

// Nom de fichier indicatif_bande_date_heure — ex. F4ABC_144_20260723_143205.wav
// qso.time ne contient que HH:MM (pas les secondes, voir nowUTC()) : deux QSO
// du même indicatif+bande dans la MÊME MINUTE UTC (ex. relogué après un
// bust, ou dupe autorisée par le règlement) produiraient sinon EXACTEMENT le
// même nom de fichier — le second clip écraserait silencieusement le premier.
// qso.id (Date.now() au moment du log, voir submitQSO) donne une précision à
// la milliseconde : on en dérive heure:minute:seconde pour lever la collision.
function _recClipName(qso){
  const call = String(qso.call || 'QSO').replace(/[^A-Za-z0-9]/g, '') || 'QSO';
  const band = String(qso.band || '').replace(/[^A-Za-z0-9]/g, '');
  const stamp = qso.id ? new Date(qso.id) : new Date();
  const time = String(stamp.getUTCHours()).padStart(2, '0')
    + String(stamp.getUTCMinutes()).padStart(2, '0')
    + String(stamp.getUTCSeconds()).padStart(2, '0');
  return `${call}_${band}_${qso.date || ''}_${time}.wav`;
}

// Sauvegarde via l'API File System Access si un dossier a été choisi (et que
// la permission tient toujours), sinon repli sur un téléchargement classique.
async function _recSaveClip(blob, name){
  if(_recDirHandle){
    try{
      if((await _recDirHandle.queryPermission({mode: 'readwrite'})) === 'granted'){
        const fh = await _recDirHandle.getFileHandle(name, {create: true});
        const w = await fh.createWritable();
        await w.write(blob);
        await w.close();
        notify(trF('🎙️ Clip QSO enregistré : {name}', {name}));
        return;
      }
    }catch(e){ console.warn('[REC] écriture dossier échouée, repli téléchargement', e); }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 4000);
  notify(trF('🎙️ Clip QSO téléchargé : {name}', {name}));
}

// Appelée juste après chaque QSO loggué avec succès (voir submitQSO). Ne
// bloque jamais le flux de saisie : appelée sans await depuis submitQSO,
// erreurs avalées.
async function captureQsoAudioClip(qso){
  if(!recEnabled || !_recStream) return;
  try{
    await _recFinishCurrentSegment();
    _recStartSegment();   // ré-enchaîne aussitôt le tampon glissant

    const cutoff = Date.now() - REC_CLIP_SECONDS * 1000;
    const segs = _recSegments.filter(s => s.end > cutoff);
    if(!segs.length) return;

    const ctx = _audioCtx || (_audioCtx = new (window.AudioContext || window.webkitAudioContext)());
    const buffers = [];
    for(const s of segs){
      try{
        const arr = await s.blob.arrayBuffer();
        buffers.push(await ctx.decodeAudioData(arr));
      }catch(e){ /* segment trop court/corrompu (ex: tout premier après un redémarrage) : ignoré */ }
    }
    if(!buffers.length) return;

    const wav = _encodeWavFromBuffers(buffers, REC_CLIP_SECONDS);
    await _recSaveClip(wav, _recClipName(qso));
  }catch(e){ console.warn('[REC] capture clip QSO', e); }
}
