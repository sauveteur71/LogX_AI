/* ─────────────────────────────────────────────────────────────────────────────
   LogX AI — Barre de statut permanente (Phase 1 UX)
   Injectée sur toutes les pages : concours actif · temps restant ·
   dernière sauvegarde · dernier check règlements.
   Inclusion : <script src="logx_statusbar.js"></script> (après la nav).
   S'appuie sur les variables CSS communes des pages (--bg2, --border, ...).
   ──────────────────────────────────────────────────────────────────────────── */
(function(){
  'use strict';
  if (location.protocol === 'file:') return; // pages affichent déjà leur erreur

  // ── Helpers ────────────────────────────────────────────────────────────────
  function getConfig(){
    try { return JSON.parse(localStorage.getItem('logx_config') || '{}'); }
    catch(e){ return {}; }
  }
  const pad = n => String(n).padStart(2, '0');

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
      ⏱ <span class="rcsb-val" id="rcsbTime">—</span>
    </div>
    <div class="rcsb-item" title="Dernier backup automatique du log (toutes les 5 min sur la page Logbook)">
      💾 <span class="rcsb-val" id="rcsbSave">—</span>
    </div>
    <div class="rcsb-item" title="Météo solaire (SFI = flux solaire, K = agitation géomagnétique) — clic : détail complet + conditions par bande">
      <a href="logx_propagation.html">☀️ <span class="rcsb-val" id="rcsbSolar">—</span></a>
    </div>
    <div class="rcsb-item" title="Rate meter : QSO/h sur 10 min glissantes (extrapolé) et 60 min glissantes. Clic : fixer un objectif — vert au-dessus, rouge en dessous."
         id="rcsbRateItem" style="cursor:pointer">
      ⚡ <span class="rcsb-val" id="rcsbRate">—</span>
    </div>
    <div class="rcsb-item" id="rcsbBandChangeItem" style="display:none"
         title="Règle des 10 minutes (Multi-Single, CQ WW et concours similaires) : un changement de bande n'est autorisé qu'une fois toutes les 10 minutes. Décompte depuis le dernier changement de bande loggué.">
      🔄 <span class="rcsb-val" id="rcsbBandChange">—</span>
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
  function refreshRate(){
    fetch('/coach/state').then(function(r){ return r.ok ? r.json() : null; })
      .then(function(st){
        if (!st) return;
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
  bar.addEventListener('click', function(e){
    if (!e.target.closest('#rcsbRateItem')) return;
    const cur = localStorage.getItem('rc_rate_goal') || '0';
    const v = prompt('Objectif de rate (QSO/h) — 0 pour désactiver :', cur);
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
  setInterval(refreshRate, 60 * 1000);

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
  setInterval(refreshSolar, 15 * 60 * 1000);   // aligné sur le cache serveur (15 min)

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
      el.textContent = 'logbook simple'; el.title = 'Mode logbook simple — pas de concours actif';
      return;
    }
    const id = cfg.contest;
    if (!id){ el.textContent = 'aucun concours'; el.title = 'Choisis un concours dans CONFIG → étape 2'; return; }
    el.textContent = contestNames[id] || id;
  }

  function refreshCountdown(){
    const cfg = getConfig();
    const el = document.getElementById('rcsbTime');
    el.className = 'rcsb-val';
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
        el.textContent = `début dans ${days} j`;
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
        el.textContent = `règlements : ${pad(dt.getDate())}/${pad(dt.getMonth()+1)}/${dt.getFullYear()}`;
      } else {
        el.textContent = 'règlements : jamais vérifiés';
      }
      if (d.alerts && d.alerts.length){
        el.textContent += ` · ⚠️ ${d.alerts.length} alerte(s)`;
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
        <div style="text-align:center;margin-top:4px;color:var(--muted,#A9B0C8)">téléchargement ${dl.pct}%</div>`;
    } else if (dl.status === 'done'){
      actionHtml = `<div class="rcsb-upd-row"><button id="rcsbUpdInstall">🔁 installer et redémarrer</button></div>`;
    } else if (dl.status === 'error'){
      actionHtml = `<div style="color:var(--red,#FF2D55);margin-top:6px">échec : ${(dl.error||'').replace(/[<>&]/g,'')}</div>
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
      "Décris le problème rencontré (inclus dans l'issue GitHub, tu pourras la relire avant envoi) :", '');
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
      alert("Impossible de préparer le rapport de bug (caractère invalide dans le texte saisi). "
          + 'Ouvre directement une Issue sur https://github.com/' + repo + '/issues/new');
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
      e.target.disabled = true;
      e.target.textContent = 'redémarrage…';
      fetch('/app/update_install', {method: 'POST'}).then(function(){ setTimeout(pollServerBackUp, 2500); });
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
  const _openWindows = {};   // panelId -> ref fenêtre (perdu au rechargement — une disposition rouvre les fenêtres)

  function openPanel(id, geo){
    const d = PANEL_DEFAULTS[id];
    if (!d) return null;
    const g = geo || {};
    const w = g.w || d.w, h = g.h || d.h;
    const left = g.x != null ? g.x : Math.max(0, (screen.width - w) / 2);
    const top = g.y != null ? g.y : Math.max(0, (screen.height - h) / 2);
    let url = 'logx_panel.html?id=' + encodeURIComponent(id);
    if (id === 'bandmap' && g.band) url += '&band=' + encodeURIComponent(g.band);
    const win = window.open(url, 'rc_panel_' + id,
      `width=${w},height=${h},left=${left},top=${top},menubar=no,toolbar=no,location=no`);
    if (win) _openWindows[id] = win;
    return win;
  }
  function closePanel(id){
    const win = _openWindows[id];
    if (win && !win.closed) win.close();
    delete _openWindows[id];
  }
  function isPanelOpen(id){
    const win = _openWindows[id];
    return !!(win && !win.closed);
  }
  window.rcOpenPanel = function(id, geo){ return openPanel(id, geo); };
  window.rcClosePanel = function(id){ closePanel(id); };
  window.rcTogglePanel = function(id){ isPanelOpen(id) ? closePanel(id) : openPanel(id); renderLayoutDD(); };

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
    Object.keys(PANEL_DEFAULTS).forEach(function(id){
      if (!isPanelOpen(id)) return;
      const win = _openWindows[id];
      let geo = {};
      try { geo = {w: win.outerWidth, h: win.outerHeight, x: win.screenX, y: win.screenY}; }
      catch (e) { /* fenêtre cross-origin ou navigateur restrictif : tailles par défaut au chargement */ }
      panels[id] = geo;
    });
    layouts[name] = {panels: panels};
    setLayouts(layouts);
    renderLayoutDD();
  }
  function loadLayout(name){
    const layout = getLayouts()[name];
    if (!layout) return;
    // Ferme d'abord ce qui n'appartient pas à cette disposition
    Object.keys(_openWindows).forEach(function(id){
      if (!layout.panels[id]) closePanel(id);
    });
    // Ouvre/repositionne chaque panneau de la disposition (synchrone, dans le
    // même geste de clic — les navigateurs bloquent les popup ouvertes hors
    // d'une interaction utilisateur directe).
    Object.keys(layout.panels).forEach(function(id){
      closePanel(id);
      openPanel(id, layout.panels[id]);
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
      const open = isPanelOpen(id);
      return '<div class="rcsb-panel-row"><span>' + PANEL_DEFAULTS[id].label + '</span>'
        + '<button data-panel-toggle="' + id + '">' + (open ? 'fermer' : 'ouvrir') + '</button></div>';
    }).join('');
    const layoutRows = names.length
      ? names.map(function(n){
          return '<div class="rcsb-layout-row"><span>' + n.replace(/[<>&]/g, '') + '</span>'
            + '<button data-layout-load="' + n.replace(/"/g, '&quot;') + '">charger</button>'
            + '<button data-layout-del="' + n.replace(/"/g, '&quot;') + '">supprimer</button></div>';
        }).join('')
      : '<div style="color:var(--muted,#A9B0C8);padding:2px 0">aucune disposition enregistrée</div>';
    dd.innerHTML =
      '<div class="rcsb-dd-title">PANNEAUX</div>' + panelRows +
      '<hr><div class="rcsb-dd-title">DISPOSITIONS ENREGISTRÉES</div>' + layoutRows +
      '<hr><input type="text" id="rcsbNewLayoutName" placeholder="nom de la disposition">' +
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
    setInterval(refreshCountdown, 1000);
    setInterval(tickBandChange, 1000);
    setInterval(refreshSave, 15000);
    setInterval(refreshRules, 10 * 60 * 1000);
    setInterval(refreshUpdateCheck, 30 * 60 * 1000);
    setInterval(refreshErrorsCheck, 60 * 1000);
    // Réagir aux sauvegardes faites dans un autre onglet
    window.addEventListener('storage', () => { refreshContest(); refreshSave(); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
