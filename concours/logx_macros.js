// EV-7 phase 2, 32e increment : MACROS F1-F8 -- extrait de
// logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script> classique
// dans logx_logbook.html, AVANT logx_logbook.js -- portee globale
// partagee (comme tous les fichiers EV-7).
//
// Contient : DEFAULT_MACROS, getMacros()/saveMacros(), expandMacro(),
// renderMacroPanel(), copyMacro(), editMacro().
//
// EXTRACTION NON CONTIGUE (piege documente dans l'inventaire EV-7) :
// dans le fichier d'origine, ce bloc etait entrecoupe de deux sections
// RESTEES dans le coeur -- i18n (trT/trF/notify(), lues ici en corps de
// fonction par copyMacro()/editMacro()) et adaptivePoll() (reutilisee
// par pollChat(), sans rapport avec les macros). Les 3 sous-blocs
// (DEFAULT_MACROS..renderMacroPanel, copyMacro, editMacro) ont ete
// recolles ici dans le meme ordre logique ; leur position relative aux
// deux sections restees dans le coeur n'a plus d'importance (JS hoiste
// les declarations de fonction).
//
// Dependances croisees verifiees sures : copyMacro()/editMacro() lisent
// trT()/trF() (coeur, i18n) en corps de fonction. copyMacro() lit
// rigState (logx_hardware_cat.js, deja extrait, charge encore plus tot)
// sous garde typeof deja existante. renderMacroPanel() est appelee
// depuis le coeur dans window.addEventListener('DOMContentLoaded', ...)
// -- motif deja eprouve, sans risque d'ordre. logx_theme_shortcuts.js
// (deja extrait, 22e increment, CHARGE AVANT ce fichier) appelle
// getMacros()/copyMacro() dans un gestionnaire keydown -- deferre a
// l'apres-chargement complet de la page (frappe utilisateur), sans
// risque d'ordre malgre le sens de dependance optionnel->optionnel
// inhabituel (fichier charge plus tot referencant un fichier charge
// plus tard). Meme raisonnement pour logx_esm_callbot.js (copyMacro(),
// deja garde par typeof). RTTY a sa PROPRE version simplifiee locale de
// expandMacro() dans logx_rtty.html (fenetre detachee, EV-7 phase 2
// increment B) -- plus une dependance a ce fichier.

// ─── MACROS F1–F8 ────────────────────────────────────────────────────────────
const DEFAULT_MACROS = [
  {key:'F1', label:'CQ RPH',   text:'CQ RPH {CALL} {CALL}'},
  {key:'F2', label:'ÉCHANGE',  text:'59 {NR} {LOC}'},
  {key:'F3', label:'TU',       text:'TU {CALL} TEST'},
  {key:'F4', label:'QSY 432?', text:'QSY 432.200?'},
  {key:'F5', label:'LOCATOR',  text:'{LOC} {LOC}'},
  {key:'F6', label:'?',        text:'{CALL}?'},
  {key:'F7', label:'AGN?',     text:'AGN?'},
  {key:'F8', label:'73',       text:'73 {CALL}'},
];
function getMacros(){ try{ const s=localStorage.getItem('logx_macros'); return s?JSON.parse(s):DEFAULT_MACROS; }catch(e){ return DEFAULT_MACROS; } }
function saveMacros(m){ localStorage.setItem('logx_macros', JSON.stringify(m)); }
// {NR} doit valoir EXACTEMENT le numéro qui sera loggué : la macro F2
// (« 59 {NR} {LOC} ») part directement au keyer de la radio via copyMacro() →
// POST /rig/cw, y compris automatiquement en mode ESM (esmSend('exchange')).
// La seule source de vérité est donc le champ N° ENVOYÉ (#inputNumSent), tenu
// à jour par updateSerialDisplay() à partir de serialByBand[bande] — le n° de
// série est alloué PAR BANDE et par portée concours (nextSerial() →
// /log/next_serial → logx_storage.allocate_next_serial), et c'est cette
// valeur-là qui finit dans num_sent puis dans l'EDI/Cabrillo.
//
// L'ancien calcul, String(qsoLog.length+1), comptait TOUS les QSO de l'édition
// toutes bandes confondues (et, en multi-poste, ceux loggués par les autres
// opérateurs sur les autres bandes) : les deux formules ne coïncidaient que sur
// un concours mono-bande sans trou. Dès le premier QSO d'une deuxième bande —
// cas normal en IARU UHF/SHF, Marconi, Rallye des Points Hauts, CQ WPX… — la
// radio envoyait sur l'air un numéro absent du log, et l'écart croissait à
// chaque QSO ; le correspondant note un numéro introuvable au cross-check, les
// deux QSO tombent, et l'opérateur n'a aucun recours (champ readOnly par
// conception, cf. updateSerialDisplay). Le chemin VOCAL (sendVoiceDynMacro)
// lisait déjà ce même champ : seul le chemin CW était resté sur le compteur global.
// {HISCALL} : l'indicatif du CORRESPONDANT, lu en direct dans le champ de
// saisie. Il manquait purement et simplement -- {CALL} désigne TA station, et
// aucun jeton ne pouvait rendre l'indicatif tapé. Renvoyer l'indicatif corrigé
// du correspondant après une reprise est pourtant un geste standard du run :
// sans lui, la macro F3 « TU {CALL} TEST » remercie sa propre station.
//
// L'alias `!` de N1MM+ a été ÉCARTÉ délibérément, après avoir été écrit puis
// retiré : il aurait épargné une réécriture aux macros importées de N1MM, mais
// au prix d'une substitution silencieuse de TOUT point d'exclamation. Une macro
// « 73 ! » serait partie en « 73 F5XYZ » sans que rien ne le signale, y compris
// par le chemin presse-papier utilisé en phonie. Un jeton entre accolades est
// visible et cohérent avec les trois autres ; un `!` invisible ne l'est pas.
// À rouvrir si des opérateurs migrant de N1MM le réclament -- ce serait alors
// une option, pas un comportement par défaut.
//
// Repli sur '' plutôt que sur un tiret : une macro envoyée alors qu'aucun
// indicatif n'est saisi ne doit pas émettre un caractère parasite sur l'air.
function _hisCall(){
  const el = document.getElementById('inputCall');
  return el ? String(el.value || '').trim().toUpperCase() : '';
}
function expandMacro(text){
  const cfg = JSON.parse(localStorage.getItem('logx_config')||'{}');
  const call = cfg.callsign || myCall || '—';
  const loc  = cfg.locator  || myLocator || '—';
  const his  = _hisCall();
  const nrEl = document.getElementById('inputNumSent');
  const nrField = nrEl ? String(nrEl.value || '').trim() : '';
  // Repli si le champ n'est pas encore renseigné (panneau macros rendu avant
  // le premier updateSerialDisplay()) : même formule que l'affichage, jamais
  // un compteur global. Pour un échange non sériel (zone, dept, classe…) il
  // n'y a rien à prédire : on laisse la valeur du champ telle quelle.
  const nr = nrField || (currentExchange.auto_serial
    ? String((serialByBand[currentBand] || 0) + 1).padStart(3,'0')
    : '');
  // {HISCALL} en DERNIER, et la justification initiale était fausse : /{CALL}/
  // ne peut PAS s'accrocher à l'intérieur de « {HISCALL} » (il faudrait une
  // accolade ouvrante juste avant « CALL », or il y a « S »). Les deux ordres
  // sont donc équivalents sur ce point — mais un seul est sûr sur un autre :
  // substituer {HISCALL} en premier réinjecte dans le texte une valeur venue
  // de la SAISIE, qui repasse ensuite sous les trois substitutions suivantes.
  // Un indicatif contenant « {LOC} » (collé depuis un spot de cluster, champ
  // mal rempli) serait alors ré-interprété. On ne re-substitue jamais une
  // valeur d'origine externe. (Revue adversariale du lot, 18/08/2026.)
  return text.replace(/{CALL}/g,call).replace(/{LOC}/g,loc).replace(/{NR}/g,nr)
             .replace(/{HISCALL}/g,his);
}
function renderMacroPanel(){
  const btns = document.getElementById('macroBtns');
  if(!btns) return;
  const macros = getMacros();
  btns.innerHTML = '';
  macros.forEach((m, idx) => {
    const btn = document.createElement('button');
    btn.className = 'macro-btn';
    btn.title = expandMacro(m.text);
    btn.innerHTML = `<span class="mk">${m.key}</span><span class="mt">${m.label}</span>`;
    btn.onclick    = e => { e.stopPropagation(); copyMacro(idx); };
    btn.ondblclick = e => { e.stopPropagation(); editMacro(idx); };
    btns.appendChild(btn);
  });
}


function copyMacro(idx){
  const m = getMacros()[idx]; if(!m) return;
  const txt = expandMacro(m.text);
  // Émission CW possible → la macro part directement par le keyer ; sinon
  // (SSB/RTTY, ou aucune manipulation pilotée) on copie dans le presse-papier.
  // On délègue à cwEmissionPossible() (logx_hardware_cat.js) : la condition
  // testait rigState.enabled, c'est-à-dire le CAT SEUL, alors que le serveur
  // route /rig/cw vers le WinKeyer AVANT tout backend CAT et indépendamment de
  // lui. Un opérateur WinKeyer sans CAT voyait donc ses macros atterrir dans le
  // presse-papier alors que le serveur savait parfaitement les envoyer à la clé.
  // Garde typeof conservée : même motif que les autres lectures de rigState
  // hors de ce fichier (EV-7).
  if(typeof cwEmissionPossible === 'function' && cwEmissionPossible()){
    fetch('/rig/cw', {method:'POST', headers:{'Content-Type':'application/json'},
                      body: JSON.stringify({text: txt})})
      .then(r=>r.json()).then(d=>{
        const toast = document.getElementById('macroToast');
        if(toast){ toast.textContent = d.ok ? trF('📻 CW → {txt}', {txt})
                                             : trF('❌ {err}', {err: d.error});
          toast.className = 'macro-toast' + (d.ok ? '' : ' toast-err');
          toast.classList.add('show'); setTimeout(()=>toast.classList.remove('show'), 2200); }
      }).catch(()=>{});
    return;
  }
  navigator.clipboard.writeText(txt).catch(()=>{});
  const toast = document.getElementById('macroToast');
  if(toast){ toast.textContent = trF('📋 {txt}', {txt}); toast.classList.add('show'); setTimeout(()=>toast.classList.remove('show'), 2000); }
}



function editMacro(idx){
  const macros = getMacros();
  const m = macros[idx];
  const newLabel = prompt(trF('Label pour {k} :', {k: m.key}), m.label);
  if(newLabel === null) return;
  // {HISCALL} annoncé ici : un jeton que l'interface ne nomme nulle part
  // n'existe pas pour l'opérateur. `!` (alias N1MM) n'est volontairement PAS
  // listé — il sert aux macros recopiées depuis N1MM, pas à la découverte.
  const newText = prompt(trT('Message ({CALL} {HISCALL} {LOC} {NR}) :'), m.text);
  if(newText === null) return;
  macros[idx] = {...m, label:newLabel.trim()||m.label, text:newText.trim()||m.text};
  saveMacros(macros); renderMacroPanel();
}

