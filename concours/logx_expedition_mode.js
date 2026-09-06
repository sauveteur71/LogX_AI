// EV-7 45e increment : MODE EXPEDITION (saisie simplifiee) -- extrait de
// logx_logbook.js (docs/LogX_AI_PRD.md). Charge en <script> classique dans
// logx_logbook.html, AVANT logx_logbook.js -- portee globale partagee.
//
// Contient : l'etat expeditionMode (let partage, lu aussi par la validation du
// coeur) et applyExpeditionMode() (masque N.serie/locator en pile-up DX/XOTA
// hors concours). Non appelee au TOP-LEVEL.

// ─── MODE EXPÉDITION : saisie simplifiée (indicatif + RST env/reçu seulement) ──
// En pile-up d'expédition (chasse DX/activation POTA-SOTA... SANS concours
// réel) l'échange est juste le report : on masque les champs N° de série et
// locator pour ne garder que l'essentiel et enchaîner très vite.
let expeditionMode = false;
function applyExpeditionMode(on){
  expeditionMode = (String(on) === '1' || on === true);
  const numRow = document.getElementById('numFieldRow');
  const locGrp = document.getElementById('locatorGroup');
  // Un VRAI concours sélectionné (REF/IARU/CQ...) impose son propre échange —
  // le masquer ferait perdre le n° de série et/ou le locator nécessaires au
  // calcul du score (ex: REF_CCD noté en km × locators -> 0 pt logué sans
  // locator correspondant). La saisie simplifiée ne doit donc s'appliquer que
  // hors concours réel (activation POTA/SOTA/... ou aucun concours choisi).
  const realContestExchange = !!currentContest && !activationProgram;
  // Certains concours réels n'ont PAS de n° de série du tout (ex. World Wide
  // Award : juste un report, règlement §3) — currentExchange.no_exchange le
  // signale explicitement (cf. applyExchangeFormat, déjà appelé avant ceci) :
  // masquer le champ N° reste correct même si realContestExchange est vrai.
  const noExchange = currentExchange && currentExchange.no_exchange === true;
  // Le n° de série (échange concours) est aussi masqué en LOGBOOK SIMPLE (pas
  // de concours -> pas d'échange à faire), indépendamment du mode expédition.
  const hideNum = (expeditionMode && !realContestExchange) || usageMode === 'simple' || noExchange;
  const hideLoc = expeditionMode && !realContestExchange;
  if(numRow) numRow.style.display = hideNum ? 'none' : '';
  if(locGrp) locGrp.style.display = hideLoc ? 'none' : '';
  document.body.classList.toggle('expedition-on', expeditionMode);
}
