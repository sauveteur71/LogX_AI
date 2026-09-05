// EV-7 38e increment : ACTIVATION SOTA/XOTA (points de chasse, role, refresh,
// export POTA) -- extrait de logx_logbook.js (docs/LogX_AI_PRD.md). Charge en
// <script> classique dans logx_logbook.html, AVANT logx_logbook.js -- portee
// globale partagee (comme tous les fichiers EV-7).
//
// Contient : _sotaPointsVisible/sotaPointsHint/refreshSotaPoints (indice + totaux
// de points de chasse SOTA "indicatifs", purement locaux), majExportSotaVisible/
// telechargerExportSota (export SOTA par role), renderXotaRoleSwitch/basculerRoleXota
// (bascule chasseur/portable XOTA), refreshActivation (compteurs d'activation) et
// exportPotaAdif. AUCUNE n'est appelee au TOP-LEVEL de logbook.js : elles sont
// invoquees par des handlers inline (logbook.html) ou d'autres fonctions du coeur,
// a l'usage -- l'ordre relatif des <script> est donc indifferent.

// ─── Points de chasse SOTA « indicatifs » (NON officiels) ────────────────────
// Purement local, JAMAIS envoyé à SOTA (le score officiel ne vient que de
// sotadata après téléversement). Règles sourcées (3.8 §3 dédup jour UTC, 3.11
// barème) côté serveur dans logx_sota_points. Deux surfaces : un indice sous le
// champ réf. (points du sommet du QSO en cours) et un panneau de totaux courants.

function _sotaPointsVisible(){
  // Même règle que theirRefGroup : mode chasseur OU je suis moi-même en portable.
  return chaserModeActif() || !!(activationProgram && myActivationRef);
}

// Indice « ▸ +N pts » sous la réf. du correspondant, SOTA uniquement (les autres
// programmes n'ont pas de barème de points par altitude). textContent, jamais de
// balisage ; le « ▸ » est un caractère texte, pas une icône.
function sotaPointsHint(){
  var el = document.getElementById('theirRefPoints');
  if(!el || !window.LogxRefInfo) return;
  var prog = (document.getElementById('theirRefProg') || {}).value;
  prog = (prog || '').toUpperCase();
  var ref = (document.getElementById('inputTheirRef') || {}).value;
  ref = (ref || '').trim().toUpperCase();
  if(prog !== 'SOTA' || !ref || !_sotaPointsVisible()){ el.hidden = true; el.textContent = ''; return; }
  LogxRefInfo.lookup('SOTA', ref).then(function(e){
    var pts = e && e.points;
    if(!pts || pts <= 0){ el.hidden = true; el.textContent = ''; return; }
    var s2s = (activationProgram === 'SOTA' && myActivationRef);
    el.textContent = '▸ +' + pts + (s2s ? ' pts S2S' : ' pts chasse') + ' (indicatif — non officiel)';
    el.hidden = false;
  });
}

// Totaux courants (année + cumul) depuis /sota/points. Lecture seule. Toutes les
// valeurs interpolées sont coercées en nombre -> aucune injection possible.
async function refreshSotaPoints(){
  var el = document.getElementById('sotaPointsPanel');
  if(!el) return;
  if(!_sotaPointsVisible()){ el.hidden = true; return; }
  try{
    var r = await fetch('/sota/points'); if(!r.ok){ el.hidden = true; return; }
    var d = await r.json();
    var year = Number(d && d.year) || 0;
    var cy = Number(d && d.chasse_year) || 0;
    var s2sy = Number(d && d.s2s_year) || 0;
    var ca = Number(d && d.chasse_all) || 0;
    if(!ca && !cy){ el.hidden = true; return; }   // rien chassé : on n'encombre pas
    var htm = 'Chasse ' + year + ' : <b>' + cy + ' pts</b>';
    if(s2sy) htm += ' · dont S2S <b>' + s2sy + '</b>';
    if(ca !== cy) htm += ' · cumul <b>' + ca + '</b>';
    htm += ' <span class="indic">(indicatif — non officiel)</span>';
    el.innerHTML = htm;
    el.hidden = false;
  }catch(e){ el.hidden = true; }
}

// Boutons d'export « prêt pour sotadata » : visibles dès que la zone chasse
// l'est (mode chasseur ou portable). L'export lui-même gère le cas « rien à
// exporter » côté serveur.
function majExportSotaVisible(){
  var el = document.getElementById('sotaExportRow');
  if(el) el.hidden = !_sotaPointsVisible();
}

// Export ADIF filtré pour téléversement MANUEL sur sotadata (conforme, aucun
// appel API). fetch + blob : gère proprement le cas « aucun QSO » (une simple
// navigation vers l'endpoint afficherait le JSON d'erreur brut). role =
// 'chaser' (chasses) | 'activator' (portable).
async function telechargerExportSota(role){
  try{
    var r = await fetch('/sota/export_adif?role=' + encodeURIComponent(role));
    if(!r.ok){
      var msg = 'Export impossible';
      try{ var d = await r.json(); if(d && d.error) msg = d.error; }catch(e){}
      if(typeof notify === 'function') notify('⚠️ ' + msg);
      return;
    }
    var blob = await r.blob();
    var cd = r.headers.get('Content-Disposition') || '';
    var m = /filename="([^"]+)"/.exec(cd);
    var nom = m ? m[1] : ('sota_' + role + '.adi');
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = nom;
    document.body.appendChild(a); a.click();
    a.remove(); URL.revokeObjectURL(a.href);
  }catch(e){
    if(typeof notify === 'function') notify('⚠️ Export SOTA impossible (réseau).');
  }
}

// ─── Mode de session XOTA : bascule 1-geste (chasse / portable / les deux) ────
// Rendu des 3 boutons (rôle courant surligné). Contenu 100% généré ici (icône,
// libellé, hint contrôlés) -> pas d'injection.
function renderXotaRoleSwitch(){
  var el = document.getElementById('xotaRoleSwitch');
  if(!el || !window.LogxXotaRole) return;
  var actuel = LogxXotaRole.getRole();
  el.innerHTML = LogxXotaRole.ROLES.map(function(r){
    return '<button type="button" class="xrs-btn' + (r.id === actuel ? ' on' : '')
      + '" onclick="basculerRoleXota(\'' + r.id + '\')" title="' + r.hint + '">'
      + '<span class="xrs-ico">' + r.icone + '</span>'
      + '<span>' + r.label + '</span>'
      + '<span class="xrs-hint">' + r.hint + '</span></button>';
  }).join('');
  el.hidden = false;
}
// Changer de rôle en 1 geste : mémorise + ré-applique toute la visibilité
// (champ réf. correspondant, points/exports de chasse) sans recharger la page.
function basculerRoleXota(role){
  if(!window.LogxXotaRole) return;
  LogxXotaRole.setRole(role);
  renderXotaRoleSwitch();
  applyActivationMode(activationProgram, myActivationRef);   // relit chaserModeActif()
}

async function refreshActivation(){
  if(!activationProgram || !myActivationRef) return;
  try{
    const r = await fetch('/activation/state'); if(!r.ok) return;
    const d = await r.json();
    if(!d.active) return;
    lastActQsoTotal = d.qso_total || 0;
    // Le seuil se juge sur les QSO UNIQUES admissibles (call+bande+mode+jour),
    // pas sur le brut : un même correspondant recontacté même bande/mode/jour
    // ne compte qu'une fois. On affiche l'admissible en primaire, et le détail
    // brut + doublons quand il y en a (repli sur qso_total si serveur ancien).
    const eligible = (d.qso_eligible != null) ? d.qso_eligible : d.qso_total;
    const pr = document.getElementById('actProgress');
    if(pr){
      let txt = `${eligible}/${d.min_qso}`;
      if(d.doublons) txt += ` · ${d.qso_total} loggés, ${d.doublons} doublon${d.doublons > 1 ? 's' : ''}`;
      pr.textContent = txt;
    }
    const fill = document.getElementById('actFill');
    if(fill) fill.style.width = Math.min(100, Math.round(100*eligible/(d.min_qso||1))) + '%';
    const v = document.getElementById('actValid');
    if(v) v.innerHTML = d.valid
      ? '<span style="color:var(--green);font-weight:700">✅ VALIDÉE</span>'
      : `<span style="color:var(--yellow)">encore ${d.needed}</span>`;
    const p2p = document.getElementById('actP2P');
    if(p2p) p2p.textContent = d.p2p_count ? `${d.p2p_label} : ${d.p2p_count}` : '';
    const r2 = document.getElementById('actRef');
    if(r2) r2.style.color = d.valid_ref ? 'var(--text)' : 'var(--red)';
  }catch(e){}
}

// Export ADIF de l'activation POTA en cours, prêt à glisser-déposer sur la
// page « My Log Uploads » de pota.app. Pas d'upload automatique : POTA
// n'a pas d'API publique documentée pour ça (contrairement à LoTW/tqsl,
// cf. logx_awards.js) — ce bouton retire toute la friction qui PEUT
// l'être sans stocker d'identifiant de compte POTA : bon format ADIF, bon
// nom de fichier, et la page d'upload s'ouvre toute seule dans un nouvel
// onglet pour qu'il ne reste qu'à y glisser le fichier téléchargé.
function exportPotaAdif(){
  if(activationProgram !== 'POTA' || !myActivationRef) return;
  if(!lastActQsoTotal){
    notify('Aucun QSO enregistré pour ce parc : logue au moins un contact avant d’exporter.');
    return;
  }
  window.location.href = '/pota/export_adif';
  window.open('https://pota.app/#/user/logs', '_blank', 'noopener');
}
