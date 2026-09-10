// ─── PANNEAUX DE CHASSE — fonctions PURES de rendu de spot ──────────────────
//
// Extraites VERBATIM de logx_chasse.html (fusion D2, incr. 1) pour être
// réutilisées par le cockpit d'accueil sans dupliquer la logique. Aucune
// dépendance DOM. `rcT` : repli identité si l'i18n (window.rcT) n'est pas
// chargé — même repli que logx_chasse.html (l.369). CHASSE n'est pas modifiée
// à cet incrément ; ce module est purement additif.
(function(global){
  'use strict';

  // Traduction : dynamique (vérifie window.rcT à chaque appel), pour marcher
  // même si l'i18n est chargé après ce module.
  function rcT(s){ return (global && global.rcT) ? global.rcT(s) : s; }

  function esc(v){ return String(v==null?'':v).replace(/[&<>"']/g,
    c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

  // Indicatif/bande réduits aux caractères valides pour un argument de chaîne
  // JS imbriquée dans onclick="...'...'" (esc() protège l'attribut HTML, pas
  // cette chaîne-là — un guillemet simple survit au décodage d'entité et
  // rouvre la chaîne avant exécution). Extraites verbatim de logx_chasse.html.
  function jsCall(v){ return String(v==null?'':v).replace(/[^A-Za-z0-9/]/g,''); }
  function jsBand(v){ return String(v==null?'':v).replace(/[^A-Za-z0-9.]/g,''); }

  const PRIO_COLORS = {1:'var(--green)',2:'var(--red)',3:'var(--orange)',4:'var(--yellow)',5:'var(--muted)',6:'var(--border)'};

  function splitBadge(s){
    const sp = s.split;
    if(!sp || !sp.split) return '';
    if(sp.qsx_khz != null){
      return `<span class="sr-split-badge" title="${rcT('Écoute (QSX) annoncée dans le commentaire du spot')}">QSX ${esc(sp.qsx_khz.toFixed(1).replace('.', ','))}</span>`;
    }
    if(sp.direction){
      const arrow = sp.direction === 'up' ? '↑' : '↓';
      const label = sp.direction === 'up' ? 'UP' : 'DOWN';
      const off = sp.offset_khz != null ? ' ' + esc(sp.offset_khz) : '';
      return `<span class="sr-split-badge" title="${rcT('Split annoncé dans le commentaire du spot')}">${arrow} ${label}${off}</span>`;
    }
    return `<span class="sr-split-badge" title="${rcT('Split annoncé dans le commentaire du spot')}">SPLIT</span>`;
  }

  // Crédit CHASSE : ce que le spot apporte de NOUVEAU (posé côté serveur par
  // logx_awards.annoter_credit — atno/new_band/new_mode/needed_confirm). Le
  // « pourquoi » (credit_raison) + le score partent en title ; le doublon
  // confirmé et l'entité inconnue n'affichent rien (aucun crédit à signaler).
  const CREDIT_LABELS = {
    atno: '🌟 ATNO', new_band: '📻 +BANDE', new_mode: '🎚 +MODE',
    new_grid: '🗺 +CARRÉ', needed_confirm: '📩 À CONFIRMER',
  };
  function creditBadge(s){
    const cl = s.credit_classe;
    const lbl = CREDIT_LABELS[cl];
    if(!lbl) return '';
    // Objectif décoché -> le serveur neutralise le crédit (score 0). On garde le
    // badge VISIBLE mais ATTÉNUÉ (classe cr-off) : le fait reste montré (« c'est
    // un ATNO ») sans être mis en avant, puisque l'opérateur ne le chasse pas.
    // Choix F4GLD (26/08) : atténuer, pas masquer.
    const off = !(s.credit_score > 0);
    const t = (s.credit_raison || '') + (s.credit_score ? ' (+' + s.credit_score + ')' : '')
            + (off ? ' — objectif désactivé' : '');
    return `<span class="sr-credit-badge cr-${esc(cl)}${off ? ' cr-off' : ''}" title="${esc(t)}">${rcT(lbl)}</span>`;
  }

  // Rendu de la need-list pour le cockpit d'accueil ET la vue activité complète
  // (fusion incr. 3, étendue incr. 4d). QSY/rotor SONT rendus quand
  // opts.rigEnabled/opts.rotorEnabled valent vrai (état lu côté appelant sur
  // /rig/state et /rotor/state, comme logx_chasse.html) — par défaut (opts
  // absent ou faux), lecture seule, comportement du cockpit inchangé. Mêmes
  // conditions par ligne que CHASSE : QSY si s.freq connu, rotor si
  // s.bearing != null (calculé côté serveur sur /data/spots_ranked, même
  // source que CHASSE). Réutilise creditBadge/splitBadge/PRIO_COLORS.
  // `opts.max` borne la liste.
  function renderNeedList(spots, opts){
    spots = spots || []; opts = opts || {};
    const max = opts.max || 12;
    const rig = !!opts.rigEnabled, rotor = !!opts.rotorEnabled;
    if(!spots.length) return '<div class="ck-need-empty">' + rcT('Aucune cible en direct.') + '</div>';
    return spots.slice(0, max).map(function(s){
      const qsyBtn = (rig && s.freq)
        ? '<button class="qsy-btn" onclick="qsyTo(' + (Number(s.freq)||0) + ',\'' + jsCall(s.call) + '\')" title="' + rcT('Régler la radio sur') + ' ' + esc(s.freq) + ' kHz">▶ QSY</button>' : '';
      const pointBtn = (rotor && s.bearing != null)
        ? '<button class="point-btn" onclick="pointTo(' + (Number(s.bearing)||0) + ',\'' + jsCall(s.call) + '\',\'' + jsBand(s.band) + '\')" title="' + rcT("Pointer l'antenne sur") + ' ' + Math.round(s.bearing) + '°">🧭 ' + Math.round(s.bearing) + '°</button>' : '';
      return '<div class="ck-need-row' + (s.already_done ? ' ck-need-done' : '') + '">'
        + '<span class="ck-need-prio" style="background:' + (PRIO_COLORS[s.priority] || 'var(--muted)') + '"></span>'
        + '<span class="ck-need-call">' + esc(s.call) + '</span>'
        + '<span class="ck-need-band">' + esc(s.band) + '</span>'
        + '<span class="ck-need-freq">' + esc(s.freq || '') + '</span>'
        + creditBadge(s) + splitBadge(s) + qsyBtn + pointBtn
        + '</div>';
    }).join('');
  }

  // Rendu des lignes d'un panneau d'activation « en direct » (POTA/SOTA/WWFF/WCA,
  // fusion incr. 4b) : format sr-act commun ; la ligne « lieu » est fournie par
  // opts.place(s) (park_name / summit_name+alt+pts / …). Champs issus de services
  // tiers publics -> tout passe par esc(). freq en kHz -> MHz (3 décimales).
  function renderActivationRows(spots, opts){
    spots = spots || []; opts = opts || {};
    const max = opts.max || 30;
    const place = opts.place || function(s){ return '<span class="sr-ref">' + esc(s.reference || '') + '</span>'; };
    return spots.slice(0, max).map(function(s){
      return '<div class="spot-row sr-act">'
        + '<div class="sr-head">'
          + '<span class="sr-call">' + esc(s.call) + '</span>'
          + '<span class="sr-band">' + (esc(s.band) || '—') + '</span>'
          + (s.freq ? '<span class="sr-qrg">' + (s.freq/1000).toFixed(3) + ' MHz</span>' : '')
          + (s.mode ? '<span class="sr-mode">' + esc(s.mode) + '</span>' : '')
        + '</div>'
        + '<div class="sr-place">' + place(s) + '</div>'
        + (s.comment ? '<div class="sr-note" title="' + esc(s.comment) + '">' + esc(s.comment) + '</div>' : '')
        + '</div>';
    }).join('');
  }

  // Rendu des annonces WCA/COTA (fusion incr. 4c) — PAS des spots confirmés sur
  // l'air (contrairement à renderActivationRows), contenu 100% textuel écrit par
  // des correspondants humains -> tout passe par esc(). `it.description` tronquée
  // à 160 car., même borne que logx_chasse.html.
  function renderWcaRows(items, opts){
    items = items || []; opts = opts || {};
    const max = opts.max || 20;
    if(!items.length) return '<div class="ck-need-empty">' + rcT("Aucune activation WCA/COTA annoncée.") + '</div>';
    return items.slice(0, max).map(function(it){
      return '<div class="spot-row sr-wca">'
        + '<div class="sr-head"><span class="sr-ref">' + esc(it.reference) + '</span>'
          + '<span class="sr-place">' + esc(it.title) + '</span></div>'
        + (it.description ? '<div class="sr-note" title="' + esc(it.description) + '">' + esc(String(it.description).slice(0, 160)) + '</div>' : '')
        + '</div>';
    }).join('');
  }

  // Rendu des expéditions DX (fusion incr. 4c) — statut actif/à venir déduit
  // côté serveur (logx_dxpeditions), badge nouveau-pays/nouvelle-bande déjà
  // calculé. Version lecture seule (pas de bouton VOACAP interactif, réservé à
  // la vue activité complète — même choix que renderNeedList pour QSY/rotor).
  function renderDxRows(list, opts){
    list = list || []; opts = opts || {};
    const max = opts.max || 40;
    if(!list.length) return '<div class="ck-need-empty">' + rcT('Aucune expédition annoncée.') + '</div>';
    return list.slice(0, max).map(function(e){
      const actif = e.status === 'active';
      const statut = actif
        ? '<span class="sr-mode" style="color:var(--green)">● ACTIVE</span>'
        : '<span class="sr-mode" style="color:var(--yellow)">' + rcT('À VENIR') + '</span>';
      const freq = e.freq_khz ? '<span class="sr-qrg">' + (e.freq_khz/1000).toFixed(3) + ' MHz</span>' : '';
      const mode = e.spot_mode ? '<span class="sr-mode">' + esc(e.spot_mode) + '</span>' : '';
      const nouveau = e.worked_status === 'new'
        ? '<span class="sr-mode" style="color:var(--green)">🆕 ' + rcT('nouveau pays') + '</span>'
        : e.worked_status === 'partial'
        ? '<span class="sr-mode" style="color:var(--yellow)">◐ ' + rcT('nouvelle bande') + '</span>' : '';
      return '<div class="spot-row sr-act">'
        + '<div class="sr-head">'
          + '<span class="sr-call">' + esc(e.callsign || '?') + '</span>'
          + statut + freq + mode + nouveau
        + '</div>'
        + '<div class="sr-place">' + esc(e.entity || '?') + ' · ' + esc(e.dates || '—') + '</div>'
        + (e.qsl ? '<div class="sr-note">QSL : ' + esc(e.qsl) + '</div>' : '')
        + '</div>';
    }).join('');
  }

  global.LogxChassePanneaux = {
    esc: esc, jsCall: jsCall, jsBand: jsBand, splitBadge: splitBadge, creditBadge: creditBadge,
    renderNeedList: renderNeedList, renderActivationRows: renderActivationRows,
    renderWcaRows: renderWcaRows, renderDxRows: renderDxRows,
    CREDIT_LABELS: CREDIT_LABELS, PRIO_COLORS: PRIO_COLORS,
  };
})(typeof window !== 'undefined' ? window : this);
