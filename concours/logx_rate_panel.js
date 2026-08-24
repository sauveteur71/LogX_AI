// ─── PANNEAU STATISTIQUES / RATE CHART (EV-7, docs/LogX_AI_PRD.md) ──────────
// 3e incrément du refactor EV-7 : dernier bloc de logx_logbook.js avant ce
// chantier (extrait tel quel, aucune restructuration nécessaire — panneau
// déjà auto-contenu). Rythme QSO/heure (Chart.js), répartition par bande et
// par heure — panneau "📊 STATS", laissé délibérément visible en mode
// débutant lors de l'audit d'intuitivité du 07/08/2026 ("repère de
// progression motivant dès les premiers QSO").
function showRatePanel(){
  const ov = document.getElementById('rateOverlay');
  if(ov){ ov.classList.add('show'); renderRateChart(); }
}
function closeRatePanel(){
  const ov = document.getElementById('rateOverlay');
  if(ov) ov.classList.remove('show');
  if(window._rateChartInst){ window._rateChartInst.destroy(); window._rateChartInst = null; }
}
function switchRateTab(tab, btn){
  document.querySelectorAll('.rate-tab').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('rateTabRate').style.display = tab === 'rate' ? '' : 'none';
  document.getElementById('rateTabBand').style.display = tab === 'band' ? '' : 'none';
  document.getElementById('rateTabHour').style.display = tab === 'hour' ? '' : 'none';
  if(tab === 'rate') renderRateChart();
  else if(tab === 'band') renderBandStats();
  else renderHourStats();
}
// 'YYYYMMDDHH' depuis les champs réels du QSO (date 'YYYYMMDD' + time 'HHMM'
// ou 'HH:MM') — les deux fonctions ci-dessous lisaient un champ `.datetime`
// qui n'a jamais été posé nulle part sur un objet QSO (bug silencieux : le
// panneau 📊 STATS affichait toujours "aucun QSO", même log bien rempli).
function _qsoHourKey(q){
  if(!q || !q.date) return null;
  const d = String(q.date).replace(/-/g, '');
  if(d.length < 8) return null;
  const t = String(q.time || '0000').replace(':', '').padEnd(4, '0');
  return d.slice(0, 8) + t.slice(0, 2);
}

function renderRateChart(){
  if(typeof Chart === 'undefined'){ console.warn('Chart.js non chargé'); return; }
  const buckets = {};
  qsoLog.forEach(q => {
    const h = _qsoHourKey(q);
    if(!h) return;
    buckets[h] = (buckets[h]||0) + 1;
  });
  const keys = Object.keys(buckets).sort();
  const labels = [], data = [];
  if(keys.length){
    // Comble les heures SANS QSO d'un zéro (pas de trou invisible dans le
    // rythme — un vrai graphique sur toute la session, pas un instantané).
    const toDate = k => new Date(Date.UTC(+k.slice(0,4), +k.slice(4,6)-1, +k.slice(6,8), +k.slice(8,10)));
    let cur = toDate(keys[0]);
    const end = toDate(keys[keys.length-1]);
    // Borne défensive : qsoLog est le carnet UNIQUE (toutes bandes/années). Deux
    // QSO éloignés (reprise le lendemain, import d'un log ancien) ou une date
    // corrompue (99991231) généreraient des milliers de barres vides, voire un
    // gel du navigateur. Une session réelle n'approche jamais un mois d'heures ;
    // au-delà, on n'affiche que la fenêtre la plus RÉCENTE (fin - MAX_HEURES).
    const MAX_HEURES = 24 * 31;
    if((end - cur) / 3600000 > MAX_HEURES - 1){
      cur = new Date(end.getTime() - (MAX_HEURES - 1) * 3600000);
    }
    while(cur <= end){
      const key = cur.getUTCFullYear() + String(cur.getUTCMonth()+1).padStart(2,'0')
                + String(cur.getUTCDate()).padStart(2,'0') + String(cur.getUTCHours()).padStart(2,'0');
      labels.push(String(cur.getUTCHours()).padStart(2,'0') + 'h');
      data.push(buckets[key] || 0);
      cur = new Date(cur.getTime() + 3600000);
    }
  }
  const ctx = document.getElementById('rateChart');
  if(!ctx) return;
  if(window._rateChartInst) window._rateChartInst.destroy();
  window._rateChartInst = new Chart(ctx, {
    type:'bar',
    data:{
      labels,
      datasets:[{ label:'QSO/heure', data, backgroundColor:'rgba(0,212,255,.55)', borderColor:'#00D4FF', borderWidth:1 }]
    },
    options:{
      responsive:true, maintainAspectRatio:false,
      scales:{
        y:{ beginAtZero:true, ticks:{color:'#A9B0C8'}, grid:{color:'rgba(255,255,255,.05)'} },
        x:{ ticks:{color:'#A9B0C8'}, grid:{color:'rgba(255,255,255,.05)'} }
      },
      plugins:{ legend:{ labels:{ color:'#E9ECF5', font:{family:'Share Tech Mono'} } } }
    }
  });
}
function renderBandStats(){
  const body = document.getElementById('bandStatsBody');
  if(!body) return;
  const bands = {};
  qsoLog.forEach(q => {
    const b = q.band || currentBand || '?';
    if(!bands[b]) bands[b] = {qso:0, pts:0, mults:new Set()};
    bands[b].qso++;
    bands[b].pts += (Number(q.points)||0);
    if(q.locator) bands[b].mults.add(q.locator.toUpperCase().slice(0,4));
  });
  const rows = Object.entries(bands).sort((a,b)=>parseFloat(a[0])-parseFloat(b[0]));
  const totQso = rows.reduce((s,[,v])=>s+v.qso,0);
  const totPts = rows.reduce((s,[,v])=>s+v.pts,0);
  const totScore = rows.reduce((s,[,v])=>s+v.pts*v.mults.size,0);
  body.innerHTML = rows.map(([b,s])=>{
    const sc = s.pts*s.mults.size;
    return `<tr><td>${escHtml(b)}m</td><td>${s.qso}</td><td>${s.pts}</td><td>${s.mults.size}</td><td>${sc}</td></tr>`;
  }).join('') + (rows.length?`<tr><td>TOTAL</td><td>${totQso}</td><td>${totPts}</td><td>—</td><td>${totScore}</td></tr>`:'')
    || '<tr><td colspan="5" style="text-align:center;color:var(--muted);padding:18px">Aucun QSO — saisis un indicatif dans le panneau SAISIE et appuie sur Entrée 🎙</td></tr>';
}
function renderHourStats(){
  const head = document.getElementById('hourHead');
  const body = document.getElementById('hourBody');
  if(!head||!body) return;
  const allBands = [...new Set(qsoLog.map(q=>q.band||currentBand||'?'))].sort((a,b)=>parseFloat(a)-parseFloat(b));
  const rows = {};
  qsoLog.forEach(q => {
    const hk = _qsoHourKey(q);
    if(!hk) return;
    const h = hk.slice(8,10)+'h';
    const b = q.band||currentBand||'?';
    if(!rows[h]) rows[h]={};
    rows[h][b] = (rows[h][b]||0)+1;
  });
  head.innerHTML = '<tr><th>HEURE</th>'+allBands.map(b=>`<th>${escHtml(b)}m</th>`).join('')+'<th>TOTAL</th></tr>';
  const sorted = Object.entries(rows).sort((a,b)=>a[0].localeCompare(b[0]));
  body.innerHTML = sorted.map(([h,bs])=>{
    const tot = Object.values(bs).reduce((a,c)=>a+c,0);
    return `<tr><td>${escHtml(h)}</td>${allBands.map(b=>`<td>${bs[b]||0}</td>`).join('')}<td>${tot}</td></tr>`;
  }).join('') || '<tr><td colspan="99" style="text-align:center;color:var(--muted);padding:18px">Aucun QSO</td></tr>';
}
