// EV-7 phase 2, 14e increment (docs/LogX_AI_PRD.md) -- panneau DECODEUR
// SSTV extrait tel quel de logx_logbook.js (extraction MECANIQUE, pas le
// motif bus d'evenements du pilote SCAN QSL PAPIER -- voir logx_scan_qsl.js).
// Analyse prealable (Workflow, cartographie + evaluation de 64 blocs) : bloc
// AUTONOME -- 7 variables d'etat 100% privees (_sstvDecoder/_sstvDevicesLoaded/
// _sstvOutDeviceLoaded/_sstvLignesRecues/_sstvTxArmed/_sstvTxPixels/
// _sstvModeSelectRempli), 7 points d'entree externes (onclick/onchange dans
// logx_logbook.html, inchanges), aucun autre fichier n'appelle une de ses
// fonctions. Le pipeline DSP (SstvAudioDecoder/SSTV_MODES_PAR_NOM/
// sstvEncodeSamples) reste dans logx_sstvdecoder.js, deja un fichier separe
// -- ce module-ci n'est que la glue UI. updateKeyerPanels() (coordinateur
// CW/RTTY/SSTV/voix, reste dans logx_logbook.js) pilote #sstvPanel par un
// couplage DOM pur (getElementById + style.display), jamais un appel a une
// fonction de ce bloc -- pas de dependance a l'envers.
//
// Aucun test ne fige le CODE SOURCE de ce bloc (verifie par grep sur tests/) :
// seule adaptation, l'ajout a JS_EXTRAITS_EV7 (test_logbook_menu_debut_fin.py),
// par convention, pas par necessite.

// ─── DÉCODEUR SSTV ───────────────────────────────────────────────────────────
// Panneau flottant à droite du panneau CW — pipeline DSP dans
// logx_sstvdecoder.js, ce fichier ne fait que le brancher à l'UI (device
// picker, bouton start/stop, canvas construit ligne à ligne).
let _sstvDecoder = null;
// Garde anti-ré-entrance du démarrage : _sstvDecoder n'est assigné qu'après le
// succès de start(), donc pendant l'invite de permission un 2e clic ne tombe
// pas dans la branche STOP mais construirait un second décodeur (le premier
// pipeline fuit). Même garde que toggleRx FT8 / toggleRttyDecoder.
let _sstvDecoderDemarrageEnCours = false;
let _sstvDevicesLoaded = false;
let _sstvOutDeviceLoaded = false;
let _sstvLignesRecues = 0;   // pour savoir si le canvas contient quelque chose à sauver

async function toggleSstvPanel(){
  const panel = document.getElementById('sstvPanel');
  panel.classList.toggle('open');
  // Même mécanique que le panneau CW : réserver la place en bas de la zone
  // qui scrolle vraiment (voir le commentaire de _reserveBottomSpace).
  _reserveBottomSpace(panel, document.querySelector('.saisie-secondary'));
  if(panel.classList.contains('open')){
    remplirSstvModeSelect();
    if(!_sstvDevicesLoaded) _sstvDevicesLoaded = await loadAudioInputDevices('sstvDevice');
    if(!_sstvOutDeviceLoaded) _sstvOutDeviceLoaded = await loadAudioOutputDevices('sstvOutDevice', true);
  }
}

async function toggleSstvDecoder(){
  const btn = document.getElementById('sstvStartBtn');
  const statut = document.getElementById('sstvStatus');
  const info = document.getElementById('sstvInfo');
  if(_sstvDecoder){
    _sstvDecoder.stop();
    _sstvDecoder = null;
    if(btn){ btn.textContent = '▶ Démarrer'; btn.classList.remove('active'); }
    if(statut) statut.textContent = '';
    if(info) info.textContent = 'Arrêté.';
    return;
  }
  if(_sstvDecoderDemarrageEnCours) return;   // ignore un 2e clic tant que le démarrage n'est pas résolu
  _sstvDecoderDemarrageEnCours = true;
  const canvas = document.getElementById('sstvCanvas');
  const ctx2d = canvas.getContext('2d');
  const dec = new SstvAudioDecoder({
    onDebutImage: mode => {
      // Le canvas prend les dimensions NATIVES du mode (jusqu'à 800×616 en
      // PD290) — c'est le CSS qui le remet à la largeur du panneau. Redonner
      // width/height efface aussi l'image précédente, c'est voulu : une
      // nouvelle réception commence.
      canvas.width = mode.largeur;
      canvas.height = mode.hauteur;
      ctx2d.fillStyle = '#000';
      ctx2d.fillRect(0, 0, canvas.width, canvas.height);
      _sstvLignesRecues = 0;
      if(statut) statut.textContent = mode.nom;
    },
    onLigne: (y, rangee, mode) => {
      ctx2d.putImageData(new ImageData(new Uint8ClampedArray(rangee), mode.largeur, 1), 0, y);
      _sstvLignesRecues++;
      if(statut && _sstvLignesRecues % 8 === 0){
        statut.textContent = mode.nom + ' · ' + Math.round(_sstvLignesRecues / mode.hauteur * 100) + '%';
      }
    },
    onFinImage: mode => {
      if(statut) statut.textContent = mode.nom + ' ✓';
      notify(trF('🖼 Image SSTV reçue ({mode})', {mode: mode.nom}));
    },
    onEtat: txt => { if(info) info.textContent = txt; },
  });
  try{
    await dec.start(document.getElementById('sstvDevice')?.value || '');
    _sstvDecoder = dec;
    if(btn){ btn.textContent = '■ Arrêter'; btn.classList.add('active'); }
    if(info) info.textContent = 'À l\'écoute — en attente d\'un en-tête VIS…';
  }catch(e){
    try{ dec.stop(); }catch(_){}   // libère un flux micro éventuellement à moitié acquis (stop() est null-safe)
    notify(trF('❌ Micro indisponible : {err}', {err: e.message}));
  }finally{
    _sstvDecoderDemarrageEnCours = false;
  }
}

function sstvSauverImage(){
  if(!_sstvLignesRecues){
    notify(trF('🖼 Aucune image SSTV à sauvegarder pour l\'instant'));
    return;
  }
  const canvas = document.getElementById('sstvCanvas');
  canvas.toBlob(blob => {
    if(!blob) return;
    // Horodatage dans le nom : plusieurs images se succèdent pendant un
    // dimanche SSTV, « sstv.png » les écraserait l'une l'autre.
    const d = new Date();
    const pad = n => String(n).padStart(2, '0');
    const nom = 'sstv_' + d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate())
              + '_' + pad(d.getHours()) + pad(d.getMinutes()) + pad(d.getSeconds()) + '.png';
    const a = document.createElement('a');
    const url = URL.createObjectURL(blob);
    a.href = url;
    a.download = nom;
    a.click();
    // Revoke DIFFÉRÉ : un revoke immédiat annulait le téléchargement PNG avant
    // que le navigateur n'ait lu le blob (audit).
    setTimeout(() => URL.revokeObjectURL(url), 40000);
  }, 'image/png');
}

function sstvEffacerImage(){
  const canvas = document.getElementById('sstvCanvas');
  const ctx2d = canvas.getContext('2d');
  ctx2d.fillStyle = '#000';
  ctx2d.fillRect(0, 0, canvas.width, canvas.height);
  _sstvLignesRecues = 0;
  const statut = document.getElementById('sstvStatus');
  if(statut) statut.textContent = '';
  const info = document.getElementById('sstvInfo');
  if(info) info.textContent = _sstvDecoder ? 'À l\'écoute — en attente d\'un en-tête VIS…' : 'En attente de signal…';
}

// ─── ÉMISSION SSTV ───────────────────────────────────────────────────────────
// SSTV_MODES_PAR_NOM vient de logx_sstvdecoder.js (chargé avant ce fichier,
// voir les <script src> de logx_logbook.html) — global navigateur, pas un
// import : peuplé une fois au premier passage dans le mode SSTV.
let _sstvTxArmed = false;
let _sstvTxPixels = null;     // RGB entrelacé (3 octets/pixel), dimensions EXACTES du mode choisi
let _sstvModeSelectRempli = false;

function remplirSstvModeSelect(){
  if(_sstvModeSelectRempli) return;
  const sel = document.getElementById('sstvTxMode');
  if(!sel || typeof SSTV_MODES_PAR_NOM === 'undefined') return;
  sel.innerHTML = Object.keys(SSTV_MODES_PAR_NOM).map(cle => {
    const m = SSTV_MODES_PAR_NOM[cle];
    return `<option value="${cle}">${escHtml(m.nom)} (${m.largeur}×${m.hauteur})</option>`;
  }).join('');
  _sstvModeSelectRempli = true;
}

function sstvOnArmChange(){
  _sstvTxArmed = document.getElementById('sstvArmTx').checked;
  document.getElementById('sstvSendBtn').disabled = !_sstvTxArmed || !_sstvTxPixels;
}

// Charge le fichier choisi, l'étire aux dimensions EXACTES du mode (pas de
// recadrage manuel dans cette version — comportement par défaut des
// logiciels SSTV quand la source n'a pas déjà le bon ratio), et prépare le
// tableau de pixels RGB attendu par sstvEncodeSamples().
function sstvChargerImage(ev){
  const fichier = ev.target.files && ev.target.files[0];
  const statut = document.getElementById('sstvTxStatus');
  if(!fichier) return;
  const modeCle = document.getElementById('sstvTxMode').value;
  const mode = SSTV_MODES_PAR_NOM[modeCle];
  if(!mode) return;
  const img = new Image();
  const urlObjet = URL.createObjectURL(fichier);
  img.onload = () => {
    const canvas = document.getElementById('sstvTxCanvas');
    canvas.width = mode.largeur;
    canvas.height = mode.hauteur;
    const ctx2d = canvas.getContext('2d');
    ctx2d.drawImage(img, 0, 0, mode.largeur, mode.hauteur);
    const donnees = ctx2d.getImageData(0, 0, mode.largeur, mode.hauteur).data;
    const pixels = new Uint8Array(mode.largeur * mode.hauteur * 3);
    for(let i = 0, j = 0; i < donnees.length; i += 4, j += 3){
      pixels[j] = donnees[i]; pixels[j + 1] = donnees[i + 1]; pixels[j + 2] = donnees[i + 2];
    }
    _sstvTxPixels = pixels;
    canvas.style.display = '';
    URL.revokeObjectURL(urlObjet);
    if(statut){ statut.textContent = 'Image prête (' + mode.nom + ', ' + mode.largeur + '×' + mode.hauteur + ')'; statut.style.color = 'var(--muted)'; }
    document.getElementById('sstvSendBtn').disabled = !_sstvTxArmed;
  };
  img.onerror = () => {
    URL.revokeObjectURL(urlObjet);
    _sstvTxPixels = null;
    document.getElementById('sstvSendBtn').disabled = true;
    if(statut){ statut.textContent = '❌ Image illisible'; statut.style.color = 'var(--red)'; }
  };
  img.src = urlObjet;
}

// L'encodeur produit la forme d'onde COMPLÈTE d'un coup (pas de flux) — la
// progression affichée est donc calculée sur le TEMPS ÉCOULÉ vs la durée
// totale connue à l'avance (wave.length/sampleRate), pas sur un vrai suivi
// d'avancement de l'encodage lui-même.
async function sstvEnvoyerImage(){
  if(!_sstvTxArmed || !_sstvTxPixels) return;
  const modeCle = document.getElementById('sstvTxMode').value;
  const mode = SSTV_MODES_PAR_NOM[modeCle];
  if(!mode) return;
  const statut = document.getElementById('sstvTxStatus');
  const sendBtn = document.getElementById('sstvSendBtn');
  sendBtn.disabled = true;
  const sampleRate = 44100;
  const wave = sstvEncodeSamples({mode: modeCle, pixels: _sstvTxPixels, sampleRate});
  const dureeS = wave.length / sampleRate;
  const debut = Date.now();
  const minuteur = setInterval(() => {
    if(!statut) return;
    const ecoule = (Date.now() - debut) / 1000;
    const pct = Math.min(100, Math.round(ecoule / dureeS * 100));
    statut.textContent = mode.nom + ' — émission ' + pct + '% (' + Math.round(ecoule) + 's / ' + Math.round(dureeS) + 's)';
  }, 1000);
  const outId = document.getElementById('sstvOutDevice')?.value || '';
  const res = await txAudioPtt(wave, sampleRate, outId);
  clearInterval(minuteur);
  sendBtn.disabled = !_sstvTxArmed;
  if(statut){
    statut.textContent = res.ok ? (mode.nom + ' émis (' + Math.round(dureeS) + 's)') : ('❌ ' + res.error);
    statut.style.color = res.ok ? 'var(--muted)' : 'var(--red)';
  }
}
