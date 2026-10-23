// ─── SAISIE QSO DÉTACHÉE (fenêtre « saisie seule » pour un 2e écran) ─────────
// Demande F4GLD (23/10/2026) : « détacher la zone de saisie de QSO pour n'avoir
// que ça sur un écran séparé ».
//
// PRINCIPE — aucune deuxième implémentation de la saisie. La fenêtre détachée
// est LA MÊME page (logx_logbook.html) ouverte avec ?vue=saisie : un script
// inline du <head> pose la classe html.vue-saisie AVANT le premier rendu, et
// une feuille de style MASQUE tout le reste (doctrine « masquer ≠ bloquer » :
// masquage CSS pur, aucune fonction désactivée). L'enregistrement d'un QSO
// passe donc par le submitQSO() habituel — validation, numéro de série,
// doublons, scoring, sauvegarde : rien n'est dupliqué. Le chemin critique ne
// dépend PAS de ce fichier : s'il ne se charge pas, seul le bouton disparaît.
//
// SYNCHRO : logx_broadcast.js diffuse déjà chaque ajout/modification/
// suppression de QSO aux autres fenêtres du même navigateur (BroadcastChannel
// 'logx_log') -> un QSO saisi dans la fenêtre détachée apparaît aussitôt dans
// le tableau de la fenêtre principale, et inversement.

(function(global){
  'use strict';

  var NOM_FENETRE = 'rc_saisie_detachee';

  function estVueSaisie(){
    return document.documentElement.classList.contains('vue-saisie');
  }

  // Ouvre (ou ramène au premier plan) la fenêtre de saisie seule. Le nom de
  // fenêtre FIXE fait que window.open() réutilise la fenêtre déjà ouverte au
  // lieu d'en empiler une deuxième.
  function detacherSaisie(){
    var w = 900;
    var h = Math.max(600, (global.screen && global.screen.availHeight) || 1000);
    var url = 'logx_logbook.html?vue=saisie';
    var win = global.open(url, NOM_FENETRE,
      'width=' + w + ',height=' + h + ',menubar=no,toolbar=no,location=no');
    if(win){ try{ win.focus(); }catch(e){} }
    else if(typeof global.alert === 'function'){
      global.alert("Le navigateur a bloqué l'ouverture de la fenêtre de saisie.\n"
        + "Autorise les fenêtres pop-up pour localhost, puis réessaie.");
    }
    return win;
  }

  global.detacherSaisie = detacherSaisie;
  global.LogxSaisieDetachee = { detacherSaisie: detacherSaisie, estVueSaisie: estVueSaisie,
                                NOM_FENETRE: NOM_FENETRE };
  if(typeof module !== 'undefined' && module.exports) module.exports = global.LogxSaisieDetachee;
})(typeof window !== 'undefined' ? window : this);
