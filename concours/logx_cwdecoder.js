// ─── DÉCODEUR CW (Morse → texte, temps réel, 100% navigateur) ───────────────
// Écoute l'AUDIO DE RÉCEPTION de la radio (câble audio virtuel ou interface
// dédiée vers l'entrée micro du PC — même principe que le keyer vocal, mais
// dans l'autre sens : radio → PC au lieu de PC → radio) et affiche le texte
// décodé en direct. Tout tourne dans le navigateur via l'API Web Audio, sans
// aller-retour serveur.
//
// Principe (pipeline DSP standard, rien d'exotique) :
//  1. Goertzel monofréquence calé sur le ton CW (bien plus robuste qu'une
//     détection d'enveloppe large bande : rejette la voix/le bruit hors bande)
//  2. Seuil ADAPTATIF (AGC : plancher de bruit ET pic de signal suivis en
//     continu, seuil RELATIF entre les deux -- invariant à l'amplitude
//     réelle du signal capté, pas calibré sur une seule échelle fixe) ->
//     signal ON/OFF
//  3. Durées des impulsions/espaces -> classification point/trait/espace par
//     rapport à une unité de temps elle-même adaptative (poursuit la vitesse)
//  4. Table Morse -> caractères
//
// AVERTISSEMENT HONNÊTE (voir aussi la note affichée dans l'UI) : un
// décodeur de ce type reste très en retrait de l'oreille humaine dès qu'il y a
// du QRM, du fading ou un pileup serré — correct sur du CW propre et pas trop
// rapide, pas un substitut à l'entraînement pour du trafic difficile.

const MORSE_TABLE = {
  '.-':'A','-...':'B','-.-.':'C','-..':'D','.':'E','..-.':'F','--.':'G',
  '....':'H','..':'I','.---':'J','-.-':'K','.-..':'L','--':'M','-.':'N',
  '---':'O','.--.':'P','--.-':'Q','.-.':'R','...':'S','-':'T','..-':'U',
  '...-':'V','.--':'W','-..-':'X','-.--':'Y','--..':'Z',
  '-----':'0','.----':'1','..---':'2','...--':'3','....-':'4',
  '.....':'5','-....':'6','--...':'7','---..':'8','----.':'9',
  '.-.-.-':'.',  '--..--':',',  '..--..':'?',  '-..-.':'/',
  '-...-':'=',  '.-.-.':'+',  '-.--.':'(',  '-.--.-':')',
  '.-...':'<AS>', '...-.-':'<SK>', '-...-.-':'<BK>', '.-.-':'<AR>',
  '-.-.-':'<KA>', '...-.':'<SN>',
};

// ─── Décodeur temporel pur (aucune dépendance audio — testable isolément) ───
// pushEdge(isMark, durationMs) : appelé à chaque transition ON->OFF ou
// OFF->ON avec la durée du segment qui vient de se terminer. onChar(ch)
// est appelé pour chaque caractère décodé (ou ' ' pour un espace de mot).
class MorseTimingDecoder {
  constructor(onChar){
    this.onChar = onChar || (()=>{});
    // Hypothèse de départ AVANT toute vraie marque mesurée -- déterminante
    // pour la classification point/trait des tout premiers symboles, tant
    // que la fenêtre glissante (recentMarks) n'a pas encore été purgée des
    // valeurs de remplissage par de vraies marques (voir _adaptUnit). Choisie
    // à 45ms (~27 MPM) et PAS à 80ms (~15 MPM, ancienne valeur) : le seuil de
    // classification point/trait est 2x l'unité (pushEdge ci-dessous), donc
    // un trait (3x l'unité réelle) n'est classé correctement QUE si
    // 3*unitRéel > 2*unitMs -- avec l'ancien défaut de 80ms, ça échouait dès
    // que le débit réel dépassait ~22 MPM (2*80/3 ≈ 53ms -> ~22 MPM), ratant
    // TOUTE la plage 25-35 MPM typique d'un concours : chaque trait du début
    // de message était décodé comme un point jusqu'à ce qu'un point réel plus
    // court apparaisse dans la fenêtre et fasse redescendre l'estimation --
    // ce qui pouvait prendre plusieurs lettres. Confirmé par le calcul :
    // seuil valide en un seul réglage pour couvrir 15-35 MPM (point correct
    // <=> unitMs > unitRéel/2 ; trait correct <=> unitMs < 1.5*unitRéel) =
    // intervalle (40ms, 51ms) -- 45ms est au centre et couvre en fait ~13 à
    // ~40 MPM. Symptôme observé côté utilisateur : décodage incohérent en
    // DÉBUT de session même sur un signal fort, car ce n'est pas un problème
    // de niveau/seuil mais de classification temporelle pure. Vérifié
    // empiriquement (tests/test_cwdecoder.py::test_demarrage_a_froid_vitesse_
    // concours) : avec l'ancien défaut, 'CQ TEST' à 35 MPM décodait
    // 'HQ TEST' -- 1re lettre fausse dès le premier caractère.
    this.unitMs = 45;
    this.recentMarks = new Array(12).fill(45);  // fenêtre glissante, sert à estimer le point
    this.buffer = '';                    // points/traits accumulés du caractère en cours
    this.wpm = 27;
  }

  // Réestime l'unité de temps (durée d'un point) via la 2E PLUS PETITE
  // valeur d'une fenêtre glissante de marques récentes — PAS le minimum
  // strict (utilisé jusqu'au 21/08/2026, voir plus bas pourquoi), PAS une
  // moyenne sur tout ce qui est classé "court". Une moyenne se laisse
  // entraîner vers le haut dès qu'un TRAIT est classé par erreur comme un
  // point (ça arrive : bruit, fist irrégulier) : ce point mesuré "trop
  // long" pousse l'unité vers le haut, ce qui rend le PROCHAIN trait
  // encore plus susceptible d'être mal classé -> boucle de rétroaction qui
  // fait dériver l'unité indéfiniment (vérifié par test : un signal propre
  // finissait par ne plus reconnaître aucun espace de mot après quelques
  // lettres).
  //
  // POURQUOI PAS LE MINIMUM STRICT (régression trouvée le 21/08/2026, sur
  // un enregistrement réel, pas une supposition) : un minimum protège bien
  // contre une durée trop LONGUE (un trait mal classé ne peut jamais tirer
  // un minimum vers le HAUT), mais n'offre AUCUNE protection dans l'autre
  // sens -- un unique blip de bruit isolé, plus COURT qu'un vrai point,
  // suffit à lui seul à faire chuter l'estimation. Le seuil de rejet des
  // impulsions trop courtes (pushEdge, plus bas) dépend lui-même de
  // unitMs : une fois l'estimation tirée vers le bas par ce premier blip,
  // le seuil de rejet baisse aussi, ce qui laisse passer un DEUXIÈME blip
  // encore plus court -- spirale descendante qui a fini par corrompre tout
  // le décodage sur un vrai enregistrement (dépôt à ~43ms de point réel,
  // effondré à ~22ms, proche du plancher de 20ms, en une douzaine de
  // marques). La 2e plus petite valeur exige qu'AU MOINS DEUX marques
  // courtes apparaissent dans la fenêtre avant de faire bouger
  // l'estimation : un blip isolé ne suffit plus plus à l'entraîner, un
  // vrai point rapide RÉPÉTÉ (donc légitime, à vitesse réellement élevée)
  // continue d'être suivi normalement.
  _adaptUnit(markMs){
    this.recentMarks.push(markMs);
    if(this.recentMarks.length > 12) this.recentMarks.shift();
    const sorted = [...this.recentMarks].sort((a, b) => a - b);
    const minRecent = sorted[1];
    this.unitMs = this.unitMs * 0.6 + minRecent * 0.4;
    this.unitMs = Math.max(20, Math.min(300, this.unitMs));  // 4-60 mots/min plausible
    this.wpm = Math.round(1200 / this.unitMs);
  }

  _flushChar(){
    if(!this.buffer) return;
    const ch = MORSE_TABLE[this.buffer] || '�';
    this.onChar(ch);
    this.buffer = '';
  }

  pushEdge(isMark, durationMs){
    if(isMark){
      // Rejette les impulsions ON trop courtes pour être un vrai point --
      // même seuil que fldigi (cw_noise_spike_threshold = dot_length/2,
      // cw.cxx). Un blip de bruit HF (crachement statique, QRM bref) classé
      // comme marque ferait sinon s'effondrer immédiatement le MINIMUM de la
      // fenêtre glissante dans _adaptUnit() (protection anti-dérive, voir
      // plus haut) -- l'estimation de vitesse s'écroule en cascade et
      // corrompt la classification de tout ce qui suit. Ignorée comme si
      // l'émetteur n'avait rien envoyé : ni caractère, ni ajustement
      // d'unité (contrairement à un point/trait réel, elle n'existe nulle
      // part dans le résultat).
      if(durationMs < this.unitMs * 0.5) return;
      // Point vs trait : seuil à 2x l'unité courante (point=1, trait=3 -> le
      // milieu naturel est à 2).
      this.buffer += (durationMs < this.unitMs * 2) ? '.' : '-';
      this._adaptUnit(durationMs);
    } else {
      // Espace : intra-caractère (<2u) ignoré, inter-caractère (2-6u) ferme
      // la lettre, inter-mot (>6u) ferme la lettre ET émet un espace.
      // Rapproché de 6u à 5u puis REVERT à 6u (15/08/2026, chantier AGC/CW
      // réel) : fldigi est plus permissif (4u) mais un essai concret a
      // montré que 5u casse la reconnaissance à vitesse LENTE en début de
      // message (test_demarrage_a_froid_vitesse_concours, 15 MPM) -- unitMs
      // met plusieurs lettres à converger depuis son hypothèse de départ
      // (45ms) vers la vraie valeur (80ms à 15 MPM), et un espace
      // inter-lettre RÉEL évalué contre ce unitMs encore bas franchissait le
      // seuil de 5u par erreur. Piste écartée : à confiance/priorité les
      // plus faibles du diagnostic (texte parfois collé, jamais un échec
      // total), pas assez de marge pour la corriger sans mieux comprendre
      // l'interaction avec la convergence à froid -- gardé pour une suite
      // éventuelle plutôt que de risquer une régression vérifiée.
      if(durationMs >= this.unitMs * 2){
        const hadChar = !!this.buffer;
        this._flushChar();
        // hadChar : un espace-mot n'a de sens qu'APRÈS un caractère réel.
        // Sans cette garde, le silence initial avant la TOUTE PREMIÈRE
        // marque d'une session (mesuré contre l'hypothèse de départ encore
        // basse de unitMs, voir constructeur) peut à lui seul dépasser le
        // seuil inter-mot et produire un espace parasite EN TÊTE de sortie,
        // avant tout texte. Trouvé en testant le pipeline CwAudioDecoder de
        // bout en bout (15/08/2026) -- jamais exercé avant ce chantier
        // (CwAudioDecoder n'avait aucun test propre jusque-là).
        if(hadChar && durationMs >= this.unitMs * 6) this.onChar(' ');
      }
    }
  }

  // À appeler périodiquement pendant un silence prolongé (fin de mot/lettre
  // qui ne serait jamais "fermée" par une transition suivante si l'émetteur
  // s'arrête) — sans ça le dernier caractère resterait bloqué en mémoire.
  flushIfIdle(idleMs){
    if(idleMs >= this.unitMs * 2) this._flushChar();
  }
}

// ─── Détecteur Goertzel monofréquence ────────────────────────────────────────
// Magnitude du signal à `targetFreq` sur un bloc de `blockSize` échantillons —
// bien moins cher qu'une FFT complète pour une seule fréquence, exactement ce
// dont on a besoin ici (le ton CW est une porteuse pure, pas un spectre large).
function goertzelMagnitude(samples, sampleRate, targetFreq){
  const n = samples.length;
  const k = Math.round(n * targetFreq / sampleRate);
  const w = (2 * Math.PI / n) * k;
  const cosine = Math.cos(w), sine = Math.sin(w), coeff = 2 * cosine;
  let q0=0, q1=0, q2=0;
  for(let i=0;i<n;i++){
    q0 = coeff*q1 - q2 + samples[i];
    q2 = q1; q1 = q0;
  }
  const real = q1 - q2*cosine, imag = q2*sine;
  return Math.sqrt(real*real + imag*imag) / n;
}

// ─── Détection automatique du ton CW (retour F4GLD 21/08/2026) ──────────────
// « c'est compliqué pour un novice, on peut pas faciliter ce réglage ? » --
// jusqu'ici, faire correspondre le ton écouté (#cwFreq) au ton RÉEL émis par
// la radio exigeait de connaître/aller lire le réglage CW Pitch du poste.
// Ici : on écoute sur TOUTES les fréquences plausibles à la fois pendant
// quelques secondes, et on retient celle qui montre un vrai RYTHME de
// signal ON/OFF -- ni un bruit large bande (aucune fréquence ne se détache),
// ni un ronflement/porteuse continue à une fréquence étrangère (present en
// permanence, jamais "OFF", donc jamais assez de transitions).
// Pas de 100 Hz : goertzelMagnitude() ARRONDIT la fréquence demandée au bin
// Goertzel le plus proche (k = round(n*freq/sampleRate)) -- à blockSize=512
// (comme CwAudioDecoder), la résolution réelle entre deux bins DISTINCTS est
// sampleRate/blockSize, soit ≈86 Hz à 44.1kHz. Des candidates à 50 Hz
// d'écart (essayé, constaté par test) tombent alors régulièrement sur le
// MÊME bin -- pas une fuite spectrale approximative, une collision EXACTE
// (magnitude rigoureusement identique). Aucune conséquence sur la qualité du
// décodage ensuite (deux candidates qui collisionnent sont interchangeables
// pour goertzelMagnitude), mais rend le résultat de detectFreq() imprévisible
// à l'oeil. 100 Hz espace suffisamment les candidates pour rester distinctes
// aux fréquences d'échantillonnage usuelles (44.1/48 kHz), tout en couvrant
// finement la plage utile d'un réglage CW Pitch (300-900 Hz).
const CW_FREQ_CANDIDATES = (() => {
  const out = [];
  for (let f = 300; f <= 900; f += 100) out.push(f);
  return out;
})();

// Sous le nombre minimal de transitions ON/OFF observées pendant la fenêtre
// de détection, une fréquence n'est JAMAIS retenue -- un unique pic isolé
// (parasite, craquement statique) ne doit pas suffire à désigner un ton.
const CW_DETECT_MIN_TRANSITIONS = 4;

// Sous cette proportion de caractères VALIDES (présents dans MORSE_TABLE,
// ni '�' ni uniquement des espaces) parmi ceux décodés pendant la fenêtre,
// une fréquence n'est jamais retenue même si elle a franchi le seuil de
// transitions -- un ronflement grave/souffle de micro peut très bien
// produire assez d'allers-retours ON/OFF pour passer CW_DETECT_MIN_
// TRANSITIONS SANS jamais respecter les proportions point/trait/espace
// d'un vrai Morse, et se décode donc presque uniquement en caractères
// inconnus.
//
// INSUFFISANT SEUL, corrigé le 21/08/2026 en le regardant tourner sur un
// vrai signal (F4GLD) : ce ratio ne protège PAS contre un bruit haché qui
// produit des impulsions COURTES. Le code Morse international assigne une
// lettre à absolument TOUTES les combinaisons de 1 à 3 symboles (E/T sur 1,
// I/A/N/M sur 2, les 8 combinaisons de 3 symboles couvrent D/U/S/W/G/R/O/K
// en entier) -- un caractère de 1-3 symboles est donc TOUJOURS "valide" par
// construction du code, qu'il vienne d'un vrai opérateur ou d'un
// bourdonnement modulé par hasard. Sur le poste de F4GLD, un tel bruit à
// 300 Hz passait ce filtre haut la main (beaucoup de courts caractères
// "valides") tout en affichant un charabia illisible -- constaté en
// direct, pas supposé.
const CW_DETECT_MIN_VALID_RATIO = 0.5;

// Deuxième garde-fou, complémentaire : la VITESSE estimée doit rester dans
// une plage humainement plausible. MorseTimingDecoder borne unitMs à
// [20,300]ms (voir son constructeur), soit 4 à 60 MPM -- un bruit haché en
// impulsions très courtes et irrégulières fait typiquement CHUTER unitMs
// jusqu'à son plancher, ce qui donne 60 MPM tout rond : pas une mesure,
// LE PLAFOND du calcul lui-même. Confirmé en direct sur le même signal :
// le candidat piégé par le premier garde-fou affichait exactement 60 MPM.
// Aucun trafic CW à la main (même un concours rapide) n'approche cette
// vitesse -- 45 MPM laisse une marge large au-dessus du rythme humain le
// plus rapide réaliste, tout en excluant nettement le plafond du calcul.
const CW_DETECT_MAX_WPM = 45;

class CwFreqDetector {
  constructor(){
    this.stats = new Map(CW_FREQ_CANDIDATES.map(f => {
      const s = {
        on: false, transitions: 0, noiseFloor: 0.001, agcPeak: 0.001,
        edgeStartMs: 0, validChars: 0, totalChars: 0,
      };
      // Décodeur Morse DÉDIÉ à cette candidate : reçoit UNIQUEMENT ses
      // propres transitions ON/OFF, jamais celles des autres candidates --
      // sa capacité à produire du texte reconnaissable est la preuve la
      // plus directe qu'on ait qu'un rythme est du VRAI Morse et pas un
      // simple bruit modulé qui franchit le seuil par coïncidence.
      s.decoder = new MorseTimingDecoder(ch => {
        s.totalChars++;
        if (ch !== '�' && ch !== ' ') s.validChars++;
      });
      return [f, s];
    }));
    this._elapsedMs = 0;
  }

  // Un bloc = mêmes samples bruts que CwAudioDecoder._onBlock, passés à
  // TOUTES les fréquences candidates (même AGC seuil-relatif que le
  // décodage réel, voir _onBlock -- la logique de séparation signal/bruit
  // ne doit pas diverger entre détection et décodage).
  feed(samples, sampleRate){
    const blockMs = samples.length / sampleRate * 1000;
    for (const f of CW_FREQ_CANDIDATES) {
      const s = this.stats.get(f);
      const mag = goertzelMagnitude(samples, sampleRate, f);
      if (mag < s.noiseFloor) s.noiseFloor = s.noiseFloor * 0.98 + mag * 0.02;
      else s.noiseFloor = s.noiseFloor * 0.999 + mag * 0.001;
      if (mag > s.agcPeak) s.agcPeak = s.agcPeak * 0.7 + mag * 0.3;
      else s.agcPeak = s.agcPeak * 0.999 + mag * 0.001;
      const span = Math.max(s.agcPeak - s.noiseFloor, 0);
      const threshold = s.noiseFloor * 2.0 + span * 0.35;
      const isOn = mag > threshold;
      if (isOn !== s.on) {
        s.transitions++;
        const durationMs = Math.max(1, this._elapsedMs - s.edgeStartMs);
        s.decoder.pushEdge(s.on, durationMs);   // rapporte le segment qui vient de finir
        s.edgeStartMs = this._elapsedMs;
        s.on = isOn;
      }
    }
    this._elapsedMs += blockMs;
  }

  // Meilleure fréquence candidate : d'abord celles qui produisent du VRAI
  // Morse décodable (proportion de caractères valides >= CW_DETECT_MIN_
  // VALID_RATIO), puis parmi elles CETTE PROPORTION elle-même (la
  // QUALITÉ), le rapport pic/plancher ne servant qu'à départager une
  // ÉGALITÉ de proportion.
  //
  // PAS le nombre de caractères valides ACCUMULÉS (essayé, puis corrigé le
  // 21/08/2026 sur un enregistrement réel) : une candidate qui capte une
  // fuite spectrale/du bruit large bande peut accumuler BEAUCOUP de
  // transitions et donc BEAUCOUP de caractères valides en volume tout en
  // n'étant correcte qu'une fois sur trois (ex. mesuré : 53 caractères
  // valides à 77 % de proportion, contre 21 à 95 % pour le vrai ton) --
  // compter le nombre brut faisait gagner la candidate la plus BRUYANTE,
  // pas la plus PROPRE. La proportion, elle, n'est pas influencée par le
  // volume d'activité : un candidat qui décode presque tout juste (même
  // peu) l'emporte légitimement sur un candidat qui décode beaucoup mais
  // approximativement.
  //
  // null si rien d'assez net/décodable n'a été observé -- mieux vaut le
  // dire honnêtement que renvoyer un résultat au hasard sur du silence, du
  // bruit pur, ou un ronflement qui imite un rythme sans être du Morse.
  best(){
    let bestFreq = null, bestValidRatio = -1, bestRatio = 0;
    for (const [f, s] of this.stats) {
      if (s.transitions < CW_DETECT_MIN_TRANSITIONS) continue;
      // Caractère en cours jamais refermé par une transition suivante (la
      // fenêtre de détection s'arrête pendant une marque/un silence) :
      // flushIfIdle() le compte quand même plutôt que de le perdre --
      // mêmes règles que le décodage réel en fin de session.
      s.decoder.flushIfIdle(this._elapsedMs - s.edgeStartMs);
      if (s.totalChars === 0) continue;
      const validRatio = s.validChars / s.totalChars;
      if (validRatio < CW_DETECT_MIN_VALID_RATIO) continue;
      if (s.decoder.wpm > CW_DETECT_MAX_WPM) continue;
      const ratio = s.agcPeak / Math.max(s.noiseFloor, 1e-6);
      if (validRatio > bestValidRatio
          || (validRatio === bestValidRatio && ratio > bestRatio)) {
        bestValidRatio = validRatio; bestRatio = ratio; bestFreq = f;
      }
    }
    return bestFreq;
  }
}

// ─── Pipeline audio temps réel (getUserMedia -> Goertzel -> décodeur) ───────
class CwAudioDecoder {
  constructor({freq=650, onChar, onLevel, onBlock} = {}){
    this.freq = freq;
    this.onLevel = onLevel || (()=>{});
    // Point d'extension pour CwFreqDetector (voir CwPanel.detectFreq()) :
    // remplace ENTIÈREMENT le traitement par bloc habituel (Goertzel mono-
    // fréquence + MorseTimingDecoder) par un simple relais des échantillons
    // bruts -- le pipeline getUserMedia/AudioContext/ScriptProcessor reste
    // identique et partagé, seul ce qu'on FAIT de chaque bloc change.
    this._onBlockOverride = onBlock || null;
    this.decoder = new MorseTimingDecoder(onChar);
    this.decoder.wpm = 0;   // 0 tant qu'aucune marque réelle n'a été mesurée — voir onLevel plus bas
    this.ctx = null; this.stream = null; this.source = null; this.proc = null;
    // Bootstrap volontairement TRÈS bas (pas 0.01 comme dans une version
    // intermédiaire de ce correctif, 15/08/2026) : un plancher de bruit ET
    // un pic de signal démarrés haut créent un écart fantôme (span) qui met
    // plusieurs SECONDES à se résorber (agcPeak décroît volontairement très
    // lentement, ~0,1%/bloc, pour ne pas "oublier" le pic entre deux marques
    // d'un même message) -- juste après avoir cliqué "Démarrer", exactement
    // la fenêtre où l'opérateur s'attend à une détection immédiate d'un
    // signal faible. Vérifié empiriquement (voir tests/test_cwdecoder.py) :
    // un bootstrap à 0.01 laissait encore passer ce symptôme. Un signal fort
    // continue de faire monter agcPeak en 1-2 blocs (attaque rapide,
    // 0.7/0.3) : rien à perdre en réactivité avec un départ bas. Un
    // éventuel bruit ambiant réel plus élevé que ce bootstrap ferait
    // remonter noiseFloor par la branche lente (voir _onBlock()) en
    // quelques dizaines de blocs -- et toute fausse marque transitoire
    // pendant cette (brève) mise à niveau est de toute façon absorbée par
    // le rejet des impulsions courtes de MorseTimingDecoder.pushEdge().
    this.noiseFloor = 0.001;
    this.agcPeak = 0.001;
    this.keyDown = false;
    this.edgeStartMs = 0;
    this.lastSampleMs = 0;
    this.blockSize = 512;   // ~11.6ms à 44.1kHz : assez court pour suivre du CW rapide
    this._buf = [];
  }

  async start(deviceId){
    // Garde de ré-entrance : un second appel avant un stop() correspondant
    // (double-clic, redémarrage sur changement de périphérique) libère
    // d'abord toute session déjà ouverte au lieu d'écraser ses références.
    if(this.ctx) this.stop();
    const constraints = {audio: deviceId ? {deviceId:{exact:deviceId}, echoCancellation:false, noiseSuppression:false, autoGainControl:false}
                                          : {echoCancellation:false, noiseSuppression:false, autoGainControl:false}};
    this.stream = await navigator.mediaDevices.getUserMedia(constraints);
    this.ctx = new (window.AudioContext || window.webkitAudioContext)();
    this.source = this.ctx.createMediaStreamSource(this.stream);
    // ScriptProcessorNode : déprécié mais universellement supporté et bien
    // assez pour un flux mono à quelques dizaines de Hz de résolution
    // temporelle — pas besoin d'un AudioWorklet pour ce cas d'usage.
    this.proc = this.ctx.createScriptProcessor(this.blockSize, 1, 1);
    this.edgeStartMs = performance.now();
    this.lastSampleMs = this.edgeStartMs;
    this.proc.onaudioprocess = (e) => {
      const samples = e.inputBuffer.getChannelData(0);
      if (this._onBlockOverride) this._onBlockOverride(samples, this.ctx.sampleRate);
      else this._onBlock(samples);
    };
    this.source.connect(this.proc);
    // Le graphe Web Audio n'avance que si le node est connecté à une
    // destination — un GainNode à 0 évite de faire sortir le son des
    // haut-parleurs tout en gardant le pipeline actif.
    this._sink = this.ctx.createGain();
    this._sink.gain.value = 0;
    this.proc.connect(this._sink);
    this._sink.connect(this.ctx.destination);
  }

  setFreq(hz){ this.freq = hz; }

  _onBlock(samples){
    const now = performance.now();
    const mag = goertzelMagnitude(samples, this.ctx.sampleRate, this.freq);

    // Plancher de bruit : moyenne très lente, tirée vers le bas plus vite
    // qu'elle ne monte (ne doit jamais "apprendre" un signal continu comme
    // étant du bruit, sinon le décodeur devient sourd à un CW soutenu).
    if(mag < this.noiseFloor) this.noiseFloor = this.noiseFloor*0.98 + mag*0.02;
    else this.noiseFloor = this.noiseFloor*0.999 + mag*0.001;
    // Pic de signal (AGC) : attaque rapide (suit vite une marque qui monte),
    // relâchement lent (ne redescend pas entre deux marques d'un même
    // message) -- SYMÉTRIQUE au plancher de bruit ci-dessus. mirror de
    // agc_peak dans fldigi (rigs/.../cw_rtty/cw.cxx, w1hkj/fldigi).
    if(mag > this.agcPeak) this.agcPeak = this.agcPeak*0.7 + mag*0.3;
    else this.agcPeak = this.agcPeak*0.999 + mag*0.001;
    // Seuil RELATIF (entre bruit et pic de signal), plus un petit facteur
    // multiplicatif sur le bruit pour éviter le crépitement quand tout est
    // silencieux (agcPeak ~= noiseFloor). AVANT : seuil en ÉCHELLE ABSOLUE
    // (`noiseFloor*2.8 + 0.003`, ce `+0.003` dominant dès que noiseFloor est
    // petit) -- calibré empiriquement contre les tons de test SYNTHÉTIQUES
    // (amplitude 1.0 = magnitude Goertzel ~0.5). Un signal RADIO réel capté
    // via carte son/interface plafonne très souvent bien plus bas (surtout
    // avec autoGainControl:false, volontaire ci-dessus) et pouvait ne
    // JAMAIS dépasser ce plancher absolu -- décodage totalement silencieux
    // quel que soit le réglage de vitesse/fréquence. Symptôme réel rapporté
    // sur IC-7300 (15/08/2026), déjà signalé une fois le 04/08/2026 sans
    // que cette logique n'ait alors été corrigée. Un seuil RELATIF au pic
    // observé est invariant à l'échelle du signal d'entrée, comme fldigi.
    const span = Math.max(this.agcPeak - this.noiseFloor, 0);
    const threshold = this.noiseFloor * 2.0 + span * 0.35;
    const isOn = mag > threshold;
    this.onLevel(mag, threshold, this.decoder.wpm);

    if(isOn !== this.keyDown){
      // Compensation du retard de détection lié au découpage en blocs : un
      // changement d'état n'est confirmé qu'au bloc COMPLET suivant, ce qui
      // allonge systématiquement chaque marque et raccourcit symétriquement
      // l'espace qui suit (vérifié empiriquement contre un signal de test :
      // biais ≈ une durée de bloc). Sans cette correction, l'unité de temps
      // adaptative dérive lentement vers le haut au fil du message et finit
      // par plus reconnaître les espaces de mot.
      const blockMs = this.blockSize / this.ctx.sampleRate * 1000;
      let durationMs = (now - this.edgeStartMs) + (this.keyDown ? -blockMs : blockMs);
      durationMs = Math.max(1, durationMs);
      this.decoder.pushEdge(this.keyDown, durationMs);
      this.keyDown = isOn;
      this.edgeStartMs = now;
    } else if(!this.keyDown){
      this.decoder.flushIfIdle(now - this.edgeStartMs);
    }
    this.lastSampleMs = now;
  }

  stop(){
    try{ this.proc && this.proc.disconnect(); }catch(e){}
    try{ this._sink && this._sink.disconnect(); }catch(e){}
    try{ this.source && this.source.disconnect(); }catch(e){}
    try{ this.stream && this.stream.getTracks().forEach(t=>t.stop()); }catch(e){}
    try{ this.ctx && this.ctx.close(); }catch(e){}
    this.ctx = null; this.stream = null;
  }
}

if(typeof module !== 'undefined') module.exports = {MORSE_TABLE, MorseTimingDecoder, goertzelMagnitude, CwAudioDecoder, CwFreqDetector, CW_FREQ_CANDIDATES, CW_DETECT_MIN_TRANSITIONS};
