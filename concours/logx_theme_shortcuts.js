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
// un symbole EV-7. Le corps de la fermeture reference de nombreux globals
// (isSetupDone, getMacros, copyMacro, so2rBasculer, submitQSO, undoLastQSO)
// mais ne les RESOUT qu'au moment reel d'une frappe clavier, bien apres que
// tous les <script> aient charge -- aucun risque d'ordre malgre
// l'enregistrement immediat.
//
// Dependance optionnel->coeur (sens autorise, fonctions seulement) :
// document.body, localStorage, fetch, isSetupDone, getMacros(), copyMacro(),
// submitQSO(), undoLastQSO().
//
// EV-7 28e increment : bandmapSaut()/bandmapNoter() ont ete extraites vers
// logx_bandmap_sp.js -- la dependance ci-dessus est desormais
// optionnel->optionnel (les deux fichiers chargent avant logx_logbook.js).
//
// EV-7 36e increment : so2rBasculer() a ete extraite vers
// logx_outils_divers.js -- direction inhabituelle deja rencontree (MACROS
// 32e increment, FILTRE SPOTS 33e) : ce fichier charge AVANT
// logx_outils_divers.js, mais l'appel reste en corps de fermeture (jamais
// au chargement), donc sans risque.
//
// EV-7 32e increment : getMacros()/copyMacro() ont ete extraites vers
// logx_macros.js -- la dependance devient optionnel->optionnel, mais dans le
// sens INHABITUEL (ce fichier, 22e increment, charge AVANT logx_macros.js,
// 32e) : sans consequence puisque le corps de la fermeture keydown ne
// resout ces symboles qu'au moment reel d'une frappe clavier, toujours apres
// la fin du chargement de TOUS les <script> -- meme raisonnement que pour
// bandmapSaut()/bandmapNoter() ci-dessus, juste applique a un fichier plus
// tardif dans l'ordre de chargement.

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
// Retourne l'élément DOM de la modale actuellement visible, ou null. Sert à la
// fois à _modaleOuverte() (booléen) et au piège de focus Tab/Shift+Tab plus bas
// (a besoin de l'élément lui-même pour lister ses champs focusables).
function _elementModaleOuverte(){
  // Bandeau de confirmation non bloquant (chantier dialogues non bloquants,
  // 10/08/2026) : vérifié EN PREMIER -- position:fixed;z-index:9999 (voir
  // logx_logbook.html), il se dessine AU-DESSUS de toute autre modale de la
  // liste ci-dessous (dont beaucoup l'appellent depuis leur propre overlay,
  // z-index:500) -- sans cette priorité, le piège de focus Tab resterait
  // confiné à l'overlay du dessous, rendant les boutons du bandeau
  // inatteignables au clavier alors qu'ils sont visuellement au premier plan.
  const dupBanner = document.getElementById('dupConfirmBanner');
  if(dupBanner && dupBanner.classList.contains('show')) return dupBanner;
  const setup = document.getElementById('setupModal');
  if(setup && setup.style.display !== 'none' && setup.style.display !== '') return setup;
  const ids = ['editOverlay', 'shortcutsOverlay', 'validateOverlay',
               'awardsOverlay', 'importOverlay', 'checklistOverlay',
               'qtcOverlay', 'filterOverlay', 'dupOverlay', 'netOverlay',
               'rateOverlay', 'qslCardOverlay',
               // Manquaient à ce registre alors qu'ils utilisent le même
               // mécanisme .classList.add('show') que les 12 ID ci-dessus
               // (voacapOverlay : logx_logbook.js openVoacapPanel() ;
               // bulkResolveOverlay : logx_bulk_resolve.js) — les macros F1-
               // F8 (TX CW/vocal) restaient actives au clavier même quand
               // ces panneaux étaient ouverts.
               'voacapOverlay', 'bulkResolveOverlay'];
  for(const id of ids){
    const el = document.getElementById(id);
    if(el && el.classList.contains('show')) return el;
  }
  return null;
}

function _modaleOuverte(){
  return !!_elementModaleOuverte();
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
    if(typeof getMacros === 'function' && typeof copyMacro === 'function'){
      const macros = getMacros();
      const idx = macros.findIndex(m => m && m.key === e.key);
      if(idx >= 0) copyMacro(idx);
    }
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
  // Escape : arrêt CW d'urgence, puis fermeture des panneaux
  if(e.key === 'Escape'){
    // PRIORITÉ ABSOLUE, avant toute fermeture de panneau : couper une émission
    // CW en cours. C'est le geste réflexe du contesteur, et jusqu'ici il
    // n'était branché sur RIEN — le seul moyen d'arrêter était un bouton
    // enfermé dans #rigPanel, donc invisible pour un opérateur WinKeyer sans
    // CAT (le WinKeyer est pourtant routé indépendamment du CAT côté serveur).
    // On ne fait PAS return : Échap doit garder tous ses autres effets.
    // Conditionné par cwEmissionPossible() plutôt qu'inconditionnel, pour ne
    // pas émettre une requête réseau à chaque Échap sur une station sans
    // manipulation CW.
    if(typeof cwEmissionPossible === 'function' && cwEmissionPossible()
       && typeof rigStopCW === 'function') rigStopCW();
    // Bandeau de confirmation non bloquant (chantier dialogues non bloquants,
    // 10/08/2026) : un confirm() natif se fermait déjà sur Échap (= refus) --
    // même comportement ici, avant tout le reste (il est visuellement au
    // premier plan, cf. priorité dans _elementModaleOuverte() plus haut).
    if(typeof _cancelPendingDupConfirm === 'function') _cancelPendingDupConfirm();
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
    // Constats audit accessibilité 09/08/2026 : ces 6 panneaux n'avaient aucun
    // moyen de fermeture au clavier (ni Échap, ni bouton focusable) -- on
    // appelle leur fonction de fermeture dédiée quand elle existe (nettoyage
    // associé : resetQTCFields, destruction du graphique du panneau taux...),
    // sinon un simple classList.remove('show') (checklistOverlay).
    if(document.getElementById('checklistOverlay')?.classList.contains('show')){
      document.getElementById('checklistOverlay').classList.remove('show');
    }
    if(document.getElementById('qtcOverlay')?.classList.contains('show') && typeof closeQTCPanel === 'function') closeQTCPanel();
    if(document.getElementById('filterOverlay')?.classList.contains('show') && typeof closeFilterBuilder === 'function') closeFilterBuilder();
    if(document.getElementById('dupOverlay')?.classList.contains('show') && typeof closeDupFinder === 'function') closeDupFinder();
    if(document.getElementById('netOverlay')?.classList.contains('show') && typeof closeNetControl === 'function') closeNetControl();
    if(document.getElementById('rateOverlay')?.classList.contains('show') && typeof closeRatePanel === 'function') closeRatePanel();
    if(document.getElementById('qslCardOverlay')?.classList.contains('show')) document.getElementById('qslCardOverlay').classList.remove('show');
    return;
  }
  // Tab / Shift+Tab : piège de focus générique dans la modale ouverte (audit
  // accessibilité 09/08/2026 -- sans ça, tabuler depuis le dernier champ d'une
  // modale ressort vers le contenu masqué derrière l'overlay). S'applique à
  // TOUTE modale connue de _elementModaleOuverte(), pas seulement aux 6 ci-dessus.
  if(e.key === 'Tab'){
    const modal = _elementModaleOuverte();
    if(modal){
      const focusables = Array.from(modal.querySelectorAll(
        'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'
      )).filter(el => el.offsetParent !== null);
      if(focusables.length){
        const first = focusables[0], last = focusables[focusables.length - 1];
        if(e.shiftKey && document.activeElement === first){
          e.preventDefault();
          last.focus();
        } else if(!e.shiftKey && document.activeElement === last){
          e.preventDefault();
          first.focus();
        }
      }
    }
  }
  // ? : afficher/masquer l'aide des raccourcis (sauf pendant une saisie)
  if(e.key === '?' && !['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)){
    e.preventDefault();
    toggleShortcutsHelp();
    return;
  }
  // Ctrl+Z : annuler le dernier QSO -- exclu des champs de saisie (même
  // filet que le raccourci '?' ci-dessus) : sans ça, un Ctrl+Z tapé dans un
  // champ (RST, remarques...) en attendant l'undo natif du navigateur
  // déclenchait à la place la suppression confirm() du dernier QSO, en
  // pleine frappe de correction (audit accessibilité 09/08/2026).
  if((e.ctrlKey || e.metaKey) && e.key === 'z' && !['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)){
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

// Focus automatique à l'ouverture de toute modale connue de
// _elementModaleOuverte() (sauf editOverlay, qui gère déjà son propre focus
// dans editQSO() -- voir logx_edit_qso.js) : sans focus initial posé DANS la
// modale, le piège Tab/Shift+Tab ci-dessus ne peut jamais s'activer, car
// document.activeElement reste hors de la liste `focusables` calculée par le
// piège (aucune des fonctions openXxx()/showXxx() existantes ne pose de
// focus). Constat MAJEUR confirmé en navigateur réel par la revue
// adversariale du 09/08/2026 -- corrigé une fois ici plutôt que de patcher
// individuellement 10 fonctions d'ouverture réparties sur 8 fichiers.
(function(){
  const watchedIds = ['shortcutsOverlay', 'validateOverlay', 'awardsOverlay',
                       'importOverlay', 'checklistOverlay', 'qtcOverlay',
                       'filterOverlay', 'dupOverlay', 'netOverlay', 'rateOverlay',
                       'qslCardOverlay', 'dupConfirmBanner'];
  function focusFirstIn(el){
    const f = el.querySelector(
      'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'
    );
    if(f) f.focus();
  }
  function attachObserver(id){
    const el = document.getElementById(id);
    if(!el) return;
    const mo = new MutationObserver(muts => {
      for(const m of muts){
        if(m.attributeName === 'class' && el.classList.contains('show')) focusFirstIn(el);
      }
    });
    mo.observe(el, {attributes: true, attributeFilter: ['class']});
  }
  function attachAll(){ watchedIds.forEach(attachObserver); }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', attachAll);
  else attachAll();
})();
