/* logx_tx_bar.js — Barre d'émission « ÉMISSION UNIQUE » du LOGBOOK.
 *
 * Surface CLIENT du consentement d'émission (backend logx_tx_consent, #255).
 * Principe VERROUILLÉ (F4GLD) : l'IA PRÉPARE une émission, l'HUMAIN la déclenche.
 *   1. l'IA (ou un test) appelle LogxTxBar.proposer({...})  -> POST /tx/prepare
 *   2. la barre affiche l'aperçu + un compte à rebours du jeton (30 s)
 *   3. l'humain clique ÉMETTRE                              -> POST /tx/authorize
 *      (le serveur relit le CAT réel, contrôle le jeton + garde-fou, PUIS PTT)
 *   4. « Stop TX » (arrêt d'urgence)                        -> POST /tx/stop
 *
 * Ce fichier ne DÉCLENCHE rien tout seul : il ne fait que relayer le geste
 * humain vers les endpoints. Inclusion : <script src="logx_tx_bar.js"></script>
 * (après logx_statusbar.js). Design : barre en pied de page, identité graphite
 * & cuivre (tokens --accent/--green/--red de la page).
 *
 * La LOGIQUE PURE (formatage, compte à rebours, corps de requêtes, machine
 * d'état) est exposée sur window.LogxTxBar pour être testée en V8 (test_tx_bar.py).
 */
(function () {
  'use strict';

  var TTL = 30;              // durée de vie du jeton (s) — miroir de CONSENT_TTL_S
  var DUREE_MAX_DEFAUT = 3;  // émission bornée par défaut (s) — jamais illimitée

  // ── Logique PURE (testée) ────────────────────────────────────────────────
  function fmtFreqKhz(hz) {
    var khz = (Number(hz) || 0) / 1000;
    // 1 décimale, séparateur milliers = espace, décimale = virgule (FR)
    var s = khz.toFixed(1);                       // ex. "14074.0"
    var parts = s.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
    return parts[0] + ',' + parts[1];
  }

  function secondsLeft(expiresIso, nowMs) {
    var exp = Date.parse(expiresIso);
    if (isNaN(exp)) { return 0; }
    var s = Math.round((exp - nowMs) / 1000);
    if (s < 0) { s = 0; }
    if (s > TTL) { s = TTL; }
    return s;
  }

  // Secondes entières avant l'AUTO-ÉMISSION (niveau 2), arrondies au plafond
  // pour ne jamais annoncer moins de temps qu'il n'en reste à l'opérateur pour
  // annuler (STOP TX). 0 si non armé (autoAt falsy) ou délai écoulé.
  function autoSecondsLeft(autoAt, nowMs) {
    if (!autoAt) { return 0; }
    var s = Math.ceil((autoAt - nowMs) / 1000);
    return s > 0 ? s : 0;
  }

  function ringPct(secs, ttl) {
    ttl = ttl || TTL;
    var p = Math.round((Number(secs) || 0) / ttl * 100);
    if (p < 0) { p = 0; }
    if (p > 100) { p = 100; }
    return p;
  }

  function preparePayload(em) {
    em = em || {};
    return {
      operator: em.operator || '',
      radio_id: em.radio_id || '',
      frequency_hz: em.frequency_hz,
      mode: em.mode || '',
      power_w: em.power_w,
      message: em.message || '',
      ptt_method: em.ptt_method || 'CAT',
      // Source voix phonie choisie (WAV enregistré / TTS / auto). Le serveur
      // tranche « selon ce que je dispose » (internet + IA). Sans objet en CW.
      voice_source: em.voice_source || 'auto'
    };
  }

  function authorizePayload(token, dureeMax, armed) {
    return { token: token, duree_max: dureeMax, armed: !!armed };
  }

  // Rend UNE entrée du journal d'audit (/tx/audit) en une ligne lisible (FR),
  // pour l'afficher à l'opérateur — la traçabilité gravée devient consultable.
  // Ne lève jamais (une entrée inattendue -> ligne minimale, jamais d'exception).
  function _auditHeure(ts) {
    var m = String(ts || '').match(/T(\d{2}:\d{2}:\d{2})/);
    return m ? m[1] : '';
  }
  function formatAuditLigne(e) {
    e = e || {};
    var h = _auditHeure(e.timestamp_utc);
    var cible = e.radio_id || '';
    var freq = e.frequency_hz ? (fmtFreqKhz(e.frequency_hz) + ' kHz') : '';
    var msg = e.message ? ('« ' + e.message + ' »') : '';
    var bloc = function (parts) { return parts.filter(Boolean).join(' '); };
    switch (e.event) {
      case 'TX_STOP':
        var n = Number(e.cancelled) || 0;
        return bloc([h, '· STOP TX (' + n + ' annulé' + (n > 1 ? 's' : '') + ')']);
      case 'TX_COPILOTE_QSO_LOGGED':
        var rr = (e.rst_sent || e.rst_rcvd) ? (String(e.rst_sent || '?') + '/' + String(e.rst_rcvd || '?')) : '';
        return bloc([h, '· QSO loggé (copilote)', cible ? ('→ ' + cible) : '',
                     bloc([e.band, e.mode]), rr, e.locator || '']);
      case 'TX_COPILOTE_EMISSION':
        var lbl = (e.declencheur === 'copilote_auto') ? 'copilote auto' : 'copilote';
        return bloc([h, '· Émis (' + lbl + ')', cible ? ('→ ' + cible) : '', bloc([freq, e.mode]), msg]);
      case 'TX_AUTHORIZED_AND_EXECUTED':
        return bloc([h, '· Émis (validé)', cible ? ('→ ' + cible) : '', bloc([freq, e.mode]), msg]);
      default:
        return bloc([h, '· ' + String(e.event || '?')]);
    }
  }

  // Trace d'audit d'une émission COPILOTE (POST /tx/trace). Le FT8 émet côté
  // CLIENT (envoyerMessage) hors /tx/authorize : cette trace grave quand même
  // l'émission dans le journal serveur (traçabilité verrouillée). `declencheur` :
  // 'copilote' (ÉMETTRE manuel) ou 'copilote_auto' (délai écoulé sans annulation).
  function tracePayload(em, declencheur) {
    em = em || {};
    return {
      operator: em.operator || '',
      radio_id: em.radio_id || '',     // DX visé, jamais l'humain
      frequency_hz: em.frequency_hz,
      mode: em.mode || '',
      message: em.message || '',
      declencheur: declencheur || 'copilote'
    };
  }

  // Machine d'état : STOP ramène TOUJOURS à 'idle' (arrêt d'urgence) ;
  // un refus serveur -> 'blocked' (l'humain doit re-préparer).
  function nextState(state, action) {
    if (action === 'STOP') { return 'idle'; }
    if (action === 'PREPARE') { return 'prepared'; }
    if (action === 'EMIT') { return state === 'prepared' ? 'emitting' : state; }
    if (action === 'BLOCKED') { return 'blocked'; }
    if (action === 'DONE' || action === 'EXPIRE') { return 'idle'; }
    return state;
  }

  var LogxTxBar = {
    TTL: TTL, DUREE_MAX_DEFAUT: DUREE_MAX_DEFAUT,
    fmtFreqKhz: fmtFreqKhz, secondsLeft: secondsLeft, ringPct: ringPct,
    preparePayload: preparePayload, authorizePayload: authorizePayload,
    nextState: nextState, autoSecondsLeft: autoSecondsLeft, tracePayload: tracePayload,
    formatAuditLigne: formatAuditLigne,
    _declencheur: 'copilote',   // déclencheur de la prochaine émission client (trace d'audit)
    state: 'idle', _token: null, _expires: null, _em: null, _timer: null, _armed: true,
    _voiceSource: 'auto',  // 'auto' | 'tts' | 'wav' — choix voix phonie (sélecteur)
    _onConfirm: null,      // callback client sur ÉMETTRE (ex. FT8) ; null = chemin serveur
    _autoAt: 0,            // ms (Date.now) d'auto-émission (niveau 2 copilote_auto) ; 0 = jamais
    _tick: _tick           // exposé pour test (pilotage du compte à rebours en V8)
  };

  // ── DOM + réseau (non testés unitairement, comme les autres modules) ──────
  var CSS = [
    '.txbar{position:fixed;left:0;right:0;bottom:0;z-index:60;display:none;',
    'background:linear-gradient(180deg,var(--bg3,#25272B),var(--bg2,#1D1F22));',
    'border-top:1px solid var(--border,#34363A);box-shadow:0 -10px 30px rgba(0,0,0,.28);',
    'font-family:var(--font-body,sans-serif);color:var(--ink,#E9E6DF)}',
    '.txbar.show{display:block}',
    '.txbar-in{max-width:1400px;margin:0 auto;display:flex;align-items:center;gap:14px;padding:9px 16px}',
    '.txbar .arm{display:inline-flex;align-items:center;gap:7px;font-family:var(--font-mono,monospace);',
    'font-size:.7rem;letter-spacing:1px;text-transform:uppercase;color:var(--green,#57B85F);',
    'padding:5px 10px;border-radius:999px;border:1px solid rgba(var(--green-rgb,87,184,95),.5);',
    'background:rgba(var(--green-rgb,87,184,95),.10);white-space:nowrap}',
    '.txbar .dot{width:8px;height:8px;border-radius:50%;background:var(--green,#57B85F)}',
    '.txbar .prev{display:flex;align-items:center;gap:16px;min-width:0;flex:1}',
    '.txbar .kv{display:flex;flex-direction:column;line-height:1.15;min-width:0}',
    '.txbar .kv .k{font-family:var(--font-mono,monospace);font-size:.55rem;letter-spacing:1px;',
    'text-transform:uppercase;color:var(--ink-faint,#6C6960)}',
    '.txbar .kv .v{font-family:var(--font-mono,monospace);font-size:1rem;',
    'overflow:hidden;text-overflow:ellipsis;white-space:nowrap}',
    '.txbar .kv .v.msg{color:var(--accent,#E8964A)}',
    '.txbar .sep{width:1px;align-self:stretch;background:var(--border,#34363A);margin:2px 0}',
    '.txbar .count{display:flex;flex-direction:column;align-items:center;line-height:1;white-space:nowrap}',
    '.txbar .count .n{font-family:var(--font-mono,monospace);font-size:1.1rem;color:var(--yellow,#E6B34A)}',
    '.txbar .count .l{font-family:var(--font-mono,monospace);font-size:.5rem;letter-spacing:1px;',
    'text-transform:uppercase;color:var(--ink-faint,#6C6960)}',
    '.txbar .emit{border:none;cursor:pointer;border-radius:10px;padding:11px 20px;',
    'font-family:var(--font-body,sans-serif);font-weight:800;font-size:.95rem;letter-spacing:.4px;',
    'color:#1a1205;background:linear-gradient(180deg,#F0A85C,#D98332);white-space:nowrap;',
    'box-shadow:0 4px 14px rgba(var(--accent-rgb,232,150,74),.32),inset 0 1px 0 rgba(255,255,255,.35);',
    'display:flex;flex-direction:column;align-items:center;line-height:1.1}',
    '.txbar .emit small{font-family:var(--font-mono,monospace);font-weight:400;font-size:.55rem;opacity:.82}',
    '.txbar .emit:disabled{filter:grayscale(.6) brightness(.8);cursor:not-allowed}',
    '.txbar .stop{border:1px solid rgba(var(--red-rgb,229,84,75),.55);cursor:pointer;white-space:nowrap;',
    'background:rgba(var(--red-rgb,229,84,75),.12);color:var(--red,#E5544B);font-weight:800;',
    'font-family:var(--font-body,sans-serif);text-transform:uppercase;font-size:.8rem;',
    'border-radius:10px;padding:11px 16px}',
    '.txbar .vsel{display:flex;border:1px solid var(--border,#34363A);border-radius:8px;overflow:hidden;flex-shrink:0}',
    '.txbar .vsel button{background:transparent;border:none;border-right:1px solid var(--border,#34363A);',
    'color:var(--ink-dim,#9A968C);font-family:var(--font-mono,monospace);font-size:.6rem;',
    'letter-spacing:.5px;padding:7px 9px;cursor:pointer;white-space:nowrap}',
    '.txbar .vsel button:last-child{border-right:none}',
    '.txbar .vsel button.on{background:rgba(var(--accent-rgb,232,150,74),.18);color:var(--accent,#E8964A)}',
    '.txbar .vsel button:focus-visible{outline:2px solid var(--accent,#E8964A);outline-offset:-2px}',
    '.txbar .msgline{max-width:1400px;margin:0 auto;padding:0 16px 9px;font-family:var(--font-mono,monospace);',
    'font-size:.8rem}',
    '.txbar .msgline.blocked{color:var(--red,#E5544B)}',
    '.txbar .msgline.ok{color:var(--green,#57B85F)}'
  ].join('');

  function _post(url, body) {
    return fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {})
    }).then(function (r) { return r.json().then(function (j) { return { status: r.status, json: j }; }); });
  }

  function _q(id) { return document.getElementById(id); }

  function _render() {
    var em = LogxTxBar._em || {};
    var bar = _q('rcTxBar'); if (!bar) { return; }
    bar.classList.toggle('show', LogxTxBar.state !== 'idle');
    var setTxt = function (id, v) { var e = _q(id); if (e) { e.textContent = v; } };
    setTxt('rcTxFreq', fmtFreqKhz(em.frequency_hz));
    setTxt('rcTxMode', em.mode || '—');
    setTxt('rcTxPow', (em.power_w != null ? em.power_w : '—'));
    setTxt('rcTxMsg', em.message || '—');
    var emit = _q('rcTxEmit'); if (emit) { emit.disabled = (LogxTxBar.state !== 'prepared'); }
  }

  function _tick() {
    var secs = secondsLeft(LogxTxBar._expires, Date.now());
    var n = _q('rcTxCount'); if (n) { n.textContent = secs; }
    // Niveau 2 : le délai d'auto-émission est écoulé -> émet UNE fois (sauf
    // annulation via STOP TX, qui remet _autoAt à 0 et coupe le timer).
    if (LogxTxBar._autoAt && LogxTxBar.state === 'prepared') {
      if (Date.now() >= LogxTxBar._autoAt) {
        LogxTxBar._autoAt = 0;
        LogxTxBar._declencheur = 'copilote_auto';   // trace : délai écoulé, pas un clic
        LogxTxBar._emettre();
        return;
      }
      // Affiche le décompte d'auto-émission pour que l'opérateur puisse annuler.
      _line('Émission auto dans ' + autoSecondsLeft(LogxTxBar._autoAt, Date.now())
            + ' s — STOP TX pour annuler.', '');
    }
    if (secs <= 0 && LogxTxBar.state === 'prepared') {
      LogxTxBar.state = nextState(LogxTxBar.state, 'EXPIRE');
      _clearTimer(); _render();
      _line('Jeton expiré — prépare à nouveau si tu veux émettre.', '');
    }
  }
  function _clearTimer() { if (LogxTxBar._timer) { clearInterval(LogxTxBar._timer); LogxTxBar._timer = null; } }
  function _line(txt, cls) {
    var e = _q('rcTxLine'); if (!e) { return; }
    e.textContent = txt || ''; e.className = 'msgline' + (cls ? ' ' + cls : '');
  }

  // ── API publique : l'IA appelle ceci pour PROPOSER une émission ──────────
  // `onConfirm` (optionnel) : callback CLIENT à exécuter sur ÉMETTRE, à la
  // place du chemin serveur /tx/authorize. Requis pour les modes dont
  // l'émission est CÔTÉ CLIENT (ex. FT8 : audio natif + envoyerMessage()),
  // que le garde-fou serveur voix/CW ne gère pas (modes data refusés).
  LogxTxBar.proposer = function (em, onConfirm, autoMs) {
    em = em || {};
    // La source voix choisie via le sélecteur s'applique si l'appelant (IA)
    // n'en impose pas une explicitement.
    if (!em.voice_source && LogxTxBar._voiceSource) {
      var merged = {};
      for (var k in em) { if (Object.prototype.hasOwnProperty.call(em, k)) { merged[k] = em[k]; } }
      merged.voice_source = LogxTxBar._voiceSource; em = merged;
    }
    // Chemin CLIENT : émission déclenchée par le callback local (pas le serveur).
    if (typeof onConfirm === 'function') {
      LogxTxBar._onConfirm = onConfirm;
      LogxTxBar._em = em; LogxTxBar._token = null;
      LogxTxBar._declencheur = 'copilote';   // par défaut : ÉMETTRE manuel (trace)
      // Niveau 2 (copilote_auto) : arme une auto-émission après `autoMs` ms.
      // Sinon 0 = geste humain requis. STOP TX (ou ÉMETTRE) l'annule.
      LogxTxBar._autoAt = (Number(autoMs) > 0) ? Date.now() + Number(autoMs) : 0;
      LogxTxBar._expires = new Date(Date.now() + TTL * 1000).toISOString();
      LogxTxBar.state = nextState('idle', 'PREPARE');
      _clearTimer(); LogxTxBar._timer = setInterval(_tick, 500); _tick();
      _line('Émission préparée par l’IA — à toi de valider.', '');
      _render();
      return Promise.resolve('client');
    }
    LogxTxBar._onConfirm = null; LogxTxBar._autoAt = 0;
    return _post('/tx/prepare', preparePayload(em)).then(function (r) {
      if (r.status !== 200 || !r.json.ok) {
        _line((r.json && r.json.error) || 'Préparation refusée', 'blocked'); return null;
      }
      LogxTxBar._em = em; LogxTxBar._token = r.json.token; LogxTxBar._expires = r.json.expires_at;
      LogxTxBar.state = nextState('idle', 'PREPARE');
      _clearTimer(); LogxTxBar._timer = setInterval(_tick, 500); _tick();
      _line('Émission préparée par l’IA — à toi de valider.', '');
      _render(); return r.json.token;
    });
  };

  LogxTxBar._emettre = function () {
    if (LogxTxBar.state !== 'prepared') { return; }
    LogxTxBar._autoAt = 0;   // émission en cours : plus d'auto-émission en attente
    LogxTxBar.state = nextState(LogxTxBar.state, 'EMIT'); _render();
    // Chemin CLIENT : exécute le callback local (ex. FT8 envoyerMessage()) ; le
    // garde-fou/PTT réel est celui du chemin d'émission client (déjà en place).
    if (typeof LogxTxBar._onConfirm === 'function') {
      var cb = LogxTxBar._onConfirm; LogxTxBar._onConfirm = null;
      _clearTimer();
      try {
        cb();
        LogxTxBar.state = nextState('emitting', 'DONE');
        _line('Émis (copilote).', 'ok');
        // Traçabilité verrouillée : le FT8 émet côté client (hors /tx/authorize),
        // on GRAVE quand même l'émission dans le journal d'audit serveur, au
        // moment EXACT du déclenchement (ÉMETTRE manuel ou délai écoulé). Trace
        // seule (aucun PTT) et fire-and-forget : une trace ratée ne doit JAMAIS
        // défaire une émission déjà partie.
        try { _post('/tx/trace', tracePayload(LogxTxBar._em, LogxTxBar._declencheur)); } catch (e2) {}
      } catch (e) {
        LogxTxBar.state = nextState('emitting', 'BLOCKED');
        _line('Émission refusée : ' + e, 'blocked');
      }
      _render();
      return Promise.resolve();
    }
    var body = authorizePayload(LogxTxBar._token, DUREE_MAX_DEFAUT, LogxTxBar._armed);
    return _post('/tx/authorize', body).then(function (r) {
      if (r.status === 200 && r.json.ok) {
        LogxTxBar.state = nextState('emitting', 'DONE'); _clearTimer();
        _line('Émis. Journal d’audit mis à jour.', 'ok');
      } else {
        LogxTxBar.state = nextState('emitting', 'BLOCKED');
        _line((r.json && r.json.error) || 'Émission refusée', 'blocked');
      }
      _render();
    });
  };

  LogxTxBar._stop = function () {
    _clearTimer();
    LogxTxBar._autoAt = 0;         // annule l'auto-émission en attente (niveau 2)
    LogxTxBar._onConfirm = null;   // annule aussi une proposition client (ex. FT8)
    return _post('/tx/stop', {}).then(function () {
      LogxTxBar.state = nextState(LogxTxBar.state, 'STOP');
      LogxTxBar._token = null;
      _line('Stop TX — émission annulée et PTT coupé.', 'blocked');
      _render();
    });
  };

  LogxTxBar.setArmed = function (b) { LogxTxBar._armed = !!b; };

  function _renderVoiceSel() {
    var sel = _q('rcTxVSel'); if (!sel || !sel.querySelectorAll) { return; }
    var btns = sel.querySelectorAll('button');
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle('on', btns[i].getAttribute('data-vs') === LogxTxBar._voiceSource);
    }
  }
  LogxTxBar.setVoiceSource = function (v) {
    if (v === 'wav' || v === 'tts' || v === 'auto') { LogxTxBar._voiceSource = v; _renderVoiceSel(); }
  };

  LogxTxBar.mount = function () {
    if (_q('rcTxBar') || !document.body) { return; }
    var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    var bar = document.createElement('div'); bar.className = 'txbar'; bar.id = 'rcTxBar';
    bar.innerHTML = [
      '<div class="txbar-in">',
      '<span class="arm"><span class="dot"></span>TX armé</span><div class="sep"></div>',
      '<div class="prev">',
      '<div class="kv"><span class="k">Fréq</span><span class="v"><b id="rcTxFreq">—</b> kHz</span></div>',
      '<div class="kv"><span class="k">Mode</span><span class="v" id="rcTxMode">—</span></div>',
      '<div class="kv"><span class="k">P (W)</span><span class="v" id="rcTxPow">—</span></div>',
      '<div class="sep"></div>',
      '<div class="kv" style="flex:1;min-width:0"><span class="k">Message préparé par l’IA</span>',
      '<span class="v msg" id="rcTxMsg">—</span></div></div>',
      '<div class="vsel" id="rcTxVSel" title="Source voix (phonie) — auto : selon internet/IA dispo">',
      '<button type="button" data-vs="auto">Auto</button>',
      '<button type="button" data-vs="tts">Voix IA</button>',
      '<button type="button" data-vs="wav">Mon WAV</button></div>',
      '<div class="count"><span class="n" id="rcTxCount">0</span><span class="l">jeton s</span></div>',
      '<button class="emit" id="rcTxEmit" disabled>ÉMETTRE<small>geste requis</small></button>',
      '<button class="stop" id="rcTxStop">STOP TX</button>',
      '</div><div class="msgline" id="rcTxLine"></div>'
    ].join('');
    document.body.appendChild(bar);
    var e = _q('rcTxEmit'); if (e) { e.addEventListener('click', LogxTxBar._emettre); }
    var s = _q('rcTxStop'); if (s) { s.addEventListener('click', LogxTxBar._stop); }
    var sel = _q('rcTxVSel');
    if (sel) {
      sel.addEventListener('click', function (ev) {
        var vs = ev.target && ev.target.getAttribute && ev.target.getAttribute('data-vs');
        if (vs) { LogxTxBar.setVoiceSource(vs); }
      });
    }
    _renderVoiceSel();
  };

  window.LogxTxBar = LogxTxBar;
  if (typeof document !== 'undefined' && document.addEventListener) {
    document.addEventListener('DOMContentLoaded', function () { LogxTxBar.mount(); });
  }
})();
