// logx_configuration_acom.js — Ampli ACOM série RS-232 (détection port, test
// connexion, OPERATE/STANDBY/OFF), extrait de logx_configuration.js le
// 23/08/2026 (chantier « alléger les gros fichiers », PASSATION §6). 2e lot,
// après Cloud Sync. Déplacement PUR, aucune modification de logique.
//
// Les 3 fonctions ne sont appelées QUE par des handlers HTML (onfocus/onclick),
// jamais au chargement -> ordre de chargement sans impact. Elles restent
// globales : les onfocus="refreshAcomPorts()"/onclick="testAcomConnection()"/
// "acomSetOperate(...)" du HTML continuent de résoudre.
//
// Dépendance : escC() (échappement HTML) et window._cfgRestauree restent des
// globaux de logx_configuration.js, chargé avec ce fichier -> disponibles au
// moment de l'appel (jamais au chargement). Chargé APRÈS configuration.js.

// ─── ACOM (série RS-232) ──────────────────────────────────────────────────────
async function refreshAcomPorts(){
  // Même patron que refreshCatPorts()/refreshAmpPorts() (réplique voulue,
  // pas de fonction générique factorisée dans ce dépôt pour l'instant) :
  // repli sur le port déjà enregistré tant que la liste réseau n'est pas
  // encore arrivée.
  const sel = document.getElementById('acom_port');
  const prev = sel.value || (window._cfgRestauree || {}).acom_port || '';
  sel.innerHTML = '<option value="">⏳ Recherche des ports...</option>';
  try{
    const res = await fetch('/rig/ports');
    const data = await res.json();
    const ports = data.ports || [];
    sel.innerHTML = ports.length
      ? ports.map(p => `<option value="${escC(p.device)}">${escC(p.device)} — ${escC(p.description||'')}</option>`).join('')
      : '<option value="">Aucun port détecté</option>';
    if (prev && ports.some(p => p.device === prev)) sel.value = prev;
  }catch(e){
    sel.innerHTML = '<option value="">Serveur injoignable</option>';
  }
}

async function testAcomConnection(){
  const result = document.getElementById('acomTestResult');
  const port = document.getElementById('acom_port').value;
  if (!port){
    result.textContent = '⚠️ Port série manquant';
    result.style.color = 'var(--yellow)';
    return;
  }
  result.textContent = '⏳ Test en cours...';
  result.style.color = 'var(--muted)';
  const payload = {
    port,
    model: document.getElementById('acom_model').value,
    timeout: parseFloat(document.getElementById('acom_timeout').value) || 3.0,
  };
  try{
    const res = await fetch('/acom/test', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)});
    const r = await res.json();
    if (r.ok){
      const t = r.telemetry || {};
      result.textContent = `✅ ACOM joint (${t.status || '?'}, ${t.power_w ?? '?'} W)`;
      result.style.color = 'var(--green)';
    } else {
      result.textContent = `❌ ${r.error || 'Échec'}`;
      result.style.color = 'var(--red)';
    }
  }catch(e){
    result.textContent = '❌ Serveur injoignable';
    result.style.color = 'var(--red)';
  }
}

async function acomSetOperate(mode){
  const result = document.getElementById('acomOperateResult');
  result.textContent = '⏳...';
  result.style.color = 'var(--muted)';
  try{
    const res = await fetch('/acom/operate', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({mode})});
    const r = await res.json();
    if (r.ok){
      result.textContent = `✅ ${mode.toUpperCase()}`;
      result.style.color = 'var(--green)';
    } else {
      result.textContent = `❌ ${r.error || 'Échec'}`;
      result.style.color = 'var(--red)';
    }
  }catch(e){
    result.textContent = '❌ Serveur injoignable';
    result.style.color = 'var(--red)';
  }
}
