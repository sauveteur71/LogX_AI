/* logx_cwssb_copilote.js — Copilote CW/SSB : prépare l'échange, l'humain émet.
 *
 * Principe VERROUILLÉ (F4GLD), identique au copilote FT8 : l'IA PRÉPARE une
 * émission, l'HUMAIN la déclenche (ÉMETTRE dans la barre de consentement,
 * logx_tx_bar.js). Ici, hors FT8 : quand un indicatif est RÉSOLU dans le
 * LOGBOOK, le copilote prépare le message d'échange du concours actif (report +
 * série/zone) dans la barre ; l'opérateur confirme et alors seulement ça part au
 * keyer (CW) ou au voice keyer (phonie).
 *
 * PROPOSE-ONLY, jamais d'auto-émission : contrairement au FT8, il n'y a AUCUN
 * flux décodé en CW/SSB pour déclencher un « émet après délai ». Le seul
 * déclencheur est le geste humain (ÉMETTRE).
 *
 * Ce module ne CONSTRUIT PAS le texte (le LOGBOOK le fait via expandMacro /
 * gabarit voix, déjà mûrs) : il ne fournit que la glue PURE et testable — faut-il
 * proposer, quelle famille de mode, comment emballer, et l'anti-spam. Testé en
 * V8 (test_cwssb_copilote.py).
 *
 * Inclusion (LOGBOOK) : <script src="logx_tx_bar.js"></script> puis
 * <script src="logx_cwssb_copilote.js"></script>.
 */
(function () {
  'use strict';

  // Famille de mode pour le consentement : 'cw' (keyer), 'phonie' (voice keyer),
  // ou null pour les modes DATA (FT8/RTTY/PSK…) — ceux-là ont leur propre chemin
  // (le copilote FT8), ce copilote ne les touche pas. Même partition que le
  // garde-fou serveur (CW* -> cw ; SSB/USB/LSB/FM/AM -> phonie ; reste -> data).
  function familleMode(mode) {
    var m = String(mode || '').toUpperCase();
    if (!m) { return null; }
    if (m.indexOf('CW') === 0) { return 'cw'; }
    if (['SSB', 'USB', 'LSB', 'FM', 'AM'].indexOf(m) !== -1) { return 'phonie'; }
    return null;   // data : hors périmètre CW/SSB
  }

  // Faut-il proposer l'échange ? Oui si le copilote est ACTIF (opt-in, éteint par
  // défaut — jamais de surprise sur le chemin critique), qu'un indicatif est
  // présent, et que le mode est CW ou phonie. L'anti-spam (ne pas re-proposer le
  // même échange) est géré par l'appelant via cle() + un dernier-proposé.
  function doitProposer(actif, call, mode) {
    return !!actif && !!String(call || '').trim() && familleMode(mode) !== null;
  }

  // Emballe le message CALCULÉ PAR LE LOGBOOK (expandMacro CW / gabarit voix)
  // pour LogxTxBar.proposer(). `txMsg` est le texte d'échange tel quel, jamais
  // recalculé ici. `monCall` = MON indicatif (opérateur), `call` = correspondant.
  // `voiceSource` (phonie) : 'wav' | 'tts' | 'auto' — sans objet en CW.
  function messagePropose(txMsg, call, mode, freqHz, monCall, voiceSource) {
    return {
      mode: String(mode || ''),
      message: String(txMsg || ''),
      frequency_hz: freqHz,
      operator: String(monCall || ''),
      radio_id: String(call || ''),     // correspondant visé (jamais l'humain)
      power_w: undefined,               // rempli par l'appelant si connu
      voice_source: voiceSource || 'auto'
    };
  }

  // Clé d'idempotence anti-spam : un même correspondant + un même texte d'échange
  // ne doit produire qu'UNE proposition (l'indicatif se résout à chaque frappe).
  // Un texte différent (série incrémentée, correction) donne une clé différente.
  function cle(call, txMsg) {
    return String(call || '').toUpperCase() + '|' + String(txMsg || '').toUpperCase();
  }

  window.LogxCwSsbCopilote = {
    familleMode: familleMode,
    doitProposer: doitProposer,
    messagePropose: messagePropose,
    cle: cle,
    _dernierePropose: null   // clé de la dernière proposition (anti-spam runtime)
  };
})();
