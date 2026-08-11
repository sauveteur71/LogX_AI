// EV-7 phase 2, 15e increment (docs/LogX_AI_PRD.md) -- panneau DECODEUR +
// EMISSION RTTY extrait tel quel de logx_logbook.js (extraction MECANIQUE).
// Charge en <script> classique dans logx_logbook.html, AVANT logx_logbook.js
// (portee globale partagee) -- juste apres logx_rttydecoder.js (deja separe,
// pipeline DSP RttyAudioDecoder/rttyEncodeSamples, uniquement reference a
// l'interieur de corps de fonction ici, jamais au chargement).
//
// 6 variables d'etat privees au bloc (_rttyDecoder, _rttyTexte,
// _rttyDevicesLoaded, RTTY_TX_MACROS, _rttyTxArmed, _rttyOutDeviceLoaded) --
// grep exhaustif sur tout le depot : aucune n'est lue/ecrite ailleurs, SAUF
// _rttyDevicesLoaded/_rttyOutDeviceLoaded qui sont aussi ECRITES depuis
// updateKeyerPanels() (reste dans logx_logbook.js, cf. plus bas) -- ecriture
// via portee globale partagee, pas un import, aucun risque d'ordre puisque
// updateKeyerPanels() n'est appelee qu'au runtime (poll d'etat radio),
// jamais au chargement des <script>.
//
// 7 points d'entree HTML (onclick/oninput/onchange dans logx_logbook.html) :
// toggleRttyPanel, rttyAppliquerTons (x2 : rttyMark/rttyShift), toggleRttyDecoder,
// rttyClicTexte, clearRttyOutput, rttyOnArmChange, rttyEnvoyerLibre.
//
// Fonctions internes au bloc (jamais cablees en HTML, seulement appelees
// depuis d'autres fonctions du meme bloc) : rttyTons, rttyRender,
// rttyEstIndicatif (lu directement par tests/test_rtty_decodeur.py, motif
// _lire_tout() applique cote test), renderRttyMacroBtns (appelee depuis
// updateKeyerPanels(), hors du bloc), rttyEnvoyerTexte.

// ─── DÉCODEUR RTTY ───────────────────────────────────────────────────────────
let _rttyDecoder = null;
let _rttyTexte = '';
let _rttyDevicesLoaded = false;

// Corrigé (11/08/2026, retour F4GLD "rien ne se passe") : l'ancienne version
// posait un style inline sur #rttyBody, toujours battu par la règle CSS
// .cw-body{display:none} -- le panneau ne s'ouvrait donc jamais. Même
// mécanique que toggleSstvPanel() (logx_sstv_panel.js) : #rttyDecoder porte
// désormais la classe .cw-panel (voir logx_logbook.html), donc
// .cw-panel.open .cw-body{display:flex} prend le relais correctement.
// _reserveBottomSpace nécessaire ici pour la même raison que pour SSTV :
// #rttyDecoder est en position:fixed (hors du flux de .keyer-dock), il doit
// donc réserver sa place plutôt que de recouvrir la saisie en dessous.
function toggleRttyPanel(){
  const panel = document.getElementById('rttyDecoder');
  if(!panel) return;
  panel.classList.toggle('open');
  _reserveBottomSpace(panel, document.querySelector('.saisie-secondary'));
}

function rttyTons(){
  const mark = parseInt(document.getElementById('rttyMark')?.value, 10) || 2125;
  const shift = parseInt(document.getElementById('rttyShift')?.value, 10) || 170;
  return {mark, space: mark + shift};
}

function rttyAppliquerTons(){
  const t = rttyTons();
  if(_rttyDecoder) _rttyDecoder.setShift(t.mark, t.space);
}

async function toggleRttyDecoder(){
  const btn = document.getElementById('rttyStartBtn');
  const etat = document.getElementById('rttyStatus');
  if(_rttyDecoder){
    _rttyDecoder.stop();
    _rttyDecoder = null;
    if(btn) btn.textContent = '▶ Démarrer';
    if(etat) etat.textContent = '';
    return;
  }
  const t = rttyTons();
  const out = document.getElementById('rttyOutput');
  _rttyDecoder = new RttyAudioDecoder({
    mark: t.mark, space: t.space,
    onChar: c => {
      // Le texte accumulé vit dans _rttyTexte et non dans le DOM : il est
      // re-rendu en jetons cliquables à chaque caractère. On le borne pour
      // qu'une nuit de réception ne fasse pas gonfler la page indéfiniment.
      _rttyTexte += c;
      if(_rttyTexte.length > 4000) _rttyTexte = _rttyTexte.slice(-3000);
      rttyRender(_rttyTexte);
    },
  });
  try{
    await _rttyDecoder.start(document.getElementById('rttyDevice')?.value || '');
    if(btn) btn.textContent = '■ Arrêter';
    if(etat) etat.textContent = t.mark + '/' + t.space + ' Hz';
  }catch(e){
    _rttyDecoder = null;
    notify(trF('❌ Micro indisponible : {err}', {err: e.message}));
  }
}

function clearRttyOutput(){
  _rttyTexte = '';
  rttyRender('');
}

// Un jeton ressemble-t-il à un indicatif ? Lettres et chiffres, au moins un
// chiffre, éventuellement barré (/P, /MM). Le filtre évite de proposer « CQ »,
// « TEST » ou « DE » comme correspondants.
function rttyEstIndicatif(mot){
  const propre = String(mot || '').toUpperCase().replace(/[^A-Z0-9/]/g, '');
  // Au moins un chiffre ET au moins une lettre. Sans la lettre, le report
  // « 599 » et le numéro de série « 001 » — qui sont dans TOUS les échanges
  // RTTY — devenaient cliquables et proposaient d'aller dans le champ
  // indicatif : un clic de travers et on loggue « 599 ».
  return (propre.length >= 3 && /[0-9]/.test(propre) && /[A-Z]/.test(propre))
         ? propre : '';
}

// Le texte décodé est rendu en JETONS : chaque indicatif devient un élément
// cliquable à part entière.
//
// La première version lisait window.getSelection() et, à défaut, la position
// du curseur. Les deux se sont révélées fragiles : dans la page réelle, une
// sélection posée par programme rend une chaîne VIDE, et la position du
// curseur demande des coordonnées d'écran. Un élément par mot ne dépend
// d'aucune de ces API — le clic arrive directement sur sa cible.
function rttyRender(texte){
  const out = document.getElementById('rttyOutput');
  if(!out) return;
  const frag = document.createDocumentFragment();
  // On coupe en gardant les séparateurs, pour ne pas écraser la mise en page
  // du texte reçu (retours ligne du correspondant compris).
  for(const jeton of String(texte).split(/(\s+)/)){
    const call = rttyEstIndicatif(jeton);
    if(call){
      const el = document.createElement('span');
      el.className = 'rtty-call';
      el.dataset.call = call;
      el.textContent = jeton;
      el.title = 'Cliquer pour mettre ' + call + ' dans la saisie';
      frag.appendChild(el);
    } else {
      frag.appendChild(document.createTextNode(jeton));
    }
  }
  out.innerHTML = '';
  out.appendChild(frag);
  out.scrollTop = out.scrollHeight;
}

// Clic sur un indicatif décodé : il part dans la saisie. C'est CE geste qui
// fait la vitesse en RTTY — recopier à la main un indicatif déjà affiché est
// du temps perdu, et une source de faute de frappe.
function rttyClicTexte(ev){
  const cible = ev.target && ev.target.closest ? ev.target.closest('.rtty-call') : null;
  const call = cible && cible.dataset ? cible.dataset.call : '';
  if(!call) return;
  const inp = document.getElementById('inputCall');
  if(inp){
    inp.value = call;
    inp.focus();
    inp.dispatchEvent(new Event('input', {bubbles: true}));
  }
}

// ─── ÉMISSION RTTY ───────────────────────────────────────────────────────────
// Macros fixes (pas d'éditeur comme les macros CW F1-F8 dans cette première
// version) — {CALL}/{LOC}/{NR} réutilisent expandMacro() telle quelle, MÊME
// convention que les macros CW ({CALL} = TA propre station, pas le
// correspondant — voir le commentaire au-dessus de DEFAULT_MACROS,
// désormais dans logx_macros.js, EV-7 32e increment — motif
// optionnel->optionnel, ce fichier (15e increment) charge AVANT
// logx_macros.js (32e), gardé par typeof plus bas pour rester défensif).
const RTTY_TX_MACROS = [
  {key:'R1', label:'CQ',      text:'CQ TEST {CALL} {CALL} TEST'},
  {key:'R2', label:'ÉCHANGE', text:'599 {NR}'},
  {key:'R3', label:'TU',      text:'TU {CALL} TEST'},
  {key:'R4', label:'AGN?',    text:'AGN?'},
];
let _rttyTxArmed = false;
let _rttyOutDeviceLoaded = false;

function rttyOnArmChange(){
  _rttyTxArmed = document.getElementById('rttyArmTx').checked;
  document.getElementById('rttySendBtn').disabled = !_rttyTxArmed;
}

function renderRttyMacroBtns(){
  const btns = document.getElementById('rttyMacroBtns');
  if(!btns) return;
  btns.innerHTML = '';
  const expand = typeof expandMacro === 'function' ? expandMacro : (t => t);
  RTTY_TX_MACROS.forEach(m => {
    const btn = document.createElement('button');
    btn.className = 'macro-btn';
    btn.title = expand(m.text);
    btn.innerHTML = `<span class="mk">${m.key}</span><span class="mt">${m.label}</span>`;
    btn.onclick = () => rttyEnvoyerTexte(expand(m.text));
    btns.appendChild(btn);
  });
}

async function rttyEnvoyerLibre(){
  const champ = document.getElementById('rttyTxText');
  const texte = champ.value.trim();
  if(!texte) return;
  await rttyEnvoyerTexte(texte);
}

// `texte` arrive déjà développé (macro ou champ libre) — un seul point
// d'émission pour les deux chemins, comme envoyerMessage() dans logx_ft8.html.
async function rttyEnvoyerTexte(texte){
  if(!_rttyTxArmed || !texte) return;
  const statut = document.getElementById('rttyTxStatus');
  const sendBtn = document.getElementById('rttySendBtn');
  sendBtn.disabled = true;
  if(statut){ statut.textContent = '🔊 ' + texte; statut.style.color = 'var(--accent2)'; }
  const t = rttyTons();
  const sampleRate = 44100;
  const wave = rttyEncodeSamples(texte, {sampleRate, mark: t.mark, space: t.space});
  const outId = document.getElementById('rttyOutDevice')?.value || '';
  const res = await txAudioPtt(wave, sampleRate, outId);
  sendBtn.disabled = !_rttyTxArmed;
  if(statut){
    statut.textContent = res.ok ? ('Émis : ' + texte) : ('❌ ' + res.error);
    statut.style.color = res.ok ? 'var(--muted)' : 'var(--red)';
  }
}
