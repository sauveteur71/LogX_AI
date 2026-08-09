// EV-7 phase 2 (docs/LogX_AI_PRD.md) -- 22e increment : TOGGLE JOUR/NUIT +
// RACCOURCIS CLAVIER GLOBAUX, extrait tel quel de logx_logbook.js. Charge en
// <script> classique dans logx_logbook.html AVANT logx_logbook.js, portee
// globale partagee (meme convention que les 21 increments precedents).
//
// Contenu : toggleTheme(), toggleShortcutsHelp(), l'IIFE auto-executee
// (function applyTheme(){...})() (theme jour/nuit au chargement -- a ne pas
// confondre avec la fonction homonyme INDEPENDANTE de logx_statusbar.js,
// portee lexicale differente, aucune collision malgre le nom identique),
// _modaleOuverte(), et le gros ecouteur document.addEventListener('keydown',
// ...) (macros F1-F8, Search&Pounce Ctrl+Fleches, SO2R Ctrl+Espace, F9
// soumettre, Echap fermer les popups, ? aide raccourcis, Ctrl+Z annuler,
// Ctrl+F focus indicatif, Entree valider).
//
// Grep exhaustif fait AVANT extraction : AUCUN appel top-level restant dans
// logx_logbook.js ne depend d'un symbole de ce fichier (les 4 identifiants
// exportes -- toggleTheme/toggleShortcutsHelp/_modaleOuverte/applyTheme --
// ne sont references NULLE PART ailleurs dans logx_logbook.js, dans les
// fichiers deja extraits, ni dans logx_logbook.html en dehors des attributs
// onclick= (resolution tardive, sans risque)). Egalement verifie
// specifiquement (piege du 21e increment, function-body depuis submitQSO()/
// clearForm()/onCallInput()) : aucune de ces 3 fonctions coeur n'appelle
// quoi que ce soit de ce bloc.
//
// document.addEventListener('keydown', ...) est lui-meme un appel TOP-LEVEL
// (s'execute au chargement de CE fichier), mais il ne fait qu'ENREGISTRER
// une fermeture (closure) -- addEventListener est une API navigateur, pas
// un symbole EV-7. Le corps de la fermeture reference de nombreux globals du
// coeur (isSetupDone, getMacros, copyMacro, so2rBasculer, submitQSO,
// undoLastQSO) mais ne les RESOUT qu'au moment reel d'une frappe clavier,
// bien apres que tous les <script> aient charge -- aucun risque d'ordre
// malgre l'enregistrement immediat.
//
// Dependance optionnel->coeur (sens autorise, fonctions seulement) :
// document.body, localStorage, fetch, isSetupDone, getMacros(), copyMacro(),
// so2rBasculer(), submitQSO(), undoLastQSO().
//
// EV-7 28e increment : bandmapSaut()/bandmapNoter() ont ete extraites vers
// logx_bandmap_sp.js -- la dependance ci-dessus est desormais
// optionnel->optionnel (les deux fichiers chargent avant logx_logbook.js).

// ─── TOGGLE JOUR/NUIT ────────────────────────────────────────────────────────
function toggleTheme(){
  const day = document.body.classList.toggle('day-mode');
  localStorage.setItem('rc_theme', day ? 'day' : 'night');
  document.getElementById('themeToggle').textContent = day ? '🌙' : '☀️';
  // Partagé au serveur : les autres postes ouvrant le lien multi-poste pour
  // la 1re fois hériteront de ce thème au lieu de retomber en mode nuit.
  fetch('/ui/theme', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({theme: day ? 'day' : 'night'})}).catch(()=>{});
}

function toggleShortcutsHelp(){
  document.getElementById('shortcutsOverlay').classList.toggle('show');
}

(function applyTheme(){
  if(localStorage.getItem('rc_theme') === 'day'){
    document.body.classList.add('day-mode');
    document.addEventListener('DOMContentLoaded', ()=>{
      const t = document.getElementById('themeToggle');
      if(t) t.textContent = '🌙';
    });
  }
})();

// ─── RACCOURCIS CLAVIER ───────────────────────────────────────────────────────
// Une fenêtre modale est-elle ouverte ? Sert à neutraliser les macros F1-F8 :
// en train d'éditer un QSO ou de relire le vérificateur, on ne veut surtout pas
// qu'une touche de fonction parte en émission. Mêmes boîtes que celles que la
// touche Échap referme, plus bas.
function _modaleOuverte(){
  const setup = document.getElementById('setupModal');
  if(setup && setup.style.display !== 'none' && setup.style.display !== '') return true;
  return ['editOverlay', 'shortcutsOverlay', 'validateOverlay',
          'awardsOverlay', 'importOverlay'].some(id => {
    const el = document.getElementById(id);
    return el && el.classList.contains('show');
  });
}

document.addEventListener('keydown', e => {
  // ─── F1 à F8 : les macros, au clavier ─────────────────────────────────────
  // Les boutons AFFICHENT « F1 »… « F8 » depuis toujours, mais seul le clic les
  // déclenchait : en run ou en pile-up, la main devait quitter le clavier pour
  // viser un bouton. C'est la fonction que N1MM, Win-Test et DXLog mettent en
  // avant en premier, et la première qu'un contesteur essaie.
  //
  // Volontairement actif MÊME quand le focus est dans un champ de saisie :
  // c'est tout l'intérêt — on tape l'indicatif, on envoie l'échange, on
  // continue de taper sans rien viser.
  //
  // preventDefault() n'est pas une politesse : dans un navigateur, F5 recharge
  // la page (perte de la saisie en cours EN PLEIN CONCOURS), F3 ouvre la
  // recherche, F1 l'aide et F6 la barre d'adresse. Sans lui, la moitié des
  // macros seraient inutilisables.
  //
  // On cherche la macro par son libellé de touche plutôt que par sa position :
  // l'utilisateur peut réaffecter la touche d'une macro (editMacro), et le
  // clavier doit suivre ce qu'il voit écrit sur le bouton.
  if(/^F[1-8]$/.test(e.key) && !e.ctrlKey && !e.altKey && !e.metaKey){
    e.preventDefault();
    if(!isSetupDone || _modaleOuverte()) return;
    const macros = getMacros();
    const idx = macros.findIndex(m => m && m.key === e.key);
    if(idx >= 0) copyMacro(idx);
    return;
  }
  // ─── Search & Pounce au clavier ───────────────────────────────────────────
  // Ctrl+↑ / Ctrl+↓ : sauter au spot suivant/précédent du band map, QSY compris
  // et indicatif pré-rempli. Ctrl+Entrée : noter la station en cours.
  // Ces trois gestes forment la boucle du S&P — balayer, noter, rappeler —
  // sans jamais quitter le clavier. Les flèches SEULES restent aux suggestions
  // d'indicatif et de locator, qu'on ne doit pas leur voler.
  if((e.ctrlKey || e.metaKey) && (e.key === 'ArrowUp' || e.key === 'ArrowDown')){
    e.preventDefault();
    if(isSetupDone && !_modaleOuverte()) bandmapSaut(e.key === 'ArrowDown' ? 1 : -1);
    return;
  }
  if((e.ctrlKey || e.metaKey) && e.key === 'Enter'){
    e.preventDefault();
    if(isSetupDone && !_modaleOuverte()) bandmapNoter();
    return;
  }
  // SO2R : Ctrl+Espace bascule l'émission sur l'autre radio. C'est LE geste
  // du SO2R, il doit être atteignable sans quitter le clavier ni regarder
  // l'écran — on appelle CQ d'un côté en cherchant de l'autre.
  if((e.ctrlKey || e.metaKey) && e.key === ' '){
    e.preventDefault();
    if(isSetupDone && !_modaleOuverte()) so2rBasculer();
    return;
  }
  // F9 : soumettre le QSO depuis n'importe où
  if(e.key === 'F9'){
    e.preventDefault();
    if(isSetupDone) submitQSO();
    return;
  }
  // Escape : fermer le modal de setup
  if(e.key === 'Escape'){
    const modal = document.getElementById('setupModal');
    if(modal && modal.style.display !== 'none') modal.style.display = 'none';
    // La fenêtre d'édition de QSO s'appelle editOverlay et s'ouvre/ferme par
    // la classe .show (pas editModal/style.display — ancien mécanisme disparu).
    const editOverlay = document.getElementById('editOverlay');
    if(editOverlay) editOverlay.classList.remove('show');
    const scOverlay = document.getElementById('shortcutsOverlay');
    if(scOverlay) scOverlay.classList.remove('show');
    const valOverlay = document.getElementById('validateOverlay');
    if(valOverlay) valOverlay.classList.remove('show');
    const awOverlay = document.getElementById('awardsOverlay');
    if(awOverlay) awOverlay.classList.remove('show');
    const impOverlay = document.getElementById('importOverlay');
    if(impOverlay) impOverlay.classList.remove('show');
    return;
  }
  // ? : afficher/masquer l'aide des raccourcis (sauf pendant une saisie)
  if(e.key === '?' && !['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)){
    e.preventDefault();
    toggleShortcutsHelp();
    return;
  }
  // Ctrl+Z : annuler le dernier QSO
  if((e.ctrlKey || e.metaKey) && e.key === 'z'){
    e.preventDefault();
    undoLastQSO();
    return;
  }
  // Ctrl+F : focus sur le champ indicatif
  if((e.ctrlKey || e.metaKey) && e.key === 'f'){
    e.preventDefault();
    const inp = document.getElementById('inputCall');
    if(inp){ inp.focus(); inp.select(); }
    return;
  }
  // Entrée : valider le QSO depuis n'importe quel champ de la saisie
  // (filet de sécurité pour les boutons OPÉRATEUR/BANDE/MODE — les champs texte
  // gèrent déjà Enter eux-mêmes et appellent preventDefault, donc pas de double envoi)
  if(e.key === 'Enter' && !e.defaultPrevented){
    const form = document.querySelector('.saisie-form');
    if(form && form.contains(e.target) && e.target.tagName !== 'TEXTAREA'){
      e.preventDefault();
      submitQSO();
    }
  }
});
