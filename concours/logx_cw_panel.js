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
    this.testDecoder = null;   // décodeur du test rapide de périphérique — voir testDevice()
    this.testTimer = null;
  }

  el(baseId){
    return document.getElementById(baseId + this.suffix);
  }

  async toggle(){
    const panel = this.el('cwPanel');
    panel.classList.toggle('open');
    if(panel.classList.contains('open') && !this.devicesLoaded){
      await this.loadDevices();
      // Test automatique du périphérique DÉJÀ sélectionné, dès la toute
      // première ouverture du panneau -- jusque-là déclenché uniquement par
      // le onchange du sélecteur (voir testDevice() plus bas). Un opérateur
      // qui ouvre le panneau, voit une liste déjà remplie et clique
      // directement sur Démarrer SANS jamais toucher au sélecteur ne
      // recevait donc AUCUNE validation avant de lancer une session : un
      // mauvais périphérique par défaut (micro intégré du PC au lieu de
      // l'interface radio) et un vrai bug de seuil DSP produisaient alors
      // EXACTEMENT le même symptôme (silence total), indiscernables l'un de
      // l'autre. Pas de await : testDevice() est un test de fond de 4s, le
      // panneau doit s'ouvrir immédiatement (même comportement que le
      // onchange existant, qui ne peut de toute façon pas être attendu).
      // testDevice() gère déjà lui-même le cas où un décodage réel tourne.
      this.testDevice();
    }
  }

  async loadDevices(){
    // loadAudioInputDevices() est générique (aussi utilisée par l'enregistreur
    // audio par QSO) — définie dans logx_cw_panel2_audio.js (EV-7 30e
    // increment, ex-logx_logbook.js), chargé APRÈS ce fichier ; référencée
    // ici seulement à l'exécution (pas au chargement du script), l'ordre des
    // <script> n'a donc pas d'importance pour cet appel.
    this.devicesLoaded = await loadAudioInputDevices('cwDevice' + this.suffix);
  }

  setFreq(freq){
    if(this.decoder) this.decoder.setFreq(freq);
  }

  // Vumètre partagé par le décodage réel (toggleDecoder) ET le test rapide de
  // périphérique (testDevice) — même rendu dans les deux cas, l'opérateur voit
  // exactement ce qu'il verra une fois le décodage démarré pour de vrai.
  _updateMeter(mag, threshold){
    const fill = this.el('cwMeterFill');
    const thr = this.el('cwMeterThreshold');
    if(!fill || !thr) return;
    // Échelle visuelle = 3x le seuil courant, pour que le repère de seuil
    // reste toujours visible même quand le bruit de fond fait dériver le
    // seuil adaptatif.
    const scale = threshold * 3 || 0.01;
    fill.style.width = Math.min(100, (mag / scale) * 100) + '%';
    fill.classList.toggle('on', mag > threshold);
    thr.style.left = Math.min(100, (threshold / scale) * 100) + '%';
  }

  toggleDecoder(){
    // Un décodage réel qui démarre prend la main sur le vumètre — annule
    // d'abord tout test de périphérique OU détection de ton en cours (sinon
    // plusieurs flux getUserMedia concurrents sur la même entrée, l'un des
    // navigateurs testés refusant carrément le second).
    this._stopTest();
    this._stopDetect();
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
        out.replaceChildren();
        const words = this.outText.match(/\S+|\s+/g) || [];
        for(const w of words){
          if(/^\s+$/.test(w)){ out.appendChild(document.createTextNode(w)); continue; }
          const span = document.createElement('span');
          span.style.cursor = 'pointer';
          span.textContent = w;
          span.onclick = () => cwToCall(span.textContent);
          out.appendChild(span);
        }
        if(!this.outText) out.textContent = '—';
        out.scrollTop = out.scrollHeight;
      },
      onLevel: (mag, threshold, wpm) => {
        if(wpm) wpmLabel.textContent = wpm + ' MPM';
        this._updateMeter(mag, threshold);
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

  // ─── Test rapide du périphérique choisi (avant de lancer le décodage) ─────
  // Répond à la demande « aider le choix du périphérique par défaut » : la
  // liste de #cwDevice ne donne que des noms système, aucun moyen de savoir
  // LEQUEL reçoit vraiment l'audio radio avant de cliquer Démarrer. Déclenché
  // par onchange sur #cwDevice/#cwDevice2 (voir logx_logbook.html) : ouvre le
  // même pipeline Goertzel que le décodage réel (au ton #cwFreq déjà réglé),
  // pendant quelques secondes, et réutilise le vumètre déjà existant pour un
  // retour immédiat — sans passer par le bouton Démarrer, donc sans polluer
  // la sortie texte ni le compteur MPM d'une vraie session d'écoute.
  async testDevice(){
    this._stopTest();
    this._stopDetect();
    // Un décodage réel est déjà en cours : le vumètre lui appartient déjà, ne
    // pas lui couper l'herbe sous le pied avec un second flux audio.
    if(this.decoder) return;
    const status = this.el('cwDeviceTestStatus');
    const deviceId = this.el('cwDevice').value;
    const freq = parseInt(this.el('cwFreq').value, 10) || 650;
    if(status){ status.textContent = 'Test du périphérique… parle ou émets un ton pendant quelques secondes'; status.className = 'cw-device-test'; }
    let sawSignal = false;
    // Jeton de course : dec.start() est async (getUserMedia attend
    // l'autorisation navigateur), donc un second appel à testDevice()/
    // toggleDecoder() peut très bien démarrer et se terminer AVANT que ce
    // premier appel-ci ne résolve (changement rapide de périphérique dans la
    // liste). Comparer ce jeton à this._testToken au retour de l'attente
    // suffit à détecter qu'on est devenu périmé, sans dépendre de l'état
    // (nullité) d'un flux tiers qui pourrait entre-temps avoir été relancé.
    const token = (this._testToken = (this._testToken || 0) + 1);
    const dec = new CwAudioDecoder({
      freq,
      onChar: () => {},   // le texte décodé pendant le test ne sert à rien, seul le niveau importe
      onLevel: (mag, threshold) => {
        if(mag > threshold) sawSignal = true;
        this._updateMeter(mag, threshold);
      },
    });
    try{
      await dec.start(deviceId || undefined);
    }catch(e){
      if(token === this._testToken && status){ status.textContent = 'Micro indisponible : ' + e.message; status.className = 'cw-device-test bad'; }
      return;
    }
    if(token !== this._testToken || this.decoder){ dec.stop(); return; }
    this.testDecoder = dec;
    this.testTimer = setTimeout(() => {
      this._stopTest();
      if(status){
        status.textContent = sawSignal
          ? 'Signal détecté sur ce périphérique — prêt à démarrer.'
          : 'Aucun signal détecté — vérifie le périphérique et le ton (Hz) choisis.';
        status.className = 'cw-device-test ' + (sawSignal ? 'good' : 'bad');
      }
    }, 4000);
  }

  _stopTest(){
    // Invalide aussi tout appel testDevice() encore en attente de
    // getUserMedia (voir le jeton dans testDevice()) — sans ça, un test
    // lancé juste avant un clic sur Démarrer pourrait résoudre APRÈS coup et
    // prendre la main sur le vumètre d'une vraie session déjà en cours.
    this._testToken = (this._testToken || 0) + 1;
    if(this.testTimer){ clearTimeout(this.testTimer); this.testTimer = null; }
    if(this.testDecoder){ this.testDecoder.stop(); this.testDecoder = null; }
  }

  // ─── Détection automatique du ton CW (retour F4GLD 21/08/2026) ───────────
  // « c'est compliqué pour un novice, on peut pas faciliter ce réglage ? »
  // -- jusqu'ici, #cwFreq exigeait de connaître le réglage CW Pitch du
  // poste. Ici : écoute quelques secondes sur toutes les fréquences
  // plausibles à la fois (CwFreqDetector, logx_cwdecoder.js) et retient
  // celle qui montre un vrai rythme de signal -- remplit #cwFreq tout seul.
  // Nécessite un VRAI signal CW pendant la fenêtre d'écoute : sur du
  // silence ou du bruit pur, dit honnêtement qu'aucun ton net n'a été
  // trouvé plutôt que de deviner.
  async detectFreq(){
    this._stopTest();
    this._stopDetect();
    // Un décodage réel est déjà en cours : ne pas lui couper l'herbe sous
    // le pied avec un second flux audio sur la même entrée (même garde que
    // testDevice()).
    if(this.decoder){ notify(trF('Arrête le décodage avant de lancer la détection.')); return; }
    const status = this.el('cwDeviceTestStatus');
    const btn = this.el('cwDetectBtn');
    const deviceId = this.el('cwDevice').value;
    if(status){ status.textContent = 'Détection du ton CW… une VRAIE station doit transmettre pendant ces quelques secondes.'; status.className = 'cw-device-test'; }
    if(btn){ btn.disabled = true; }
    const detector = new CwFreqDetector();
    // Même mécanique de jeton de course que testDevice() ci-dessus : start()
    // est async (attente getUserMedia), un second appel peut résoudre avant.
    const token = (this._detectToken = (this._detectToken || 0) + 1);
    const dec = new CwAudioDecoder({
      onBlock: (samples, sampleRate) => detector.feed(samples, sampleRate),
    });
    try{
      await dec.start(deviceId || undefined);
    }catch(e){
      if(token === this._detectToken){
        if(status){ status.textContent = 'Micro indisponible : ' + e.message; status.className = 'cw-device-test bad'; }
        if(btn) btn.disabled = false;
      }
      return;
    }
    if(token !== this._detectToken || this.decoder){ dec.stop(); return; }
    this.detectDecoder = dec;
    this.detectTimer = setTimeout(() => {
      this._stopDetect();
      if(btn) btn.disabled = false;
      const found = detector.best();
      if(found){
        const freqInput = this.el('cwFreq');
        if(freqInput) freqInput.value = found;
        this.setFreq(found);
        if(status){ status.textContent = `Ton détecté : ${found} Hz — champ mis à jour.`; status.className = 'cw-device-test good'; }
        notify(trF('✅ Ton CW détecté : {hz} Hz', {hz: found}));
      }else if(status){
        status.textContent = "Aucun ton CW net détecté — vérifie qu'une station transmet vraiment, puis réessaie.";
        status.className = 'cw-device-test bad';
      }
    }, 4000);
  }

  _stopDetect(){
    this._detectToken = (this._detectToken || 0) + 1;
    if(this.detectTimer){ clearTimeout(this.detectTimer); this.detectTimer = null; }
    if(this.detectDecoder){ this.detectDecoder.stop(); this.detectDecoder = null; }
  }
}
