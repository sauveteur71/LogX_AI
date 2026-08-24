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
