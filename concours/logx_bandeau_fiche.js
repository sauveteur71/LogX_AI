// Fiche « spot » au clic sur un item ACTIF du bandeau défilant — PARTAGÉ par les
// pages qui portent le bandeau MAIS n'ont pas déjà leur propre fiche intégrée
// (accueil, logbook). La page de CHASSE a sa PROPRE fiche (intégrée à #lastRefresh
// / rotor) : ce module n'y est PAS chargé, pour ne pas doubler le handler.
//
// Problème corrigé (F4GLD 03/09/2026) : sans ce module, un clic sur un spot du
// bandeau suivait le href de repli ('logx_chasse.html') -> dialogue « Quitter le
// site » puis navigation vers CHASSE. Attendu : ouvrir une fiche SUR PLACE avec
// un bouton QSY qui règle la radio sur la fréquence du spot.
//
// AUTONOME À DESSEIN : son propre esc(), sa propre CSS (variables de thème,
// jamais de hex codé en dur), sa propre confirmation dans le popup (pas de
// #lastRefresh comme sur CHASSE). N'utilise que window.rcT (repli identité) et
// les endpoints serveur globaux /rig/state, /rig/qsy, /calldb/lookup.
//
// SÛRETÉ : QSY = réglage du VFO en RÉCEPTION, JAMAIS d'émission (pas de PTT, pas
// de séquenceur). Aucune autorisation TX n'est donc requise — voir skill
// tx-human-consent : ce chemin ne peut pas activer d'émission.
(function(){
  'use strict';
  // Idempotent : un double <script> (ou un futur chargement sur une page qui
  // câble déjà sa fiche) ne doit pas brancher deux écouteurs -> deux popups.
  if(window.__lbfCablee) return;
  window.__lbfCablee = true;

  var wrap = document.getElementById('bandeaux');
  if(!wrap) return;                                   // page sans bandeau -> no-op

  function T(s){ try{ return window.rcT ? window.rcT(s) : s; }catch(e){ return s; } }
  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
      return { '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c];
    });
  }
  // « home call » d'un indicatif portable : le plus long segment séparé par '/'
  // (DL1ABC/P -> DL1ABC ET VP8/DL1ABC -> DL1ABC), pour le lookup nom et le lien
  // QRZ. Un simple split('/')[0] renverrait le préfixe, pas l'indicatif de base.
  function homeCall(call){
    var parts = String(call || '').split('/');
    return parts.sort(function(a, b){ return b.length - a.length; })[0] || call;
  }

  // CSS injectée une seule fois. Le bouton QSY est en style « contour » (bordure
  // + fond translucide accent, texte accent) : PAS de remplissage plein, donc
  // aucun piège de contraste texte-sombre-sur-cuivre en mode jour.
  function injecterStyle(){
    if(document.getElementById('lbf-style')) return;
    var st = document.createElement('style');
    st.id = 'lbf-style';
    st.textContent = [
      '#lbf-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);',
      '  z-index:10000;align-items:center;justify-content:center;padding:16px}',
      '#lbf-overlay .lbf-box{background:var(--bg2);border:1px solid var(--border);',
      '  border-radius:12px;max-width:340px;width:100%;padding:16px 18px;',
      '  box-shadow:0 12px 40px rgba(0,0,0,.5)}',
      '.lbf-head{display:flex;align-items:center;justify-content:space-between;',
      '  gap:8px;margin-bottom:10px}',
      '.lbf-title{font-family:var(--font-display,serif);font-weight:900;',
      '  letter-spacing:.2px;color:var(--text)}',
      '.lbf-x{background:none;border:none;color:var(--muted);font-size:18px;',
      '  cursor:pointer;line-height:1;padding:2px 6px}',
      '.lbf-x:hover{color:var(--text)}',
      '.lbf-btn{font-family:var(--font-mono,monospace);font-size:12px;',
      '  padding:5px 11px;border-radius:6px;border:1px solid var(--accent);',
      '  background:rgba(var(--accent-rgb),.12);color:var(--accent);cursor:pointer;',
      '  letter-spacing:1px;font-weight:700;text-decoration:none;display:inline-block}',
      '.lbf-btn:hover{background:rgba(var(--accent-rgb),.22)}',
      '.lbf-status{margin-top:10px;min-height:16px;font-family:var(--font-mono,monospace);',
      '  font-size:12px}'
    ].join('');
    document.head.appendChild(st);
  }

  // État du pilotage CAT (CONFIG) : une seule requête, mémorisée. Sans pilotage
  // activé, on n'affiche pas de bouton QSY (rien à régler) — la fiche reste utile
  // (fréquence, nom, lien QRZ).
  var _rigPromise = null;
  function rigActive(){
    if(!_rigPromise){
      _rigPromise = fetch('/rig/state')
        .then(function(r){ return r.ok ? r.json() : null; })
        .then(function(d){ return !!(d && d.enabled); })
        .catch(function(){ return false; });
    }
    return _rigPromise;
  }

  var _ficheCall = null;   // garde anti-course : ignore un lookup revenu après ouverture d'une autre fiche

  function fermer(){ var ov = document.getElementById('lbf-overlay'); if(ov) ov.style.display = 'none'; }

  function qsy(freqKhz, call, statusEl){
    // MÊME contrat que la page CHASSE : on poste freq_khz, le serveur convertit
    // et règle le VFO. Réception seule, aucune émission.
    statusEl.textContent = 'QSY ' + freqKhz + ' kHz…';
    statusEl.style.color = 'var(--muted)';
    fetch('/rig/qsy', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ freq_khz: parseFloat(freqKhz) })
    }).then(function(r){ return r.json(); }).then(function(d){
      statusEl.textContent = d && d.ok
        ? '📻 QSY ' + freqKhz + ' kHz → ' + call
        : '❌ ' + ((d && d.error) || T('échec CAT'));
      statusEl.style.color = (d && d.ok) ? 'var(--green)' : 'var(--red)';
    }).catch(function(){
      statusEl.textContent = '❌ ' + T('serveur injoignable');
      statusEl.style.color = 'var(--red)';
    });
  }

  function ouvrir(d){
    injecterStyle();
    var call = d.call || '?';
    _ficheCall = call;
    var ov = document.getElementById('lbf-overlay');
    if(!ov){
      ov = document.createElement('div');
      ov.id = 'lbf-overlay';
      ov.addEventListener('click', function(e){ if(e.target === ov) fermer(); });
      ov.innerHTML = '<div class="lbf-box"><div class="lbf-head">'
        + '<span class="lbf-title" id="lbf-title"></span>'
        + '<button class="lbf-x" id="lbf-x" aria-label="' + esc(T('fermer')) + '">✕</button>'
        + '</div><div id="lbf-body"></div></div>';
      document.body.appendChild(ov);
      document.getElementById('lbf-x').addEventListener('click', fermer);
      document.addEventListener('keydown', function(e){ if(e.key === 'Escape') fermer(); });
    }
    document.getElementById('lbf-title').textContent = '📇 ' + T('Fiche') + ' — ' + call;

    var lignes = [];
    if(d.entity){
      var neuf = d.neuf ? ' <span style="color:var(--green);font-weight:800">' + esc(T('NOUVEAU PAYS')) + '</span>' : '';
      lignes.push('<div style="font-size:15px;font-weight:700;color:var(--text)">' + esc(d.entity) + neuf + '</div>');
    }
    var qrg = [];
    if(d.freq) qrg.push(esc((Number(d.freq) / 1000).toFixed(3)) + ' MHz');
    if(d.band) qrg.push(esc(d.band));
    if(d.mode) qrg.push(esc(d.mode));
    if(qrg.length) lignes.push('<div style="color:var(--accent2);font-weight:700;margin-top:4px">📡 ' + qrg.join(' · ') + '</div>');
    lignes.push('<div id="lbf-nom" style="color:var(--muted);margin-top:6px">' + esc(T('Nom')) + ' : …</div>');
    lignes.push('<div id="lbf-actions" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px"></div>');
    lignes.push('<div class="lbf-status" id="lbf-status"></div>');
    document.getElementById('lbf-body').innerHTML = lignes.join('');

    // Actions : QSY (si CAT activé ET fréquence connue) + lien QRZ. Le bouton QSY
    // est ajouté APRÈS résolution de /rig/state pour ne pas le montrer si le
    // pilotage est coupé (on ne peut rien régler).
    var actions = document.getElementById('lbf-actions');
    var qrz = document.createElement('a');
    qrz.className = 'lbf-btn';
    qrz.href = 'https://www.qrz.com/db/' + encodeURIComponent(homeCall(call));
    qrz.target = '_blank'; qrz.rel = 'noopener';
    qrz.textContent = T('Ouvrir sur QRZ.com') + ' ↗';
    actions.appendChild(qrz);

    if(d.freq){
      rigActive().then(function(ok){
        if(_ficheCall !== call || !ok) return;         // fiche changée entre-temps, ou CAT coupé
        if(document.getElementById('lbf-qsy')) return;  // déjà posé
        var b = document.createElement('button');
        b.className = 'lbf-btn'; b.id = 'lbf-qsy';
        b.textContent = '▶ QSY ' + esc(d.freq) + ' kHz';
        b.title = T('Régler la radio sur') + ' ' + d.freq + ' kHz';
        b.addEventListener('click', function(){
          qsy(d.freq, call, document.getElementById('lbf-status'));
        });
        actions.insertBefore(b, actions.firstChild);    // QSY en premier
      });
    }

    ov.style.display = 'flex';

    // Nom de l'opérateur : lookup best-effort. L'échec n'empêche rien.
    fetch('/calldb/lookup/' + encodeURIComponent(homeCall(call)))
      .then(function(r){ return r.json(); }).then(function(j){
        if(_ficheCall !== call) return;                 // résultat obsolète
        var el = document.getElementById('lbf-nom'); if(!el) return;
        if(j && j.name){
          el.innerHTML = esc(T('Nom')) + ' : <b style="color:var(--text)">' + esc(j.name) + '</b>'
            + (j.locator ? ' · ' + esc(j.locator) : '');
        } else {
          el.textContent = T('Nom') + ' : ' + T('inconnu');
        }
      }).catch(function(){
        var el = document.getElementById('lbf-nom'); if(el) el.textContent = T('Nom') + ' : —';
      });
  }

  // Clic DÉLÉGUÉ sur #bandeaux (un seul écouteur, robuste aux re-rendus du
  // contenu). On n'intercepte QUE les items ACTIFS (data-fiche) : les items « à
  // venir » restent de simples liens. preventDefault -> pas de navigation.
  wrap.addEventListener('click', function(ev){
    var a = ev.target.closest ? ev.target.closest('a.rcb-item[data-fiche]') : null;
    if(!a) return;
    ev.preventDefault();
    ouvrir({
      call:   a.getAttribute('data-call')   || '',
      freq:   a.getAttribute('data-freq')   || '',
      band:   a.getAttribute('data-band')   || '',
      mode:   a.getAttribute('data-mode')   || '',
      entity: a.getAttribute('data-entity') || '',
      neuf:   a.getAttribute('data-neuf')   || ''
    });
  });

  // Exposé pour les tests (logique PURE, testable en V8 sans DOM).
  window.LogxBandeauFiche = { homeCall: homeCall };
})();
