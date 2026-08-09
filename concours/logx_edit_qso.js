// ─── EV-7 : ÉDITION QSO (extrait de logx_logbook.js) ──────────────────────
// editQSO()/saveEdit()/deleteQSO()/deleteQSOSilent()/undoLastQSO() + les
// champs ADIF personnalisés (renderEditExtraFields/addEditExtraField/
// removeEditExtraField/updateEditExtraField) et leurs utilitaires
// (updateEditDistInfo/closeEdit). Chargé en <script> classique AVANT
// logx_logbook.js dans logx_logbook.html — même portée globale partagée,
// pas de module ES.
//
// Grep exhaustif fait AVANT extraction (candidat n°3 de
// inventaire-ev7-23e-2026-08-09.md) : AUCUN appel top-level restant dans
// logx_logbook.js ne dépend d'un symbole de ce fichier — editQSO()/
// deleteQSO() n'apparaissent dans logx_logbook.js QUE comme texte à
// l'intérieur de templates onclick/ondblclick (attributs HTML générés
// par renderLog(), résolus par le navigateur au moment du clic, pas au
// chargement du script).
//
// Dépendances croisées EN CORPS DE FONCTION (sûres dans ce modèle à
// portée globale partagée, documentées ici par prudence) :
//   - logx_dup_finder.js appelle deleteQSOSilent() (suppression en lot,
//     une seule confirmation) ;
//   - logx_theme_shortcuts.js appelle undoLastQSO() (raccourci Ctrl+Z) ;
//   - logx_verif_panel.js appelle editQSO() depuis fixFromValidation()
//     (bouton "Corriger" sur un constat IA du panneau VÉRIFIER).
// Aucune de ces trois n'est exercée par un test V8 qui n'aurait pas déjà
// besoin de charger ce fichier (vérifié : test_macros_au_clavier.py ne
// teste que le bloc F1-F8, pas Ctrl+Z ; test_peer_version_xss.py exerce
// showChecklist() mais jamais fixFromValidation()).
//
// Ce fichier appelle en retour des fonctions restées dans le cœur
// (calcDist/calcPoints/renderLog/updateStats/bcBroadcast/notify/trT/trF/
// nowUTC/nowDateUTC) — sûr pour la même raison (portée globale partagée,
// résolution au moment de l'appel, pas au chargement).

// ─── ÉDITION QSO ─────────────────────────────────────────────────────────────
// Mémorise l'élément qui avait le focus au moment de l'ouverture de la modale
// (ex. le bouton crayon de la ligne QSO) pour le lui rendre à la fermeture
// (closeEdit()) — sans ça, un utilisateur clavier perd son repère de position
// dans la page après Échap ou un clic sur la croix.
let _editQsoTrigger = null;

function editQSO(id, triggerEl){
  const q = qsoLog.find(x=>x.id===id);
  if(!q) return;
  // triggerEl : repli explicite pour les appelants qui masquent leur propre
  // overlay AVANT d'appeler editQSO() (ex. fixFromValidation()) -- à ce
  // moment-là document.activeElement a déjà été blur() vers <body> par le
  // navigateur (l'ancêtre focus devient display:none), donc le capturer ici
  // serait trop tard. Revue adversariale 09/08/2026.
  _editQsoTrigger = triggerEl || document.activeElement;
  document.getElementById('editId').value = id;
  document.getElementById('editCall').value = q.call||'';
  document.getElementById('editDate').value = q.date||'';
  document.getElementById('editTime').value = q.time||'';
  document.getElementById('editRSTsent').value = q.rst_sent||'';
  document.getElementById('editNumSent').value = q.num_sent||'';
  document.getElementById('editRSTrcvd').value = q.rst_rcvd||'';
  document.getElementById('editNumRcvd').value = q.num_rcvd||'';
  document.getElementById('editFreq').value = q.freq||'';
  // Peupler le select bande avec les bandes du concours — PLUS celle du QSO
  // si elle n'y est pas (QSO logué sous un autre concours actif, ou hors
  // concours). Piège corrigé ici : un <select> a TOUJOURS une valeur dès
  // qu'il a des <option> (le navigateur sélectionne la première par défaut
  // si aucune n'a "selected") — `if(!editBandSel.value)` n'est donc jamais
  // vrai et ce filet ne se déclenchait jamais, laissant la bande/le mode
  // réels du QSO silencieusement remplacés par le premier choix de la
  // liste (ex. un QSO FT8 affiché "SSB" en édition dès que le concours
  // actif ne compte pas FT8 parmi ses modes). Corrigé en garantissant que
  // l'option existe TOUJOURS, plutôt qu'en réparant après coup une valeur
  // que le select a déjà mal choisie.
  const editBandSel = document.getElementById('editBand');
  const contestBands = CONTEST_BANDS[currentContest] || ALL_BANDS;
  const editBandOptions = (q.band && !contestBands.includes(q.band)) ? [...contestBands, q.band] : contestBands;
  editBandSel.innerHTML = editBandOptions.map(b =>
    `<option value="${b}"${b===q.band?' selected':''}>${BAND_LABELS[b]||b+' MHz'}</option>`
  ).join('');
  // Peupler le select mode avec les modes du concours — même correctif.
  const editModeSel = document.getElementById('editMode');
  const contestModes = CONTEST_MODES[currentContest] || ['SSB','CW','FM','FT8','FT4','RTTY'];
  const editModeOptions = (q.mode && !contestModes.includes(q.mode)) ? [...contestModes, q.mode] : contestModes;
  editModeSel.innerHTML = editModeOptions.map(m =>
    `<option value="${m}"${m===q.mode?' selected':''}>${m}</option>`
  ).join('');
  document.getElementById('editLocator').value = q.locator||'';
  updateEditDistInfo(q.locator);
  document.getElementById('editLocator').addEventListener('input', function(){
    updateEditDistInfo(this.value.toUpperCase());
    this.value = this.value.toUpperCase();
  });
  // EV-7 phase 2 : premier pilote du bus d'événements (voir logx_scan_qsl.js
  // pour le pourquoi). Le cœur ne connaît plus _renderEditQslScan() ; il
  // notifie juste qu'un QSO vient de s'ouvrir en édition.
  document.dispatchEvent(new CustomEvent('logx:qso-editing-opened', {detail: {qso: q}}));
  const scanStatus = document.getElementById('editQslScanStatus');
  if(scanStatus) scanStatus.textContent = '';
  // Champs ADIF personnalisés : {NOM: valeur} -> tableau de paires éditables
  // (un objet ne préserve pas un ordre de saisie fiable une fois qu'on retire
  // puis rajoute des clés, un tableau si).
  editExtraFields = Object.entries(q.extra_fields || {}).map(([name, value]) => ({name, value}));
  renderEditExtraFields();
  document.getElementById('editOverlay').classList.add('show');
  document.getElementById('editCall').focus();
}

// ─── CHAMPS ADIF PERSONNALISÉS ────────────────────────────────────────────
// N'importe quel tag ADIF que LogX ne modélise pas nativement (ex. MY_RIG,
// COMMENT, un champ propriétaire d'un autre logiciel) — stocké sous
// q.extra_fields, qui part dans la colonne `extra` générique de logx_storage
// (_row_from_qso sérialise déjà TOUTE clé hors de _CORE, aucun changement
// serveur nécessaire) et ressort tel quel à l'export ADIF (buildAdifText).
let editExtraFields = [];

function renderEditExtraFields(){
  const wrap = document.getElementById('editExtraFields');
  if(!wrap) return;
  const esc = s => String(s==null?'':s).replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  wrap.innerHTML = editExtraFields.map((f, i) => `<div class="exf-row">
    <input type="text" placeholder="NOM_CHAMP" value="${esc(f.name)}" oninput="updateEditExtraField(${i},'name',this.value)">
    <input type="text" placeholder="valeur" value="${esc(f.value)}" oninput="updateEditExtraField(${i},'value',this.value)">
    <span class="exf-del" onclick="removeEditExtraField(${i})" title="Retirer">✕</span>
  </div>`).join('');
}

function addEditExtraField(){
  editExtraFields.push({name:'', value:''});
  renderEditExtraFields();
}

function removeEditExtraField(i){
  editExtraFields.splice(i, 1);
  renderEditExtraFields();
}

function updateEditExtraField(i, key, value){
  editExtraFields[i][key] = value;
}

function updateEditDistInfo(loc){
  const info = document.getElementById('editDistInfo');
  if(loc && loc.length===6){
    const dist = calcDist(loc);
    const pts = calcPoints(loc, document.getElementById('editBand').value||currentBand);
    if(dist>0){
      info.textContent = `📏 Distance : ${dist} km → 🏆 ${pts} pts`;
      info.style.display = 'block';
    }
  } else {
    info.style.display = 'none';
  }
}

function closeEdit(){
  document.getElementById('editOverlay').classList.remove('show');
  if(_editQsoTrigger && typeof _editQsoTrigger.focus === 'function') _editQsoTrigger.focus();
  _editQsoTrigger = null;
}

async function saveEdit(){
  const id = parseInt(document.getElementById('editId').value);
  const q = qsoLog.find(x=>x.id===id);
  if(!q) return;

  const newCall = document.getElementById('editCall').value.trim().toUpperCase();
  const newLoc  = document.getElementById('editLocator').value.trim().toUpperCase();
  const newBand = document.getElementById('editBand').value;
  const newDate = document.getElementById('editDate').value.trim() || nowDateUTC();
  const newTime = document.getElementById('editTime').value.trim() || nowUTC();

  if(!newCall){ notify('Indicatif manquant !'); return; }
  if(!/^\d{8}$/.test(newDate)){ notify('Date invalide !\nFormat attendu : AAAAMMJJ (ex: 20260705)'); return; }
  if(!/^\d{1,2}:\d{2}$/.test(newTime)){ notify('Heure invalide !\nFormat attendu : HH:MM (ex: 14:32)'); return; }

  const dist = calcDist(newLoc);
  const newMode = document.getElementById('editMode')?.value || q.mode || 'SSB';
  const pts  = newLoc ? calcPoints(newLoc, newBand, newCall, newMode) : 0;

  // Mise à jour locale
  Object.assign(q, {
    call: newCall,
    date: newDate,
    time: newTime,
    rst_sent: document.getElementById('editRSTsent').value.trim()||'59',
    num_sent: document.getElementById('editNumSent').value.trim(),
    rst_rcvd: document.getElementById('editRSTrcvd').value.trim()||'59',
    num_rcvd: currentExchange.pad_r === true
      ? (v=>v?String(parseInt(v,10)||0).padStart(3,'0'):'')(document.getElementById('editNumRcvd').value.trim())
      : document.getElementById('editNumRcvd').value.trim(),
    band: newBand,
    mode: document.getElementById('editMode').value,
    freq: document.getElementById('editFreq').value.trim(),
    locator: newLoc,
    dist, points: pts,
    _edited: true,
  });

  // Champs ADIF personnalisés : noms vides ignorés, normalisés en MAJUSCULES
  // (convention ADIF) ; underscore/tiret/point tolérés (variantes courantes,
  // ex. "MY.RIG" recopié d'un autre logiciel), le reste retiré pour rester un
  // nom de tag ADIF valide. Objet supprimé plutôt que laissé vide : un QSO
  // sans champ personnalisé ne doit pas trimballer `extra_fields:{}` pour
  // toujours dans le log partagé.
  const extraObj = {};
  editExtraFields.forEach(f => {
    const name = String(f.name||'').trim().toUpperCase().replace(/[^A-Z0-9_.-]/g, '');
    if(name) extraObj[name] = f.value||'';
  });
  if(Object.keys(extraObj).length) q.extra_fields = extraObj;
  else delete q.extra_fields;

  // Envoi au serveur
  try{
    await fetch('/log/update', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(q)
    });
  }catch(e){ console.warn('Serveur hors ligne, correction locale uniquement'); }

  closeEdit();
  renderLog();
  updateStats();
}

// Sans confirmation ni re-rendu : factorisée pour les suppressions en lot
// (recherche de doublons) qui ne veulent qu'UNE confirmation pour tout le
// lot, pas une par QSO, et qui rafraîchissent l'affichage une seule fois
// après la dernière suppression plutôt qu'à chaque itération.
async function deleteQSOSilent(id){
  qsoLog = qsoLog.filter(q=>q.id!==id);
  try{
    await fetch(`/log/delete/${id}`, {method:'DELETE'});
  }catch(e){}
  bcBroadcast('delete', {id});
}

async function deleteQSO(id){
  if(!confirm(trT('Supprimer ce QSO ?'))) return;
  await deleteQSOSilent(id);
  renderLog();
  updateStats();
}

async function undoLastQSO(){
  if(!qsoLog.length){ notify('Aucun QSO à annuler !'); return; }
  const last = qsoLog[qsoLog.length-1];
  if(!confirm(trF('Annuler le dernier QSO ?\n{call} — {band} MHz — {time}', {call: last.call, band: last.band, time: last.time}))) return;
  qsoLog = qsoLog.slice(0,-1);
  try{
    await fetch(`/log/delete/${last.id}`, {method:'DELETE'});
  }catch(e){}
  renderLog();
  updateStats();
}
