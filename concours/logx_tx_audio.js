// ─── EV-7 : TX AUDIO GÉNÉRIQUE RTTY/SSTV (extrait de logx_logbook.js) ─────
// txAudioPtt() : PTT ON -> lecture de la forme d'onde -> PTT OFF (toujours,
// même en cas d'erreur, via finally). Chargé en <script> classique AVANT
// logx_logbook.js dans logx_logbook.html -- même portée globale partagée.
//
// Grep exhaustif fait AVANT extraction (candidat n°1 du 3e inventaire,
// inventaire-ev7-3e-2026-08-09.md, le plus sûr des 3 inventaires cumulés) :
// AUCUN appel top-level, AUCUNE dépendance du chemin critique. Les 2 SEULS
// appelants historiques étaient logx_rtty_panel.js (rttyEnvoyerTexte) et
// logx_sstv_panel.js (sstvEnvoyerImage), tous deux DÉJÀ des fichiers
// optionnels extraits par EV-7 -- dépendance optionnel→optionnel, le sens
// sûr établi par la convention EV-7. RTTY a depuis rejoint sa propre
// fenêtre détachée (logx_rtty.html, EV-7 phase 2 incrément B) qui charge
// ce fichier directement -- même appel rttyEnvoyerTexte(), portée globale
// partagée inchangée. Aucun fichier de test ne référence txAudioPtt
// directement.

// ─── TX audio générique (RTTY/SSTV) : PTT ON -> lecture -> PTT OFF ──────────
// Même modèle que logx_ft8.html (jouerForme+pttOn) — dupliqué ici plutôt que
// partagé entre pages : logx_ft8.html est une page <script> isolée (IIFE),
// aucun fichier JS commun entre les deux pour l'instant. PTT OFF dans un
// `finally` : même si la lecture audio plante en cours de route, la radio ne
// doit jamais rester bloquée en émission.
async function txAudioPtt(wave, sampleRate, outDeviceId){
  // duree_max : on CONNAÎT exactement la durée de ce qu'on va émettre, donc
  // on l'annonce. Elle ne limite rien — elle resserre le chien de garde du
  // PTT par ligne série (logx_cat.set_ptt_ligne), donc la durée pendant
  // laquelle une porteuse resterait sur l'air si cette page disparaissait en
  // pleine émission. Sans cette annonce, une image SSTV de 20 s serait
  // couverte par le plafond générique de 360 s, calibré lui sur la PD290
  // (289,7 s mesurées). +5 s de marge : démarrage de l'AudioContext et
  // latence de la carte son.
  const dureeMax = Math.ceil(wave.length / sampleRate) + 5;
  const pttOk = await fetch('/rig/ptt', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({on:true, duree_max: dureeMax})}).then(r=>r.json()).then(d=>!!d.ok).catch(()=>false);
  if(!pttOk) return {ok:false, error:"PTT refusé — vérifie le pilotage radio (CONFIG)"};
  try{
    const ctx = new (window.AudioContext || window.webkitAudioContext)({sampleRate});
    const buf = ctx.createBuffer(1, wave.length, sampleRate);
    buf.copyToChannel(wave, 0);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    if(outDeviceId && HTMLMediaElement.prototype.setSinkId){
      // Route vers un périphérique de sortie précis : MediaStreamDestination
      // + <audio> caché (setSinkId n'existe que sur HTMLMediaElement, pas
      // directement sur AudioContext dans la plupart des navigateurs).
      const dest = ctx.createMediaStreamDestination();
      src.connect(dest);
      const audioEl = new Audio();
      audioEl.srcObject = dest.stream;
      await audioEl.setSinkId(outDeviceId);
      await audioEl.play();
      src.start();
      await new Promise(resolve => { src.onended = resolve; });
      audioEl.pause();
    } else {
      src.connect(ctx.destination);
      src.start();
      await new Promise(resolve => { src.onended = resolve; });
    }
    try{ ctx.close(); }catch(e){}
    return {ok:true};
  }catch(e){
    return {ok:false, error: e.message};
  } finally {
    fetch('/rig/ptt', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({on:false})}).catch(()=>{});
  }
}
