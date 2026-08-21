// EV-7 phase 2, 30e increment : DECODEUR CW #2 (audio) -- extrait de
// logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script> classique
// dans logx_logbook.html, AVANT logx_logbook.js -- portee globale
// partagee (comme tous les fichiers EV-7).
//
// Contient : _cwPanelInstances/_cwPanel() (instanciation paresseuse de
// CwPanel, radio 1 et radio 2 SO2R), les wrappers globaux
// toggleCwPanel()/toggleCwPanel2()/toggleCwDecoder()/toggleCwDecoder2()/
// clearCwOutput()/clearCwOutput2()/setCwFreq()/setCwFreq2(), les
// accesseurs de compatibilite _cwOutText/_cwOutText2, ET
// loadAudioInputDevices()/loadAudioOutputDevices() -- generiques,
// reutilisees par l'enregistreur audio par QSO (startAudioRecorder(),
// reste dans le coeur) et par le panneau RTTY (updateKeyerPanels(),
// reste dans le coeur, garde par if(rtty), meme motif deja accepte pour
// renderRttyMacroBtns()).
//
// Dependances croisees verifiees sures : startAudioRecorder() (L1426 du
// coeur) appelle loadAudioInputDevices('qsoRecDevice', true) -- via la
// chaine TOP-LEVEL initAudioRecorderPanel() (appelee non gardee en bas
// de logx_logbook.js), mais initAudioRecorderPanel() est async et son
// premier await (IndexedDB, toujours asynchrone) reporte tout appel
// reel a loadAudioInputDevices() APRES la fin du chargement synchrone
// de TOUS les <script>, donc sans risque d'ordre. updateKeyerPanels()
// (coeur) appelle loadAudioInputDevices('rttyDevice')/
// loadAudioOutputDevices('rttyOutDevice', true), toujours gardees par
// if(rtty){}.

// ─── DÉCODEUR CW ─────────────────────────────────────────────────────────────
// Vit dans .keyer-dock (bandeau plein largeur sous .main, voir logx_logbook.html)
// depuis le 04/08/2026 — plus un panneau flottant, donc plus besoin de
// _reserveBottomSpace() ici : .keyer-dock pousse .main dans le flux normal
// au lieu de flotter par-dessus. pipeline DSP dans logx_cwdecoder.js, ce
// fichier ne fait que le brancher à l'UI (device picker, bouton start/stop,
// sortie texte défilante).
// Composant partagé radio 1 / radio 2 (SO2R Phase 2) : voir logx_cw_panel.js
// (chargé avant ce fichier) pour ce qui était ~90 lignes dupliquées ligne à
// ligne (même convention de duplication que cat_port/cat2_port ailleurs dans
// le projet, ici remplacée par UNE classe paramétrée par le suffixe d'id DOM
// — CwAudioDecoder reste réentrante, les deux décodeurs tournent toujours
// indépendamment et simultanément si besoin).
// Instanciation PARESSEUSE (pas au chargement du script) : de nombreux tests
// (test_notify_dynamic_i18n.py, test_rph_weekend_fallback.py, etc.) évaluent
// logx_logbook.js dans un moteur JS isolé, SANS logx_cw_panel.js — un
// `new CwPanel()` immédiat ferait échouer leur simple chargement du script
// (donc TOUTES leurs assertions, même sans aucun rapport avec le CW) avec
// une ReferenceError. La vraie page HTML charge bien logx_cw_panel.js avant
// logx_logbook.js, donc CwPanel est de toute façon déjà disponible au moment
// où un opérateur clique réellement sur le panneau — la paresse ne change
// rien en usage normal, elle protège seulement les harnais de test partiels.
let _cwPanelInstances = null;
function _cwPanel(suffix){
  if(!_cwPanelInstances) _cwPanelInstances = { '': new CwPanel(''), '2': new CwPanel('2') };
  return _cwPanelInstances[suffix];
}

// Wrappers globaux conservés tels quels (nom et arité inchangés) : le HTML
// (onclick="toggleCwPanel()" etc.) et tests/test_cw_panel_consolidation.py
// (qui vérifie qu'il n'existe qu'UNE SEULE déclaration de toggleCwDecoder)
// n'ont besoin de rien savoir de CwPanel.
function toggleCwPanel(){ return _cwPanel('').toggle(); }
function toggleCwPanel2(){ return _cwPanel('2').toggle(); }
function toggleCwDecoder(){ return _cwPanel('').toggleDecoder(); }
function toggleCwDecoder2(){ return _cwPanel('2').toggleDecoder(); }
function clearCwOutput(){ return _cwPanel('').clearOutput(); }
function clearCwOutput2(){ return _cwPanel('2').clearOutput(); }
function setCwFreq(freq){ _cwPanel('').setFreq(freq); }
function setCwFreq2(freq){ _cwPanel('2').setFreq(freq); }
// Aide au choix du périphérique (voir CwPanel.testDevice() dans
// logx_cw_panel.js) : appelée par onchange sur #cwDevice/#cwDevice2.
function cwTestDevice(){ return _cwPanel('').testDevice(); }
function cwTestDevice2(){ return _cwPanel('2').testDevice(); }
// Détection automatique du ton CW (voir CwPanel.detectFreq() dans
// logx_cw_panel.js) : appelée par le bouton #cwDetectBtn/#cwDetectBtn2.
function cwDetectFreq(){ return _cwPanel('').detectFreq(); }
function cwDetectFreq2(){ return _cwPanel('2').detectFreq(); }

// _cwOutText/_cwOutText2 : accesseurs de compatibilité vers l'état interne de
// CwPanel — tests/test_cw_panel_consolidation.py lit/écrit _cwOutText
// directement (écrit avant ce refactor, sur le comportement de
// clearCwOutput()) ; plutôt que de le réécrire pour un détail d'implémentation
// sans rapport avec ce qu'il vérifie réellement, ces deux variables globales
// historiques restent lisibles/inscriptibles et reflètent fidèlement
// this.outText de chaque instance. Object.defineProperty() elle-même
// n'instancie rien (la paresse de _cwPanel() est préservée).
Object.defineProperty(window, '_cwOutText', {
  get(){ return _cwPanel('').outText; },
  set(v){ _cwPanel('').outText = v; },
});
Object.defineProperty(window, '_cwOutText2', {
  get(){ return _cwPanel('2').outText; },
  set(v){ _cwPanel('2').outText = v; },
});

// Peuple un <select> d'entrées audio disponibles — générique, réutilisé par
// le décodeur CW ET l'enregistreur audio par QSO (voir plus haut). Les
// libellés des périphériques ne sont visibles qu'APRÈS une autorisation
// micro accordée (contrainte navigateur) : on la demande une fois ici juste
// pour peupler la liste, le flux est refermé aussitôt.
// `alreadyGranted` évite de rouvrir un DEUXIÈME flux micro concurrent quand
// l'appelant a DÉJÀ un flux ouvert avec la permission accordée (cas de
// startAudioRecorder juste après son propre getUserMedia) : la permission et
// les libellés sont globaux au navigateur, pas liés à un flux particulier —
// un second getUserMedia() ici serait un flux superflu, jamais fermé
// explicitement en cas d'erreur avant son propre stop().
async function loadAudioInputDevices(selectId, alreadyGranted){
  const sel = document.getElementById(selectId);
  if(!sel) return false;
  try{
    if(!alreadyGranted){
      const tmp = await navigator.mediaDevices.getUserMedia({audio:true});
      tmp.getTracks().forEach(t=>t.stop());
    }
    const devices = await navigator.mediaDevices.enumerateDevices();
    const inputs = devices.filter(d=>d.kind==='audioinput');
    sel.innerHTML = '<option value="">— périphérique par défaut —</option>'
      + inputs.map(d=>`<option value="${d.deviceId}">${escHtml(d.label||'Entrée audio')}</option>`).join('');
    return true;
  }catch(e){
    sel.innerHTML = '<option value="">Accès micro refusé</option>';
    return false;
  }
}
// Périphériques de SORTIE (émission RTTY/SSTV) : setSinkId (utilisé par
// txAudioPtt() pour router la lecture vers CE périphérique précis) n'existe
// que sur HTMLMediaElement, jamais directement sur AudioContext — d'où le
// test de support explicite, comme dans logx_ft8.html. Les libellés ne sont
// visibles qu'après une autorisation micro (même contrainte navigateur que
// pour les entrées, y compris pour lister des SORTIES) : `alreadyGranted`
// évite de redemander si l'appelant vient déjà d'obtenir la permission via
// loadAudioInputDevices() pour le même panneau.
async function loadAudioOutputDevices(selectId, alreadyGranted){
  const sel = document.getElementById(selectId);
  if(!sel) return false;
  if(!HTMLMediaElement.prototype.setSinkId){
    sel.innerHTML = '<option value="">Choix de sortie non supporté par ce navigateur</option>';
    sel.disabled = true;
    return false;
  }
  try{
    if(!alreadyGranted){
      const tmp = await navigator.mediaDevices.getUserMedia({audio:true});
      tmp.getTracks().forEach(t=>t.stop());
    }
    const devices = await navigator.mediaDevices.enumerateDevices();
    const outputs = devices.filter(d=>d.kind==='audiooutput');
    sel.innerHTML = '<option value="">— périphérique par défaut —</option>'
      + outputs.map(d=>`<option value="${d.deviceId}">${escHtml(d.label||'Sortie audio')}</option>`).join('');
    return true;
  }catch(e){
    sel.innerHTML = '<option value="">Accès micro refusé</option>';
    return false;
  }
}
