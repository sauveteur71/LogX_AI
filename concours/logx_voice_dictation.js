// Saisie vocale mains libres (EXPÉRIMENTALE) : dictée de l'indicatif via
// l'API navigateur Web Speech (SpeechRecognition / webkitSpeechRecognition).
//
// Pas un moteur de transcription maison -- aucun serveur LogX AI n'est
// impliqué, l'audio part directement du navigateur vers les serveurs de
// reconnaissance de Google (Chrome/Edge). Contrairement au TTS (rcSpeak,
// logx_statusbar.js, 100% hors-ligne via speechSynthesis, voix locales du
// navigateur), CETTE fonction nécessite une connexion Internet -- attendu,
// annoncé dans le bandeau non bloquant affiché au premier usage.
//
// Trois limites réelles (pas juste théoriques) à connaître avant de toucher
// à ce fichier -- voir aussi le rapport de faisabilité qui a précédé ce
// chantier :
//  1. CONTEXTE SÉCURISÉ OBLIGATOIRE -- getUserMedia (donc SpeechRecognition)
//     est refusé par Chrome/Edge sur toute origine http:// SAUF
//     http://localhost. LogX AI est pensé pour du multi-poste LAN (accès
//     via http://192.168.x.x:8080 depuis un autre PC) -- sur ces postes-là
//     le bouton peut être visible (SpeechRecognition existe bien en tant que
//     classe navigateur) mais recognition.start() échoue silencieusement à
//     l'usage (catch ci-dessous) : le bandeau affiché au premier clic le dit
//     explicitement pour ne pas laisser croire à un bug.
//  2. DÉPENDANCE RÉSEAU -- aucun moteur de reconnaissance local, contrairement
//     au TTS. Ne fonctionne pas en expédition sans connectivité.
//  3. ALPHABET PHONÉTIQUE NON ENTRAÎNÉ -- ces moteurs grand public sont
//     entraînés à la dictée de langage naturel, pas à l'épellation. La table
//     PHONETIC_MAP ci-dessous convertit les mots de l'alphabet OACI/anglais
//     courant reconnus ("foxtrot", "four", "golf"...) vers leur lettre/
//     chiffre, mais un mot mal reconnu par le moteur (avant toute
//     retraduction) reste possible -- d'où la relecture obligatoire par
//     l'opérateur : le résultat REMPLIT le champ mais NE SOUMET JAMAIS le
//     QSO automatiquement.
//
// Scope MVP volontairement restreint à #inputCall (logx_logbook.html) --
// pas RST/locator au premier lot. Bouton #callMicBtn gate expert-only :
// fonctionnalité avancée non indispensable au chemin critique -- le champ
// texte lui-même reste toujours saisissable au clavier, quel que soit le
// mode simple/expert (masquer ≠ bloquer l'accès, cf. CLAUDE.md).

(function () {

  var SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;

  // Mots reconnus (langue de reconnaissance forcée en 'en-US', voir
  // ensureRecognition() -- l'alphabet OACI est anglais, forcer l'anglais
  // maximise la fiabilité même sur une UI en français) -> caractère.
  // Alphabet OACI complet + chiffres + quelques homophones fréquemment
  // renvoyés par le moteur à la place du mot chiffre attendu.
  var PHONETIC_MAP = {
    alpha: 'A', alfa: 'A', bravo: 'B', charlie: 'C', delta: 'D', echo: 'E',
    foxtrot: 'F', golf: 'G', hotel: 'H', india: 'I', juliet: 'J', juliett: 'J',
    kilo: 'K', lima: 'L', mike: 'M', november: 'N', oscar: 'O', papa: 'P',
    quebec: 'Q', romeo: 'R', sierra: 'S', tango: 'T', uniform: 'U', victor: 'V',
    whiskey: 'W', whisky: 'W', xray: 'X', yankee: 'Y', zulu: 'Z',
    zero: '0', one: '1', two: '2', three: '3', four: '4', five: '5', six: '6',
    seven: '7', eight: '8', nine: '9', niner: '9',
    // homophones fréquents renvoyés à la place du mot chiffre attendu
    for: '4', too: '2', to: '2', ate: '8', won: '1'
  };

  // Transcript en langage naturel (ex. "foxtrot four golf lima delta") ->
  // indicatif compact ("F4GLD"). Un mot non reconnu dans la table est
  // conservé tel quel s'il est déjà un fragment alphanumérique court (le
  // moteur renvoie parfois directement "f4gld" ou une lettre/un chiffre
  // isolé), sinon abandonné -- mieux vaut un trou visible dans le champ
  // qu'un mot parasite injecté dans l'indicatif : l'opérateur relit et
  // corrige de toute façon avant d'enregistrer le QSO.
  function transcriptToCall(transcript) {
    var words = String(transcript || '').toLowerCase().split(/\s+/).filter(Boolean);
    var out = '';
    for (var i = 0; i < words.length; i++) {
      var w = words[i].replace(/[^a-z0-9]/g, '');
      if (!w) continue;
      if (PHONETIC_MAP[w]) { out += PHONETIC_MAP[w]; continue; }
      if (/^[a-z0-9]{1,2}$/.test(w)) { out += w; continue; }             // lettre/chiffre déjà isolé
      if (/^[a-z][0-9]{1,2}[a-z]{1,4}$/i.test(w)) { out += w; continue; } // indicatif entier reconnu comme un seul bloc
      // mot non résolu : abandonné volontairement (voir commentaire ci-dessus)
    }
    return out.toUpperCase();
  }
  window._rcTranscriptToCall = transcriptToCall; // exposé pour vérification manuelle en console

  var recognition = null;
  var listening = false;

  function ensureRecognition() {
    if (recognition) return recognition;
    recognition = new SpeechRecognitionCtor();
    recognition.lang = 'en-US';
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.onresult = function (e) {
      var transcript = (e.results && e.results[0] && e.results[0][0]) ? e.results[0][0].transcript : '';
      var call = transcriptToCall(transcript);
      var input = document.getElementById('inputCall');
      if (input && call) {
        input.value = call;
        if (typeof onCallInput === 'function') onCallInput(); // ré-arme autocomplete/doublon/QRZ -- JAMAIS la soumission du QSO
        input.focus();
      } else if (typeof notify === 'function') {
        notify("⚠️ Indicatif non reconnu — réessaie ou saisis-le au clavier.");
      }
    };
    recognition.onerror = function () {
      if (typeof notify === 'function') {
        notify("❌ Dictée vocale interrompue (micro refusé ou hors-ligne) — saisis l'indicatif au clavier.");
      }
      setListening(false);
    };
    recognition.onend = function () { setListening(false); };
    return recognition;
  }

  function setListening(on) {
    listening = on;
    var btn = document.getElementById('callMicBtn');
    if (btn) btn.classList.toggle('active', on);
  }

  // Bandeau non bloquant affiché une seule fois (localStorage), pas un
  // confirm()/alert() -- cohérent avec le reste du logbook (chantier
  // "dialogues non bloquants"). Rappelle les 3 limites réelles ci-dessus
  // pour qu'un opérateur en LAN ne prenne pas le blocage pour un bug.
  function warnFirstUse() {
    try {
      if (localStorage.getItem('rc_dictation_warned') === '1') return;
      localStorage.setItem('rc_dictation_warned', '1');
    } catch (e) { /* localStorage indisponible : on affiche quand même */ }
    if (typeof notify === 'function') {
      notify("🎙️ Dictée vocale EXPÉRIMENTALE : nécessite Chrome/Edge + connexion Internet, et un accès via localhost ou HTTPS (bloquée en LAN http://). Relis toujours l'indicatif avant d'enregistrer le QSO.", 9000);
    }
  }

  window.toggleCallDictation = function () {
    if (!SpeechRecognitionCtor) return; // filet -- le bouton ne devrait déjà pas être visible (voir initCallDictation)
    if (listening) {
      try { recognition && recognition.stop(); } catch (e) { /* déjà arrêté */ }
      setListening(false);
      return;
    }
    warnFirstUse();
    var rec = ensureRecognition();
    try {
      rec.start();
      setListening(true);
    } catch (e) {
      // start() jette si déjà démarré ou si getUserMedia est refusé
      // (contexte non sécurisé -- accès LAN non-HTTPS, voir commentaire
      // d'en-tête, limite #1).
      if (typeof notify === 'function') {
        notify("❌ Micro indisponible (nécessite localhost ou HTTPS) — saisis l'indicatif au clavier.");
      }
      setListening(false);
    }
  };

  // Appelée depuis le DOMContentLoaded de logx_logbook.js. Même patron que
  // addSpeakIcon()/window.speechSynthesis (logx_carte.html) : pas de bouton
  // mort si l'API n'existe pas (Firefox par défaut, Safari incohérent) --
  // feature-detect pure, aucune dépendance à l'accès réseau ici (ça, c'est
  // vérifié seulement à l'usage, voir toggleCallDictation()).
  window.initCallDictation = function () {
    var btn = document.getElementById('callMicBtn');
    if (!btn) return;
    if (!SpeechRecognitionCtor) {
      btn.style.display = 'none';
      return;
    }
    btn.style.display = '';
  };

})();
