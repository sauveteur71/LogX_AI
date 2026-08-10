// ─── CARTE QSL — designer imprimable minimal (export PNG/JPG) ────────────────
// Chantier concurrentiel (Wavelog/Log4OM/GridTracker2 ont tous un outil
// équivalent, LogX AI n'en avait aucun). Rendu 100% CLIENT-SIDE (canvas 2D),
// aucun nouvel endpoint serveur : les données existent déjà côté client
// (qsoLog, myCall/myLocator -- voir logx_logbook.js). Ouvert depuis le menu
// ☰ DÉBUT/FIN de LOGBOOK (itemsMenuLogbook(), groupe « APRÈS LA SESSION »).
//
// Même patron que showAwards() (logx_awards.js) : overlay
// .shortcuts-overlay/.shortcuts-box déjà stylé globalement (voir
// logx_logbook.html), <script> classique, portée globale partagée.
//
// Dépend de globals restés dans logx_logbook.js (sens autorisé, fonctions
// seulement, cf. en-têtes des fichiers EV-7 déjà extraits) : qsoLog, myCall,
// myLocator, escHtml, notify. fmtDate (logx_callbook.js, format
// YYYYMMDD -> DD/MM/YYYY) est réutilisée telle quelle -- ordre de <script>
// entre les fichiers extraits sans importance (fmtDate n'est appelée qu'à
// l'intérieur de corps de fonction ici).
//
// Direction design (CLAUDE.md, palette graphite&cuivre) : SEUL le cadre de
// l'overlay suit le thème sombre habituel de l'app. Le <canvas> lui-même
// imite une VRAIE carte QSL imprimée sur papier -- fond crème #F7F3EA, filet
// cuivre #8B4F1F FIXE (teinte JOUR de --accent, volontairement indépendante
// du thème d'interface actif : la carte est un objet imprimable, pas un écran
// radar HUD).

let _qslBgImage = null;   // Image chargée par FileReader (upload optionnel), ou null

// ─── Ouverture du panneau ─────────────────────────────────────────────────
function showQslCardDesigner(){
  const ov = document.getElementById('qslCardOverlay');
  if(!ov) return;
  ov.classList.add('show');
  // Repartir d'un filtre vide à chaque ouverture -- sinon le champ de
  // recherche garde le texte d'une session précédente alors que la liste,
  // elle, est reconstruite complète : désynchronisation visuelle.
  const searchInput = document.getElementById('qslQsoSearch');
  if(searchInput) searchInput.value = '';
  _qslPopulateQsoSelect();
  _qslRender();
}

// Remplit le <select> à partir de qsoLog -- le plus récent d'abord (même
// motif que qsoLog.slice().reverse() déjà utilisé ailleurs dans
// logx_logbook.js). La sélection est reposée EXPLICITEMENT (pas de recours au
// comportement implicite du navigateur qui sélectionne le premier <option> à
// la reconstruction de innerHTML) : plus robuste, et testable hors navigateur.
function _qslPopulateQsoSelect(filtre){
  const sel = document.getElementById('qslQsoSelect');
  if(!sel) return;
  const f = String(filtre || '').trim().toUpperCase();
  const liste = qsoLog.slice().reverse()
    .filter(q => !f || String(q.call || '').toUpperCase().includes(f));
  const prevValue = String(sel.value || '');
  sel.innerHTML = liste.length
    ? liste.map(q => `<option value="${escHtml(q.id)}">${escHtml(q.call)} · ${escHtml(q.band)} MHz · ${escHtml(q.mode)} · ${escHtml(fmtDate(q.date))} ${escHtml(q.time || '')}</option>`).join('')
    : `<option value="">— aucun QSO —</option>`;
  const gardeSelection = liste.some(q => String(q.id) === prevValue);
  sel.value = gardeSelection ? prevValue : (liste.length ? String(liste[0].id) : '');
}

function _qslFiltrerListeQso(){
  const q = document.getElementById('qslQsoSearch');
  _qslPopulateQsoSelect(q ? q.value : '');
  _qslRender();
}

function _qslSelectedQso(){
  const sel = document.getElementById('qslQsoSelect');
  if(!sel || !sel.value) return null;
  return qsoLog.find(q => String(q.id) === String(sel.value)) || null;
}

// ─── Image de fond (optionnelle) ──────────────────────────────────────────
function _qslOnBgFileChange(evt){
  const file = evt && evt.target && evt.target.files && evt.target.files[0];
  if(!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    const img = new Image();
    img.onload = () => {
      _qslBgImage = img;
      const clearBtn = document.getElementById('qslBgClearBtn');
      if(clearBtn) clearBtn.style.display = '';
      _qslRender();
    };
    img.onerror = () => notify('❌ Image illisible.');
    img.src = reader.result;
  };
  reader.onerror = () => notify('❌ Lecture du fichier image impossible.');
  reader.readAsDataURL(file);
}

function _qslClearBgImage(){
  _qslBgImage = null;
  const input = document.getElementById('qslBgFile');
  if(input) input.value = '';
  const clearBtn = document.getElementById('qslBgClearBtn');
  if(clearBtn) clearBtn.style.display = 'none';
  _qslRender();
}

// ─── Rendu canvas ──────────────────────────────────────────────────────────
// La résolution du raster est posée ICI en JS (pas seulement via les
// attributs width/height du <canvas> dans le HTML) : format carte postale
// fixe, indépendant du CSS d'affichage (#qslCanvas le redimensionne à
// l'écran sans jamais toucher à la résolution réelle du raster).
function _qslRender(){
  const canvas = document.getElementById('qslCanvas');
  if(!canvas) return;
  canvas.width = 1500;
  canvas.height = 1000;
  const ctx = canvas.getContext('2d');
  if(!ctx) return;
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const q = _qslSelectedQso();
  if(!q){
    _qslDrawEmptyState(ctx, w, h);
    return;
  }

  const tplSel = document.getElementById('qslTemplateSelect');
  const template = tplSel ? tplSel.value : 'classique';
  const msgInput = document.getElementById('qslMessageInput');
  const rawMsg = msgInput ? msgInput.value : '';
  const data = _qslBuildCardData(q, rawMsg);
  if(template === 'epure') _qslDrawEpure(ctx, w, h, data);
  else _qslDrawClassique(ctx, w, h, data);
}

// Construit les données de la carte à partir du QSO sélectionné -- fonction
// PURE (aucun accès DOM/canvas), extraite de _qslRender() pour être testable
// indépendamment du rendu (le stub <canvas> des tests JS ne fournit pas de
// vrai contexte 2D).
function _qslBuildCardData(q, rawMsg){
  // Indicatif JAMAIS "undefined" à l'écran/à l'impression : repli explicite
  // si la station n'est pas encore configurée. PRIORITÉ à q.my_call (celui
  // RÉELLEMENT utilisé pendant CE QSO, ex. F4GLD/P) sur l'indicatif courant
  // de la session -- qsoLog est filtré par PORTÉE (concours+année), pas par
  // indicatif : un opérateur portable qui change d'identité dans la même
  // journée (nouveau SETUP) verrait sinon une carte QSL avec le MAUVAIS
  // indicatif pour un vieux QSO. Même repli déjà en place pour myLocator
  // juste en dessous.
  const call = String(q.my_call || myCall || '').toUpperCase() || '(indicatif non configuré)';
  return {
    myCall: call,
    myLocator: (q.my_locator || myLocator || '').toUpperCase(),
    call: String(q.call || '').toUpperCase(),
    band: q.band || '',
    mode: q.mode || '',
    date: fmtDate(q.date),
    time: q.time || '',
    rstSent: q.rst_sent || '',
    rstRcvd: q.rst_rcvd || '',
    locator: (q.locator || '').toUpperCase(),
    message: String(rawMsg || '').split('{MYCALL}').join(call),
  };
}

function _qslDrawEmptyState(ctx, w, h){
  ctx.fillStyle = '#F7F3EA';
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = '#8B4F1F';
  ctx.lineWidth = 3;
  ctx.strokeRect(20, 20, w - 40, h - 40);
  ctx.fillStyle = '#5A5245';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';
  ctx.font = '600 34px "Fraunces", serif';
  ctx.fillText('Aucun QSO enregistré', w / 2, h / 2 - 20);
  ctx.font = '18px "Share Tech Mono", monospace';
  ctx.fillText('Logge un QSO pour générer une carte QSL.', w / 2, h / 2 + 24);
}

// Image de fond en mode « cover » (remplit tout le cadre, recadrée si besoin),
// puis voile crème translucide par-dessus pour garder le texte lisible quelle
// que soit la photo choisie -- l'état par défaut (sans image) doit rester
// visuellement fini, ce voile est donc calculé pour ne rien casser si
// _qslBgImage est null (la fonction ne fait alors rien).
function _qslDrawBgImage(ctx, w, h, overlayAlpha){
  if(!_qslBgImage) return;
  const img = _qslBgImage;
  const iw = img.width || img.naturalWidth || 0;
  const ih = img.height || img.naturalHeight || 0;
  if(!iw || !ih) return;
  const scale = Math.max(w / iw, h / ih);
  const dw = iw * scale, dh = ih * scale;
  ctx.drawImage(img, (w - dw) / 2, (h - dh) / 2, dw, dh);
  ctx.fillStyle = `rgba(247,243,234,${overlayAlpha})`;
  ctx.fillRect(0, 0, w, h);
}

// Retour à la ligne manuel (canvas ne le fait pas nativement) -- centré ou
// aligné à gauche selon align.
function _qslWrapText(ctx, text, x, y, maxWidth, lineHeight, align){
  const mots = String(text || '').split(/\s+/).filter(Boolean);
  ctx.textAlign = align || 'center';
  let ligne = '', ly = y;
  mots.forEach(mot => {
    const essai = ligne ? ligne + ' ' + mot : mot;
    if(ligne && ctx.measureText(essai).width > maxWidth){
      ctx.fillText(ligne, x, ly);
      ligne = mot;
      ly += lineHeight;
    }else{
      ligne = essai;
    }
  });
  if(ligne) ctx.fillText(ligne, x, ly);
}

// ─── Gabarit 1 : CLASSIQUE — cartouche complet ────────────────────────────
function _qslDrawClassique(ctx, w, h, d){
  const ink = '#3A3226', muted = '#8A7F68', copper = '#8B4F1F';
  ctx.fillStyle = '#F7F3EA';
  ctx.fillRect(0, 0, w, h);
  _qslDrawBgImage(ctx, w, h, 0.86);

  // Double cadre
  ctx.strokeStyle = copper;
  ctx.lineWidth = 4;
  ctx.strokeRect(22, 22, w - 44, h - 44);
  ctx.lineWidth = 1.5;
  ctx.strokeRect(34, 34, w - 68, h - 68);

  ctx.textAlign = 'center';
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = copper;
  ctx.font = '700 20px "Share Tech Mono", monospace';
  ctx.fillText('C A R T E   Q S L', w / 2, 78);

  ctx.fillStyle = ink;
  ctx.font = '900 76px "Fraunces", serif';
  ctx.fillText(d.myCall, w / 2, 160);

  if(d.myLocator){
    ctx.fillStyle = muted;
    ctx.font = '20px "Share Tech Mono", monospace';
    ctx.fillText(d.myLocator, w / 2, 195);
  }

  ctx.strokeStyle = copper;
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(120, 222); ctx.lineTo(w - 120, 222); ctx.stroke();

  ctx.fillStyle = ink;
  ctx.font = '22px "Exo 2", sans-serif';
  ctx.fillText('Cette carte confirme le contact radio bilatéral avec', w / 2, 266);

  ctx.fillStyle = copper;
  ctx.font = '900 62px "Fraunces", serif';
  ctx.fillText(d.call, w / 2, 336);

  // Tableau des détails du QSO — grille 4 colonnes
  const items = [
    ['DATE (UTC)', d.date || '—'], ['HEURE (UTC)', d.time || '—'],
    ['BANDE', d.band ? d.band + ' MHz' : '—'], ['MODE', d.mode || '—'],
    ['RST ENVOYÉ', d.rstSent || '—'], ['RST REÇU', d.rstRcvd || '—'],
    ['LOCATOR', d.locator || '—'],
  ];
  const cols = 4, startX = 120, tableW = w - 240, cellW = tableW / cols, startY = 410, cellH = 100;
  ctx.textAlign = 'center';
  items.forEach((it, i) => {
    const col = i % cols, row = Math.floor(i / cols);
    const cx = startX + col * cellW + cellW / 2;
    const cy = startY + row * cellH;
    ctx.fillStyle = muted;
    ctx.font = '600 15px "Share Tech Mono", monospace';
    ctx.fillText(it[0], cx, cy);
    ctx.fillStyle = ink;
    ctx.font = '700 30px "Share Tech Mono", monospace';
    ctx.fillText(it[1], cx, cy + 34);
  });

  ctx.strokeStyle = copper;
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(120, 690); ctx.lineTo(w - 120, 690); ctx.stroke();

  ctx.fillStyle = ink;
  ctx.font = 'italic 24px "Exo 2", sans-serif';
  _qslWrapText(ctx, d.message, w / 2, 740, w - 300, 32, 'center');

  ctx.fillStyle = muted;
  ctx.font = '14px "Share Tech Mono", monospace';
  ctx.textAlign = 'center';
  ctx.fillText('LogX AI — carte QSL générée automatiquement', w / 2, h - 38);
}

// ─── Gabarit 2 : ÉPURÉ — minimaliste ───────────────────────────────────────
function _qslDrawEpure(ctx, w, h, d){
  const ink = '#3A3226', muted = '#8A7F68', copper = '#8B4F1F';
  ctx.fillStyle = '#F7F3EA';
  ctx.fillRect(0, 0, w, h);
  _qslDrawBgImage(ctx, w, h, 0.9);

  ctx.strokeStyle = copper;
  ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(60, 60); ctx.lineTo(w - 60, 60); ctx.stroke();

  ctx.textAlign = 'left';
  ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = copper;
  ctx.font = '600 16px "Share Tech Mono", monospace';
  ctx.fillText(d.myCall + (d.myLocator ? ' · ' + d.myLocator : ''), 60, 100);

  ctx.fillStyle = ink;
  ctx.font = '900 54px "Fraunces", serif';
  ctx.fillText('QSL', 60, 190);

  ctx.font = '20px "Exo 2", sans-serif';
  ctx.fillStyle = ink;
  ctx.fillText('Confirmation de contact bilatéral avec', 60, 236);

  ctx.fillStyle = copper;
  ctx.font = '900 70px "Fraunces", serif';
  ctx.fillText(d.call, 60, 316);

  const rows = [
    ['Date (UTC)', d.date || '—'], ['Heure (UTC)', d.time || '—'],
    ['Bande', d.band ? d.band + ' MHz' : '—'], ['Mode', d.mode || '—'],
    ['RST envoyé / reçu', (d.rstSent || '—') + ' / ' + (d.rstRcvd || '—')],
    ['Locator', d.locator || '—'],
  ];
  let ly = 390;
  rows.forEach(([label, val]) => {
    ctx.textAlign = 'left';
    ctx.fillStyle = muted;
    ctx.font = '15px "Share Tech Mono", monospace';
    ctx.fillText(label.toUpperCase(), 60, ly);
    ctx.fillStyle = ink;
    ctx.font = '700 26px "Share Tech Mono", monospace';
    ctx.fillText(val, 320, ly);
    ly += 46;
  });

  ctx.strokeStyle = copper;
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(60, ly + 16); ctx.lineTo(w - 60, ly + 16); ctx.stroke();

  ctx.fillStyle = ink;
  ctx.font = '22px "Exo 2", sans-serif';
  _qslWrapText(ctx, d.message, 60, ly + 60, w - 120, 30, 'left');

  ctx.fillStyle = muted;
  ctx.font = '13px "Share Tech Mono", monospace';
  ctx.textAlign = 'right';
  ctx.fillText('LogX AI', w - 60, h - 34);
}

// ─── Téléchargement PNG / JPG ──────────────────────────────────────────────
// Jamais de '/' brut dans le nom de fichier : un indicatif portable
// (F4GLD/P) casserait sinon le nom de fichier généré.
function _qslSanitizeFilename(s){
  return String(s || 'QSO').replace(/[\/\\?%*:|"<>]/g, '_').trim() || 'QSO';
}

// Pattern <a download> temporaire créé puis retiré du DOM, déjà utilisé
// ailleurs dans le projet (voir _recSaveClip(), logx_logbook.js).
function downloadQslCard(format){
  const canvas = document.getElementById('qslCanvas');
  if(!canvas) return;
  const q = _qslSelectedQso();
  if(!q){ notify('⚠️ Sélectionne un QSO avant de télécharger.'); return; }
  const isJpg = format === 'jpg';
  const mime = isJpg ? 'image/jpeg' : 'image/png';
  const ext = isJpg ? 'jpg' : 'png';
  const dataUrl = isJpg ? canvas.toDataURL(mime, 0.92) : canvas.toDataURL(mime);
  const callPart = _qslSanitizeFilename(String(q.my_call || myCall || 'QSL').toUpperCase());
  const corrPart = _qslSanitizeFilename(String(q.call || 'QSO').toUpperCase());
  const name = `QSL_${callPart}_${corrPart}_${q.date || ''}.${ext}`;
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  notify(trF('🖼️ Carte QSL téléchargée : {name}', {name}));
}
