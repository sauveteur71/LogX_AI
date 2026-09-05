// EV-7 42e increment : PREREMPLISSAGE MODAL + NOMS OPERATEURS -- extrait de
// logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script> classique dans
// logx_logbook.html, AVANT logx_logbook.js -- portee globale partagee.
//
// Contient : prefillSetupFromConfig() (prerempli le modal de setup depuis la
// config + noms des operateurs). Non appelee au TOP-LEVEL ; invoquee par des
// handlers (logbook.html) et par logx_contest_picker.js / logx_outils_divers.js,
// a l'usage -- ordre de <script> indifferent.

// ─── PRÉREMPLISSAGE MODAL + NOMS OPÉRATEURS ──────────────────────────────────
function prefillSetupFromConfig(){
  let cfg = {};
  try{ cfg = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}

  applyUsageModeToLogbook(cfg.usage_mode);

  // Pré-remplir indicatif et locator
  const callEl  = document.getElementById('setupCallsign');
  const locEl   = document.getElementById('setupLocator');
  const opEl    = document.getElementById('setupOperator');

  // Callsign : localStorage (config perso) prioritaire sur le serveur
  if(cfg.callsign_contest || cfg.callsign || serverCallsign)
    callEl.value = cfg.callsign_contest || cfg.callsign || serverCallsign;
  if(cfg.locator || serverLocator)
    locEl.value = cfg.locator || serverLocator;
  // Choix explicite utilisateur (localStorage) prioritaire sur le défaut serveur
  const contestToSet = cfg.contest || serverContest;
  if(contestToSet) csSetValue(contestToSet);

  // Injecter les vrais noms opérateurs depuis config
  const ops = cfg.operators || [];
  // SINGLE-OP : la section concours SO* (Single Operator) prime — un seul
  // opérateur, sélecteur inutile. On considère aussi single-op si la config
  // ne liste qu'un opérateur. Sinon (MO*) : le multi-op reste disponible.
  // LOGBOOK SIMPLE : un seul opérateur, point — le rôle auparavant tenu par
  // le champ CLUB ici (radio-club = plusieurs opérateurs qui se relaient) est
  // désormais assuré par le mode RADIOCLUB dédié (cf. logx_configuration.html).
  // RADIOCLUB : jusqu'à 40 opérateurs, pas de classification SO*/MO* EDI
  // pertinente ici — seul le nombre d'opérateurs déclarés compte.
  const isSingleOp = usageMode === 'simple'
    ? true
    : usageMode === 'radioclub'
    ? ops.length <= 1
    : (/^SO/i.test(cfg.section || '') || ops.length <= 1);
  if(ops.length){
    opEl.innerHTML = '<option value="">-- Sélectionne ton identifiant opérateur --</option>';
    ops.forEach((op, i) => {
      const val = `OP${i+1}`;
      const call = op.call || op.callsign || '';
      const lbl = call ? `${escHtml(val)} — ${escHtml(call)}${op.name?' ('+escHtml(op.name)+')':''}` : escHtml(val);
      opEl.innerHTML += `<option value="${escHtml(val)}">${lbl}</option>`;
    });
    // Boutons OP du formulaire : régénérés depuis la config (jusqu'à 40 en
    // mode RADIOCLUB, la grille flex existante wrap automatiquement) — un
    // bouton par opérateur réellement configuré, plus de OP4/OP5 fantômes.
    const opPopupEl = document.getElementById('opPickerPopup');
    const activeOp = opPopupEl.querySelector('.op-btn.active')?.dataset.op || myOp;
    opPopupEl.innerHTML = ops.map((op, i) => {
      const val = `OP${i+1}`;
      const call = op.call || op.callsign || val;
      return `<button class="op-btn${val===activeOp?' active':''}" data-op="${val}" onclick="pickOp('${val}')">${escHtml(call)}</button>`;
    }).join('');
    _setCurrentOpLabel(activeOp);
  }
  // Masquer tout ce qui est multi-op en single-op : sélecteur d'opérateur,
  // classement par opérateur, chat inter-postes. L'opérateur reste OP1.
  const opGroup = document.getElementById('opCurrentBtn').closest('.field-group');
  if(opGroup) opGroup.style.display = isSingleOp ? 'none' : '';
  const opStats = document.getElementById('opStatsBar');
  if(opStats) opStats.style.display = isSingleOp ? 'none' : '';
  const chatPanel = document.getElementById('chatPanel');
  if(chatPanel) chatPanel.style.display = isSingleOp ? 'none' : '';
  const peersInfo = document.getElementById('netPeers');
  if(peersInfo && isSingleOp){
    const wrap = peersInfo.closest('span'); if(wrap) wrap.style.display = 'none';
  }
  // Colonne OP du tableau de QSO : même logique, un seul opérateur rend la
  // colonne redondante (bruit visuel). Classe posée sur le conteneur du
  // tableau plutôt que sur chaque <td> (régénérés à chaque renderLog()) —
  // masquage CSS pur, cf. règle .single-op-mode .th-op-col/.td-op-col.
  const logTableWrap = document.getElementById('logTableWrap');
  if(logTableWrap) logTableWrap.classList.toggle('single-op-mode', isSingleOp);
  if(isSingleOp){
    myOp = 'OP1';
    const cur = document.getElementById('currentOp');
    if(cur) cur.textContent = (ops[0] && (ops[0].call || ops[0].callsign)) || cfg.callsign || 'OP1';
  }

  const modal = document.getElementById('setupModal');

  // Config complète → démarrage direct, sans afficher le modal
  if(callEl.value && locEl.value){
    if(!opEl.value) opEl.value = 'OP1';
    // modal reste caché (display:none par défaut)
    setupDone();
  } else {
    // Config incomplète → afficher le modal pour que l'utilisateur complète
    modal.style.display = 'flex';
  }
}
