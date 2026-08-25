// EV-7 phase 2, 33e increment : FILTRE D'AFFICHAGE DES SPOTS +
// refreshBandMap() -- extrait de logx_logbook.js (docs/LogX_AI_PRD.md).
// Charge en <script> classique dans logx_logbook.html, AVANT
// logx_logbook.js -- portee globale partagee (comme tous les fichiers
// EV-7).
//
// Contient : _SF_CONTINENTS, _spotFiltre/_spotFiltreEnVol/
// _spotFiltreOuvert, toggleSpotFiltre(), dessinerChipsFiltre(),
// basculerContinent(), majSpotFiltre(), appliquerRetourFiltre(),
// refreshBandMap().
//
// Dependances croisees verifiees sures :
// - refreshBandMap() (ici) lit _BM_RANGE/_BM_PCOL/escHtml (coeur),
//   ecrit _bmSpots (logx_bandmap_sp.js, deja extrait), appelle
//   drawBandscope()/drawWaterfallRow() (logx_bandscope_waterfall.js,
//   deja extrait) -- toujours en corps de fonction, jamais au
//   chargement du script, donc deja disponibles au moment ou
//   refreshBandMap() est reellement appelee (toujours apres la fin du
//   chargement de TOUS les <script>).
// - pickBand()/onFreqInput() (coeur) appellent refreshBandMap() sous
//   une garde 'typeof refreshBandMap==="function"' deja existante --
//   sans risque d'ordre.
// - logx_bandmap_sp.js (deja extrait, charge AVANT ce fichier) appelle
//   refreshBandMap() en corps de bandmapNoter() -- sans risque
//   d'ordre malgre le fait que ce fichier charge apres lui (motif
//   deja rencontre pour les MACROS F1-F8, 32e increment).
// - Le coeur contient un appel TOP-LEVEL non garde
//   'setInterval(refreshBandMap,15000); setTimeout(refreshBandMap,2500);'
//   (juste apres bandmapClick(), resté dans le coeur) -- sans risque
//   puisque ce fichier charge TOUJOURS avant logx_logbook.js.
// - bandmapClick() (coeur, resté en place) a 3 sites de reference,
//   aucun au chargement du script -- sans risque d'ordre : la chaine
//   onclick generee ICI par refreshBandMap() (attribut HTML), une
//   deuxieme chaine onclick generee par drawBandscope() dans
//   logx_bandscope_waterfall.js, et un appel DIRECT en JS (pas via
//   onclick) depuis bandmapSaut() dans logx_bandmap_sp.js.

// ─── FILTRE D'AFFICHAGE DES SPOTS ────────────────────────────────────────────
// Le filtrage lui-même est fait CÔTÉ SERVEUR (logx_spotfilter.py), avant que
// /data/spots_ranked ne coupe la liste à 40 : filtrer ici, après la coupe,
// n'écarterait que ce qui a déjà survécu — c'est-à-dire trop tard. Ici on ne
// fait que présenter les réglages et afficher ce qui a été masqué.
const _SF_CONTINENTS = ['EU','NA','SA','AS','AF','OC','AN'];
let _spotFiltre = {spotter_continents:[], dx_continents:[], masquer_deja_faits:false,
                   seulement_lotw:false, seulement_besoins:false};
// Nombre d'enregistrements en vol. Tant qu'il n'est pas nul, on ne resynchro-
// nise PAS l'écran depuis le serveur : sinon un clic pourrait être visuellement
// annulé le temps d'un tick, juste avant que le POST n'arrive.
let _spotFiltreEnVol = 0;
let _spotFiltreOuvert = false;

function toggleSpotFiltre(){
  const box = document.getElementById('bmFiltre');
  if(!box) return;
  _spotFiltreOuvert = !box.classList.contains('on');
  box.classList.toggle('on', _spotFiltreOuvert);
  if(_spotFiltreOuvert) dessinerChipsFiltre();
}

function dessinerChipsFiltre(){
  for(const [id, cle] of [['bmChipsSpotter','spotter_continents'], ['bmChipsDx','dx_continents']]){
    const box = document.getElementById(id);
    if(!box) continue;
    const sel = _spotFiltre[cle] || [];
    // Liste vide = joker « tous », même convention que côté serveur : on
    // allume alors TOUTES les pastilles, parce que « aucun coché » et « tous
    // cochés » produisent le même résultat et que montrer sept pastilles
    // éteintes ferait croire que plus rien ne passe.
    const tous = sel.length === 0;
    box.innerHTML = _SF_CONTINENTS.map(c =>
      `<button type="button" class="bm-chip${tous || sel.includes(c) ? ' on' : ''}"`
      + ` onclick="basculerContinent('${cle}','${c}')">${c}</button>`).join('');
  }
  const m = {bmFiltreDejaFaits:'masquer_deja_faits', bmFiltreLotw:'seulement_lotw',
             bmFiltreBesoins:'seulement_besoins'};
  for(const id in m){
    const el = document.getElementById(id);
    if(el) el.checked = !!_spotFiltre[m[id]];
  }
}

function basculerContinent(cle, c){
  let sel = (_spotFiltre[cle] || []).slice();
  // Partant de « tous » (liste vide), le premier clic doit vouloir dire
  // « celui-ci seulement » et non « tous sauf celui-ci » : on part donc de la
  // sélection pleine avant de retirer, sinon le clic donnerait l'inverse de
  // ce que l'opérateur vient de demander.
  if(sel.length === 0) sel = _SF_CONTINENTS.slice();
  sel = sel.includes(c) ? sel.filter(x => x !== c) : sel.concat([c]);
  // Deux cas retombent volontairement sur le joker « tous » : les sept cochés,
  // et plus aucun. Décocher le dernier continent ne vide donc pas l'écran — il
  // rallume les sept pastilles, ce qui dit tout seul où on en est.
  _spotFiltre[cle] = (sel.length === _SF_CONTINENTS.length || !sel.length) ? [] : sel;
  dessinerChipsFiltre();
  majSpotFiltre(true);
}

async function majSpotFiltre(depuisChip){
  if(!depuisChip){
    const m = {bmFiltreDejaFaits:'masquer_deja_faits', bmFiltreLotw:'seulement_lotw',
               bmFiltreBesoins:'seulement_besoins'};
    for(const id in m){
      const el = document.getElementById(id);
      if(el) _spotFiltre[m[id]] = !!el.checked;
    }
  }
  _spotFiltreEnVol++;
  try{
    await fetch('/spots/filter', {method:'POST', headers:{'Content-Type':'application/json'},
                                  body: JSON.stringify(_spotFiltre)});
  }catch(e){ /* réglage non persisté : le serveur continue avec l'ancien */ }
  finally{ _spotFiltreEnVol--; }
  refreshBandMap();
}

// Affiche ce que le filtre a retiré, et repeint les pastilles si le réglage a
// changé ailleurs (autre poste, autre fenêtre).
function appliquerRetourFiltre(f){
  const ligne = document.getElementById('bmMasques');
  const btn = document.getElementById('spotFiltreBtn');
  f = f || {};
  if(f.reglages && !_spotFiltreEnVol){
    const avant = JSON.stringify(_spotFiltre);
    _spotFiltre = Object.assign({}, _spotFiltre, f.reglages);
    if(JSON.stringify(_spotFiltre) !== avant && _spotFiltreOuvert) dessinerChipsFiltre();
  }
  const r = _spotFiltre;
  const actif = !!((r.spotter_continents||[]).length || (r.dx_continents||[]).length ||
                   r.masquer_deja_faits || r.seulement_lotw || r.seulement_besoins);
  if(btn) btn.style.color = actif ? 'var(--yellow)' : 'var(--accent2)';
  if(!ligne) return;
  const n = f.masques || 0;
  if(!n){ ligne.style.display = 'none'; ligne.textContent = ''; return; }
  let txt = '🔎 ' + n + ' spot' + (n > 1 ? 's' : '') + ' masqué' + (n > 1 ? 's' : '');
  if(f.repeches) txt += ' — ' + f.repeches + ' gardé' + (f.repeches > 1 ? 's' : '') + ' par une alerte';
  ligne.textContent = txt;
  ligne.style.display = '';
}

// Jeton de génération : refreshBandMap() est appelée depuis plusieurs sites
// (changement de bande, saisie fréquence, bandmapNoter()...) — sans garde,
// une réponse réseau arrivée dans le désordre (2 appels rapprochés) pouvait
// afficher les spots d'une bande déjà quittée.
let _bandmapGen = 0;

async function refreshBandMap(){
  const list = document.getElementById('bandmapList');
  if(!list) return;
  const _gen = ++_bandmapGen;
  const bandEl = document.getElementById('bandmapBand');
  if(bandEl) bandEl.textContent = (currentBand || '—') + ' MHz';
  try{
    const r = await fetch('/data/spots_ranked');
    if(!r.ok) return;
    const d = await r.json();
    if(_gen!==_bandmapGen) return;   // un appel plus récent a déjà démarré
    appliquerRetourFiltre(d.filtre);
    // Deuxième source : ce que l'opérateur a entendu LUI-MÊME en balayant.
    // Le S&P fait facilement la moitié des QSO d'un mono-opérateur, et une
    // station entendue mais spottée par personne était jusqu'ici perdue.
    let locaux = [];
    try{
      const rl = await fetch('/bandmap/local');
      if(rl.ok) locaux = (await rl.json()).spots || [];
    }catch(e){ /* le band map cluster reste utilisable sans les spots locaux */ }
    if(_gen!==_bandmapGen) return;
    const rng = _BM_RANGE[String(currentBand)];
    const inBand = s => {
      if(!s.freq) return false;
      if(rng){ const f = parseFloat(s.freq); return f >= rng[0] && f <= rng[1]; }
      return String(s.band) === String(currentBand);   // repli si bande hors table
    };
    // Les spots locaux portent leur fréquence en kHz : on la ramène en MHz
    // pour parler la même langue que le cluster avant de fusionner.
    const locauxMhz = locaux.map(s => ({
      call: s.call, freq: (Number(s.freq_khz) || 0) / 1000, band: s.band,
      local: true, age_s: s.age_s, note: s.note,
      explanation: 'Entendu il y a ' + Math.round((s.age_s || 0) / 60) + ' min'
                   + (s.note ? ' — ' + s.note : ''),
    }));
    // Une station à la fois spottée et entendue ne doit pas apparaître deux
    // fois : le spot du cluster gagne (il porte les points et le statut
    // multiplicateur), on ne garde le local que s'il n'a pas d'équivalent.
    // Le serveur envoie des kHz — unité du protocole cluster, imposée à toutes
    // les sources par freq_en_khz (logx_clusters.py). Tout le band map raisonne
    // en MHz : _BM_RANGE, le bandscope, la chute d'eau et bandmapClick, qui
    // multiplie par 1000 avant de commander le QSY. UNE seule conversion, ici
    // à l'entrée, au même endroit que celle des spots locaux juste au-dessus.
    const clusterMhz = (d.spots || []).map(
      s => Object.assign({}, s, {freq: (parseFloat(s.freq) || 0) / 1000}));
    const clusterCles = new Set(clusterMhz.map(
      s => String(s.call || '').toUpperCase() + '@' + Math.round(parseFloat(s.freq) * 1000)));
    const spots = clusterMhz
      .concat(locauxMhz.filter(
        s => !clusterCles.has(String(s.call || '').toUpperCase() + '@' + Math.round(s.freq * 1000))))
      .filter(inBand)
      .sort((a,b) => parseFloat(b.freq) - parseFloat(a.freq));   // fréquence haute en haut
    _bmSpots = spots;   // memorise pour la navigation clavier
    // Stations spottées dans un DÉPARTEMENT PAS ENCORE FAIT (demande F4GLD) :
    // croisées par indicatif avec /departments/targets (qui résout le dept via
    // le cluster ou le locator). Colorées distinctement + badge dept -> un clic
    // QSY + pré-remplit (bandmapClick, déjà en place). Seulement quand les
    // départements comptent (VHF/UHF ou échange-département) : aucun surcoût sinon.
    let _deptManquantParCall = {};
    const _deptPertinent = (typeof BANDES_THF !== 'undefined' && BANDES_THF.indexOf(currentBand) !== -1)
      || (window.LogxDeptGrid && typeof currentExchange !== 'undefined'
          && LogxDeptGrid.doitAfficher(currentExchange.label_r));
    if(_deptPertinent){
      try{
        const rt = await fetch('/departments/targets');
        if(rt.ok){
          const dt = await rt.json();
          (dt.targets || []).forEach(function(t){
            (t.spotted || []).forEach(function(sp){
              _deptManquantParCall[String(sp.call || '').toUpperCase()] = t.dept;
            });
          });
        }
      }catch(e){ /* band map utilisable sans l'info dept */ }
      if(_gen !== _bandmapGen) return;   // un refresh plus récent a démarré
    }
    const rig = (typeof rigState !== 'undefined') ? rigState : {};
    const txMhz = (rig.enabled && rig.freq_khz) ? rig.freq_khz/1000 : null;
    const rows = [];
    let txDone = false;
    const txRow = m => `<div class="bm-tx">▶ ${m.toFixed(3)} (radio)</div>`;
    for(const s of spots){
      const f = parseFloat(s.freq);
      if(txMhz && !txDone && f <= txMhz){ rows.push(txRow(txMhz)); txDone = true; }
      // Un spot local se distingue à l'œil du spot cluster : l'opérateur doit
      // savoir s'il regarde une information vérifiée par le réseau ou sa
      // propre note de balayage.
      const col = s.local ? 'var(--accent2)'
                          : (s.new_mult ? 'var(--green)' : (_BM_PCOL[s.priority] || 'var(--text)'));
      const style = `color:${col}` + (s.already_done ? ';opacity:.45;text-decoration:line-through' : '');
      // s.call vient du cluster DX (source externe non maîtrisée). Pour l'argument
      // onclick (contexte chaîne JS DANS un attribut HTML), escHtml ne suffit pas :
      // on restreint l'indicatif aux seuls caractères d'indicatif valides. Le texte
      // affiché et le title passent par escHtml.
      // Département PAS ENCORE FAIT pour cette station spottée -> à chasser.
      const _deptM = _deptManquantParCall[String(s.call || '').toUpperCase()] || '';
      const jsCall = String(s.call || '').replace(/[^A-Za-z0-9/]/g, '');
      // Repêché par une alerte alors que le filtre l'écartait : il DOIT rester
      // visible, sinon l'alerte sonnerait pour un spot introuvable dans la
      // liste — la meilleure façon de faire couper les alertes.
      const cls = 'bm-spot' + (s.hors_filtre ? ' hors' : '') + (_deptM ? ' bm-dept-manquant' : '');
      const infoBulle = (s.explanation || '')
        + (_deptM ? ' — DÉPARTEMENT ' + _deptM + ' pas encore fait : à chasser' : '')
        + (s.hors_filtre ? ' — hors filtre, gardé par une règle d\'alerte' : '')
        + (s.spotter ? ' — spotté par ' + s.spotter : '');
      // « Écouter ce spot » : mêmes règles d'hygiène que jsCall — mode et
      // coordonnées viennent du cluster (source externe), on ne laisse passer
      // dans l'attribut onclick que des caractères/nombres sûrs.
      const modeSpot = String(s.mode || '').replace(/[^A-Za-z0-9/-]/g, '');
      const earLat = Number.isFinite(s.lat) ? s.lat : 'null';
      const earLon = Number.isFinite(s.lon) ? s.lon : 'null';
      // Le cluster fournit bien plus souvent une GRILLE que des coordonnées,
      // et un spot local (entendu par l'opérateur) n'a aucune position. Sans
      // ça, le bouton promettait « proche du DX » et donnait en silence un
      // récepteur proche de CHEZ MOI — le titre le dit maintenant, et la
      // grille est transmise pour que le serveur situe le DX quand il peut.
      const grilleSpot = String(s.locator || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 6);
      const dxSitue = Number.isFinite(s.lat) || grilleSpot.length >= 4;
      const titreOreille = dxSitue
        ? trT('Écouter ce spot sur un récepteur WebSDR proche du DX')
        : trT('Position du DX inconnue — écouter cette fréquence sur un récepteur proche de chez toi');
      rows.push(`<div class="${cls}" onclick="bandmapClick('${jsCall}',${f},'${modeSpot}')" title="${escHtml(infoBulle)}">`
        + `<span class="bm-f">${f.toFixed(3)}</span>`
        + `<span class="bm-c" style="${style}">${s.local ? '👂' : (s.new_mult ? '★' : '')}${escHtml(s.call)}</span>`
        + (_deptM ? `<span class="bm-dept" title="Département ${escHtml(_deptM)} pas encore fait">${escHtml(_deptM)}</span>` : '')
        + `<span class="bm-ear${dxSitue ? '' : ' flou'}" onclick="event.stopPropagation();`
        + `ecouterSpot(${(f * 1000).toFixed(1)},${earLat},${earLon},'${modeSpot}','${grilleSpot}')"`
        + ` title="${escHtml(titreOreille)}">🔊</span></div>`);
    }
    if(txMhz && !txDone) rows.push(txRow(txMhz));
    list.innerHTML = rows.length ? rows.join('')
      : '<div class="bm-empty">aucun spot sur cette bande</div>';
    drawBandscope(spots, rng, txMhz);   // spectre d'activité visuel
    drawWaterfallRow(spots, rng);       // chute d'eau : mêmes spots, dans le temps
  }catch(e){ /* serveur injoignable : band map inchangé */ }
}
