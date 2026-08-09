// ─── EV-7 : SOAPBOX PAR BANDE (extrait de logx_logbook.js) ────────────────
// SOAPBOX_BANDS (bandes THF concernées), toggleSoapbox() (repli/dépli du
// panneau), saveSoapbox()/loadSoapbox() (persistance localStorage),
// getSoapbox(band) (lecture pour l'export EDI). Chargé en <script>
// classique AVANT logx_logbook.js dans logx_logbook.html -- même portée
// globale partagée.
//
// Grep exhaustif fait AVANT extraction (1er candidat MOYEN du 3e
// inventaire, inventaire-ev7-3e-2026-08-09.md) : AUCUN appel top-level
// direct -- `loadSoapbox()` est bien appelée dans le corps d'un callback
// `window.addEventListener('DOMContentLoaded', () => {...})` du cœur (la
// SEULE registration est top-level, pas l'appel lui-même, qui n'a lieu
// qu'une fois tous les <script> exécutés -- motif déjà sûr, identique au
// correctif adaptivePoll de logx_hardware_cat.js).
//
// Dépendance croisée EN CORPS DE FONCTION (sûre, optionnel->optionnel) :
// logx_export_edi.js appelle getSoapbox(band) dans exportEDI() (remarques
// EDI par bande) -- les deux fichiers chargent avant logx_logbook.js,
// aucune contrainte d'ordre entre eux.

// ─── SOAPBOX PAR BANDE ───────────────────────────────────────────────────────
const SOAPBOX_BANDS = ['144','432','1296'];
function toggleSoapbox(){
  const title  = document.getElementById('soapboxToggle');
  const fields = document.getElementById('soapboxFields');
  if(!title || !fields) return;
  const collapsed = title.classList.toggle('collapsed');
  fields.classList.toggle('hidden', collapsed);
}
function saveSoapbox(){
  const data = {};
  SOAPBOX_BANDS.forEach(b => {
    const el = document.getElementById(`soap_${b}`);
    if(el) data[b] = el.value;
  });
  localStorage.setItem('logx_soapbox', JSON.stringify(data));
}
function loadSoapbox(){
  try{
    const data = JSON.parse(localStorage.getItem('logx_soapbox')||'{}');
    SOAPBOX_BANDS.forEach(b => {
      const el = document.getElementById(`soap_${b}`);
      if(el && data[b]) el.value = data[b];
    });
  }catch(e){}
}
function getSoapbox(band){
  try{
    const data = JSON.parse(localStorage.getItem('logx_soapbox')||'{}');
    return (data[band]||'').trim();
  }catch(e){ return ''; }
}
