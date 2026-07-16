/* ─────────────────────────────────────────────────────────────────────────────
   RadioContest AI — Barre de statut permanente (Phase 1 UX)
   Injectée sur toutes les pages : concours actif · temps restant ·
   dernière sauvegarde · dernier check règlements.
   Inclusion : <script src="statusbar.js"></script> (après la nav).
   S'appuie sur les variables CSS communes des pages (--bg2, --border, ...).
   ──────────────────────────────────────────────────────────────────────────── */
(function(){
  'use strict';
  if (location.protocol === 'file:') return; // pages affichent déjà leur erreur

  // ── Helpers ────────────────────────────────────────────────────────────────
  function getConfig(){
    try { return JSON.parse(localStorage.getItem('radiocontest_config') || '{}'); }
    catch(e){ return {}; }
  }
  const pad = n => String(n).padStart(2, '0');

  // ── Création du DOM ────────────────────────────────────────────────────────
  const bar = document.createElement('div');
  bar.id = 'rcStatusBar';
  bar.innerHTML = `
    <style>
      #rcStatusBar{display:flex;align-items:center;gap:0;flex-wrap:wrap;
        background:var(--bg2,#0D0E1A);border-bottom:1px solid var(--border,#1E2040);
        font-family:var(--font-mono,'Share Tech Mono',monospace);font-size:10px;
        color:var(--muted,#B8A040);padding:0 12px;min-height:26px}
      #rcStatusBar .rcsb-item{display:flex;align-items:center;gap:5px;
        padding:4px 12px;border-right:1px solid var(--border,#1E2040);white-space:nowrap}
      #rcStatusBar .rcsb-item:last-child{border-right:none}
      #rcStatusBar .rcsb-val{color:var(--text,#FFE566)}
      #rcStatusBar .rcsb-contest{color:var(--accent,#FF6B00);font-weight:700;letter-spacing:1px}
      #rcStatusBar .rcsb-running{color:var(--green,#00FF88)}
      #rcStatusBar .rcsb-soon{color:var(--yellow,#FFD60A)}
      #rcStatusBar .rcsb-over{color:var(--red,#FF2D55)}
      #rcStatusBar a{color:inherit;text-decoration:none}
      #rcStatusBar a:hover{color:var(--accent2,#00D4FF)}
      @media (max-width:900px){ #rcStatusBar .rcsb-item{padding:4px 7px} }
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
    <div class="rcsb-item" title="Dernière vérification automatique des règlements par le serveur">
      📄 <a href="calendrier.html" id="rcsbRules">règlements : —</a>
    </div>`;

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
    const id = cfg.contest;
    if (!id){ el.textContent = 'aucun concours'; el.title = 'Choisis un concours dans CONFIG → étape 2'; return; }
    el.textContent = contestNames[id] || id;
  }

  function refreshCountdown(){
    const cfg = getConfig();
    const el = document.getElementById('rcsbTime');
    el.className = 'rcsb-val';
    if (!cfg.contest || !cfg.contest_end_date){ el.textContent = '—'; return; }
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
