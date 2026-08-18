// Mode DÉBUTANT/EXPERT — socle minimal, pour les pages SANS barre de statut.
//
// POURQUOI CE FICHIER EXISTE
// Le mécanisme `.expert-only` vivait entièrement dans logx_statusbar.js. Or les
// fenêtres DÉTACHÉES (FT8, RTTY, SSTV, panadapter, scope, mur d'expédition…)
// n'incluent pas ce script : elles n'ont ni navigation ni barre de statut, par
// conception — ce sont des panneaux qu'on sort sur un second écran.
// Conséquence mesurée le 18/08/2026 : ces pages ne comptaient AUCUN élément
// `expert-only`, et il aurait été inutile d'en ajouter — sans la règle CSS
// injectée par la barre de statut, la classe n'aurait rien masqué du tout.
// C'est un défaut de PORTÉE du mécanisme, pas un oubli de marquage.
//
// Ce fichier n'apporte donc que le strict nécessaire : lire le choix de
// l'opérateur et appliquer la règle. Aucune barre, aucun bouton, aucun réseau.
// logx_statusbar.js s'appuie dessus quand il est présent (voir plus bas), pour
// qu'il n'existe qu'UNE définition de « mode simple » dans le produit.
//
// À INCLURE dans toute nouvelle page détachée, avant les scripts qui rendent
// l'interface — sans quoi elle repart avec le même trou.
(function () {
  'use strict';

  // Même clé que CONFIG et que la barre de statut : le choix est GLOBAL, une
  // fenêtre détachée doit respecter le mode choisi dans la fenêtre principale.
  function uiModeIsSimple() {
    try { return localStorage.getItem('rc_ui_mode') === 'simple'; }
    catch (e) { return false; }   // stockage indisponible : on n'ampute rien
  }

  function appliquerUiMode() {
    if (!uiModeIsSimple()) return;
    document.body.classList.add('simple-mode');
    // Règle injectée plutôt que posée dans chaque feuille de style : les 19
    // pages dupliquent déjà leurs propres tokens CSS, on n'ajoute pas une
    // 20e copie d'une règle qui doit rester identique partout.
    const st = document.createElement('style');
    st.textContent = 'body.simple-mode .expert-only{display:none!important}';
    document.head.appendChild(st);
  }

  // <body> peut ne pas exister encore selon l'endroit où le script est inclus.
  if (document.body) appliquerUiMode();
  else document.addEventListener('DOMContentLoaded', appliquerUiMode);

  // Exposé pour logx_statusbar.js (qui a en plus un bouton de bascule) et pour
  // les tests.
  window.rcUiModeIsSimple = uiModeIsSimple;
  window.rcAppliquerUiMode = appliquerUiMode;
})();
