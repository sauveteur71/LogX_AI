// ─── CONSTRUCTEUR DE FILTRE AVANCÉ (EV-7, docs/LogX_AI_PRD.md) ──────────────
// Deuxième incrément du refactor EV-7 après le pilote logx_cw_panel.js : pas
// de duplication à éliminer ici (contrairement au décodeur CW radio1/2),
// juste une fonctionnalité auto-contenue extraite hors du monolithe
// logx_logbook.js (9193 lignes avant ce chantier) vers son propre fichier —
// "logique métier mêlée à la présentation" au sens littéral du PRD.
//
// Ce fichier ne contient QUE l'UI du popup (rendu des groupes/conditions,
// préréglages) — le moteur de correspondance (FILTER_FIELDS/FILTER_OPS/
// matchesAdvancedFilter) est resté dans logx_logbook.js : renderLog()
// (chemin critique, jamais déplacé) en dépend directement, donc le faire
// dépendre en sens inverse d'un fichier "fonctionnalité optionnelle" aurait
// été une dépendance à l'envers (trouvé en revue adversariale). `fltBuilder`
// (l'état d'ÉDITION en cours du popup) et `advancedFilter` (le filtre
// RÉELLEMENT appliqué au tableau, logx_logbook.js) restent deux variables
// distinctes pour que l'aperçu du nombre de résultats et l'export
// "résultat" reflètent ce qu'on est en train de composer, sans affecter le
// tableau principal tant qu'on n'a pas cliqué APPLIQUER.

// État du CONSTRUCTEUR (édition en cours) — distinct de `advancedFilter`
// (le filtre RÉELLEMENT appliqué au tableau, logx_logbook.js) pour que
// l'aperçu du nombre de résultats et l'export "résultat" reflètent ce qu'on
// est en train de composer, sans affecter le tableau principal tant qu'on
// n'a pas cliqué APPLIQUER.
let fltBuilder = {groups: [[]]};

function fltCurrentMatches(){
  return qsoLog.filter(q => matchesAdvancedFilter(q, fltBuilder));
}

function openFilterBuilder(){
  if(advancedFilter) fltBuilder = JSON.parse(JSON.stringify(advancedFilter));
  if(!fltBuilder.groups || !fltBuilder.groups.length) fltBuilder = {groups:[[]]};
  fltRenderGroups();
  fltRenderPresets();
  document.getElementById('filterOverlay').classList.add('show');
}

function closeFilterBuilder(){
  document.getElementById('filterOverlay').classList.remove('show');
}

function fltAddGroup(){
  fltBuilder.groups.push([]);
  fltRenderGroups();
}

function fltAddCond(gi){
  fltBuilder.groups[gi].push({field:'call', op:'contains', value:''});
  fltRenderGroups();
}

function fltRemoveCond(gi, ci){
  fltBuilder.groups[gi].splice(ci, 1);
  if(!fltBuilder.groups[gi].length && fltBuilder.groups.length > 1) fltBuilder.groups.splice(gi, 1);
  fltRenderGroups();
}

function fltUpdateCond(gi, ci, key, value){
  const cond = fltBuilder.groups[gi][ci];
  cond[key] = value;
  if(key === 'field'){
    // Changer de champ peut changer de type (texte/nombre/booléen) — l'opérateur
    // choisi pour l'ancien type n'a pas forcément de sens pour le nouveau.
    cond.op = FILTER_OPS[fltFieldDef(value).type][0][0];
  }
  fltRenderGroups();
}

function fltRenderGroups(){
  const wrap = document.getElementById('fltGroups');
  if(!wrap) return;
  const esc = s => String(s==null?'':s).replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let h = '';
  fltBuilder.groups.forEach((group, gi) => {
    if(gi) h += '<div class="flt-or-sep">— OU —</div>';
    h += `<div class="flt-group">
      <div class="flt-group-hdr"><span class="flt-group-lbl">GROUPE ${gi+1} (ET)</span></div>`;
    group.forEach((cond, ci) => {
      const def = fltFieldDef(cond.field);
      const fieldOpts = FILTER_FIELDS.map(f =>
        `<option value="${f.key}"${f.key===cond.field?' selected':''}>${esc(f.label)}</option>`).join('');
      const opOpts = FILTER_OPS[def.type].map(([k,l]) =>
        `<option value="${k}"${k===cond.op?' selected':''}>${esc(l)}</option>`).join('');
      const valueInput = def.type === 'bool'
        ? '<input type="text" value="—" disabled>'
        : `<input type="text" value="${esc(cond.value)}" oninput="fltUpdateCond(${gi},${ci},'value',this.value)">`;
      h += `<div class="flt-row">
        <select onchange="fltUpdateCond(${gi},${ci},'field',this.value)">${fieldOpts}</select>
        <select onchange="fltUpdateCond(${gi},${ci},'op',this.value)">${opOpts}</select>
        ${valueInput}
        <span class="flt-remove" onclick="fltRemoveCond(${gi},${ci})" title="Retirer">✕</span>
      </div>`;
    });
    h += `<button class="flt-add-cond" onclick="fltAddCond(${gi})">+ CONDITION</button></div>`;
  });
  wrap.innerHTML = h;
  const cnt = document.getElementById('fltCount');
  if(cnt) cnt.textContent = `${fltCurrentMatches().length} QSO correspondent`;
}

function fltApply(){
  advancedFilter = JSON.parse(JSON.stringify(fltBuilder));
  closeFilterBuilder();
  renderLog();
}

function fltReset(){
  advancedFilter = null;
  fltBuilder = {groups:[[]]};
  fltRenderGroups();
  renderLog();
}

function fltExportFiltered(){
  const qsos = fltCurrentMatches().filter(isValidQSO);
  if(!qsos.length){ notify(trF('Aucun QSO ne correspond au filtre courant.')); return; }
  downloadAdifBlob(buildAdifText(qsos), 'filtre');
}

// ── Préréglages : par POSTE (localStorage), pas synchronisés réseau — un
// filtre est une préférence d'analyse individuelle, pas un réglage station
// partagé comme les règles d'alerte (voir logx_configuration.html:alertRules).
const FLT_PRESETS_KEY = 'rc_filter_presets';
function fltLoadPresets(){
  try{ return JSON.parse(localStorage.getItem(FLT_PRESETS_KEY) || '[]'); }
  catch(e){ return []; }
}
function fltSavePresets(list){
  localStorage.setItem(FLT_PRESETS_KEY, JSON.stringify(list));
}

function fltSavePreset(){
  const input = document.getElementById('fltPresetName');
  const name = (input.value || '').trim();
  if(!name) return;
  const list = fltLoadPresets();
  const preset = {id:'p'+Date.now(), name, tree: JSON.parse(JSON.stringify(fltBuilder))};
  fltSavePresets(list.filter(p=>p.name!==name).concat([preset]));
  input.value = '';
  fltRenderPresets();
}

function fltLoadPreset(id){
  const p = fltLoadPresets().find(p=>p.id===id);
  if(!p) return;
  fltBuilder = JSON.parse(JSON.stringify(p.tree));
  fltRenderGroups();
}

function fltDeletePreset(id){
  fltSavePresets(fltLoadPresets().filter(p=>p.id!==id));
  fltRenderPresets();
}

function fltRenderPresets(){
  const wrap = document.getElementById('fltPresetList');
  if(!wrap) return;
  const esc = s => String(s==null?'':s).replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  wrap.innerHTML = fltLoadPresets().map(p =>
    `<span class="flt-preset-chip"><span onclick="fltLoadPreset('${p.id}')">${esc(p.name)}</span>` +
    `<span class="flt-preset-del" onclick="fltDeletePreset('${p.id}')" title="Supprimer">✕</span></span>`
  ).join('') || '<span style="color:var(--muted);font-size:12px">Aucun préréglage enregistré</span>';
}
