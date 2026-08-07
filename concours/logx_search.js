/* ─────────────────────────────────────────────────────────────────────────────
   LogX AI — Recherche plein-texte dans les pages (demande F4GLD 07/08/2026 :
   « je cherche sstv, je ne sais pas où c'est dans le logiciel »).
   Injecte une icône loupe dans la nav (avant .nav-spacer) qui ouvre un panneau
   de résultats interrogeant GET /search?q=... (voir logx_search.py).
   Un clic sur un résultat ouvre la page ciblée avec ?rcq=<terme> ; CE MÊME
   script, chargé sur cette page ensuite, retrouve le premier passage
   correspondant, le fait défiler à l'écran et le met brièvement en surbrillance.
   Inclusion : <script src="logx_search.js"></script> (après la nav, comme
   logx_statusbar.js/logx_i18n.js).
   ──────────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  if (location.protocol === 'file:') return; // pages affichent déjà leur erreur

  const rcT = s => (window.rcT ? window.rcT(s) : s);

  function esc(s) {
    return String(s).replace(/[&<>"']/g, c => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
  }

  const CSS = `
.nav-search-wrap{position:relative;display:flex;align-items:center}
.nav-search-btn{background:none;border:none;color:var(--muted);cursor:pointer;
  padding:6px;display:flex;align-items:center;border-radius:6px;transition:color .15s,background .15s}
.nav-search-btn:hover,.nav-search-btn.active{color:var(--accent2);background:rgba(var(--accent-rgb),.1)}
.nav-search-panel{position:absolute;top:calc(100% + 8px);right:0;width:360px;max-width:88vw;
  background:var(--bg2);border:1px solid var(--border);border-radius:10px;
  box-shadow:0 12px 32px rgba(0,0,0,.35);backdrop-filter:blur(10px);
  padding:10px;z-index:9998;display:none;font-family:var(--font-mono)}
.nav-search-panel.open{display:block}
.nav-search-input{width:100%;background:var(--bg3);border:1px solid var(--border);
  border-radius:7px;color:var(--text);padding:9px 12px;font-family:var(--font-mono);
  font-size:14px;outline:none;transition:border-color .15s}
.nav-search-input:focus{border-color:var(--accent2);box-shadow:0 0 0 2px rgba(var(--accent-rgb),.15)}
.nav-search-results{max-height:50vh;overflow-y:auto;margin-top:8px}
.nav-search-hit{display:flex;flex-direction:column;gap:2px;padding:8px 9px;
  border-radius:7px;text-decoration:none;color:var(--text);margin-bottom:3px;transition:background .15s}
.nav-search-hit:hover{background:rgba(var(--accent-rgb),.1)}
.nav-search-hit-page{font-size:10px;letter-spacing:1px;color:var(--accent2);
  font-weight:700;text-transform:uppercase}
.nav-search-hit-title{font-size:13px;font-weight:600;color:var(--text)}
.nav-search-hit-snippet{font-size:12px;color:var(--muted);line-height:1.4}
.nav-search-empty,.nav-search-hint{padding:14px 6px;color:var(--muted);font-size:12.5px;text-align:center}
@keyframes rcSearchFlash{
  0%{box-shadow:0 0 0 0 rgba(var(--accent-rgb),0)}
  15%{box-shadow:0 0 0 6px rgba(var(--accent-rgb),.35)}
  100%{box-shadow:0 0 0 0 rgba(var(--accent-rgb),0)}
}
.rc-search-hit-flash{animation:rcSearchFlash 1.3s ease-out 2;
  outline:2px solid var(--accent2);outline-offset:3px;border-radius:4px}
`;

  function injectStyle() {
    const st = document.createElement('style');
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  function init() {
    const nav = document.querySelector('nav.app-nav');
    if (!nav) return;
    injectStyle();

    const wrap = document.createElement('div');
    wrap.className = 'nav-search-wrap';
    wrap.innerHTML =
      '<button type="button" class="nav-search-btn" id="navSearchBtn" title="' +
      esc(rcT('Rechercher dans les pages')) + '">' +
      '<svg viewBox="0 0 18 18" width="15" height="15" fill="none" stroke="currentColor" ' +
      'stroke-width="1.6" stroke-linecap="round"><circle cx="7.8" cy="7.8" r="5.3"/>' +
      '<line x1="11.8" y1="11.8" x2="16.5" y2="16.5"/></svg></button>' +
      '<div class="nav-search-panel" id="navSearchPanel">' +
      '<input type="text" id="navSearchInput" class="nav-search-input" autocomplete="off" ' +
      'placeholder="' + esc(rcT('Rechercher… (ex. SSTV, panadapter, MySQL)')) + '">' +
      '<div class="nav-search-results" id="navSearchResults">' +
      '<div class="nav-search-hint">' + esc(rcT('Tapez au moins 2 caractères')) + '</div></div></div>';

    const spacer = nav.querySelector('.nav-spacer');
    if (spacer) nav.insertBefore(wrap, spacer);
    else nav.appendChild(wrap);

    const btn = wrap.querySelector('#navSearchBtn');
    const panel = wrap.querySelector('#navSearchPanel');
    const input = wrap.querySelector('#navSearchInput');
    const resultsEl = wrap.querySelector('#navSearchResults');

    function open() {
      panel.classList.add('open');
      btn.classList.add('active');
      setTimeout(() => input.focus(), 10);
    }
    function close() {
      panel.classList.remove('open');
      btn.classList.remove('active');
    }
    btn.addEventListener('click', e => {
      e.stopPropagation();
      panel.classList.contains('open') ? close() : open();
    });
    panel.addEventListener('click', e => e.stopPropagation());
    document.addEventListener('click', () => close());
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });

    let seq = 0;
    let debounceTimer = null;

    function renderResults(results) {
      if (!results.length) {
        resultsEl.innerHTML = '<div class="nav-search-empty">' + esc(rcT('Aucun résultat')) + '</div>';
        return;
      }
      resultsEl.innerHTML = results.map(r => {
        const href = r.page + '?rcq=' + encodeURIComponent(input.value.trim());
        return '<a class="nav-search-hit" href="' + esc(href) + '">' +
          '<span class="nav-search-hit-page">' + esc(r.page_label) + '</span>' +
          (r.title ? '<span class="nav-search-hit-title">' + esc(r.title) + '</span>' : '') +
          '<span class="nav-search-hit-snippet">' + esc(r.snippet) + '</span></a>';
      }).join('');
    }

    function runSearch(q) {
      const mySeq = ++seq;
      fetch('/search?q=' + encodeURIComponent(q))
        .then(r => r.json())
        .then(data => { if (mySeq === seq) renderResults(data.results || []); })
        .catch(() => { if (mySeq === seq) resultsEl.innerHTML = ''; });
    }

    input.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      const q = input.value.trim();
      if (q.length < 2) {
        resultsEl.innerHTML = '<div class="nav-search-hint">' + esc(rcT('Tapez au moins 2 caractères')) + '</div>';
        return;
      }
      debounceTimer = setTimeout(() => runSearch(q), 220);
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        const first = resultsEl.querySelector('.nav-search-hit');
        if (first) first.click();
      }
    });
  }

  // ── Page cible d'un clic sur un résultat (?rcq=...) : retrouve le premier
  //    passage correspondant dans le texte visible et le fait défiler/flash.
  //    Tourne sur TOUTE page incluant ce script, pas seulement celle où le
  //    panneau a été ouvert. ───────────────────────────────────────────────
  function findMatch(needle) {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    let node;
    while ((node = walker.nextNode())) {
      if (!node.nodeValue || !node.nodeValue.toLowerCase().includes(needle)) continue;
      const el = node.parentElement;
      if (!el || el.closest('script,style,.nav-search-panel')) continue;
      return el;
    }
    return null;
  }

  // Beaucoup de panneaux (macros, listes chargées par fetch...) ne sont
  // remplis qu'APRÈS DOMContentLoaded — un seul essai à ce moment-là rate
  // fréquemment un résultat pourtant bien réel (vérifié en navigateur sur
  // le panneau CALLBOT de logx_logbook.html). Réessaie donc à intervalles
  // pendant quelques secondes avant d'abandonner.
  function highlightFromQuery() {
    let q;
    try { q = new URLSearchParams(location.search).get('rcq'); } catch (e) { return; }
    if (!q) return;
    const needle = q.trim().toLowerCase();
    if (needle.length < 2) return;

    let attempts = 0;
    const MAX_ATTEMPTS = 8; // ~2.4s au total, cf. commentaire ci-dessus

    function tryOnce() {
      const target = findMatch(needle);
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        target.classList.add('rc-search-hit-flash');
        setTimeout(() => target.classList.remove('rc-search-hit-flash'), 2700);
        cleanUrl();
        return;
      }
      attempts++;
      if (attempts < MAX_ATTEMPTS) setTimeout(tryOnce, 300);
      else cleanUrl(); // rien trouvé : au moins ne pas garder un paramètre mort
    }

    function cleanUrl() {
      const url = new URL(location.href);
      url.searchParams.delete('rcq');
      history.replaceState(null, '', url.pathname + (url.search || '') + url.hash);
    }

    tryOnce();
  }

  function boot() {
    init();
    highlightFromQuery();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
