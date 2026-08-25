/* logx_ft8_copilote.js — Copilote FT8 : niveau « copilote » du séquenceur.
 *
 * Principe VERROUILLÉ (F4GLD) : l'IA PRÉPARE, l'HUMAIN déclenche. À
 * seqNiveau === 'copilote', le séquenceur FT8 existant (logx_ft8.html, #179)
 * calcule le message suivant EXACTEMENT comme d'habitude (machine d'état QSO,
 * report/R+report/RR73/73, journalisation) — mais au lieu d'auto-émettre, il
 * route le message vers la barre de consentement (logx_tx_bar.js, #256) :
 * l'opérateur confirme via ÉMETTRE, et alors seulement l'émission part.
 *
 * Ce module ne RECALCULE PAS le message (le séquenceur reste la source de
 * vérité) : il ne fournit que la glue PURE et testable — faut-il proposer,
 * comment emballer la proposition, et l'anti-spam (idempotence sur les
 * re-décodes d'un même cycle 15 s). Testé en V8 (test_ft8_copilote.py).
 *
 * Inclusion : <script src="logx_tx_bar.js"></script> puis
 * <script src="logx_ft8_copilote.js"></script> sur logx_ft8.html.
 */
(function () {
  'use strict';

  // Ne proposer (au lieu d'auto-émettre) QU'au niveau 'copilote'. Les niveaux
  // historiques (manuel/assisté/séquenceur/auto) gardent leur comportement.
  function doitProposer(seqNiveau) {
    return seqNiveau === 'copilote';
  }

  // Emballe le message CALCULÉ PAR LE SÉQUENCEUR pour LogxTxBar.proposer().
  // `txMsg` est le message FT8 tel quel (ex. 'F4ABC F1XYZ -12'), jamais
  // recalculé ici. `monCall` = MON indicatif (opérateur). voice_source neutre :
  // le FT8 n'est pas de la voix.
  function messagePropose(txMsg, dxCall, freqHz, monCall) {
    return {
      mode: 'FT8',
      message: String(txMsg || ''),
      frequency_hz: freqHz,
      operator: String(monCall || ''),
      radio_id: String(dxCall || ''),   // trace le DX visé (jamais l'humain)
      power_w: undefined,               // rempli par l'appelant si connu
      voice_source: 'auto'
    };
  }

  // Clé d'idempotence anti-spam : un même DX + un même message TX (re-décodé
  // plusieurs fois dans le cycle 15 s) ne doit produire qu'UNE proposition.
  // Un message TX différent (étape suivante du QSO) donne une clé différente.
  function cle(dxCall, txMsg) {
    return String(dxCall || '').toUpperCase() + '|' + String(txMsg || '').toUpperCase();
  }

  // Format report FT8 : signe + 2 chiffres (ex. -12, +03, -05).
  function fmtSnr(snr) {
    var n = Math.round(Number(snr) || 0);
    return (n >= 0 ? '+' : '-') + String(Math.abs(n)).padStart(2, '0');
  }

  // Réponse FT8 à un décode qui M'EST ADRESSÉ, selon le protocole standard
  // (table SOURCÉE F4GLD). Retourne {message, dxCall} ou null si rien à
  // proposer (pas pour moi / QSO fini / message inattendu). NE calcule PAS
  // depuis la grille (report = SNR reçu) : évite le piège grille='RR73'.
  //   « monCall DX <grille|rien> » -> « DX monCall <report> »   (on m'appelle)
  //   « monCall DX <report nu> »   -> « DX monCall R<report> »  (report reçu)
  //   « monCall DX R<report> »     -> « DX monCall RR73 »       (accusé + report)
  //   « monCall DX RRR|RR73|73 »   -> null                      (QSO terminé)
  function reponseFt8(decodeMsg, snr, monCall) {
    var toks = String(decodeMsg || '').trim().toUpperCase().split(/\s+/);
    monCall = String(monCall || '').toUpperCase();
    if (toks.length < 2 || toks[0] !== monCall) { return null; }   // pas pour moi
    var dx = toks[1];
    if (!dx || dx === 'CQ') { return null; }
    var r0 = toks[2] || '';
    if (r0 === 'RRR' || r0 === 'RR73' || r0 === '73') { return null; }  // QSO fini
    if (/^R[+-]\d{1,2}$/.test(r0)) { return { message: dx + ' ' + monCall + ' RR73', dxCall: dx }; }
    if (/^[+-]\d{1,2}$/.test(r0)) { return { message: dx + ' ' + monCall + ' R' + fmtSnr(snr), dxCall: dx }; }
    if (toks.length === 2 || /^[A-R]{2}\d{2}$/.test(r0)) {
      return { message: dx + ' ' + monCall + ' ' + fmtSnr(snr), dxCall: dx };
    }
    return null;
  }

  // Message INITIAL pour répondre à un CQ / appeler une station : « CIBLE
  // MONCALL MONGRILLE4 » (grille tronquée à 4 car ; omise si absente — un appel
  // sans grille reste un message FT8 valide). null si cible ou mon indicatif
  // manquant. La suite du QSO (report, RR73…) est gérée par reponseFt8 (auto).
  function appelInitial(cible, monCall, monGrid) {
    cible = String(cible || '').trim().toUpperCase();
    monCall = String(monCall || '').trim().toUpperCase();
    if (!cible || !monCall) { return null; }
    var g = String(monGrid || '').trim().toUpperCase().slice(0, 4);
    return cible + ' ' + monCall + (g ? ' ' + g : '');
  }

  // ── Extraction pour la JOURNALISATION du QSO copilote (données à
  // enregistrer, doc F4GLD). Le copilote (approche X) n'utilise pas la boucle
  // du séquenceur : il trace lui-même les reports/grille au fil des décodes
  // et appelle offrirLogQso() à la clôture. Ces helpers restent purs/testables.

  // Report d'un message FT8 = dernier jeton « [R]±NN » (R d'accusé retiré).
  // null si le dernier jeton n'est pas un report (grille, RR73, 73…).
  function extraireReport(ft8Msg) {
    var toks = String(ft8Msg || '').trim().toUpperCase().split(/\s+/);
    var m = (toks[toks.length - 1] || '').match(/^R?([+-]\d{1,2})$/);
    return m ? m[1] : null;
  }

  // Grille 4 caractères (Maidenhead) d'un message, en EXCLUANT 'RR73' — qui
  // satisfait la regex grille ([A-R]{2}\d{2}) et a déjà causé un vrai bug de
  // distance/log dans le séquenceur (locator='RR73', 5665 km fantômes).
  function extraireGrille(ft8Msg) {
    var toks = String(ft8Msg || '').trim().toUpperCase().split(/\s+/);
    for (var i = 0; i < toks.length; i++) {
      if (toks[i] !== 'RR73' && /^[A-R]{2}\d{2}$/.test(toks[i])) { return toks[i]; }
    }
    return null;
  }

  // Le décode m'annonce-t-il la CLÔTURE du QSO (RRR/RR73/73 qui M'EST adressé) ?
  function estFinQso(decodeMsg, monCall) {
    var toks = String(decodeMsg || '').trim().toUpperCase().split(/\s+/);
    if (toks[0] !== String(monCall || '').toUpperCase()) { return false; }
    var r0 = toks[2] || '';
    return r0 === 'RRR' || r0 === 'RR73' || r0 === '73';
  }

  window.LogxFt8Copilote = {
    doitProposer: doitProposer,
    messagePropose: messagePropose,
    reponseFt8: reponseFt8,
    appelInitial: appelInitial,
    extraireReport: extraireReport,
    extraireGrille: extraireGrille,
    estFinQso: estFinQso,
    fmtSnr: fmtSnr,
    cle: cle,
    _dernierePropose: null   // clé de la dernière proposition émise/en cours (anti-spam runtime)
  };
})();
