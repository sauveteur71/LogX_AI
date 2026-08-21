// ─── EV-7 : EXPORTS EDI + CABRILLO (extrait de logx_logbook.js) ───────────
// ediSerial()/exportEDI() (format REG1TEST, dépôt THF par bande) et
// exportCabrillo()/remindSubmitLog() (le fichier Cabrillo lui-même est
// fabriqué PAR LE SERVEUR, logx_export.build_cabrillo -- ce client ne fait
// que naviguer vers /log/export/cabrillo et rappeler l'URL de dépôt).
// Chargé en <script> classique AVANT logx_logbook.js dans
// logx_logbook.html -- même portée globale partagée, pas de module ES.
//
// Grep exhaustif fait AVANT extraction (candidat n°4 de
// inventaire-ev7-23e-2026-08-09.md) : AUCUN appel top-level restant dans
// logx_logbook.js ne dépend d'un symbole de ce fichier, et aucun autre
// fichier concours/logx_*.js déjà extrait n'y fait référence. exportEDI()
// appelle exportCabrillo() en corps de fonction (repli HF, formatDepot()
// !== 'EDI') -- les deux restent ensemble dans ce fichier, pas de
// dépendance croisée introduite.

// ─── EXPORTS ─────────────────────────────────────────────────────────────────

// N° de série d'un enregistrement EDI, tel qu'il a RÉELLEMENT circulé sur l'air.
//
// Le n° envoyé est alloué par le serveur (logx_storage.allocate_next_serial via
// /log/next_serial), affiché à l'opérateur puis transmis au correspondant : il
// ne doit JAMAIS être redérivé de la position du QSO dans le fichier exporté.
// La séquence des num_sent comporte des trous parfaitement NOMINAUX — QSO
// supprimé en cours d'épreuve (deleteQSO/undoLastQSO), doublon refusé après
// allocation, erreur serveur après allocation, n° corrigé à la main, sans
// compter les QSO incomplets écartés par isValidQSO() — et allocate_next_serial
// ne réutilise jamais un numéro libéré (« un trou dans la séquence est
// toléré »). Renuméroter 1..N décale alors TOUS les QSO suivants de la bande :
// en cross-check IARU/REF, un n° envoyé qui ne correspond pas au n° reçu par le
// correspondant fait tomber le QSO (NIL) des DEUX côtés.
//
// Un champ vide reste vide : dans un log de soumission on n'invente pas un
// numéro qui n'a jamais été échangé (l'ancien repli `||'001'` sur le n° reçu
// fabriquait de la donnée). Un échange fixe non numérique (type Field Day) est
// recopié tel quel.
function ediSerial(v){
  const s = String(v == null ? '' : v).trim();
  if(!s) return '';
  return /^\d+$/.test(s) ? s.padStart(3,'0') : s;
}

async function exportEDI(){
  // Validation avant export
  const warnings = [];
  const invalid = qsoLog.filter(q=>!isValidQSO(q));
  if(invalid.length) warnings.push(trF('⚠️ {n} QSO incomplet(s) ignoré(s) ({calls})', {n: invalid.length, calls: invalid.map(q=>q.call||'?').join(', ')}));
  const missingLoc = qsoLog.filter(q=>isValidQSO(q) && (!q.locator||q.locator.length<6));
  if(missingLoc.length) warnings.push(trF('⚠️ {n} QSO sans locator (points = 0)', {n: missingLoc.length}));
  // isValidQSO() n'exige pas le n° envoyé (import ADIF sans STX, champ vidé à la
  // main) : il partira VIDE plutôt qu'inventé — autant le signaler avant.
  const missingSerial = qsoLog.filter(q=>isValidQSO(q) && !ediSerial(q.num_sent));
  if(missingSerial.length) warnings.push(trF('⚠️ {n} QSO sans n° de série envoyé ({calls})', {n: missingSerial.length, calls: missingSerial.map(q=>q.call||'?').join(', ')}));
  const dups = countDupes(qsoLog);
  if(dups) warnings.push(trF('⚠️ {n} doublon(s) dans le log', {n: dups}));
  if(warnings.length){
    if(!(await _confirmDupBanner(trF('VALIDATION LOG\n\n{warnings}\n\nGénérer quand même le fichier EDI ?', {warnings: warnings.join('\n')}), 'Générer quand même', 'Annuler'))) return;
  }

  // Lire config depuis localStorage
  let ediCfg = {};
  try{ ediCfg = JSON.parse(localStorage.getItem('logx_config')||'{}'); }catch(e){}
  const ediCall    = ediCfg.callsign || myCall || 'F6KQJ';
  const ediLocator = ediCfg.locator  || myLocator || '';
  const ediClub    = ediCfg.club     || ediCfg.callsign || 'F6KQJ';
  const ediRName   = ediCfg.op_name  || 'Opérateur';
  const ediRCall   = ediCfg.op_call  || ediCall;
  const ediCity    = ediCfg.city     || '';
  const ediPostal  = ediCfg.postal   || '';
  const ediAltitude= ediCfg.altitude || '';
  const ediDept    = ediPostal.length>=2 ? ediPostal.slice(0,2) : '';
  const ediEmail   = ediCfg.email    || '';
  const ediPower   = ediCfg.power    || '100';
  const ediRadio   = ediCfg.radio    || 'IC-9700';
  const ediCountry = ediCfg.country  || 'FRA';
  const ediAnt144  = ediCfg.ant_144  || 'Yagi';
  const ediAnt432  = ediCfg.ant_432  || 'Yagi';
  // Tous les opérateurs réels (multi-op) — MOpe1/MOpe2 = format EDI (2 slots max),
  // la liste complète est aussi rappelée dans les Remarks pour ne perdre personne.
  const ediOpList  = (ediCfg.operators||[]).map(o=>o.call).filter(Boolean);
  const ediMOpe1   = ediOpList[0] || ediRCall;
  const ediMOpe2   = ediOpList[1] || '';
  // Dates du concours
  const TDATE_START = (ediCfg.contest_start_date||'20260704').replace(/-/g,'');
  const TDATE_END   = (ediCfg.contest_end_date  ||'20260705').replace(/-/g,'');

  // Le format vient du RÈGLEMENT du concours (voir formatDepot) et non plus
  // d'une liste d'identifiants tenue à la main, qui en oubliait dix-sept.
  if(formatDepot() !== 'EDI'){
    exportCabrillo(ediCfg, myCall);
    return;
  }

  // Le 6 m (50 MHz) EST du THF et se dépose en EDI : sans lui, IARU_50MHZ (et
  // tout log 6 m) donnait « Aucun QSO VHF/UHF à exporter » — aucun fichier au
  // moment du dépôt (revue 01/08/2026).
  const VHF_UHF_SHF_BANDS = ['50','144','432','1296','2320','3400','5760','10368','24048','47088'];
  const bands = [...new Set(qsoLog.map(q=>q.band))].filter(b=>VHF_UHF_SHF_BANDS.includes(b));
  if(!bands.length){ notify('Aucun QSO VHF/UHF à exporter !\n\nPour les concours HF (ARRL FD, CQ WW, etc.),\nle format Cabrillo sera généré automatiquement.'); return; }

  // Téléchargements espacés dans le temps : déclenchés trop vite d'affilée
  // (boucle synchrone), Chrome bloque silencieusement le 2e fichier en
  // pensant à un spam de téléchargements — d'où "je ne reçois que le 144".
  bands.forEach((band, bandIdx)=>{ setTimeout(()=>{
    const bandQSOs = qsoLog.filter(q=>q.band===band && isValidQSO(q));
    if(!bandQSOs.length) return;
    const bandScore = bandQSOs.reduce((s,q)=>s+(q.points||0),0);
    const antBand   = band==='432' ? ediAnt432 : ediAnt144;

    const lines = [
      '[REG1TEST;1]',
      `TName=${ediCfg.contest||'Rallye des Points Hauts'}`,
      `TDate=${TDATE_START};${TDATE_END}`,
      `PCall=${myCall||ediCall}`,
      `PWWLo=${myLocator||ediLocator}`,
      `PExch=`,
      `PSect=${ediCfg.section||'SOMB'}`,
      `PBand=${band} MHz`,
      `PClub=${ediClub}`,
      `RName=${ediRName}`,
      `RCall=${ediRCall}`,
      `RAdr1=${ediCity}`,
      `RPoCo=${ediPostal}`,
      `RCity=${ediCity}`,
      `RCoun=${ediCountry}`,
      `RPhon=`,
      `RHBBS=${ediEmail}`,
      `MOpe1=${ediMOpe1}`,
      `MOpe2=${ediMOpe2}`,
      `STXEq=${ediRadio}`,
      `SPowe=${ediPower}`,
      `SRXEq=${ediRadio}`,
      `SAnte=${antBand}`,
      `SAntH=`,
      // Spec officielle REG1TEST (IARU Region 1, "Standard Format for
      // Electronic Contest Log Exchange", Vienna 1998, issue 1.1) : CQSOs
      // attend DEUX valeurs séparées par ';' (nombre de QSO;multiplicateur
      // de bande) — le champ ne portait que le nombre de QSO. Multiplicateur
      // fixé à 1 (pas de multiplicateur de bande distinct dans les concours
      // REF THF actuels) — valeur vue telle quelle dans les deux exemples
      // officiels du document ("CQSOs=24;1").
      // Le champ 'CScor' n'existe PAS dans la spec : le score total
      // s'appelle 'CToSc' ("Claimed total score"). Un champ inconnu peut
      // faire échouer un validateur strict côté club/robot de dépôt.
      `CQSOs=${bandQSOs.length};1`,
      `CQSOP=${bandScore}`,
      `CToSc=${bandScore}`,
      `TMore=`,
      `[Remarks]`,
      `Logiciel: LogX AI v3.0 — ${ediCall} ${ediLocator}`,
      ...(ediAltitude ? [`Altitude: ${ediAltitude}m`] : []),
      ...(ediDept ? [`Département: ${ediDept}`] : []),
      ...(ediOpList.length ? [`Opérateurs : ${ediOpList.join(', ')}`] : []),
      ...(getSoapbox(band) ? [getSoapbox(band)] : []),
      `[QSOrecords;${bandQSOs.length}]`,
    ];

    let edi = lines.join('\r\n') + '\r\n';
    bandQSOs.forEach(q=>{
      const serial  = ediSerial(q.num_sent);   // celui transmis sur l'air, JAMAIS l'index de boucle
      const numRcvd = ediSerial(q.num_rcvd);   // vide reste vide : rien d'inventé
      const timeStr = q.time.replace(':',''); // HHMM
      const modeCode = q.mode==='CW'?2:q.mode==='FM'?6:1; // 1=SSB
      // Gabarit REG1TEST, 15 champs : date;heure;indicatif;mode;RST env;n° env;
      // RST reçu;n° reçu;échange reçu;WWL reçu;points;new exchange;new WWL;
      // new DXCC;doublon. Le mode est déjà en champ 4 sous forme de code
      // numérique — le champ 13 est l'indicateur « new WWL », pas une seconde
      // copie du mode en texte.
      edi += `${q.date};${timeStr};${q.call};${modeCode};${q.rst_sent};${serial};${q.rst_rcvd};${numRcvd};;${q.locator||''};${q.points||0};;;;\r\n`;
    });
    edi += `[END; do not edit below this line]\r\n`;

    const blob = new Blob([edi],{type:'text/plain;charset=utf-8'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    // Nom fichier dynamique : CALL_CONTESTNAME_YEAR_BANDMHz.edi
    const contestSlug = (ediCfg.contest||'Contest').replace(/[^A-Za-z0-9]/g,'_').replace(/_+/g,'_').slice(0,30);
    const contestYear = TDATE_START.slice(0,4) || new Date().getFullYear();
    a.download = `${myCall.replace('/','_')}_${contestSlug}_${contestYear}_${band}MHz.edi`;
    a.click();
  }, bandIdx * 500); });

  // Rappel soumission
  setTimeout(()=>{
    remindSubmitLog(ediCfg, {
      fallbackUrl: 'http://concours.r-e-f.org/tools/upload/thf.php',
      extraNote: trF('⚠️ 1 fichier EDI PAR BANDE (144 MHz et 432 MHz séparés)'),
    });
  }, bands.length * 500 + 300);
}

// Le fichier Cabrillo est fabriqué PAR LE SERVEUR (logx_export.build_cabrillo).
// Il y avait ici une seconde implémentation, complète et divergente : elle
// détenait seule les noms officiels de concours, mais écrivait l'échange SANS
// le compte-rendu (un CQ WW partait avec « 001 » au lieu de « 59 14 »),
// n'émettait les lignes CATEGORY-* que pour le Field Day, et exportait qsoLog
// sans le filtrage de portée concours+année qu'applique /log/export/cabrillo.
// Deux générateurs pour un même fichier, c'est une divergence garantie : le
// second est supprimé, les noms officiels sont passés dans les définitions de
// concours (cabrillo_name), où le serveur les lit.
function exportCabrillo(cfg, call){
  const nom = (CONTEST_SCHEDULE[currentContest] || {}).name || currentContest;
  const score = qsoLog.reduce((s, q) => s + (q.points || 0), 0);
  // Téléchargement par navigation : le serveur pose déjà Content-Disposition
  // avec le bon nom de fichier, et le cookie de session part avec la requête.
  window.location.href = '/log/export/cabrillo';
  setTimeout(() => {
    notify(trF('📤 FICHIER CABRILLO GÉNÉRÉ\n\nConcours : {contest}\nQSOs : {n} — Score déclaré : {score} pts',
      {contest: nom, n: qsoLog.length, score: score}));
    remindSubmitLog(cfg);
  }, 400);
}

// Rappel + ouverture directe de la page de soumission — auto-remplie en CONFIG
// depuis le règlement du concours sélectionné (voir selectContest() côté
// logx_configuration.html), corrigeable manuellement si besoin. Un clic en
// moins qu'un simple rappel texte : le fichier vient d'être téléchargé, la
// page de dépôt s'ouvre directement dans un nouvel onglet pour le déposer.
function remindSubmitLog(cfg, opts){
  opts = opts || {};
  const submitUrl = (cfg && cfg.submit_url || '').trim() || opts.fallbackUrl || '';
  const submitDeadline = (cfg && cfg.submit_deadline || '').trim();
  if (!submitUrl){
    notify(trF('📭 Aucune URL de soumission connue pour ce concours — pense à vérifier le règlement et à renseigner le champ en CONFIG (section SCOREBOARD & SOUMISSION).'));
    return;
  }
  const deadlineLine = submitDeadline ? trF('\nDélai : {d}', {d: submitDeadline}) : '';
  const extraLine = opts.extraNote ? ('\n\n' + opts.extraNote) : '';
  notify(trF('📤 SOUMISSION DU LOG\n\nOuverture de la page de dépôt…{deadline}{extra}',
    {deadline: deadlineLine, extra: extraLine}));
  // Popup bloquée par le navigateur : window.open() renvoie null, on retombe
  // sur le lien cliquable déjà donné dans la notification texte ci-dessus.
  const w = window.open(submitUrl, '_blank', 'noopener');
  if (!w){
    notify(trF('⚠️ Le navigateur a bloqué l\'ouverture automatique — clique le lien : {url}', {url: submitUrl}));
  }
}
