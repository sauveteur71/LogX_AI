// ─── RECHERCHE DE DOUBLONS DÉDIÉE (EV-7, docs/LogX_AI_PRD.md) ───────────────
// Extrait hors du monolithe logx_logbook.js (chantier EV-7, même logique que
// logx_filter_builder.js à côté). Distincte du surlignage en direct de
// renderLog() (dupCounts, resté dans logx_logbook.js, juste call+band —
// chemin critique, jamais touché ici) : ici l'opérateur choisit explicitement
// le critère (± jour, ± minute) et peut nettoyer le log en lot, pas
// seulement repérer visuellement.
let dupOptions = {sameDay:false, sameMinute:false};

function dupKeyOf(q){
  let k = (q.call||'').toUpperCase() + '|' + (q.band||'') + '|' + (q.mode||'').toUpperCase();
  if(dupOptions.sameDay) k += '|' + (q.date||'');
  // 'HH:MM' ou 'HH:MM:SS' selon la source (saisie manuelle vs import) — les 5
  // premiers caractères couvrent les deux formats sans dépendre de la longueur.
  if(dupOptions.sameMinute) k += '|' + String(q.time||'').slice(0,5);
  return k;
}

function findDuplicateGroups(){
  const map = new Map();
  qsoLog.forEach(q=>{
    const k = dupKeyOf(q);
    if(!map.has(k)) map.set(k, []);
    map.get(k).push(q);
  });
  // Le plus ANCIEN en tête de groupe : « garder le premier » doit garder le
  // QSO originel, pas un doublon arrivé après coup par resynchro réseau.
  return [...map.values()]
    .filter(g => g.length > 1)
    .map(g => g.slice().sort((a,b) => (a.date+a.time).localeCompare(b.date+b.time)))
    .sort((a,b) => b.length - a.length);
}

function openDupFinder(){
  document.getElementById('dupSameDay').checked = dupOptions.sameDay;
  document.getElementById('dupSameMinute').checked = dupOptions.sameMinute;
  renderDupResults();
  document.getElementById('dupOverlay').classList.add('show');
}

function closeDupFinder(){
  document.getElementById('dupOverlay').classList.remove('show');
}

function dupOptionsChanged(){
  dupOptions.sameDay = document.getElementById('dupSameDay').checked;
  dupOptions.sameMinute = document.getElementById('dupSameMinute').checked;
  renderDupResults();
}

function renderDupResults(){
  const wrap = document.getElementById('dupResults');
  if(!wrap) return;
  const groups = findDuplicateGroups();
  if(!groups.length){
    wrap.innerHTML = `<div style="color:var(--muted);text-align:center;padding:20px">${trT('Aucun doublon trouvé.')}</div>`;
  } else {
    wrap.innerHTML = groups.map(g => {
      const extraIds = JSON.stringify(g.slice(1).map(q=>q.id));
      const rows = g.map(q => `<div class="dup-row">
        <span>${escHtml(q.date)} ${escHtml(q.time)}</span>
        <span>${escHtml(q.call)}</span>
        <span>${BAND_LABELS[q.band]||escHtml(q.band)}</span>
        <span>${escHtml(q.mode)}</span>
        <span>${escHtml(q.rst_sent)}/${escHtml(q.rst_rcvd)}</span>
        <span class="dup-del" onclick="dupDeleteOne(${q.id})" title="Supprimer ce QSO">✕</span>
      </div>`).join('');
      return `<div class="dup-group">
        <div class="dup-group-hdr">
          <span>${escHtml(g[0].call)} · ${BAND_LABELS[g[0].band]||escHtml(g[0].band)} · ${escHtml(g[0].mode)} — ${g.length} occurrences</span>
          <button class="flt-add-cond" onclick="dupDeleteMany(${extraIds})">GARDER LE 1ᵉʳ, SUPPRIMER LE RESTE</button>
        </div>
        ${rows}
      </div>`;
    }).join('');
  }
  const totalEnTrop = groups.reduce((s,g) => s + g.length - 1, 0);
  document.getElementById('dupCount').textContent = groups.length
    ? trF('{g} groupe(s), {n} QSO en trop', {g: groups.length, n: totalEnTrop})
    : '';
}

async function dupDeleteOne(id){
  if(!(await _confirmDupBanner(trT('Supprimer ce QSO ?'), 'Supprimer', 'Annuler'))) return;
  await deleteQSOSilent(id);
  renderLog();
  updateStats();
  renderDupResults();
}

async function dupDeleteMany(ids){
  if(!ids.length) return;
  if(!(await _confirmDupBanner(trF('Supprimer {n} QSO en double (le plus ancien de chaque groupe est conservé) ?', {n: ids.length}), 'Supprimer', 'Annuler'))) return;
  for(const id of ids) await deleteQSOSilent(id);
  renderLog();
  updateStats();
  renderDupResults();
}

function dupDeleteAllExceptFirst(){
  const ids = findDuplicateGroups().flatMap(g => g.slice(1).map(q=>q.id));
  dupDeleteMany(ids);
}
