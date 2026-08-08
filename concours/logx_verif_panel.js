// ─── PANNEAU VÉRIFIER (EV-7, docs/LogX_AI_PRD.md) ────────────────────────────
// 4e incrément du refactor EV-7 : extrait tel quel de logx_logbook.js (aucune
// restructuration nécessaire). Checklist avant-trafic (config/base indicatifs/
// réseau/heure/version pairs) + validateur du log (doublons, locators,
// distances, départements) + audit IA à la demande, avec les actions Corriger/
// Supprimer câblées sur les deux.
//
// SENSIBLE SÉCURITÉ — showChecklist() échappe via escHtml() la version
// déclarée par un poste voisin (_lastServerVersion/_versionMismatches, issue
// de GET /log/list?ver=, servi SANS authentification) avant de l'injecter
// dans innerHTML : c'était le seul chemin réseau du fichier oublié par
// escHtml (cf. bandmap, callbook, chat, validation). Couvert par
// tests/test_peer_version_xss.py, qui charge maintenant ce fichier EN PLUS de
// logx_logbook.js avant d'appeler le vrai showChecklist(). Ne jamais retirer
// cet échappement.
//
// Dépend de globals restés dans logx_logbook.js (portée globale partagée via
// <script> classique, voir logx_logbook.html) : escHtml, trT, trF, qsoLog,
// editQSO, renderLog, updateStats, bcBroadcast, _lastServerVersion,
// _myVersion, _lastPeerList, _versionMismatches.
// callDB est extraite depuis le 17e incrément EV-7 (docs/LogX_AI_PRD.md)
// vers logx_lookup.js -- même portée globale partagée, lue ici en corps de
// fonction uniquement, sans importance sur l'ordre relatif des <script>.
function toggleChecklist(){
  document.getElementById('checklistOverlay').classList.toggle('show');
}

async function showChecklist(){
  document.getElementById('checklistOverlay').classList.add('show');
  const inner = document.getElementById('checklistInner');
  inner.innerHTML = '<div class="shortcuts-row"><span>⏳ Vérification en cours…</span></div>';

  const rows = [];

  // 1. Config sauvegardée
  let cfg = {};
  try{ cfg = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}
  const cfgOk = !!(cfg.callsign && cfg.locator && cfg.contest);
  rows.push({ok: cfgOk, label: cfgOk ? `Config sauvegardée (${cfg.callsign}, ${cfg.contest})` : 'Config incomplète — vérifie l\'onglet CONFIG'});

  // 2. Base d'indicatifs chargée
  const dbCount = Object.keys(callDB).length;
  rows.push({ok: dbCount > 0, label: dbCount > 0 ? `Base d'indicatifs chargée (${dbCount.toLocaleString()} entrées)` : 'Base d\'indicatifs non chargée — recharge la page'});

  // 3. Serveur connecté
  const netDotEl = document.getElementById('netDot');
  const netOk = netDotEl && netDotEl.classList.contains('online');
  rows.push({ok: netOk, label: netOk ? 'Serveur connecté' : 'Hors ligne — le log restera local jusqu\'à reconnexion'});

  // 4. Heure synchronisée (comparaison avec l'en-tête Date renvoyé par le serveur)
  let timeOk = false, timeMsg = 'Impossible de vérifier l\'heure serveur';
  try{
    const res = await fetch('/config', {cache:'no-store'});
    const serverDate = new Date(res.headers.get('Date'));
    const diffSec = Math.abs((Date.now() - serverDate.getTime())/1000);
    timeOk = diffSec < 30;
    timeMsg = timeOk ? `Heure système synchronisée (écart ${diffSec.toFixed(0)}s)` : `Écart de ${diffSec.toFixed(0)}s avec le serveur — vérifie l'heure système`;
  }catch(e){}
  rows.push({ok: timeOk, label: timeMsg});

  // 5. Postes connectés (info)
  const peersEl = document.getElementById('netPeers');
  rows.push({ok: true, info: true, label: `Postes connectés au réseau : ${peersEl ? peersEl.textContent : '—'}`});

  // 6. Version cohérente entre postes (même logique que les équipes N1MM qui
  // s'alignent sur un numéro de version avant un événement) — réutilise le
  // dernier snapshot connu (rafraîchi toutes les 60 s par refreshCluster(),
  // voir updateVersionStatus()) plutôt que de refaire un appel réseau ici.
  if(_lastServerVersion){
    const versionMism = _versionMismatches(_lastServerVersion, _myVersion, _lastPeerList);
    // escHtml OBLIGATOIRE ici (faille corrigée) : r.label est injecté tel quel
    // dans inner.innerHTML quelques lignes plus bas, or m.version est une
    // chaîne DÉCLARÉE par un autre poste (GET /log/list?ver=, route servie
    // SANS authentification). Sans échappement, n'importe quel appareil du LAN
    // faisait exécuter son HTML/JS dans cette page — qui porte le cookie de
    // session de l'opérateur, donc accès à /log/reset, /config/save,
    // /auth/set_password... C'était le seul chemin réseau du fichier oublié
    // par escHtml (cf. bandmap, callbook, chat, validation).
    rows.push({
      ok: versionMism.length === 0,
      label: versionMism.length === 0
        ? `Version cohérente sur tous les postes (v${escHtml(_lastServerVersion)})`
        : `Versions différentes : ${versionMism.map(m=>`${escHtml(m.ip)} v${escHtml(m.version)}`).join(', ')} — serveur : v${escHtml(_lastServerVersion)}`,
    });
  } else {
    rows.push({ok: true, info: true, label: 'Version : pas encore vérifiée (patiente quelques secondes puis rouvre la checklist)'});
  }

  inner.innerHTML = rows.map(r=>{
    const icon  = r.info ? 'ℹ️' : (r.ok ? '✅' : '⚠️');
    const color = r.info ? 'var(--accent2)' : (r.ok ? 'var(--green)' : 'var(--yellow)');
    return `<div class="shortcuts-row"><span class="shortcuts-key" style="color:${color};min-width:32px">${icon}</span><span>${r.label}</span></div>`;
  }).join('');
}

// ─── VÉRIFICATION DU LOG AVANT SOUMISSION (validateur serveur, spécial REF) ───
// Doublons, locators absents/invalides, distances anormales, départements
// invalides, QSO hors fenêtre — tout ce qui coûterait des points au contrôle.
async function showValidation(){
  const ov = document.getElementById('validateOverlay');
  const inner = document.getElementById('validateInner');
  if(!ov || !inner) return;
  ov.classList.add('show');
  inner.innerHTML = '<div class="shortcuts-row"><span>⏳ Analyse du log en cours…</span></div>';
  let d;
  try{
    const r = await fetch('/log/validate');
    if(!r.ok) throw new Error('HTTP '+r.status);
    d = await r.json();
  }catch(e){
    inner.innerHTML = `<div class="shortcuts-row"><span style="color:var(--red)">❌ Serveur injoignable (${e.message})</span></div>`;
    return;
  }
  const c = d.counts || {};
  const head =
    `<div class="shortcuts-row" style="font-weight:700">`+
    `<span>${d.qso_count} QSO analysés — `+
    `<span style="color:var(--red)">${c.erreur||0} erreur${(c.erreur||0)>1?'s':''}</span> · `+
    `<span style="color:var(--yellow)">${c.attention||0} à vérifier</span> · `+
    `<span style="color:var(--accent2)">${c.info||0} info${(c.info||0)>1?'s':''}</span></span></div>`;
  // Audit IA APPROFONDI (à la demande) : relit le log et repère ce qu'aucune
  // règle ne code. Déterministe d'abord, IA en bonus — les constats IA se
  // fusionnent SOUS ceux-ci, avec les mêmes boutons Corriger/Supprimer.
  const aiSection =
    `<div class="shortcuts-row expert-only" style="border-top:1px solid var(--border);margin-top:6px;padding-top:8px;gap:8px;align-items:center">`+
    `<button id="aiAuditBtn" class="export-btn" style="color:var(--accent2);border-color:rgba(0,212,255,.4)" onclick="runAiAudit()">🤖 ${escHtml(trT('AUDIT IA APPROFONDI'))}</button>`+
    `<span style="color:var(--muted);font-size:12px">${escHtml(trT('l\'IA relit le log et repère ce que les règles ne voient pas'))}</span>`+
    `</div><div id="aiAuditResults"></div>`;
  if(!(d.findings||[]).length){
    inner.innerHTML = head +
      `<div class="shortcuts-row"><span style="color:var(--green);font-weight:700">`+
      `✅ Aucun problème détecté — le log est prêt à être exporté et envoyé.</span></div>`+
      aiSection;
    return;
  }
  const ICO = {erreur:'❌', attention:'⚠️', info:'ℹ️'};
  const COL = {erreur:'var(--red)', attention:'var(--yellow)', info:'var(--accent2)'};
  const BTN = 'cursor:pointer;border:1px solid var(--border,#3a3a4a);background:transparent;'+
              'border-radius:5px;padding:2px 7px;font-size:13px;line-height:1.4';
  inner.innerHTML = head + d.findings.map(f => {
    // f.msg contient l'indicatif (potentiellement issu d'un ADIF importé) : échappé.
    const act = (f.id != null) ?
      `<span style="display:inline-flex;gap:6px;margin-left:auto;flex:0 0 auto">`+
        `<button style="${BTN};color:var(--accent2)" title="Corriger ce QSO" onclick="fixFromValidation(${f.id})">✏️ Corriger</button>`+
        `<button style="${BTN};color:var(--red)" title="Supprimer ce QSO" onclick="delFromValidation(${f.id})">🗑 Supprimer</button>`+
      `</span>` : '';
    return `<div class="shortcuts-row" style="align-items:center;gap:8px">`+
      `<span class="shortcuts-key" style="color:${COL[f.level]||'var(--muted)'};min-width:32px">${ICO[f.level]||'•'}</span>`+
      `<span>${escHtml(f.msg)}${f.at ? ` <span style="color:var(--muted);font-size:12px">(${escHtml(f.at)})</span>` : ''}</span>`+
      act+
      `</div>`;
  }).join('') + (d.truncated ? `<div class="shortcuts-row"><span style="color:var(--muted)">… liste tronquée</span></div>` : '') + aiSection;
}

// ─── AUDIT IA DU LOG (à la demande, sous le VÉRIFIER déterministe) ───────────
// Lance un job serveur (l'appel LLM peut durer) et poll son état, puis fusionne
// les constats IA — MÊME format {level,msg,id} — avec les boutons Corriger/
// Supprimer déjà câblés. Hors-ligne / sans clé : message clair, jamais d'erreur
// brutale (le VÉRIFIER déterministe, lui, a déjà fait son travail au-dessus).
async function runAiAudit(){
  const res = document.getElementById('aiAuditResults');
  const btn = document.getElementById('aiAuditBtn');
  if(!res) return;
  if(btn) btn.disabled = true;
  res.innerHTML = `<div class="shortcuts-row"><span>⏳ ${escHtml(trT('Audit IA en cours…'))}</span></div>`;
  let id;
  try{
    const r = await fetch('/log/audit', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const j = await r.json();
    if(!r.ok || !j.id) throw new Error(j.error || ('HTTP '+r.status));
    id = j.id;
  }catch(e){
    res.innerHTML = `<div class="shortcuts-row"><span style="color:var(--yellow)">🤖 ${escHtml(trT('Audit IA indisponible'))} — ${escHtml(e.message)}</span></div>`;
    if(btn) btn.disabled = false;
    return;
  }
  const poll = async () => {
    let s;
    try{ const r = await fetch('/log/audit/state?id='+encodeURIComponent(id)); s = await r.json(); }
    catch(e){ setTimeout(poll, 2500); return; }
    if(s.status === 'running'){ setTimeout(poll, 1500); return; }
    if(btn) btn.disabled = false;
    if(s.status === 'done') renderAiFindings(s.findings || [], !!s.truncated);
    else if(s.status === 'error') res.innerHTML = `<div class="shortcuts-row"><span style="color:var(--yellow)">🤖 ${escHtml(trT('Audit IA échoué'))} — ${escHtml(s.error||'')}</span></div>`;
    else res.innerHTML = `<div class="shortcuts-row"><span style="color:var(--muted)">🤖 ${escHtml(trT('Audit introuvable (serveur redémarré ?)'))}</span></div>`;
  };
  poll();
}
function renderAiFindings(findings, truncated){
  const res = document.getElementById('aiAuditResults');
  if(!res) return;
  const ICO = {erreur:'❌', attention:'⚠️', info:'ℹ️'};
  const COL = {erreur:'var(--red)', attention:'var(--yellow)', info:'var(--accent2)'};
  const BTN = 'cursor:pointer;border:1px solid var(--border,#3a3a4a);background:transparent;'+
              'border-radius:5px;padding:2px 7px;font-size:13px;line-height:1.4';
  if(!findings.length){
    res.innerHTML = `<div class="shortcuts-row"><span style="color:var(--green)">🤖 ${escHtml(trT('L\'IA n\'a rien trouvé de plus à corriger.'))}</span></div>`;
    return;
  }
  const headTxt = truncated ? trT('🤖 Constats IA (log tronqué aux plus récents)') : trT('🤖 Constats IA');
  res.innerHTML =
    `<div class="shortcuts-row" style="font-weight:700;color:var(--accent2)"><span>${escHtml(headTxt)}</span></div>`+
    findings.map(f => {
      const act = (f.id != null) ?
        `<span style="display:inline-flex;gap:6px;margin-left:auto;flex:0 0 auto">`+
          `<button style="${BTN};color:var(--accent2)" title="Corriger ce QSO" onclick="fixFromValidation(${f.id})">✏️ ${escHtml(trT('Corriger'))}</button>`+
          `<button style="${BTN};color:var(--red)" title="Supprimer ce QSO" onclick="delFromValidation(${f.id})">🗑 ${escHtml(trT('Supprimer'))}</button>`+
        `</span>` : '';
      return `<div class="shortcuts-row" style="align-items:center;gap:8px">`+
        `<span class="shortcuts-key" style="color:${COL[f.level]||'var(--muted)'};min-width:32px">🤖${ICO[f.level]||''}</span>`+
        `<span>${escHtml(f.msg)}</span>`+ act +`</div>`;
    }).join('');
}

// Corriger un QSO signalé par le VÉRIFIER : ferme la fenêtre de vérification
// et ouvre l'édition du QSO (l'utilisateur peut ensuite RE-VÉRIFIER).
function fixFromValidation(id){
  const ov = document.getElementById('validateOverlay');
  if(ov) ov.classList.remove('show');
  editQSO(id);
}

// Supprimer directement un QSO signalé, puis rafraîchir la liste des problèmes.
async function delFromValidation(id){
  const q = qsoLog.find(x=>x.id===id);
  const label = q ? trF('\n{call} — {band} MHz — {time}', {call: q.call||'?', band: q.band||'?', time: q.time||''}) : '';
  if(!confirm(trF('Supprimer ce QSO ?{label}', {label}))) return;
  qsoLog = qsoLog.filter(x=>x.id!==id);
  try{ await fetch(`/log/delete/${id}`, {method:'DELETE'}); }catch(e){}
  renderLog();
  updateStats();
  try{ bcBroadcast('delete', {id}); }catch(e){}
  showValidation();   // relance la vérification pour refléter la suppression
}
