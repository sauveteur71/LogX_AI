// EV-7 43e increment : BARRES DE STATS (classement operateurs + recap par bande)
// -- extrait de logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script>
// classique dans logx_logbook.html, AVANT logx_logbook.js -- portee globale.
//
// Contient : updateOpStats() (classement operateurs multi-op, barre opStatsBar)
// et updateBandRecap() (recap QSO par bande, barre bandRecapBar). Comme
// drawHourChart (logx_hour_chart.js), elles suivent la regle bandeauxRythmeMasques
// et sont appelees par le panneau de stats du coeur. Non appelees au TOP-LEVEL.

// ─── CLASSEMENT OPÉRATEURS (multi-op) ─────────────────────────────────────────
function updateOpStats(){
  const bar   = document.getElementById('opStatsBar');
  const inner = document.getElementById('opStatsInner');
  if(!bar || !inner) return;
  if(bandeauxRythmeMasques()){ bar.style.display = 'none'; return; }

  const opsUsed = new Set(qsoLog.map(q=>q.operator).filter(Boolean));
  if(opsUsed.size < 2){ bar.style.display = 'none'; return; }

  const stats = {};
  qsoLog.forEach(q=>{
    const op = q.operator || '—';
    if(!stats[op]) stats[op] = {count:0, pts:0};
    stats[op].count++;
    stats[op].pts += q.points || 0;
  });

  const sorted = Object.entries(stats).sort((a,b)=>b[1].pts-a[1].pts);
  const topPts = sorted.length ? sorted[0][1].pts : 0;
  inner.innerHTML = sorted.map(([op, d])=>{
    const opColor = opColorAttr(op);
    const isLeader = d.pts === topPts && topPts > 0;
    return `<div class="ops-item${isLeader?' leader':''}">`
      + `<div class="ops-op ${opColor.cls}" style="border-radius:4px;display:inline-block;padding:1px 8px;${opColor.style}">${escHtml(_resolveOperatorCallsign(op))}${isLeader?' 🏆':''}</div>`
      + `<div class="ops-lbl">QSO · PTS</div>`
      + `<div class="ops-vals">${d.count} · ${d.pts.toLocaleString()}</div>`
      + `</div>`;
  }).join('');
  bar.style.display = 'block';
}

// ─── RÉCAP PAR BANDE ─────────────────────────────────────────────────────────
function updateBandRecap(){
  const bar   = document.getElementById('bandRecapBar');
  const inner = document.getElementById('bandRecapInner');
  if(!bar || !inner) return;
  if(bandeauxRythmeMasques()){ bar.style.display = 'none'; return; }
  if(qsoLog.length === 0){ bar.style.display = 'none'; return; }

  const bands = {};
  qsoLog.forEach(q => {
    const b = q.band || '?';
    if(!bands[b]) bands[b] = {count:0, totalKm:0, maxKm:0, bestCall:'—', bestBear:'—'};
    const km = (q.locator && q.locator.length >= 6) ? calcDist(q.locator) : 0;
    bands[b].count++;
    bands[b].totalKm += km;
    if(km > bands[b].maxKm){
      bands[b].maxKm   = km;
      bands[b].bestCall = q.call || '—';
      if(q.locator && q.locator.length >= 6){ const brg = bearing(q.locator); if(brg !== null) bands[b].bestBear = cardinalDir(brg); }
    }
  });

  const sortedBands = Object.keys(bands).sort((a,b) => (parseFloat(a)||0) - (parseFloat(b)||0));
  inner.innerHTML = '';
  sortedBands.forEach(b => {
    const d   = bands[b];
    const lbl = BAND_LABELS[b] || `${b} MHz`;
    const div = document.createElement('div');
    div.className = 'brd-item';
    div.innerHTML =
      `<div class="brd-band">${lbl}</div>` +
      `<div class="brd-lbl">QSO · KM TOTAL · DX MAX</div>` +
      `<div class="brd-vals">${d.count} · ${Math.round(d.totalKm).toLocaleString()} km · <span class="brd-dx">${Math.round(d.maxKm)} km</span></div>` +
      `<div class="brd-vals" style="color:var(--muted);font-size:12px">${escHtml(d.bestCall)} ${escHtml(d.bestBear)}</div>`;
    inner.appendChild(div);
  });
  bar.style.display = 'block';
}
