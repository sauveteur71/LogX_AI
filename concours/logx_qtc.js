// ─── QTC (WAE) (EV-7, docs/LogX_AI_PRD.md) ───────────────────────────────────
// 6e incrément du refactor EV-7 : extrait tel quel de logx_logbook.js (aucune
// restructuration nécessaire — panneau déjà auto-contenu). Saisie et
// historique des séries QTC du règlement WAEDC : score final =
// (QSO + QTC) × mults, chaque QTC transféré (émis OU reçu) vaut 1 point. Une
// série QTC copie de 1 à 10 QSO déjà loggués vers/depuis une autre station —
// voir logx_export.build_cabrillo pour le format WAE-QTC exporté (une ligne
// "QTC:" par QSO rapporté, vérifié contre les règles publiques DARC/WAEDC).
//
// Dépend de globals restés dans logx_logbook.js (portée globale partagée via
// <script> classique, voir logx_logbook.html) : currentBand, currentMode,
// escHtml(), notify(), trF(), trT(). Aucune fonction de ce fichier n'est
// appelée depuis le cœur (renderLog(), la sauvegarde d'un QSO, l'init de
// page, les dispatchers auto-appelés) : showQTCPanel() n'est déclenché que
// par le bouton dédié #qtcBtn (onclick HTML, pas dans le menu DÉBUT/FIN), et
// le setInterval/setTimeout de refreshQTC() en bas de fichier n'appelle que
// du code interne à ce même fichier.
const QTC_BANDS = ['3.5', '7', '14', '21', '28'];   // seules bandes HF du WAE
let qtcEntries = [];      // dernier /qtc/list connu (séries déjà enregistrées)
let qtcRows = [{time: '', call: '', nr: ''}];   // lignes en cours de saisie

async function refreshQTC(){
  try{
    const r = await fetch('/qtc/list');
    if(!r.ok) return;
    const d = await r.json();
    qtcEntries = d.entries || [];
    const btn = document.getElementById('qtcBtn');
    if(!btn) return;
    // Icône fixe dans le HTML (jamais réécrite ici) : ne toucher que le
    // compteur, pour ne pas écraser le <svg> par du texte brut.
    const countEl = document.getElementById('qtcCount');
    if(countEl) countEl.textContent = d.total || 0;
    // Afficher le bouton pour les concours à QTC (WAE*) — sinon masqué
    const contest = (JSON.parse(localStorage.getItem('logx_config')||'{}').contest)||'';
    btn.style.display = /^WAEDC/i.test(contest) ? '' : 'none';
    if(document.getElementById('qtcOverlay')?.classList.contains('show')) renderQTCList();
  }catch(e){}
}

function showQTCPanel(){
  const ov = document.getElementById('qtcOverlay');
  if(!ov) return;
  ov.classList.add('show');
  const bandSel = document.getElementById('qtcBand');
  if(bandSel) bandSel.value = QTC_BANDS.includes(currentBand) ? currentBand : '14';
  const modeSel = document.getElementById('qtcMode');
  if(modeSel) modeSel.value = /CW/i.test(currentMode) ? 'CW' : (/RTTY|DIGI|FT/i.test(currentMode) ? 'RTTY' : 'SSB');
  resetQTCFields();
  qtcRows = [{time: '', call: '', nr: ''}];
  renderQTCRows();
  suggestQTCSeriesNumber();
  renderQTCList();
}

function closeQTCPanel(){
  document.getElementById('qtcOverlay')?.classList.remove('show');
  resetQTCFields();
}

// Remet indicatif partenaire + sens à leur valeur neutre — sans ça, le
// panneau gardait l'indicatif ET le sens (émis/reçu) de la série PRÉCÉDENTE
// d'une ouverture à l'autre (et après un enregistrement réussi), au risque
// de logguer la série suivante sous le mauvais indicatif/sens par inattention.
function resetQTCFields(){
  const dirSel = document.getElementById('qtcDirection');
  if(dirSel) dirSel.value = 'sent';
  const partnerInput = document.getElementById('qtcPartner');
  if(partnerInput) partnerInput.value = '';
}

// Numéro de série suggéré = dernier numéro déjà utilisé DANS CE SENS + 1 (le
// numéro reste modifiable — pour une série reçue, c'est en réalité le numéro
// annoncé par l'AUTRE station qu'il faut reporter, pas un compteur qu'on maîtrise).
function suggestQTCSeriesNumber(){
  const dir = document.getElementById('qtcDirection')?.value || 'sent';
  const maxN = qtcEntries
    .filter(e => (e.direction || 'sent') === dir)
    .reduce((m, e) => Math.max(m, parseInt(e.series_number, 10) || 0), 0);
  const numInput = document.getElementById('qtcSeriesNum');
  if(numInput) numInput.value = maxN + 1;
}

function renderQTCRows(){
  const wrap = document.getElementById('qtcRows');
  if(!wrap) return;
  wrap.innerHTML = qtcRows.map((row, i) => `
    <div style="display:flex;gap:6px;margin-bottom:4px;align-items:center">
      <input type="text" placeholder="HHMM" maxlength="4" value="${escHtml(row.time)}"
        style="width:60px;background:var(--bg3);border:1px solid var(--border);color:var(--text);border-radius:5px;padding:4px 6px"
        onchange="qtcRows[${i}].time=this.value.trim()">
      <input type="text" placeholder="Indicatif" value="${escHtml(row.call)}"
        style="width:110px;text-transform:uppercase;background:var(--bg3);border:1px solid var(--border);color:var(--text);border-radius:5px;padding:4px 6px"
        onchange="qtcRows[${i}].call=this.value.trim().toUpperCase()">
      <input type="text" placeholder="N°" value="${escHtml(row.nr)}"
        style="width:70px;background:var(--bg3);border:1px solid var(--border);color:var(--text);border-radius:5px;padding:4px 6px"
        onchange="qtcRows[${i}].nr=this.value.trim()">
      <span onclick="removeQTCRow(${i})" title="Retirer cette ligne" style="color:var(--red);cursor:pointer;font-size:13px">✕</span>
    </div>`).join('') +
    (qtcRows.length < 10 ?
      `<button class="export-btn" onclick="addQTCRow()" style="margin-top:4px">+ Ligne (${qtcRows.length}/10)</button>` :
      `<div style="color:var(--muted);font-size:12px;margin-top:4px">Maximum 10 QTC par série (règlement WAE)</div>`);
}

function addQTCRow(){
  if(qtcRows.length >= 10) return;
  qtcRows.push({time: '', call: '', nr: ''});
  renderQTCRows();
}

function removeQTCRow(i){
  qtcRows.splice(i, 1);
  if(!qtcRows.length) qtcRows.push({time: '', call: '', nr: ''});
  renderQTCRows();
}

async function saveQTCSeries(){
  const direction = document.getElementById('qtcDirection')?.value || 'sent';
  const call = (document.getElementById('qtcPartner')?.value || '').toUpperCase().trim();
  const band = document.getElementById('qtcBand')?.value || '14';
  const mode = document.getElementById('qtcMode')?.value || 'SSB';
  const series_number = parseInt(document.getElementById('qtcSeriesNum')?.value, 10) || 1;
  if(!call){ notify('QTC refusé : indicatif de la station partenaire manquant.'); return; }
  const entries = qtcRows
    .map(r => ({time: r.time.trim(), call: r.call.trim().toUpperCase(), nr: r.nr.trim()}))
    .filter(r => r.time || r.call || r.nr);
  if(!entries.length){ notify('QTC refusé : aucune ligne saisie.'); return; }
  if(entries.some(e => !e.time || !e.call || !e.nr)){
    notify('QTC refusé : chaque ligne doit avoir heure + indicatif + n° (règlement WAE).');
    return;
  }
  try{
    const r = await fetch('/qtc/add', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({call, direction, band, mode, series_number, entries})
    });
    const d = await r.json();
    if(r.ok){
      const sens = direction === 'recv' ? 'reçue de' : 'envoyée à';
      notify(trF('✉ Série QTC {num}/{total} {sens} {call} enregistrée — total {pts} pts',
        {num: series_number, total: entries.length, sens: trT(sens), call, pts: d.total}));
      qtcRows = [{time: '', call: '', nr: ''}];
      renderQTCRows();
      resetQTCFields();
      await refreshQTC();
      suggestQTCSeriesNumber();
    } else {
      notify(trF('QTC refusé : {err}', {err: d.error || '?'}));
    }
  }catch(e){ notify('Serveur injoignable — QTC non enregistré.'); }
}

function renderQTCList(){
  const wrap = document.getElementById('qtcListInner');
  if(!wrap) return;
  if(!qtcEntries.length){
    wrap.innerHTML = '<div class="shortcuts-row"><span style="color:var(--muted)">Aucune série QTC enregistrée pour ce concours.</span></div>';
    return;
  }
  wrap.innerHTML = qtcEntries.slice().reverse().map(e => {
    const dirLabel = e.direction === 'recv' ? '⬇ reçue de' : '⬆ envoyée à';
    const n = (e.entries || []).length || e.count || 0;
    const grp = e.series_number ? `QTC ${e.series_number}/${n}` : `${n} QTC`;
    const delBtn = (e.id != null) ?
      `<span onclick="deleteQTCSeries(${e.id})" title="Supprimer cette série"
         style="cursor:pointer;color:var(--red);margin-left:auto;font-size:13px">🗑</span>` : '';
    return `<div class="shortcuts-row" style="align-items:center;gap:8px">
      <span style="color:var(--accent2)">${dirLabel} ${escHtml(e.call || '?')}</span>
      <span style="color:var(--muted);font-size:12px">${grp} — ${escHtml(e.date || '')} ${escHtml(e.time || '')}</span>
      ${delBtn}
    </div>`;
  }).join('');
}

async function deleteQTCSeries(id){
  if(!confirm(trT('Supprimer cette série QTC ?'))) return;
  try{ await fetch(`/qtc/delete/${id}`, {method: 'DELETE'}); }catch(e){}
  await refreshQTC();
}

setInterval(refreshQTC, 60*1000);
setTimeout(refreshQTC, 1500);
