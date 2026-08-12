// EV-7 phase 2, 34e increment : RACCOURCI BUREAU (bandeau offre de creation
// au premier lancement de l'executable fige) -- extrait de logx_logbook.js
// (docs/LogX_AI_PRD.md). Charge en <script> classique dans logx_logbook.html,
// AVANT logx_logbook.js -- portee globale partagee (comme tous les fichiers
// EV-7).
//
// Contient : checkShortcutOffer(), hideShortcutOffer(), createDesktopShortcut(),
// dismissShortcutOffer().
//
// Dependances croisees verifiees sures :
// - Seul appelant : init() (coeur), en corps de fonction, elle-meme appelee
//   uniquement via window.addEventListener('DOMContentLoaded', ...) --
//   jamais au chargement du script. Aucun appel top-level, aucune constante
//   locale recherchee par un test, aucun test existant ne fait reference a
//   ces 4 fonctions ni au bandeau (grep verifie sur concours/tests/).
// - logx_logbook.html reference createDesktopShortcut()/dismissShortcutOffer()
//   via deux attributs onclick -- resolus au clic, jamais au chargement.
// - Hors chemin critique : ni setupDone(), ni clearForm(), ni submitQSO(),
//   ni pickBand(), ni onFreqInput() n'appellent ni ne sont appeles par ces
//   4 fonctions (verifie explicitement, 4e inventaire EV-7).

// ─── RACCOURCI BUREAU (premier lancement de l'exécutable figé) ───────────────
// GET /shortcut/status ne renvoie show:true que si is_frozen() ET qu'aucun
// marqueur .shortcut_offered n'existe encore (voir logx_shortcut.py) — donc
// systématiquement false en mode développeur (python logx_serveur.py), la
// bannière ne peut alors jamais s'afficher, comme voulu.
async function checkShortcutOffer(){
  try{
    const r = await fetch('/shortcut/status');
    const d = await r.json();
    if(d.show){
      const el = document.getElementById('shortcutOffer');
      if(el) el.classList.add('show');
    }
  }catch(e){ /* pas bloquant : au pire la bannière n'apparaît pas cette fois */ }
}

function hideShortcutOffer(){
  const el = document.getElementById('shortcutOffer');
  if(el) el.classList.remove('show');
}

// Clic "Oui" : le serveur crée réellement le raccourci (PowerShell/COM, voir
// logx_winshell.create_desktop_shortcut) ET pose le marqueur dans tous les
// cas — la bannière ne doit donc plus jamais réapparaître après ce clic,
// même si la création elle-même a échoué.
async function createDesktopShortcut(){
  hideShortcutOffer();
  try{
    const r = await fetch('/shortcut/create_desktop', {method:'POST', headers: {'Content-Type': 'application/json'}});
    const d = await r.json();
    if(d.ok) notify(trF('🖥️ Raccourci créé sur le bureau : {path}', {path: d.path}));
    else notify(trF('❌ Raccourci bureau : {err}', {err: d.message || d.error || trT('échec')}));
  }catch(e){ notify(trT('❌ Serveur injoignable pour créer le raccourci')); }
}

// Clic "Non merci" : ne crée rien, pose juste le marqueur pour ne plus
// jamais reproposer la bannière.
function dismissShortcutOffer(){
  hideShortcutOffer();
  fetch('/shortcut/dismiss', {method:'POST', headers: {'Content-Type': 'application/json'}}).catch(()=>{});
}
