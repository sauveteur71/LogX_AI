/* LogX AI — décodage FT8 hors du fil principal.
 *
 * POURQUOI CE FICHIER EXISTE. Le décodage d'un créneau bloquait le fil
 * principal 2 576 ms (mesuré en navigateur réel : Chrome 148 / Electron 42,
 * fenêtre 16,5 s à 48 kHz, 3 stations). Pendant ce temps ni la cascade ne se
 * redessine, ni le ScriptProcessorNode qui collecte l'audio ne s'exécute :
 * les blocs sautés font dériver l'horloge du tampon, que la page doit ensuite
 * reprendre — d'où le compteur « N resynchro. audio » qui monte sans fin. Le
 * décodage se sabotait lui-même : plus il durait, plus il perdait d'audio.
 *
 * La décimation avait divisé le blocage par 4 (10 319 -> 2 576 ms) sans le
 * supprimer : DERIVE_MAX_MS vaut 400 ms, on restait 6,4 fois au-dessus. Sortir
 * le calcul du fil principal est le seul changement qui rende le trou NUL.
 *
 * C'EST LE PREMIER WEB WORKER DU DÉPÔT (vérifié : 0 occurrence de
 * « new Worker » avant celui-ci). Il est possible parce que logx_ft8_dsp.js et
 * logx_ft8_codec.js sont du calcul PUR : zéro référence à window, document,
 * localStorage ou navigator — vérifié par comptage sur les deux fichiers.
 *
 * ─── LE PIÈGE QUI AURAIT CASSÉ L'ÉMISSION ────────────────────────────────
 * La table de hachage des indicatifs est partagée par DEUX chemins dans la
 * page : le décodage (verifierCycle) ET l'encodage des messages à ÉMETTRE
 * (ft8EncodeMessage). Si ce Worker accumulait les hachages de son côté, la
 * page perdrait ceux dont elle a besoin pour encoder un indicatif composé
 * (`<F4GLD/P>`) — une panne d'émission SILENCIEUSE, visible seulement d'en
 * face. D'où le protocole : la page envoie sa table, le Worker rend les
 * entrées APPARUES pendant le décodage, et la page les FUSIONNE dans la
 * sienne. Jamais de remplacement en bloc : la page peut avoir ajouté une
 * entrée (côté émission) pendant que le Worker travaillait.
 *
 * ─── PAS DE TRANSFERT DES ÉCHANTILLONS ───────────────────────────────────
 * `samples` arrive par COPIE (clone structuré), jamais en transférable. La
 * page réutilise le même tableau juste après, pour surveillerSilenceAnormal :
 * un transfert le viderait côté page et la surveillance du silence
 * mesurerait un tableau vide — donc « silence » à chaque créneau. ~3,2 Mo par
 * créneau de 15 s, sans commune mesure avec les 2,5 s qu'on économise.
 */

/* eslint-env worker */
/* global ft8Decimer, ft8DecodeAudioAll, ft8CreateHashTable */

self.importScripts('logx_ft8_codec.js', 'logx_ft8_dsp.js');

self.onmessage = function (ev) {
  var m = (ev && ev.data) || {};
  if (m.type !== 'decoder') return;

  // Table reconstruite À CHAQUE message depuis celle de la page : le Worker
  // ne garde AUCUN état entre deux créneaux. Un état résident divergerait de
  // la page dès la première entrée ajoutée côté émission, et le désaccord
  // serait invisible jusqu'au jour où un indicatif composé ne passe plus.
  var table = ft8CreateHashTable();
  var connuesAvant = [];
  if (m.hachages && m.hachages.length) {
    for (var i = 0; i < m.hachages.length; i++) {
      table.byN22.set(m.hachages[i][0], m.hachages[i][1]);
      connuesAvant.push(m.hachages[i][0]);
    }
  }
  var avant = new Set(connuesAvant);

  var reponse = {
    type: 'decode',
    jeton: m.jeton,            // repris tel quel : la page écarte les réponses
    slot: m.slot,              // périmées sans avoir à les interpréter
    sampleRate: 0,
    results: [],
    hachagesNeufs: [],
    erreur: null,
  };

  try {
    var dec = ft8Decimer(m.samples, m.sampleRate);
    reponse.sampleRate = dec.sampleRate;
    reponse.results = ft8DecodeAudioAll(dec.samples, dec.sampleRate, table, {
      centerSample: (m.centerMs / 1000) * dec.sampleRate,
    }) || [];
    // Uniquement ce que CE décodage a appris : la page fusionne, elle ne
    // remplace pas.
    table.byN22.forEach(function (v, k) {
      if (!avant.has(k)) reponse.hachagesNeufs.push([k, v]);
    });
  } catch (e) {
    // Un décodage qui échoue ne doit PAS laisser la page attendre : elle
    // resterait sans réponse pour ce créneau et le séquenceur se figerait sur
    // un « j'attends » qui ne viendrait jamais. On répond toujours.
    reponse.erreur = (e && e.message) ? String(e.message) : String(e);
  }

  self.postMessage(reponse);
};
