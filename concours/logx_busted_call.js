// EV-7 phase 2, 13e increment (docs/LogX_AI_PRD.md) -- FILET ANTI-BUSTED
// CALL extrait tel quel de logx_logbook.js (extraction MECANIQUE, pas le
// motif bus d'evenements du pilote SCAN QSL PAPIER -- voir logx_scan_qsl.js).
// Analyse prealable (Workflow, cartographie + evaluation de 64 blocs) :
// bloc AUTONOME -- variable d'etat locale (_bcPastille) non partagee, UN SEUL
// point d'entree externe (2 lignes adjacentes dans submitQSO(), le coeur
// d'enregistrement d'un QSO, cf. logx_logbook.js -- vieillirPastilleBusted();
// verifierIndicatifApres(qso);), aucun autre fichier du depot n'appelle ces
// fonctions (grep confirme -- logx_outils_autonomes.js se contente de CITER
// corrigerBusted() en commentaire d'en-tete, decision du 9e increment EV-7
// de le laisser ici, pas un appel reel). Deja repere comme candidat propre
// lors du 9e increment sans avoir ete traite a ce moment-la.
//
// Dependances sortantes (escHtml/trF/trT/document.getElementById/fetch/
// qsoLog/renderLog/updateStats/notify) : memes globals "coeur" deja lus par
// les 13 extractions precedentes, portee partagee via <script> classique.
//
// tests/test_busted_call.py lit ce code directement (3 assertions sur la
// DEFINITION des fonctions, pas seulement leur site d'appel) -- adapte en
// meme temps que cette extraction, voir _lire_tout() dans ce fichier de test.

// ═══ FILET ANTI-BUSTED CALL ══════════════════════════════════════════════════
// Un indicatif mal copié coûte le QSO ET une pénalité au dépouillement, et on
// ne s'en aperçoit que des mois plus tard, sur le rapport de l'organisateur.
//
// LE MOMENT COMPTE PLUS QUE LE MOYEN. Vérifier PENDANT la frappe, c'est
// interrompre l'opérateur au pire moment et se tromper une fois sur deux (un
// indicatif à demi tapé ressemble à tout). On vérifie donc APRÈS coup : le
// QSO est logué, le formulaire est vidé, l'opérateur enchaîne — et une seconde
// plus tard, s'il y a lieu, une pastille propose la correction. Rien n'est
// modal, rien ne vole le focus, rien n'attend de réponse.
//
// TOUT EST LOCAL : /call/near mesure une distance de Damerau-Levenshtein sur
// l'index d'indicatifs du poste (calldb, MASTER.SCP si importé, archives, log
// en cours). Aucun réseau, aucune IA, aucun coût. Ce code existait déjà,
// testé, avec son endpoint — sans un seul appelant côté client.
let _bcPastille = null;      // {id, propose, restant} du QSO en cours de doute
// Jeton de génération : un 2e QSO loggué avant que la vérification /call/near
// du 1er n'ait répondu déclenche une 2e verifierIndicatifApres() — sans ce
// garde, la réponse TARDIVE du 1er QSO (déjà dépassé) pouvait écraser la
// pastille du 2e, proposant de corriger le mauvais QSO.
let _bcGen = 0;

async function verifierIndicatifApres(qso){
  const _gen = ++_bcGen;
  try{
    if(!qso || !qso.call) return;
    const r = await fetch('/call/near?call=' + encodeURIComponent(qso.call));
    if(!r.ok) return;
    const m = (await r.json()).matches || [];
    if(_gen!==_bcGen) return;   // un QSO plus récent a déjà déclenché sa propre vérification
    if(!m.length) return;   // near_matches rend [] si l'indicatif est CONNU
    // QUEL candidat mérite d'interrompre l'opérateur ? Premier essai : « un
    // indicatif que j'ai déjà travaillé ». Vérification en navigateur sur le
    // poste réel : F4GLDD → F4GLD était REJETÉ, parce que F4GLD figure dans la
    // base d'indicatifs sans jamais avoir été travaillé (on ne se travaille
    // pas soi-même). Un filet qui ne se déclenche jamais vaut un filet
    // débranché — c'est le défaut qu'on est en train de corriger.
    //
    // Règle retenue, à deux détentes :
    //   - un voisin DÉJÀ TRAVAILLÉ est un signal fort : on le propose ;
    //   - sinon, on ne propose que s'il n'y a QU'UN SEUL voisin connu. Deux
    //     candidats jamais travaillés, c'est une devinette, et une pastille
    //     qui devine est une pastille qu'on cesse de lire.
    const travaille = m.find(c => c.qso_count > 0);
    const cible = travaille || (m.length === 1 ? m[0] : null);
    if(!cible) return;
    afficherPastilleBusted(qso, cible);
  }catch(e){ /* filet optionnel : jamais d'erreur visible pour l'opérateur */ }
}

function afficherPastilleBusted(qso, cible){
  const zone = document.getElementById('bustedPastille');
  if(!zone) return;
  _bcPastille = {id: qso.id, propose: cible.call, restant: 2};
  // Dire d'où vient la confiance : « 12 QSO dans ton historique » n'a pas le
  // même poids que « connu, jamais contacté ». L'opérateur tranche mieux avec
  // cette nuance qu'avec une pastille qui affirme sans se justifier.
  const vus = cible.qso_count > 0
    ? trF('{n} QSO dans ton historique', {n: cible.qso_count})
    : trT('indicatif connu, jamais contacté');
  zone.innerHTML =
      `<span class="bp-txt">${escHtml(qso.call)} → <b>${escHtml(cible.call)}</b> ?</span>`
    + `<span class="bp-info">${escHtml(vus)}</span>`
    + `<button class="bp-oui" onclick="corrigerBusted()">${escHtml(trT('corriger'))}</button>`
    + `<button class="bp-non" onclick="fermerPastilleBusted()">${escHtml(trT('non'))}</button>`;
  zone.style.display = 'flex';
}

function fermerPastilleBusted(){
  const zone = document.getElementById('bustedPastille');
  if(zone){ zone.style.display = 'none'; zone.innerHTML = ''; }
  _bcPastille = null;
}

// Sans action, la pastille s'efface au bout de deux QSO : elle ne doit pas
// rester en travers de l'écran pendant une série.
function vieillirPastilleBusted(){
  if(!_bcPastille) return;
  if(--_bcPastille.restant <= 0) fermerPastilleBusted();
}

async function corrigerBusted(){
  const p = _bcPastille;
  if(!p) return;
  fermerPastilleBusted();
  const q = qsoLog.find(x => x.id === p.id);
  if(!q){ notify(trT('QSO introuvable — corrige-le à la main dans le log.')); return; }
  const ancien = q.call;
  q.call = p.propose;
  q._edited = true;
  try{
    await fetch('/log/update', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(q)
    });
  }catch(e){
    // Hors ligne : la correction reste locale, comme editQSO() (même choix).
    console.warn('Serveur hors ligne, correction locale uniquement');
  }
  try{ renderLog(); }catch(e){}
  try{ updateStats(); }catch(e){}
  notify(trF('{a} corrigé en {b}', {a: ancien, b: p.propose}));
}
