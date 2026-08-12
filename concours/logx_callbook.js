// EV-7 phase 2, 16e increment (docs/LogX_AI_PRD.md) -- fiche CALLBOOK a la
// frappe (QRZ/HamQTH/HamDB, statut a la frappe, historique "deja contacte")
// extrait tel quel de logx_logbook.js (extraction MECANIQUE). Charge en
// <script> classique dans logx_logbook.html, AVANT logx_logbook.js (portee
// globale partagee).
//
// Etat interne prive au bloc (grep exhaustif sur tout le depot) :
// _checkTimer/_checkSeq, _qrzTimer/_qrzSeq, _stateAnnuaire,
// CALLBOOK_SOURCE_LABEL, _prevTimer/_prevSeq -- SAUF _stateAnnuaire, lu (pas
// ecrit) depuis submitQSO() dans logx_logbook.js (reste dans ce fichier),
// portee globale partagee, corps de fonction uniquement -- sans risque
// d'ordre de <script>.
//
// 3 points d'entree, tous appeles depuis logx_logbook.js (jamais cables en
// HTML directement) : lookupQRZ(call)/checkCallStatus(call)/
// checkPrevQsos(call), tous les 3 appeles ensemble a la frappe de
// l'indicatif (onLocatorInput()/oninput du champ indicatif, reste dans
// logx_logbook.js).
//
// fmtDate(d) est aussi consommee par logx_awards.js (deja un fichier EV-7
// extrait, 4e increment) -- portee globale partagee, uniquement a
// l'interieur de corps de fonction cote logx_awards.js, ordre de <script>
// entre les deux fichiers extraits sans importance.

// ─── STATUT À LA FRAPPE (serveur) ────────────────────────────────────────────
// GET /log/check : nouveau / doublon / nouveau_mult, évalué par le MOTEUR DE
// SCORING contre le log partagé multi-op (pas seulement le log local).
let _checkTimer = null;
let _checkSeq = 0;

// ─── FICHE CALLBOOK (à la frappe) ────────────────────────────────────────────
// Affiche nom / QTH / locator du correspondant, en cascade QRZ (si identifiants
// configurés) -> HamQTH -> HamDB (côté serveur, logx_callbook.py).
// Debounce plus long (600 ms) : une requête réseau par indicatif fini.
let _qrzTimer = null, _qrzSeq = 0;
// Dernier état US rapporté par l'annuaire, avec l'indicatif auquel il se
// rapporte ({call, state}). L'indicatif est conservé À DESSEIN : la réponse
// arrive en différé, et sans cette vérification l'état d'une station
// précédente se retrouverait collé au QSO en cours de saisie.
let _stateAnnuaire = null;
const CALLBOOK_SOURCE_LABEL = {hamqth: 'HamQTH', hamdb: 'HamDB'};  // QRZ = pas de tag (source par défaut)

function lookupQRZ(call){
  clearTimeout(_qrzTimer);
  const row = document.getElementById('qrzInfoRow');
  const el = document.getElementById('qrzInfo');
  const photo = document.getElementById('qrzPhoto');
  if(!el || !row) return;
  if(!call || call.length < 3){ row.style.display = 'none'; return; }
  const seq = ++_qrzSeq;
  _qrzTimer = setTimeout(async () => {
    try{
      const r = await fetch('/qrz/lookup?call=' + encodeURIComponent(call));
      if(!r.ok || seq !== _qrzSeq) return;
      const d = await r.json();
      if(!d.ok){ row.style.display = 'none'; return; }
      // Données d'annuaires en ligne tiers (QRZ/HamQTH/HamDB) : origine Internet
      // hors du contrôle de l'utilisateur → échappées avant insertion en innerHTML
      // (un champ QTH contenant du HTML exécuterait sinon du script à la frappe).
      const bits = [];
      if(d.name) bits.push('👤 ' + escHtml(d.name));
      if(d.qth)  bits.push('📍 ' + escHtml(d.qth));
      if(d.grid) bits.push('🗺 ' + escHtml(d.grid));
      if(d.country && !d.qth) bits.push(escHtml(d.country));
      const sourceLabel = CALLBOOK_SOURCE_LABEL[d.source];
      if(sourceLabel) bits.push('· ' + escHtml(sourceLabel));
      el.innerHTML = bits.join(' · ');
      // Photo (QRZ uniquement, comptes abonnés) : `.src` n'exécute jamais de
      // script même sur une URL malveillante, mais on revérifie quand même le
      // schéma ici — défense en profondeur, le serveur (logx_qrz.py) filtre déjà.
      if(photo){
        if(d.image && /^https?:\/\//i.test(d.image)){
          photo.onerror = () => { photo.style.display = 'none'; };   // lien mort (ex. QRZ ayant retiré la fiche depuis)
          photo.src = d.image;
          photo.style.display = 'block';
        } else {
          photo.style.display = 'none';
          photo.src = '';
        }
      }
      row.style.display = (bits.length || (photo && photo.style.display === 'block')) ? 'flex' : 'none';
      // Pré-remplit le locator s'il est vide et que la source en connaît un
      const locInput = document.getElementById('inputLocator');
      if(locInput && !locInput.value && d.grid && d.grid.length >= 4){
        locInput.value = d.grid;
        onLocatorInput();
      }
      // État US retenu pour le QSO : c'est la SEULE source à la saisie, l'état
      // ne se déduisant pas de l'indicatif (un W6 peut habiter n'importe où).
      // Mémorisé avec l'indicatif auquel il se rapporte : sans ça, un état
      // resté d'une frappe précédente serait recopié sur le QSO suivant.
      _stateAnnuaire = (d.state && /^[A-Z]{2}$/.test(String(d.state).toUpperCase()))
        ? {call: call, state: String(d.state).toUpperCase()} : null;
    }catch(e){ /* réseau callbook indispo : rien */ }
  }, 600);
}

function checkCallStatus(call){
  clearTimeout(_checkTimer);
  const badge = document.getElementById('callStatusBadge');
  if(!badge) return;
  if(!call || call.length < 3){ badge.style.display = 'none'; return; }
  const seq = ++_checkSeq;
  _checkTimer = setTimeout(async () => {
    try{
      const r = await fetch(`/log/check?call=${encodeURIComponent(call)}` +
                            `&band=${encodeURIComponent(currentBand || '')}` +
                            `&mode=${encodeURIComponent(currentMode || '')}`);
      if(!r.ok || seq !== _checkSeq) return;   // réponse périmée : ignorer
      const st = await r.json();
      if(st.status === 'inconnu'){ badge.style.display = 'none'; return; }
      const styles = {
        doublon:      ['⚠️ DOUBLON sur cette bande', 'var(--red)'],
        nouveau_mult: ['📈 NOUVEAU MULTIPLICATEUR' + (st.mult_type ? ' (' + st.mult_type + ')' : ''), 'var(--green)'],
        nouveau:      ['✔ nouveau' + (st.points ? ' · ' + st.points + ' pt' + (st.points > 1 ? 's' : '') : ''), 'var(--accent2)'],
      };
      const [txt, col] = styles[st.status] || styles.nouveau;
      badge.textContent = txt;
      badge.style.color = col;
      badge.style.border = '1px solid ' + col;
      badge.style.display = 'block';
      badge.title = st.explanation || '';
    }catch(e){ /* hors ligne : badge local dupWarn suffit */ }
  }, 250);
}

// ─── « DÉJÀ CONTACTÉ » (historique station, tous concours) ───────────────────
// À la frappe d'un indicatif, montre tous les QSO passés avec cette station
// (dates, bandes, confirmé LoTW) + alerte « NOUVEAU PAYS/DÉPARTEMENT » à vie —
// façon fiche « previous contacts » de Log4OM / HRD.
let _prevTimer = null, _prevSeq = 0;

function checkPrevQsos(call){
  clearTimeout(_prevTimer);
  const el = document.getElementById('prevQsos');
  if(!el) return;
  if(!call || call.length < 3){ el.style.display = 'none'; return; }
  const seq = ++_prevSeq;
  _prevTimer = setTimeout(async () => {
    try{
      const r = await fetch(`/call/history?call=${encodeURIComponent(call)}` +
                            `&band=${encodeURIComponent(currentBand || '')}` +
                            `&mode=${encodeURIComponent(currentMode || '')}`);
      if(!r.ok || seq !== _prevSeq) return;
      const d = await r.json();
      const parts = [];
      // Alerte « nouveau à vie » (pays / département jamais contacté)
      (d.new_one || []).forEach(n => {
        parts.push(`<div style="color:var(--green);font-weight:700">🌟 ${n.label}</div>`);
      });
      // Besoin LoTW : « pas confirmé LoTW » n'est PAS « jamais contacté ». Un
      // pays travaillé dix fois mais jamais confirmé ne compte toujours pas
      // pour le DXCC — et une confirmation eQSL ou papier n'y change rien.
      // L'entité jamais confirmée nulle part passe en rouge : c'est celle qui
      // fait avancer le compteur.
      if(d.lotw_need && d.lotw_need.besoin){
        const jamais = d.lotw_need.raison === 'jamais_confirme';
        parts.push(`<div style="color:${jamais ? 'var(--red)' : 'var(--accent2)'};font-weight:700">` +
                   `${jamais ? '📛' : '📻'} ${escHtml(d.lotw_need.label)}</div>`);
      }
      // État US / province canadienne, quand on la connaît (même champ ADIF
      // STATE des deux côtés de la frontière).
      if(d.state){
        parts.push(`<div style="color:var(--muted)">🏛 ${escHtml(d.state)}</div>`);
      }
      // Utilisateur LoTW. Décisif juste au-dessus de l'alerte « pas confirmé
      // LoTW » : si le correspondant n'uploade pas, le créneau ne se comblera
      // jamais avec lui. `undefined`/null = liste pas encore téléchargée, on
      // n'affiche RIEN plutôt que d'annoncer « n'utilise pas LoTW » à tort.
      if(d.lotw_user === true){
        const depuis = d.lotw_last ? ` · dernier envoi ${escHtml(d.lotw_last)}` : '';
        parts.push(`<div style="color:var(--green)">✅ LoTW${depuis}</div>`);
      } else if(d.lotw_user === false){
        parts.push(`<div style="color:var(--muted)">🚫 pas sur LoTW — ne sera jamais confirmé</div>`);
      }
      if(d.count > 0){
        const conf = d.confirmed ? ` · <span style="color:var(--green)">${d.confirmed} confirmé${d.confirmed>1?'s':''}</span>` : '';
        const bands = d.bands && d.bands.length ? ` sur ${escHtml(d.bands.join('/'))} MHz` : '';
        parts.push(`<div><b style="color:var(--accent2)">${d.count} QSO</b>${bands}${conf}` +
                   (d.last ? ` · dernier ${fmtDate(d.last)}` : '') + '</div>');
        // Les 3 plus récents
        d.qsos.slice(0,3).forEach(q => {
          parts.push(`<div style="opacity:.75">${fmtDate(q.date)} — ${escHtml(q.band)} MHz ${escHtml(q.mode)}` +
                     `${q.contest ? ' · ' + escHtml(q.contest.replace(/_/g,' ')) : ''}` +
                     `${q.confirmed ? ' ✅' : ''}</div>`);
        });
      } else if(!(d.new_one||[]).length){
        parts.push(`<span style="color:var(--muted)">jamais contacté</span>`);
      }
      el.innerHTML = parts.join('');
      el.style.display = parts.length ? 'block' : 'none';
    }catch(e){ el.style.display = 'none'; }
  }, 350);
}

function fmtDate(d){
  d = String(d || '');
  return d.length === 8 ? `${d.slice(6,8)}/${d.slice(4,6)}/${d.slice(0,4)}` : d;
}
