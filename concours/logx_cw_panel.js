// ─── PANNEAU DÉCODEUR CW — composant réutilisable (EV-7, docs/LogX_AI_PRD.md) ─
// Premier pilote du refactor EV-7 : avant ce fichier, logx_logbook.js
// dupliquait intégralement (suffixe "2", même convention que cat_port/
// cat2_port) l'état et la logique du panneau décodeur CW pour la radio 2
// (SO2R Phase 2) — 6 variables globales et 6 fonctions quasi identiques,
// dupliquées ligne à ligne. CwPanel encapsule cette logique UNE fois,
// paramétrée par un suffixe d'id DOM ('' pour la radio 1, '2' pour la
// radio 2) — exactement le "composant panneau unifié" qu'EV-7 demande.
//
// Ce que CwPanel NE fait PAS : le pipeline DSP (Goertzel, seuil adaptatif,
// classification Morse) reste entièrement dans CwAudioDecoder
// (logx_cwdecoder.js), déjà correctement séparé de la présentation avant ce
// chantier — CwPanel ne fait que le BRANCHEMENT à l'UI (sélecteur de
// périphérique, bouton démarrer/arrêter, vumètre, sortie texte), comme le
// faisaient déjà les fonctions qu'il remplace.
//
// Chargé en <script> classique (pas de module ES) : ce projet n'utilise
// aucun bundler, tout le JS partage la même portée globale (voir
// logx_cwdecoder.js, même convention). Doit être chargé APRÈS
// logx_cwdecoder.js (dépendance sur CwAudioDecoder) et AVANT logx_logbook.js
// (qui instancie CwPanel et expose les wrappers globaux historiques
// toggleCwPanel()/toggleCwDecoder()/clearCwOutput() etc., conservés tels
// quels pour ne rien changer côté HTML ni côté tests existants qui les
// appellent par leur nom).

class CwPanel {
  constructor(suffix){
    this.suffix = suffix;   // '' radio 1, '2' radio 2
    this.decoder = null;
    this.devicesLoaded = false;
    this.outText = '';   // texte décodé cumulé (survit aux re-rendus) — voir toggleDecoder()/clearOutput()
  }

  el(baseId){
    return document.getElementById(baseId + this.suffix);
  }

  async toggle(){
    const panel = this.el('cwPanel');
    panel.classList.toggle('open');
    if(panel.classList.contains('open') && !this.devicesLoaded) await this.loadDevices();
  }

  async loadDevices(){
    // loadAudioInputDevices() est générique (aussi utilisée par l'enregistreur
    // audio par QSO) — définie dans logx_logbook.js, chargé APRÈS ce fichier ;
    // référencée ici seulement à l'exécution (pas au chargement du script),
    // l'ordre des <script> n'a donc pas d'importance pour cet appel.
    this.devicesLoaded = await loadAudioInputDevices('cwDevice' + this.suffix);
  }

  setFreq(freq){
    if(this.decoder) this.decoder.setFreq(freq);
  }

  toggleDecoder(){
    const btn = this.el('cwStartBtn');
    if(this.decoder){
      this.decoder.stop();
      this.decoder = null;
      btn.textContent = '▶ Démarrer';
      btn.classList.remove('active');
      return;
    }
    const deviceId = this.el('cwDevice').value;
    const freq = parseInt(this.el('cwFreq').value, 10) || 650;
    const out = this.el('cwOutput');
    const wpmLabel = this.el('cwWpmLabel');
    this.outText = '';
    const dec = new CwAudioDecoder({
      freq,
      onChar: ch => {
        this.outText = (this.outText + ch).slice(-400);   // borne la mémoire sur une session longue
        // Mots cliquables : reprend le comportement de l'ancien panneau compact
        // (voir cwToCall) — clique un mot décodé pour le mettre dans l'indicatif.
        out.innerHTML = this.outText.replace(/(\S+)/g, '<span style="cursor:pointer" onclick="cwToCall(this.textContent)">$1</span>') || '—';
        out.scrollTop = out.scrollHeight;
      },
      onLevel: (mag, threshold, wpm) => {
        if(wpm) wpmLabel.textContent = wpm + ' MPM';
        // Vumètre de diagnostic : échelle visuelle = 3x le seuil courant, pour
        // que le repère de seuil reste toujours visible même quand le bruit de
        // fond fait dériver le seuil adaptatif.
        const fill = this.el('cwMeterFill');
        const thr = this.el('cwMeterThreshold');
        if(fill && thr){
          const scale = threshold * 3 || 0.01;
          fill.style.width = Math.min(100, (mag / scale) * 100) + '%';
          fill.classList.toggle('on', mag > threshold);
          thr.style.left = Math.min(100, (threshold / scale) * 100) + '%';
        }
      },
    });
    dec.start(deviceId || undefined).then(() => {
      this.decoder = dec;
      btn.textContent = '■ Arrêter';
      btn.classList.add('active');
    }).catch(e => {
      notify(trF('❌ Micro indisponible : {err}', {err: e.message}));
    });
  }

  // Vide la sortie décodée — remet aussi outText à zéro (sinon le prochain
  // caractère décodé re-rendrait tout l'ancien texte accumulé par-dessus le
  // champ visuellement vidé, puisque le texte cumulé vit dans cette propriété,
  // pas dans le DOM).
  clearOutput(){
    this.outText = '';
    const out = this.el('cwOutput');
    if(out) out.textContent = '';
  }
}
