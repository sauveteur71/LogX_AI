// Onglets de la fenêtre de saisie (sous-chantier A, lot 1/6).
// Le chemin critique (indicatif, RST, N°, bande/mode, enregistrer) reste
// HORS onglet, dans le bandeau permanent -- voir logx_logbook.html. Ce
// fichier ne touche qu'aux champs SECONDAIRES existants (locator, source,
// commentaire...) repositionnés dans .entry-tabpane. Aucun champ nouveau.
function entryTabSelect(name){
  var panes = document.querySelectorAll('.entry-tabpane');
  for (var i=0;i<panes.length;i++) panes[i].style.display = (panes[i].getAttribute('data-pane')===name)?'':'none';
  var tabs = document.querySelectorAll('.entry-tab');
  for (var j=0;j<tabs.length;j++) tabs[j].classList.toggle('active', tabs[j].getAttribute('data-tab')===name);
  try { localStorage.setItem('logx_entry_tab', name); } catch(e){}
}
function entryTabsInit(){
  var tabs = document.querySelectorAll('.entry-tab');
  for (var i=0;i<tabs.length;i++){
    tabs[i].addEventListener('click', function(){ entryTabSelect(this.getAttribute('data-tab')); });
  }
  var last = 'qso';
  try { last = localStorage.getItem('logx_entry_tab') || 'qso'; } catch(e){}
  entryTabSelect(last);
}
// Auto-init à l'ouverture de la page -- même motif que les autres modules
// extraits chargés en <script> classique (voir logx_theme_shortcuts.js) :
// pas de dépendance sur le DOMContentLoaded de logx_logbook.js (fichier hors
// périmètre du lot 1), ce module se pose lui-même dès que le DOM est prêt.
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', entryTabsInit);
else entryTabsInit();

// ── Tags multi-activité (lot 4, sous-chantier A) ────────────────────────────
// activity_tags = liste cumulée (FT8 + SOTA + QRP + DX…), ORTHOGONALE à
// `contest`. Beaucoup sont AUTO-dérivés du QSO ; l'opérateur ajoute des tags
// MANUELS que le recalcul auto ne doit jamais effacer (mergeTags préserve).
function deriveActivityTags(q){
  var t = [];
  if(q.mode) t.push(String(q.mode).toUpperCase());
  // 5 W : seuil QRP usuel (SOURCE : skill radioamateur / règlements diplômes QRP).
  if(q.tx_pwr != null && Number(q.tx_pwr) > 0 && Number(q.tx_pwr) <= 5) t.push('QRP');
  (q.my_refs || []).concat(q.refs || []).forEach(function(r){ if(r && r.program) t.push(String(r.program).toUpperCase()); });
  if(q.operating_location && q.operating_location !== 'HOME') t.push(q.operating_location);
  if(q.prop_mode) t.push(String(q.prop_mode).toUpperCase());
  if(q.sat_name) t.push('SAT');
  // DX (seuil de distance) : VALEUR À SOURCER -> ajouté quand le seuil DX sera
  // arbitré (heuristique existante 3000/8000 km). Pas dérivé pour l'instant.
  return t.filter(function(v, i, a){ return a.indexOf(v) === i; });
}
function mergeTags(auto, manuels){
  var out = (manuels || []).slice();
  (auto || []).forEach(function(x){ if(out.indexOf(x) === -1) out.push(x); });
  return out;
}
var _manualTags = [];
function getManualTags(){ return _manualTags.slice(); }
function resetManualTags(){ _manualTags = []; renderActivityTags(); }
function addManualTag(name){
  name = String(name || '').trim().toUpperCase();
  if(name && _manualTags.indexOf(name) === -1){ _manualTags.push(name); renderActivityTags(); }
}
function removeManualTag(name){
  var i = _manualTags.indexOf(name);
  if(i !== -1){ _manualTags.splice(i, 1); renderActivityTags(); }
}
// Instantané des champs du formulaire qui DÉRIVENT des tags auto (pour l'aperçu
// live). Lit le mode courant, la puissance, le lieu, la propagation et les
// références — exactement ce que deriveActivityTags() consomme.
function _formQsoSnapshot(){
  var g = function(id){ var e = document.getElementById(id); return e ? e.value : ''; };
  var q = {};
  if(typeof currentMode !== 'undefined' && currentMode) q.mode = currentMode;
  var p = g('inputTxPwr'); if(p) q.tx_pwr = Number(p);
  var ol = g('inputOperatingLocation'); if(ol) q.operating_location = ol;
  var pm = g('inputPropMode'); if(pm) q.prop_mode = pm;
  if(typeof collectRefs === 'function'){ q.my_refs = collectRefs('myRefsList'); q.refs = collectRefs('refsList'); }
  return q;
}
function renderActivityTags(){
  var box = document.getElementById('activityTags');
  if(!box) return;
  // escHtml() est la fonction d'échappement globale de la page (logx_logbook.js) ;
  // repli inerte si elle n'est pas encore chargée.
  var esc = (typeof escHtml === 'function') ? escHtml : function(s){ return String(s); };
  // Tags AUTO dérivés du formulaire EN COURS (aperçu live), hors ceux déjà manuels.
  var auto = deriveActivityTags(_formQsoSnapshot()).filter(function(t){ return _manualTags.indexOf(t) === -1; });
  var autoChips = auto.map(function(t){ return '<span class="chip auto">' + esc(t) + '</span>'; }).join('');
  var manChips = _manualTags.map(function(t){
    return '<span class="chip man" data-tag="'+esc(t)+'">'+esc(t)+' <span class="x">✕</span></span>'; }).join('');
  box.innerHTML = '<span class="field-label" style="margin:0 4px 0 0">TAGS</span>' + autoChips + manChips +
    '<span class="chip add" id="addTagChip">+ tag</span>';
  var add = document.getElementById('addTagChip');
  if(add) add.addEventListener('click', function(){
    var v = window.prompt('Ajouter un tag (ex. DX, EXPERIMENTAL, EMCOMM) :');
    if(v) addManualTag(v);
  });
  box.querySelectorAll('.chip.man .x').forEach(function(x){
    x.addEventListener('click', function(){ removeManualTag(x.parentNode.getAttribute('data-tag')); });
  });
}
// Re-rendu de l'aperçu quand un champ qui dérive les tags change.
function _bindTagPreview(){
  ['inputTxPwr','inputOperatingLocation','inputPropMode'].forEach(function(id){
    var e = document.getElementById(id);
    if(e) e.addEventListener('change', renderActivityTags);
  });
  renderActivityTags();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _bindTagPreview);
else _bindTagPreview();
