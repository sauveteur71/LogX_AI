// ─── EV-7 : BAND MAP SEARCH & POUNCE (extrait de logx_logbook.js) ─────────
// _bmSpots (liste des spots réellement affichés, pour la navigation
// clavier), bandmapNoter() (noter la station entendue à la fréquence
// radio), bandmapSaut() (sauter de spot en spot au clavier). Chargé en
// <script> classique AVANT logx_logbook.js dans logx_logbook.html --
// même portée globale partagée.
//
// Grep exhaustif fait AVANT extraction (candidat n°2 du 3e inventaire,
// inventaire-ev7-3e-2026-08-09.md) : AUCUN appel top-level. Périmètre de
// lignes délibérément restreint à CE bloc précis -- la section voisine
// (_BM_PCOL/_BM_CSSVAR/_BM_RANGE, juste au-dessus dans logx_logbook.js)
// reste dans le cœur, utilisée par bandFromFreq() (chemin critique).
//
// Dépendances croisées EN CORPS DE FONCTION (sûres, direction
// optionnel<->cœur déjà établie par la convention EV-7) :
//   - bandmapNoter() appelle refreshBandMap() (EV-7 33e increment :
//     extraite vers logx_filtre_spots.js, plus dans logx_logbook.js --
//     ce fichier-ci charge AVANT logx_filtre_spots.js, mais sans risque
//     car l'appel se produit en corps de fonction, jamais au chargement,
//     motif déjà rencontré avec les MACROS F1-F8 au 32e increment) ;
//   - bandmapSaut() appelle bandmapClick() (cœur, resté dans
//     logx_logbook.js) ;
//   - refreshBandMap() (désormais logx_filtre_spots.js) écrit
//     `_bmSpots = spots;` -- variable déclarée ici, lue par bandmapSaut()
//     -- sûr car ce fichier charge TOUJOURS avant logx_logbook.js (portée
//     globale partagée, pas de chargement conditionnel) ;
//   - logx_theme_shortcuts.js (déjà extrait) appelle bandmapSaut()/
//     bandmapNoter() depuis son gestionnaire clavier global (Ctrl+↑/↓,
//     Ctrl+Entrée) -- devient optionnel→optionnel après cette extraction.

// ─── BAND MAP : SEARCH & POUNCE ──────────────────────────────────────────────
// Les spots réellement affichés, dans l'ordre où ils le sont : c'est sur cette
// liste que saute la navigation clavier, pour que « suivant » veuille dire la
// ligne suivante À L'ÉCRAN et pas autre chose.
let _bmSpots = [];

// Noter la station en cours : l'indicatif tapé, à la fréquence où la radio est
// posée. C'est LE geste du S&P — on entend quelqu'un, on le note, on continue
// de balayer, on le rappellera plus tard.
async function bandmapNoter(){
  const inp = document.getElementById('inputCall');
  const call = inp ? inp.value.trim().toUpperCase() : '';
  const rig = (typeof rigState !== 'undefined') ? rigState : {};
  if(!call){ notify('👂 Tape d\'abord l\'indicatif entendu'); return; }
  if(!rig.enabled || !rig.freq_khz){
    notify('👂 Fréquence radio inconnue — le pilotage CAT doit être actif');
    return;
  }
  try{
    const res = await fetch('/bandmap/add', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({call, freq_khz: rig.freq_khz, band: currentBand,
                            mode: rig.mode || currentMode})}).then(r=>r.json());
    if(res.ok){
      notify(trF('👂 {call} noté sur {f} kHz', {call, f: Math.round(rig.freq_khz)}));
      refreshBandMap();
    } else notify(trF('❌ {err}', {err: res.error || 'refus'}));
  }catch(e){ notify(trF('❌ {err}', {err: e.message})); }
}

// Saut de spot en spot au clavier, sans jamais viser à la souris. L'indicatif
// est pré-rempli au passage : en S&P on arrive sur la station en sachant déjà
// qui c'est, il ne reste qu'à confirmer et loguer.
function bandmapSaut(sens){
  if(!_bmSpots.length){ notify('band map vide sur cette bande'); return; }
  const rig = (typeof rigState !== 'undefined') ? rigState : {};
  const ici = (rig.enabled && rig.freq_khz) ? rig.freq_khz / 1000 : null;
  let cible = null;
  if(ici === null){
    cible = _bmSpots[sens > 0 ? 0 : _bmSpots.length - 1];
  } else if(sens < 0){
    // _bmSpots est trié fréquence DÉCROISSANTE : « suivant vers le haut » est
    // donc le dernier élément encore au-dessus de la fréquence courante.
    const sup = _bmSpots.filter(s => parseFloat(s.freq) > ici + 0.0002);
    cible = sup.length ? sup[sup.length - 1] : null;
  } else {
    cible = _bmSpots.find(s => parseFloat(s.freq) < ici - 0.0002) || null;
  }
  if(!cible){ notify(sens > 0 ? 'dernier spot de la bande' : 'premier spot de la bande'); return; }
  bandmapClick(String(cible.call || '').replace(/[^A-Za-z0-9/]/g, ''), parseFloat(cible.freq),
              String(cible.mode || '').replace(/[^A-Za-z0-9/-]/g, ''));
}
