/* logx_ft8_session.js — Session autonome FT8 (niveaux 3-4). LOGIQUE PURE :
 * pas de DOM, pas de réseau, pas d'horloge implicite. Décide de la VALIDITÉ
 * d'une session (reflet de l'état radio réel) et de la trame à émettre en
 * enchaînant la logique du séquenceur (logx_ft8_copilote.js). N'ÉMET PAS
 * elle-même : l'appelant (logx_ft8.html) émet et trace.
 *
 * Sécurité (tx-human-consent) : une session ne vaut QUE si l'état radio n'a pas
 * bougé depuis l'armement (bande/fréquence/mode/puissance), CAT connecté,
 * horloge OK, pas de Stop, encore armée. Toute cause -> {ok:false, raison}.
 */
(function () {
  'use strict';

  function creerSession(niveau, empreinte, sessionId) {
    empreinte = empreinte || {};
    return {
      armed: true,
      niveau: String(niveau || ''),
      radioEmpreinte: {
        band: String(empreinte.band || ''),
        dial_hz: Number(empreinte.dial_hz || 0),
        mode: String(empreinte.mode || ''),
        power_w: Number(empreinte.power_w || 0)
      },
      sessionId: String(sessionId || ''),
      txCount: 0,
      qsoActifDx: null,
      file: [],
      vu: {}
    };
  }

  // Validité = reflet de l'état radio. Ordre des causes : stop > desarmee >
  // cat > horloge > radio (la plus « dure » d'abord ; un seul motif renvoyé).
  function sessionValide(session, radioActuelle, etat) {
    session = session || {}; radioActuelle = radioActuelle || {}; etat = etat || {};
    if (etat.stop) { return { ok: false, raison: 'stop' }; }
    if (!session.armed) { return { ok: false, raison: 'desarmee' }; }
    if (!etat.cat_ok) { return { ok: false, raison: 'cat' }; }
    if (!etat.horloge_ok) { return { ok: false, raison: 'horloge' }; }
    var e = session.radioEmpreinte || {};
    var tol = Number(etat.dial_tol_hz || 0);
    if (String(radioActuelle.band || '') !== e.band ||
        String(radioActuelle.mode || '') !== e.mode ||
        Number(radioActuelle.power_w || 0) !== e.power_w ||
        Math.abs(Number(radioActuelle.dial_hz || 0) - e.dial_hz) > tol) {
      return { ok: false, raison: 'radio' };
    }
    return { ok: true, raison: '' };
  }

  // Driver N3 : enchaînement QSO complet (report→R→RR73→fin).
  // Retourne {action, message, dx} où action ∈ {'emettre','loguer','ignorer'} :
  //   - 'emettre' + message (trame FT8) + dx : émettre la réponse
  //   - 'loguer' + dx : correspondant a clôturé → proposer le log
  //   - 'ignorer' : rien à faire (pas pour moi / autre station en QSO)
  // Le module NE modifie PAS session (l'appelant applique le résultat).
  function _cop() { return (window.LogxFt8Copilote || {}); }

  function prochaineTrameQso(session, decode, monCall) {
    decode = decode || {};
    var cop = _cop();
    if (cop.estFinQso && cop.estFinQso(decode.message, monCall)) {
      return { action: 'loguer', message: '', dx: decode.dx || '' };
    }
    var rep = cop.reponseFt8 ? cop.reponseFt8(decode.message, decode.snr, monCall) : null;
    if (!rep) { return { action: 'ignorer', message: '', dx: '' }; }
    return { action: 'emettre', message: rep.message, dx: rep.dxCall };
  }

  // Contrôle de présence : filet d'arrêt pour le copilote. Désactivé par défaut
  // (presence.actif=false). Retourne true si la présence est active ET que le
  // délai d'inactivité a dépassé le seuil (nowMs - dernierPingMs > delaiPauseMs).
  // nowMs injecté pour tester.
  function doitPauserPresence(presence, nowMs) {
    presence = presence || {};
    if (!presence.actif) { return false; }
    return (Number(nowMs) - Number(presence.dernierPingMs || 0)) > Number(presence.delaiPauseMs || 0);
  }

  // Driver N4 : combine N3 (QSO en cours) et N4 (CQ + pile-up).
  // Retourne {action, message, dx, engager} où action ∈ {'emettre','loguer','cq','attendre'} :
  //   - 'emettre' : émettre (avec message + dx engagé ou QSO en cours)
  //   - 'cq' : appel CQ
  //   - 'attendre' : rien à faire (pas de CQ + pas d'appelant + pas de QSO)
  //   - 'loguer' : (délégué à N3, convertit 'loguer' → 'attendre')
  // L'appelant met à jour session.qsoActifDx/txCount/file selon le résultat.
  function prochaineAction(session, decodes, monCall, monGrid) {
    session = session || {}; decodes = decodes || [];
    var cop = _cop();
    // 1) QSO en cours : poursuivre avec un décode de CE correspondant.
    if (session.qsoActifDx) {
      var cible = String(session.qsoActifDx).toUpperCase();
      for (var i = 0; i < decodes.length; i++) {
        if (String(decodes[i].dx || '').toUpperCase() === cible) {
          var t = prochaineTrameQso(session, decodes[i], monCall);
          return { action: t.action === 'ignorer' ? 'attendre' : t.action,
                   message: t.message, dx: t.dx, engager: '' };
        }
      }
      return { action: 'attendre', message: '', dx: '', engager: '' };
    }
    // 2) Pas de QSO : un décode m'appelle-t-il ? -> engager + répondre.
    for (var j = 0; j < decodes.length; j++) {
      var t2 = prochaineTrameQso(session, decodes[j], monCall);
      if (t2.action === 'emettre') {
        return { action: 'emettre', message: t2.message, dx: t2.dx, engager: t2.dx };
      }
    }
    // 3) Personne : CQ (niveau cq) ou attendre (niveau qso).
    if (session.niveau === 'copilote_cq') {
      var cq = cop.appelCQ ? cop.appelCQ(monCall, monGrid) : null;
      if (cq) { return { action: 'cq', message: cq, dx: '', engager: '' }; }
    }
    return { action: 'attendre', message: '', dx: '', engager: '' };
  }

  window.LogxFt8Session = {
    creerSession: creerSession,
    sessionValide: sessionValide,
    prochaineTrameQso: prochaineTrameQso,
    prochaineAction: prochaineAction,
    doitPauserPresence: doitPauserPresence
  };
})();
