// Carte de sortie XOTA — rendu canvas HORS-LIGNE (aucune tuile externe) d'une
// « carte de sortie » partageable en PNG. La carte Leaflet interactive du
// logbook (logx_qso_map.js) reste inchangée : ceci est un rendu DIFFÉRENT,
// dédié au partage, insensible au blocage antivirus (pas de requête réseau au
// dessin). Charge AVANT logx_logbook.js ; ne s'exécute qu'à l'appel, lit
// qsoLog/locLL/myLocator/myCall en toute sécurité (même garantie d'ordre que
// logx_qso_map.js).
//
// Ce fichier expose window.LogxCarteSortie. Les fonctions PURES ci-dessous
// (projection, filtre, position, stats, couleur) sont testées hors DOM
// (py_mini_racer) ; le dessin canvas et l'export PNG (imperatifs, non
// testables en unitaire) viennent après.
(function(){
  'use strict';

  // Palette par bande, alignée sur logx_qso_map.js (BAND_COLORS) pour que la
  // carte de sortie et la carte du logbook parlent le même langage couleur.
  const BAND_COLORS = {
    '1.8':'#FF2D55','3.5':'#FF6B35','7':'#FF9F0A','14':'#FFD60A','21':'#34C759',
    '28':'#00C7BE','50':'#00D4FF','70':'#40C8FF','144':'#BF5AF2','432':'#FF8C00',
    '1296':'#FF2D55','2320':'#00FF88','3400':'#E040FB','default':'#AAAAAA',
  };
  function couleurBande(band){ return BAND_COLORS[band] || BAND_COLORS['default']; }

  // Projection équirectangulaire : lon∈[-180,180]→x∈[0,w], lat∈[90,-90]→y∈[0,h].
  // Trivialement inversible et sans dépendance — le fond de carte embarqué est
  // dessiné dans la MÊME projection, donc rayons et côtes coïncident.
  function projeterEquirect(lat, lon, w, h){
    const x = (Number(lon) + 180) / 360 * w;
    const y = (90 - Number(lat)) / 180 * h;
    return { x: x, y: y };
  }

  // Un QSO appartient-il à CETTE sortie (programme + référence que J'ACTIVE) ?
  // Compare my_sig/my_sig_info (posés par le mode portable). Insensible à la
  // casse (les réf. SOTA/POTA sont normalisées en majuscules).
  function matchSortie(qso, prog, ref){
    if(!qso) return false;
    const p = String(prog || '').toUpperCase();
    const r = String(ref || '').toUpperCase();
    return String(qso.my_sig || '').toUpperCase() === p
        && String(qso.my_sig_info || '').toUpperCase() === r;
  }

  // Position d'une station contactée, pour la tracer :
  //   - locator Maidenhead ≥ 6 → position PRÉCISE (approx:false) ;
  //   - sinon indicatif → centroïde DXCC (approx:true, cty.dat via /dxcc/positions) ;
  //   - sinon null (impossible à placer, ex. indicatif inconnu sans locator).
  // locResolver(locator)->{lat,lon}|null (locLL côté page) ; dxccPos = map
  // {INDICATIF:{lat,lon,country}} renvoyée par l'endpoint serveur.
  function positionStation(qso, dxccPos, locResolver){
    if(!qso) return null;
    const loc = String(qso.locator || '');
    if(loc.length >= 6 && typeof locResolver === 'function'){
      const ll = locResolver(loc);
      if(ll && ll.lat != null && ll.lon != null){
        return { lat: ll.lat, lon: ll.lon, approx: false, source: 'locator' };
      }
    }
    const call = String(qso.call || '').toUpperCase();
    const p = dxccPos && dxccPos[call];
    if(p && p.lat != null && p.lon != null){
      return { lat: p.lat, lon: p.lon, approx: true, source: 'indicatif' };
    }
    return null;
  }

  // Statistiques du bandeau : nb QSO, nb pays DISTINCTS, bandes triées.
  // paysDe(qso)->pays (chaîne) ; '' ou absent = pays inconnu (non compté).
  // Le tri des bandes est NUMÉRIQUE (14 avant 144, pas l'ordre lexical).
  function statsSortie(qsos, paysDe){
    const liste = qsos || [];
    const pays = new Set();
    const bandes = new Set();
    liste.forEach(function(q){
      if(typeof paysDe === 'function'){
        const c = paysDe(q);
        if(c) pays.add(c);
      }
      if(q && q.band) bandes.add(String(q.band));
    });
    const bandesTri = Array.from(bandes).sort(function(a, b){
      return parseFloat(a) - parseFloat(b);
    });
    return { nQso: liste.length, nPays: pays.size, bandes: bandesTri };
  }

  // Sorties DISTINCTES que l'opérateur a lui-même loggées en portable (couples
  // my_sig/my_sig_info non vides) — sert à peupler le sélecteur avant de tracer
  // une carte (une sortie = un my_sig/my_sig_info, jamais un my_call/QSO isolé).
  // Regroupement insensible à la casse (même logique que matchSortie), mais le
  // couple programme+réf ressorti est normalisé en MAJUSCULES — il est réinjecté
  // tel quel dans matchSortie() par l'appelant, qui compare aussi en majuscules.
  // Triées par date la plus RÉCENTE d'abord (dateMax décroissant) ; une sortie
  // dont aucun QSO ne porte de date connue est reléguée en fin de liste.
  function listerSorties(qsoLog){
    const liste = qsoLog || [];
    const groupes = {};
    const ordre = [];
    liste.forEach(function(q){
      if(!q) return;
      const prog = String(q.my_sig || '').trim();
      const ref = String(q.my_sig_info || '').trim();
      if(!prog || !ref) return;
      const key = prog.toUpperCase() + '|' + ref.toUpperCase();
      let g = groupes[key];
      if(!g){
        g = { program: prog.toUpperCase(), ref: ref.toUpperCase(), count: 0, dateMin: '', dateMax: '' };
        groupes[key] = g;
        ordre.push(key);
      }
      g.count++;
      const d = String(q.date || '');
      if(d){
        if(!g.dateMin || d < g.dateMin) g.dateMin = d;
        if(!g.dateMax || d > g.dateMax) g.dateMax = d;
      }
    });
    const out = ordre.map(function(k){ return groupes[k]; });
    out.sort(function(a, b){
      if(a.dateMax === b.dateMax) return 0;
      if(!a.dateMax) return 1;    // pas de date connue -> en dernier
      if(!b.dateMax) return -1;
      return a.dateMax < b.dateMax ? 1 : -1;   // plus récent d'abord
    });
    return out;
  }

  window.LogxCarteSortie = {
    couleurBande: couleurBande,
    projeterEquirect: projeterEquirect,
    matchSortie: matchSortie,
    positionStation: positionStation,
    statsSortie: statsSortie,
    listerSorties: listerSorties,
    _BAND_COLORS: BAND_COLORS,
  };
})();

// ─── RENDU CANVAS + ORCHESTRATION UI (impératif, hors du champ des tests
// unitaires — voir concours/tests/test_xota_carte_js.py pour ce qui EST
// testé). Lit qsoLog/myCall/myLocator/locLL/trT/trF/BAND_LABELS, tous définis
// plus haut dans logx_logbook.js mais lus uniquement à l'intérieur du corps
// des fonctions ci-dessous — jamais au chargement du script — donc aucun
// souci d'ordre malgré ce fichier chargé AVANT logx_logbook.js (même garantie
// que logx_qso_map.js, voir l'en-tête de ce fichier).
(function(){
  'use strict';

  const C = window.LogxCarteSortie;

  // Repli identité si logx_logbook.js n'est pas chargé (page de test, page
  // sans logbook) : jamais de plantage, jamais de texte "undefined" affiché.
  function _trT(s){ return (typeof trT === 'function') ? trT(s) : s; }
  function _trF(s, p){
    if(typeof trF === 'function') return trF(s, p);
    let o = s;
    for(const k in (p || {})) o = o.split('{' + k + '}').join(p[k]);
    return o;
  }
  function _bandLabel(b){
    return (typeof BAND_LABELS !== 'undefined' && BAND_LABELS[b]) || (b + ' MHz');
  }
  function _monCall(){ return (typeof myCall !== 'undefined' && myCall) || ''; }
  function _monLocator(){ return (typeof myLocator !== 'undefined') ? myLocator : ''; }
  function _monLog(){ return (typeof qsoLog !== 'undefined' && qsoLog) || []; }
  function _locLL(loc){ return (typeof locLL === 'function') ? locLL(loc) : null; }

  // Valeur d'une variable de thème courante ('--accent', '--bg2'…). Lue sur
  // <body> (pas <html>) : body.day-mode redéfinit les tokens sur le SÉLECTEUR
  // body, getComputedStyle(document.documentElement) ne le verrait pas (l'
  // héritage des custom properties descend le DOM, <html> n'est pas
  // descendant de <body>).
  function _cssVar(name, repli){
    try{
      const v = getComputedStyle(document.body).getPropertyValue(name).trim();
      if(v) return v;
      const v2 = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      return v2 || repli;
    }catch(e){ return repli; }
  }

  // ─── Fond de carte : GeoJSON monde (Natural Earth 110m), mis en cache une
  // fois pour toute la session — aucune requête réseau au-delà de la 1re
  // ouverture, jamais d'appel externe (endpoint local /data/world_geojson).
  let _fondPromise = null;
  function _fond(){
    if(!_fondPromise){
      _fondPromise = fetch('/data/world_geojson')
        .then(function(r){ return r.ok ? r.json() : null; })
        .catch(function(){ return null; });
    }
    return _fondPromise;
  }

  function _dessinerFond(ctx, geo, rect){
    if(!geo || !geo.features) return;
    ctx.save();
    ctx.lineWidth = 0.7;
    ctx.strokeStyle = _cssVar('--border', '#34363A');
    ctx.fillStyle = _cssVar('--bg3', '#25272B');
    geo.features.forEach(function(f){
      const geom = f && f.geometry;
      if(!geom) return;
      const polys = geom.type === 'Polygon' ? [geom.coordinates]
                  : geom.type === 'MultiPolygon' ? geom.coordinates
                  : null;
      if(!polys) return;
      polys.forEach(function(rings){
        (rings || []).forEach(function(ring){
          if(!ring || !ring.length) return;
          ctx.beginPath();
          ring.forEach(function(pt, j){
            const p = C.projeterEquirect(pt[1], pt[0], rect.w, rect.h);
            const x = rect.x + p.x, y = rect.y + p.y;
            if(j === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
          });
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
        });
      });
    });
    ctx.restore();
  }

  function _dessinerLegende(ctx, rect, bandes){
    if(!bandes || !bandes.length) return;
    const pad = 10, sw = 12, lh = 18;
    const w = 132, h = pad * 2 + lh * bandes.length + 16;
    const x = rect.x + 12, y = rect.y + 12;
    ctx.save();
    ctx.fillStyle = 'rgba(10,11,20,.6)';
    ctx.fillRect(x, y, w, h);
    ctx.strokeStyle = _cssVar('--border', '#34363A');
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, w, h);
    ctx.font = '11px monospace';
    ctx.textBaseline = 'middle';
    bandes.forEach(function(b, i){
      const yy = y + pad + i * lh + lh / 2;
      ctx.fillStyle = C.couleurBande(b);
      ctx.fillRect(x + pad, yy - 5, sw, 10);
      ctx.fillStyle = '#EDEDED';
      ctx.fillText(_bandLabel(b), x + pad + sw + 6, yy);
    });
    ctx.font = '10px monospace';
    ctx.fillStyle = '#BFC2C8';
    ctx.fillText(_trT('○ pointillé = position approximative (pays)'), x + pad, y + h - 8);
    ctx.restore();
  }

  function _dessinerBandeau(ctx, rect, titre, stats){
    ctx.save();
    ctx.fillStyle = _cssVar('--bg2', '#1D1F22');
    ctx.fillRect(rect.x, rect.y, rect.w, rect.h);
    ctx.strokeStyle = _cssVar('--accent', '#E8964A');
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(rect.x, rect.y + rect.h - 1);
    ctx.lineTo(rect.x + rect.w, rect.y + rect.h - 1);
    ctx.stroke();

    const midY = rect.y + rect.h / 2;
    ctx.textBaseline = 'middle';
    ctx.fillStyle = _cssVar('--accent', '#E8964A');
    ctx.font = 'bold ' + Math.round(rect.h * 0.30) + 'px monospace';
    const ligne1 = (titre.call || '') + '  ·  ' + (titre.program || '') + ' ' + (titre.ref || '');
    ctx.fillText(ligne1, 18, midY - rect.h * 0.17);

    ctx.fillStyle = _cssVar('--text', '#EDEDED');
    ctx.font = Math.round(rect.h * 0.19) + 'px monospace';
    const bandesTxt = (stats.bandes || []).map(_bandLabel).join(', ');
    const ligne2 = _trF('{n} QSO · {p} pays · {b} · {d}',
      {n: stats.nQso, p: stats.nPays, b: bandesTxt, d: titre.date || ''});
    ctx.fillText(ligne2, 18, midY + rect.h * 0.20);
    ctx.restore();
  }

  // Dessine la carte de sortie complète dans `canvas` (déjà dimensionné par
  // l'appelant). options = { origine:{lat,lon}, stations:[{call,band,lat,lon,
  // approx}], stats:{nQso,nPays,bandes}, titre:{call,program,ref,date} }.
  // Impératif + async (fetch du fond) -> non testable en py_mini_racer/unitaire,
  // c'est attendu (voir en-tête de fichier).
  async function dessinerCarteSortie(canvas, opts){
    opts = opts || {};
    const stations = opts.stations || [];
    const origine = opts.origine || null;
    const stats = opts.stats || {nQso: 0, nPays: 0, bandes: []};
    const titre = opts.titre || {};
    const ctx = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const bandeauH = Math.round(H * 0.13);
    const rect = {x: 0, y: bandeauH, w: W, h: H - bandeauH};

    ctx.fillStyle = _cssVar('--bg', '#17181A');
    ctx.fillRect(0, 0, W, H);

    const geo = await _fond();
    _dessinerFond(ctx, geo, rect);

    if(origine && origine.lat != null && origine.lon != null){
      const o = C.projeterEquirect(origine.lat, origine.lon, rect.w, rect.h);
      const ox = rect.x + o.x, oy = rect.y + o.y;

      // Rayons d'abord (sous les marqueurs), colorés par bande.
      stations.forEach(function(st){
        if(!st || st.lat == null || st.lon == null) return;
        const p = C.projeterEquirect(st.lat, st.lon, rect.w, rect.h);
        const sx = rect.x + p.x, sy = rect.y + p.y;
        ctx.save();
        ctx.globalAlpha = 0.5;
        ctx.strokeStyle = C.couleurBande(st.band);
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(ox, oy);
        ctx.lineTo(sx, sy);
        ctx.stroke();
        ctx.restore();
      });

      // Marqueurs stations : plein = position précise, pointillé creux = pays
      // approximatif (jamais confondu visuellement avec une position exacte).
      stations.forEach(function(st){
        if(!st || st.lat == null || st.lon == null) return;
        const p = C.projeterEquirect(st.lat, st.lon, rect.w, rect.h);
        const sx = rect.x + p.x, sy = rect.y + p.y;
        ctx.save();
        const coul = C.couleurBande(st.band);
        if(st.approx){
          ctx.strokeStyle = coul;
          ctx.lineWidth = 1.4;
          ctx.setLineDash([2, 2]);
          ctx.beginPath();
          ctx.arc(sx, sy, 4, 0, Math.PI * 2);
          ctx.stroke();
        } else {
          ctx.fillStyle = coul;
          ctx.beginPath();
          ctx.arc(sx, sy, 3.5, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.restore();
      });

      // Marqueur origine (losange cuivre/accent) au-dessus de tout le reste.
      ctx.save();
      ctx.fillStyle = _cssVar('--accent', '#E8964A');
      ctx.strokeStyle = _cssVar('--bg', '#17181A');
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(ox, oy - 7);
      ctx.lineTo(ox + 7, oy);
      ctx.lineTo(ox, oy + 7);
      ctx.lineTo(ox - 7, oy);
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }

    _dessinerLegende(ctx, rect, stats.bandes);
    _dessinerBandeau(ctx, {x: 0, y: 0, w: W, h: bandeauH}, titre, stats);
  }

  // ─── Orchestration UI : overlay construit dynamiquement (même idiome que
  // logx_search.js/logx_statusbar.js — <style> injecté une fois, DOM créé au
  // premier appel puis réutilisé). Aucune requête réseau externe : seulement
  // /dxcc/positions et /data/world_geojson (nos endpoints localhost).
  let _overlayEl = null, _bodyEl = null;

  function _assurerOverlay(){
    if(_overlayEl) return _overlayEl;

    const style = document.createElement('style');
    style.textContent =
      '.xota-carte-overlay{position:fixed;inset:0;background:rgba(7,8,15,.92);display:none;align-items:center;justify-content:center;z-index:2000}' +
      '.xota-carte-overlay.show{display:flex}' +
      '.xota-carte-box{background:var(--bg2);border:2px solid var(--accent2);border-radius:14px;padding:20px;width:min(96vw,1020px);max-height:92vh;overflow-y:auto;box-shadow:0 0 40px rgba(var(--accent-rgb),.25)}' +
      '.xota-carte-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;gap:12px}' +
      '.xota-carte-hdr h3{font-family:var(--font-display);font-size:17px;font-weight:900;color:var(--accent2);letter-spacing:.2px;margin:0}' +
      '.xota-carte-close{cursor:pointer;background:none;border:none;color:var(--muted);padding:4px;line-height:1}' +
      '.xota-carte-close:hover{color:var(--red)}' +
      '.xota-liste{display:flex;flex-direction:column;gap:8px;max-height:64vh;overflow-y:auto}' +
      '.xota-sortie-btn{display:flex;justify-content:space-between;gap:14px;align-items:center;width:100%;text-align:left;background:var(--bg3);border:1px solid var(--border);border-radius:8px;color:var(--text);font-family:var(--font-mono);font-size:14px;padding:12px 14px;cursor:pointer;transition:border-color .15s}' +
      '.xota-sortie-btn:hover{border-color:var(--accent2)}' +
      '.xota-sortie-ref{color:var(--accent);font-weight:800;letter-spacing:1px;white-space:nowrap}' +
      '.xota-sortie-meta{color:var(--muted);font-size:12px;white-space:nowrap}' +
      '.xota-carte-msg{color:var(--muted);font-family:var(--font-mono);font-size:14px;padding:24px 4px;line-height:1.6}' +
      '.xota-canvas-wrap{width:100%;text-align:center}' +
      '.xota-canvas-wrap canvas{width:100%;height:auto;border-radius:8px;border:1px solid var(--border);display:block}' +
      '.xota-carte-actions{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap;align-items:center}' +
      '.xota-btn{background:var(--bg3);border:1px solid var(--border);border-radius:7px;color:var(--text);font-family:var(--font-mono);font-size:13px;padding:9px 16px;cursor:pointer}' +
      '.xota-btn:hover{border-color:var(--accent2)}' +
      '.xota-btn.primary{background:linear-gradient(135deg,var(--accent2),#0080FF);border:none;color:#fff;font-weight:700}' +
      '.xota-carte-note{color:var(--muted);font-size:12px;font-family:var(--font-mono)}';
    document.head.appendChild(style);

    const overlay = document.createElement('div');
    overlay.className = 'xota-carte-overlay';
    overlay.id = 'xotaCarteOverlay';
    overlay.innerHTML =
      '<div class="xota-carte-box">' +
        '<div class="xota-carte-hdr">' +
          '<h3></h3>' +
          '<button type="button" class="xota-carte-close" title="Fermer">' +
            '<svg viewBox="0 0 18 18" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg>' +
          '</button>' +
        '</div>' +
        '<div class="xota-carte-body"></div>' +
      '</div>';
    document.body.appendChild(overlay);

    overlay.querySelector('.xota-carte-close').addEventListener('click', _fermerCarteSortie);
    overlay.addEventListener('click', function(e){ if(e.target === overlay) _fermerCarteSortie(); });
    document.addEventListener('keydown', function(e){
      if(e.key === 'Escape' && overlay.classList.contains('show')) _fermerCarteSortie();
    });
    overlay.querySelector('h3').textContent = _trT('CARTE DE SORTIE');

    _overlayEl = overlay;
    _bodyEl = overlay.querySelector('.xota-carte-body');
    return overlay;
  }

  function _fermerCarteSortie(){
    if(_overlayEl) _overlayEl.classList.remove('show');
  }

  function _fmtPeriode(dmin, dmax){
    const f = function(d){
      if(!d || d.length !== 8) return '';
      return d.slice(6, 8) + '/' + d.slice(4, 6) + '/' + d.slice(0, 4);
    };
    const a = f(dmin), b = f(dmax);
    if(!a && !b) return '';
    return a === b ? a : (a + ' → ' + b);
  }

  // Point d'entrée public (bouton du logbook). Ouvre l'overlay et affiche
  // d'abord le sélecteur de sorties.
  function ouvrirCarteSortie(){
    const overlay = _assurerOverlay();
    overlay.classList.add('show');
    _afficherListeSorties();
  }

  function _afficherListeSorties(){
    const sorties = C.listerSorties(_monLog());
    if(!sorties.length){
      _bodyEl.innerHTML = '<p class="xota-carte-msg"></p>';
      _bodyEl.querySelector('p').textContent = _trT(
        'Aucune sortie enregistrée pour l’instant. Sors en portable avec un ' +
        'programme (SOTA/POTA/WWFF…) pour créer ta première carte de sortie.');
      return;
    }
    const wrap = document.createElement('div');
    wrap.className = 'xota-liste';
    sorties.forEach(function(s){
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'xota-sortie-btn';
      const g = document.createElement('span');
      g.className = 'xota-sortie-ref';
      g.textContent = s.program + ' ' + s.ref;
      const meta = document.createElement('span');
      meta.className = 'xota-sortie-meta';
      meta.textContent = _trF('{n} QSO · {d}', {n: s.count, d: _fmtPeriode(s.dateMin, s.dateMax)});
      b.appendChild(g);
      b.appendChild(meta);
      b.addEventListener('click', function(){ _genererCarte(s); });
      wrap.appendChild(b);
    });
    _bodyEl.innerHTML = '';
    _bodyEl.appendChild(wrap);
  }

  function _paysDe(dxccPos){
    return function(q){
      if(q.country) return q.country;
      const c = dxccPos[String(q.call || '').trim().toUpperCase()];
      return c ? c.country : '';
    };
  }

  async function _genererCarte(sortie){
    _bodyEl.innerHTML = '<p class="xota-carte-msg"></p>';
    _bodyEl.querySelector('p').textContent = _trT('Génération de la carte…');

    const filtres = _monLog().filter(function(q){ return C.matchSortie(q, sortie.program, sortie.ref); });

    // Indicatifs SANS locator précis (≥6) -> résolution serveur (cty.dat).
    const vus = {};
    const calls = [];
    filtres.forEach(function(q){
      if(String(q.locator || '').length >= 6) return;
      const c = String(q.call || '').trim().toUpperCase();
      if(!c || vus[c]) return;
      vus[c] = 1;
      calls.push(c);
    });

    let dxccPos = {};
    if(calls.length){
      try{
        const r = await fetch('/dxcc/positions', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({calls: calls}),
        });
        if(r.ok){
          const d = await r.json();
          dxccPos = (d && d.positions) || {};
        }
      }catch(e){ /* hors-ligne : ces stations resteront non localisées */ }
    }

    // Origine = la référence de sortie elle-même (lat/lon direct, sinon son
    // locator) ; repli sur le QTH déclaré si la base ne connaît ni l'un ni
    // l'autre (ex. réf non trouvée dans la base locale).
    let origine = null, origineNote = '';
    let entry = null;
    try{
      entry = window.LogxRefInfo ? await window.LogxRefInfo.lookup(sortie.program, sortie.ref) : null;
    }catch(e){ entry = null; }
    if(entry && entry.lat != null && entry.lon != null){
      origine = {lat: entry.lat, lon: entry.lon};
    } else if(entry && entry.locator){
      origine = _locLL(entry.locator);
    }
    if(!origine){
      origine = _locLL(_monLocator());
      if(origine) origineNote = _trT('Position de la sortie inconnue — carte centrée sur ton QTH déclaré.');
    }

    if(!origine){
      _bodyEl.innerHTML = '<p class="xota-carte-msg"></p>';
      _bodyEl.querySelector('p').textContent = _trT(
        'Origine introuvable : ni la référence de sortie ni ton QTH ne portent de ' +
        'position connue. Renseigne ton locator dans CONFIGURATION pour générer la carte.');
      return;
    }

    const stations = [];
    let nonLocalisees = 0;
    filtres.forEach(function(q){
      const pos = C.positionStation(q, dxccPos, _locLL);
      if(!pos){ nonLocalisees++; return; }
      stations.push({call: q.call, band: q.band, lat: pos.lat, lon: pos.lon, approx: pos.approx});
    });

    const stats = C.statsSortie(filtres, _paysDe(dxccPos));
    const titre = {
      call: _monCall(),
      program: sortie.program,
      ref: sortie.ref,
      date: _fmtPeriode(sortie.dateMin, sortie.dateMax),
    };

    _bodyEl.innerHTML =
      '<div class="xota-canvas-wrap"><canvas width="1200" height="680"></canvas></div>' +
      '<div class="xota-carte-actions">' +
        '<button type="button" class="xota-btn" data-act="retour"></button>' +
        '<button type="button" class="xota-btn primary" data-act="png"></button>' +
        '<span class="xota-carte-note"></span>' +
      '</div>';
    _bodyEl.querySelector('[data-act="retour"]').textContent = _trT('← Choisir une autre sortie');
    _bodyEl.querySelector('[data-act="png"]').textContent = _trT('Télécharger PNG');

    const notes = [];
    if(origineNote) notes.push(origineNote);
    if(nonLocalisees) notes.push(_trF('{n} station(s) non localisée(s)', {n: nonLocalisees}));
    _bodyEl.querySelector('.xota-carte-note').textContent = notes.join(' · ');

    _bodyEl.querySelector('[data-act="retour"]').addEventListener('click', _afficherListeSorties);

    const canvas = _bodyEl.querySelector('canvas');
    await dessinerCarteSortie(canvas, {origine: origine, stations: stations, stats: stats, titre: titre});

    _bodyEl.querySelector('[data-act="png"]').addEventListener('click', function(){
      _telechargerPNG(canvas, sortie);
    });
  }

  // dataURL -> Blob (canvas.toDataURL, PAS canvas.toBlob : motif explicitement
  // demandé, aligné sur downloadAdifBlob ci-dessous : dataURL/Blob, ancre,
  // clic, PUIS revoke DIFFÉRÉ 40s -- un revoke immédiat peut annuler le
  // téléchargement, cf. concours/logx_export_adif.js:234-244).
  function _dataURLversBlob(dataUrl){
    const parts = dataUrl.split(',');
    const mime = (parts[0].match(/:(.*?);/) || [, 'image/png'])[1];
    const bstr = atob(parts[1]);
    let n = bstr.length;
    const u8 = new Uint8Array(n);
    while(n--){ u8[n] = bstr.charCodeAt(n); }
    return new Blob([u8], {type: mime});
  }

  function _telechargerPNG(canvas, sortie){
    const blob = _dataURLversBlob(canvas.toDataURL('image/png'));
    const a = document.createElement('a');
    const url = URL.createObjectURL(blob);
    a.href = url;
    const call = (_monCall() || 'LOGX').replace('/', '_');
    const nomSortie = (sortie.program + '_' + sortie.ref).replace(/[^A-Za-z0-9_-]/g, '_');
    a.download = call + '_carte_sortie_' + nomSortie + '.png';
    a.click();
    setTimeout(function(){ URL.revokeObjectURL(url); }, 40000);
  }

  C.dessinerCarteSortie = dessinerCarteSortie;
  C.ouvrirCarteSortie = ouvrirCarteSortie;
  window.ouvrirCarteSortie = ouvrirCarteSortie;
})();
