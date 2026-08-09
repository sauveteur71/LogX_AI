// EV-7 phase 2, 31e increment : BANDSCOPE + WATERFALL (visualisation de
// densite des spots sur la bande courante) -- extrait de logx_logbook.js
// (docs/LogX_AI_PRD.md). Charge en <script> classique dans
// logx_logbook.html, AVANT logx_logbook.js -- portee globale partagee
// (comme tous les fichiers EV-7).
//
// Contient : drawBandscope(), toggleWaterfall()/_wfShown/_wfLastBand,
// _cssVar(), drawWaterfallRow().
//
// Dependances croisees verifiees sures : refreshBandMap() appelle
// drawBandscope()/drawWaterfallRow() en fin de traitement --
// fonction-corps, jamais top-level, sans risque d'ordre. MAJ EV-7 33e
// increment : refreshBandMap() a ete deplacee du coeur vers
// logx_filtre_spots.js, qui charge APRES ce fichier dans
// logx_logbook.html -- direction inhabituelle deja rencontree pour les
// MACROS F1-F8 (32e increment) : sans risque tant que l'appel reste en
// corps de fonction (jamais au chargement du script). drawBandscope()/
// drawWaterfallRow() lisent en retour des constantes du coeur
// (_BM_PCOL, _BM_CSSVAR, escHtml, currentBand) -- toujours en
// fonction-corps (jamais au chargement du script), donc deja
// disponibles au moment ou elles sont reellement appelees (apres
// interaction/polling, jamais avant la fin du chargement de la page).
// bandmapClick() (coeur, definie dans logx_logbook.js) N'A PAS ete
// deplacee : elle gere le clic sur un spot (QSY radio), chemin
// different de la visualisation bandscope/waterfall. drawBandscope()
// genere elle-meme un onclick="bandmapClick(...)" (attribut HTML,
// jamais appele au chargement) -- deuxieme site de reference a
// bandmapClick(), en plus de celui de logx_filtre_spots.js.

// ─── BANDSCOPE : spectre d'activité de la bande (densité de spots) ────────────
// Un « scope » sans SDR : chaque spot devient une barre placée à sa fréquence,
// hauteur selon la priorité, vert = nouveau multiplicateur, ▼ = fréquence radio.
function drawBandscope(spots, rng, txMhz){
  const svg = document.getElementById('bandscope');
  if(!svg) return;
  if(!rng){ svg.innerHTML = ''; return; }
  const base = 62, x0 = 4, x1 = 176, span = (rng[1] - rng[0]) || 1;
  const xf = f => x0 + Math.max(0, Math.min(1, (f - rng[0]) / span)) * (x1 - x0);
  let g = `<line x1="${x0}" y1="${base}" x2="${x1}" y2="${base}" style="stroke:var(--border)" stroke-width="1"/>`;
  for(let i = 0; i <= 4; i++){
    const x = x0 + (x1 - x0) * i / 4;
    g += `<line x1="${x}" y1="${base}" x2="${x}" y2="${base+3}" style="stroke:var(--border)" stroke-width="0.5"/>`;
  }
  for(const s of (spots || [])){
    const f = parseFloat(s.freq);
    if(!isFinite(f)) continue;
    const x = xf(f);
    const h = s.new_mult ? 50 : Math.max(8, 46 - (s.priority || 3) * 7);
    const col = s.new_mult ? 'var(--green)' : (_BM_PCOL[s.priority] || 'var(--muted)');
    const op = s.already_done ? 0.35 : 1;
    const safeCall = String(s.call || '').replace(/[^A-Z0-9/]/gi, '');
    const safeMode = String(s.mode || '').replace(/[^A-Za-z0-9/-]/g, '');
    g += `<rect class="bs-bar" x="${(x-1).toFixed(1)}" y="${(base-h).toFixed(1)}" width="2" height="${h.toFixed(1)}"`
       + ` style="fill:${col}" opacity="${op}" onclick="bandmapClick('${safeCall}',${f},'${safeMode}')">`
       + `<title>${escHtml(s.call)} ${f.toFixed(3)}</title></rect>`;
  }
  if(txMhz && txMhz >= rng[0] && txMhz <= rng[1]){
    const x = xf(txMhz).toFixed(1);
    g += `<line x1="${x}" y1="8" x2="${x}" y2="${base}" style="stroke:var(--accent)" stroke-width="1.2"/>`
       + `<text x="${x}" y="7" style="fill:var(--accent)" font-size="6" text-anchor="middle">▼</text>`;
  }
  g += `<text x="${x0}" y="72" style="fill:var(--muted)" font-size="7">${rng[0]}</text>`
     + `<text x="${x1}" y="72" style="fill:var(--muted)" font-size="7" text-anchor="end">${rng[1]}</text>`;
  svg.innerHTML = g;
}

// ─── WATERFALL : mêmes spots que le bandscope, empilés dans le temps ─────────
// Contrairement au bandscope (redessiné en entier à chaque tick), le canvas
// est décalé d'une ligne vers le bas et une seule NOUVELLE ligne est peinte en
// haut (technique standard des waterfalls SDR) — l'historique visuel des
// derniers ticks (par défaut ~15 s/ligne, voir refreshBandMap) permet de voir
// QUAND la bande s'est ouverte, pas juste où. Masqué par défaut (toggleWaterfall)
// pour ne pas faire tourner de dessin canvas inutilement en arrière-plan.
let _wfShown = false;
// Dernière bande dessinée dans le canvas — sert à détecter un changement de
// bande pour vider l'historique (voir drawWaterfallRow). Sans ce suivi, le
// canvas n'est vidé QUE quand rng est falsy (bande hors table _BM_RANGE), ce
// qui n'arrive presque jamais : en pratique, changer de bande empilait les
// nouveaux spots par-dessus l'ancien historique au lieu de repartir à zéro.
let _wfLastBand = null;

function toggleWaterfall(){
  _wfShown = !_wfShown;
  const cv = document.getElementById('bandWaterfall');
  const sv = document.getElementById('bandscope');
  if(cv) cv.style.display = _wfShown ? 'block' : 'none';
  if(sv) sv.style.display = _wfShown ? 'none' : 'block';
  const btn = document.getElementById('waterfallToggleBtn');
  if(btn) btn.style.color = _wfShown ? 'var(--green)' : 'var(--accent2)';
}

function _cssVar(name){
  return (getComputedStyle(document.body).getPropertyValue(name) || '').trim() || '#8792B5';
}

function drawWaterfallRow(spots, rng){
  const canvas = document.getElementById('bandWaterfall');
  if(!canvas) return;
  // Changement de bande : purge l'historique même si le waterfall est
  // actuellement masqué, sinon l'ancien contenu resurgit tel quel au prochain
  // toggleWaterfall() (le canvas n'est jamais touché tant qu'il est caché).
  const bandChanged = currentBand !== _wfLastBand;
  _wfLastBand = currentBand;
  if(!_wfShown){
    if(bandChanged) canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
    return;   // caché : inutile de dessiner en arrière-plan
  }
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  if(bandChanged) ctx.clearRect(0, 0, w, h);   // nouvelle bande : pas l'historique de l'ancienne
  if(!rng){ ctx.clearRect(0, 0, w, h); return; }
  // Défile le contenu existant d'une ligne vers le bas en recopiant le canvas
  // sur lui-même décalé — PAS un redraw complet (on perdrait l'historique).
  ctx.drawImage(canvas, 0, 0, w, h - 1, 0, 1, w, h - 1);
  ctx.clearRect(0, 0, w, 1);   // nouvelle ligne transparente = fond du thème visible
  const x0 = 4, x1 = w - 4, span = (rng[1] - rng[0]) || 1;
  for(const s of spots){
    const f = parseFloat(s.freq);
    if(!isFinite(f)) continue;
    const x = Math.round(x0 + Math.max(0, Math.min(1, (f - rng[0]) / span)) * (x1 - x0));
    ctx.fillStyle = s.new_mult ? _cssVar('--green') : _cssVar(_BM_CSSVAR[s.priority] || '--muted');
    ctx.fillRect(Math.max(0, x - 1), 0, 3, 1);
  }
}
