// logx_configuration_cloudsync.js — Synchronisation multi-poste (Cloud Sync +
// MySQL), extrait de logx_configuration.js le 23/08/2026 (chantier « alléger
// les gros fichiers », PASSATION §6). Bloc le plus sûr : zéro dépendance
// externe (uniquement getElementById/fetch/JSON/parseInt), aucune émission
// radio, aucun code exécuté au chargement — pures déclarations globales.
//
// Chargé en <script src> APRÈS logx_configuration.js dans logx_configuration.
// html : les fonctions restent globales, donc les onclick="cloudsyncNow()"/
// "testMysqlConnection()"/"mysqlSyncNow()" du HTML continuent de résoudre. Le
// code ci-dessous est le déplacement EXACT du bloc d'origine, sans une seule
// modification de logique (vérifié par test d'équivalence + contre-épreuve).

// ─── CLOUD SYNC (dossier partagé multi-poste) ───────────────────────────────
async function cloudsyncNow(){
  const result = document.getElementById('cloudsyncResult');
  result.textContent = '⏳ synchronisation en cours…';
  result.style.color = 'var(--muted)';
  try{
    // Correctif M6 : contrairement à testCatConnection()/testAmpConnection()
    // (lisent les valeurs ACTUELLEMENT affichées), ce bouton n'envoyait rien
    // et le serveur retombait sur la DERNIÈRE config sauvegardée — un champ
    // modifié sans clic préalable sur SAUVEGARDER était ignoré en silence.
    const res = await fetch('/cloudsync/now', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        cloudsync_mode: document.getElementById('cloudsync_mode').value,
        cloudsync_folder: document.getElementById('cloudsync_folder').value.trim(),
      }),
    });
    const r = await res.json();
    if(r.ok){
      result.textContent = `✅ ${r.pushed} QSO envoyés · ${r.pulled} récupérés` + (r.sources ? ` (${r.sources} autre(s) poste(s))` : '');
      result.style.color = 'var(--green)';
    } else {
      result.textContent = `❌ ${r.error || 'échec'}`;
      result.style.color = 'var(--red)';
    }
  }catch(e){
    result.textContent = `❌ Serveur injoignable : ${e.message}`;
    result.style.color = 'var(--red)';
  }
}

function _mysqlFieldsFromForm(){
  return {
    host: document.getElementById('mysql_host').value.trim(),
    port: parseInt(document.getElementById('mysql_port').value, 10) || 3306,
    user: document.getElementById('mysql_user').value.trim(),
    password: document.getElementById('mysql_password').value,
    database: document.getElementById('mysql_database').value.trim(),
  };
}

async function testMysqlConnection(){
  const result = document.getElementById('mysqlTestResult');
  const f = _mysqlFieldsFromForm();
  if (!f.host || !f.database){
    result.textContent = '⚠️ Adresse et base de données requises';
    result.style.color = 'var(--yellow)';
    return;
  }
  result.textContent = '⏳ Test en cours...';
  result.style.color = 'var(--muted)';
  try{
    const res = await fetch('/mysql/test', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(f)});
    const r = await res.json();
    if (r.ok){
      result.textContent = `✅ Connecté (${r.qso_count} QSO déjà partagés)`;
      result.style.color = 'var(--green)';
    } else {
      result.textContent = `❌ ${r.error || 'Échec'}`;
      result.style.color = 'var(--red)';
    }
  }catch(e){
    result.textContent = `❌ Serveur injoignable : ${e.message}`;
    result.style.color = 'var(--red)';
  }
}

async function mysqlSyncNow(){
  const result = document.getElementById('mysqlTestResult');
  result.textContent = '⏳ synchronisation en cours…';
  result.style.color = 'var(--muted)';
  try{
    // Même motif que cloudsyncNow() (correctif M6) : les champs saisis mais
    // pas encore enregistrés priment sur la config sauvegardée.
    const f = _mysqlFieldsFromForm();
    const res = await fetch('/mysql/now', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        mysql_mode: document.getElementById('mysql_mode').value,
        mysql_host: f.host, mysql_port: f.port, mysql_user: f.user,
        mysql_password: f.password, mysql_database: f.database,
      })});
    const r = await res.json();
    if (r.ok){
      result.textContent = `✅ ${r.pushed} QSO envoyés · ${r.pulled} récupérés`;
      result.style.color = 'var(--green)';
    } else {
      result.textContent = `❌ ${r.error || 'échec'}`;
      result.style.color = 'var(--red)';
    }
  }catch(e){
    result.textContent = `❌ Serveur injoignable : ${e.message}`;
    result.style.color = 'var(--red)';
  }
}
