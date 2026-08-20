// Puissance TX automatique par mode — protection du final en numérique.
//
// POURQUOI CE FICHIER EXISTE. La règle vivait dans logx_logbook.js, et n'était
// donc appliquée QUE depuis le sélecteur de bande/mode du LOGBOOK. Or c'est la
// page FT8 qui émet réellement en FT8 : un opérateur qui ouvre
// MODE NUMÉRIQUE → FT8 directement — le chemin naturel — n'avait AUCUNE des
// deux protections qu'il croyait avoir. Son poste restait sur son réglage
// phonie, et chaque créneau partait à cette puissance-là en porteuse à rapport
// cyclique 100 % pendant 12,6 s, exactement ce que le réglage existe pour
// éviter. Le libellé de CONFIG disait d'ailleurs « quand tu choisis un mode
// numérique dans LOGBOOK », ce qui décrivait fidèlement le code — et ne
// correspondait pas à ce qu'un opérateur comprend par « protection du final ».
//
// La table des modes et les clés de configuration ne doivent exister QU'ICI :
// deux copies divergent au premier mode ajouté, et la divergence serait
// invisible (un mode oublié d'un côté n'émet aucune erreur, il laisse
// simplement passer la pleine puissance).
//
// TOUT EST DÉSACTIVÉ PAR DÉFAUT : rien n'est poussé tant que l'opérateur n'a
// pas coché la protection dans CONFIG. Repli sûr à chaque étape — réglage
// décoché, configuration jamais enregistrée sur ce poste, ou champ de
// puissance vide : on ne touche à rien. Un champ vide ne doit JAMAIS se
// traduire par 0 W poussé sur l'air.
(function(){
  'use strict';

  // Reprend la même famille que MODES_NUMERIQUES (logx_cat.py,
  // normaliser_mode) plutôt que d'inventer une 3e liste ; RTTY y figure bien
  // qu'il ait sa propre table de conversion CAT côté serveur
  // (MODE_RTTY_PAR_MARQUE) — il reste, comme FT8/FT4, un mode à 100 % de cycle
  // de service, concerné par la protection du final au même titre.
  const MODES_NUMERIQUES_PUISSANCE = new Set([
    'FT8', 'FT4', 'FT2', 'RTTY', 'PSK', 'PSK31', 'PSK63', 'JS8', 'JS8CALL',
    'MSK144', 'Q65', 'JT65', 'JT9', 'MFSK', 'OLIVIA', 'DIGI', 'DATA', 'DIGITAL',
  ]);

  function _config(){
    try{ return JSON.parse(localStorage.getItem('logx_config') || '{}'); }
    catch(e){ return {}; }
  }

  // Watts à pousser pour ce mode, ou 0 si on ne doit RIEN pousser.
  // Renvoyer 0 plutôt que null garde un seul test à faire chez l'appelant, et
  // 0 ne peut pas être confondu avec une consigne valable : une puissance
  // nulle n'est jamais un réglage voulu.
  function puissanceVoulueW(mode){
    const cfg = _config();
    if(!cfg.cat_power_auto_enabled) return 0;
    const numerique = MODES_NUMERIQUES_PUISSANCE.has(String(mode || '').toUpperCase());
    const brut = numerique ? cfg.cat_power_digital_w : cfg.cat_power_phone_w;
    const watts = parseInt(brut, 10);
    return (watts > 0) ? watts : 0;
  }

  // Pousse la puissance vers la radio et REND COMPTE : {demande, applique,
  // erreur}. L'appelant peut donc le dire à l'opérateur au lieu de le laisser
  // croire à une protection qui n'a pas eu lieu — c'est exactement le point
  // qui manquait, l'ancienne version partant en `fetch().catch(()=>{})`.
  //
  // Le refus n'a rien d'exceptionnel, il est même le cas le plus courant :
  // cat.set_power() (logx_cat.py) refuse explicitement Icom/Xiegu, parce que
  // la seule commande CI-V de puissance règle un NIVEAU RELATIF 0-100 % et non
  // des watts, et que la correspondance dépend du plafond « RF POWER » du menu
  // de chaque poste. Il refuse aussi tout mode CAT autre que le pilotage
  // natif. Le serveur répond alors 400 avec un message explicite : ce message
  // doit remonter jusqu'à l'écran, sinon l'opérateur d'un IC-7300 croit son
  // final protégé alors que rien n'a été envoyé.
  function appliquerPuissanceAuto(mode){
    const watts = puissanceVoulueW(mode);
    if(!watts) return Promise.resolve({demande: 0, applique: 0, erreur: ''});
    return fetch('/rig/set_power', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({watts: watts})
    }).then(function(r){
      return r.json().catch(function(){ return {}; }).then(function(d){
        if(r.ok && d && d.ok){
          return {demande: watts, applique: (d.watts || watts), erreur: ''};
        }
        return {demande: watts, applique: 0,
                erreur: (d && d.error) || 'la radio n\'a pas confirmé'};
      });
    }).catch(function(){
      return {demande: watts, applique: 0, erreur: 'serveur injoignable'};
    });
  }

  window.MODES_NUMERIQUES_PUISSANCE = MODES_NUMERIQUES_PUISSANCE;
  window.puissanceVoulueW = puissanceVoulueW;
  window.appliquerPuissanceAuto = appliquerPuissanceAuto;
})();
