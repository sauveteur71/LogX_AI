// ─── PANNEAU DIPLÔMES & QSL (EV-7, docs/LogX_AI_PRD.md) ──────────────────────
// 4e incrément du refactor EV-7 : extrait tel quel de logx_logbook.js (aucune
// restructuration nécessaire). Carnet permanent tous concours (DXCC/départe-
// ments/continents), diplômes classiques (WAZ/WAC/WAS/DXCC Challenge/VUCC/CQ
// DX Field), worked matrix bande×mode, records DX, activité 21 jours, et
// actions QSL (upload eQSL/ClubLog/QRZCQ/HRDLog, sync LoTW).
//
// SENSIBLE — showAwards() affiche l'état du disjoncteur ClubLog Live Stream
// (q.clublog_realtime_blocked, posé par GET /qsl/status côté
// concours/logx_qsl.py) : sans cet avertissement, un opérateur dont le flux
// est suspendu (refus HTTP 403) ne le sait pas et ses QSO suivants ne
// partent plus vers ClubLog en silence. Couvert par
// tests/test_awards_clublog_realtime_blocked_js.py (y compris un contrôle
// négatif rejouant le commit 1720e6b, avant ce fix) — ce fichier doit
// désormais être chargé EN PLUS de logx_logbook.js pour le scénario HEAD.
//
// Dépend de globals restés dans logx_logbook.js (portée globale partagée via
// <script> classique, voir logx_logbook.html) : escHtml, notify, trF, trT.
// fmtDate est extraite depuis le 16e incrément EV-7 (docs/LogX_AI_PRD.md)
// vers logx_callbook.js -- même portée globale partagée, ordre de <script>
// entre les deux fichiers extraits sans importance (fmtDate n'est jamais
// appelée qu'à l'intérieur de corps de fonction ici).
//
// qslLastSync()/qslAction() (8e incrément EV-7) ont rejoint ce fichier : elles
// n'avaient qu'un seul consommateur, showAwards() ci-dessous — dépendance déjà
// documentée dans une version antérieure de cet en-tête, refermée maintenant
// que les deux vivent au même endroit.
// ─── WORKED MATRIX (grille bande × CW/Phone/Digital) ─────────────────────────
function renderWorkedMatrix(m){
  if(!m || !m.bands || !m.bands.length){
    return `<div style="font-size:12px;color:var(--muted);font-family:var(--font-mono)">Pas encore de QSO.</div>`;
  }
  const catIcon = {CW:'📟', PHONE:'🎙️', DIGITAL:'💻'};
  // Chaque case porte DEUX chiffres, et ils ne disent pas la même chose : le
  // nombre de QSO dit l'ACTIVITÉ, le nombre d'entités DXCC dit l'AVANCEMENT du
  // Challenge. Une case à 3621 QSO et 135 entités est une case d'habitué ; une
  // case à 12 QSO et 12 entités est une case de chasseur. C'est le second
  // chiffre qui indique où il reste à faire.
  //
  // L'entité confirmée LoTW est distinguée du reste : pour l'ARRL, une
  // confirmation eQSL ou papier ne compte pas (même règle que les alertes).
  const cell = (c) => {
    if(!c || !c.qso) return `<td style="text-align:center;padding:4px 8px;color:var(--muted)">—</td>`;
    const dxcc = c.dxcc ? `<div style="font-size:11px;color:var(--accent2)">${c.dxcc} DXCC` +
      (c.dxcc_lotw ? ` · <span style="color:var(--green)">${c.dxcc_lotw} LoTW</span>` : '') + `</div>` : '';
    return `<td style="text-align:center;padding:4px 8px;background:rgba(0,212,255,.08)">` +
           `<b>${c.qso}</b>${dxcc}</td>`;
  };
  const rows = m.bands.map(b => {
    const g = m.grid[b] || {};
    return `<tr><td style="padding:4px 8px;color:var(--muted)">${escHtml(b)} MHz</td>` +
      m.categories.map(c => cell(g[c])).join('') + `</tr>`;
  }).join('');
  const totalsRow = `<tr style="border-top:1px solid var(--border)"><td style="padding:4px 8px;color:var(--muted)">Total</td>` +
    m.categories.map(c => `<td style="text-align:center;padding:4px 8px"><b>${(m.totals&&m.totals[c])||0}</b></td>`).join('') + `</tr>`;
  return `<table style="width:100%;border-collapse:collapse;font-family:var(--font-mono);font-size:12px">
    <thead><tr><td></td>${m.categories.map(c=>`<td style="text-align:center;padding:4px 8px;color:var(--accent2)">${catIcon[c]||''} ${c}</td>`).join('')}</tr></thead>
    <tbody>${rows}${totalsRow}</tbody>
  </table>
  <div style="font-size:11px;color:var(--muted);margin-top:4px">QSO travaillés · entités DXCC · confirmées LoTW en vert${
    m.challenge ? ` — <b style="color:var(--text)">${m.challenge}</b> cases DXCC Challenge (160 m → 6 m)` +
                  (m.challenge_lotw ? `, <span style="color:var(--green)">${m.challenge_lotw} confirmées LoTW</span>` : '') : ''}</div>`;
}

// ─── RECORDS DX (déjà calculés côté serveur — logx_awards.dx_records) ───────
function renderDxRecords(dxr){
  if(!dxr || !dxr.overall){
    return `<div style="font-size:12px;color:var(--muted);font-family:var(--font-mono)">Aucun record calculable pour l'instant (locator QTH à renseigner dans CONFIG, ou aucun QSO avec locator connu).</div>`;
  }
  const rows = Object.entries(dxr.by_band || {}).map(([b, r]) => `
    <tr><td style="padding:4px 8px;color:var(--muted)">${escHtml(b)} MHz</td>
      <td style="padding:4px 8px"><b>${Math.round(r.dist_km)} km</b></td>
      <td style="padding:4px 8px">${escHtml(r.call)}</td>
      <td style="padding:4px 8px;color:var(--muted)">${escHtml(r.locator)} · ${fmtDate(r.date)}</td>
    </tr>`).join('');
  const o = dxr.overall;
  return `<div style="font-size:12px;color:var(--muted);font-family:var(--font-mono);margin-bottom:8px">
      🏆 Record absolu : <b style="color:var(--text)">${Math.round(o.dist_km)} km</b> avec ${escHtml(o.call)} sur ${escHtml(o.band)} MHz (${fmtDate(o.date)})</div>
    <table style="width:100%;border-collapse:collapse;font-family:var(--font-mono);font-size:12px">
      <thead><tr style="color:var(--accent2)"><td style="padding:4px 8px">BANDE</td><td style="padding:4px 8px">DISTANCE</td><td style="padding:4px 8px">INDICATIF</td><td style="padding:4px 8px">LOCATOR / DATE</td></tr></thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ─── ACTIVITÉ RÉCENTE (petit sparkline, données de logx_awards.activity_by_day)
function renderActivityChart(days){
  if(!days || !days.length){
    return `<div style="font-size:12px;color:var(--muted);font-family:var(--font-mono)">Pas encore de QSO.</div>`;
  }
  const max = Math.max(1, ...days.map(d => d.qso));
  const bars = days.map(d => {
    const h = d.qso ? Math.max(2, Math.round((d.qso / max) * 40)) : 1;
    return `<div style="flex:1;display:flex;align-items:flex-end;justify-content:center">
      <div style="width:100%;max-width:14px;height:${h}px;background:${d.qso ? 'var(--accent2)' : 'var(--border)'};border-radius:2px" title="${fmtDate(d.date)} : ${d.qso} QSO"></div>
    </div>`;
  }).join('');
  return `<div style="display:flex;align-items:flex-end;gap:2px;height:44px">${bars}</div>
    <div style="font-size:10px;color:var(--muted);display:flex;justify-content:space-between;margin-top:2px">
      <span>${fmtDate(days[0].date)}</span><span>${fmtDate(days[days.length - 1].date)}</span>
    </div>`;
}

// ─── DIPLÔMES & QSL (carnet permanent, tous concours) ────────────────────────
async function showAwards(){
  const ov = document.getElementById('awardsOverlay');
  const inner = document.getElementById('awardsInner');
  if(!ov || !inner) return;
  ov.classList.add('show');
  inner.innerHTML = '<div class="shortcuts-row"><span>⏳ Calcul des diplômes…</span></div>';
  let a, q, m, dxr, act;
  try{
    [a, q, m, dxr, act] = await Promise.all([
      fetch('/awards/summary').then(r=>r.json()),
      fetch('/qsl/status').then(r=>r.json()),
      fetch('/awards/matrix').then(r=>r.json()),
      fetch('/data/dx_records').then(r=>r.json()),
      fetch('/awards/activity?days=21').then(r=>r.json()),
    ]);
  }catch(e){
    inner.innerHTML = `<div class="shortcuts-row"><span style="color:var(--red)">❌ Serveur injoignable</span></div>`;
    return;
  }
  const dep = a.departments || {};
  const bar = (w,t) => {
    const pct = t ? Math.round(100*w/t) : 0;
    return `<div style="background:var(--bg3);border-radius:5px;height:10px;overflow:hidden;border:1px solid var(--border)">`+
           `<div style="height:100%;width:${pct}%;background:linear-gradient(90deg,var(--green),var(--accent2))"></div></div>`;
  };
  const row = (label, val) => `<div style="display:flex;justify-content:space-between;padding:4px 0"><span>${label}</span><b>${val}</b></div>`;
  const confNote = a.has_confirmations ? '' :
    `<div style="color:var(--muted);font-size:12px;margin:4px 0 10px">Aucune confirmation importée — synchronise LoTW ci-dessous pour voir le « confirmé ».</div>`;
  const perBand = Object.entries(a.per_band||{}).map(([b,v]) =>
    `<span style="display:inline-block;margin:2px 6px 2px 0;color:var(--muted)">${b} MHz : <b style="color:var(--text)">${v.qso}</b> QSO / ${v.dxcc} DXCC</span>`).join('');
  // ── Diplômes classiques ────────────────────────────────────────────────
  // Tous calculés RÉTROACTIVEMENT sur le carnet existant, sauf le WAS :
  // l'entité, la zone et le continent se déduisent de l'indicatif, le champ et
  // le carré du locator déjà enregistré. L'état US, lui, ne se déduit de rien.
  const dip = (label, d, unite) => {
    if(!d) return '';
    const tot = d.total ? `/${d.total}` : '';
    const conf = `<span style="color:var(--green)">${d.confirmed} conf.</span>`;
    return row(label, `${d.worked}${tot} ${unite||''} · ${conf}`) +
           (d.total ? bar(d.worked, d.total) : '');
  };
  const manquants = (d, titre) => (d && d.missing && d.missing.length)
    ? `<div style="margin-top:4px;font-size:12px;color:var(--muted)">${titre} : ${d.missing.join(' ')}</div>` : '';
  // Le WAS s'affiche différemment tant qu'aucun état n'est connu : « 0/50 »
  // laisserait croire à un carnet vide alors que c'est la DONNÉE qui manque.
  const wasHtml = a.was_data
    ? dip('🇺🇸 WAS (états US)', a.was) + manquants(a.was, 'États manquants')
    : row('🇺🇸 WAS (états US)', `<span style="color:var(--muted)">état non renseigné</span>`) +
      `<div style="margin-top:2px;font-size:12px;color:var(--muted)">L'état ne se déduit pas de l'indicatif. Il se remplit à la saisie (annuaire) et par un import ADIF LoTW/ClubLog.</div>`;
  const vuccBandes = (a.vucc && a.vucc.per_band)
    ? Object.entries(a.vucc.per_band).map(([b,n]) =>
        `<span style="display:inline-block;margin:2px 6px 2px 0;color:var(--muted)">${b} MHz : <b style="color:var(--text)">${n}</b></span>`).join('')
    : '';
  const diplomesHtml = `
    <div style="border-top:1px solid var(--border);margin-top:14px;padding-top:12px">
      <div style="color:var(--accent2);letter-spacing:1px;margin-bottom:8px;font-family:var(--font-mono);font-size:13px">🏅 DIPLÔMES</div>
      <div style="font-family:var(--font-mono);font-size:13px;line-height:1.6">
        ${dip('🌐 WAZ (zones CQ)', a.waz)}
        ${manquants(a.waz, 'Zones manquantes')}
        ${dip('📡 Zones ITU (RSGB)', a.waz_itu)}
        ${manquants(a.waz_itu, 'Zones manquantes')}
        ${dip('🗺️ WAC (continents)', a.wac)}
        ${wasHtml}
        ${dip('📻 DXCC Challenge', a.dxcc_challenge, 'cases entité×bande')}
        ${dip('🔲 VUCC (carrés QRA)', a.vucc, 'carrés')}
        ${vuccBandes ? `<div style="margin-top:2px;font-size:12px">${vuccBandes}</div>` : ''}
        ${dip('🧭 CQ DX Field (champs QRA)', a.dx_field, 'champs')}
      </div>
    </div>`;
  const matrixHtml = renderWorkedMatrix(m);
  const dxRecordsHtml = renderDxRecords(dxr);
  const activityHtml = renderActivityChart((act && act.days) || []);

  inner.innerHTML = `
    <div style="font-family:var(--font-mono);font-size:13px;line-height:1.6">
      <div style="color:var(--accent2);letter-spacing:1px;margin:6px 0">📊 CARNET PERMANENT — ${a.qso_total} QSO à vie</div>
      ${confNote}
      ${a.dxcc.total
        ? row('🌍 DXCC (pays)', `${a.dxcc.worked}/${a.dxcc.total} · <span style="color:var(--green)">${a.dxcc.confirmed} confirmés</span>`) + bar(a.dxcc.worked, a.dxcc.total)
        : row('🌍 DXCC (pays)', `${a.dxcc.worked} travaillés · <span style="color:var(--green)">${a.dxcc.confirmed} confirmés</span>`)}
      ${a.dxcc.missing && a.dxcc.missing.length ? `<div style="margin-top:4px;font-size:12px;color:var(--muted)">Entités DXCC manquantes : ${a.dxcc.missing.join(', ')}${a.dxcc.missing.length>=40?'…':''}</div>` : ''}
      ${row('🇫🇷 Départements métropole', `${dep.metro_worked}/${dep.metro_total} · <span style="color:var(--green)">${dep.metro_confirmed||0} conf.</span>`)}
      ${bar(dep.metro_worked, dep.metro_total)}
      ${dep.dom_worked ? row('🏝️ Outre-mer', dep.dom_worked) : ''}
      ${row('🗺️ Continents', (a.continents||[]).join(' '))}
      <div style="margin-top:8px;font-size:12px">${perBand}</div>
      ${dep.missing && dep.missing.length ? `<div style="margin-top:8px;font-size:12px;color:var(--muted)">Départements manquants : ${dep.missing.join(', ')}${dep.missing.length>=40?'…':''}</div>` : ''}
    </div>
    ${diplomesHtml}
    <div style="border-top:1px solid var(--border);margin-top:14px;padding-top:12px">
      <div style="color:var(--accent2);letter-spacing:1px;margin-bottom:8px;font-family:var(--font-mono);font-size:13px">🧮 WORKED MATRIX — bande × mode</div>
      ${matrixHtml}
    </div>
    <div style="border-top:1px solid var(--border);margin-top:14px;padding-top:12px">
      <div style="color:var(--accent2);letter-spacing:1px;margin-bottom:8px;font-family:var(--font-mono);font-size:13px">🏆 RECORDS DX — plus grande distance par bande</div>
      ${dxRecordsHtml}
    </div>
    <div style="border-top:1px solid var(--border);margin-top:14px;padding-top:12px">
      <div style="color:var(--accent2);letter-spacing:1px;margin-bottom:8px;font-family:var(--font-mono);font-size:13px">📅 ACTIVITÉ — 21 derniers jours</div>
      ${activityHtml}
    </div>
    <div style="border-top:1px solid var(--border);margin-top:14px;padding-top:12px;font-family:var(--font-mono);font-size:13px">
      <div style="color:var(--accent2);letter-spacing:1px;margin-bottom:8px">📮 QSL — ${a.confirmed_total||0} QSO confirmés (${q.confirmations||0} croisés)</div>
      ${q.clublog_realtime_blocked ? `<div style="color:var(--red);background:rgba(255,68,68,.12);border:1px solid rgba(255,68,68,.4);border-radius:6px;padding:8px 10px;margin-bottom:10px">⚠️ ClubLog Live Stream suspendu (refus HTTP 403) — plus aucun QSO n'est poussé en temps réel. Corrige les identifiants ClubLog dans CONFIG pour réactiver l'envoi.</div>` : ''}
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="export-btn" onclick="qslAction('upload','eqsl',this)" ${q.eqsl?'':'disabled title="Configure eQSL dans CONFIG"'} style="color:var(--accent2);border-color:rgba(var(--accent-rgb),.4)">⬆ eQSL</button>
        <button class="export-btn" onclick="qslAction('upload','clublog',this)" ${q.clublog?'':'disabled title="Configure ClubLog dans CONFIG"'} style="color:var(--accent2);border-color:rgba(var(--accent-rgb),.4)">⬆ ClubLog</button>
        <button class="export-btn" onclick="qslAction('upload','qrzcq',this)" ${q.qrzcq?'':'disabled title="Configure QRZCQ dans CONFIG"'} style="color:var(--accent2);border-color:rgba(var(--accent-rgb),.4)">⬆ QRZCQ</button>
        <button class="export-btn" onclick="qslAction('upload','hrdlog',this)" ${q.hrdlog?'':'disabled title="Configure HRDLog dans CONFIG"'} style="color:var(--accent2);border-color:rgba(var(--accent-rgb),.4)">⬆ HRDLog</button>
        <button class="export-btn" onclick="qslAction('sync','lotw',this)" ${q.lotw?'':'disabled title="Configure LoTW dans CONFIG"'} style="color:var(--green);border-color:rgba(0,255,136,.4)">⬇ Confirmations LoTW</button>
      </div>
      <div id="qslResult" style="margin-top:10px;color:var(--muted);font-size:12px">${qslLastSync(q)}</div>
      <div style="margin-top:8px;font-size:11px;color:var(--muted)">Identifiants des services : CONFIG → étape PROPAGATION → « QSL & DIPLÔMES ». Stockés côté serveur.</div>
    </div>`;
}

function qslLastSync(q){
  const l = q.last || {};
  const bits = [];
  if(l.eqsl_upload) bits.push('eQSL envoyé le ' + l.eqsl_upload);
  if(l.clublog_upload) bits.push('ClubLog envoyé le ' + l.clublog_upload);
  if(l.qrzcq_upload) bits.push('QRZCQ envoyé le ' + l.qrzcq_upload);
  if(l.hrdlog_upload) bits.push('HRDLog envoyé le ' + l.hrdlog_upload);
  if(l.lotw) bits.push('LoTW synchro le ' + l.lotw);
  return bits.length ? bits.join(' · ') : 'aucune synchro encore';
}

async function qslAction(kind, service, btn){
  const out = document.getElementById('qslResult');
  const old = btn.textContent;
  btn.disabled = true; btn.textContent = '⏳…';
  if(out) out.textContent = trF(kind==='upload' ? 'Envoi vers {service} en cours…' : 'Synchro {service} en cours…', {service});
  try{
    const url = kind === 'upload' ? '/qsl/upload' : '/qsl/sync';
    const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({service})});
    const d = await r.json();
    if(d.ok){
      if(kind==='upload' && service==='hrdlog') out.innerHTML =
        `<span style="color:var(--green)">${trF('✅ {sent}/{total} QSO envoyés à HRDLog{failed}.',
          {sent: d.sent, total: d.qso_count, failed: d.failed ? trF(' ({n} échoués)', {n: d.failed}) : ''})}</span>`;
      else if(kind==='upload') out.innerHTML = `<span style="color:var(--green)">${trF('✅ {n} QSO envoyés à {service}.', {n: d.qso_count, service: d.service})}</span>`;
      else out.innerHTML = `<span style="color:var(--green)">${trF('✅ {n} nouvelles confirmations ({total} au total).', {n: d.newly_added, total: d.total_confirmations})}</span>`;
      notify(trF('✅ QSL {action}', {action: kind==='upload' ? trT('envoyé') : trT('synchronisé')}));
      if(kind==='sync') setTimeout(()=>{ const ov = document.getElementById('awardsOverlay'); if(ov && ov.classList.contains('show')) showAwards(); }, 800);   // rafraîchit les « confirmés »
    }else{
      out.innerHTML = `<span style="color:var(--red)">${trF('❌ {err}', {err: escHtml(d.error || trT('échec'))})}</span>`;
    }
  }catch(e){
    out.innerHTML = `<span style="color:var(--red)">${trF('❌ {err}', {err: e.message})}</span>`;
  }finally{
    btn.disabled = false; btn.textContent = old;
  }
}
