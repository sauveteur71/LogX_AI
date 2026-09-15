// EV-7 (découpage logx_logbook.js, 14/09/2026) : QUESTIONS SUR LE CARNET (C1)
// -- extrait de logx_logbook.js. Charge en <script> classique dans
// logx_logbook.html, portee globale partagee.
//
// Candidat vérifié SANS ambiguïté avant extraction : aucune fonction/variable
// de ce bloc n'est atteignable depuis submitQSO()/renderLog()/autoFillQso()
// (chemin critique du carnet, analyse d'appels faite avant tout déplacement)
// -- contrairement au moteur de filtres avancés (matchesAdvancedFilter, resté
// dans logx_logbook.js exprès, voir son commentaire) et validateLocator()
// (appelée sans garde dans submitQSO()), qui eux ne doivent PAS être déplacés.
// Aucun autre fichier du dépôt ne référence carnetHistorique/poserQuestion*
// -- seul logx_logbook.html (boutons du panneau) en dépend.

// ─── QUESTIONS SUR LE CARNET (C1) ────────────────────────────────────────────
// docs/superpowers/specs/2026-09-11-c1-requetes-langage-naturel-carnet.md.
// Boutons rapides (incr. 1) : 0 jeton, 0 appel LLM. Question libre
// (incr. 2) : palier IA si aucun motif fixe ne matche côté serveur.
// Historique multi-tour (incr. 3, 12/09/2026) : le CLIENT porte
// carnetHistorique -- même patron que conversationHistory de Carte IA
// (logx_carte.html), mais sans persistance localStorage (portée : la
// session de page en cours, remise à zéro explicite via le bouton dédié).
// Le serveur reste sans état -- il revalide/borne cet historique à chaque
// appel (logx_carnet_questions.valider_historique), jamais une confiance
// aveugle dans ce qu'envoie le client. Dans tous les cas la réponse est du
// texte simple assignée via textContent, jamais innerHTML -- rien à
// composer côté client.
let carnetHistorique = [];
const CARNET_HISTORIQUE_MAX = 20;   // 10 tours -- même borne que le serveur

function showCarnetQuestions(){
  const ov = document.getElementById('carnetQuestionsOverlay');
  if(!ov) return;
  ov.classList.add('show');
}
function closeCarnetQuestions(){
  const ov = document.getElementById('carnetQuestionsOverlay');
  if(ov) ov.classList.remove('show');
}

async function poserQuestionCarnet(topic){
  const box = document.getElementById('qcReponse');
  if(!box) return;
  box.className = 'qc-reponse';
  box.textContent = 'Recherche…';
  const params = new URLSearchParams({topic: topic});
  if(topic === 'deja_travaille'){
    const input = document.getElementById('qcIndicatifInput');
    params.set('indicatif', (input && input.value || '').trim());
  }
  try{
    const r = await fetch('/log/question?' + params.toString());
    const d = await r.json();
    if(!d.ok){
      box.className = 'qc-reponse qc-erreur';
      box.textContent = d.error || 'Question sans réponse.';
      return;
    }
    box.textContent = d.reponse;
  }catch(e){
    box.className = 'qc-reponse qc-erreur';
    box.textContent = trT('Serveur injoignable — réessaie.');
  }
}

// ─── Question libre (C1, incréments 2 et 3) ─────────────────────────────────
// Aucun motif fixe reconnu côté serveur -> palier IA (jeton). POST (pas
// GET) depuis l'incr. 3 : porte carnetHistorique, une forme impraticable en
// query string. Même réponse texte assignée via textContent que
// poserQuestionCarnet() ci-dessus.
async function poserQuestionLibreCarnet(){
  const input = document.getElementById('qcLibreInput');
  const texte = (input && input.value || '').trim();
  if(!texte) return;
  const box = document.getElementById('qcReponse');
  if(!box) return;
  box.className = 'qc-reponse';
  box.textContent = 'Recherche… (appel IA, ça peut prendre quelques secondes)';
  try{
    const r = await fetch('/log/question', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({texte: texte, historique: carnetHistorique})
    });
    const d = await r.json();
    if(!d.ok){
      box.className = 'qc-reponse qc-erreur';
      box.textContent = d.error || 'Question sans réponse.';
      return;
    }
    box.textContent = d.reponse;
    input.value = '';
    // Seul un vrai tour IA alimente la conversation -- une réponse
    // déterministe (topic !== 'ia', ex. "déjà travaillé" reconnu dans le
    // texte libre) n'a pas de raison de peser sur le contexte multi-tour.
    if(d.topic === 'ia'){
      carnetHistorique.push({role: 'user', content: texte});
      carnetHistorique.push({role: 'assistant', content: d.reponse});
      if(carnetHistorique.length > CARNET_HISTORIQUE_MAX){
        carnetHistorique = carnetHistorique.slice(-CARNET_HISTORIQUE_MAX);
      }
    }
    majIndicateurConversationCarnet();
  }catch(e){
    box.className = 'qc-reponse qc-erreur';
    box.textContent = trT('Serveur injoignable — réessaie.');
  }
}

function reinitialiserConversationCarnet(){
  carnetHistorique = [];
  majIndicateurConversationCarnet();
}

// Visibilité de l'état de conversation -- intuitivité : sans indice, rien
// ne dit à l'opérateur qu'une question de suivi ("et en CW ?") va réutiliser
// le contexte précédent plutôt que repartir de zéro.
function majIndicateurConversationCarnet(){
  const btn = document.getElementById('qcResetBtn');
  if(!btn) return;
  const tours = carnetHistorique.length / 2;
  btn.hidden = tours === 0;
  btn.textContent = tours > 0
    ? 'Nouvelle conversation (' + tours + ' tour' + (tours > 1 ? 's' : '') + ')'
    : '';
}
