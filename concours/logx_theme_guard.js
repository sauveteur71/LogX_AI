// logx_theme_guard.js — détecte une feuille de THÈME non appliquée et le DIT.
//
// POURQUOI. Les tokens de thème (couleurs, polices) vivent dans
// logx_theme.css (mutualisé, PR #342). Si cette feuille est bloquée ou tronquée
// avant d'être appliquée — cas RÉEL : le Web Shield d'un antivirus (Avast) ou un
// proxy local inspecte/coupe la réponse — TOUT `var(--x)` devient indéfini. Les
// symptômes sont alors épars et déroutants : police serif au lieu de la mono,
// texte sombre sur fond sombre (modales illisibles), barres/repères sans couleur
// (ex. la barre de cycle FT8 en vert qui « disparaît »). L'opérateur les
// découvre un par un sans jamais voir la cause commune.
//
// CE QUE FAIT CE GARDE-FOU. Après chargement, il lit UN token cœur (--accent)
// sur :root. Vide => la feuille de thème n'est pas appliquée => bandeau rouge
// explicite, avec la cause probable et le geste (exception antivirus + Ctrl+F5).
// Le bandeau n'utilise QUE des valeurs EN DUR (police système, hex fixes) : il
// doit rester visible PRÉCISÉMENT quand les tokens de thème manquent.
(function(global){
  'use strict';

  // true si la feuille de thème est appliquée (token cœur présent sur :root).
  function themeApplique(){
    try{
      var doc = global.document;
      var v = global.getComputedStyle(doc.documentElement)
                    .getPropertyValue('--accent').trim();
      return !!v;
    }catch(e){
      return true;   // pas de DOM/getComputedStyle (banc de test) : ne rien signaler
    }
  }

  function afficherBandeau(){
    var doc = global.document;
    if(doc.getElementById('themeGuardBanner')) return;
    var b = doc.createElement('div');
    b.id = 'themeGuardBanner';
    b.setAttribute('role', 'alert');
    b.style.cssText = 'position:fixed;left:0;right:0;top:0;z-index:2147483647;'
      + 'background:#B3261E;color:#fff;font:600 13px/1.45 system-ui,Arial,sans-serif;'
      + 'padding:10px 16px;text-align:center;box-shadow:0 2px 10px rgba(0,0,0,.45)';
    b.textContent = "⚠ Feuille de style non chargée — l'affichage est "
      + "dégradé (polices, couleurs, barres de progression, contraste). Cause "
      + "probable : un antivirus ou proxy (ex. Avast Web Shield) bloque logx_theme.css. "
      + "Ajoute une exception pour http://localhost:8080 (et l'IP du serveur), puis "
      + "recharge avec Ctrl+F5.";
    (doc.body || doc.documentElement).appendChild(b);
  }

  function verifier(){
    if(!themeApplique()) afficherBandeau();
  }

  function armer(){
    // Léger différé : certains navigateurs appliquent la CSS de façon asynchrone
    // même après 'load'. On laisse au <link> le temps de s'appliquer.
    var doc = global.document;
    if(!doc) return;
    if(doc.readyState === 'complete') global.setTimeout(verifier, 300);
    else global.addEventListener('load', function(){ global.setTimeout(verifier, 300); });
  }

  // Exposé pour les tests ; auto-armement en navigateur.
  global.LogxThemeGuard = {themeApplique: themeApplique, verifier: verifier,
                           afficherBandeau: afficherBandeau};
  if(global.document && global.addEventListener) armer();

})(typeof window !== 'undefined' ? window : this);
