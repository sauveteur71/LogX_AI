// ─── RETOUR AU LOGBOOK pour les pages « fenêtre détachée » ───────────────────
// FT8, RTTY et SSTV n'ont pas de barre de navigation : elles sont prévues pour
// s'ouvrir en fenêtre détachée depuis la page Numérique (ouvrirFenetreDetachee,
// noms rc_ft8 / rc_rtty / rc_sstv). Ouvertes en plein onglet (favori, lien,
// capture F4GLD du 28/10/2026), il n'y avait AUCUN moyen de revenir au carnet
// (audit 25/11/2026). Ce lien n'apparaît que dans ce cas-là.
(function(){
  'use strict';
  function estDetachee(){
    try{ if(window.opener && !window.opener.closed) return true; }catch(e){ return true; }
    return /^rc_/.test(window.name || '');
  }
  function poser(){
    if(estDetachee()) return;
    var hote = document.querySelector('header .logo-wrap');
    if(!hote || document.getElementById('retourLogbook')) return;
    var a = document.createElement('a');
    a.id = 'retourLogbook';
    a.href = '/logx_logbook.html';
    a.textContent = '← LOGBOOK';
    a.title = 'Revenir au carnet';
    a.style.cssText = 'margin-left:14px;font-family:var(--font-mono);font-size:13px;font-weight:700;'
      + 'letter-spacing:1px;color:var(--accent);text-decoration:none;border:1px solid var(--accent);'
      + 'border-radius:6px;padding:3px 10px';
    hote.appendChild(a);
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', poser);
  else poser();
  window.LogxRetourLogbook = {estDetachee: estDetachee, poser: poser};
})();
