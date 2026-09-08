// logx_voacap_panel.js — Panneau VOACAP a la demande du LOGBOOK
// Extrait de logx_logbook.js (campagne EV-7, 53e increment, 2026-09-08).
// Deux fonctions autonomes (feature expert-only) : ouverture du panneau et
// calcul cote serveur (/data/voacap). Depend de escHtml() du coeur, appele
// a l'execution — chargement classique AVANT logx_logbook.js (portee globale
// partagee, pas de module ES), meme convention que les 52 increments precedents.

function openVoacapPanel(){
  const ov = document.getElementById('voacapOverlay');
  const dxField = document.getElementById('voacapDx');
  if(!ov || !dxField) return;
  const current = (document.getElementById('inputCall')||{}).value || '';
  dxField.value = current.trim().toUpperCase();
  ov.classList.add('show');
  document.getElementById('voacapInner').innerHTML = '';
  dxField.focus();
}

async function runVoacapCheck(){
  const inner = document.getElementById('voacapInner');
  const dx = (document.getElementById('voacapDx').value || '').trim();
  const mode = document.getElementById('voacapMode').value;
  const power = document.getElementById('voacapPower').value || '100';
  if(!dx){
    inner.innerHTML = '<div class="shortcuts-row"><span style="color:var(--red)">Indique un locator ou un indicatif</span></div>';
    return;
  }
  inner.innerHTML = '<div class="shortcuts-row"><span>⏳ Calcul VOACAP en cours (peut prendre quelques secondes)…</span></div>';
  let data;
  try{
    const res = await fetch(`/data/voacap?dx=${encodeURIComponent(dx)}&mode=${encodeURIComponent(mode)}&power=${encodeURIComponent(power)}`);
    data = await res.json();
  }catch(e){
    inner.innerHTML = '<div class="shortcuts-row"><span style="color:var(--red)">❌ Serveur injoignable</span></div>';
    return;
  }
  if(!data.ok){
    inner.innerHTML = `<div class="shortcuts-row"><span style="color:var(--red)">❌ ${escHtml(data.error||'Échec du calcul')}</span></div>`;
    return;
  }
  const relColor = (rel) => {
    if(rel == null) return 'var(--bg3)';
    if(rel >= 0.7) return 'var(--green)';
    if(rel >= 0.3) return 'var(--yellow)';
    if(rel > 0) return 'rgba(var(--accent-rgb),.35)';
    return 'var(--bg3)';
  };
  const hours = data.hours || [];
  const freqs = data.freqs_mhz || [];
  let head = '<div style="font-family:var(--font-mono);font-size:12px;color:var(--muted);margin-bottom:10px">'+
    `${data.distance_km} km · az ${data.azimuth_deg}° / retour ${data.back_azimuth_deg}° · SSN ${data.ssn} · ${data.month}/${data.year}`+
    '</div>';
  let table = '<table style="border-collapse:collapse;width:100%;font-family:var(--font-mono);font-size:11px">';
  table += '<tr><td style="padding:2px 4px;color:var(--muted)">MHz \\ h</td>' +
    hours.map(h=>`<td style="padding:2px 3px;text-align:center;color:var(--muted)">${h.hour}</td>`).join('') + '</tr>';
  freqs.forEach((f, fi) => {
    table += `<tr><td style="padding:2px 4px;color:var(--text)">${f}</td>`;
    hours.forEach(h => {
      const b = (h.bands||[])[fi] || {};
      const title = b.rel != null
        ? `${Math.round(b.rel*100)}% · SNR ${b.snr_db!=null?b.snr_db+' dB':'?'}${b.mode?' · '+b.mode:''}`
        : 'pas de donnée';
      table += `<td title="${title}" style="padding:3px;text-align:center;background:${relColor(b.rel)};border:1px solid var(--bg)">`+
        (b.rel != null ? Math.round(b.rel*100) : '·') + '</td>';
    });
    table += '</tr>';
  });
  table += '</table>';
  inner.innerHTML = head + table;
}
