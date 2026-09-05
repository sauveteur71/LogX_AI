// EV-7 41e increment : GRAPHE QSO/HEURE (sparkline SVG inline) -- extrait de
// logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script> classique dans
// logx_logbook.html, AVANT logx_logbook.js -- portee globale partagee.
//
// Contient : drawHourChart() (barre de rythme QSO/heure, SVG inline + pic).
// Non appelee au TOP-LEVEL ; invoquee par le panneau de stats du coeur.

// ─── GRAPHE QSO/HEURE (sparkline SVG inline) ─────────────────────────────────
function drawHourChart(){
  const bar  = document.getElementById('hourChartBar');
  const svg  = document.getElementById('hourChartSvg');
  const peak = document.getElementById('hourChartPeak');
  if(!bar || !svg) return;
  if(bandeauxRythmeMasques()){ bar.style.display = 'none'; return; }
  if(qsoLog.length === 0){ bar.style.display = 'none'; return; }

  // Grouper par heure UTC (clé = "YYYYMMDD-HH")
  const buckets = {};
  qsoLog.forEach(q => {
    if(!q.date || !q.time) return;
    const key = q.date + '-' + q.time.slice(0,2);
    buckets[key] = (buckets[key]||0) + 1;
  });
  const keys = Object.keys(buckets).sort();
  if(keys.length === 0){ bar.style.display = 'none'; return; }

  const maxVal = Math.max(...Object.values(buckets));
  // Heure courante UTC pour surligner la barre active
  const now = new Date();
  const nowKey = now.toISOString().slice(0,8).replace(/-/g,'') + '-' + now.toISOString().slice(11,13);

  // Dimensions SVG en unités viewBox
  const VW = 1000, VH = 40;
  const n = keys.length;
  const gap = 1;
  // Math.max(0.1, …) : au-delà d'~1000 tranches heure/date (log couvrant
  // beaucoup de jours), la formule devient négative ou nulle — SVG rejette
  // width<0 (erreur console en boucle, une par barre, valeur identique).
  const bw = Math.max(0.1, Math.floor((VW - gap * (n - 1)) / n));

  let markup = '';
  let bestHour = '', bestCount = 0;
  keys.forEach((k, i) => {
    const count = buckets[k];
    const x = i * (bw + gap);
    const barH = Math.max(3, Math.round((count / maxVal) * (VH - 10)));
    const y = VH - barH;
    const isCurrent = (k === nowKey);
    const col = isCurrent ? '#ffffff'
              : count >= 20 ? 'var(--green)'
              : count >= 10 ? 'var(--yellow)'
              : count >=  5 ? '#FF8C00'
              : 'var(--accent2)';
    const hh = k.slice(-2); // "HH"
    markup += `<rect x="${x}" y="${y}" width="${bw}" height="${barH}" fill="${col}" rx="1" opacity="${isCurrent?1:.85}">`;
    markup += `<title>${hh}:00 UTC — ${count} QSO</title></rect>`;
    // Étiquette heure toutes les 3h ou si n≤12
    if(n <= 12 || parseInt(hh,10) % 3 === 0){
      markup += `<text x="${x+bw/2}" y="${VH+7}" text-anchor="middle" font-size="10" font-family="monospace" fill="var(--muted)">${hh}</text>`;
    }
    // Valeur sur barre haute
    if(count === maxVal || count >= 10){
      markup += `<text x="${x+bw/2}" y="${y-2}" text-anchor="middle" font-size="10" font-family="monospace" fill="${col}">${count}</text>`;
    }
    if(count > bestCount){ bestCount = count; bestHour = hh + ':00'; }
  });

  // Ligne objectif de taux (20 QSO/h)
  const TARGET_RATE = 20;
  if(maxVal > 0 && TARGET_RATE <= maxVal){
    const ty = Math.round(VH - (TARGET_RATE / maxVal) * (VH - 10));
    markup += `<line x1="0" y1="${ty}" x2="${VW}" y2="${ty}" stroke="rgba(255,214,10,.55)" stroke-width="1.5" stroke-dasharray="8,5"/>`;
    markup += `<text x="${VW-2}" y="${ty-2}" text-anchor="end" font-size="6.5" font-family="monospace" fill="rgba(255,214,10,.8)">${TARGET_RATE}/h</text>`;
  }
  svg.setAttribute('viewBox', `0 0 ${VW} ${VH + 10}`);
  svg.innerHTML = markup;
  if(peak) peak.textContent = `PEAK ${bestHour} UTC — ${bestCount} QSO/h`;
  bar.style.display = 'block';
}
