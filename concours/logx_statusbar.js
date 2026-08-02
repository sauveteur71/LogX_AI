/* ─────────────────────────────────────────────────────────────────────────────
   LogX AI — Barre de statut permanente (Phase 1 UX)
   Injectée sur toutes les pages : concours actif · temps restant ·
   dernière sauvegarde · dernier check règlements.
   Inclusion : <script src="logx_statusbar.js"></script> (après la nav).
   S'appuie sur les variables CSS communes des pages (--bg2, --border, ...).
   ──────────────────────────────────────────────────────────────────────────── */
(function(){
  'use strict';

  // ── rcPoll : minuteurs de rafraîchissement suspendus onglet masqué ─────────
  // Ordonnanceur commun à la barre ET aux pages qui restent ouvertes en
  // permanence (propagation, chasse). setInterval nu continue d'interroger le
  // serveur — et donc les sources externes — dans un onglet masqué : sur un
  // poste qui garde ces pages ouvertes à côté du log, c'est du trafic
  // permanent que personne ne regarde (mesuré : 12 requêtes en 46 s sur une
  // page CHASSE masquée, 27 en 68 s sur PROPAGATION).
  //   • document.hidden = true  → tous les minuteurs sont ARRÊTÉS (clearInterval,
  //     pas un simple « return » : ni requête, ni réveil du minuteur).
  //   • retour à l'écran       → réarmés, et ceux dont l'échéance est dépassée
  //     sont rejoués TOUT DE SUITE. Sans ce rattrapage, revenir sur l'onglet
  //     afficherait des données périmées jusqu'au prochain tick — inacceptable
  //     pour les balises (5 s) ou les spots.
  // Volontairement défini AVANT le garde-fou file: ci-dessous : c'est une
  // fonction utilitaire, les pages doivent pouvoir s'y fier sans condition.
  // Les minuteurs purement locaux (compte à rebours, extrapolation du timer
  // de changement de bande, horodatage de sauvegarde) ne passent PAS par
  // rcPoll : ils ne font aucune requête, et le navigateur les bride déjà.
  const _polls = [];
  function _armPoll(p){
    if (p.timer) return;
    p.timer = setInterval(function(){ p.last = Date.now(); p.fn(); }, p.ms);
  }
  function rcPoll(fn, ms){
    const p = { fn: fn, ms: ms, timer: null, last: Date.now() };
    _polls.push(p);
    if (!document.hidden) _armPoll(p);
    return p;
  }
  window.rcPoll = rcPoll;
  document.addEventListener('visibilitychange', function(){
    if (document.hidden){
      _polls.forEach(function(p){
        if (p.timer){ clearInterval(p.timer); p.timer = null; }
      });
      return;
    }
    const now = Date.now();
    _polls.forEach(function(p){
      _armPoll(p);
      if (now - p.last >= p.ms){ p.last = now; try { p.fn(); } catch(e){} }
    });
  });

  if (location.protocol === 'file:') return; // pages affichent déjà leur erreur

  // ── Helpers ────────────────────────────────────────────────────────────────
  function getConfig(){
    try { return JSON.parse(localStorage.getItem('logx_config') || '{}'); }
    catch(e){ return {}; }
  }
  const pad = n => String(n).padStart(2, '0');

  // ── Traduction ─────────────────────────────────────────────────────────────
  // Le gros du texte de cette barre est injecté par innerHTML : le
  // MutationObserver de logx_i18n.js le traduit tout seul, une entrée de
  // dictionnaire suffit. Ces deux raccourcis servent aux DEUX cas qu'aucun
  // observateur ne peut atteindre :
  //   • ce qui sort du DOM — prompt(), confirm(), et `el.title = …` posé
  //     depuis le JS (l'observateur ne surveille pas les attributs) ;
  //   • ce qui est ASSEMBLÉ avec une valeur (`'… (depuis ' + n + ' min)'`) :
  //     la chaîne finale ne pourra jamais être une clé, donc on traduit le
  //     gabarit et on y réinjecte la valeur.
  // Repli identité si logx_i18n.js n'est pas encore chargé — cette barre est
  // incluse AVANT lui sur plusieurs pages, et rien ne doit dépendre de l'ordre.
  const rcT = s => (window.rcT ? window.rcT(s) : s);
  const rcTf = (s, p) => (window.rcTf ? window.rcTf(s, p)
    : String(s).replace(/\{(\w+)\}/g, (m, k) => (p && k in p) ? p[k] : m));

  // ── Création du DOM ────────────────────────────────────────────────────────
  const bar = document.createElement('div');
  bar.id = 'rcStatusBar';
  bar.innerHTML = `
    <style>
      #rcStatusBar{display:flex;align-items:center;gap:0;flex-wrap:wrap;
        background:var(--bg2,#0D0E1A);border-bottom:1px solid var(--border,#2B2F4A);
        font-family:var(--font-mono,'Share Tech Mono',monospace);font-size:14px;
        color:var(--muted,#A9B0C8);padding:0 12px;min-height:34px}
      #rcStatusBar .rcsb-item{display:flex;align-items:center;gap:6px;
        padding:6px 14px;border-right:1px solid var(--border,#2B2F4A);white-space:nowrap}
      #rcStatusBar .rcsb-item:last-child{border-right:none}
      #rcStatusBar .rcsb-val{color:var(--text,#E9ECF5)}
      #rcStatusBar .rcsb-contest{color:var(--accent,#FF5030);font-weight:700;letter-spacing:1px}
      #rcStatusBar .rcsb-running{color:var(--green,#00FF88)}
      #rcStatusBar .rcsb-soon{color:var(--yellow,#FFD60A)}
      #rcStatusBar .rcsb-over{color:var(--red,#FF2D55)}
      #rcStatusBar a{color:inherit;text-decoration:none}
      #rcStatusBar a:hover{color:var(--accent2,#00D4FF)}
      @media (max-width:900px){ #rcStatusBar .rcsb-item{padding:4px 7px} }
      #rcsbLayoutDD{position:absolute;top:100%;left:0;z-index:2000;min-width:260px;
        background:var(--bg2,#0D0E1A);border:1px solid var(--border,#2B2F4A);border-radius:0 0 8px 8px;
        box-shadow:0 8px 24px rgba(0,0,0,.5);padding:10px;font-size:13px;white-space:normal}
      #rcsbLayoutDD .rcsb-panel-row,#rcsbLayoutDD .rcsb-layout-row{display:flex;align-items:center;gap:6px;padding:4px 0}
      #rcsbLayoutDD .rcsb-panel-row span, #rcsbLayoutDD .rcsb-layout-row span{flex:1}
      #rcsbLayoutDD button{font-family:inherit;font-size:11px;background:var(--bg3,#14172C);
        color:var(--text,#E9ECF5);border:1px solid var(--border,#2B2F4A);border-radius:4px;
        padding:3px 8px;cursor:pointer}
      #rcsbLayoutDD button:hover{border-color:var(--accent2,#00D4FF);color:var(--accent2,#00D4FF)}
      #rcsbLayoutDD input{font-family:inherit;font-size:12px;background:var(--bg3,#14172C);
        color:var(--text,#E9ECF5);border:1px solid var(--border,#2B2F4A);border-radius:4px;
        padding:4px 6px;width:100%}
      #rcsbLayoutDD hr{border:none;border-top:1px solid var(--border,#2B2F4A);margin:8px 0}
      #rcsbLayoutDD .rcsb-dd-title{color:var(--muted,#A9B0C8);letter-spacing:1px;font-size:11px;margin-bottom:4px}
      #rcsbUpdateItem{display:none;cursor:pointer;position:relative;color:var(--yellow,#FFD60A);font-weight:700}
      #rcsbUpdateDD{position:absolute;top:100%;right:0;z-index:2000;min-width:280px;
        background:var(--bg2,#0D0E1A);border:1px solid var(--border,#2B2F4A);border-radius:0 0 8px 8px;
        box-shadow:0 8px 24px rgba(0,0,0,.5);padding:10px;font-size:13px;white-space:normal;color:var(--text,#E9ECF5)}
      #rcsbUpdateDD .rcsb-upd-notes{max-height:120px;overflow-y:auto;color:var(--muted,#A9B0C8);
        font-size:12px;white-space:pre-wrap;margin:6px 0;border-top:1px solid var(--border,#2B2F4A);
        border-bottom:1px solid var(--border,#2B2F4A);padding:6px 0}
      #rcsbUpdateDD .rcsb-upd-row{display:flex;gap:6px;margin-top:8px}
      #rcsbUpdateDD button, #rcsbUpdateDD a.rcsb-upd-btn{font-family:inherit;font-size:12px;
        background:var(--accent,#FF5030);color:#fff;border:none;border-radius:4px;
        padding:6px 10px;cursor:pointer;text-decoration:none;display:inline-block;text-align:center;flex:1}
      #rcsbUpdateDD button.rcsb-upd-secondary{background:var(--bg3,#14172C);color:var(--text,#E9ECF5);
        border:1px solid var(--border,#2B2F4A);flex:none}
      #rcsbUpdateDD .rcsb-upd-progress{height:6px;border-radius:3px;background:var(--bg3,#14172C);
        overflow:hidden;margin-top:8px}
      #rcsbUpdateDD .rcsb-upd-progress-fill{height:100%;background:var(--green,#00FF88);width:0%;transition:width .3s}
    </style>
    <div class="rcsb-item" title="Concours actif (choisi dans CONFIG)">
      🏁 <span class="rcsb-contest" id="rcsbContest">aucun concours</span>
    </div>
    <div class="rcsb-item" title="Temps restant de l'épreuve (dates de l'étape CONCOURS)">
      ⏱ <span class="rcsb-val rc-i18n-live" id="rcsbTime">—</span>
    </div>
    <div class="rcsb-item" title="Dernier backup automatique du log (toutes les 5 min sur la page Logbook)">
      💾 <span class="rcsb-val" id="rcsbSave">—</span>
    </div>
    <div class="rcsb-item" title="Météo solaire (SFI = flux solaire, K = agitation géomagnétique) — clic : détail complet + conditions par bande">
      <a href="logx_propagation.html">☀️ <span class="rcsb-val" id="rcsbSolar">—</span></a>
    </div>
    <div class="rcsb-item" id="rcsbBeaconItem" title="Balise NCDXF/IBP active maintenant sur 20m (réseau mondial de 18 balises, rotation de 10 s) — clic : les 5 bandes + panneau complet">
      <a href="logx_propagation.html#beaconPanel">📻 <span class="rcsb-val" id="rcsbBeacon">—</span></a>
    </div>
    <div class="rcsb-item" id="rcsbStormItem" style="display:none">
      <a id="rcsbStormLink" href="https://www.blitzortung.org/fr/live_lightning_maps.php?map=0"
         target="_blank" rel="noopener noreferrer">
        <span id="rcsbStormIcon">⚡</span> <span class="rcsb-val" id="rcsbStorm">—</span></a>
    </div>
    <div class="rcsb-item" id="rcsbNetworkItem" style="display:none"
         title="Un service en ligne est temporairement injoignable — l'appli continue de fonctionner en local, nouvelle tentative automatique dès que possible">
      📡 <span class="rcsb-val" id="rcsbNetworkText" style="color:var(--red,#FF2D55)">—</span>
    </div>
    <div class="rcsb-item" title="Rate meter : QSO/h sur 10 min glissantes (extrapolé) et 60 min glissantes. Clic : fixer un objectif — vert au-dessus, rouge en dessous."
         id="rcsbRateItem" style="cursor:pointer">
      ⚡ <span class="rcsb-val" id="rcsbRate">—</span>
    </div>
    <div class="rcsb-item" id="rcsbBandChangeItem" style="display:none"
         title="Règle des 10 minutes (Multi-Single, CQ WW et concours similaires) : un changement de bande n'est autorisé qu'une fois toutes les 10 minutes. Décompte depuis le dernier changement de bande loggué.">
      🔄 <span class="rcsb-val rc-i18n-live" id="rcsbBandChange">—</span>
    </div>
    <div class="rcsb-item" title="Dernière vérification automatique des règlements par le serveur">
      📄 <a href="logx_calendrier.html" id="rcsbRules">règlements : —</a>
    </div>
    <div class="rcsb-item" id="rcsbLayoutItem" style="cursor:pointer;position:relative" title="Panneaux détachables + dispositions nommées (comme un espace de travail à onglets, en fenêtres séparées)">
      🗔 <span class="rcsb-val">DISPOSITION</span>
      <div id="rcsbLayoutDD" style="display:none"></div>
    </div>
    <div class="rcsb-item" id="rcsbUpdateItem" title="Une nouvelle version de LogX AI est disponible">
      🆕 <span id="rcsbUpdateLabel">mise à jour</span>
      <div id="rcsbUpdateDD" style="display:none"></div>
    </div>
    <div class="rcsb-item" title="Version de LogX AI installée — à indiquer en cas de bug">
      🏷️ <span class="rcsb-val" id="rcsbVersion">—</span>
    </div>
    <div class="rcsb-item" id="rcsbReportItem" style="cursor:pointer"
         title="Ouvre une Issue GitHub pré-remplie (version + plateforme) pour signaler un problème">
      🐛 <span class="rcsb-val">signaler un problème</span>
    </div>`;

  // ── Rate meter (A3) : QSO/h 10 min extrapolé + 60 min, objectif cliquable ──
  // Le même appel /coach/state porte aussi `band_change` (règle des 10 min
  // multi-op) — un seul poll partagé plutôt qu'une requête dédiée de plus.
  let _bandChange = null;
  let _bandChangeFetchedAt = 0;
  function nudgesOn(){ try { return localStorage.getItem('rc_live_nudges') === '1'; } catch(e){ return false; } }
  function refreshRate(){
    // Nudges live (OFF par défaut) : on ne demande le calcul serveur que si
    // l'opérateur l'a activé — sinon `?nudges=1` absent, le serveur ne dépense
    // rien. Même poll partagé, aucune boucle réseau supplémentaire.
    var url = '/coach/state?lang=' + encodeURIComponent((typeof rcLang === 'function') ? rcLang() : 'fr');
    if (nudgesOn()) url += '&nudges=1';
    fetch(url).then(function(r){ return r.ok ? r.json() : null; })
      .then(function(st){
        if (!st) return;
        if (st.nudge) maybeShowNudge(st.nudge);
        const el = document.getElementById('rcsbRate');
        if (el){
          const s = st.stats || {};
          const running = st.clock && st.clock.status === 'en_cours';
          const goal = parseInt(localStorage.getItem('rc_rate_goal') || '0', 10);
          if (!running){ el.textContent = '—'; el.style.color = ''; }
          else {
            el.textContent = (s.rate_10min || 0) + '/h (10min) · '
                           + (s.rate_60min || 0) + '/h (60min)'
                           + (goal ? ' · obj ' + goal : '');
            el.style.color = goal
              ? ((s.rate_10min || 0) >= goal ? 'var(--green,#00FF88)' : 'var(--red,#FF2D55)')
              : '';
          }
        }
        _bandChange = st.band_change || null;
        _bandChangeFetchedAt = Date.now();
        tickBandChange();
      }).catch(function(){});
  }

  // ── Nudges IA événementiels : UNE phrase d'action en toast, au bon moment ──
  // Débounce DUR (≥5 min) + dédup par signature d'événement : jamais deux fois
  // le même, jamais une rafale (fatigue d'alerte). Le serveur ne renvoie un
  // `nudge` que si l'option est active (voir refreshRate/`?nudges=1`).
  var NUDGE_DEBOUNCE_MS = 5 * 60 * 1000;
  function maybeShowNudge(nudge){
    if (!nudge || !nudge.text || !nudge.sig) return;
    var last = {};
    try { last = JSON.parse(localStorage.getItem('rc_nudge_last') || '{}'); } catch(e){}
    var now = Date.now();
    if (last.sig === nudge.sig) return;                              // événement déjà montré
    if (last.ts && (now - last.ts) < NUDGE_DEBOUNCE_MS) return;      // débounce dur
    try { localStorage.setItem('rc_nudge_last', JSON.stringify({sig: nudge.sig, ts: now})); } catch(e){}
    showNudgeToast(nudge);
  }
  function escNudge(s){ var d = document.createElement('div'); d.textContent = String(s == null ? '' : s); return d.innerHTML; }
  function showNudgeToast(nudge){
    var el = document.getElementById('rcsbNudgeToast');
    if (!el){
      el = document.createElement('div');
      el.id = 'rcsbNudgeToast';
      el.style.cssText = 'position:fixed;left:50%;transform:translateX(-50%);bottom:52px;z-index:99999;'
        + 'max-width:min(560px,92vw);background:var(--bg2,#12172e);color:var(--text,#dfe6ff);'
        + 'border:1px solid var(--accent2,#22e0ff);border-left:4px solid var(--accent2,#22e0ff);'
        + 'border-radius:8px;padding:10px 14px;font-family:var(--font-mono,monospace);font-size:14px;'
        + 'line-height:1.5;box-shadow:0 8px 30px rgba(0,0,0,.5);display:flex;gap:10px;align-items:center';
      document.body.appendChild(el);
    }
    el.innerHTML = '<span style="flex:1">🤖 ' + escNudge(nudge.text) + '</span>'
      + '<button aria-label="fermer" style="cursor:pointer;border:0;background:transparent;'
      + 'color:var(--muted,#7a86b6);font-size:18px;line-height:1">✕</button>';
    el.querySelector('button').onclick = function(){ el.remove(); };
    el.style.display = 'flex';
    // Alerte réglable par type (#5) : un nudge « nouvelle cible » sonne comme un
    // nouveau pays, un nudge de rythme comme le type « rate ». Chacun réglable
    // (son + voix) dans CONFIG ; à défaut, repli sur la lecture auto globale.
    var _nsig = String(nudge.sig || '');
    var _ntype = _nsig.indexOf('target:') === 0 ? 'new_dxcc' : 'rate';
    if (window.rcAlert) window.rcAlert(_ntype, nudge.text);
    else if (window.rcSpeak) window.rcSpeak(nudge.text);
    clearTimeout(el._auto);
    el._auto = setTimeout(function(){ if (el && el.parentNode) el.remove(); }, 30000);
  }

  // ── Lecture vocale HORS-LIGNE (#6) : l'agent PARLE via speechSynthesis, avec
  // les voix SAPI LOCALES (localService) — aucune clé, aucun réseau, jamais la
  // radio (casque de suivi). En pile-up, entendre une alerte la tête baissée
  // peut faire décrocher le contact. Exposé en window.rcSpeak pour toutes les
  // pages (carte, barre d'état). Régex volontairement SIMPLES (pas de lookbehind
  // ni \p{} ni flag u) : elles sont sûres partout, y compris en test.
  var _rcVoices = [];
  function _rcLoadVoices(){ try { _rcVoices = (window.speechSynthesis ? speechSynthesis.getVoices() : []) || []; } catch(e){ _rcVoices = []; } }
  if (window.speechSynthesis){
    _rcLoadVoices();
    try { speechSynthesis.onvoiceschanged = _rcLoadVoices; } catch(e){}   // getVoices() se peuple en asynchrone
  }
  function _rcPickVoice(){
    var lang = ((typeof rcLang === 'function') ? rcLang() : 'fr').toLowerCase();
    var local = _rcVoices.filter(function(v){ return v.localService; });  // 100% hors-ligne
    var pool = local.length ? local : _rcVoices;
    var same = pool.filter(function(v){ return (v.lang || '').toLowerCase().indexOf(lang) === 0; });
    return same[0] || pool[0] || null;
  }
  var _RC_EMO = ['⚡','🌟','🎯','📡','🏆','📶','📋','🌍','🤖','🔊','🔇','✅','⚠️','❌','ℹ️','📴','🧠','⏱','⏳','🏁','💡','🔴','🟡','🌤','🇫🇷','🆕','🔲','🌐','▶','⏹'];
  function _rcShorten(text){
    var s = String(text == null ? '' : text).replace(/\s+/g, ' ').trim();
    for (var i = 0; i < _RC_EMO.length; i++){ s = s.split(_RC_EMO[i]).join(''); }
    s = s.replace(/\s+/g, ' ').trim();
    var idx = s.search(/[.!?]/);                       // 1re phrase seulement (pas les 4000 tokens)
    if (idx >= 0 && idx < s.length - 1) s = s.slice(0, idx + 1);
    if (s.length > 180) s = s.slice(0, 180);
    return s.trim();
  }
  window.rcTtsEnabled = function(){ try { return localStorage.getItem('rc_tts') === '1'; } catch(e){ return false; } };
  window.rcSpeak = function(text, force){
    if (!window.speechSynthesis) return;
    if (!force && !window.rcTtsEnabled()) return;      // auto-lecture seulement si activée
    var phrase = _rcShorten(text);
    if (!phrase) return;
    try {
      speechSynthesis.cancel();                        // ne pas empiler les tirades
      var u = new SpeechSynthesisUtterance(phrase);
      // Affecter la voix dans un try SÉPARÉ : si le setter la refuse, on garde
      // la voix par défaut plutôt que de perdre TOUTE la lecture.
      try { var v = _rcPickVoice(); if (v){ u.voice = v; u.lang = v.lang; } } catch(e){}
      u.rate = 1.0; u.volume = 1.0;
      speechSynthesis.speak(u);
    } catch(e){}
  };

  // ── ALERTES : SON + VOIX RÉGLABLES PAR TYPE (#5) ───────────────────────────
  // Chaque type d'alerte (nouveau pays, carré, besoin LoTW, rate…) peut être
  // réglé indépendamment : un SON choisi (motif WebAudio, 100 % hors-ligne, pas
  // de fichier) et/ou une ANNONCE VOCALE (« Nouveau pays détecté »). Réglages
  // par poste dans localStorage rc_alerts. Exposé window.rcAlert pour toutes les
  // pages ; les sites d'alerte (FT8, nudges) appellent rcAlert au lieu de bipper
  // en dur, pour que le réglage vaille partout.
  var RC_ALERT_TYPES = [
    { id: 'new_dxcc', label: 'Nouveau pays (DXCC)',      voice: 'Nouveau pays détecté',        sound: 'carillon' },
    { id: 'new_dept', label: 'Nouveau département',       voice: 'Nouveau département',          sound: 'montant' },
    { id: 'new_grid', label: 'Nouveau carré',            voice: 'Nouveau carré',               sound: 'aigu' },
    { id: 'lotw_need', label: 'Besoin LoTW',             voice: 'Besoin LoTW',                 sound: 'double' },
    { id: 'mult',     label: 'Nouveau multiplicateur',   voice: 'Nouveau multiplicateur',      sound: 'grave' },
    { id: 'rate',     label: 'Rythme (rate)',            voice: 'Attention au rythme',         sound: 'grave' },
  ];
  // Motifs : liste de notes [fréquence, durée ms, décalage ms (optionnel)].
  var RC_ALERT_SOUNDS = {
    aucun:    [],
    aigu:     [[1318, 90]],
    grave:    [[660, 130]],
    double:   [[1174, 80], [1174, 80, 120]],
    montant:  [[880, 90], [1175, 120, 110]],
    carillon: [[988, 90], [1319, 90, 110], [1568, 150, 220]],
    sirene:   [[700, 90], [1200, 100, 90], [700, 100, 190]],
  };
  var _rcAudio = null;
  function _rcBeep(freq, dur){
    try {
      if (!_rcAudio) _rcAudio = new (window.AudioContext || window.webkitAudioContext)();
      var ctx = _rcAudio, osc = ctx.createOscillator(), g = ctx.createGain();
      osc.connect(g); g.connect(ctx.destination); osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      g.gain.setValueAtTime(0.18, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + dur / 1000);
      osc.start(ctx.currentTime); osc.stop(ctx.currentTime + dur / 1000 + 0.05);
    } catch (e) {}
  }
  window.rcTone = function(name){
    var pat = RC_ALERT_SOUNDS[name];
    if (!pat || !pat.length) return;
    pat.forEach(function(n){
      var delay = n[2] || 0;
      if (delay) setTimeout(function(){ _rcBeep(n[0], n[1]); }, delay);
      else _rcBeep(n[0], n[1]);
    });
  };
  function _rcAlertDefaults(){
    var d = {};
    RC_ALERT_TYPES.forEach(function(t){ d[t.id] = { voice: false, sound: t.sound }; });
    return d;
  }
  function _rcAlertPrefs(){
    var d = _rcAlertDefaults();
    try {
      var saved = JSON.parse(localStorage.getItem('rc_alerts') || '{}');
      Object.keys(d).forEach(function(id){
        if (saved[id]) {
          if (typeof saved[id].voice === 'boolean') d[id].voice = saved[id].voice;
          if (typeof saved[id].sound === 'string' && RC_ALERT_SOUNDS[saved[id].sound]) d[id].sound = saved[id].sound;
        }
      });
    } catch (e) {}
    return d;
  }
  // API pour l'écran CONFIG (liste des types, sons disponibles, prefs).
  window.rcAlertTypes = function(){ return RC_ALERT_TYPES.map(function(t){ return { id: t.id, label: t.label }; }); };
  window.rcAlertSounds = function(){ return Object.keys(RC_ALERT_SOUNDS); };
  window.rcAlertPrefs = _rcAlertPrefs;
  window.rcAlertVoiceFor = function(id){ var t = RC_ALERT_TYPES.filter(function(x){ return x.id === id; })[0]; return t ? t.voice : ''; };
  // Déclenche une alerte : son (selon le type) + voix (si activée pour ce type,
  // OU si la lecture auto globale 🔊 est active — le bouton global continue de
  // tout lire, un type peut en plus forcer la voix même quand il est coupé).
  window.rcAlert = function(id, voiceText){
    var p = _rcAlertPrefs()[id];
    if (!p) { p = { voice: false, sound: 'aigu' }; }
    try { window.rcTone(p.sound); } catch (e) {}
    var speak = p.voice || (window.rcTtsEnabled && window.rcTtsEnabled());
    if (speak && window.rcSpeak) {
      window.rcSpeak(voiceText || window.rcAlertVoiceFor(id), true);
    }
  };

  bar.addEventListener('click', function(e){
    if (!e.target.closest('#rcsbRateItem')) return;
    const cur = localStorage.getItem('rc_rate_goal') || '0';
    const v = prompt(rcT('Objectif de rate (QSO/h) — 0 pour désactiver :'), cur);
    if (v !== null){
      localStorage.setItem('rc_rate_goal', String(parseInt(v, 10) || 0));
      refreshRate();
    }
  });

  // ── Compte à rebours « règle des 10 minutes » (Multi-Single) ──────────────
  // Visible seulement en multi-op (plusieurs opérateurs déclarés, hors mode
  // simple) — un opérateur seul ne peut de toute façon être que sur une
  // bande à la fois, la règle ne le concerne jamais. Le compte à rebours lui-
  // même est calculé côté serveur (logx_coach.band_change_timer) à partir du
  // log partagé ; on l'extrapole seconde par seconde ici entre deux polls
  // (60 s, cf. boot()) pour un affichage fluide sans requête supplémentaire.
  function isMultiOp(){
    const cfg = getConfig();
    return cfg.usage_mode !== 'simple' && (cfg.operators || []).length > 1;
  }
  // Exposée pour réutilisation par logx_logbook.js (vue Partner, cf.
  // _isMultiOp() dans ce fichier) — évite d'avoir DEUX implémentations qui
  // pourraient diverger silencieusement. logx_statusbar.js est chargé avant
  // logx_logbook.js sur logx_logbook.html donc déjà disponible à l'usage ;
  // logx_logbook.js garde un repli local au cas où il tourne sans cette barre.
  window.rcIsMultiOp = isMultiOp;
  function tickBandChange(){
    const item = document.getElementById('rcsbBandChangeItem');
    const el = document.getElementById('rcsbBandChange');
    if (!item || !el) return;
    if (!isMultiOp() || !_bandChange || !_bandChange.current_band){
      item.style.display = 'none';
      return;
    }
    item.style.display = 'flex';
    const band = _bandChange.current_band;
    if (_bandChange.ready){
      el.textContent = band + ' MHz — changement libre';
      el.style.color = 'var(--green,#00FF88)';
      return;
    }
    const drift = (Date.now() - _bandChangeFetchedAt) / 1000;
    const remaining = Math.max(0, Math.round(_bandChange.remaining_s - drift));
    if (remaining <= 0){
      el.textContent = band + ' MHz — changement libre';
      el.style.color = 'var(--green,#00FF88)';
      return;
    }
    const m = Math.floor(remaining / 60);
    const s = remaining % 60;
    el.textContent = band + ' MHz — ' + m + ':' + pad(s) + ' avant changement';
    el.style.color = remaining <= 60 ? 'var(--yellow,#FFD60A)' : 'var(--muted,#A9B0C8)';
  }
  refreshRate();
  rcPoll(refreshRate, 60 * 1000);

  // ── Météo solaire (badge compact, toutes pages) ────────────────────────────
  // Réutilise /data/propagation (déjà servi côté serveur pour la page
  // propagation et le contexte IA, cache 15 min) — pas de nouvel appel réseau
  // ajouté au budget de l'app, juste un affichage permanent au lieu de devoir
  // naviguer vers la page dédiée pour voir SFI/K.
  function refreshSolar(){
    fetch('/data/propagation').then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        const el = document.getElementById('rcsbSolar');
        if (!el) return;
        const s = (d && d.solar) || {};
        if (s.sfi === undefined && s.k_index === undefined){ el.textContent = '—'; el.style.color = ''; return; }
        el.textContent = 'SFI ' + (s.sfi != null && s.sfi !== '' ? s.sfi : '—')
                        + ' · K ' + (s.k_index != null && s.k_index !== '' ? s.k_index : '—');
        const k = parseFloat(s.k_index);
        el.style.color = !isNaN(k)
          ? (k <= 2 ? 'var(--green,#00FF88)' : k <= 4 ? 'var(--yellow,#FFD60A)' : 'var(--red,#FF2D55)')
          : '';
      }).catch(function(){});
  }
  refreshSolar();
  rcPoll(refreshSolar, 15 * 60 * 1000);        // aligné sur le cache serveur (15 min)

  // ── Balise NCDXF/IBP active maintenant (badge compact, toutes pages) ──────
  // Découvrabilité du réseau de balises : un utilisateur qui ne va jamais
  // sur la page Propagation ne sait pas que la fonctionnalité existe. Ce
  // badge réutilise /beacons/now (déjà servi pour le panneau complet de
  // logx_propagation.html, calcul pur sans réseau) — aucune logique dupliquée,
  // juste un affichage permanent + un lien ancré vers le panneau détaillé.
  // On affiche la bande 20m comme repère (bande d'écoute la plus universelle)
  // et le détail des 5 bandes apparaît dans l'infobulle au survol.
  // Mutualisation réelle : ce minuteur est le SEUL à interroger /beacons/now.
  // La réponse est rediffusée via l'événement 'logx:beacons' pour que le
  // panneau complet de logx_propagation.html s'y abonne au lieu de lancer son
  // propre poll à 5 s (sinon 2 requêtes identiques toutes les 5 s sur la page
  // justement destinée à rester ouverte en permanence). Le drapeau est posé
  // AVANT le 1er fetch : la barre est incluse avant le script de la page, qui
  // peut donc tester sa présence de façon fiable.
  window.logxBeaconFeed = true;
  function refreshBeacon(){
    fetch('/beacons/now').then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        if (d){
          try { document.dispatchEvent(new CustomEvent('logx:beacons', { detail: d })); }
          catch(e){}
        }
        const el = document.getElementById('rcsbBeacon');
        const item = document.getElementById('rcsbBeaconItem');
        if (!el || !item) return;
        const list = (d && d.beacons) || [];
        if (!list.length){ el.textContent = '—'; return; }
        const main = list.find(function(b){ return b.band === '20m'; }) || list[0];
        el.textContent = main.call + ' ' + main.band;
        item.title = rcTf('Balises NCDXF/IBP actives maintenant : {liste} — clic : panneau complet + écoute',
          {liste: list.map(function(b){
            return b.band + ' ' + b.call + ' (' + b.qth + ')';
          }).join(' · ')});
      }).catch(function(){});
  }
  refreshBeacon();
  rcPoll(refreshBeacon, 5 * 1000);             // balises : changent toutes les 10 s

  // ── Foudre / orage au QTH (pastille d'alerte, toutes pages) ───────────────
  // Remplace l'ancien panneau « FOUDRE EN DIRECT » de logx_propagation.html :
  // une iframe Blitzortung de 420 px de haut, occupée en permanence par une
  // carte qu'on ne consulte qu'en cas d'orage, et visible seulement quand on
  // était SUR la page propagation — donc jamais au moment où ça compte, c'est-
  // à-dire pendant qu'on logue. La sécurité antenne devient donc une pastille
  // présente sur TOUTES les pages, et la carte tierce n'est plus encadrée mais
  // ouverte dans un onglet séparé (le frame-buster de blitzortung.org, qui
  // avait déjà détourné l'onglet entier, n'a plus de prise du tout).
  //
  // Source : /data/weather (Open-Meteo, cache serveur 10 min, jamais bloquant)
  // — déjà servi pour l'écran mural et le logbook, aucun nouvel appel ajouté
  // au budget réseau. On lit le booléen `storm` (codes WMO 95/96/99 isolés
  // côté serveur) plutôt que de chercher le mot « ORAGE » dans la phrase
  // d'alerte française, qui ne survivrait ni à un reformulage ni à la
  // traduction de l'interface.
  // Reprise courte après un cache serveur froid — justification sous la
  // fonction, avec celle du 1er appel dans boot().
  const STORM_RETRY_MS = 3000;
  const STORM_RETRY_MAX = 5;
  let _stormRetries = 0;
  // Point d'entrée « normal » (boot + tic rcPoll) : ouvre un nouveau budget de
  // reprises rapprochées. Les reprises, elles, rappellent fetchStorm() pour ne
  // pas remettre le compteur à zéro et boucler indéfiniment.
  function refreshStorm(){
    _stormRetries = STORM_RETRY_MAX;
    fetchStorm();
  }
  function fetchStorm(){
    fetch('/data/weather').then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        const item = document.getElementById('rcsbStormItem');
        const el = document.getElementById('rcsbStorm');
        const icon = document.getElementById('rcsbStormIcon');
        if (!item || !el || !icon) return;
        // Pas de locator, ou cache encore vide au tout premier chargement :
        // on n'affiche rien plutôt qu'un « — » que l'opérateur prendrait pour
        // une absence d'orage constatée.
        if (!d || !d.ok){
          item.style.display = 'none';
          // ... mais on RÉESSAIE tout de suite, quelques fois. Le serveur ne
          // préchauffe pas son cache météo : get_weather_cached() (logx_weather
          // .py) répond ok:false + stale:true au tout premier appel du process
          // ET après tout changement de locator, en lançant seulement un
          // rafraîchissement de fond — la donnée arrive ~1 à 2 s plus tard.
          // Sans reprise, le seul autre déclencheur est le tic rcPoll : la
          // pastille « débranche les antennes » resterait invisible 5 MINUTES
          // à CHAQUE démarrage, et 5 minutes de plus dès qu'on saisit son
          // locator /P en arrivant sur site — exactement les moments où on
          // manipule les antennes. Budget borné (5 × 3 s) : au-delà, ce n'est
          // plus un cache froid mais une panne, que le tic normal couvrira.
          if (_stormRetries-- > 0) setTimeout(fetchStorm, STORM_RETRY_MS);
          return;
        }
        _stormRetries = 0;
        item.style.display = 'flex';
        if (d.storm){
          icon.textContent = '⛈️';
          el.textContent = 'ORAGE';
          el.style.color = 'var(--red,#FF2D55)';
          el.style.fontWeight = '700';
        } else {
          icon.textContent = '⚡';
          el.textContent = 'pas d\'orage';
          el.style.color = 'var(--muted,#A9B0C8)';
          el.style.fontWeight = '';
        }
        item.title = (d.storm
            ? rcT('ORAGE sur le QTH — débranche les antennes.') + ' '
            : rcT('Aucun orage sur le QTH') + ' ' + (d.desc ? '(' + d.desc + '). ' : '. '))
          + (d.warn ? d.warn + ' — ' : '')
          + rcT('Clic : carte de foudre en direct Blitzortung.org (nouvel onglet).');
      }).catch(function(){});
  }
  // PAS de refreshStorm() ici : la barre n'est encore qu'un <div> détaché à ce
  // stade (insert() n'a lieu qu'au DOMContentLoaded), donc getElementById
  // rendrait null et la fonction sortirait sans rien faire — la pastille
  // resterait masquée pendant 5 MINUTES, jusqu'au premier tic. Le 1er appel
  // est donc fait dans boot(), après insert(). Constaté en navigateur : avec
  // une réponse /data/weather servie instantanément, la pastille ne
  // s'affichait jamais.
  // Ce 1er appel dans boot() était nécessaire mais PAS suffisant : au démarrage
  // du serveur, /data/weather rend forcément ok:false (cache froid), d'où la
  // reprise courte ajoutée dans fetchStorm().
  rcPoll(refreshStorm, 5 * 60 * 1000);         // aligné sous le cache serveur (10 min)

  // ── Dégradation réseau (pastille discrète, jamais bloquante) ──────────────
  // Rend VISIBLE côté client des mécanismes qui existaient déjà côté serveur
  // mais restaient silencieux hors de la console (disjoncteur callbook,
  // échecs solaires consécutifs, dernier échec Cloud Sync — voir GET
  // /data/network_status). N'apparaît QUE si quelque chose est réellement
  // dégradé ; disparaît tout seul dès que le service concerné se rétablit.
  function refreshNetworkStatus(){
    fetch('/data/network_status').then(function(r){ return r.ok ? r.json() : null; })
      .then(function(d){
        const item = document.getElementById('rcsbNetworkItem');
        const el = document.getElementById('rcsbNetworkText');
        if (!item || !el || !d) return;
        const parts = [];
        // Chaque morceau est traduit AVANT le join : la chaîne assemblée
        // (« Callbook hors ligne · Cloud Sync en échec ») ne serait une clé
        // dans aucun dictionnaire, et resterait donc en français dès qu'il y a
        // plus d'un service dégradé — précisément le cas où on la lit.
        if (d.callbook && d.callbook.open){
          parts.push(rcTf('Callbook hors ligne (retry {s}s)', {s: d.callbook.wait_s}));
        }
        if (d.solar && d.solar.degraded){
          parts.push(rcT('Météo solaire injoignable'));
        }
        if (d.cloudsync && d.cloudsync.enabled && d.cloudsync.last_error){
          const mn = Math.max(0, Math.round(d.cloudsync.last_error.age_s / 60));
          parts.push(rcTf('Cloud Sync en échec (depuis {n} min)', {n: mn}));
        }
        if (parts.length){
          item.style.display = 'flex';
          el.textContent = parts.join(' · ');
        } else {
          item.style.display = 'none';
        }
      }).catch(function(){ /* le serveur n'est pas indispensable pour la barre */ });
  }
  refreshNetworkStatus();
  rcPoll(refreshNetworkStatus, 20 * 1000);

  // ── Thème jour/nuit GLOBAL (rc_theme, basculé sur config/carte/logbook) ───
  // Chaque page définit sa palette body.day-mode ; ici on applique le choix
  // partout (le calendrier ne le faisait pas) et on suit les autres onglets.
  function applyTheme(){
    document.body.classList.toggle('day-mode', localStorage.getItem('rc_theme') === 'day');
  }
  applyTheme();
  window.addEventListener('storage', function(e){
    if (e.key === 'rc_theme') applyTheme();
  });
  // Un poste qui ouvre le lien multi-poste POUR LA 1re FOIS n'a encore rien
  // dans son localStorage → retombait sur le mode nuit par défaut, même si
  // la station principale est en mode jour. On hérite alors du dernier
  // thème connu du serveur (jamais si ce navigateur a déjà choisi lui-même —
  // même priorité "local d'abord, sinon serveur" que expedition_mode).
  if (localStorage.getItem('rc_theme') === null){
    fetch('/config').then(function(r){ return r.ok ? r.json() : null; }).then(function(c){
      if (c && c.ui_theme && localStorage.getItem('rc_theme') === null){
        localStorage.setItem('rc_theme', c.ui_theme);
        applyTheme();
      }
    }).catch(function(){});
  }

  // ── Mode débutant/expert GLOBAL (choisi dans CONFIG via 🎚) ────────────────
  // Toutes les pages masquent leurs éléments .expert-only en mode simple ;
  // la page config gère son propre défaut, ici on applique juste le choix.
  if (localStorage.getItem('rc_ui_mode') === 'simple'){
    document.body.classList.add('simple-mode');
    const st = document.createElement('style');
    st.textContent = 'body.simple-mode .expert-only{display:none!important}';
    document.head.appendChild(st);
  }

  // Insertion : après la nav si présente, sinon après le header, sinon en tête de body
  function insert(){
    const nav = document.querySelector('nav.app-nav') || document.querySelector('.nav-links');
    const header = document.querySelector('header');
    if (nav && nav.parentNode) nav.parentNode.insertBefore(bar, nav.nextSibling);
    else if (header && header.parentNode) header.parentNode.insertBefore(bar, header.nextSibling);
    else document.body.insertBefore(bar, document.body.firstChild);
  }

  // ── Concours actif + temps restant ─────────────────────────────────────────
  let contestNames = {};   // id → nom lisible (depuis /data/calendar)

  function refreshContest(){
    const cfg = getConfig();
    const el = document.getElementById('rcsbContest');
    // LOGBOOK SIMPLE : pas de concours, même si un concours a été choisi ou
    // testé auparavant (state.contest peut rester en mémoire côté serveur).
    if (cfg.usage_mode === 'simple'){
      // .title posé depuis le JS : l'observateur du moteur ne surveille pas les
      // attributs, donc lui seul ne suffirait pas — d'où rcT() ici.
      el.textContent = 'logbook simple'; el.title = rcT('Mode logbook simple — pas de concours actif');
      return;
    }
    const id = cfg.contest;
    if (!id){ el.textContent = 'aucun concours'; el.title = rcT('Choisis un concours dans CONFIG → étape 2'); return; }
    el.textContent = contestNames[id] || id;
  }

  function refreshCountdown(){
    const cfg = getConfig();
    const el = document.getElementById('rcsbTime');
    // .rc-i18n-live exclut ce texte purement numérique de la re-traduction i18n
    // (voir logx_i18n.js) : il ne faut PAS l'écraser en réinitialisant className.
    el.className = 'rcsb-val rc-i18n-live';
    if (cfg.usage_mode === 'simple' || !cfg.contest || !cfg.contest_end_date){ el.textContent = '—'; return; }
    try{
      // start : contest_start_date à 00:00 si l'heure n'est pas connue —
      // on ne s'en sert que pour distinguer "pas commencé" de "en cours".
      const end = new Date(`${cfg.contest_end_date}T${cfg.contest_end_utc || '00:00'}:00Z`);
      const start = cfg.contest_start_date ? new Date(`${cfg.contest_start_date}T00:00:00Z`) : null;
      const now = new Date();
      if (isNaN(end)){ el.textContent = '—'; return; }
      if (start && now < start){
        const days = Math.ceil((start - now) / 86400000);
        el.textContent = rcTf('début dans {j} j', {j: days});
        el.classList.add('rcsb-soon');
        return;
      }
      const diff = end - now;
      if (diff <= 0){ el.textContent = 'terminé'; el.classList.add('rcsb-over'); return; }
      const h = Math.floor(diff / 3600000);
      const m = Math.floor((diff % 3600000) / 60000);
      const s = Math.floor((diff % 60000) / 1000);
      el.textContent = `reste ${h}:${pad(m)}:${pad(s)}`;
      el.classList.add('rcsb-running');
    }catch(e){ el.textContent = '—'; }
  }

  // ── Dernière sauvegarde (backup log 5 min, sinon sauvegarde config) ───────
  function refreshSave(){
    const el = document.getElementById('rcsbSave');
    const logBackup = localStorage.getItem('rc_log_backup_time'); // "HH:MM UTC"
    if (logBackup){ el.textContent = `log ${logBackup}`; return; }
    const cfg = getConfig();
    if (cfg.saved_at){
      const d = new Date(cfg.saved_at);
      if (!isNaN(d)){ el.textContent = `config ${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())} UTC`; return; }
    }
    el.textContent = 'jamais';
  }

  // ── Dernier check règlements + noms des concours ───────────────────────────
  async function refreshRules(){
    const el = document.getElementById('rcsbRules');
    try{
      const r = await fetch('/data/rules_status');
      const d = await r.json();
      if (d.last_update){
        const dt = new Date(d.last_update);
        el.textContent = rcTf('règlements : {date}',
          {date: `${pad(dt.getDate())}/${pad(dt.getMonth()+1)}/${dt.getFullYear()}`});
      } else {
        el.textContent = 'règlements : jamais vérifiés';
      }
      if (d.alerts && d.alerts.length){
        el.textContent += rcTf(' · ⚠️ {n} alerte(s)', {n: d.alerts.length});
        el.style.color = 'var(--yellow,#FFD60A)';
      }
    }catch(e){ el.textContent = 'règlements : serveur ?'; }
  }

  async function loadContestNames(){
    try{
      const r = await fetch('/data/calendar');
      const d = await r.json();
      (d.contests || []).forEach(c => { contestNames[c.id] = c.name; });
      refreshContest();
    }catch(e){ /* le serveur n'est pas indispensable pour la barre */ }
  }

  // ── Mise à jour logicielle (proposée, jamais installée sans clic) ─────────
  // Sondage léger de /app/update_check (cache serveur 6h, aucun appel réseau
  // direct GitHub depuis le navigateur). Le badge ne s'affiche QUE si une
  // version plus récente existe ET que ce navigateur n'a pas déjà refusé
  // CETTE version précise (rc_update_dismissed).
  let _updState = null;

  function renderUpdateDD(){
    const dd = document.getElementById('rcsbUpdateDD');
    if (!dd || !_updState) return;
    const st = _updState;
    const dl = window._rcsbDownload || {status: 'idle', pct: 0};
    const notes = (st.notes || '').replace(/[<>&]/g, c => ({'<':'&lt;','>':'&gt;','&':'&amp;'}[c]));
    let actionHtml;
    if (dl.status === 'downloading'){
      actionHtml = `<div class="rcsb-upd-progress"><div class="rcsb-upd-progress-fill" style="width:${dl.pct}%"></div></div>
        <div style="text-align:center;margin-top:4px;color:var(--muted,#A9B0C8)">${rcTf('téléchargement {pct}%', {pct: dl.pct})}</div>`;
    } else if (dl.status === 'done'){
      actionHtml = `<div class="rcsb-upd-row"><button id="rcsbUpdInstall">🔁 installer et redémarrer</button></div>`;
    } else if (dl.status === 'error'){
      actionHtml = `<div style="color:var(--red,#FF2D55);margin-top:6px">${rcTf('échec : {err}', {err: (dl.error||'').replace(/[<>&]/g,'')})}</div>
        <div class="rcsb-upd-row"><button id="rcsbUpdDownload">réessayer</button></div>`;
    } else if (st.installable){
      actionHtml = `<div class="rcsb-upd-row">
        <button id="rcsbUpdDownload">⬇️ télécharger et installer</button>
        <button class="rcsb-upd-secondary" id="rcsbUpdLater">plus tard</button></div>`;
    } else {
      actionHtml = `<div class="rcsb-upd-row">
        <a class="rcsb-upd-btn" href="${st.release_url || '#'}" target="_blank" rel="noopener">voir la release</a>
        <button class="rcsb-upd-secondary" id="rcsbUpdLater">plus tard</button></div>`;
    }
    dd.innerHTML = `<div class="rcsb-dd-title">LOGX AI ${st.latest}</div>
      <div>version actuelle : ${st.current}</div>
      ${notes ? '<div class="rcsb-upd-notes">' + notes + '</div>' : ''}
      ${actionHtml}`;
  }

  function pollDownload(){
    fetch('/app/update_status').then(r => r.ok ? r.json() : null).then(function(d){
      if (!d) return;
      window._rcsbDownload = d;
      renderUpdateDD();
      if (d.status === 'downloading') setTimeout(pollDownload, 800);
    }).catch(function(){});
  }

  function pollServerBackUp(){
    // Après /app/update_install, le serveur coupe volontairement le processus
    // pour que le script auxiliaire puisse remplacer l'exécutable — on
    // réessaie jusqu'à ce que la nouvelle instance réponde, puis recharge.
    fetch('/data/rules_status', {cache: 'no-store'}).then(function(r){
      if (r.ok) location.reload();
      else setTimeout(pollServerBackUp, 2000);
    }).catch(function(){ setTimeout(pollServerBackUp, 2000); });
  }

  function refreshUpdateCheck(){
    fetch('/app/update_check').then(r => r.ok ? r.json() : null).then(function(d){
      if (!d) return;
      _updState = d;
      // La version installée vient de 'current', toujours présent (même hors
      // ligne — voir logx_update.get_cached_check) : pas de requête dédiée.
      const vEl = document.getElementById('rcsbVersion');
      if (vEl && d.current) vEl.textContent = 'v' + d.current;
      const item = document.getElementById('rcsbUpdateItem');
      if (!item) return;
      const dismissed = localStorage.getItem('rc_update_dismissed');
      if (d.available && dismissed !== d.latest){
        item.style.display = 'flex';
        document.getElementById('rcsbUpdateLabel').textContent = 'v' + d.latest + ' disponible';
        renderUpdateDD();
      } else {
        item.style.display = 'none';
      }
    }).catch(function(){});
  }

  // ── Signaler un problème : Issue GitHub pré-remplie (version + plateforme) ─
  // Repo lu depuis _updState.repo (source unique = logx_update.GITHUB_REPO) ;
  // ce repli codé en dur ne sert qu'avant le tout premier /app/update_check.
  const REPORT_REPO_FALLBACK = 'sauveteur71/radioaamateur-program-Contest';
  // Fichier du formulaire GitHub Issue Forms (.github/ISSUE_TEMPLATE/bug.yml).
  // Les GitHub Issue Forms (YAML) ne se pré-remplissent QUE via
  // ?template=<fichier>&<id_du_champ>=<valeur> : le format historique des
  // issues "classiques" (?title=/&body=) est silencieusement IGNORÉ dès
  // qu'un template YAML existe (blank_issues_enabled: false le rend
  // d'ailleurs obligatoire, voir config.yml) — le bouton ouvrait alors une
  // issue vide, formulaire non rempli, sans la moindre erreur visible.
  const REPORT_TEMPLATE = 'bug.yml';
  const REPORT_FIELD_MAX = 1500; // marge sous la limite GitHub (414 URI Too Long)

  // Tronque en POINTS DE CODE (jamais en unités UTF-16 brutes comme le fait
  // String.slice()) : couper au milieu d'une paire de substitution (emoji,
  // etc.) laisse un demi-caractère orphelin, et encodeURIComponent() lève
  // une URIError non interceptée dessus — voir revue commit f20799a.
  function truncateCodePoints(str, maxCodePoints){
    const chars = Array.from(str);
    if (chars.length <= maxCodePoints) return str;
    return chars.slice(0, maxCodePoints).join('');
  }

  // Tronque `str` pour que sa version ENCODÉE (ce qui part réellement dans
  // l'URL) ne dépasse pas maxEncodedLen unités. Un texte français accentué
  // peut faire 2 à 6x sa longueur brute une fois passé à encodeURIComponent
  // (é -> %C3%A9, etc.) : REPORT_FIELD_MAX doit borner CE nombre-là, pas
  // str.length — voir revue commit f20799a. Recherche dichotomique sur les
  // points de code (jamais sur les unités UTF-16, cf. truncateCodePoints).
  function truncateToEncodedLength(str, maxEncodedLen){
    const chars = Array.from(str);
    if (encodeURIComponent(str).length <= maxEncodedLen) return str;
    let lo = 0, hi = chars.length;
    while (lo < hi){
      const mid = (lo + hi + 1) >> 1;
      if (encodeURIComponent(chars.slice(0, mid).join('')).length <= maxEncodedLen) lo = mid;
      else hi = mid - 1;
    }
    return chars.slice(0, lo).join('');
  }

  function detectPlatformLabel(){
    try{
      const uaData = navigator.userAgentData;
      if (uaData && uaData.platform) return uaData.platform + ' — ' + navigator.userAgent;
    }catch(e){ /* userAgentData pas supporté partout, repli ci-dessous */ }
    return (navigator.platform || 'plateforme inconnue') + ' — ' + navigator.userAgent;
  }

  // Doit renvoyer EXACTEMENT une des options du menu déroulant `os` de
  // bug.yml (voir tests/test_release_ci_config.py::
  // test_bug_yml_dropdown_os_couvre_les_plateformes_courantes) : une valeur
  // qui ne correspond à aucune option n'est simplement pas présélectionnée
  // par GitHub au chargement du formulaire (silencieux, mais dégradé), donc
  // pas de texte libre ici — uniquement un des 6 libellés fixes.
  function detectOsFormOption(){
    let hay = '';
    try{ hay = ((navigator.userAgent || '') + ' ' + (navigator.platform || '')).toLowerCase(); }
    catch(e){ /* navigator absent (contexte non-navigateur) */ }
    // Android avant Linux : le user-agent Android contient aussi "Linux"
    // (noyau), il faut donc tester le plus spécifique en premier.
    if (/android/.test(hay)) return 'Android (navigateur/PWA)';
    if (/iphone|ipad|ipod/.test(hay)) return 'iPhone / iPad (navigateur/PWA)';
    if (/mac/.test(hay)) return 'macOS';
    if (/win/.test(hay)) return 'Windows';
    if (/linux/.test(hay)) return 'Linux';
    return 'Autre / je ne sais pas';
  }

  // Journal d'erreurs local (voir logx_errorlog.py, GET /debug/errors) : lu en
  // tâche de fond (comme _updState/refreshUpdateCheck) et JAMAIS via un fetch
  // synchrone dans openReportIssue() — un window.open() appelé après un
  // .then() (donc hors du geste utilisateur d'origine) risquerait d'être
  // bloqué par le popup blocker du navigateur.
  let _errState = null;

  // Au-delà de ce délai, la dernière erreur connue est considérée hors-sujet
  // et n'est plus jointe au rapport : sans cette borne, une exception d'un
  // thread de fond survenue plusieurs heures plus tôt (donc sans rapport
  // avec ce que l'opérateur signale maintenant) polluait systématiquement
  // le corps de l'issue GitHub.
  const ERROR_RECENCY_MS = 15 * 60 * 1000; // 15 minutes

  // Borne la taille de e.message avant de l'inclure dans le champ
  // "journal-technique" : contrairement à `tail` (traceback, déjà tronqué
  // ci-dessous), le message n'était borné nulle part — un message
  // d'exception anormalement long pouvait à lui seul dépasser
  // REPORT_FIELD_MAX (le champ journal-technique et le champ description
  // sont désormais des paramètres d'URL séparés, voir openReportIssue : un
  // message d'erreur trop long ne peut donc plus effacer la description de
  // l'opérateur comme avant, seul son propre champ écope).
  const MAX_ERROR_MESSAGE_CHARS = 300;

  function refreshErrorsCheck(){
    fetch('/debug/errors').then(r => r.ok ? r.json() : null).then(function(d){
      if (d) _errState = d;
    }).catch(function(){});
  }

  // Parse le format 'YYYY-MM-DD HH:MM:SS' écrit par logx_errorlog.py
  // (datetime.now().strftime(...), heure LOCALE) : `new Date(str)` n'est pas
  // fiable sur ce format (pas de 'T'/'Z', interprétation dépendante du
  // moteur JS), d'où un parsing manuel des composants.
  function _parseErrorTs(ts){
    const m = /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$/.exec(ts || '');
    if (!m) return null;
    return new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]).getTime();
  }

  function formatLastErrorForReport(){
    if (!_errState || !_errState.errors || !_errState.errors.length) return '';
    const e = _errState.errors[_errState.errors.length - 1]; // le plus récent
    const ts = _parseErrorTs(e.ts);
    // Erreur trop ancienne (ou horodatage illisible) : ne rien joindre plutôt
    // que d'induire l'opérateur en erreur avec une trace sans rapport.
    if (ts === null || (Date.now() - ts) > ERROR_RECENCY_MS) return '';
    let tail = (e.traceback || '').trim();
    if (tail.length > 400){
      // Derniers 400 points de code (pas unités UTF-16) : voir truncateCodePoints.
      const chars = Array.from(tail);
      tail = '…' + chars.slice(Math.max(0, chars.length - 400)).join('');
    }
    let msg = e.message || '';
    if (Array.from(msg).length > MAX_ERROR_MESSAGE_CHARS){
      msg = truncateCodePoints(msg, MAX_ERROR_MESSAGE_CHARS) + '…';
    }
    // Texte brut, sans titre markdown ni ```fences``` manuelles : cette
    // valeur part dans le champ "journal-technique" de bug.yml, dont
    // `render: text` encadre déjà la réponse d'un bloc de code une fois
    // l'issue créée — un fence manuel ici casserait ce rendu (bloc imbriqué).
    return e.ts + ' (thread ' + e.thread + ')\n' + e.type + ': ' + msg + '\n' + tail;
  }

  function openReportIssue(){
    const description = prompt(
      rcT("Décris le problème rencontré (inclus dans l'issue GitHub, tu pourras la relire avant envoi) :"), '');
    if (description === null) return; // annulé

    const version = (_updState && _updState.current) || 'inconnue';
    const repo = (_updState && _updState.repo) || REPORT_REPO_FALLBACK;
    const firstLine = description.split('\n')[0].trim();
    const title = firstLine ? ('[Bug] ' + truncateCodePoints(firstLine, 80)) : '[Bug] signalé depuis LogX AI';

    // REPORT_FIELD_MAX borne la longueur ENCODÉE (ce qui part réellement
    // dans l'URL), pas descriptionField.length : un texte français accentué
    // peut faire 2 à 6x sa taille brute une fois passé à encodeURIComponent.
    let descriptionField = description.trim() || '(non renseignée)';
    if (encodeURIComponent(descriptionField).length > REPORT_FIELD_MAX){
      const suffix = '\n…(tronqué)';
      const suffixLen = encodeURIComponent(suffix).length;
      descriptionField = truncateToEncodedLength(
        descriptionField, Math.max(0, REPORT_FIELD_MAX - suffixLen)) + suffix;
    }

    // Un paramètre par `id:` déclaré dans bug.yml (voir REPORT_TEMPLATE
    // ci-dessus) — "activite" n'est volontairement pas pré-rempli, le
    // bouton n'a jamais promis plus que "version + plateforme" (voir title
    // de #rcsbReportItem) et cette réponse reste à la charge de l'opérateur.
    const params = {
      template: REPORT_TEMPLATE,
      title: title,
      labels: 'bug',
      version: 'v' + version,
      os: detectOsFormOption(),
      description: descriptionField
    };
    // Journal technique : plateforme détaillée (User-Agent complet, plus
    // précis que le libellé fixe du champ "os") + dernière erreur locale
    // récente, si disponible — c'est la partie de la promesse "version +
    // plateforme" du bouton (voir title de #rcsbReportItem) qui ne rentre
    // pas dans le champ "os" (options fixes du menu déroulant de bug.yml).
    const lastError = formatLastErrorForReport();
    params['journal-technique'] = detectPlatformLabel()
      + (lastError ? '\n\nDernière erreur du journal local :\n' + lastError : '');

    // Filet de sécurité : malgré les troncatures ci-dessus (en points de
    // code, jamais en unités UTF-16), un caractère invalide échappé de
    // quelque part lèverait une URIError non interceptée et ferait échouer
    // le bouton en silence — voir revue commit f20799a.
    let url;
    try{
      url = 'https://github.com/' + repo + '/issues/new?' + Object.keys(params).map(function(k){
        return encodeURIComponent(k) + '=' + encodeURIComponent(params[k]);
      }).join('&');
    }catch(err){
      alert(rcT("Impossible de préparer le rapport de bug (caractère invalide dans le texte saisi).") + " "
          + rcTf('Ouvre directement une Issue sur {url}',
                 {url: 'https://github.com/' + repo + '/issues/new'}));
      return;
    }
    window.open(url, '_blank', 'noopener,noreferrer');
  }

  bar.addEventListener('click', function(e){
    if (e.target.closest('#rcsbReportItem')) openReportIssue();
  });

  bar.addEventListener('click', function(e){
    const updItem = e.target.closest('#rcsbUpdateItem');
    const updDD = document.getElementById('rcsbUpdateDD');
    if (updItem && !e.target.closest('#rcsbUpdateDD')){
      const willOpen = updDD.style.display === 'none';
      updDD.style.display = willOpen ? 'block' : 'none';
      return;
    }
    if (e.target.id === 'rcsbUpdDownload'){
      fetch('/app/update_download', {method: 'POST'}).then(function(){ pollDownload(); });
      return;
    }
    if (e.target.id === 'rcsbUpdInstall'){
      var _ib = e.target;
      _ib.disabled = true;
      _ib.textContent = 'redémarrage…';
      fetch('/app/update_install', {method: 'POST'})
        .then(function(r){ return r.json().catch(function(){ return {}; }).then(function(j){ return {ok: r.ok, j: j}; }); })
        .then(function(res){
          if (res.ok && res.j && res.j.restarting){
            setTimeout(pollServerBackUp, 2500);      // le serveur se coupe puis revient
            return;
          }
          // ÉCHEC D'INSTALLATION rendu VISIBLE : sans ça le bouton restait figé
          // sur « redémarrage… » et l'opérateur croyait que rien ne se passait
          // (cas réel : fichier non vérifié, téléchargement incomplet, ou lancé
          // hors .exe en mode développement — apply_update_and_relaunch refuse).
          _ib.disabled = false;
          _ib.textContent = '🔁 installer et redémarrer';
          var _msg = (res.j && res.j.error) || 'échec inconnu';
          var _row = _ib.closest ? _ib.closest('.rcsb-upd-row') : null;
          var _err = document.createElement('div');
          _err.style.cssText = 'color:var(--red,#FF2D55);margin-top:6px;font-size:12px';
          _err.textContent = rcTf('échec : {err}', {err: ('' + _msg).replace(/[<>&]/g, '')});
          (_row || _ib.parentNode).appendChild(_err);
        })
        .catch(function(){
          _ib.disabled = false;
          _ib.textContent = '🔁 installer et redémarrer';
        });
      return;
    }
    if (e.target.id === 'rcsbUpdLater'){
      if (_updState) localStorage.setItem('rc_update_dismissed', _updState.latest);
      document.getElementById('rcsbUpdateItem').style.display = 'none';
      updDD.style.display = 'none';
      return;
    }
  });
  document.addEventListener('click', function(e){
    const dd = document.getElementById('rcsbUpdateDD');
    const item = document.getElementById('rcsbUpdateItem');
    if (dd && dd.style.display !== 'none' && item && !item.contains(e.target)) dd.style.display = 'none';
  });

  // ── Panneaux détachables + dispositions nommées (roadmap "lot structurant",
  // inspiré du docking des loggers concurrents sans copier le docking générique : ici de
  // simples fenêtres popup, une disposition = quelles fenêtres sont ouvertes
  // et à quelle taille/position). Accessible depuis N'IMPORTE QUELLE page
  // puisque ce fichier est inclus partout — les panneaux eux-mêmes vivent sur
  // des pages différentes (coach=carte, cluster/soleil=propagation,
  // bandmap=logbook) mais une fois détachés ce sont juste des fenêtres OS
  // indépendantes, sans lien avec la page qui les a ouvertes.
  const PANEL_DEFAULTS = {
    coach:        {w: 420, h: 620, label: 'Coach'},
    cluster:      {w: 560, h: 640, label: 'Cluster — need list'},
    solarweather: {w: 420, h: 420, label: 'Soleil & ionosphère'},
    bandmap:      {w: 260, h: 640, label: 'Band Map'},
    workedmatrix: {w: 480, h: 520, label: 'Worked Matrix'},
  };
  const _openWindows = {};   // clé d'instance -> ref fenêtre (perdu au rechargement — une disposition rouvre les fenêtres)

  // CLÉ D'INSTANCE, pas de type. Un band map n'a de sens que rapporté À UNE
  // BANDE : en vouloir cinq côte à côte (20 m, 15 m, 10 m, 6 m, 2 m) sur un 2e
  // écran est l'usage NORMAL en concours, pas un cas limite.
  //
  // DÉFAUT CORRIGÉ ICI : le nom de fenêtre était « rc_panel_bandmap », sans la
  // bande. Or window.open() RÉUTILISE la fenêtre qui porte déjà ce nom : le 2e
  // band map ne s'ouvrait pas, il faisait CHANGER DE BANDE le premier. Aucune
  // erreur, aucun message — juste une fenêtre qui saute d'une bande à l'autre
  // pendant qu'on croit en avoir ouvert deux.
  function panelKey(id, g){
    return (id === 'bandmap' && g && g.band) ? id + '@' + g.band : id;
  }
  function panelBand(cle){
    const i = String(cle).indexOf('@');
    return i < 0 ? null : String(cle).slice(i + 1);
  }
  function panelId(cle){
    const i = String(cle).indexOf('@');
    return i < 0 ? String(cle) : String(cle).slice(0, i);
  }

  function openPanel(id, geo){
    const d = PANEL_DEFAULTS[id];
    if (!d) return null;
    const g = geo || {};
    const w = g.w || d.w, h = g.h || d.h;
    const left = g.x != null ? g.x : Math.max(0, (screen.width - w) / 2);
    const top = g.y != null ? g.y : Math.max(0, (screen.height - h) / 2);
    let url = 'logx_panel.html?id=' + encodeURIComponent(id);
    if (id === 'bandmap' && g.band) url += '&band=' + encodeURIComponent(g.band);
    const cle = panelKey(id, g);
    // Le nom de fenêtre doit être un identifiant simple : la bande peut
    // contenir un point (10.1 MHz), que l'on remplace comme le fait déjà
    // popoutBandes() dans logx_logbook.js.
    const nom = 'rc_panel_' + cle.replace('@', '_').replace(/\./g, '_');
    const win = window.open(url, nom,
      `width=${w},height=${h},left=${left},top=${top},menubar=no,toolbar=no,location=no`);
    if (win) _openWindows[cle] = win;
    return win;
  }
  function closePanel(cle){
    const win = _openWindows[cle];
    if (win && !win.closed) win.close();
    delete _openWindows[cle];
  }
  function isPanelOpen(cle){
    const win = _openWindows[cle];
    return !!(win && !win.closed);
  }
  // Toutes les instances OUVERTES d'un type — « bandmap » en a autant que de
  // bandes détachées.
  function openInstances(id){
    return Object.keys(_openWindows).filter(function(cle){
      return panelId(cle) === id && isPanelOpen(cle);
    });
  }
  window.rcOpenPanel = function(id, geo){ return openPanel(id, geo); };
  window.rcClosePanel = function(id){ closePanel(id); };
  // ── Écrans détachés (bandscope, mural, une fenêtre par bande) ────────────
  // Ces trois-là ne sont PAS des « panneaux » (logx_panel.html) mais des pages
  // à part entière. Ils vivaient sur des boutons de la barre d'outils du
  // logbook ; en épurant cette page je les ai retirés en croyant que le menu
  // DISPOSITION les couvrait déjà — il ne couvrait que les panneaux, et
  // popoutBandes() s'est retrouvée SANS AUCUN APPELANT. Rattrapé par le test
  // qui protégeait ce câblage.
  //
  // Les mettre ICI vaut mieux que de les rendre au logbook : la barre de
  // statut est sur toutes les pages, on peut donc ouvrir l'écran mural depuis
  // la page propagation, ce qui était impossible avant.
  function ouvrirEcran(quoi){
    // Sur la page logbook, on réutilise les fonctions existantes : elles
    // connaissent la bande courante et les bandes réellement visibles.
    const local = {scope: 'popoutScope', mur: 'popoutWall', bandes: 'popoutBandes'}[quoi];
    if (local && typeof window[local] === 'function') { window[local](); return; }
    if (quoi === 'mur') {
      window.open('/logx_wall.html', 'rc_wall',
        'width=1280,height=720,menubar=no,toolbar=no,location=no');
      return;
    }
    // Hors logbook, la liste des bandes vient de la config partagée.
    let bandes = [];
    try {
      const cfg = JSON.parse(localStorage.getItem('logx_config') || '{}');
      bandes = (cfg.bands || []).map(String).filter(Boolean);
    } catch (e) { /* config illisible : on retombe sur la bande par défaut */ }
    if (quoi === 'scope') {
      const b = bandes[0] || '144';
      window.open('/logx_scope.html?band=' + encodeURIComponent(b),
        'rc_scope_' + b.replace(/\./g, '_'),
        'width=1100,height=560,menubar=no,toolbar=no,location=no');
      return;
    }
    if (!bandes.length) {
      alert(rcT("Aucune bande active : choisis un concours ou coche des bandes dans CONFIG"));
      return;
    }
    bandes.slice(0, 12).forEach(function(b, i){
      window.open('/logx_bande.html?band=' + encodeURIComponent(b),
        'rc_bande_' + String(b).replace(/\./g, '_'),
        'width=420,height=520,left=' + (40 + i * 40) + ',top=' + (40 + i * 30)
        + ',menubar=no,toolbar=no,location=no');
    });
  }
  window.rcOuvrirEcran = ouvrirEcran;

  // Le bouton du menu agit sur le TYPE : s'il y a cinq band maps ouverts,
  // « fermer » les ferme tous les cinq — sinon il en resterait quatre à
  // fermer une par une, alors que le bouton affiche « fermer (5) ».
  window.rcTogglePanel = function(id){
    const ouvertes = openInstances(id);
    if (ouvertes.length) ouvertes.forEach(closePanel);
    else openPanel(id);
    renderLayoutDD();
  };

  function getLayouts(){
    try { return JSON.parse(localStorage.getItem('rc_layouts') || '{}'); }
    catch (e){ return {}; }
  }
  function setLayouts(obj){
    localStorage.setItem('rc_layouts', JSON.stringify(obj));
  }
  function saveLayout(name){
    name = (name || '').trim();
    if (!name) return;
    const layouts = getLayouts();
    const panels = {};
    // On parcourt les fenêtres OUVERTES, pas la liste des TYPES de panneaux :
    // sinon cinq band maps sur cinq bandes n'en auraient enregistré qu'un, et
    // recharger la disposition en aurait rouvert un seul. La bande est
    // mémorisée dans l'entrée pour pouvoir rouvrir la bonne.
    Object.keys(_openWindows).forEach(function(cle){
      if (!isPanelOpen(cle)) return;
      const win = _openWindows[cle];
      let geo = {};
      try { geo = {w: win.outerWidth, h: win.outerHeight, x: win.screenX, y: win.screenY}; }
      catch (e) { /* fenêtre cross-origin ou navigateur restrictif : tailles par défaut au chargement */ }
      geo.id = panelId(cle);
      const b = panelBand(cle);
      if (b) geo.band = b;
      panels[cle] = geo;
    });
    layouts[name] = {panels: panels};
    setLayouts(layouts);
    renderLayoutDD();
  }
  function loadLayout(name){
    const layout = getLayouts()[name];
    if (!layout) return;
    // Ferme d'abord ce qui n'appartient pas à cette disposition
    Object.keys(_openWindows).forEach(function(cle){
      if (!layout.panels[cle]) closePanel(cle);
    });
    // Ouvre/repositionne chaque panneau de la disposition (synchrone, dans le
    // même geste de clic — les navigateurs bloquent les popup ouvertes hors
    // d'une interaction utilisateur directe).
    Object.keys(layout.panels).forEach(function(cle){
      const geo = layout.panels[cle] || {};
      // Dispositions enregistrées AVANT l'ajout des instances : la clé valait
      // le type seul et l'entrée n'avait ni `id` ni `band`. On les relit sans
      // rien casser en dérivant les deux depuis la clé.
      const id = geo.id || panelId(cle);
      if (!geo.band) { const b = panelBand(cle); if (b) geo.band = b; }
      closePanel(cle);
      openPanel(id, geo);
    });
    renderLayoutDD();
  }
  function deleteLayout(name){
    const layouts = getLayouts();
    delete layouts[name];
    setLayouts(layouts);
    renderLayoutDD();
  }
  function resetLayout(){
    Object.keys(_openWindows).forEach(closePanel);
    renderLayoutDD();
  }
  window.rcSaveLayout = saveLayout;
  window.rcLoadLayout = loadLayout;
  window.rcDeleteLayout = deleteLayout;
  window.rcResetLayout = resetLayout;

  function renderLayoutDD(){
    const dd = document.getElementById('rcsbLayoutDD');
    if (!dd) return;
    const layouts = getLayouts();
    const names = Object.keys(layouts);
    const panelRows = Object.keys(PANEL_DEFAULTS).map(function(id){
      // Compte les INSTANCES : cinq band maps ouverts, c'est « fermer (5) ».
      // Se contenter de isPanelOpen(id) afficherait « ouvrir » alors que cinq
      // fenêtres sont sous les yeux de l'opérateur.
      const n = openInstances(id).length;
      const suffixe = n > 1 ? ' (' + n + ')' : '';
      return '<div class="rcsb-panel-row"><span>' + PANEL_DEFAULTS[id].label + '</span>'
        + '<button data-panel-toggle="' + id + '">'
        + (n ? 'fermer' + suffixe : 'ouvrir') + '</button></div>';
    }).join('');
    const layoutRows = names.length
      ? names.map(function(n){
          return '<div class="rcsb-layout-row"><span>' + n.replace(/[<>&]/g, '') + '</span>'
            + '<button data-layout-load="' + n.replace(/"/g, '&quot;') + '">charger</button>'
            + '<button data-layout-del="' + n.replace(/"/g, '&quot;') + '">supprimer</button></div>';
        }).join('')
      : '<div style="color:var(--muted,#A9B0C8);padding:2px 0">aucune disposition enregistrée</div>';
    // Écrans détachés : des PAGES entières (bandscope, mural, une fenêtre par
    // bande), à distinguer des panneaux ci-dessus.
    const ecranRows =
      '<div class="rcsb-panel-row"><span>' + rcT('Bandscope') + '</span>'
      + '<button data-ecran="scope">' + rcT('ouvrir') + '</button></div>'
      + '<div class="rcsb-panel-row"><span>' + rcT('Écran mural') + '</span>'
      + '<button data-ecran="mur">' + rcT('ouvrir') + '</button></div>'
      + '<div class="rcsb-panel-row"><span>' + rcT('Une fenêtre par bande') + '</span>'
      + '<button data-ecran="bandes">' + rcT('ouvrir') + '</button></div>';

    dd.innerHTML =
      '<div class="rcsb-dd-title">PANNEAUX</div>' + panelRows +
      '<hr><div class="rcsb-dd-title">' + rcT('ÉCRANS DÉTACHÉS') + '</div>' + ecranRows +
      '<hr><div class="rcsb-dd-title">' + rcT('DISPOSITIONS ENREGISTRÉES') + '</div>' + layoutRows +
      '<hr><input type="text" id="rcsbNewLayoutName" placeholder="' + rcT('nom de la disposition') + '">' +
      '<div style="display:flex;gap:6px;margin-top:6px">' +
      '<button id="rcsbSaveLayoutBtn" style="flex:1">💾 enregistrer l\'actuelle</button>' +
      '<button id="rcsbResetLayoutBtn">tout fermer</button></div>';
  }

  // Délégation d'événements : la dropdown est régénérée à chaque ouverture,
  // pas besoin de re-binder des listeners individuels à chaque rendu.
  bar.addEventListener('click', function(e){
    const layoutItem = e.target.closest('#rcsbLayoutItem');
    const dd = document.getElementById('rcsbLayoutDD');
    if (layoutItem && !e.target.closest('#rcsbLayoutDD')){
      const willOpen = dd.style.display === 'none';
      dd.style.display = willOpen ? 'block' : 'none';
      if (willOpen) renderLayoutDD();
      return;
    }
    const toggleBtn = e.target.closest('[data-panel-toggle]');
    if (toggleBtn){ window.rcTogglePanel(toggleBtn.getAttribute('data-panel-toggle')); return; }
    const ecranBtn = e.target.closest('[data-ecran]');
    if (ecranBtn){ ouvrirEcran(ecranBtn.getAttribute('data-ecran')); return; }
    const loadBtn = e.target.closest('[data-layout-load]');
    if (loadBtn){ loadLayout(loadBtn.getAttribute('data-layout-load')); return; }
    const delBtn = e.target.closest('[data-layout-del]');
    if (delBtn){ deleteLayout(delBtn.getAttribute('data-layout-del')); return; }
    if (e.target.id === 'rcsbSaveLayoutBtn'){
      const input = document.getElementById('rcsbNewLayoutName');
      saveLayout(input ? input.value : '');
      return;
    }
    if (e.target.id === 'rcsbResetLayoutBtn'){ resetLayout(); return; }
  });
  document.addEventListener('click', function(e){
    const dd = document.getElementById('rcsbLayoutDD');
    const item = document.getElementById('rcsbLayoutItem');
    if (dd && dd.style.display !== 'none' && item && !item.contains(e.target)) dd.style.display = 'none';
  });

  // ── Boot ───────────────────────────────────────────────────────────────────
  function boot(){
    insert();
    refreshContest(); refreshCountdown(); refreshSave();
    loadContestNames();
    refreshRules();
    refreshUpdateCheck();
    refreshErrorsCheck();
    refreshStorm();   // après insert() : la pastille n'existe pas avant
    // Purement local (aucune requête) : recalculé à chaque tick depuis
    // l'horloge et localStorage, donc juste à l'affichage même après un
    // passage en arrière-plan — pas la peine de les suspendre.
    setInterval(refreshCountdown, 1000);
    setInterval(tickBandChange, 1000);
    setInterval(refreshSave, 15000);
    // Réseau : suspendus onglet masqué, rattrapés au retour (cf. rcPoll).
    rcPoll(refreshRules, 10 * 60 * 1000);
    rcPoll(refreshUpdateCheck, 30 * 60 * 1000);
    rcPoll(refreshErrorsCheck, 60 * 1000);
    // Réagir aux sauvegardes faites dans un autre onglet
    window.addEventListener('storage', () => { refreshContest(); refreshSave(); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
