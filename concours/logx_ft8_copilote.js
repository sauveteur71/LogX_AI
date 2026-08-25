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

  window.LogxFt8Copilote = {
    doitProposer: doitProposer,
    messagePropose: messagePropose,
    cle: cle,
    _dernierePropose: null   // clé de la dernière proposition émise/en cours (anti-spam runtime)
  };
})();
