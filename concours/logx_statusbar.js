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
    <div class="rcsb-item" title="Rate meter : QSO/h sur 10 min glissantes (extrapolé) et 60 min glissantes. Clic : fixer un objectif — vert au-dessus, rouge en dessous."
         id="rcsbRateItem" style="cursor:pointer">
      ⚡ <span class="rcsb-val" id="rcsbRate">—</span>
    </div>
    <div class="rcsb-item" title="Dernière vérification automatique des règlements par le serveur">
      📄 <a href="logx_calendrier.html" id="rcsbRules">règlements : —</a>
    </div>
    <div class="rcsb-item" id="rcsbLayoutItem" style="cursor:pointer;position:relative" title="Panneaux détachables + dispositions nommées (comme un espace de travail à onglets, en fenêtres séparées)">
      🗔 <span class="rcsb-val">DISPOSITION</span>
      <div id="rcsbLayoutDD" style="display:none"></div>
    </div>`;

  // ── Rate meter (A3) : QSO/h 10 min extrapolé + 60 min, objectif cliquable ──
  function refreshRate(){
    fetch('/coach/state').then(function(r){ return r.ok ? r.json() : null; })
      .then(function(st){
        const el = document.getElementById('rcsbRate');
        if (!el || !st) return;
        const s = st.stats || {};
        const running = st.clock && st.clock.status === 'en_cours';
        const goal = parseInt(localStorage.getItem('rc_rate_goal') || '0', 10);
        if (!running){ el.textContent = '—'; el.style.color = ''; return; }
        el.textContent = (s.rate_10min || 0) + '/h (10min) · '
                       + (s.rate_60min || 0) + '/h (60min)'
                       + (goal ? ' · obj ' + goal : '');
        el.style.color = goal
          ? ((s.rate_10min || 0) >= goal ? 'var(--green,#00FF88)' : 'var(--red,#FF2D55)')
          : '';
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
  refreshRate();
  setInterval(refreshRate, 60 * 1000);

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
    setInterval(refreshCountdown, 1000);
    setInterval(refreshSave, 15000);
    setInterval(refreshRules, 10 * 60 * 1000);
    // Réagir aux sauvegardes faites dans un autre onglet
    window.addEventListener('storage', () => { refreshContest(); refreshSave(); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
