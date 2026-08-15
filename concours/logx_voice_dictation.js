// Saisie vocale mains libres (EXPÉRIMENTALE) via l'API navigateur Web Speech
// (SpeechRecognition / webkitSpeechRecognition).
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
//  3. ALPHABET PHONÉTIQUE NON ENTRAÎNÉ (dictée d'indicatif uniquement) -- ces
//     moteurs grand public sont entraînés à la dictée de langage naturel, pas
//     à l'épellation. La table PHONETIC_MAP ci-dessous convertit les mots de
//     l'alphabet OACI/anglais courant reconnus ("foxtrot", "four", "golf"...)
//     vers leur lettre/chiffre, mais un mot mal reconnu par le moteur (avant
//     toute retraduction) reste possible -- d'où la relecture obligatoire par
//     l'opérateur : le résultat REMPLIT le champ mais NE SOUMET JAMAIS
//     automatiquement (QSO comme message de chat).
//
// Deux instances construites sur la même fabrique _createVoiceDictation() :
//  - dictée de l'INDICATIF (#inputCall, logx_logbook.html) -- scope MVP
//    d'origine, reconnaissance forcée en anglais (alphabet OACI), transcript
//    compacté par transcriptToCall(). API historique conservée à l'identique
//    (window.initCallDictation/window.toggleCallDictation) pour ne rien
//    casser côté logbook.
//  - dictée du CHAT (#userInput, logx_carte.html) -- ajoutée le 15/08/2026
//    (tâche #92bis, dernier point du backlog CARTE IA) : transcript brut
//    (langage naturel, pas d'épellation), langue de reconnaissance alignée
//    sur la langue d'interface courante (rc_lang), jamais d'envoi auto du
//    message -- même principe que l'indicatif, la dictée REMPLIT le champ,
//    l'opérateur relit et valide lui-même (Entrée ou clic ▶).
//
// Bouton micro gate expert-only dans les deux cas : fonctionnalité avancée
// non indispensable au chemin critique -- le champ texte lui-même reste
// toujours saisissable au clavier, quel que soit le mode simple/expert
// (masquer ≠ bloquer l'accès, cf. CLAUDE.md).

(function () {

  var SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;

  // Mots reconnus (langue de reconnaissance forcée en 'en-US' pour la dictée
  // d'indicatif, voir _createVoiceDictation() -- l'alphabet OACI est anglais,
  // forcer l'anglais maximise la fiabilité même sur une UI en français) ->
  // caractère. Alphabet OACI complet + chiffres + quelques homophones
  // fréquemment renvoyés par le moteur à la place du mot chiffre attendu.
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

  // Langue de reconnaissance pour la dictée en langage naturel (chat) --
  // alignée sur la langue d'interface courante (rc_lang, posée par
  // logx_i18n.js), repli fr-FR si absente/inconnue. Sans lien avec la
  // dictée d'indicatif ci-dessus, qui reste forcée en anglais (alphabet
  // OACI, indépendant de la langue d'interface).
  var SPEECH_LANG_MAP = {
    fr: 'fr-FR', en: 'en-US', de: 'de-DE', es: 'es-ES', it: 'it-IT',
    pt: 'pt-PT', nl: 'nl-NL', pl: 'pl-PL'
  };
  function naturalSpeechLang() {
    var lang = 'fr';
    try { lang = localStorage.getItem('rc_lang') || 'fr'; } catch (e) { /* localStorage indisponible */ }
    return SPEECH_LANG_MAP[lang] || 'fr-FR';
  }

  // Fabrique d'un contrôleur de dictée indépendant, un par champ cible.
  // cfg = {
  //   inputId,          id du champ à remplir (texte brut ou transformé)
  //   micBtnId,         id du bouton micro associé
  //   lang,             code langue SpeechRecognition (ex. 'en-US') ou
  //                     fonction () -> code langue, évaluée à chaque écoute
  //                     (permet de suivre un changement de langue d'interface
  //                     entre deux dictées sans recréer le contrôleur)
  //   transform,        (transcript) -> valeur posée dans le champ ; par
  //                     défaut identité (transcript brut, pour le chat)
  //   onFilled,         (input) -> void, appelée après avoir posé la valeur
  //                     (ex. ré-armer un autocomplete, redimensionner une
  //                     textarea) -- jamais la soumission automatique
  //   notify,           (message) -> void, bandeau non bloquant
  //   warnedKey,        clé localStorage du bandeau "vu une fois"
  //   warnMessage,      texte du bandeau pédagogique au premier usage
  //   emptyResultMessage, errorMessage, startErrorMessage -- messages des
  //     3 cas d'échec (transcript vide/non exploitable, erreur pendant
  //     l'écoute, échec au démarrage -- contexte non sécurisé notamment)
  // }
  function _createVoiceDictation(cfg) {
    var recognition = null;
    var listening = false;

    function notify(msg) {
      if (typeof cfg.notify === 'function') cfg.notify(msg);
    }

    function ensureRecognition() {
      if (recognition) return recognition;
      recognition = new SpeechRecognitionCtor();
      recognition.lang = typeof cfg.lang === 'function' ? cfg.lang() : (cfg.lang || 'en-US');
      recognition.continuous = false;
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;
      recognition.onresult = function (e) {
        var transcript = (e.results && e.results[0] && e.results[0][0]) ? e.results[0][0].transcript : '';
        var value = (cfg.transform ? cfg.transform(transcript) : transcript || '').trim();
        var input = document.getElementById(cfg.inputId);
        if (input && value) {
          input.value = value;
          if (typeof cfg.onFilled === 'function') cfg.onFilled(input);
          input.focus();
        } else {
          notify(cfg.emptyResultMessage);
        }
      };
      recognition.onerror = function () {
        notify(cfg.errorMessage);
        setListening(false);
      };
      recognition.onend = function () { setListening(false); };
      return recognition;
    }

    function setListening(on) {
      listening = on;
      var btn = document.getElementById(cfg.micBtnId);
      if (btn) btn.classList.toggle(cfg.activeClass || 'active', on);
    }

    // Bandeau non bloquant affiché une seule fois (localStorage), pas un
    // confirm()/alert() -- cohérent avec le reste du logiciel (chantier
    // "dialogues non bloquants"). Rappelle les 3 limites réelles ci-dessus
    // pour qu'un opérateur en LAN ne prenne pas le blocage pour un bug.
    function warnFirstUse() {
      try {
        if (localStorage.getItem(cfg.warnedKey) === '1') return;
        localStorage.setItem(cfg.warnedKey, '1');
      } catch (e) { /* localStorage indisponible : on affiche quand même */ }
      notify(cfg.warnMessage);
    }

    function toggle() {
      if (!SpeechRecognitionCtor) return; // filet -- le bouton ne devrait déjà pas être visible (voir init())
      if (listening) {
        try { recognition && recognition.stop(); } catch (e) { /* déjà arrêté */ }
        setListening(false);
        return;
      }
      warnFirstUse();
      // Reconnaissance recréée à chaque écoute si cfg.lang est une fonction
      // (langue d'interface a pu changer depuis la dernière dictée) --
      // recognition.lang ne peut être modifié qu'avant start().
      if (typeof cfg.lang === 'function') recognition = null;
      var rec = ensureRecognition();
      try {
        rec.start();
        setListening(true);
      } catch (e) {
        // start() jette si déjà démarré ou si getUserMedia est refusé
        // (contexte non sécurisé -- accès LAN non-HTTPS, voir commentaire
        // d'en-tête, limite #1).
        notify(cfg.startErrorMessage);
        setListening(false);
      }
    }

    // Feature-detect pure, aucune dépendance à l'accès réseau ici (ça, c'est
    // vérifié seulement à l'usage, voir toggle()) -- pas de bouton mort si
    // l'API n'existe pas (Firefox par défaut, Safari incohérent).
    function init() {
      var btn = document.getElementById(cfg.micBtnId);
      if (!btn) return;
      btn.style.display = SpeechRecognitionCtor ? '' : 'none';
    }

    return { init: init, toggle: toggle };
  }

  // ─── Instance historique : dictée de l'INDICATIF (logx_logbook.html) ──────
  // API globale inchangée (window.initCallDictation/toggleCallDictation) --
  // aucun changement de comportement pour le logbook.
  var _callDictation = _createVoiceDictation({
    inputId: 'inputCall',
    micBtnId: 'callMicBtn',
    lang: 'en-US',
    transform: transcriptToCall,
    onFilled: function () {
      if (typeof onCallInput === 'function') onCallInput(); // ré-arme autocomplete/doublon/QRZ -- JAMAIS la soumission du QSO
    },
    notify: function (msg) { if (typeof notify === 'function') notify(msg); },
    warnedKey: 'rc_dictation_warned',
    warnMessage: "🎙️ Dictée vocale EXPÉRIMENTALE : nécessite Chrome/Edge + connexion Internet, et un accès via localhost ou HTTPS (bloquée en LAN http://). Relis toujours l'indicatif avant d'enregistrer le QSO.",
    emptyResultMessage: "⚠️ Indicatif non reconnu — réessaie ou saisis-le au clavier.",
    errorMessage: "❌ Dictée vocale interrompue (micro refusé ou hors-ligne) — saisis l'indicatif au clavier.",
    startErrorMessage: "❌ Micro indisponible (nécessite localhost ou HTTPS) — saisis l'indicatif au clavier.",
  });
  window.initCallDictation = _callDictation.init;
  window.toggleCallDictation = _callDictation.toggle;

  // ─── Nouvelle instance : dictée du CHAT (logx_carte.html) ─────────────────
  // Transcript brut (pas de transcriptToCall -- une question en langage
  // naturel n'a rien d'un indicatif), langue alignée sur l'interface,
  // jamais d'envoi automatique du message.
  var _chatDictation = _createVoiceDictation({
    inputId: 'userInput',
    micBtnId: 'chatMicBtn',
    lang: naturalSpeechLang,
    transform: null,
    onFilled: function (input) {
      // input.value = ... ne déclenche pas l'event 'oninput' du textarea
      // (auto-redimensionnement défini en HTML) -- reproduit le même calcul ici.
      input.style.height = 'auto';
      input.style.height = input.scrollHeight + 'px';
    },
    notify: function (msg) { (window.rcToast || window.notify || function () {})(msg); },
    warnedKey: 'rc_dictation_chat_warned',
    warnMessage: "🎙️ Dictée vocale EXPÉRIMENTALE : nécessite Chrome/Edge + connexion Internet, et un accès via localhost ou HTTPS (bloquée en LAN http://). Relis toujours ta question avant de l'envoyer.",
    emptyResultMessage: "⚠️ Question non reconnue — réessaie ou tape-la au clavier.",
    errorMessage: "❌ Dictée vocale interrompue (micro refusé ou hors-ligne) — tape ta question au clavier.",
    startErrorMessage: "❌ Micro indisponible (nécessite localhost ou HTTPS) — tape ta question au clavier.",
    activeClass: 'qbtn-coach', // pas de .active dans le CSS de logx_carte.html -- réutilise l'état "actif" déjà utilisé par #ttsBtn (syncTtsBtn())
  });
  window.initChatDictation = _chatDictation.init;
  window.toggleChatDictation = _chatDictation.toggle;

})();
