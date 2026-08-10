// Raccourcis i18n (fournis par logx_i18n.js ; repli = identite si absent).
// Le moteur traduit tout ce qui passe par le DOM, mais PAS alert/confirm/
// prompt : ces textes ne sont jamais des noeuds. Tf remplace les trous {x}
// APRES traduction — indispensable des qu'une phrase porte une valeur.
const T = s => (window.rcT ? window.rcT(s) : s);
const Tf = (s, p) => (window.rcTf ? window.rcTf(s, p) : (function(){
  let o = s; for(const k in (p || {})) o = o.split('{' + k + '}').join(p[k]); return o;
})());
// Base locale : {id du champ -> explication en clair}. C'EST la première ligne
// d'aide (aucun réseau requis) ; la question libre de l'assistant y cherche
// aussi une correspondance avant, éventuellement, de solliciter l'IA.
const CONFIG_HELP = {
  callsign: "Ton indicatif radioamateur personnel (ex. F4GLD). C'est ton identité de base : il sert notamment à retrouver ton pays/zone automatiquement.",
  callsign_contest: "L'indicatif que tu émets réellement pendant CE concours, s'il diffère de ton indicatif personnel (ex. indicatif de club, ou /P si tu émets en portable depuis un autre pays comme EA/F4GLD). Laisse vide pour reprendre ton indicatif normal.",
  locator: "Ta position exprimée en grille Maidenhead (6 caractères, ex. JN15XC). Sert à calculer les distances et les directions d'antenne. Utilise le bouton « 📍 Sur la carte » si tu ne le connais pas par cœur.",
  city: "Ta ville/QTH, affichée dans les résumés et sur l'écran mural. Purement informatif, n'affecte pas le scoring.",
  altitude: "Ton altitude en mètres. Utile pour le Rallye des Points Hauts et pour affiner les prédictions de propagation troposphérique.",
  power: "Ta puissance d'émission en watts. Utilisée pour le calcul de certains bonus/catégories (ex. QRP).",
  power_class: "Ta catégorie de puissance déclarée pour le concours (HP=haute puissance, LP=basse puissance, QRP/QRP10/QRP15=très faible puissance selon ton palier). Certains concours notent différemment selon la catégorie. Dans l'export Cabrillo, les 3 paliers QRP sont tous déclarés comme la catégorie standard « QRP ».",
  active_satellite: "Le satellite via lequel tu opères actuellement — repère informatif uniquement, n'affecte ni le score ni le filtrage des bandes (ça reste les cases QO-100/Autres SAT ci-dessus). Utile en fin de saison pour te souvenir de tes sorties.",
  operator_name: "Ton prénom/nom, utilisé dans les exports (ADIF/Cabrillo) et certains formulaires de diplômes.",
  email: "Ton adresse email, utilisée pour certains envois de log automatiques (ex. soumission de concours) si le concours le demande.",
  club: "Le nom de ton club radioamateur, s'il y a lieu — apparaît dans certains exports Cabrillo.",
  op_call: "L'indicatif de la personne responsable du log si elle diffère de l'opérateur principal (utile en multi-opérateurs) — repris dans les champs RCall/MOpe1 de l'export EDI.",
  postal: "Ton code postal — les deux premiers chiffres identifient ton département, affiché dans l'en-tête du logbook.",

  usage_mode: "Détermine le fonctionnement général du logiciel : LOGBOOK SIMPLE (trafic courant, un seul opérateur, pas de règles de concours), CONCOURS (scoring/règlement actifs), EXPÉDITION (pile-up, multi-poste), ou RADIOCLUB (déclaration des postes radio physiques, pour un club où plusieurs membres se relaient). Sauf en LOGBOOK SIMPLE, mono-opérateur par conception, tous les modes acceptent jusqu'à 40 opérateurs : une DXpédition à 10 n'a AUCUNE raison de passer en RADIOCLUB. Change ce réglage si l'étape CONCOURS te paraît hors sujet. L'écran mural (section ci-dessous) n'est PAS réservé au mode EXPÉDITION : il fonctionne dans n'importe quel mode, même seul — pratique pour suivre les QSO depuis une autre pièce.",
  expedition_mode: "Active les fonctions pensées pour une sortie DXpédition/SOTA/POTA en groupe : écran mural partagé, synchronisation multi-poste, statistiques de pile-up.",
  activation_program: "Le programme concerné si tu opères depuis une référence (SOTA, POTA, WWFF, châteaux...). Permet d'afficher les bons outils pour ce programme.",
  my_activation_ref: "La référence précise du site d'où tu opères (ex. un code SOTA ou POTA), affichée sur l'écran mural et dans les exports.",
  wall_qso_goal: "Objectif de QSO TOTAL pour la session/l'événement en cours (ex. « en route vers 10 000 QSO »), affiché sous forme de barre de progression sur l'écran mural — distinct de l'objectif QSO/heure affiché dans la barre de statut. Laisse à 0 pour ne pas afficher cette barre.",

  contest_start_date: "Date de début du concours choisi (remplie automatiquement dès que tu sélectionnes un concours dans l'étape 2, sauf réglage personnalisé).",
  contest_end_date: "Date de fin du concours — sert au compte à rebours affiché en permanence et au contrôle « QSO hors fenêtre » du bouton VÉRIFIER.",
  contest_end_utc: "Heure de fin exacte en UTC (temps universel, pas ton heure locale) — les concours radioamateur se règlent presque toujours sur UTC.",
  submit_deadline: "La date limite d'envoi de ton log au concours — purement informatif, pense à noter un rappel !",
  submit_url: "Le lien vers lequel envoyer ton log une fois le concours terminé (site officiel de soumission).",
  log_software: "Uniquement si tu fais dialoguer LogX AI en réseau avec un AUTRE logiciel de log (pont ADIF/EDI) — choisis le format de CET autre logiciel. Laisse « Aucun — LogX AI seul » si tu n'utilises que LogX AI, c'est le réglage par défaut.",
  section_edi: "Le code de section utilisé dans l'export EDI (format suisse USKA) — laisse vide si le concours n'en a pas besoin.",
  radio: "Le modèle de ton transceiver (ex. IC-9700, FT-991A) — purement informatif, affiché dans les résumés de station et repris dans l'export EDI.",
  country: "Le code pays ISO 3 lettres de ta station (ex. FRA pour la France) — déduit automatiquement de ton indicatif, modifiable si besoin. Repris dans l'export EDI/Cabrillo.",
  ant_hf: "Description libre de ton antenne HF (ex. Dipôle 40m, Vertical, Yagi 3 éléments) — purement informative, affichée dans les résumés de station.",
  ant_144: "Description libre de ton antenne 144 MHz (ex. Yagi 9 éléments) — reprise dans l'export EDI.",
  ant_432: "Description libre de ton antenne 432 MHz (ex. Yagi 21 éléments) — reprise dans l'export EDI.",
  ant_shf: "Description libre de ton antenne UHF/SHF (ex. parabole 60cm) — purement informative, affichée dans les résumés de station.",

  priority_mode: "Comment le logiciel classe les stations à contacter : par distance (les plus lointaines d'abord) ou par valeur de points/multiplicateur. Change l'ordre affiché dans la « need list ».",
  alert_dx_km: "Distance (km) au-delà de laquelle une station spottée est considérée comme un DX exceptionnel à signaler en priorité. L'assistant IA ajuste déjà ce seuil AUTOMATIQUEMENT selon la bande de chaque spot (HF ≈ milliers de km, VHF/UHF/SHF ≈ centaines à dizaines de km, propagation très différente) — cette valeur ne sert que de repli pour une bande sans seuil dédié.",
  spotter_reliable_km: "Distance de fiabilité d'un spotteur : au-delà, une info venant d'un cluster lointain est traitée avec plus de prudence. Comme pour l'alerte DX, l'assistant IA applique déjà un seuil différent par bande automatiquement — cette valeur est le repli pour une bande non couverte.",
  spot_prefix_filter: "Liste de préfixes séparés par des virgules (ex. K,VE,W) pour ne garder QUE les spots de ces pays/préfixes dans la need list — utile pour un concours ciblé (ex. ARRL Field Day).",

  cluster_spot_enabled: "Active la réception des spots DX en direct depuis un cluster telnet (annonces d'autres opérateurs sur les stations entendues).",
  cluster_spot_host: "Adresse du serveur de cluster DX à utiliser (ex. dxc.ref-union.org). Demande à ton club ou cherche « DX cluster telnet » si tu n'en as pas.",
  cluster_spot_port: "Port réseau du cluster DX — généralement 7300, indiqué par le fournisseur du cluster.",
  rbn_enabled: "Active le Reverse Beacon Network : un réseau mondial de récepteurs qui te signale automatiquement où et comment ton signal CW est entendu.",

  cat_enabled: "Active le pilotage direct de la radio (lecture fréquence/mode, bascule émission) depuis le logiciel.",
  cat_mode: "Choisis comment le logiciel parle à ta radio : NATIF (câble série direct, sans logiciel intermédiaire), TCI (protocole réseau moderne type SunSDR/ExpertSDR), RIGCTLD (passe par le standard Hamlib, compatible presque toutes les radios), FLRIG (autre pilote CAT réseau, courant sous Linux/fldigi), OMNIRIG (composant COM Windows, avancé — lecture/écriture complètes), FLEXRADIO (API réseau native SmartSDR — lecture + PTT seulement), ou ICOM RÉSEAU (IC-705/7610/905, pas encore disponible).",
  cat_brand: "La marque de ta radio pour le mode NATIF (Icom, Yaesu, Kenwood, Elecraft...) — détermine le protocole exact utilisé.",
  cat_model: "Le modèle précis de ta radio, pour affiner l'adresse/le protocole (notamment important pour Icom en CI-V).",
  cat_port: "Le port série (COM) où ta radio est reliée à l'ordinateur (ex. COM3 sous Windows). Visible dans le Gestionnaire de périphériques Windows. Interface multi-radio (microHAM, 4O3A Signature...) : c'est le port COM VIRTUEL que le logiciel de l'interface (ex. microHAM Router / USB Device Router) crée pour LogX AI — il ne fonctionne que si ce logiciel tourne, avec la bonne radio sélectionnée dedans. Ce port peut être différent de celui utilisé par WSJT-X ou un autre logiciel, et il change parfois après un redémarrage : rafraîchis la liste si besoin.",
  cat_baudrate: "La vitesse de communication série (bauds) réglée sur ta radio elle-même — doit correspondre EXACTEMENT au réglage du menu de la radio.",
  cat_civ_addr: "Adresse CI-V (Icom/Xiegu) — laisse vide pour utiliser l'adresse usine du modèle choisi. À remplir seulement si tu as changé cette adresse dans le menu SET de la radio (pratique courante en multi-poste/SO2R pour éviter les collisions sur le bus CI-V) : sans ça, LogX AI continue d'interroger l'ancienne adresse et la radio ne répond jamais.",
  rig_host: "Adresse réseau (souvent 127.0.0.1 si sur le même PC) du serveur rigctld qui pilote ta radio via Hamlib.",
  rig_port: "Port réseau de rigctld — 4532 par défaut.",
  tci_host: "Adresse réseau du serveur TCI (ex. ExpertSDR3) qui pilote ta radio — 127.0.0.1 si sur le même PC.",
  tci_port: "Port réseau du serveur TCI — vérifie ce port dans les réglages de ton logiciel SDR.",
  flrig_host: "Adresse réseau (souvent 127.0.0.1 si sur le même PC) du serveur XML-RPC de flrig qui pilote ta radio.",
  flrig_port: "Port réseau du serveur XML-RPC de flrig — 12345 par défaut.",

  cat2_enabled: "Active une DEUXIÈME radio pilotée en parallèle (opération SO2R — Single Operator 2 Radios). Laisse désactivé si tu n'opères qu'avec une seule radio.",
  cat2_mode: "Comment le logiciel parle à la RADIO 2 : NATIF (câble série direct) ou OMNIRIG (composant COM Windows). Le CAT natif série ne peut piloter qu'une radio à la fois par connexion — OmniRig est la voie recommandée pour la radio 2 tant qu'aucun boîtier OTRSP n'impose le CAT natif dual.",
  cat2_brand: "La marque de la RADIO 2 (Icom, Yaesu, Kenwood, Elecraft, Xiegu) — utilisé en mode NATIF uniquement.",
  cat2_port: "Le port série (COM) où la RADIO 2 est reliée à l'ordinateur — doit être différent du port de la radio 1.",
  cat2_baudrate: "La vitesse de communication série de la RADIO 2 — doit correspondre au réglage du menu de cette radio.",
  cat2_omnirig_rig_num: "Le numéro de radio configuré côté OmniRig pour la RADIO 2 (Rig1 ou Rig2) — différent de celui choisi pour la radio 1 (fenêtre OmniRig → onglet Rig1/Rig2).",
  voicekeyer_device2: "Le périphérique audio par lequel sort le keyer vocal (CQ/report dits par synthèse) quand la RADIO 2 a l'émission. Laisse vide pour réutiliser le même périphérique que la radio 1.",
  so2r_enabled: "Indique si un boîtier OTRSP (microHAM, YCCC, EA4TX...) est branché pour commuter automatiquement émission et audio entre les deux radios SO2R. Sans lui, la bascule reste logicielle (Ctrl+Espace) et tu rebranches le casque à la main.",
  so2r_port: "Le port série (COM) où le boîtier OTRSP est relié à l'ordinateur.",
  so2r_stereo: "Comment le boîtier OTRSP répartit l'écoute entre les deux radios : STÉRÉO (une oreille sur chaque radio en permanence) ou MONO (l'écoute suit la radio qui a l'émission).",
  winkeyer_enabled: "Active un boîtier WinKeyer (K1EL) branché sur son propre port série pour la manipulation CW — prend la main sur l'envoi CW quelle que soit la marque de radio. C'est la SEULE manipulation CW possible en Icom et en Yaesu (leur protocole CAT ne publie pas de commande d'envoi de texte).",
  winkeyer_port: "Le port série (COM sous Windows, /dev/ttyUSBx sous Linux) où le WinKeyer est relié à l'ordinateur.",
  winkeyer_wpm: "La vitesse d'envoi CW en mots par minute — se règle ICI et non sur la radio quand le WinKeyer est activé.",

  amp_enabled: "Active le pilotage de ton amplificateur linéaire (lecture de puissance/ROS, bascule standby/émission) depuis le logiciel.",
  amp_brand: "La marque de ton amplificateur (Elecraft, Icom, SPE...) — détermine le protocole de communication utilisé.",
  amp_port: "Le port série (COM) où ton amplificateur est relié à l'ordinateur.",
  amp_baudrate: "La vitesse de communication série réglée sur ton amplificateur.",
  amp_civ_addr: "L'adresse CI-V de l'ampli (pour les modèles compatibles Icom) — vérifie dans le menu de l'ampli si besoin de la changer.",
  amp_conn_mode: "Le KPA1500 (pas le KPA500) a un port Ethernet natif : tu peux le piloter en réseau (TCP ou UDP) au lieu du port série USB. Mêmes commandes, juste un autre chemin — utile si l'ampli est loin du PC ou déjà relié à ton réseau local.",
  amp_host: "L'adresse IP du KPA1500 sur ton réseau (visible dans le menu de l'ampli ou sur ta box/routeur).",
  amp_net_port: "Le port TCP/UDP du KPA1500 — 1500 par défaut, modifiable sur l'ampli via la commande ^CP si tu l'as changé.",

  rotor_enabled: "Active le pilotage de ton rotor d'antenne (pointage automatique vers une station) depuis le logiciel.",
  rotor_brand: "Marque de ton rotor. La choisir règle automatiquement le protocole conseillé et signale si le boîtier gère l'élévation (satellite/EME).",
  rotor_model: "Modèle précis. « Az/El » = boîtier azimut + élévation (ex. Yaesu G-5500, SPID ROT2PROG) pour le suivi satellite.",
  rotor_proto: "Protocole : GS-232 natif (LogX parle direct au boîtier Yaesu/Kenpro ou à un serveur TCP PstRotator/microHam), ou Hamlib rotctld (universel : SPID, Pro.Sis.Tel, Hy-Gain, M2…).",
  rotor_host: "Adresse réseau : IP du PC où tourne rotctld, ou IP du boîtier/serveur GS-232 en TCP.",
  rotor_port: "Port réseau — 4533 par défaut pour rotctld, souvent 4001 pour un serveur GS-232 en TCP.",

  relay_enabled: "Active le pilotage d'une carte relais (commutation d'antennes ou d'accessoires) depuis le logiciel.",
  relay_kind: "KMTronic/Denkovi/série générique : même protocole d'octets, en USB/RS-232. WebSwitch (Digital Loggers) : boîtier réseau piloté en HTTP.",
  relay_count: "Le nombre de relais que porte ta carte — détermine le nombre de boutons de la bascule manuelle et les numéros disponibles pour l'auto-pilotage.",
  relay_auto_band: "Bascule automatiquement le relais mappé à la bande courante (table BANDE → RELAIS ci-dessous) dès que la radio change de bande.",
  relay_port: "Le port série (COM) où la carte relais est reliée à l'ordinateur — utilisé pour KMTronic/Denkovi/série générique.",
  relay_baud: "La vitesse de communication série (bauds) de la carte relais — doit correspondre au réglage de la carte, souvent 9600 par défaut.",
  relay_host: "Adresse IP du boîtier WebSwitch (Digital Loggers) sur ton réseau local.",
  relay_user: "Identifiant de connexion au WebSwitch (Digital Loggers) — souvent « admin » par défaut.",
  relay_password: "Mot de passe de connexion au WebSwitch (Digital Loggers).",

  voicekeyer_enabled: "Active le keyer vocal : le logiciel peut synthétiser et émettre un message phonie (CQ, échange...) automatiquement, sans micro.",
  voicekeyer_voice_id: "La voix de synthèse à utiliser (dépend des voix installées sur ton système Windows).",
  voicekeyer_rate: "La vitesse de la voix de synthèse (débit de parole).",
  voicekeyer_device: "Le périphérique audio de sortie à utiliser pour le keyer vocal — choisis une interface dédiée vers l'entrée micro de ta radio, JAMAIS tes haut-parleurs.",
  voicekeyer_ai_enabled: "Essaie une voix IA cloud (plus naturelle qu'une voix Windows) AVANT la voix locale — nécessite internet et une clé API. Si le fournisseur est injoignable ou mal configuré, LogX AI retombe automatiquement et silencieusement sur la voix locale hors-ligne : le keyer vocal continue de fonctionner sans réseau.",
  voicekeyer_ai_api_key: "Clé API de ton compte chez le fournisseur choisi (ex. ElevenLabs). Stockée uniquement côté serveur, jamais dans le navigateur.",
  voicekeyer_ai_voice_id: "Identifiant de la voix chez le fournisseur (visible sur ton tableau de bord ElevenLabs — Voice ID).",
  voicekeyer_piper_enabled: "Essaie Piper (moteur neuronal local, hors-ligne, sans abonnement) avant la voix Windows — rendu nettement plus naturel. Nécessite pip install piper-tts + un modèle de voix téléchargé une fois. Repli automatique et silencieux sur la voix Windows si Piper n'est pas installé/configuré.",
  voicekeyer_piper_exe: "Nom ou chemin complet de la commande piper — laisse 'piper' si elle est accessible depuis le PATH système.",
  voicekeyer_piper_model: "Chemin du fichier de voix .onnx téléchargé (ex. depuis huggingface.co/rhasspy/piper-voices) — un modèle par langue/voix.",

  wsjtx_enabled: "Active la réception automatique des QSO validés dans WSJT-X (FT8/FT4) : ils apparaissent dans ton log SANS ressaisie.",
  wsjtx_port: "Le port UDP sur lequel WSJT-X diffuse ses informations — doit correspondre au réglage « UDP Server » dans WSJT-X (Réglages → Rapports), généralement 2237.",
  adifnet_mode: "Comment ce PC échange des QSO en réseau avec un autre logiciel (N1MM/DXLog) : recevoir seulement, envoyer seulement, ou les deux.",
  adifnet_port: "Le port UDP utilisé pour cet échange réseau ADIF.",
  adifnet_target: "L'adresse IP du PC voisin avec lequel échanger les QSO en réseau (laisser vide pour diffuser en broadcast sur tout le réseau local).",
  mqtt_enabled: "Publie QSO/fréquence radio/score vers un broker MQTT local, pour un tableau de bord externe (Node-RED, Home Assistant...). Nécessite le paquet Python optionnel paho-mqtt — sans effet si non installé.",
  mqtt_host: "Adresse réseau du broker MQTT (ex. Mosquitto) — souvent 127.0.0.1 si le broker tourne sur ce même PC.",
  mqtt_port: "Port du broker MQTT — 1883 par défaut (sans chiffrement).",
  mqtt_topic_prefix: "Préfixe des topics publiés (défaut « logx ») : donne logx/qso, logx/rig/freq, logx/score.",

  access_password: "Mot de passe optionnel exigé avant d'accorder les droits d'écriture (ajout de QSO, configuration) à un appareil qui charge une page du logiciel. Laisse vide et clique « Désactiver » pour retirer la protection (comportement par défaut : accès automatique, adapté à un LAN de confiance). Circule en clair sur le réseau local (pas de HTTPS) — protège d'un accès non voulu, pas d'une écoute réseau active. Définir ou modifier ce mot de passe déconnecte immédiatement tous les appareils déjà connectés (jeton d'écriture régénéré) : reconnexion nécessaire partout, y compris sur ce poste (automatique).",

  ai_model: "Le modèle d'intelligence artificielle utilisé par le copilote (analyse de règlement, coach pendant le concours, cet assistant). Change de fournisseur si tu as une clé d'un autre service.",
  api_key: "Ta clé d'accès personnelle au service d'IA choisi (Anthropic/OpenAI/Gemini). Indispensable pour utiliser le copilote IA — reste stockée uniquement sur ton poste, jamais partagée. Sans elle, le logiciel fonctionne normalement, seul le copilote IA est indisponible.",

  qrz_user: "Ton identifiant de connexion QRZ.com — permet de rechercher automatiquement les infos (nom, QTH, adresse) d'un indicatif que tu contactes.",
  qrz_password: "Ton mot de passe QRZ.com. Reste stocké uniquement sur ton poste.",
  eqsl_user: "Ton identifiant eQSL.cc, pour envoyer/recevoir tes confirmations de QSO électroniques.",
  eqsl_password: "Ton mot de passe eQSL.cc.",
  lotw_user: "Ton identifiant ARRL Logbook of the World (LoTW), pour synchroniser tes confirmations DXCC.",
  lotw_password: "Ton mot de passe LoTW (ou mot de passe de certificat TQSL selon ta configuration).",
  clublog_callsign: "L'indicatif enregistré sur ton compte ClubLog.org, pour l'upload automatique de ton log.",
  clublog_email: "L'email associé à ton compte ClubLog.org.",
  clublog_password: "Un « Application Password » ClubLog — PAS ton mot de passe principal du site : génère-le sur clublog.org → Settings → App Passwords (ClubLog le recommande explicitement pour tout logiciel tiers comme celui-ci, il ne donne pas accès au site web et ignore la double authentification).",
  clublog_api_key: "Ta clé API ClubLog (fournie par ClubLog.org), nécessaire pour certaines fonctions avancées comme le live upload.",
  clublog_live: "Active la remontée en direct de chaque QSO vers ClubLog Live pendant une expédition — les chasseurs te voient en temps réel.",
  qrzcq_callsign: "Ton indicatif enregistré sur QRZCQ.com.",
  qrzcq_api_key: "Ta clé API QRZCQ.com.",
  hrdlog_callsign: "Ton indicatif enregistré sur HRDLog.net.",
  hrdlog_code: "Ton code d'upload personnel HRDLog.net (trouvable dans les réglages de ton compte HRDLog).",
  qrz_logbook_key: "Ta clé API QRZ Logbook (nécessite un abonnement QRZ XML actif — qrz.com → Mon compte → Logbook Data → API Key). Vide = fonctionnalité inactive.",
  qrz_logbook_push: "Insère automatiquement chaque QSO ajouté dans ton carnet QRZ Logbook (ACTION=INSERT), en plus du log local. Nécessite la clé API ci-dessus.",
  sota_client_id: "Identifiant OAuth personnel délivré par l'équipe SOTA (SOTA Reflector, groupe « API-consumers ») pour publier tes spots directement sur SOTAwatch3. Vide = fonctionnalité inactive. Les CGU de l'API SOTA exigent en plus un accord préalable explicite pour tout logiciel assisté par IA (voir la case à cocher juste en dessous) — demande les deux en même temps à l'équipe SOTA.",
  sota_ai_approval_ack: "Confirme que tu as obtenu l'accord explicite de l'équipe SOTA pour utiliser ce logiciel (assisté par IA) avec leur API — exigé par leurs Conditions d'Utilisation avant toute publication de spot, en plus du clientId.",
  on4kst_callsign: "Ton indicatif pour te connecter au chat ON4KST (chat texte très utilisé en VHF/UHF pour organiser des skeds).",
  on4kst_password: "Ton mot de passe du chat ON4KST.",

  cloudsync_folder: "Le dossier local DÉJÀ synchronisé par un outil comme Synology Drive/OneDrive/Dropbox : c'est via ce dossier partagé que plusieurs postes échangent leurs QSO, sans service en ligne dédié. Choisis l'option « toujours conserver sur cet appareil » dans cet outil (pas de fichiers à la demande) pour que la synchro reste rapide.",
  lan_sync_enabled: "Synchro LAN directe : les postes LogX du même réseau se découvrent automatiquement (beacon UDP) et échangent leurs QSO en direct, sans dossier partagé. Indépendant du Cloud Sync — tu peux activer les deux. Aucune adresse à saisir ; un poste voisin apparaît en 15 à 25 secondes.",
  lan_sync_token: "Optionnel. Sans lui, la synchro LAN accepte tout poste du réseau local qui se présente. Avec lui (même valeur sur tous les postes de l'équipe), seuls les postes qui le connaissent sont acceptés — utile sur un WiFi partagé (salle commune, visiteurs). À communiquer directement entre opérateurs, jamais par ce dossier.",
  cloudsync_mode: "FULL = ce poste envoie ET reçoit les QSO des autres postes ; PUSH = il envoie seulement (utile pour un poste isolé avec liaison intermittente) ; OFF = désactivé.",
  cloudsync_interval: "La fréquence (en minutes) à laquelle ce poste vérifie s'il y a de nouveaux QSO à échanger.",
  cloudsync_secret: "Optionnel. Sans lui, les fichiers cloudsync ne sont pas signés (rétro-compatible). Avec lui (même valeur sur tous les postes de l'équipe), chaque fichier déposé dans le dossier partagé est signé et vérifié (HMAC) — un tiers ayant accès à ce dossier (Dropbox/OneDrive/Synology partagé) ne peut plus en falsifier le contenu sans connaître ce jeton. À communiquer directement entre opérateurs, jamais par ce dossier.",
  mysql_mode: "« Synchronisation complète » lit ET écrit (chaque poste voit les QSO des autres) ; « Envoi seul » écrit sans rien récupérer (utile pour un poste isolé qui alimente la base sans avoir besoin des QSO des autres).",
  mysql_host: "Adresse IP ou nom d'hôte du serveur MySQL/MariaDB partagé.",
  mysql_port: "Port du serveur MySQL — 3306 par défaut.",
  mysql_user: "Identifiant MySQL avec droits de lecture/écriture sur la base indiquée.",
  mysql_password: "Mot de passe MySQL de l'identifiant ci-dessus — stocké côté serveur uniquement.",
  mysql_database: "Nom de la base de données — doit être identique sur tous les postes qui synchronisent ensemble. La table y est créée automatiquement au premier essai.",
  backup_folder: "Le dossier où les sauvegardes automatiques de ton log sont écrites — choisis un emplacement hors du dossier du logiciel (clé USB, cloud...).",
  backup_interval: "La fréquence (en minutes) des sauvegardes automatiques.",
  scoreboard_enabled: "Active la publication automatique de ton score en direct sur un tableau de bord en ligne, visible par d'autres.",
  scoreboard_interval: "La fréquence (en minutes) de mise à jour du scoreboard en ligne.",

  refresh_min: "La fréquence (en minutes) à laquelle le logiciel rafraîchit automatiquement les spots/la propagation en tâche de fond.",

  omnirig_rig_num: "Le numéro de radio configuré côté OmniRig (Rig1 ou Rig2) — OmniRig doit déjà tourner et être réglé sur ce PC.",
  flexradio_host: "Adresse réseau (IP) de la radio ou du poste FlexRadio qui expose l'API SmartSDR (port TCP natif, pas le serveur DAX/CAT virtuel).",
  flexradio_port: "Port TCP de l'API SmartSDR — 4992 par défaut.",
  icomremote_host: "IP de la radio Icom en réseau (IC-705/IC-7610/IC-905...) — ce mode n'est pas encore fonctionnel, voir la note dans la section RADIO.",
  icomremote_control_port: "Port UDP du canal de contrôle Icom (pairing/authentification) — 50001 par défaut.",
  icomremote_civ_port: "Port UDP du canal CI-V encapsulé Icom — 50002 par défaut.",
  icomremote_civ_addr: "Adresse CI-V de la radio (menu Set → CI-V Address), en hexadécimal — ex. AC pour l'IC-705.",
  icomremote_username: "Identifiant réseau configuré sur la radio (menu Set → Network → Access Control).",
  icomremote_password: "Mot de passe réseau configuré sur la radio — stocké localement, jamais transmis (ce mode n'ouvre encore aucune connexion).",
  pgxl_enabled: "Active la lecture des mesureurs (FWD/RL/DRV/ID/TEMP) du PowerGenius XL via son API réseau — pas de bascule standby/operate à distance (voir la note de cette section).",
  pgxl_host: "Adresse IP du PowerGenius XL sur le réseau local.",
  pgxl_port: "Port TCP de l'API réseau du PowerGenius XL — 9008 par défaut.",
  pgxl_timeout: "Délai d'attente réseau (secondes) avant d'abandonner une commande — borné entre 1 et 10 s côté serveur.",
  acom_enabled: "Active le pilotage d'un amplificateur ACOM (série RS-232) depuis le logiciel : lecture de la télémétrie et bascule Operate/Standby.",
  acom_port: "Port série (COM) où est branché l'ACOM — utilise la liste détectée automatiquement.",
  acom_model: "Modèle exact de l'ampli — sert uniquement à calibrer l'affichage de la température (offset propre à chaque modèle), aucun effet sur les commandes.",
  acom_timeout: "Délai d'attente série (secondes) avant d'abandonner une commande — borné entre 1 et 10 s côté serveur.",
  telemetry_enabled: "Envoie un heartbeat quotidien minimal (identifiant d'installation aléatoire, version, système d'exploitation) — jamais ton indicatif, jamais de QSO. Activée par défaut, désactivable ici en un clic.",
  telemetry_endpoint: "Champ avancé. Tant qu'il est vide, aucune requête réseau n'est jamais envoyée — aucune destination officielle n'existe pour l'instant.",
};

// Icône "?" ajoutée automatiquement à côté de chaque label dont le champ
// associé est répertorié dans CONFIG_HELP — pas besoin de modifier le HTML
// de chaque champ un par un.
function initFieldHelp(){
  document.querySelectorAll('.form-group').forEach(group => {
    const field = group.querySelector('input[id], select[id], textarea[id]');
    const label = group.querySelector('label');
    if (!field || !label || !CONFIG_HELP[field.id]) return;
    if (label.querySelector('.help-dot')) return;   // déjà enrichi
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'help-dot';
    btn.textContent = '?';
    btn.title = 'Explication de ce champ';
    btn.style.cssText = 'display:inline-flex;align-items:center;justify-content:center;'
      + 'width:16px;height:16px;margin-left:6px;border-radius:50%;background:var(--bg3);'
      + 'border:1px solid var(--accent2);color:var(--accent2);font-size:10.5px;font-weight:700;'
      + 'cursor:pointer;vertical-align:middle;line-height:1';
    btn.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); showFieldHelp(field.id, btn); });
    label.appendChild(btn);
  });
}

function showFieldHelp(fieldId, anchorEl){
  const bubble = document.getElementById('fieldHelpBubble');
  const text = CONFIG_HELP[fieldId];
  if (!text) return;
  document.getElementById('fieldHelpText').textContent = text;
  const r = anchorEl.getBoundingClientRect();
  bubble.style.display = 'block';
  // Repositionne si la bulle sortirait de l'écran (bords droit/bas).
  let left = r.left, top = r.bottom + 8;
  requestAnimationFrame(() => {
    const bw = bubble.offsetWidth, bh = bubble.offsetHeight;
    if (left + bw > window.innerWidth - 12) left = window.innerWidth - bw - 12;
    if (top + bh > window.innerHeight - 12) top = r.top - bh - 8;
    bubble.style.left = Math.max(8, left) + 'px';
    bubble.style.top = Math.max(8, top) + 'px';
  });
}
document.addEventListener('click', e => {
  const bubble = document.getElementById('fieldHelpBubble');
  if (bubble.style.display !== 'none' && !e.target.closest('.help-dot') && !e.target.closest('#fieldHelpBubble')) {
    bubble.style.display = 'none';
  }
});

// ─── PANNEAU ASSISTANT (questions libres) ────────────────────────────────────
const ASSISTANT_SUGGESTIONS = [
  "Quelle est la différence entre INDICATIF et INDICATIF CONCOURS ?",
  "Quel mode d'utilisation choisir ?",
  "Comment trouver mon locator ?",
  "À quoi sert le mode CAT / TCI / rigctld / flrig ?",
  "Comment fonctionne le Cloud Sync ?",
  "Ai-je besoin d'une clé API ?",
];

function toggleAssistant(){
  const panel = document.getElementById('assistantPanel');
  const willOpen = panel.style.display === 'none';
  panel.style.display = willOpen ? 'flex' : 'none';
  if (willOpen && !panel.dataset.booted){
    panel.dataset.booted = '1';
    addAssistantMsg('agent', "Bonjour ! Je peux expliquer n'importe quel champ de cette page. Clique une question ci-dessous, ou tape la tienne.");
    const sugg = document.createElement('div');
    sugg.style.cssText = 'display:flex;flex-direction:column;gap:6px';
    sugg.innerHTML = ASSISTANT_SUGGESTIONS.map(q =>
      `<button type="button" onclick="askAssistant(${JSON.stringify(q)})" style="text-align:left;background:var(--bg3);`
      + `border:1px solid var(--border);color:var(--text);border-radius:6px;padding:7px 10px;cursor:pointer;font-size:12.5px">${q}</button>`
    ).join('');
    document.getElementById('assistantBody').appendChild(sugg);
  }
}

function addAssistantMsg(who, text){
  const body = document.getElementById('assistantBody');
  const div = document.createElement('div');
  div.style.cssText = who === 'user'
    ? 'align-self:flex-end;background:#C9822E;color:#04222b;border-radius:10px 10px 2px 10px;padding:8px 11px;max-width:85%;white-space:pre-wrap'
    : 'align-self:flex-start;background:var(--bg3);color:var(--text);border-radius:10px 10px 10px 2px;padding:8px 11px;max-width:85%;white-space:pre-wrap;border:1px solid var(--border)';
  div.textContent = text;
  body.appendChild(div);
  body.scrollTop = body.scrollHeight;
  return div;
}

// Recherche mot-clé simple dans CONFIG_HELP : suffisant pour une base d'une
// centaine d'entrées, sans dépendance externe. Retourne les meilleures
// correspondances (champ trouvé dans le label OU dans le texte d'aide).
//
// Correctif (retour F4GLD, capture d'écran 07/08/2026) : « hay.includes(w) »
// faisait un match de SOUS-CHAÎNE, pas de mot entier — "trouve" matchait
// dans "retrouver", faisant remonter l'entrée « indicatif » comme réponse à
// « où se trouve le module de décodage sstv », alors qu'AUCUNE entrée de
// CONFIG_HELP ne parle de sstv (cette base ne couvre que les champs de
// formulaire de LA page CONFIG, pas le reste du logiciel — pour "où est une
// fonctionnalité dans l'appli", voir plutôt la loupe de recherche de la nav,
// logx_search.js, qui couvre le contenu réel des pages). Passage à un match
// par mot ENTIER (frontières \b) pour ne plus remonter de faux positifs.
function _wholeWordIncludes(haystack, word){
  const esc = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp('\\b' + esc + '\\b').test(haystack);
}
function _searchLocalHelp(query){
  const q = query.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const words = q.split(/\s+/).filter(w => w.length > 2);
  if (!words.length) return [];
  const scored = Object.entries(CONFIG_HELP).map(([id, text]) => {
    const hay = (id + ' ' + text).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    const score = words.reduce((s, w) => s + (_wholeWordIncludes(hay, w) ? 1 : 0), 0);
    return { id, text, score };
  }).filter(x => x.score > 0);
  scored.sort((a, b) => b.score - a.score);
  return scored.slice(0, 3);
}

async function askAssistant(presetQuestion){
  const input = document.getElementById('assistantInput');
  const q = (presetQuestion || input.value).trim();
  if (!q) return;
  input.value = '';
  addAssistantMsg('user', q);

  // Correctif B5 : attendre que le chargement initial de la config soit
  // terminé avant de juger #api_key vide — sinon un clic immédiatement après
  // un rechargement de page (avant la résolution du fetch('/config.json')
  // asynchrone) donnait "pas de clé API" alors qu'une clé existe côté serveur.
  // No-op si déjà résolu (cas courant : callsign déjà en localStorage).
  if (typeof _initReady !== 'undefined') { try { await _initReady; } catch(e){} }

  const hits = _searchLocalHelp(q);
  const apiKey = (document.getElementById('api_key').value || '').trim();

  if (!apiKey){
    // Pas de clé IA configurée : réponse basée UNIQUEMENT sur la base locale,
    // toujours utile et jamais bloquante pour un débutant qui démarre.
    if (hits.length){
      addAssistantMsg('agent', hits.map(h => `• ${h.text}`).join('\n\n'));
    } else {
      addAssistantMsg('agent', "Je n'ai pas de réponse toute prête pour cette question précise. "
        + "Survole les « ? » à côté des champs pour leur explication, ou configure une clé API "
        + "(étape PROPAGATION → COPILOTE IA) pour que je puisse répondre plus librement.");
    }
    return;
  }

  const thinking = addAssistantMsg('agent', '…');
  try{
    const helpDump = Object.entries(CONFIG_HELP).map(([id, t]) => `- ${id} : ${t}`).join('\n');
    const provider = (localStorage.getItem('logx_ai_provider') || 'anthropic');
    const model = document.getElementById('ai_model') && document.getElementById('ai_model').value || 'claude-sonnet-4-6';
    const system = "Tu es l'assistant intégré au formulaire de CONFIGURATION du logiciel radioamateur LogX AI. "
      + "Réponds en français, en 2 à 5 phrases MAXIMUM, avec des mots simples pour un débutant (pas de jargon "
      + "non expliqué). Voici le sens exact des champs du formulaire (ne parle QUE de ce qui existe réellement "
      + "ici, n'invente jamais un champ ou une fonctionnalité) :\n" + helpDump;
    const res = await fetch('/proxy/ai', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ model, max_tokens: 400, system, messages: [{ role:'user', content:q }] })
    });
    const data = await res.json();
    const reply = (data.content || []).filter(b => b.type === 'text').map(b => b.text).join('\n').trim();
    thinking.textContent = reply || "Pas de réponse du copilote IA — vérifie ta clé API.";
  }catch(e){
    thinking.textContent = hits.length
      ? hits.map(h => `• ${h.text}`).join('\n\n')
      : "Le copilote IA n'a pas répondu (réseau ?) et je n'ai pas de fiche locale pour cette question précise.";
  }
}

document.addEventListener('DOMContentLoaded', initFieldHelp);
// La page reconstruit certains blocs de formulaire dynamiquement (résumé,
// profils...) ; on ré-applique l'enrichissement après le chargement initial
// pour couvrir les champs ajoutés après coup.

// Point d'entrée léger depuis LOGBOOK (retour audit trouvabilité 09/08/2026) :
// l'assistant IA d'aide n'existait QUE sur CONFIG, aucun secours depuis
// LOGBOOK en pleine session. Plutôt que dupliquer tout le panneau, un simple
// lien logx_configuration.html?openAssistant=1 depuis LOGBOOK rouvre CONFIG
// avec le panneau déjà ouvert.
// readyState vérifié explicitement (pas juste DOMContentLoaded) : sur cette
// page, ce bloc <script> s'exécute parfois APRÈS que l'événement soit déjà
// passé (constaté en navigateur réel) — même raison que le setTimeout(800)
// de secours juste en dessous pour initFieldHelp.
function _openAssistantFromQuery(){
  if (new URLSearchParams(location.search).get('openAssistant') === '1') toggleAssistant();
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', _openAssistantFromQuery);
else _openAssistantFromQuery();
setTimeout(initFieldHelp, 800);
// ─── STATE ───────────────────────────────────────────────────────────────────
const state = {
  contest: null,
  toggles: {},
  alertRules: [],
  datesAutoFor: null, // concours pour lequel les dates ont été auto-calculées
  submitUrlAutoFor: null, // concours pour lequel submit_url a été auto-rempli
};
// Contest pour lequel applyContestFilters a déjà été appliqué (évite d'écraser
// les choix manuels de l'utilisateur à chaque réouverture du panneau FILTRES)
let _filtersAppliedFor = null;

// ─── CONTESTS DATA ───────────────────────────────────────────────────────────
// Calendrier REF 2026 complet + concours internationaux
const CONTESTS = [

  // ── CALENDRIER REF 2026 ──────────────────────────────────────────────────
  {
    id:'REF_CHALLENGE_THF', name:'Challenge THF', org:'REF',
    date:'01/01/2026 → 31/12/2026', correcteur:'CC',
    bands:['144MHz→47GHz'], modes:['SSB','CW','FM','DIGI'],
    score:'Cumulatif annuel — pts/km × locators', color:'#FF5030',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_challengethf_fr_20251209.pdf',
    group:'REF'
  },
  {
    id:'REF_CCD_JAN1', name:'Courte Durée Cumulatif — 1re partie', org:'REF',
    date:'11/01/2026 06h00-11h00', correcteur:'F6IIT',
    bands:['432MHz','1296MHz','2320MHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators — cumulatif 6 épreuves', color:'#00D4FF',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ccdthf_fr_20260429.pdf',
    group:'REF'
  },
  {
    id:'REF_CCD_JAN2', name:'Courte Durée Cumulatif — 2e partie', org:'REF',
    date:'18/01/2026 06h00-11h00', correcteur:'F6IIT',
    bands:['144MHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators — cumulatif 6 épreuves', color:'#00D4FF',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ccdthf_fr_20260429.pdf',
    group:'REF'
  },
  {
    id:'REF_CDF_HF_CW', name:'Championnat de France HF Télégraphie', org:'REF',
    date:'24-25/01/2026 06h00→18h00', correcteur:'F4CWN',
    bands:['3.5MHz','7MHz','14MHz','21MHz','28MHz'], modes:['CW'],
    score:'pts × depts + DXCC', color:'#FFD60A',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_cdfhf_fr_20251117.pdf',
    group:'REF'
  },
  {
    id:'REF_CCD_FEV1', name:'Courte Durée Cumulatif — 3e partie', org:'REF',
    date:'08/02/2026 06h00-11h00', correcteur:'F6IIT',
    bands:['432MHz','1296MHz','2320MHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators — cumulatif 6 épreuves', color:'#00D4FF',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ccdthf_fr_20260429.pdf',
    group:'REF'
  },
  {
    id:'REF_CCD_FEV2', name:'Courte Durée Cumulatif — 4e partie', org:'REF',
    date:'15/02/2026 06h00-11h00', correcteur:'F6IIT',
    bands:['144MHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators — cumulatif 6 épreuves', color:'#00D4FF',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ccdthf_fr_20260429.pdf',
    group:'REF'
  },
  {
    id:'REF_CDF_HF_SSB', name:'Championnat de France HF Téléphonie', org:'REF',
    date:'21-22/02/2026 06h00→18h00', correcteur:'F4CWN',
    bands:['3.5MHz','7MHz','14MHz','21MHz','28MHz'], modes:['SSB'],
    score:'pts × depts + DXCC', color:'#FF5030',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_cdfhf_fr_20251117.pdf',
    group:'REF'
  },
  {
    id:'REF_NAT_THF', name:'National THF — Trophée F3SK', org:'REF',
    date:'07-08/03/2026 14h00→14h00', correcteur:'F4CIB',
    bands:['144MHz→47GHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators', color:'#00D4FF',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_natthf_fr_20250312.pdf',
    group:'REF'
  },
  {
    id:'REF_CCD_MAR', name:'Concours de Courte Durée (Mars)', org:'REF',
    date:'22/03/2026 06h00-11h00', correcteur:'F6DZR',
    bands:['144MHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators', color:'#00D4FF',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ccdthf_fr_20260429.pdf',
    group:'REF'
  },
  {
    id:'REF_NAT_TVA', name:'National TVA', org:'REF',
    date:'29/03/2026 06h00-11h00', correcteur:'F1BLQ',
    bands:['438MHz+','TVA'], modes:['FM','ATV'],
    score:'pts × relais TVA', color:'#BF5AF2',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_nattva_fr_20251209.pdf',
    group:'REF'
  },
  {
    id:'REF_CCD_AVR_CW', name:'Concours de Courte Durée CW (Avril)', org:'REF',
    date:'19/04/2026 05h00-10h00', correcteur:'F4CWN',
    bands:['144MHz'], modes:['CW'],
    score:'1pt/km × locators', color:'#FFD60A',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ccdthf_fr_20260429.pdf',
    group:'REF'
  },
  {
    id:'REF_PRINTEMPS', name:'Concours du Printemps', org:'REF',
    date:'02-03/05/2026 14h00→14h00', correcteur:'F4CIB',
    bands:['144MHz→47GHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators', color:'#00D4FF',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_printemps_fr_20250312.pdf',
    group:'REF'
  },
  {
    id:'REF_CCD_MAI', name:'Concours de Courte Durée (Mai)', org:'REF',
    date:'17/05/2026 05h00-10h00', correcteur:'F5RQQ',
    bands:['432MHz','1296MHz','2320MHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators', color:'#00D4FF',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ccdthf_fr_20260429.pdf',
    group:'REF'
  },
  {
    id:'REF_CDF_THF', name:'Championnat de France THF', org:'REF',
    date:'06-07/06/2026 14h00→14h00', correcteur:'F6IIT',
    bands:['144MHz→47GHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators', color:'#FF5030',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_cdfthf_fr_20251222.pdf',
    group:'REF'
  },
  {
    id:'REF_IARU_TVA', name:'IARU R1 TVA', org:'REF/IARU',
    date:'13-14/06/2026 12h00→18h00', correcteur:'F1BLQ',
    bands:['438MHz+','TVA'], modes:['FM','ATV'],
    score:'pts × relais TVA', color:'#BF5AF2',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_iarutva_fr_20251209.pdf',
    group:'REF'
  },
  {
    id:'REF_DDFM_50', name:'DDFM 50MHz', org:'REF',
    date:'13-14/06/2026 14h00→14h00', correcteur:'F4CWN',
    bands:['50MHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators', color:'#30D158',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ddfm50_fr_20250312.pdf',
    group:'REF'
  },
  {
    id:'REF_IARU_50', name:'IARU R1 50MHz — Mémorial F8SH', org:'REF/IARU',
    date:'20-21/06/2026 14h00→14h00', correcteur:'F4CIB',
    bands:['50MHz'], modes:['SSB','CW'],
    score:'1pt/km × locators', color:'#30D158',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_iaru50_fr_20250312.pdf',
    group:'REF'
  },
  {
    id:'REF_RPH', name:'Rallye des Points Hauts', org:'REF',
    date:'04-05/07/2026 14h00→14h00', correcteur:'F6DZR',
    bands:['144MHz→47GHz'], modes:['SSB'],
    score:'1pt/km — NO DIGI — portable obligatoire', color:'#FF5030',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_rph_fr_20250312.pdf',
    group:'REF'
  },
  {
    id:'REF_QRP', name:'Bol d\'or des QRP — Trophée F8BO', org:'REF',
    date:'18-19/07/2026 14h00→14h00', correcteur:'F6DZR',
    bands:['144MHz→47GHz'], modes:['SSB','CW'],
    score:'1pt/km × locators — QRP uniquement (≤5W)', color:'#FFD60A',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_qrp_fr_20250312.pdf',
    group:'REF'
  },
  {
    id:'REF_ETE', name:'Concours d\'été', org:'REF',
    date:'01-02/08/2026 14h00→14h00', correcteur:'F5RQQ',
    bands:['144MHz→47GHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators', color:'#00D4FF',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ete_fr_20250312.pdf',
    group:'REF'
  },
  {
    id:'REF_F8TD', name:'Trophée F8TD', org:'REF',
    date:'30/08/2026 04h00-13h00', correcteur:'F6DZR',
    bands:['1296MHz→47GHz'], modes:['SSB','CW'],
    score:'1pt/km × locators — SHF uniquement', color:'#BF5AF2',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_f8td_fr_20250312.pdf',
    group:'REF'
  },
  {
    id:'REF_IARU_VHF', name:'IARU R1 VHF', org:'REF/IARU',
    date:'05-06/09/2026 14h00→14h00', correcteur:'F4CIB',
    bands:['144MHz'], modes:['SSB','CW'],
    score:'1pt/km × locators', color:'#BF5AF2',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_iaruvhf_fr_20250312.pdf',
    group:'REF'
  },
  {
    id:'REF_CDF_TVA', name:'Championnat de France TVA', org:'REF',
    date:'12-13/09/2026 12h00→12h00', correcteur:'F1BLQ',
    bands:['438MHz+','TVA'], modes:['FM','ATV'],
    score:'pts × relais TVA', color:'#BF5AF2',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_cdftva_fr_20251209.pdf',
    group:'REF'
  },
  {
    id:'REF_IARU_UHF', name:'IARU UHF/SHF', org:'REF/IARU',
    date:'03-04/10/2026 14h00→14h00', correcteur:'F4CIB',
    bands:['432MHz→47GHz'], modes:['SSB','CW'],
    score:'1pt/km × locators', color:'#BF5AF2',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_iaruuhf_fr_20250312.pdf',
    group:'REF'
  },
  {
    id:'REF_CCD_OCT', name:'Concours de Courte Durée (Octobre)', org:'REF',
    date:'18/10/2026 05h00-10h00', correcteur:'F5RQQ',
    bands:['432MHz','1296MHz','2320MHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators', color:'#00D4FF',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ccdthf_fr_20260429.pdf',
    group:'REF'
  },
  {
    id:'REF_MARCONI', name:'IARU R1 VHF CW — Mémorial Marconi', org:'REF/IARU',
    date:'07-08/11/2026 14h00→14h00', correcteur:'F4CIB',
    bands:['144MHz'], modes:['CW'],
    score:'1pt/km × locators — CW uniquement', color:'#FFD60A',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_marconi_fr_20250312.pdf',
    group:'REF'
  },
  {
    id:'REF_160M', name:'REF 160m — Trophée F8EX', org:'REF',
    date:'21-22/11/2026 17h00→00h00', correcteur:'F4CWN',
    bands:['1.8MHz'], modes:['SSB','CW'],
    score:'pts × depts français + DXCC', color:'#FF2D55',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ref160_fr_20250312.pdf',
    group:'REF'
  },
  {
    id:'REF_CCD_NOV', name:'Concours de Courte Durée (Novembre)', org:'REF',
    date:'22/11/2026 06h00-11h00', correcteur:'F6IIT',
    bands:['144MHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators', color:'#00D4FF',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ccdthf_fr_20260429.pdf',
    group:'REF'
  },
  {
    id:'REF_CCD_DEC', name:'Concours de Courte Durée (Décembre)', org:'REF',
    date:'06/12/2026 06h00-11h00', correcteur:'F5RQQ',
    bands:['144MHz'], modes:['SSB','CW','FM'],
    score:'1pt/km × locators', color:'#00D4FF',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ccdthf_fr_20260429.pdf',
    group:'REF'
  },
  {
    id:'REF_CCD_DEC_CW', name:'Concours de Courte Durée CW (Décembre)', org:'REF',
    date:'20/12/2026 06h00-11h00', correcteur:'F6DZR',
    bands:['144MHz'], modes:['CW'],
    score:'1pt/km × locators — CW uniquement', color:'#FFD60A',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_ccdthf_fr_20260429.pdf',
    group:'REF'
  },
  {
    id:'REF_NAT_TVA_DEC', name:'National TVA (Décembre)', org:'REF',
    date:'27/12/2026 06h00-11h00', correcteur:'F1BLQ',
    bands:['438MHz+','TVA'], modes:['FM','ATV'],
    score:'pts × relais TVA', color:'#BF5AF2',
    rules:'https://concours.r-e-f.org/reglements/actuels/reg_nattva_fr_20251209.pdf',
    group:'REF'
  },

  // ── AUTRES FRANÇAIS ──────────────────────────────────────────────────────
  {
    id:'F9NL', name:'Mémorial F9NL', org:'UFT',
    date:'3e week-end septembre 05h00-10h00 UTC', correcteur:'UFT',
    bands:['HF'], modes:['CW'],
    score:'pts × depts + DXCC — CW uniquement', color:'#FFD60A',
    rules:'https://www.uft.net', group:'Autre FR'
  },
  {
    id:'UFT_RENCONTRES', name:'Rencontres UFT', org:'UFT',
    date:'1er week-end décembre', correcteur:'UFT',
    bands:['HF'], modes:['CW'],
    score:'pts × depts — CW uniquement', color:'#FFD60A',
    rules:'https://www.uft.net', group:'Autre FR'
  },

  // ── INTERNATIONAUX ───────────────────────────────────────────────────────
  {
    id:'CQ_WW_SSB', name:'CQ World Wide DX — SSB', org:'CQ Magazine',
    date:'Dernier week-end octobre', correcteur:'CQ',
    bands:['1.8','3.5','7','14','21','28MHz'], modes:['SSB'],
    score:'pts × zones CQ × DXCC', color:'#FF5030', group:'International'
  },
  {
    id:'CQ_WW_CW', name:'CQ World Wide DX — CW', org:'CQ Magazine',
    date:'Dernier week-end novembre', correcteur:'CQ',
    bands:['1.8','3.5','7','14','21','28MHz'], modes:['CW'],
    score:'pts × zones CQ × DXCC', color:'#FFD60A', group:'International'
  },
  // ── World Wide Award (hamaward.cloud) — pas un concours classique : les
  // hunters ne marquent des points qu'en contactant l'une des stations
  // spéciales inscrites (ex. II1WWA), simple report RS/RST, sans N° de série
  // ni multiplicateur géographique. Voir https://hamaward.cloud/wwa/rules.
  {
    id:'WWA_2027_JAN', name:'World Wide Award — janvier', org:'HamAward',
    date:'01/01/2027 00h00 → 31/01/2027 23h59', correcteur:'',
    bands:['3.5','7','10.1MHz','14','18MHz','21','24MHz','28MHz'], modes:['SSB','CW','FT8','FT4','FT2','RTTY','PSK'],
    score:'10pts CW / 5pts SSB / 2pts FT8-FT4-FT2 / 5pts RTTY-PSK par station spéciale — 1 QSO/jour/bande/mode',
    color:'#FFD60A',
    rules:'https://hamaward.cloud/wwa/rules',
    group:'International'
  },
  {
    id:'WWA_2027_JUL', name:'World Wide Award — Sprint', org:'HamAward',
    date:'28/06/2027 00h00 → 04/07/2027 23h59', correcteur:'',
    bands:['3.5','7','10.1MHz','14','18MHz','21','24MHz','28MHz'], modes:['SSB','CW','FT8','FT4','FT2','RTTY','PSK'],
    score:'10pts CW / 5pts SSB / 2pts FT8-FT4-FT2 / 5pts RTTY-PSK par station spéciale — 1 QSO/jour/bande/mode',
    color:'#FFD60A',
    rules:'https://hamaward.cloud/wwa/rules',
    group:'International'
  },
  {
    id:'CQ_WPX_SSB', name:'CQ WPX — SSB', org:'CQ Magazine',
    date:'Dernier week-end mars', correcteur:'CQ',
    bands:['HF'], modes:['SSB'],
    score:'pts × préfixes uniques', color:'#FF5030', group:'International'
  },
  {
    id:'CQ_WPX_CW', name:'CQ WPX — CW', org:'CQ Magazine',
    date:'Dernier week-end mai', correcteur:'CQ',
    bands:['HF'], modes:['CW'],
    score:'pts × préfixes uniques', color:'#FFD60A', group:'International'
  },
  {
    id:'ARRL_DX_SSB', name:'ARRL DX — SSB', org:'ARRL',
    date:'3e week-end mars', correcteur:'ARRL',
    bands:['HF'], modes:['SSB'],
    score:'3pts × états/provinces US/Canada', color:'#30D158', group:'International'
  },
  {
    id:'ARRL_DX_CW', name:'ARRL DX — CW', org:'ARRL',
    date:'2e week-end février', correcteur:'ARRL',
    bands:['HF'], modes:['CW'],
    score:'3pts × états/provinces US/Canada', color:'#30D158', group:'International'
  },
  {
    id:'ARRL_FD', name:'ARRL Field Day', org:'ARRL',
    date:'27-28/06/2026 — 18h00 UTC (24h+)', correcteur:'ARRL',
    bands:['160m','80m','40m','20m','15m','10m','50MHz+'], modes:['SSB','CW','FT8','FT4','RTTY'],
    score:'QSO_pts × mult puissance + bonus autonomie',
    color:'#30D158', group:'International',
    rules:'https://www.arrl.org/field-day-rules'
  },
  {
    id:'SOTA', name:'Summits on the Air', org:'SOTA',
    date:'Permanent', correcteur:'SOTA',
    bands:['Toutes'], modes:['Tous'],
    score:'pts sommets portable/chasse', color:'#FFD60A', group:'International'
  },
  {
    id:'POTA', name:'Parks on the Air', org:'POTA',
    date:'Permanent', correcteur:'POTA',
    bands:['Toutes'], modes:['Tous'],
    score:'pts parcs portable/chasse', color:'#30D158', group:'International'
  },
  {
    id:'CUSTOM', name:'Concours personnalisé', org:'Manuel',
    date:'À définir', correcteur:'—',
    bands:['Au choix'], modes:['Au choix'],
    score:'À configurer manuellement', color:'#8E8E93', group:'Autre'
  },
];

// ─── SÉLECTEUR UNIFIÉ : FUSION SERVEUR + WA7BNM ──────────────────────────────
// Enrichit la liste locale CONTESTS avec :
//  1. la base serveur (/data/calendar) → badge "✓ règlement suivi" (dates et
//     règlements re-vérifiés automatiquement chaque année par logx_serveur.py) ;
//  2. le calendrier mondial WA7BNM (/data/external_contests) → badge
//     "à confirmer" (paramètres non vérifiés, à saisir manuellement — la
//     lecture IA du règlement arrivera en Phase 3).
const VERIFIED_IDS = new Set();   // ids présents dans la base serveur

// Vrai règlement (bandes/modes) tel que connu côté serveur — CONTEST_DEFINITIONS
// (logx_definitions.py, y compris les concours personnalisés fusionnés depuis
// custom_contests.json), exposé tel quel par /data/calendar (valeurs brutes
// MHz ex. '144'/'3.5' et modes majuscules ex. 'SSB'/'FT8', ou 'all'). Utilisé
// par _resolveContestFilters() pour restreindre l'étape FILTRES sans dupliquer
// une 2e fois ce règlement à la main (voir LEGACY_CONTEST_FILTERS plus bas,
// qui ne sert plus que pour les quelques concours ABSENTS de cette base).
const SERVER_CONTEST_RULES = {};

async function mergeServerContests(){
  try{
    const res = await fetch('/data/calendar');
    const data = await res.json();
    (data.contests || []).forEach(sc => {
      VERIFIED_IDS.add(sc.id);
      SERVER_CONTEST_RULES[sc.id] = { bands: sc.bands || [], modes: sc.modes || [] };
      const local = CONTESTS.find(c => c.id === sc.id);
      if (local){
        // La date serveur est recalculée chaque année → plus fiable que celle en dur
        if (sc.date && sc.date !== '—') local.date = sc.date;
        if (sc.rules_url) local.rules = sc.rules_url;
        if (sc.log_submit) local.log_submit = sc.log_submit;
        local._server_date = sc.date;         // "DD/MM/YYYY à HHhMM UTC"
        local._duration_h  = sc.duration_h;
        local._start_utc   = sc.start_utc;
        local._custom      = !!sc.custom;
      } else {
        CONTESTS.push({
          id: sc.id, name: sc.name, org: sc.organizer,
          date: sc.date || '', correcteur: '—',
          bands: (sc.bands || []).map(b => b + 'MHz'),
          modes: sc.modes || [],
          score: (sc.scoring && sc.scoring.unit) || '—',
          color: '#00D4FF', rules: sc.rules_url || '', log_submit: sc.log_submit || '',
          group: (sc.organizer || '').includes('REF') ? 'REF' : 'International',
          _server_date: sc.date, _duration_h: sc.duration_h, _start_utc: sc.start_utc,
          _custom: !!sc.custom,
        });
      }
    });
  }catch(e){ console.warn('[UNIFIÉ] base serveur non disponible :', e); }
}

async function mergeExternalContests(){
  try{
    const res = await fetch('/data/external_contests');
    const data = await res.json();
    (data.contests || []).forEach(ec => {
      const id = 'EXT_' + (ec.ref || (ec.name || '').replace(/\W+/g, '_').toUpperCase());
      if (CONTESTS.find(c => c.id === id)) return;
      CONTESTS.push({
        id, name: ec.name || 'Concours externe', org: 'WA7BNM',
        date: [ec.date_str, ec.time_str].filter(Boolean).join(' '), correcteur: '—',
        bands: [], modes: [],
        score: 'à confirmer — voir règlement', color: '#FFD60A',
        rules: ec.url || '', group: 'Mondial (WA7BNM)', external: true,
      });
    });
  }catch(e){ console.warn('[UNIFIÉ] WA7BNM non disponible :', e); }
}

// ─── SECRETS DE CONFIG (audit sécurité) ──────────────────────────────────────
// Ces champs ne sont JAMAIS écrits dans localStorage['logx_config'] (voir
// saveConfig()) — ils vivent uniquement côté serveur (current_config) et sont
// relus via GET /config/secrets (authentifié), pas via le cache local.
// api_key exclu volontairement de cette liste PARTAGÉE avec le serveur : la
// clé IA a son propre mécanisme dédié par fournisseur (logx_apikey_<provider>
// dans localStorage, utilisé aussi par d'autres pages) — inchangé ici, hors
// périmètre de ce correctif précis, mais bien exclue du blob logx_config par
// la même liste (elle y figurait sous la clé 'api_key').
const SECRET_CONFIG_FIELDS = ['api_key', 'clublog_api_key', 'clublog_password',
  'eqsl_password', 'lan_sync_token', 'lotw_password', 'on4kst_password',
  'qrz_password', 'qrzcq_api_key', 'hrdlog_code', 'qrz_logbook_key', 'sota_client_id',
  'cloudsync_secret', 'voicekeyer_ai_api_key', 'mysql_password'];

// Ré-assainit un blob localStorage['logx_config'] écrit par une VERSION
// ANTÉRIEURE du logiciel (avant ce correctif), qui pouvait encore contenir
// des secrets en clair — sans ça, le simple fait de ne plus les y ÉCRIRE
// laisserait ceux déjà présents sur le poste indéfiniment.
function _redactStaleSecretsInLocalStorage(){
  try{
    const raw = localStorage.getItem('logx_config');
    if(!raw) return;
    const c = JSON.parse(raw);
    let touched = false;
    for(const f of SECRET_CONFIG_FIELDS){
      if(f in c){ delete c[f]; touched = true; }
    }
    if(touched) localStorage.setItem('logx_config', JSON.stringify(c));
  }catch(e){ /* JSON invalide : loadSavedConfig() le signalera déjà */ }
}

// Rapatrie les secrets depuis le serveur (authentifié) pour pré-remplir les
// champs correspondants — le pendant de leur retrait de localStorage.
// Appelée APRÈS loadSavedConfig()/loadFromServerConfig() : ne fait que
// COMPLÉTER les champs secrets, jamais écraser le reste du formulaire déjà
// posé. Best-effort : hors-ligne ou non authentifié, les champs restent
// simplement vides comme avant ce correctif (l'opérateur les ressaisit).
// 'api_key' est délibérément SAUTÉ ici : le serveur n'a qu'UNE seule clé API
// globale (current_config['api_key']) alors que le client gère PLUSIEURS
// clés par fournisseur (logx_apikey_<provider> dans localStorage, déjà posée
// dans #api_key par onProviderChange()/applyFullConfigToForm() avant l'appel
// à cette fonction) — repeupler sans condition depuis le serveur écraserait
// la bonne valeur par-fournisseur avec la mauvaise valeur globale.
async function loadSecretsFromServer(){
  try{
    const res = await fetch('/config/secrets');
    if(!res.ok) return;
    const secrets = await res.json();
    for(const f of SECRET_CONFIG_FIELDS){
      if(f === 'api_key') continue;
      const v = secrets[f];
      const el = document.getElementById(f);
      // « Complète, n'écrase jamais » : ne poser la valeur serveur que si le
      // champ est encore vide (pas déjà rempli par un autre mécanisme).
      if(el && v && !el.value) el.value = v;
    }
  }catch(e){ /* pas de réseau/serveur : champs laissés vides, comportement inchangé */ }
}

// ─── CHARGEMENT CONFIG ───────────────────────────────────────────────────────
// Correctif H1 : l'ancienne applyConfigToForm() (~40 champs) utilisée par
// loadProfile() a été retirée — la restauration complète est maintenant
// applyFullConfigToForm(), partagée avec loadSavedConfig() (voir plus bas,
// recherche du même nom), pour que changer de profil restaure aussi les
// identifiants QRZ/eQSL/LoTW/ClubLog/QRZCQ/HRDLog, le pilotage radio/ampli/
// rotor, WSJT-X, le réseau ADIF, le keyer vocal, scoreboard/backup/cloud
// sync et les alertes personnalisées.

// ─── POSITION DYNAMIQUE DU PANNEAU/ARBORESCENCE CONFIG ──────────────────────
// .cat-modal-box/.config-sidebar (position:fixed) doivent démarrer SOUS
// header+nav+statusbar, dont la hauteur combinée n'est PAS fixe (statusbar
// injectée par logx_statusbar.js après un fetch async, flex-wrap:wrap donc
// peut passer sur 2 lignes sur fenêtre étroite) — un top:X% en dur avait
// laissé le panneau recouvrir la nav (dont LOGBOOK) et la statusbar aux
// résolutions courantes, en violation de la règle CLAUDE.md « chemin
// critique jamais cachable » (trouvé par la revue adversariale du
// 08/08/2026, la vérification navigateur initiale n'avait testé qu'un point
// tombant par hasard sur le seul lien de nav épargné). Mesurée en JS et
// tenue à jour par ResizeObserver — pas seulement au chargement — puisque
// le contenu de la statusbar peut changer de hauteur après coup.
function _updateConfigPanelTop(){
  const ref = document.getElementById('rcStatusBar') || document.querySelector('.app-nav');
  if(!ref) return;
  const bottom = ref.getBoundingClientRect().bottom;
  document.documentElement.style.setProperty('--config-panel-top', Math.max(bottom, 0) + 12 + 'px');
}
_updateConfigPanelTop();
window.addEventListener('resize', _updateConfigPanelTop);
if(typeof ResizeObserver !== 'undefined'){
  const _configPanelTopObserver = new ResizeObserver(_updateConfigPanelTop);
  const _navEl = document.querySelector('.app-nav');
  const _statusBarEl = document.getElementById('rcStatusBar');
  if(_navEl) _configPanelTopObserver.observe(_navEl);
  if(_statusBarEl) _configPanelTopObserver.observe(_statusBarEl);
  // La statusbar est injectée APRÈS le chargement de logx_statusbar.js, en
  // principe déjà présente ici (script bloquant chargé avant ce bloc) —
  // filet de sécurité si jamais l'ordre changeait un jour.
  else document.addEventListener('DOMContentLoaded', _updateConfigPanelTop);
}

// ─── INIT ────────────────────────────────────────────────────────────────────
async function init() {
  await maybeShowOnboarding(); // écran d'accueil (première visite) — résout tout de suite sinon
  applyUiMode(); // Mode débutant/expert (avant tout rendu)
  buildContestGrid();
  onProviderChange(); // Initialise le select modèle (Anthropic par défaut)
  _redactStaleSecretsInLocalStorage(); // avant lecture : purge un blob pré-correctif
  const hasLocal = loadSavedConfig();
  if (!hasLocal) await loadFromServerConfig();
  loadSecretsFromServer(); // best-effort, ne bloque pas le reste de l'init (fire-and-forget)
  applyUsageMode(); // Sûr même si aucune config n'a encore été chargée (défaut 'contest')
  updateOpRowControls(); // État initial des boutons +/- opérateurs (au cas où aucune config n'a encore été restaurée)
  // Sélecteur unifié : enrichir avec la base serveur + WA7BNM puis re-render
  await Promise.all([mergeServerContests(), mergeExternalContests()]);
  buildContestGrid(document.getElementById('contestSearch').value || '');
  populateImportContestSelect();
  // Re-marquer la carte du concours sauvegardé (le re-render l'a reconstruite)
  if (state.contest) {
    const card = document.getElementById('card_' + state.contest);
    if (card) card.classList.add('selected');
  }
  // Panneau par défaut au chargement : plus de hub d'accueil depuis la
  // refonte sidebar du 08/08/2026 — Identité est la 1re étape du chemin
  // critique (indicatif), donc le point d'entrée le plus logique. Un
  // deep-link ?contest=ID (juste après) prend le dessus si présent.
  openCategoryPopup('identity');
  handleContestParam(); // Assistant : ?contest=ID depuis le calendrier
  renderParcStation(); // Parc antennes/rotors/amplis (vide si jamais configuré)
  updateCatModelOptions(); updateCatModeVisibility(); refreshCatPorts(); // Radio CAT native
  updateCat2ModeVisibility(); // Radio 2 (SO2R)
  loadVoiceKeyerDevices();
  loadDxRecord();
  updateAmpFieldsVisibility(); refreshAmpPorts(); // Amplificateur HF
  // Correctif M5 : refléter l'état Activé/Désactivé sur les champs dépendants
  // dès l'affichage initial (pas seulement au changement manuel du select).
  updateEnabledFieldsVisibility('amp_enabled', ['amp_brand','amp_conn_mode','amp_port','amp_baudrate','amp_civ_addr','amp_host','amp_net_port']);
  updateEnabledFieldsVisibility('rotor_enabled', ['rotor_brand','rotor_model','rotor_proto','rotor_host','rotor_port']);
  updateEnabledFieldsVisibility('cloudsync_mode', ['cloudsync_folder','cloudsync_interval','cloudsync_secret'], v => v !== '');
  updateEnabledFieldsVisibility('mysql_mode', ['mysql_host','mysql_port','mysql_user','mysql_password','mysql_database'], v => v !== 'off');
  updateEnabledFieldsVisibility('pgxl_enabled', ['pgxl_host','pgxl_port','pgxl_timeout']);
  updateEnabledFieldsVisibility('acom_enabled', ['acom_port','acom_model','acom_timeout']);
  updateEnabledFieldsVisibility('telemetry_enabled', ['telemetry_endpoint']);
  validateActivationRef(); // Si une référence est déjà enregistrée, la vérifier contre la base au chargement
  _updateActivationNearbyVisibility();
  _updateSotaSectionVisibility(); refreshSotaStatus(); // au cas où loadFromServerConfig() a été utilisé (pas de config locale)
  const sotaHint = document.getElementById('sotaRedirectUriHint');
  if (sotaHint) sotaHint.textContent = `http://localhost:${window.location.port || 8080}/sota/oauth/callback`;
  refreshAccessPasswordStatus(); // Mot de passe d'accès optionnel (section RÉSEAU)
  renderConfigTree(); // Arborescence de réglages : badges d'état initiaux
}

// ─── SOTA : recherche/validation de sommet contre la vraie base ─────────────
// logx_activation.py ne vérifiait que le FORMAT (regex) de MA RÉFÉRENCE
// ACTIVÉE, jamais si le sommet existe réellement. La base (181 000 sommets,
// storage.sota.org.uk/summitslist.csv) se charge en tâche de fond côté
// serveur — ces fonctions gèrent l'état "pas encore prêt" sans jamais
// bloquer la saisie (la référence reste éditable manuellement à tout moment,
// que la base soit chargée, en cours de chargement, ou injoignable).
let _activationSearchTimer = null;

// Un seul programme (POTA/SOTA/WWFF/IOTA) a un point GPS unique et fiable ;
// IOTA n'a que le centre d'une boîte englobante (approximatif) ; WCA n'a
// aucune coordonnée dans sa source (nearby désactivé) ; ARLHS n'a pas de
// base téléchargée du tout (permission de réutilisation non obtenue — cf.
// logx_wca.py/logx_iota.py pour le détail des sources), donc absent d'ici :
// la saisie reste alors une simple validation de FORMAT (regex), comme avant.
const ACTIVATION_DB_PROGRAMS = {
  POTA: {hasNearby:true,
    line:e=>`${_vkEsc(e.name)} <span style="color:var(--muted)">(${_vkEsc(e.location)})</span>`,
    plain:e=>`${e.name} (${e.location})`},
  SOTA: {hasNearby:true,
    line:e=>`${_vkEsc(e.name)} <span style="color:var(--muted)">(${e.alt_m} m, ${e.points} pts, ${_vkEsc(e.region)})</span>`,
    plain:e=>`${e.name} — ${e.alt_m} m, ${e.points} pts (${e.region})`},
  WWFF: {hasNearby:true,
    line:e=>`${_vkEsc(e.name)} <span style="color:var(--muted)">(${_vkEsc(e.country||e.region)})</span>`,
    plain:e=>`${e.name} (${e.country||e.region})`},
  IOTA: {hasNearby:true,
    line:e=>`${_vkEsc(e.name)}`,
    plain:e=>`${e.name}`},
  WCA:  {hasNearby:false,
    line:e=>`${_vkEsc(e.name)} <span style="color:var(--muted)">(${_vkEsc(e.location)})</span>`,
    plain:e=>`${e.name} (${e.location})`},
};

function _activationProgram(){
  const el = document.getElementById('activation_program');
  return el ? el.value : '';
}

function onActivationProgramChange(){
  const el = document.getElementById('activationValidation');
  if (el) el.textContent = '';
  hideActivationSuggestions();
  _renderWcaGeocodedInfo(null); // changement de programme : plus de château affiché
  const spec = ACTIVATION_DB_PROGRAMS[_activationProgram()];
  _updateActivationNearbyVisibility();
  _updateSotaSectionVisibility();
  if (spec) validateActivationRef();
}

// ─── AUTO-SPOT SOTA (SOTA SSO + api2.sota.org.uk, cf. logx_sota_spot.py) ─────
function _updateSotaSectionVisibility(){
  const section = document.getElementById('sotaAutoSpotSection');
  if (section) section.style.display = (_activationProgram() === 'SOTA') ? '' : 'none';
}

async function refreshSotaStatus(){
  const el = document.getElementById('sotaAuthStatus');
  if (!el) return;
  try{
    const r = await fetch('/sota/status');
    const d = await r.json();
    if (!d.configured) el.textContent = 'Non configuré (clientId manquant)';
    else if (!d.ai_approval_ack) el.textContent = '⚠️ Accord IA non coché (voir ci-dessus)';
    else if (d.authenticated) el.textContent = '✅ Connecté à SOTA';
    else el.textContent = 'Configuré — clique « Se connecter à SOTA »';
  }catch(e){ el.textContent = 'État inconnu'; }
}

async function connectSota(){
  // Le serveur lit sota_client_id depuis SA config déjà sauvegardée
  // (current_config) — on sauvegarde silencieusement et on ATTEND que le
  // serveur ait bien reçu cette config (même pattern que testVoiceKeyer())
  // avant d'ouvrir la fenêtre de connexion, sinon la fenêtre OAuth peut
  // démarrer avec un clientId périmé (course entre le fetch de sauvegarde
  // et l'ouverture de /sota/oauth/start).
  const clientId = document.getElementById('sota_client_id')?.value.trim();
  if (!clientId){ _configToast(T('Renseigne d\'abord le clientId SOTA ci-dessus.')); return; }
  saveConfig(true);
  await _lastConfigSavePromise;
  window.open('/sota/oauth/start', 'sota_oauth',
    'width=520,height=680,menubar=no,toolbar=no,location=yes');
  setTimeout(refreshSotaStatus, 4000);   // laisse le temps de finir la connexion
}

// Le bloc "À PROXIMITÉ" reste visible pour tout programme dont la base est
// chargée côté serveur (recherche par nom toujours possible), même quand la
// recherche par distance elle-même n'a pas de sens faute de coordonnées GPS
// dans la source (WCA) — sinon le bouton disparaît silencieusement et
// ressemble à un bug plutôt qu'à une limite documentée de la source.
function _updateActivationNearbyVisibility(){
  const spec = ACTIVATION_DB_PROGRAMS[_activationProgram()];
  const block = document.getElementById('activationNearbyBlock');
  const searchRow = document.getElementById('activationNearbySearchRow');
  const unavailable = document.getElementById('activationNearbyUnavailable');
  if (!block) return;
  block.style.display = spec ? '' : 'none';
  if (searchRow) searchRow.style.display = (spec && spec.hasNearby) ? '' : 'none';
  if (unavailable) unavailable.style.display = (spec && !spec.hasNearby) ? '' : 'none';
}

// Échappe une valeur pour un usage sûr à la fois comme argument d'une
// fonction JS et dans un attribut HTML (onclick="...", onmousedown="...") :
// JSON.stringify() produit un littéral JS valide (échappe guillemets/
// antislashs), puis _vkEsc() échappe les guillemets doubles restants en
// entités HTML pour qu'ils ne referment pas prématurément l'attribut.
// e.code vient de la base d'activation externe (POTA/SOTA/WWFF/IOTA,
// /activation_db/nearby et /activation_db/search) : contenu tiers non
// maîtrisé, ne jamais l'interpoler brut dans un attribut HTML.
function jsAttrArg(v){ return _vkEsc(JSON.stringify(String(v == null ? '' : v))); }

async function loadNearbyActivationRefs(){
  const program = _activationProgram();
  const spec = ACTIVATION_DB_PROGRAMS[program];
  const list = document.getElementById('activationNearbyList');
  const maxKm = parseInt(document.getElementById('activationNearbyMaxKm').value, 10) || 60;
  if (!spec) return;
  list.innerHTML = '<div style="padding:8px 4px;font-family:var(--font-mono);font-size:12px;color:var(--muted)">Recherche…</div>';
  try{
    const r = await fetch(`/activation_db/nearby?program=${program}&max_km=${maxKm}`);
    const d = await r.json();
    if (!d.status || !d.status.ready){
      list.innerHTML = '<div style="padding:8px 4px;font-family:var(--font-mono);font-size:12px;color:var(--muted)"><svg style="width:12px;height:12px;vertical-align:-1px;margin-right:4px" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="9" r="6.5"/><line x1="9" y1="9" x2="9" y2="5"/><line x1="9" y1="9" x2="12" y2="10.5"/></svg>Chargement de la base (peut prendre jusqu\'à une minute la première fois)…</div>';
      return;
    }
    const entries = d.entries || [];
    if (!entries.length){
      list.innerHTML = `<div style="padding:8px 4px;font-family:var(--font-mono);font-size:12px;color:var(--muted)">Aucune référence à moins de ${maxKm} km — renseigne ton locator dans « MA STATION » ou élargis le rayon.</div>`;
      return;
    }
    list.innerHTML = entries.map(e => `
      <div onclick="pickActivationRef(${jsAttrArg(e.code)})" style="padding:7px 10px;cursor:pointer;font-family:var(--font-mono);font-size:13px;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;gap:10px">
        <span><b style="color:var(--accent2)">${_vkEsc(e.code)}</b> — ${spec.line(e)}</span>
        <span style="color:var(--muted);white-space:nowrap">${e.dist_km.toFixed(1)} km · ${e.cardinal}</span>
      </div>`).join('');
  }catch(e){
    list.innerHTML = '<div style="padding:8px 4px;font-family:var(--font-mono);font-size:12px;color:var(--red)"><svg style="width:12px;height:12px;vertical-align:-1px;margin-right:4px" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg>Recherche indisponible</div>';
  }
}

function onActivationRefInput(){
  const elv = document.getElementById('activationValidation');
  if (elv) elv.textContent = '';
  _renderWcaGeocodedInfo(null); // la saisie change : l'ancienne position géocodée n'est plus fiable
  const program = _activationProgram();
  if (!ACTIVATION_DB_PROGRAMS[program]) { hideActivationSuggestions(); return; }
  const val = document.getElementById('my_activation_ref').value.trim();
  clearTimeout(_activationSearchTimer);
  if (val.length < 2) { hideActivationSuggestions(); return; }
  _activationSearchTimer = setTimeout(() => searchActivationRefs(program, val), 300);
}

async function searchActivationRefs(program, query){
  const spec = ACTIVATION_DB_PROGRAMS[program];
  const box = document.getElementById('activationSuggestions');
  if (!spec) { hideActivationSuggestions(); return; }
  try{
    const r = await fetch(`/activation_db/search?program=${program}&q=` + encodeURIComponent(query));
    const d = await r.json();
    if (!d.status || !d.status.ready){
      box.style.display = 'block';
      box.innerHTML = '<div style="padding:8px 12px;font-family:var(--font-mono);font-size:12px;color:var(--muted)"><svg style="width:12px;height:12px;vertical-align:-1px;margin-right:4px" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="9" r="6.5"/><line x1="9" y1="9" x2="9" y2="5"/><line x1="9" y1="9" x2="12" y2="10.5"/></svg>Chargement de la base (peut prendre jusqu\'à une minute la première fois)…</div>';
      return;
    }
    const results = d.results || [];
    if (!results.length) { hideActivationSuggestions(); return; }
    box.style.display = 'block';
    box.innerHTML = results.map(e => `
      <div onmousedown="pickActivationRef(${jsAttrArg(e.code)})" style="padding:7px 12px;cursor:pointer;font-family:var(--font-mono);font-size:13px;border-bottom:1px solid var(--border)">
        <b style="color:var(--accent2)">${_vkEsc(e.code)}</b> — ${spec.line(e)}
      </div>`).join('');
  }catch(e){ hideActivationSuggestions(); }
}

function pickActivationRef(code){
  document.getElementById('my_activation_ref').value = code;
  hideActivationSuggestions();
  validateActivationRef();
}

function hideActivationSuggestions(){
  const box = document.getElementById('activationSuggestions');
  if (box) { box.style.display = 'none'; box.innerHTML = ''; }
}

async function validateActivationRef(){
  const el = document.getElementById('activationValidation');
  if (!el) return;
  const program = _activationProgram();
  const spec = ACTIVATION_DB_PROGRAMS[program];
  if (!spec) { el.textContent = ''; _renderWcaGeocodedInfo(null); return; }
  const ref = document.getElementById('my_activation_ref').value.trim().toUpperCase();
  if (!ref) { el.textContent = ''; _renderWcaGeocodedInfo(null); return; }
  try{
    const r = await fetch(`/activation_db/lookup?program=${program}&ref=` + encodeURIComponent(ref));
    const d = await r.json();
    if (!d.status || !d.status.ready){
      el.textContent = '⏳ Vérification en attente du chargement de la base…';
      el.style.color = 'var(--muted)';
      return;
    }
    if (d.entry){
      el.textContent = `✅ ${spec.plain(d.entry)}`;
      el.style.color = 'var(--green)';
    } else {
      el.textContent = `⚠️ Référence non trouvée dans la base ${program} — vérifie l'orthographe, ou c'est une entrée récente pas encore répertoriée (la saisie reste valable)`;
      el.style.color = 'var(--yellow)';
    }
    // WCA seul : le lookup serveur géocode à la demande LA référence trouvée
    // (cf. logx_wca.get_castle_geocoded) — les autres programmes ont déjà
    // leurs propres coordonnées et n'en ont pas besoin ici.
    _renderWcaGeocodedInfo(program === 'WCA' ? d.entry : null);
  }catch(e){ el.textContent = ''; _renderWcaGeocodedInfo(null); }
}

// Affiche la position géocodée (Nominatim) de MON château WCA + distance/
// azimut depuis ma station (mêmes formules que le reste de la page), pour
// donner à WCA la même info « où est ma référence » que les 5 autres
// programmes tirent nativement de leur base — sans jamais avoir géocodé
// autre chose que cette seule référence (cf. logx_wca.geocode_castle).
function _renderWcaGeocodedInfo(entry){
  const box = document.getElementById('activationWcaGeocoded');
  if (!box) return;
  if (!entry || entry.lat == null || entry.lon == null) { box.innerHTML = ''; return; }
  let distTxt = '';
  const loc = locatorToLatLon((document.getElementById('locator') || {}).value || '');
  if (loc){
    const km = _haversineKm(loc.lat, loc.lon, entry.lat, entry.lon);
    const az = _bearingDeg(loc.lat, loc.lon, entry.lat, entry.lon);
    distTxt = ` — ${km} km · ${az}° (${_cardinalDir(az)}) depuis ta station`;
  }
  const mapUrl = `https://www.openstreetmap.org/?mlat=${entry.lat}&mlon=${entry.lon}#map=14/${entry.lat}/${entry.lon}`;
  box.innerHTML = `<svg style="width:12px;height:12px;vertical-align:-1px;margin-right:4px" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 16s5.5-5.8 5.5-9.5A5.5 5.5 0 0 0 3.5 6.5C3.5 10.2 9 16 9 16z"/><circle cx="9" cy="6.5" r="1.6" fill="currentColor" stroke="none"/></svg>Position géocodée (Nominatim) : ${entry.lat.toFixed(4)}, ${entry.lon.toFixed(4)}` +
    `${distTxt} · <a href="${_vkEsc(mapUrl)}" target="_blank" rel="noopener">voir sur la carte</a>`;
}

// ─── KEYER VOCAL : périphériques audio + voix TTS (chargés une fois) ────────
function _vkEsc(v){
  return String(v == null ? '' : v).replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

// ─── RECORD DX (calculé serveur depuis le vrai log, remplace l'ancien champ
// manuel record_dx) ───────────────────────────────────────────────────────
let _dxRecordCache = null;

function _dxRecordSummaryText(){
  return (_dxRecordCache && _dxRecordCache.overall) ? _dxRecordCache.overall.dist_km : '—';
}

async function loadDxRecord(){
  const el = document.getElementById('dxRecordDisplay');
  try{
    const r = await fetch('/data/dx_records');
    const d = await r.json();
    _dxRecordCache = d;
    if(!el) return;
    const o = d.overall;
    el.textContent = o
      ? `${o.dist_km} km — ${o.band} MHz, ${o.call}${o.date ? ' (' + o.date + ')' : ''}`
      : 'Aucun QSO avec locator archivé pour le moment';
  }catch(e){
    if(el) el.textContent = 'Indisponible (serveur injoignable)';
  }
}

// Devine si un nom de périphérique audio ressemble à un câble virtuel/une
// interface dédiée (ce qu'il FAUT choisir ici, voir le texte d'aide
// au-dessus du sélecteur) plutôt qu'à une sortie physique (haut-parleurs/
// casque, à éviter). Heuristique sur le NOM SEUL : PortAudio/sounddevice ne
// distingue pas "virtuel" de "physique" autrement — jamais fiable à 100%,
// donc on GROUPE plutôt qu'on ne masque (un setup atypique reste choisissable).
function _vkIsLikelyVirtual(name){
  const n = (name || '').toLowerCase();
  return /vb-?audio|vb-?cable|\bcable\b|\bvac\b|virtual|voicemeeter|microham|signalink|rigblaster|digirig|\bvoicetronic\b/.test(n);
}

async function loadVoiceKeyerDevices(){
  const devSel = document.getElementById('voicekeyer_device');
  const voiceSel = document.getElementById('voicekeyer_voice_id');
  // Radio 2 (SO2R, Phase 2) : optionnel — absent des pages qui n'ont pas cette
  // section (aucune pour l'instant, mais ce champ pourrait un jour être omis
  // en mode débutant, d'où le test null-safe comme les autres champs cat2_*).
  const devSel2 = document.getElementById('voicekeyer_device2');
  if(!devSel || !voiceSel) return;
  try{
    const r = await fetch('/voicekeyer/devices');
    if(!r.ok) throw new Error('http ' + r.status);
    const d = await r.json();
    const devices = d.devices || [];
    const virtuels = devices.filter(x => _vkIsLikelyVirtual(x.name));
    const autres = devices.filter(x => !_vkIsLikelyVirtual(x.name));
    const optHtml = x => `<option value="${x.index}">${_vkEsc(x.name)}</option>`;
    const optionsHtml = (virtuels.length ? `<optgroup label="Câbles virtuels / interfaces (recommandé)">${virtuels.map(optHtml).join('')}</optgroup>` : '')
      + (autres.length ? `<optgroup label="Autres sorties (haut-parleurs, casque…)">${autres.map(optHtml).join('')}</optgroup>` : '');
    devSel.innerHTML = '<option value="">— périphérique par défaut —</option>' + optionsHtml;
    voiceSel.innerHTML = '<option value="">— voix par défaut —</option>'
      + (d.voices || []).map(x => `<option value="${_vkEsc(x.id)}">${_vkEsc(x.name)}${x.lang ? ' (' + _vkEsc(x.lang) + ')' : ''}</option>`).join('');
    // Même parc de périphériques (un seul PC serveur) : pas de second appel réseau.
    if(devSel2) devSel2.innerHTML = '<option value="">— même périphérique que la radio 1 —</option>' + optionsHtml;
  }catch(e){
    devSel.innerHTML = '<option value="">indisponible (sounddevice non installé ?)</option>';
    voiceSel.innerHTML = '<option value="">indisponible (pyttsx3 non installé ?)</option>';
    if(devSel2) devSel2.innerHTML = '<option value="">indisponible (sounddevice non installé ?)</option>';
  }
  // Ré-applique les valeurs sauvegardées maintenant que les <option> existent
  try{
    const cfg = JSON.parse(localStorage.getItem('logx_config') || '{}');
    if(cfg.voicekeyer_device !== undefined) devSel.value = cfg.voicekeyer_device;
    if(cfg.voicekeyer_voice_id !== undefined) voiceSel.value = cfg.voicekeyer_voice_id;
    if(devSel2 && cfg.voicekeyer_device2 !== undefined) devSel2.value = cfg.voicekeyer_device2;
  }catch(e){}
}

async function testVoiceKeyer(){
  const out = document.getElementById('voiceKeyerTestResult');
  // Le serveur teste toujours la DERNIÈRE config qu'il a reçue via /config/save,
  // jamais ce qui est affiché à l'écran — sans ça, changer KEYER VOCAL sur
  // "Activé" puis cliquer Tester sans être passé par SAUVEGARDER échoue avec
  // "Keyer vocal désactivé (CONFIG)" alors que le sélecteur affiche "Activé".
  // On sauvegarde donc (silencieux, permissif) et on ATTEND que le serveur
  // ait bien reçu cette config avant de lancer le test dessus.
  if(out){ out.textContent = '⏳ synchronisation de la config…'; out.style.color = 'var(--muted)'; }
  saveConfig(true);
  await _lastConfigSavePromise;
  if(out){ out.textContent = '⏳ test en cours…'; out.style.color = 'var(--muted)'; }
  try{
    // skip_ptt : ce bouton ne fait que PRÉVISUALISER le périphérique/la voix
    // choisis — il ne doit jamais exiger que le pilotage radio soit déjà
    // configuré, ni engager le PTT pour autant (retour F4GLD 04/08/2026 :
    // le test échouait systématiquement tant que CAT n'était pas réglé,
    // alors qu'on veut juste vérifier le son). L'indicatif testé vient du
    // champ à côté du bouton (retour F4GLD 04/08/2026 : pouvoir vérifier
    // l'épellation phonétique sur SON PROPRE indicatif, pas juste F8TEST) —
    // vide = F8TEST par défaut, comme avant.
    const testCallInput = document.getElementById('voiceKeyerTestCall');
    const testCall = (testCallInput && testCallInput.value.trim()) || 'F8TEST';
    const r = await fetch('/rig/voice', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({template: '{CALL} {DE} {MYCALL}, {RST_SENT}',
        call: testCall, mycall: document.getElementById('callsign').value || 'F1TEST', rst_sent: '59',
        skip_ptt: true})});
    const d = await r.json();
    if(out){
      out.textContent = d.ok ? `✅ Lu (sans PTT) : « ${d.text} »` : `❌ ${d.error}`;
      out.style.color = d.ok ? 'var(--green)' : 'var(--red)';
    }
  }catch(e){
    if(out){ out.textContent = '❌ ' + e.message; out.style.color = 'var(--red)'; }
  }
}

// ─── RADIO CAT NATIVE (pilotage direct, sans Hamlib) ─────────────────────────
// Miroir client de logx_cat.py (CIV_ADDRESSES / ASCII_ID_TABLE /
// BRAND_BY_MODEL) — garder synchronisé si la liste des modèles évolue côté
// serveur. Les adresses CI-V servent juste d'indication (valeurs usine,
// modifiables sur la radio) ; le pilote lit toujours la valeur du champ.
const CAT_MODELS = {
  icom: [
    ['IC-705','A4'], ['IC-706MKIIG','58'], ['IC-7000','70'], ['IC-7100','88'],
    ['IC-718','5E'], ['IC-7200','76'], ['IC-7300','94'], ['IC-7410','80'],
    ['IC-746','56'], ['IC-746PRO','66'],
    ['IC-756','50'], ['IC-756PRO','5C'], ['IC-756PROII','64'], ['IC-756PROIII','6E'],
    ['IC-7600','7A'], ['IC-7610','98'], ['IC-7700','74'], ['IC-7800','6A'],
    ['IC-7851','8E'], ['IC-905','AC'], ['IC-910H','60'],
    ['IC-9100','7C'], ['IC-9700','A2'],
    ['IC-R75','5A'], ['IC-R8600','96'],
  ],
  xiegu: [['XIEGU-G90','70'], ['XIEGU-G106','70'], ['XIEGU-X6100','A4'], ['XIEGU-X5105','70']],
  // Yaesu a DEUX protocoles CAT selon l'epoque du poste, et le pilote natif
  // n'en parle qu'un.
  //   - famille ASCII (FT-891, FT-991/991A, FTDX10, FTDX101) : 2 lettres + ';'
  //   - famille BINAIRE 5 octets (FT-817/818/857/897, FT-847, FT-100) :
  //     commandes de longueur fixe, le dernier octet est l'opcode.
  // Les quatre postes binaires etaient proposes ici alors que le pilote natif
  // leur envoyait « IF; » : ils ne repondent JAMAIS, sans le moindre message
  // d'erreur cote radio. Ils restent dans la liste — les faire disparaitre
  // laisserait leur proprietaire sans reponse — mais marques, et le pilotage
  // passe par le mode rigctld/Hamlib, qui les gere parfaitement.
  yaesu: [
    ['FT-891'],['FT-991'],['FT-991A'],['FTDX10'],['FTDX101D'],['FTDX101MP'],
    ['FT-817', '', 'hamlib'],['FT-818', '', 'hamlib'],
    ['FT-857', '', 'hamlib'],['FT-897', '', 'hamlib'],
  ],
  kenwood: [['TS-480'],['TS-570'],['TS-2000'],['TS-590S'],['TS-590SG'],['TS-890S'],['TS-990S']],
  elecraft: [['K2'],['K3'],['K3S'],['KX2'],['KX3'],['K4']],
};
const CAT_DEFAULT_BAUD = { icom: 19200, xiegu: 19200, yaesu: 4800, kenwood: 9600, elecraft: 38400 };

// Comptes affichés dans le bloc "Quel mode choisir ?" — calculés depuis
// CAT_MODELS pour ne jamais désynchroniser le texte de la vraie liste.
(function fillCatDocCounts(){
  const set = (id, n) => { const el = document.getElementById(id); if(el) el.textContent = n; };
  set('catDocIcomCount', CAT_MODELS.icom.length + CAT_MODELS.xiegu.length);
  set('catDocYaesuCount', CAT_MODELS.yaesu.length);
  set('catDocKenwoodCount', CAT_MODELS.kenwood.length);
  set('catDocElecraftCount', CAT_MODELS.elecraft.length);
})();

function updateCatModeVisibility(){
  const mode = document.getElementById('cat_mode').value;
  document.getElementById('catNativeFields').style.display = mode === 'native' ? '' : 'none';
  document.getElementById('catTciFields').style.display = mode === 'tci' ? '' : 'none';
  document.getElementById('catRigctldFields').style.display = mode === 'rigctld' ? '' : 'none';
  document.getElementById('catFlrigFields').style.display = mode === 'flrig' ? '' : 'none';
  document.getElementById('catOmnirigFields').style.display = mode === 'omnirig' ? '' : 'none';
  document.getElementById('catFlexFields').style.display = mode === 'flex' ? '' : 'none';
  document.getElementById('catIcomRemoteFields').style.display = mode === 'icom_remote' ? '' : 'none';
}

// SO2R Phase 1 (MVP logiciel-seul) : le CAT natif série est un singleton --
// basculer le focus vers la radio 2 FERME la connexion à la radio 1, donc
// natif est inutilisable en usage SO2R réel (écoute simultanée des deux
// radios). OmniRig n'a pas ce verrou (voir docs/ETUDE_SO2R.md §3) : seuls
// ces deux modes sont proposés pour la radio 2, pas les 5 autres backends de
// la radio 1 (TCI/rigctld/flrig/flex/icom_remote restent hors périmètre).
function updateCat2ModeVisibility(){
  const mode = document.getElementById('cat2_mode').value;
  document.getElementById('cat2NativeFields').style.display = mode === 'omnirig' ? 'none' : '';
  document.getElementById('cat2OmnirigFields').style.display = mode === 'omnirig' ? '' : 'none';
}

function updateCatModelOptions(){
  const brand = document.getElementById('cat_brand').value;
  const sel = document.getElementById('cat_model');
  const models = CAT_MODELS[brand] || [];
  // m[2] === 'hamlib' : poste que le pilote NATIF ne sait pas commander (voir
  // le commentaire de CAT_MODELS). Le dire dans l'intitule, sinon l'operateur
  // choisit son poste, ne voit rien venir, et cherche un probleme de cable.
  // LA SÉLECTION EST PRÉSERVÉE À TRAVERS LA RECONSTRUCTION.
  //
  // DÉFAUT SIGNALÉ PAR F4GLD : « je choisis une radio, je sauvegarde, je vais
  // au logbook, je reviens et ma radio n'est plus sélectionnée ». Cause :
  // init() restaure la config (qui pose bien la marque ET le modèle), puis
  // rappelle updateCatModelOptions() quelques lignes plus bas. Réécrire
  // innerHTML remet un <select> sur sa PREMIÈRE option — le modèle enregistré
  // était donc perdu à chaque retour sur la page, sans le moindre message.
  const modelePrecedent = sel.value || (window._cfgRestauree || {}).cat_model || '';
  sel.innerHTML = models.map(m => `<option value="${m[0]}">${m[0]}${
    m[2] === 'hamlib' ? ' — via rigctld/Hamlib' : ''}</option>`).join('');
  if (modelePrecedent && models.some(m => m[0] === modelePrecedent)) {
    sel.value = modelePrecedent;
  }
  const note = document.getElementById('catAddrNote');
  const isCiv = (brand === 'icom' || brand === 'xiegu');
  document.getElementById('catCivAddrField').style.display = isCiv ? '' : 'none';
  if (isCiv && models.length){
    note.textContent = `Adresse CI-V usine : ${models[0][1]} (modifiable sur la radio — indique la nouvelle adresse dans le champ « ADRESSE CI-V (avancé) » si besoin)`;
  } else {
    note.textContent = '';
  }
  const baud = document.getElementById('cat_baudrate');
  if (!baud.value) baud.value = CAT_DEFAULT_BAUD[brand] || 19200;
  updateCatAddrNoteForModel();
}

function updateCatAddrNoteForModel(){
  const brand = document.getElementById('cat_brand').value;
  const model = document.getElementById('cat_model').value;
  const note = document.getElementById('catAddrNote');
  const entry = (CAT_MODELS[brand] || []).find(m => m[0] === model);
  if (entry && entry[2] === 'hamlib'){
    note.textContent = `${model} : protocole CAT binaire 5 octets, que le pilotage `
      + `natif ne parle pas. Choisis le mode « rigctld / Hamlib » plus haut — `
      + `Hamlib gère ce poste parfaitement.`;
    return;
  }
  // VITESSE : 4800 est le repli par defaut de la marque Yaesu, et c'est la
  // valeur d'usine des FT-8x7 et des Yaesu historiques (FT-840, FT-900,
  // FT-1000) — un repli sur pour un premier branchement.
  //
  // Mais le pilote NATIF ne gere justement PAS ces postes-la (CAT binaire, ils
  // passent par Hamlib). Les Yaesu qu'il gere — FT-891, FT-991/991A, FTDX10,
  // FTDX101 — sortent d'usine bien plus haut, 9600 ou 38400. Le champ
  // pre-rempli a 4800 les fait donc echouer... sur un « pas de reponse »
  // indiscernable d'un cable debranche.
  //
  // On ne devine PAS la valeur exacte par modele (elle depend du menu CAT
  // RATE, que l'operateur a pu changer) : on le DIT, et il regarde son poste.
  if (brand === 'yaesu' && entry){
    note.textContent = `Vérifie la vitesse : le champ propose 4800 bauds `
      + `(valeur d'usine des FT-8x7), mais un ${model} sort d'usine plus haut — `
      + `9600 ou 38400 selon le poste. La valeur est dans le menu CAT RATE de `
      + `la radio, et les deux doivent coïncider, sinon rien ne répond.`;
    return;
  }
  const isCiv = (brand === 'icom' || brand === 'xiegu');
  if (!isCiv) { note.textContent = ''; return; }
  note.textContent = entry ? `Adresse CI-V usine : ${entry[1]} (modifiable sur la radio — indique la nouvelle adresse dans le champ « ADRESSE CI-V (avancé) » si besoin)` : '';
}
document.addEventListener('DOMContentLoaded', () => {
  const modelSel = document.getElementById('cat_model');
  if (modelSel) modelSel.addEventListener('change', updateCatAddrNoteForModel);
});

async function refreshCatPorts(){
  const sel = document.getElementById('cat_port');
  // Le port enregistré sert de REPLI. Au chargement, la liste des ports arrive
  // du serveur APRÈS la restauration de la config : poser `.value` sur un
  // <select> encore vide échoue en silence, `sel.value` est alors vide, et le
  // port sauvegardé était perdu au profit du premier port détecté. Même
  // défaut que le modèle de radio, même remède.
  const prev = sel.value || (window._cfgRestauree || {}).cat_port || '';
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

// ─── AMPLIFICATEUR HF (Elecraft/Icom/SPE) ────────────────────────────────────
const AMP_DEFAULT_BAUD = {elecraft: 38400, icom: 19200, spe: 9600};

// Correctif M5 : les champs dépendants d'un toggle "Désactivé" (Ampli/Rotor/
// Cloud Sync) restaient pleinement éditables visuellement quand le toggle
// était sur Désactivé — aucune perte de donnée, mais aucun indice visuel
// que ces champs n'ont alors plus aucun effet.
function updateEnabledFieldsVisibility(toggleId, childIds, isEnabledFn){
  const toggle = document.getElementById(toggleId);
  if(!toggle) return;
  const enabled = isEnabledFn ? isEnabledFn(toggle.value) : toggle.value === '1';
  childIds.forEach(id => {
    const el = document.getElementById(id);
    if(!el) return;
    el.disabled = !enabled;
    const group = el.closest('.form-group');
    if(group) group.classList.toggle('field-disabled', !enabled);
  });
}

function updateAmpFieldsVisibility(){
  const brand = document.getElementById('amp_brand').value;
  document.getElementById('ampCivAddrField').style.display = brand === 'icom' ? '' : 'none';
  // Réseau TCP/UDP : uniquement le KPA1500 (port Ethernet natif documenté) —
  // Icom/SPE n'ont aucun accès réseau documenté, on les force en série.
  const connSel = document.getElementById('amp_conn_mode');
  document.getElementById('ampConnModeField').style.display = brand === 'elecraft' ? '' : 'none';
  if (brand !== 'elecraft' && connSel.value !== 'serial') connSel.value = 'serial';
  const isNetwork = brand === 'elecraft' && connSel.value !== 'serial';
  document.getElementById('ampPortField').style.display = isNetwork ? 'none' : '';
  document.getElementById('ampBaudField').style.display = isNetwork ? 'none' : '';
  document.getElementById('ampHostField').style.display = isNetwork ? '' : 'none';
  document.getElementById('ampNetPortField').style.display = isNetwork ? '' : 'none';
  const baud = document.getElementById('amp_baudrate');
  if (!baud.value) baud.value = AMP_DEFAULT_BAUD[brand] || 9600;
  const netPort = document.getElementById('amp_net_port');
  if (!netPort.value) netPort.value = 1500;
}

async function refreshAmpPorts(){
  const sel = document.getElementById('amp_port');
  // Même repli que refreshCatPorts : le port de l'ampli était perdu de la
  // même façon, la liste arrivant du serveur après la restauration.
  const prev = sel.value || (window._cfgRestauree || {}).amp_port || '';
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

async function testAmpConnection(){
  const result = document.getElementById('ampTestResult');
  const brand = document.getElementById('amp_brand').value;
  const connMode = brand === 'elecraft' ? document.getElementById('amp_conn_mode').value : 'serial';
  const isNetwork = connMode !== 'serial';
  const port = document.getElementById('amp_port').value;
  const host = document.getElementById('amp_host').value.trim();
  if (isNetwork && !host){
    result.textContent = '⚠️ Renseigne l\'adresse IP/hôte du KPA1500 d\'abord';
    result.style.color = 'var(--yellow)';
    return;
  }
  if (!isNetwork && !port){
    result.textContent = '⚠️ Choisis un port série d\'abord';
    result.style.color = 'var(--yellow)';
    return;
  }
  result.textContent = '⏳ Test en cours...';
  result.style.color = 'var(--muted)';
  const payload = {
    brand, port,
    baudrate: parseInt(document.getElementById('amp_baudrate').value, 10) || AMP_DEFAULT_BAUD[brand] || 9600,
    civ_addr: document.getElementById('amp_civ_addr').value.trim() || undefined,
    conn_mode: connMode, host,
    net_port: parseInt(document.getElementById('amp_net_port').value, 10) || 1500,
  };
  try{
    const res = await fetch('/amp/test', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload),
    });
    const r = await res.json();
    if (r.ok){
      const st = r.status || {};
      const bits = [];
      if (st.power_w !== undefined) bits.push(`${st.power_w} W`);
      if (st.swr !== undefined) bits.push(`SWR ${st.swr}`);
      if (st.power_raw !== undefined) bits.push(`Po brut ${st.power_raw}`);
      result.textContent = `✅ Ampli joint${bits.length ? ' — ' + bits.join(', ') : ''}`;
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

// QRZ Logbook : ACTION=STATUS (pas d'insertion) pour vérifier la clé avant
// de compter dessus pendant un concours — sauvegarde d'abord la clé tapée
// (le serveur lit sa propre config, pas le formulaire) comme connectSota().
async function testQrzLogbook(){
  const result = document.getElementById('qrzLogbookTestResult');
  const key = document.getElementById('qrz_logbook_key').value.trim();
  if (!key){
    result.textContent = '⚠️ Renseigne la clé API QRZ Logbook d\'abord';
    result.style.color = 'var(--yellow)';
    return;
  }
  result.textContent = '⏳ synchronisation de la config…';
  result.style.color = 'var(--muted)';
  // Le serveur teste sa propre config sauvegardée (current_config), pas le
  // formulaire affiché — sans ce await, un test lancé juste après avoir tapé
  // la clé peut encore voir l'ancienne clé (ou aucune) côté serveur (même
  // pattern que testVoiceKeyer()/connectSota()).
  saveConfig(true);
  await _lastConfigSavePromise;
  result.textContent = '⏳ Test en cours...';
  result.style.color = 'var(--muted)';
  try{
    const res = await fetch('/qrz_logbook/test', {method: 'POST'});
    const r = await res.json();
    if (r.ok){
      result.textContent = '✅ Clé QRZ Logbook valide';
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

// Sélecteur de dossier natif Windows pour DOSSIER DE SAUVEGARDE — le serveur
// tourne en local sur cette machine, donc peut ouvrir un vrai dialogue OS
// (voir logx_winshell.py). La requête reste en attente jusqu'à ce que
// l'utilisateur réponde au dialogue (comportement voulu, pas un bug).
// N'enregistre pas la config automatiquement : comme d'habitude, il faut
// encore cliquer "Enregistrer" dans la popup.
async function pickBackupFolder(){
  const input = document.getElementById('backup_folder');
  const btn = document.getElementById('backupFolderPickBtn');
  const result = document.getElementById('backupFolderPickResult');
  result.textContent = '';
  btn.disabled = true;
  const prevLabel = btn.textContent;
  btn.textContent = '⏳';
  try{
    const res = await fetch('/backup/pick_folder', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ initial_dir: input.value.trim() }),
    });
    const r = await res.json();
    if (r.ok){
      input.value = r.path;
    } else if (r.error !== 'annule'){
      // "annule" = l'utilisateur a fermé le dialogue sans choisir : rien à
      // signaler, ce n'est pas une erreur.
      result.textContent = r.message || `❌ ${r.error || 'Échec'}`;
      result.style.color = 'var(--red)';
    }
  }catch(e){
    result.textContent = '❌ Serveur injoignable';
    result.style.color = 'var(--red)';
  }finally{
    btn.disabled = false;
    btn.textContent = prevLabel;
  }
}

async function testCatConnection(){
  const result = document.getElementById('catTestResult');
  result.textContent = '⏳ Test en cours...';
  result.style.color = 'var(--muted)';
  const mode = document.getElementById('cat_mode').value;
  let payload;
  // Correctif B3 : contrairement au mode natif (bloque si cat_port est vide),
  // rien ne signalait un tci_host vide — le serveur retombe silencieusement
  // sur 127.0.0.1 (valeur par défaut légitime si le logiciel SDR tourne sur
  // le même PC, donc pas bloquant : juste rendu explicite dans le résultat).
  const tciHostEmpty = mode === 'tci' && !document.getElementById('tci_host').value.trim();
  if (mode === 'tci'){
    payload = { mode: 'tci',
      host: document.getElementById('tci_host').value.trim() || '127.0.0.1',
      port: parseInt(document.getElementById('tci_port').value, 10) || 50001 };
  } else if (mode === 'rigctld'){
    // Correctif H6 : jusqu'ici confondu avec le mode natif ci-dessous (testait
    // un port SÉRIE jamais utilisé par rigctld, qui parle réseau sur rig_host/rig_port).
    payload = { mode: 'rigctld',
      host: document.getElementById('rig_host')?.value.trim() || '127.0.0.1',
      port: parseInt(document.getElementById('rig_port')?.value, 10) || 4532 };
  } else if (mode === 'flrig'){
    payload = { mode: 'flrig',
      host: document.getElementById('flrig_host')?.value.trim() || '127.0.0.1',
      port: parseInt(document.getElementById('flrig_port')?.value, 10) || 12345 };
  } else if (mode === 'omnirig'){
    payload = { mode: 'omnirig',
      rig_num: parseInt(document.getElementById('omnirig_rig_num')?.value, 10) || 1 };
  } else if (mode === 'flex'){
    payload = { mode: 'flex',
      host: document.getElementById('flexradio_host')?.value.trim() || '127.0.0.1',
      port: parseInt(document.getElementById('flexradio_port')?.value, 10) || 4992 };
  } else if (mode === 'icom_remote'){
    payload = { mode: 'icom_remote',
      host: document.getElementById('icomremote_host')?.value.trim() || '',
      port: parseInt(document.getElementById('icomremote_control_port')?.value, 10) || 50001 };
  } else {
    payload = {
      brand: document.getElementById('cat_brand').value,
      model: document.getElementById('cat_model').value,
      port: document.getElementById('cat_port').value,
      baudrate: parseInt(document.getElementById('cat_baudrate').value, 10) || CAT_DEFAULT_BAUD[document.getElementById('cat_brand').value] || 19200,
      civ_addr: document.getElementById('cat_civ_addr').value.trim() || undefined,
    };
    if (!payload.port){
      result.textContent = '⚠️ Choisis un port série d\'abord';
      result.style.color = 'var(--yellow)';
      return;
    }
  }
  try{
    const res = await fetch('/rig/connect_test', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload),
    });
    const r = await res.json();
    if (r.ok && mode === 'tci'){
      result.textContent = `✅ Serveur TCI joint (${payload.host}${tciHostEmpty ? ' — défaut, champ vide' : ''}) : ${r.device || 'appareil inconnu'} (${r.freq_hz ? (r.freq_hz/1e6).toFixed(3)+' MHz' : 'fréquence non reçue'})`;
      result.style.color = 'var(--green)';
    } else if (r.ok && mode === 'rigctld'){
      result.textContent = `✅ rigctld joint (${payload.host}:${payload.port}) : ${r.freq_hz ? (r.freq_hz/1e6).toFixed(3)+' MHz' : 'fréquence non lue'}${r.mode ? ' — mode ' + r.mode : ''}`;
      result.style.color = 'var(--green)';
    } else if (r.ok && mode === 'flrig'){
      result.textContent = `✅ flrig joint (${payload.host}:${payload.port}) : ${r.freq_hz ? (r.freq_hz/1e6).toFixed(3)+' MHz' : 'fréquence non lue'}${r.mode ? ' — mode ' + r.mode : ''}`;
      result.style.color = 'var(--green)';
    } else if (r.ok && mode === 'omnirig'){
      result.textContent = `✅ OmniRig joint (Rig${payload.rig_num}) : ${r.device || 'appareil inconnu'} (${r.freq_hz ? (r.freq_hz/1e6).toFixed(3)+' MHz' : 'fréquence non lue'})`;
      result.style.color = 'var(--green)';
    } else if (r.ok && mode === 'flex'){
      result.textContent = `✅ FlexRadio joint (${payload.host}:${payload.port}) : ${r.freq_hz ? (r.freq_hz/1e6).toFixed(3)+' MHz' : 'fréquence non lue'}${r.mode ? ' — mode ' + r.mode : ''}`;
      result.style.color = 'var(--green)';
    } else if (mode === 'icom_remote'){
      result.textContent = `❌ ${r.error || 'Protocole non implémenté'}`;
      result.style.color = 'var(--red)';
    } else if (r.ok){
      result.textContent = `✅ Radio détectée : ${r.detected_model || payload.model} (${r.freq_hz ? (r.freq_hz/1e6).toFixed(3)+' MHz' : 'fréquence non lue'})`;
      result.style.color = 'var(--green)';
    } else {
      result.textContent = `❌ ${r.error || 'Connexion impossible'}${tciHostEmpty ? ` (adresse TCI non renseignée — testé sur ${payload.host} par défaut)` : ''}`;
      result.style.color = 'var(--red)';
    }
  }catch(e){
    result.textContent = `❌ Serveur injoignable : ${e.message}`;
    result.style.color = 'var(--red)';
  }
}

// Retour beta-testeur microHAM (02/08/2026) : le bouton "Tester" exige déjà
// marque+modèle choisis, donc n'auto-détecte jamais rien — il ne fait que
// revérifier un choix déjà fait. Ce bouton-ci appelle autodetect_scan() côté
// serveur (balaie plusieurs vitesses, interroge la radio elle-même) et
// PEUPLE marque/modèle/vitesse sur succès, sans que l'opérateur ait besoin
// de les connaître à l'avance.
async function autodetectCat(){
  const result = document.getElementById('catTestResult');
  const portVal = document.getElementById('cat_port').value;
  if (!portVal){
    result.textContent = '⚠️ Choisis un port série d\'abord';
    result.style.color = 'var(--yellow)';
    return;
  }
  result.textContent = '⏳ Auto-détection en cours (peut prendre jusqu\'à ~50 s, plusieurs vitesses testées)...';
  result.style.color = 'var(--muted)';
  try{
    const res = await fetch('/rig/autodetect', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ port: portVal }),
    });
    const r = await res.json();
    if (r.ok){
      if (r.brand){
        document.getElementById('cat_brand').value = r.brand;
        updateCatModelOptions();
      }
      if (r.model && document.getElementById('cat_model').querySelector(`option[value="${r.model}"]`)) {
        document.getElementById('cat_model').value = r.model;
        updateCatAddrNoteForModel();
      }
      if (r.baudrate) document.getElementById('cat_baudrate').value = r.baudrate;
      const label = r.model || (r.brand ? `${r.brand} (modèle non confirmé)` : 'radio');
      if (r.certain){
        result.textContent = `✅ Détecté : ${label} à ${r.baudrate} bauds`;
        result.style.color = 'var(--green)';
      } else {
        result.textContent = `⚠️ Détecté probablement : ${label} à ${r.baudrate} bauds — ${r.note || 'vérifie que c\'est le bon modèle'}`;
        result.style.color = 'var(--yellow)';
      }
    } else {
      result.textContent = `❌ ${r.error || 'Aucune radio détectée'}`;
      result.style.color = 'var(--red)';
    }
  }catch(e){
    result.textContent = `❌ Serveur injoignable : ${e.message}`;
    result.style.color = 'var(--red)';
  }
}

// ─── Détection de branchement (plug-and-play) ───────────────────────────
// Le serveur surveille les branchements en tâche de fond (aucun octet CAT
// envoyé — voir logx_cat.py:port_watcher_loop) et propose un indice passif
// (VID:PID/numéro de série). On ne fait JAMAIS confiance à cet indice seul :
// « Configurer » ouvre la popup radio et relance la sonde active existante
// (autodetectCat(), déjà sûre — lecture seule) sur le port détecté, comme
// si l'opérateur l'avait cliquée lui-même. Jamais d'activation automatique
// du pilotage sans ce clic (voir CLAUDE.md, chantier CAT 03/08/2026).
let _catDetectionShown = null;

async function pollCatDetections(){
  let data;
  try{
    const res = await fetch('/rig/pending_detections');
    data = await res.json();
  }catch(e){ return; }
  const list = data.detections || [];
  const banner = document.getElementById('catDetectionBanner');
  if (!list.length){
    banner.style.display = 'none';
    _catDetectionShown = null;
    return;
  }
  const d = list[list.length - 1];   // la plus récente
  if (d.device === _catDetectionShown) return;   // déjà affichée, pas de clignotement
  _catDetectionShown = d.device;
  const label = d.kind === 'radio'
    ? `${(d.brand || '').toUpperCase()} ${d.model || ''}`.trim()
    : (d.label || 'Interface CAT');
  document.getElementById('catDetectionText').textContent =
    `📡 ${label} détecté sur ${d.device} — vérifier et activer le pilotage CAT ?`;
  banner.dataset.device = d.device;
  banner.style.display = 'block';
}

async function applyCatDetection(){
  const banner = document.getElementById('catDetectionBanner');
  const device = banner.dataset.device;
  if (!device) return;
  await openCategoryPopup('radio');
  await refreshCatPorts();
  const portSel = document.getElementById('cat_port');
  // 🚨 Trouvé en revue adversariale : si le port a disparu entre la
  // détection et le clic (débranché, ou réénuméré sous un autre nom), NE
  // PAS enchaîner sur autodetectCat() en silence — celui-ci sonderait
  // alors l'ANCIEN port déjà sélectionné (repli de refreshCatPorts()) et
  // pourrait afficher "✅ Détecté" pour une radio différente de celle que
  // l'opérateur vient de brancher, sans qu'il s'en rende compte.
  const option = portSel.querySelector(`option[value="${CSS.escape(device)}"]`);
  dismissCatDetectionBanner();
  if (!option){
    const result = document.getElementById('catTestResult');
    if (result){
      result.textContent = `⚠️ ${device} n'est plus dans la liste des ports (débranché entre-temps ?) — choisis le port toi-même.`;
      result.style.color = 'var(--yellow)';
    }
    return;
  }
  portSel.value = device;
  await autodetectCat();
}

function dismissCatDetectionBanner(){
  const banner = document.getElementById('catDetectionBanner');
  const device = banner.dataset.device;
  banner.style.display = 'none';
  // _catDetectionShown n'est PAS remis à null ici (trouvé en revue
  // adversariale) : POST /rig/dismiss_detection est fire-and-forget, donc
  // un tour de pollCatDetections() qui tomberait dans la fenêtre avant que
  // le serveur ait pris en compte le retrait ferait sinon réapparaître le
  // bandeau une fraction de seconde. pollCatDetections() est seul à le
  // remettre à null, seulement quand le serveur confirme la liste vide.
  if (device){
    fetch('/rig/dismiss_detection', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({device}),
    }).catch(()=>{});
  }
}

setInterval(function(){ try{ pollCatDetections(); }catch(e){} }, 2000);

// Échappement HTML — c.name/c.org/c.date/c.rules/c.score peuvent venir du flux
// externe WA7BNM (/data/external_contests, contenu tiers non maîtrisé) via
// mergeExternalContests(). Sans échappement, ces champs s'injectent en innerHTML.
function escC(v){ return String(v==null?'':v).replace(/[&<>"']/g,
  c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
// URL de règlement : n'autoriser que http/https (bloque javascript:, data:...).
function safeUrl(u){ const s=String(u||''); return /^https?:\/\//i.test(s) ? s : ''; }
// id de concours pour un argument de chaîne JS (onclick) : caractères sûrs seulement.
function jsId(v){ return String(v==null?'':v).replace(/[^A-Za-z0-9_\-]/g,''); }

function buildContestGrid(filter = '') {
  const grid = document.getElementById('contestGrid');
  const q = filter.toLowerCase().trim();

  // Bouton effacer
  const clr = document.getElementById('contestSearchClear');
  if (clr) clr.style.display = q ? 'block' : 'none';

  // Filtrage
  const visible = q
    ? CONTESTS.filter(c =>
        c.name.toLowerCase().includes(q) ||
        c.id.toLowerCase().includes(q) ||
        (c.org||'').toLowerCase().includes(q) ||
        c.bands.some(b => b.toLowerCase().includes(q)) ||
        c.modes.some(m => m.toLowerCase().includes(q)) ||
        (c.score||'').toLowerCase().includes(q)
      )
    : CONTESTS;

  const groups = {};
  visible.forEach(c => {
    const g = c.group || 'Autre';
    if (!groups[g]) groups[g] = [];
    groups[g].push(c);
  });

  if (!visible.length) {
    grid.innerHTML = `<div style="grid-column:1/-1;padding:24px;text-align:center;font-family:var(--font-mono);color:var(--muted);font-size:14px">Aucun concours pour « ${filter} »</div>`;
    return;
  }

  const groupOrder = ['REF', 'Autre FR', 'International', 'Mondial (WA7BNM)', 'Autre'];
  const groupColors = {
    'REF': '#00D4FF',
    'Autre FR': '#FFD60A',
    'International': '#FF5030',
    'Mondial (WA7BNM)': '#FFD60A',
    'Autre': '#8E8E93',
  };

  // Badge de confiance : base serveur = dates/règlement re-vérifiés chaque année ;
  // custom = extrait du règlement par l'IA puis validé par relecture humaine
  const badge = c => c.external
    ? `<span style="font-family:var(--font-mono);font-size:11px;letter-spacing:1px;padding:2px 6px;border-radius:3px;background:rgba(255,214,10,.12);color:#FFD60A;border:1px solid rgba(255,214,10,.35)" title="Concours du calendrier mondial WA7BNM — utilise 🤖 ANALYSER UN RÈGLEMENT pour le faire lire par l'IA"><svg viewBox="0 0 18 18" width="12" height="12" style="vertical-align:-1px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 2.5 16 15H2z"/><line x1="9" y1="7" x2="9" y2="11"/><circle cx="9" cy="13.3" r="0.9" fill="currentColor" stroke="none"/></svg> À CONFIRMER</span>`
    : c._custom
      ? `<span style="font-family:var(--font-mono);font-size:11px;letter-spacing:1px;padding:2px 6px;border-radius:3px;background:rgba(var(--accent-rgb),.1);color:var(--accent2);border:1px solid rgba(var(--accent-rgb),.3)" title="Définition extraite du règlement par l'IA puis validée par relecture humaine"><svg viewBox="0 0 18 18" width="12" height="12" style="vertical-align:-1px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="6" width="11" height="8" rx="1.5"/><line x1="9" y1="6" x2="9" y2="3"/><circle cx="9" cy="2.2" r="1" fill="currentColor" stroke="none"/><circle cx="6.5" cy="10" r="1" fill="currentColor" stroke="none"/><circle cx="11.5" cy="10" r="1" fill="currentColor" stroke="none"/><line x1="6" y1="13" x2="12" y2="13"/></svg> IA + RELECTURE</span>`
      : VERIFIED_IDS.has(c.id)
        ? `<span style="font-family:var(--font-mono);font-size:11px;letter-spacing:1px;padding:2px 6px;border-radius:3px;background:rgba(0,255,136,.1);color:#00FF88;border:1px solid rgba(0,255,136,.3)" title="Concours de la base serveur — dates et règlement re-vérifiés automatiquement chaque année"><svg viewBox="0 0 18 18" width="12" height="12" style="vertical-align:-1px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3,10 7,14 15,4"/></svg> RÈGLEMENT SUIVI</span>`
        : '';

  grid.innerHTML = groupOrder.map(gname => {
    const cs = groups[gname];
    if (!cs || !cs.length) return '';
    return `
      <div style="grid-column:1/-1;margin-top:12px;margin-bottom:6px">
        <div style="font-family:var(--font-mono);font-size:12px;color:${groupColors[gname]};letter-spacing:3px;border-bottom:1px solid ${groupColors[gname]}44;padding-bottom:5px">
          ${gname === 'REF' ? '<svg viewBox="0 0 18 18" width="12" height="12" style="vertical-align:-1px;flex-shrink:0" fill="currentColor" stroke="none"><path d="M9 1.5l2.2 4.9 5.3.6-4 3.6 1.1 5.3L9 13.2 4.4 15.9l1.1-5.3-4-3.6 5.3-.6z"/></svg> ' : ''}${gname.toUpperCase()} ${gname === 'REF' ? '— Calendrier 2026 officiel' : ''}
        </div>
      </div>
      ${cs.map(c => `
        <div class="contest-card" id="card_${escC(c.id)}" data-id="${escC(c.id)}" onclick="selectContest('${jsId(c.id)}')" style="border-left:3px solid ${escC(c.color)}44">
          <div class="contest-name" style="display:flex;justify-content:space-between;align-items:center;gap:6px">${escC(c.name)} ${badge(c)}</div>
          <div class="contest-org" style="display:flex;justify-content:space-between;align-items:center">
            <span>${escC(c.org)}</span>
            ${safeUrl(c.rules) ? `<a href="${escC(safeUrl(c.rules))}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()" style="font-size:12px;color:var(--muted);letter-spacing:1px;font-family:var(--font-mono)"><svg viewBox="0 0 18 18" width="12" height="12" style="vertical-align:-1px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 2.5h5.5L13.5 5.5V15.5H5z"/><path d="M10.5 2.5V5.5H13.5"/><line x1="7" y1="9" x2="11.5" y2="9"/><line x1="7" y1="12" x2="11.5" y2="12"/></svg> RÈGLEMENT</a>` : ''}
          </div>
          ${c.date ? `<div style="font-family:var(--font-mono);font-size:12px;color:var(--yellow);letter-spacing:1px;margin-bottom:7px"><svg viewBox="0 0 18 18" width="12" height="12" style="vertical-align:-1px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="3.5" width="13" height="11.5" rx="1.5"/><line x1="2.5" y1="7.5" x2="15.5" y2="7.5"/><line x1="6" y1="1.5" x2="6" y2="4.5"/><line x1="12" y1="1.5" x2="12" y2="4.5"/></svg> ${escC(c.date)}</div>` : ''}
          <div class="contest-tags">
            ${c.bands.map(b=>`<span class="tag tag-band">${escC(b)}</span>`).join('')}
            ${c.modes.map(m=>`<span class="tag tag-mode">${escC(m)}</span>`).join('')}
            <span class="tag tag-score">${escC(c.score)}</span>
          </div>
        </div>
      `).join('')}
    `;
  }).join('');
}

// ─── AUTO-REMPLISSAGE INDICATIF ───────────────────────────────────────────────
let _callContest_manual = false;

// Préfixe indicatif → code pays ISO 3 lettres. Couvre l'Europe (usage
// principal de l'app, champs EDI) + les principales destinations DX ;
// n'a pas vocation à couvrir les ~340 entités DXCC — le champ PAYS reste
// éditable pour les cas non couverts (cf. dataset.manual plus bas).
const CALLSIGN_COUNTRY_PREFIXES = {
  // France + voisins
  F:'FRA', TK:'FRA', TM:'FRA', TO:'FRA', TX:'FRA',
  EA:'ESP', EA6:'ESP', EA8:'ESP', EA9:'ESP', EB:'ESP', EC:'ESP', ED:'ESP', EF:'ESP', EG:'ESP', EH:'ESP',
  DL:'DEU', DA:'DEU', DB:'DEU', DC:'DEU', DD:'DEU', DF:'DEU', DG:'DEU', DH:'DEU', DJ:'DEU', DK:'DEU', DM:'DEU', DO:'DEU',
  G:'GBR', M:'GBR', '2E':'GBR', GW:'GBR', GM:'GBR', GI:'GBR', GD:'GBR', GJ:'GBR', GU:'GBR', GX:'GBR',
  I:'ITA', IK:'ITA', IZ:'ITA', IW:'ITA', IU:'ITA', IQ:'ITA', IN:'ITA',
  ON:'BEL', OO:'BEL', OP:'BEL', OQ:'BEL', OR:'BEL', OS:'BEL', OT:'BEL',
  PA:'NLD', PB:'NLD', PC:'NLD', PD:'NLD', PE:'NLD', PF:'NLD', PG:'NLD', PH:'NLD', PI:'NLD',
  HB9:'CHE', HB3:'CHE', HB0:'LIE',
  OE:'AUT',
  SM:'SWE', SA:'SWE', SB:'SWE', SC:'SWE', SD:'SWE', SE:'SWE', SF:'SWE', SG:'SWE', SH:'SWE', SI:'SWE', SJ:'SWE', SK:'SWE', SL:'SWE',
  LA:'NOR', LB:'NOR', LJ:'NOR',
  OZ:'DNK', '5P':'DNK', '5Q':'DNK',
  OH:'FIN', OF:'FIN', OG:'FIN', OI:'FIN', OJ:'FIN',
  CT:'PRT', CQ:'PRT', CR:'PRT', CS:'PRT',
  SP:'POL', SN:'POL', SO:'POL', SQ:'POL', SR:'POL', HF:'POL', '3Z':'POL',
  OK:'CZE', OL:'CZE',
  OM:'SVK',
  S5:'SVN',
  '9A':'HRV',
  HA:'HUN', HG:'HUN',
  YO:'ROU', YP:'ROU', YQ:'ROU', YR:'ROU',
  LZ:'BGR',
  ES:'EST',
  YL:'LVA',
  LY:'LTU',
  UR:'UKR', UT:'UKR', UU:'UKR', UV:'UKR', UW:'UKR', UX:'UKR', UY:'UKR', UZ:'UKR', EM:'UKR', EN:'UKR', EO:'UKR',
  EW:'BLR',
  ER:'MDA',
  '4O':'MNE', E7:'BIH', Z3:'MKD',
  SV:'GRC', SW:'GRC', SX:'GRC', SY:'GRC', SZ:'GRC', J4:'GRC',
  TA:'TUR', TC:'TUR',
  '4X':'ISR', '4Z':'ISR',
  JY:'JOR', OD:'LBN',
  EI:'IRL', EJ:'IRL',
  C3:'AND', '3A':'MCO', '9H':'MLT', ZA:'ALB', TF:'ISL',
  UA:'RUS', UB:'RUS', RA:'RUS', RK:'RUS', RN:'RUS', RU:'RUS', RV:'RUS', RW:'RUS', RX:'RUS', RZ:'RUS', R1:'RUS', R2:'RUS', R3:'RUS', R4:'RUS', R5:'RUS', R6:'RUS', R7:'RUS', R8:'RUS', R9:'RUS',
  // Amérique
  K:'USA', N:'USA', W:'USA', AA:'USA', AB:'USA', AC:'USA', AD:'USA', AE:'USA', AF:'USA', AG:'USA', AI:'USA', AJ:'USA', AK:'USA', KA:'USA', KB:'USA', KC:'USA', KD:'USA', KE:'USA', KF:'USA', KG:'USA', KI:'USA', KJ:'USA', KK:'USA', KM:'USA', KN:'USA', KO:'USA', KQ:'USA', KR:'USA', KS:'USA', KT:'USA', KU:'USA', KV:'USA', KW:'USA', KX:'USA', KY:'USA', KZ:'USA', WA:'USA', WB:'USA', WC:'USA', WD:'USA', WE:'USA', WF:'USA', WG:'USA', WI:'USA', WJ:'USA', WK:'USA', WM:'USA', WN:'USA', WO:'USA', WQ:'USA', WR:'USA', WS:'USA', WT:'USA', WU:'USA', WV:'USA', WW:'USA', WX:'USA', WY:'USA', WZ:'USA',
  VE:'CAN', VA:'CAN', VO:'CAN', VY:'CAN',
  XE:'MEX',
  PY:'BRA', PP:'BRA', PQ:'BRA', PR:'BRA', PS:'BRA', PT:'BRA', PU:'BRA', PV:'BRA', PW:'BRA', ZV:'BRA', ZW:'BRA', ZX:'BRA', ZY:'BRA', ZZ:'BRA',
  LU:'ARG', AY:'ARG', AZ:'ARG',
  CE:'CHL', CX:'URY', HK:'COL', YV:'VEN', OA:'PER', CP:'BOL', HC:'ECU',
  // Asie-Pacifique / Afrique
  JA:'JPN', JE:'JPN', JF:'JPN', JG:'JPN', JH:'JPN', JI:'JPN', JJ:'JPN', JK:'JPN', JL:'JPN', JM:'JPN', JN:'JPN', JO:'JPN', JP:'JPN', JQ:'JPN', JR:'JPN', JS:'JPN',
  BY:'CHN', BG:'CHN', BH:'CHN', BI:'CHN', BJ:'CHN', BL:'CHN',
  BV:'TWN',
  HL:'KOR', DS:'KOR',
  VK:'AUS', ZL:'NZL',
  ZS:'ZAF', ZR:'ZAF', ZT:'ZAF', ZU:'ZAF',
  VU:'IND', '9V':'SGP', HS:'THA', E2:'THA',
  YB:'IDN', YC:'IDN', YD:'IDN', YE:'IDN', YF:'IDN', YG:'IDN', YH:'IDN',
  DU:'PHL', DV:'PHL', DW:'PHL', DX:'PHL', DY:'PHL', DZ:'PHL',
  VR:'HKG',
};

// Suffixes/segments à ignorer quand on choisit quelle partie d'un indicatif
// barré (EA/F4GLD, F/ON4ABC/P) porte l'information de pays.
const CALLSIGN_SUFFIX_TOKENS = new Set(['P','M','MM','AM','A','QRP']);

function deriveCountryFromCallsign(call){
  call = (call||'').toUpperCase().trim();
  if(!call) return '';
  let parts = call.split('/').filter(p => p && !CALLSIGN_SUFFIX_TOKENS.has(p) && !/^\d+$/.test(p));
  if(parts.length > 1) parts.sort((a,b) => a.length - b.length); // préfixe hôte (le plus court) prioritaire
  else if(!parts.length) parts = [call];
  for(const part of parts){
    for(let len = Math.min(part.length, 3); len >= 1; len--){
      const hit = CALLSIGN_COUNTRY_PREFIXES[part.slice(0, len)];
      if(hit) return hit;
    }
  }
  return '';
}

function autoFillCallsign(val){
  val = val.toUpperCase();
  if(!_callContest_manual){
    document.getElementById('callsign_contest').value = val;
  }
  const opCall = document.getElementById('op_call');
  if(opCall && !opCall.dataset.manual) opCall.value = val;
  const op1 = document.getElementById('op1_call');
  if(op1 && !op1.dataset.manual) op1.value = val;
  const countryEl = document.getElementById('country');
  if(countryEl && !countryEl.dataset.manual){
    const derived = deriveCountryFromCallsign(val);
    if(derived) countryEl.value = derived;
  }
}
// ─── PROFILS STATION MULTIPLES ────────────────────────────────────────────────
function getProfiles(){ try{ return JSON.parse(localStorage.getItem('logx_profiles')||'{}'); }catch(e){ return {}; } }
function setProfiles(p){ localStorage.setItem('logx_profiles', JSON.stringify(p)); }

function refreshProfileSelect(){
  const sel = document.getElementById('profileSelect');
  if(!sel) return;
  const profiles = getProfiles();
  const current = sel.value;
  sel.innerHTML = '<option value="">— Sélectionner un profil —</option>';
  Object.keys(profiles).sort().forEach(name => {
    const opt = document.createElement('option');
    opt.value = name; opt.textContent = name;
    if(name === current) opt.selected = true;
    sel.appendChild(opt);
  });
}

function saveProfile(){
  const name = prompt(T('Nom du profil (ex: F6KQJ RPH 2026, Club 144, Home HF…) :'),
    document.getElementById('profileSelect').value || '');
  if(!name || !name.trim()) return;
  // Capturer l'état courant du formulaire via saveConfig silencieux puis lire
  saveConfig(true);
  const cfg = JSON.parse(localStorage.getItem('logx_config')||'{}');
  // Audit sécurité : depuis le durcissement de saveConfig(), localStorage['logx_config']
  // ne contient JAMAIS les champs de SECRET_CONFIG_FIELDS (copie 'localCopy' expurgée) —
  // les relire ici les laisserait vides à vie dans le profil (régression du bug H1
  // « chargement de profil incomplet », déjà corrigé une fois). Un PROFIL est un
  // mécanisme différent : une sauvegarde complète de la config choisie par l'opérateur
  // (pas un cache anti-perte-de-frappe entre visites) — les secrets y sont donc capturés
  // EN CLAIR directement depuis le formulaire, pas depuis le blob localStorage expurgé.
  for(const f of SECRET_CONFIG_FIELDS){
    const el = document.getElementById(f);
    if(el) cfg[f] = el.value;
  }
  const profiles = getProfiles();
  profiles[name.trim()] = cfg;
  setProfiles(profiles);
  refreshProfileSelect();
  document.getElementById('profileSelect').value = name.trim();
  _configToast(Tf('✅ Profil « {n} » sauvegardé.', {n: name.trim()}));
}

function loadProfile(){
  const sel = document.getElementById('profileSelect');
  const name = sel ? sel.value : '';
  if(!name){ _configToast(T('Sélectionnez un profil à charger.')); return; }
  const profiles = getProfiles();
  const cfg = profiles[name];
  if(!cfg){ _configToast(Tf('Profil introuvable : {n}', {n: name})); return; }
  applyFullConfigToForm(cfg);
  _configToast(Tf('📂 Profil « {n} » chargé.', {n: name}));
}

async function deleteProfile(){
  const sel = document.getElementById('profileSelect');
  const name = sel ? sel.value : '';
  if(!name){ _configToast(T('Sélectionnez un profil à supprimer.')); return; }
  if(!(await _confirmConfigBanner(Tf('Supprimer le profil « {n} » ?', {n: name}), 'Supprimer', 'Annuler'))) return;
  const profiles = getProfiles();
  delete profiles[name];
  setProfiles(profiles);
  refreshProfileSelect();
}

document.addEventListener('DOMContentLoaded',()=>{
  ['op_call','op1_call'].forEach(id=>{
    const el = document.getElementById(id);
    if(el) el.addEventListener('input',()=>{ el.dataset.manual='1'; });
  });
  // Afficher concours actif dans la nav
  try{
    const cfg = JSON.parse(localStorage.getItem('logx_config')||'{}');
    const el = document.getElementById('navContest');
    if(el && cfg.contest) el.textContent = cfg.contest.replace(/_/g,' ');
  }catch(e){}
  refreshProfileSelect();
});

// ─── CALCUL DATES DEPUIS CONCOURS ─────────────────────────────────────────────
// Règles date pour les concours principaux
const CONTEST_DATE_RULES = {
  'REF_RPH':        { rule:'first_saturday_july',    dur:24, start_utc:'14:00' },
  'ARRL_FD':        { rule:'last_full_weekend_june',  dur:27, start_utc:'18:00' },
  'CQ_WW_SSB':      { rule:'last_full_weekend_oct',   dur:48, start_utc:'00:00' },
  'CQ_WW_CW':       { rule:'last_full_weekend_nov',   dur:48, start_utc:'00:00' },
  'CQ_WPX_SSB':     { rule:'last_full_weekend_mar',   dur:48, start_utc:'00:00' },
  'CQ_WPX_CW':      { rule:'last_full_weekend_may',   dur:48, start_utc:'00:00' },
  'IARU_HF':        { rule:'second_full_weekend_jul', dur:24, start_utc:'12:00' },
  'REF_RPH_VHF':    { rule:'first_saturday_july',     dur:24, start_utc:'14:00' },
  'REF_VHF_UHF_FR': { rule:'first_full_weekend_sep',  dur:24, start_utc:'14:00' },
  'EU_VHF':         { rule:'first_full_weekend_aug',  dur:24, start_utc:'14:00' },
  'IARU_VHF':       { rule:'first_full_weekend_sep',  dur:24, start_utc:'14:00' },
};
function calcContestDates(id){
  const yr = new Date().getFullYear();
  const rule = CONTEST_DATE_RULES[id];
  if(!rule) return null;
  let d = null;
  const r = rule.rule;
  function nthWeekday(month, weekday, n){
    // month 0-based, weekday 0=Sun, n=1-based or -1=last
    let dt = new Date(yr, month, 1);
    if(n>0){
      let count=0;
      while(dt.getMonth()===month){
        if(dt.getDay()===weekday){ count++; if(count===n) return new Date(dt); }
        dt.setDate(dt.getDate()+1);
      }
    } else { // last
      dt = new Date(yr, month+1, 0);
      while(dt.getMonth()===month){
        if(dt.getDay()===weekday) return new Date(dt);
        dt.setDate(dt.getDate()-1);
      }
    }
    return null;
  }
  function lastFullWeekend(month){
    // Last Saturday where Sunday is still in the same month
    let dt = new Date(yr, month+1, 0); // last day of month
    while(dt.getDay()!==0) dt.setDate(dt.getDate()-1); // last Sunday
    return new Date(dt.getFullYear(), dt.getMonth(), dt.getDate()-1); // Saturday before
  }
  function firstFullWeekend(month){
    let dt = new Date(yr, month, 1);
    while(dt.getDay()!==6) dt.setDate(dt.getDate()+1); // first Saturday
    return new Date(dt);
  }
  function nthFullWeekend(month, n){
    let dt = firstFullWeekend(month);
    dt.setDate(dt.getDate()+(n-1)*7);
    return dt;
  }
  if(r==='first_saturday_july')       d = nthWeekday(6,6,1);
  else if(r==='last_full_weekend_june') d = lastFullWeekend(5);
  else if(r==='last_full_weekend_oct')  d = lastFullWeekend(9);
  else if(r==='last_full_weekend_nov')  d = lastFullWeekend(10);
  else if(r==='last_full_weekend_mar')  d = lastFullWeekend(2);
  else if(r==='last_full_weekend_may')  d = lastFullWeekend(4);
  else if(r==='second_full_weekend_jul')d = nthFullWeekend(6,2);
  else if(r==='first_full_weekend_sep') d = firstFullWeekend(8);
  else if(r==='first_full_weekend_aug') d = firstFullWeekend(7);
  if(!d) return null;
  const pad = n=>String(n).padStart(2,'0');
  // d ne porte que la BONNE DATE CALENDAIRE (weekday trouvé en heure locale) —
  // on reconstruit tout le calcul en UTC pur à partir de là, en y injectant
  // enfin rule.start_utc (ex: "14:00"), qui était ignoré avant (bug : l'heure
  // de fin sortait toujours à 00:00 au lieu de start_utc + durée).
  const [startH, startM] = (rule.start_utc||'00:00').split(':').map(Number);
  const startMs = Date.UTC(d.getFullYear(), d.getMonth(), d.getDate(), startH, startM);
  const endMs   = startMs + rule.dur * 3600 * 1000;
  const fmtUTC = ms=>{
    const dt = new Date(ms);
    return `${dt.getUTCFullYear()}-${pad(dt.getUTCMonth()+1)}-${pad(dt.getUTCDate())}`;
  };
  const startDate = fmtUTC(startMs);
  const endDate   = fmtUTC(endMs);
  const endDt = new Date(endMs);
  const endTime = `${pad(endDt.getUTCHours())}:${pad(endDt.getUTCMinutes())}`;
  return { startDate, endDate, endTime };
}

async function selectContest(id, _skipConfirm) {
  // Correctif H3 : re-cliquer la carte déjà sélectionnée ne changeait rien en
  // apparence mais réinitialisait quand même bandes/modes/dates en silence —
  // désormais un no-op franc. Changer POUR un autre concours alors qu'un
  // concours était déjà actif écrasait aussi silencieusement bandes/modes/
  // dates personnalisés : on demande confirmation avant.
  // _skipConfirm=true : appels programmatiques (restauration de config/profil,
  // lien calendrier ?contest=ID, validation IA d'un règlement) où l'intention
  // de choisir CE concours est déjà explicite — jamais de confirm() ici.
  if (id === state.contest) return;
  if (!_skipConfirm && state.contest) {
    const prev = CONTESTS.find(c => c.id === state.contest);
    const next = CONTESTS.find(c => c.id === id);
    const msg = `Changer pour « ${next ? next.name : id} » va réinitialiser bandes/modes/dates `
      + `selon ce règlement — tes personnalisations pour « ${prev ? prev.name : state.contest} » seront perdues.\n\nContinuer ?`;
    if (!(await _confirmConfigBanner(msg, 'Changer de concours', 'Annuler'))) return;
  }
  state.contest = id;
  document.querySelectorAll('.contest-card').forEach(c => c.classList.remove('selected'));
  const card = document.getElementById('card_'+id);
  if(card) card.classList.add('selected');
  // Auto-appliquer les bandes/modes du concours dès la sélection
  applyContestFilters(id);
  _filtersAppliedFor = id;
  // Auto-calculer les dates : règle locale, sinon date serveur (recalculée
  // chaque année par logx_serveur.py — couvre toute la base "règlement suivi")
  const dates = calcContestDates(id) || serverContestDates(id);
  const banner = document.getElementById('contest_dates_auto');
  if(dates){
    document.getElementById('contest_start_date').value = dates.startDate;
    document.getElementById('contest_end_date').value   = dates.endDate;
    document.getElementById('contest_end_utc').value    = dates.endTime;
    state.datesAutoFor = id; // l'assistant sait que ces dates sont pour CE concours
    if(banner) banner.innerHTML = `<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="3.5" width="13" height="11.5" rx="1.5"/><line x1="2.5" y1="7.5" x2="15.5" y2="7.5"/><line x1="6" y1="1.5" x2="6" y2="4.5"/><line x1="12" y1="1.5" x2="12" y2="4.5"/></svg> <strong>${id}</strong> — Début : <strong>${dates.startDate}</strong> · Fin : <strong>${dates.endDate} ${dates.endTime} UTC</strong> — <span style="color:var(--muted)">Modifie manuellement si besoin</span>`;
  } else {
    // Ne pas laisser traîner les dates d'un AUTRE concours dans les champs
    if(state.datesAutoFor && state.datesAutoFor !== id){
      document.getElementById('contest_start_date').value = '';
      document.getElementById('contest_end_date').value   = '';
      document.getElementById('contest_end_utc').value    = '';
    }
    state.datesAutoFor = null;
    if(banner) banner.innerHTML = `<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="3.5" width="13" height="11.5" rx="1.5"/><line x1="2.5" y1="7.5" x2="15.5" y2="7.5"/><line x1="6" y1="1.5" x2="6" y2="4.5"/><line x1="12" y1="1.5" x2="12" y2="4.5"/></svg> Dates pour <strong>${id}</strong> non calculables automatiquement — saisis-les manuellement.`;
  }
  // Auto-remplir l'URL de soumission du log depuis le règlement (si connue,
  // via SERVER_CONTEST_RULES/mergeServerContests → local.log_submit) — même
  // logique que les dates ci-dessus : écrasée à chaque changement de concours
  // (l'opérateur vient d'accepter cette réinitialisation via la confirmation
  // plus haut), corrigeable ensuite à la main si le règlement a changé ou est
  // erroné. Sans ça le champ restait vide pour tout concours, même quand
  // l'info est déjà connue côté serveur.
  const submitUrlEl = document.getElementById('submit_url');
  const selectedDef = CONTESTS.find(c => c.id === id);
  if (selectedDef && selectedDef.log_submit){
    submitUrlEl.value = selectedDef.log_submit;
    state.submitUrlAutoFor = id;
  } else if (state.submitUrlAutoFor && state.submitUrlAutoFor !== id){
    submitUrlEl.value = '';
    state.submitUrlAutoFor = null;
  }
  // Correctif : le statut Call History (MASTER.SCP/Call History importés)
  // n'était rafraîchi qu'au chargement de la page et après un import —
  // changer de concours ici sans recharger la page laissait le compteur du
  // PRÉCÉDENT concours affiché.
  refreshCallHistoryStatus();
  refreshContestBestScore(id);
  renderConfigTree();
}

// Liste déroulante du panneau d'import d'anciens logs -- reflète TOUJOURS
// CONTESTS (y compris après mergeServerContests()/mergeExternalContests()),
// distincte de la sélection state.contest : on peut vouloir archiver une
// vieille édition d'un AUTRE concours que celui actuellement configuré.
function populateImportContestSelect(){
  const sel = document.getElementById('importOldLogContest');
  if(!sel) return;
  const prev = sel.value;
  // Option de tête « Détection automatique » (demande F4GLD 10/08/2026 :
  // « sans avoir à choisir le concours ») -- valeur vide, comprise par
  // import_external_log() côté serveur comme « devine depuis le fichier »
  // (guess_contest_id() sur la ligne CONTEST: Cabrillo ou le tag CONTEST_ID
  // ADIF). La liste complète reste disponible pour le cas où le fichier ne
  // porte pas ce champ, ou si la détection se trompe.
  const options = CONTESTS.slice().sort((a, b) => a.name.localeCompare(b.name))
    .map(c => `<option value="${escC(c.id)}">${escC(c.name)}</option>`).join('');
  sel.innerHTML = '<option value="">— Détection automatique —</option>' + options;
  if(prev && (prev === '' || CONTESTS.some(c => c.id === prev))) sel.value = prev;
}

async function importOldLog(file){
  if(!file) return;
  const statusEl = document.getElementById('importOldLogStatus');
  const fmt = document.getElementById('importOldLogFormat').value;
  const contestSel = document.getElementById('importOldLogContest');
  const contest = contestSel.value;   // vide = laisser le serveur deviner
  const scoreEl = document.getElementById('importOldLogScore');
  const fileInput = document.getElementById('importOldLogFile');
  statusEl.textContent = 'Import en cours…';
  try{
    const text = await file.text();
    const r = await (await fetch('/log/archives/import', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({format: fmt, text, contest, score: scoreEl.value || null})
    })).json();
    if(r.ok){
      const detectedPart = r.detected ? ' (détecté automatiquement)' : '';
      statusEl.textContent = `Importé pour ${escC(r.contest)}${detectedPart} : ${r.qso_count} QSO archivés.`;
      scoreEl.value = '';
      if(state.contest === r.contest) refreshContestBestScore(r.contest);
    } else if(r.needs_manual){
      statusEl.textContent = 'Concours non détecté automatiquement — choisis-le dans la liste, puis réessaie.';
      contestSel.focus();
    } else {
      statusEl.textContent = 'Erreur : ' + (r.error || 'import refusé');
    }
  }catch(e){
    statusEl.textContent = 'Erreur réseau : ' + e.message;
  }
  fileInput.value = '';   // permet de réimporter le même fichier ensuite si besoin
}

// Revenir à « pas de concours » — seul selectContest() existait, qui ne fait
// que CHANGER pour un autre concours, jamais redevenir "sans concours". Utile
// hors mode LOGBOOK SIMPLE (masqué) : en EXPÉDITION notamment, participer ou
// non à un concours ponctuel est un vrai choix réversible.
function deselectContest(){
  if(!state.contest) return;
  state.contest = null;
  document.querySelectorAll('.contest-card').forEach(c => c.classList.remove('selected'));
  // Ne PAS réinitialiser les bandes/modes déjà cochés (contrairement au
  // passage en LOGBOOK SIMPLE) : l'utilisateur reprend juste la main
  // librement à l'étape FILTRES, sans perdre sa sélection en cours.
  applyContestFilters(null);
  _filtersAppliedFor = null;
  state.datesAutoFor = null;
  if(state.submitUrlAutoFor){
    document.getElementById('submit_url').value = '';
    state.submitUrlAutoFor = null;
  }
  const banner = document.getElementById('contest_dates_auto');
  if(banner) banner.innerHTML = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="3.5" width="13" height="11.5" rx="1.5"/><line x1="2.5" y1="7.5" x2="15.5" y2="7.5"/><line x1="6" y1="1.5" x2="6" y2="4.5"/><line x1="12" y1="1.5" x2="12" y2="4.5"/></svg> Choisis un concours ci-dessus : ses dates se calculent automatiquement.';
  refreshCallHistoryStatus();   // même correctif que selectContest() : ne pas laisser un compteur obsolète
  refreshContestBestScore(null);
  renderConfigTree();
}

// Dates depuis la base serveur : parse "DD/MM/YYYY à HHhMM UTC" + durée
function serverContestDates(id){
  const c = CONTESTS.find(x => x.id === id);
  if (!c || !c._server_date || !c._duration_h) return null;
  const m = String(c._server_date).match(/(\d{2})\/(\d{2})\/(\d{4})/);
  if (!m) return null;
  // Heure de début : champ start_utc, sinon le "à 14h00" du libellé serveur
  // (certaines définitions portent l'heure dans la règle de date uniquement)
  let startUtc = c._start_utc;
  if (!startUtc || startUtc === '00:00'){
    const h = String(c._server_date).match(/à\s+(\d{1,2})h(\d{2})/i);
    if (h) startUtc = `${h[1].padStart(2,'0')}:${h[2]}`;
  }
  const [sh, sm] = (startUtc || '00:00').split(':').map(Number);
  const startMs = Date.UTC(+m[3], +m[2]-1, +m[1], sh, sm);
  const endMs = startMs + c._duration_h * 3600 * 1000;
  const pad = n => String(n).padStart(2,'0');
  const iso = ms => { const d = new Date(ms); return `${d.getUTCFullYear()}-${pad(d.getUTCMonth()+1)}-${pad(d.getUTCDate())}`; };
  const endD = new Date(endMs);
  return { startDate: iso(startMs), endDate: iso(endMs),
           endTime: `${pad(endD.getUTCHours())}:${pad(endD.getUTCMinutes())}` };
}

function toggle(el) {
  el.classList.toggle('on');
  state.toggles[el.dataset.key] = el.classList.contains('on');
  renderConfigTree();
}

// ─── ARBORESCENCE DE RÉGLAGES (refonte façon OpsLog, 08/08/2026) ────────────
// Un panneau statique par catégorie (voir CSS .cat-modal-box) : changer de
// section ne fait que basculer sa visibilité, aucun champ n'est déplacé à
// l'exécution. Une arborescence PERMANENTE (#configSidebar) remplace le hub
// de cartes + la popup plein écran par catégorie : un seul panneau visible à
// la fois, plus de retour à un "hub" (qui n'existe plus). Tous les champs vivent en
// permanence dans le DOM (les popups sont juste masqués) : changer de section ne
// perd jamais une saisie, et Enregistrer lit toujours l'ensemble.
const _ICO_IDENTITY = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="6" r="3"/><path d="M3 15.5c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5"/></svg>';
const _ICO_OPERATORS = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="6.5" cy="5.5" r="2.3"/><circle cx="12.5" cy="5.5" r="2.3"/><path d="M2 15.5c0-2.8 2-4.7 4.5-4.7s4.5 1.9 4.5 4.7"/><path d="M7.5 15.5c0-2.8 2-4.7 4.5-4.7s4.5 1.9 4.5 4.7"/></svg>';
const _ICO_TROPHY = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5.5 3h7v4a3.5 3.5 0 0 1-7 0z"/><path d="M5.5 4h-2v1.5a2.5 2.5 0 0 0 2.3 2.5"/><path d="M12.5 4h2v1.5a2.5 2.5 0 0 1-2.3 2.5"/><line x1="9" y1="10.5" x2="9" y2="13"/><line x1="6" y1="15.5" x2="12" y2="15.5"/><line x1="6.5" y1="13" x2="11.5" y2="13"/></svg>';
const _ICO_CALENDAR = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="3.5" width="13" height="11.5" rx="1.5"/><line x1="2.5" y1="7.5" x2="15.5" y2="7.5"/><line x1="6" y1="1.5" x2="6" y2="4.5"/><line x1="12" y1="1.5" x2="12" y2="4.5"/></svg>';
const _ICO_RADIO = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="6.5" width="13" height="8.5" rx="1.3"/><line x1="5" y1="6.5" x2="8" y2="2"/><circle cx="12.3" cy="10.5" r="1.6"/><line x1="4" y1="13" x2="8.5" y2="13"/></svg>';
const _ICO_BATTERY = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="5" width="11" height="8" rx="1.3"/><line x1="13.5" y1="7.5" x2="15.5" y2="7.5"/><line x1="13.5" y1="10.5" x2="15.5" y2="10.5"/><path d="M9.2 6.8 6.5 10.2h2.2L7.5 12.8l3.6-3.7H8.9z" fill="currentColor" stroke="none"/></svg>';
const _ICO_COMPASS = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="9" r="6.5"/><path d="M11.5 6.5 9.8 9.8 6.5 11.5 8.2 8.2z" fill="currentColor" stroke="none"/></svg>';
const _ICO_CLOUD = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5.5 13.5h7.5a2.7 2.7 0 0 0 0-5.4 4 4 0 0 0-7.6-1.3 3.2 3.2 0 0 0-2.4 3.1 2.6 2.6 0 0 0 2.5 3.6z"/></svg>';
const _ICO_FLOPPY = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 2.5h9L15 5.5V15.5H3z"/><rect x="5.5" y="2.5" width="5" height="4"/><rect x="5" y="10" width="8" height="5.5"/></svg>';
const _ICO_DISH = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M3 12a6 6 0 0 1 12 0"/><line x1="9" y1="12" x2="9" y2="16"/><line x1="9" y1="9" x2="9" y2="6"/><circle cx="9" cy="5" r="1.3" fill="currentColor" stroke="none"/></svg>';
const _ICO_BELL = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 2.5a4 4 0 0 0-4 4v2.3c0 .9-.4 1.8-1.1 2.4l-.6.6h11.4l-.6-.6a3.3 3.3 0 0 1-1.1-2.4V6.5a4 4 0 0 0-4-4z"/><path d="M7.3 14.5a1.8 1.8 0 0 0 3.4 0"/></svg>';
const _ICO_ENVELOPE = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="4" width="13" height="10" rx="1.2"/><path d="M2.8 4.6 9 9.5l6.2-4.9"/></svg>';
const _ICO_RELAY = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="4" width="13" height="10" rx="1.5"/><circle cx="6" cy="9" r="1.1" fill="currentColor" stroke="none"/><circle cx="9" cy="9" r="1.1" fill="currentColor" stroke="none"/><circle cx="12" cy="9" r="1.1" fill="currentColor" stroke="none"/></svg>';
const _ICO_PLAY = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="currentColor" stroke="none"><polygon points="6,3.5 14,9 6,14.5"/></svg>';
const _ICO_GLOBE = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="9" cy="9" r="6.5"/><ellipse cx="9" cy="9" rx="2.7" ry="6.5"/><line x1="2.5" y1="9" x2="15.5" y2="9"/></svg>';
const _ICO_ROBOT = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="6" width="11" height="8" rx="1.5"/><line x1="9" y1="6" x2="9" y2="3"/><circle cx="9" cy="2.2" r="1" fill="currentColor" stroke="none"/><circle cx="6.5" cy="10" r="1" fill="currentColor" stroke="none"/><circle cx="11.5" cy="10" r="1" fill="currentColor" stroke="none"/><line x1="6" y1="13" x2="12" y2="13"/></svg>';
const _ICO_SIGNAL = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="9" y1="7" x2="9" y2="15"/><circle cx="9" cy="5" r="1.3" fill="currentColor" stroke="none"/><path d="M5.5 8a5 5 0 0 1 7 0"/><path d="M3 5.5a8.5 8.5 0 0 1 12 0"/></svg>';
const _ICO_SUMMARY = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="14.5" x2="4" y2="9"/><line x1="9" y1="14.5" x2="9" y2="4"/><line x1="14" y1="14.5" x2="14" y2="11"/></svg>';
// Même tracé que le titre de la modale IMPORT ADIF de logx_logbook.html
// (dossier) -- langage visuel cohérent entre les deux pages pour la même action.
const _ICO_IMPORT = '<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4.5a1 1 0 0 1 1-1h4l1.5 2H15a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1z"/></svg>';
// Source UNIQUE des catégories (tree + badges + _catStatus()) : la
// duplication d'une 2e liste (ancien tableau codé en dur de renderHub())
// avait déjà causé un vrai bug (badge 'relay' jamais mis à jour, voir
// test_config_sections_et_render_hub_listent_les_memes_categories) —
// renderConfigTree() itère CE tableau directement, plus de 2e source.
const CONFIG_SECTIONS = [
  ['identity',_ICO_IDENTITY+' 1. Identité'], ['operators',_ICO_OPERATORS+' 2. Opérateurs'],
  ['contest',_ICO_TROPHY+' 3. Sélection du concours'], ['filters',_ICO_CALENDAR+' 4. Dates, bandes &amp; modes'],
  ['radio',_ICO_RADIO+' 5. Radio (CAT)'], ['amp',_ICO_BATTERY+' 6. Amplificateur'],
  ['rotor',_ICO_COMPASS+' 7. Rotor'], ['network',_ICO_CLOUD+' 8. Multi-poste &amp; Cloud'],
  ['backup',_ICO_FLOPPY+' 9. Sauvegarde'], ['sources',_ICO_DISH+' 10. Sources de spots &amp; propagation'],
  ['alerts',_ICO_BELL+' 11. Alertes'], ['qsl',_ICO_ENVELOPE+' 12. QSL &amp; diplômes'],
  ['scoreboard',_ICO_TROPHY+' 13. Scoreboard'], ['expedition',_ICO_GLOBE+' 14. Expédition'],
  ['ai',_ICO_ROBOT+' 15. Assistant IA'], ['relay',_ICO_RELAY+' 16. Station Control (relais)'],
  ['autostart',_ICO_PLAY+' 17. Auto-lancement'], ['pgxl',_ICO_BATTERY+' 18. PowerGenius XL'],
  ['telemetry',_ICO_SIGNAL+' 19. Télémétrie'], ['acom',_ICO_BATTERY+' 20. ACOM'],
  ['summary',_ICO_SUMMARY+' Résumé']
];
// 5 catégories réservées au mode expert (CLAUDE.md « Intuitivité ») — même
// liste que les anciennes .hub-card.expert-only, appliquée maintenant aux
// entrées de l'arborescence elles-mêmes (l'ancien panneau flottant les
// listait TOUTES sans filtre, lacune trouvée par l'investigation du
// 08/08/2026 avant de coder cette refonte).
const _EXPERT_ONLY_CATS = new Set(['relay', 'autostart', 'pgxl', 'telemetry', 'acom']);

function buildConfigSidebar(){
  if(document.getElementById('configSidebar')) return;
  // <nav> (pas <div>) : c'est le seul mécanisme de navigation entre les ~20
  // catégories de réglages CONFIG, exactement comme <nav class="app-nav">
  // en haut de page -- audit accessibilité 09/08/2026 (landmark manquant).
  const nav = document.createElement('nav');
  nav.id = 'configSidebar';
  // Propriété directe (pas setAttribute) : le faux DOM de
  // tests/test_config_category_switch.py (makeFakeNav()) n'implémente pas
  // setAttribute, qui y lèverait une TypeError. .ariaLabel est Baseline
  // "widely available" (Chrome/Edge 123+, Firefox 119+, Safari 15.4+,
  // 2023-2024) -- largement couvert par le Chrome/Edge réel que
  // logx_bootstrap.py lance toujours (jamais un Chromium embarqué figé).
  nav.ariaLabel = 'Catégories de configuration';
  nav.className = 'config-sidebar';
  nav.innerHTML = '<div class="config-sidebar-title">CONFIGURATION</div>'
    // Retour utilisateur (09/08/2026, voir commentaire CSS .config-sidebar-import) :
    // action d'import placée en tête, avant même la 1re catégorie de réglages.
    // Ouvre directement le sélecteur de fichier ICI (10/08/2026, retour F4GLD :
    // « ca devrait plutot ouvrir l'explorateur de fichier pour importer
    // directement ») -- naviguait auparavant vers logx_logbook.html?action=import
    // puis rouvrait le menu DÉBUT/FIN là-bas pour atteindre triggerImport() :
    // un détour à deux clics pour ce qui peut être un seul.
    + '<button type="button" class="config-sidebar-import" onclick="triggerConfigImportAdif()"'
      + ' title="Importer un fichier ADIF depuis un autre logiciel (N1MM+, Win-Test, DXLog, Log4OM, Cloudlog, LoTW...)">'
      + _ICO_IMPORT + ' Importer un log existant</button>'
    + '<div class="config-sidebar-divider"></div>'
    + '<div class="config-sidebar-scroll">'
    + CONFIG_SECTIONS.map(function(s){
        const cat = s[0];
        const divider = cat === 'summary' ? '<div class="config-sidebar-divider"></div>' : '';
        const expertCls = _EXPERT_ONLY_CATS.has(cat) ? ' expert-only' : '';
        return divider + '<button type="button" class="config-sidebar-item' + expertCls + '" data-cat="' + cat
          + '" onclick="switchSection(\'' + cat + '\')">' + s[1]
          + '<span class="tree-badge" id="treebadge_' + cat + '"></span></button>';
      }).join('')
    + '</div>'
    // Chemin critique (CLAUDE.md) épinglé en bas, toujours visible quelle
    // que soit la catégorie ouverte — remplace le bouton du hub disparu.
    + '<button type="button" class="config-sidebar-launch" onclick="launchApp()"><svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 1.8c2.1 1.8 3.1 4.5 2.8 7.8L9 12.3 6.2 9.6C5.9 6.3 6.9 3.6 9 1.8z"/><circle cx="9" cy="6.7" r="1" fill="currentColor" stroke="none"/><path d="M6.2 9.6 4 11l.7 2.7M11.8 9.6 14 11l-.7 2.7"/><path d="M7.4 12.1 9 16.2l1.6-4.1"/></svg> LOGGER</button>';
  document.body.appendChild(nav);
}

// ─── Import ADIF direct depuis CONFIG (10/08/2026) ──────────────────────────
// Même serveur (/log/import_adif/preview puis /commit) que triggerImport()/
// previewImportAdif()/confirmImportAdif() dans logx_import_adif.js (LOGBOOK) --
// mais sans jamais quitter CONFIG : aperçu et confirmation via l'infra
// bandeau/toast déjà en place ici (_confirmConfigBanner()/_configToast(),
// chantier dialogues non bloquants), pas la modale #importOverlay de LOGBOOK
// (absente de cette page). Le sélecteur de fichier s'ouvre en réponse DIRECTE
// au clic (aucune navigation entre les deux) : geste utilisateur valide dans
// tous les navigateurs, contrairement à un site distinct qui tenterait de le
// déclencher tout seul après un chargement de page.
function triggerConfigImportAdif(){
  const inp = document.createElement('input');
  inp.type = 'file'; inp.accept = '.adi,.adif,.ADI,.ADIF';
  inp.onchange = e => {
    const f = e.target.files[0]; if(!f) return;
    const reader = new FileReader();
    reader.onload = ev => _previewConfigImportAdif(ev.target.result);
    reader.readAsText(f, 'UTF-8');
  };
  inp.click();
}

async function _previewConfigImportAdif(text){
  let p;
  try{
    const res = await fetch('/log/import_adif/preview', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({adif: text}),
    });
    p = await res.json();
  }catch(e){
    _configToast('Serveur injoignable : ' + e.message);
    return;
  }
  if(!p.ok){
    _configToast('Erreur : ' + (p.error || 'Fichier illisible'));
    return;
  }
  if(p.new === 0){
    _configToast(`Aucun nouveau QSO à importer (${p.duplicates} déjà dans le log).`);
    return;
  }
  const errPart = (p.errors && p.errors.length) ? `, ${p.errors.length} ignorés` : '';
  const msg = `${p.total_in_file} QSO dans le fichier — ${p.new} nouveaux, ${p.duplicates} déjà dans le log${errPart}.\n\nImporter les ${p.new} nouveaux QSO ?`;
  if(!(await _confirmConfigBanner(msg, 'Importer', 'Annuler'))) return;
  try{
    const r2 = await (await fetch('/log/import_adif/commit', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({adif: text}),
    })).json();
    if(r2.ok){
      const err2 = (r2.errors && r2.errors.length) ? `, ${r2.errors.length} ignorés` : '';
      _configToast(`Import terminé : ${r2.imported} QSO importés${err2}.`);
    } else {
      _configToast('Import échoué : ' + (r2.error || 'erreur inconnue'));
    }
  }catch(e){
    _configToast('Import échoué : ' + e.message);
  }
}

function _currentOpenCat(){
  for(const s of CONFIG_SECTIONS){
    const m = document.getElementById('catmodal_' + s[0]);
    if(m && m.style.display === 'block') return s[0];
  }
  return null;
}

// ─── Avertir avant de perdre des modifications non enregistrées ─────────────
// Photo des champs d'UNE section (catbody_<cat>) prise à l'ouverture ET à
// chaque sauvegarde réussie (voir saveConfig()) — comparée à l'état courant
// au moment de fermer. Ne remplace PAS la règle F4GLD du 04/08/2026 (fermer
// ne sauvegarde jamais) : avertit seulement qu'on va PERDRE quelque chose,
// laisse l'opérateur annuler la fermeture pour aller cliquer Enregistrer.
let _catFormSnapshots = {};

function _snapshotCatForm(cat){
  const body = document.getElementById('catbody_' + cat);
  if(!body) return null;
  const vals = [];
  body.querySelectorAll('input,select,textarea').forEach(el => {
    // Groupe de boutons radio SANS id individuel (ex. choix du fournisseur
    // IA, .catbody_ai : 6 <input type="radio" name="api_provider"> sans id)
    // — suivi par `name`, seul l'état "checked" compte, sinon un changement
    // de sélection passait inaperçu (trouvé par la revue adversariale du
    // 08/08/2026 : changer de fournisseur IA puis Fermer ne prévenait pas).
    if(el.type === 'radio' && !el.id){ if(el.name) vals.push('radio:' + el.name + ':' + el.checked); return; }
    if(!el.id) return;
    vals.push(el.id + ':' + ((el.type === 'checkbox' || el.type === 'radio') ? el.checked : el.value));
  });
  return vals.join('|');
}

function _catHasUnsavedChanges(cat){
  if(!cat || _catFormSnapshots[cat] === undefined) return false;
  return _snapshotCatForm(cat) !== _catFormSnapshots[cat];
}

// Message unique, réutilisé aux deux points de sortie (bouton Fermer d'une
// section ET clic à côté du popup / bouton Fermer de la barre latérale).
async function _confirmDiscardCatChanges(cat){
  if(!_catHasUnsavedChanges(cat)) return true;
  return await _confirmConfigBanner(T('Des modifications de cette section n\'ont pas été enregistrées. Fermer quand même et les perdre ?'), 'Fermer sans enregistrer', 'Annuler');
}
async function openCategoryPopup(cat){
  // Avant de basculer : si la section actuellement ouverte a des
  // modifications non enregistrées, avertir -- que ce soit via un clic sur
  // une autre entrée de l'arborescence (switchSection()) ou un appel direct
  // (deep-link ?contest=ID, détection CAT auto...). Un refus annule TOUT le
  // changement de section (trouvé par la revue adversariale du 08/08/2026 :
  // avant, seul un ancien mécanisme de fermeture chaînée vérifiait ce garde,
  // pas openCategoryPopup() lui-même).
  let _curAvantOuverture = null;
  try { _curAvantOuverture = (typeof _currentOpenCat === 'function') ? _currentOpenCat() : null; } catch(e){}
  // Re-cliquer l'entrée DÉJÀ active de l'arborescence permanente est un geste
  // courant (elle reste visible et cliquable en continu, contrairement à
  // l'ancien hub caché derrière la popup une fois ouverte) : sans ce no-op
  // explicite, le code plus bas retombait jusqu'à la ligne finale qui
  // réécrit INCONDITIONNELLEMENT _catFormSnapshots[cat] avec l'état COURANT
  // du formulaire -- effaçant silencieusement le marqueur de modifications
  // non enregistrées, sans jamais solliciter confirm(), avant même de
  // changer de section (trouvé par la revue adversariale du 08/08/2026).
  if(_curAvantOuverture === cat) return true;
  if(_curAvantOuverture && _curAvantOuverture !== cat && !(await _confirmDiscardCatChanges(_curAvantOuverture))) return;
  // CŒUR d'abord : masquer la section ouverte, montrer la demandée. Fait AVANT
  // la barre latérale pour qu'un environnement minimal (tests) où
  // createElement/body n'existent pas ouvre quand même la bonne section.
  try {
    const cur = _curAvantOuverture;
    if(cur && cur !== cat){ const mo = document.getElementById('catmodal_' + cur); if(mo) mo.style.display = 'none'; delete _catFormSnapshots[cur]; }
  } catch(e){}
  const modal = document.getElementById('catmodal_' + cat);
  if(modal) modal.style.display = 'block';
  try {
    buildConfigSidebar();
    const nav = document.getElementById('configSidebar');
    if(nav) nav.querySelectorAll('.config-sidebar-item').forEach(function(b){ b.classList.toggle('active', b.dataset.cat === cat); });
  } catch(e){}
  // Planning de roulement : liste ET options du <select> reconstruites à chaque
  // ouverture — les créneaux vivent côté serveur, hors de l'état de config.
  if(cat === 'operators'){
    refreshShiftOperatorSelect();
    loadShifts();
  }
  // Résumé : recalculé à chaque ouverture (recap texte + prompt système),
  // comme l'ancien openSummaryPopup() avant la fusion dans l'arborescence.
  if(cat === 'summary') buildSummary();
  _catFormSnapshots[cat] = _snapshotCatForm(cat);
}
function switchSection(cat){ openCategoryPopup(cat); }

// Statut d'une catégorie pour le badge de sa carte : 'ok' (✅), 'warning' (⚠️,
// remplie mais invalide/incomplète), 'empty' (○, non configurée — souvent
// normal, ces catégories sont majoritairement optionnelles).
function _catStatus(cat){
  const val = id => (document.getElementById(id)?.value || '').trim();
  switch(cat){
    case 'identity': {
      if(!val('callsign')) return 'empty';
      const loc = val('locator');
      return (loc && isValidLocator(loc)) ? 'ok' : 'warning';
    }
    case 'operators':
      return val('op1_call') ? 'ok' : 'empty';
    case 'contest':
      if(_contestOptional()) return 'ok'; // pas requis dans ce mode (H4/M4)
      return state.contest ? 'ok' : 'empty';
    case 'filters': {
      if(getUsageMode() === 'simple') return 'ok';
      const hasBand = !!document.querySelector('[data-key^="band_"].on');
      const hasMode = !!document.querySelector('[data-key^="mode_"].on');
      const sd = val('contest_start_date'), ed = val('contest_end_date');
      const datesOk = !(sd && ed && ed < sd);
      return (hasBand && hasMode && datesOk) ? 'ok' : 'warning';
    }
    case 'radio':
      return val('cat_enabled') === '1' ? 'ok' : 'empty';
    case 'amp':
      return val('amp_enabled') === '1' ? 'ok' : 'empty';
    case 'rotor':
      return val('rotor_enabled') === '1' ? 'ok' : 'empty';
    case 'network':
      return val('cloudsync_mode') ? 'ok' : 'empty';
    case 'backup':
      return val('backup_folder') ? 'ok' : 'empty';
    case 'sources':
      return 'empty'; // toggles multiples (cluster/RBN/ON4KST) — pas de statut unique pertinent
    case 'alerts':
      return (state.alertRules && state.alertRules.length) ? 'ok' : 'empty';
    case 'qsl': {
      if(val('clublog_live') === '1'){
        const missing = ['clublog_email','clublog_callsign','clublog_password','clublog_api_key']
          .some(id => !val(id));
        if(missing) return 'warning';
      }
      if(val('qrz_logbook_push') === '1' && !val('qrz_logbook_key')) return 'warning';
      return 'ok';
    }
    case 'scoreboard':
      return 'empty'; // section optionnelle, pas de champ requis
    case 'expedition':
      return getUsageMode() === 'expedition' ? (val('activation_program') ? 'ok' : 'warning') : 'empty';
    case 'ai':
      return val('api_key') ? 'ok' : 'empty';
    case 'relay':
      return val('relay_enabled') === '1' ? 'ok' : 'empty';
    case 'autostart':
      return autostartRows.length ? 'ok' : 'empty';
    case 'pgxl':
      return val('pgxl_enabled') === '1' ? 'ok' : 'empty';
    case 'acom':
      return val('acom_enabled') === '1' ? 'ok' : 'empty';
    case 'telemetry':
      return val('telemetry_enabled') === '1' ? 'ok' : 'empty';
    case 'summary':
      return 'empty'; // recap pur, pas de champ propre — pas de statut pertinent
    default:
      return 'empty';
  }
}

const _CAT_BADGE = { ok: 'status-ok', warning: 'status-warning', empty: 'status-empty' };
// Libellés du title= des points de statut (accessibilité daltonien — retour
// audit trouvabilité 09/08/2026 : la couleur seule ne dit rien au survol).
const _CAT_BADGE_TITLE = {
  ok: 'Catégorie configurée', warning: 'Configuration incomplète', empty: 'Pas encore configuré',
};

// Renommée depuis renderHub() (le hub de cartes a disparu avec la refonte
// sidebar du 08/08/2026) : rafraîchit le point de statut de CHAQUE entrée de
// l'arborescence. Itère CONFIG_SECTIONS directement, plus de liste dupliquée
// à tenir synchronisée (voir commentaire sur CONFIG_SECTIONS).
function renderConfigTree(){
  CONFIG_SECTIONS.forEach(function(s){
    const badge = document.getElementById('treebadge_' + s[0]);
    if(!badge) return;
    badge.classList.remove('status-ok','status-warning','status-empty');
    const st = _catStatus(s[0]);
    badge.classList.add(_CAT_BADGE[st] || 'status-empty');
    badge.title = _CAT_BADGE_TITLE[st] || _CAT_BADGE_TITLE.empty;
  });
}

// ─── RÈGLES D'ALERTE PERSONNALISÉES (évaluées côté serveur, logx_alerts.py) ─
const CONTINENT_LABEL = {EU:'Europe', NA:'Amérique du Nord', SA:'Amérique du Sud',
                         AF:'Afrique', AS:'Asie', OC:'Océanie', AN:'Antarctique'};

function renderAlertRules(){
  const el = document.getElementById('alertRulesList');
  if(!el) return;
  const rules = state.alertRules || [];
  if(!rules.length){
    el.innerHTML = '<div style="color:var(--muted);font-family:var(--font-mono);font-size:13px">Aucune règle personnalisée pour l\'instant.</div>';
    return;
  }
  el.innerHTML = rules.map(r => {
    const bits = [];
    if(r.call_prefix) bits.push('préfixe ' + r.call_prefix);
    if(r.continent) bits.push(CONTINENT_LABEL[r.continent] || r.continent);
    if(r.cq_zone) bits.push('zone CQ ' + r.cq_zone);
    if(r.band) bits.push(r.band + ' MHz');
    if(r.status === 'new_mult') bits.push('nouveau mult');
    if(r.status === 'already_done') bits.push('déjà travaillé');
    if(r.comment_contains) bits.push('commentaire « ' + r.comment_contains + ' »');
    const on = r.enabled !== false;
    return `<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border);font-family:var(--font-mono);font-size:13px">
      <span class="toggle-btn${on?' on':''}" style="padding:4px 10px" onclick="toggleAlertRule('${r.id}')">${on?'<svg viewBox="0 0 18 18" width="11" height="11" style="vertical-align:-1px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3,10 7,14 15,4"/></svg> actif':'<svg viewBox="0 0 18 18" width="11" height="11" style="vertical-align:-1px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4.5" y1="4.5" x2="13.5" y2="13.5"/><line x1="13.5" y1="4.5" x2="4.5" y2="13.5"/></svg> coupé'}</span>
      <b style="flex:1;color:var(--text)">${r.name}</b>
      <span style="color:var(--muted)">${bits.join(' · ') || 'tout spot'}</span>
      <button type="button" class="btn btn-secondary" style="padding:4px 10px;font-size:11px" onclick="deleteAlertRule('${r.id}')" title="Supprimer cette règle d'alerte"><svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="5" x2="15" y2="5"/><path d="M6.5 5V3.5h5V5"/><path d="M4.5 5 5.2 15h7.6L13.5 5"/><line x1="7.5" y1="7.5" x2="7.5" y2="12.5"/><line x1="10.5" y1="7.5" x2="10.5" y2="12.5"/></svg></button>
    </div>`;
  }).join('');
}

function addAlertRule(){
  const msg = document.getElementById('ruleAddMsg');
  const name = document.getElementById('newRuleName').value.trim();
  if(!name){
    if(msg){ msg.textContent = '⚠️ Donne un nom à la règle'; msg.style.color = 'var(--yellow)'; }
    return;
  }
  const rule = {
    id: 'r' + Date.now(),
    name, enabled: true,
    call_prefix: document.getElementById('newRulePrefix').value.trim().toUpperCase(),
    continent: document.getElementById('newRuleContinent').value,
    cq_zone: document.getElementById('newRuleCqZone').value.trim(),
    band: document.getElementById('newRuleBand').value.trim(),
    status: document.getElementById('newRuleStatus').value,
    comment_contains: document.getElementById('newRuleComment').value.trim(),
  };
  state.alertRules = (state.alertRules || []).concat([rule]);
  renderAlertRules();
  ['newRuleName','newRulePrefix','newRuleCqZone','newRuleBand','newRuleComment'].forEach(id => {
    document.getElementById(id).value = '';
  });
  document.getElementById('newRuleContinent').value = '';
  document.getElementById('newRuleStatus').value = 'any';
  if(msg){ msg.textContent = '✅ Règle ajoutée — pense à SAUVEGARDER CONFIG'; msg.style.color = 'var(--green)'; }
}

function toggleAlertRule(id){
  const r = (state.alertRules || []).find(x => x.id === id);
  if(r){ r.enabled = r.enabled === false ? true : false; renderAlertRules(); }
}

function deleteAlertRule(id){
  state.alertRules = (state.alertRules || []).filter(x => x.id !== id);
  renderAlertRules();
}

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

// ─── Mot de passe d'accès optionnel (voir logx_http._access_password_enabled) ─
// Volontairement PAS dans saveConfig()/le gros objet `config` : /config/save
// REMPLACE tout current_config à chaque sauvegarde (y compris la sauvegarde
// silencieuse déclenchée par chaque étape) — un champ mot de passe toujours
// vide dans ce formulaire (on ne peut pas ré-afficher un hash) aurait effacé
// la protection à la sauvegarde suivante de n'importe quel AUTRE réglage.
// Route dédiée /auth/set_password à la place, comme /ui/theme.
async function refreshAccessPasswordStatus(){
  const el = document.getElementById('accessPasswordStatus');
  const disableBtn = document.getElementById('disableAccessPasswordBtn');
  if(!el) return;
  try{
    const res = await fetch('/auth/status');
    const d = await res.json();
    if(d.enabled){
      el.textContent = "🔒 Protection activée — un mot de passe est requis pour obtenir les droits d'écriture.";
      el.style.color = 'var(--accent2)';
      if(disableBtn) disableBtn.style.display = '';
    } else {
      el.textContent = '🔓 Aucun mot de passe configuré — accès en écriture automatique (comportement par défaut).';
      el.style.color = 'var(--muted)';
      if(disableBtn) disableBtn.style.display = 'none';
    }
  }catch(e){
    el.textContent = 'Statut indisponible (serveur injoignable).';
    el.style.color = 'var(--red)';
  }
}

async function setAccessPassword(){
  const input = document.getElementById('access_password');
  const pw = input.value;
  const result = document.getElementById('accessPasswordResult');
  if(!pw){
    result.textContent = "Champ vide — utilise « Désactiver la protection » pour la retirer.";
    result.style.color = 'var(--muted)';
    return;
  }
  if(pw.length < 4){
    result.textContent = '⚠️ 4 caractères minimum.';
    result.style.color = 'var(--red)';
    return;
  }
  result.textContent = '⏳ enregistrement…';
  result.style.color = 'var(--muted)';
  try{
    const res = await fetch('/auth/set_password', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({password: pw}),
    });
    const d = await res.json();
    if(d.ok){
      result.textContent = '✅ Mot de passe enregistré.';
      result.style.color = 'var(--green)';
      input.value = '';
      refreshAccessPasswordStatus();
    } else {
      result.textContent = `❌ ${d.error || 'échec'}`;
      result.style.color = 'var(--red)';
    }
  }catch(e){
    result.textContent = `❌ Serveur injoignable : ${e.message}`;
    result.style.color = 'var(--red)';
  }
}

async function disableAccessPassword(){
  if(!(await _confirmConfigBanner("Désactiver la protection ? Tout appareil du réseau obtiendra de nouveau les droits d'écriture automatiquement.", 'Désactiver', 'Annuler'))) return;
  const result = document.getElementById('accessPasswordResult');
  try{
    const res = await fetch('/auth/set_password', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({password: ''}),
    });
    const d = await res.json();
    if(d.ok){
      result.textContent = '✅ Protection désactivée.';
      result.style.color = 'var(--green)';
    } else {
      result.textContent = `❌ ${d.error || 'échec'}`;
      result.style.color = 'var(--red)';
    }
    document.getElementById('access_password').value = '';
    refreshAccessPasswordStatus();
  }catch(e){
    result.textContent = `❌ Serveur injoignable : ${e.message}`;
    result.style.color = 'var(--red)';
  }
}

// ─── FILTRES AUTOMATIQUES PAR CONCOURS ────────────────────────────────────────
// Correctif [audit config bandes/modes] : la grille de toggles était filtrée
// par un objet client codé à la main (CONTEST_FILTERS, ~35 concours) qui ne
// couvrait ni les concours personnalisés (custom_contests.json) ni les futurs
// concours serveur, et ne masquait jamais les MODES hors règlement (seulement
// les bandes) — un opérateur pouvait cocher un mode que le concours n'autorise
// pas. Source de vérité désormais : SERVER_CONTEST_RULES (rempli par
// mergeServerContests() depuis /data/calendar, lui-même dérivé de
// CONTEST_DEFINITIONS + custom_contests.json côté serveur), traduit vers les
// clés toggle via BAND_TOGGLE_KEY/MODE_TOGGLE_KEY (repris tels quels de
// logx_logbook.js pour ne pas re-diverger une 2e fois du même mapping — c'est
// exactement l'absence de clé WWA FT2/PSK dans CONTEST_FILTERS qui avait
// provoqué le bug constaté par l'audit).
//
// LEGACY_CONTEST_FILTERS ne sert plus que de repli pour les quelques concours
// ABSENTS de CONTEST_DEFINITIONS (parties CCD mensuelles, TVA, Marconi, F8TD,
// 50 MHz REF/IARU, UFT...) : leur règlement n'existe nulle part ailleurs côté
// serveur, donc cette table reste ici l'unique source pour CES ids précis —
// ce n'est plus une duplication du même règlement que celui déjà exposé par
// /data/calendar (voir _resolveContestFilters ci-dessous).
const LEGACY_CONTEST_FILTERS = {

  // ── Challenge THF annuel cumulatif (144MHz→47GHz, tous modes)
  'REF_CHALLENGE_THF': { modes:['mode_ssb','mode_cw','mode_fm','mode_ft8','mode_ft4'],
                          bands:['band_2m','band_70cm','band_23cm','band_13cm','band_9cm','band_6cm','band_3cm','band_6mm','band_4mm'] },

  // ── CCD parties THF (432/1296/2320 MHz = 70cm+23cm+13cm)
  'REF_CCD_JAN1':  { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_70cm','band_23cm','band_13cm'] },
  'REF_CCD_FEV1':  { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_70cm','band_23cm','band_13cm'] },
  'REF_CCD_MAI':   { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_70cm','band_23cm','band_13cm'] },
  'REF_CCD_OCT':   { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_70cm','band_23cm','band_13cm'] },

  // ── CCD parties 144 MHz (SSB+CW+FM)
  'REF_CCD_JAN2':  { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_2m'] },
  'REF_CCD_FEV2':  { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_2m'] },
  'REF_CCD_MAR':   { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_2m'] },
  'REF_CCD_NOV':   { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_2m'] },
  'REF_CCD_DEC':   { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_2m'] },

  // ── CCD CW uniquement (144 MHz)
  'REF_CCD_AVR_CW':{ modes:['mode_cw'], bands:['band_2m'] },
  'REF_CCD_DEC_CW':{ modes:['mode_cw'], bands:['band_2m'] },

  // ── TVA (ATV/FM relais — 70cm+23cm)
  'REF_NAT_TVA':     { modes:['mode_fm'], bands:['band_70cm','band_23cm'] },
  'REF_IARU_TVA':    { modes:['mode_fm'], bands:['band_70cm','band_23cm'] },
  'REF_CDF_TVA':     { modes:['mode_fm'], bands:['band_70cm','band_23cm'] },
  'REF_NAT_TVA_DEC': { modes:['mode_fm'], bands:['band_70cm','band_23cm'] },

  // ── 50 MHz
  'REF_DDFM_50':   { modes:['mode_ssb','mode_cw','mode_fm'], bands:['band_6m'] },
  'REF_IARU_50':   { modes:['mode_ssb','mode_cw'],           bands:['band_6m'] },
  'IARU_50':       { modes:['mode_ssb','mode_cw'],           bands:['band_6m'] },

  // ── F8TD — SHF uniquement (1296MHz→47GHz, SSB+CW)
  'REF_F8TD':      { modes:['mode_ssb','mode_cw'],
                     bands:['band_23cm','band_13cm','band_9cm','band_6cm','band_3cm','band_6mm','band_4mm'] },

  // ── IARU VHF (144MHz uniquement, SSB+CW) — id historique REF_IARU_VHF,
  // distinct de IARU_VHF (celui-ci EST dans CONTEST_DEFINITIONS)
  'REF_IARU_VHF':  { modes:['mode_ssb','mode_cw'], bands:['band_2m'] },

  // ── Marconi (144MHz, CW UNIQUEMENT) — id historique REF_MARCONI, distinct
  // de IARU_MARCONI (CONTEST_DEFINITIONS)
  'REF_MARCONI':   { modes:['mode_cw'], bands:['band_2m'] },

  // ── IARU UHF/SHF (432MHz→47GHz) — id historique REF_IARU_UHF, distinct de
  // IARU_UHF (CONTEST_DEFINITIONS)
  'REF_IARU_UHF':  { modes:['mode_ssb','mode_cw'],
                     bands:['band_70cm','band_23cm','band_13cm','band_9cm','band_6cm','band_3cm','band_6mm','band_4mm'] },

  // ── UFT (HF 80→10m, CW uniquement)
  'F9NL':          { modes:['mode_cw'], bands:['band_80m','band_40m','band_20m','band_15m','band_10m'] },
  'UFT_RENCONTRES':{ modes:['mode_cw'], bands:['band_80m','band_40m','band_20m','band_15m','band_10m'] },
};

// Correspondance valeur bande serveur (MHz brut, ex. '144') → clé toggle —
// copie exacte de BAND_TOGGLE_KEY (logx_logbook.js, ~ligne 2318) : même
// mapping, pas de 2e version qui pourrait diverger.
const BAND_TOGGLE_KEY = {
  '1.8':   'band_160m', '3.5':   'band_80m',  '7':     'band_40m',
  '10.1':  'band_30m',  '14':    'band_20m',  '18':    'band_17m',
  '21':    'band_15m',  '24':    'band_12m',  '28':    'band_10m',
  '50':    'band_6m',   '70':    'band_4m',    '144':   'band_2m',
  '432':   'band_70cm', '1296':  'band_23cm',  '2320':  'band_13cm',
  '3400':  'band_9cm',  '5760':  'band_6cm',   '10368': 'band_3cm',
  '24048': 'band_6mm',  '47088': 'band_4mm',
};

// Correspondance mode serveur → clé toggle — copie exacte de MODE_TOGGLE_KEY
// (logx_logbook.js, ~ligne 2362), y compris les rattachements WWA FT2→FT8 et
// PSK→RTTY déjà en place (règlement WWA §5, même famille "DIGI").
const MODE_TOGGLE_KEY = {
  'SSB':  'mode_ssb',
  'CW':   'mode_cw',
  'FM':   'mode_fm',
  'FT8':  'mode_ft8',
  'FT4':  'mode_ft4',
  'RTTY': 'mode_rtty',
  'SSTV': 'mode_sstv',  // mode d'activité (dimanches SSTV, ISS) — jamais imposé par un concours
  'DIGI': 'mode_ft8',
  'FT2':  'mode_ft8',   // WWA (règlement §5) — pas de toggle dédié, rattaché à FT8
  'PSK':  'mode_rtty',  // WWA — rattaché à RTTY (même famille "DIGI" au règlement)
};

// Résout les clés toggle bandes/modes autorisées pour un concours :
// 1. règlement serveur (SERVER_CONTEST_RULES, source de vérité) ;
// 2. à défaut, repli LEGACY_CONTEST_FILTERS (concours absents côté serveur) ;
// 3. sinon null → aucune restriction (comportement sûr par défaut).
// Les deux axes (bandes/modes) sont résolus INDÉPENDAMMENT l'un de l'autre :
// 'all' explicite, ou un règlement dont aucun code ne se traduit via
// BAND_TOGGLE_KEY/MODE_TOGGLE_KEY, lève la restriction sur CET axe seul —
// jamais sur l'autre. Avant ce correctif, un OR unique (bands.includes('all')
// || modes.includes('all')) levait TOUTE restriction dès que l'un des deux
// axes était 'all', y compris quand l'autre axe listait des valeurs précises
// (ex. bands:['all'], modes:['CW'] laissait SSB/FT8/... cochables alors que
// seul CW est autorisé). Le retour est { bands, modes } où chaque champ vaut
// soit un tableau de clés à restreindre, soit null si l'axe est libre.
function _resolveContestFilters(contestId) {
  const rules = SERVER_CONTEST_RULES[contestId];
  if (rules) {
    const bands = rules.bands || [];
    const modes = rules.modes || [];
    const bandKeys = bands.includes('all') ? [] : [...new Set(bands.map(b => BAND_TOGGLE_KEY[b]).filter(Boolean))];
    const modeKeys = modes.includes('all') ? [] : [...new Set(modes.map(m => MODE_TOGGLE_KEY[m]).filter(Boolean))];
    const restrictBands = bandKeys.length > 0;
    const restrictModes = modeKeys.length > 0;
    if (!restrictBands && !restrictModes) return null; // aucun des deux axes n'a de restriction traduisible
    return { bands: restrictBands ? bandKeys : null, modes: restrictModes ? modeKeys : null };
  }
  return LEGACY_CONTEST_FILTERS[contestId] || null;
}

const HF_BANDS  = ['band_vlf','band_160m','band_80m','band_60m','band_40m','band_30m','band_20m','band_17m','band_15m','band_12m','band_10m','band_8m'];
const VHF_BANDS = ['band_6m','band_4m','band_2m','band_220','band_70cm','band_23cm','band_13cm','band_9cm','band_6cm','band_3cm','band_6mm','band_4mm','band_qo100','band_sat'];

function applyContestFilters(contestId) {
  const secHF  = document.getElementById('section_hf');
  const secVHF = document.getElementById('section_vhf');

  // Réafficher tout par défaut (si pas de filtre)
  document.querySelectorAll('[data-key^="band_"], [data-key^="mode_"]').forEach(el => {
    el.style.display = '';
  });
  if(secHF)  secHF.style.display  = '';
  if(secVHF) secVHF.style.display = '';

  const note = document.getElementById('filterAutoNote');
  // LOGBOOK SIMPLE : pas de concours -> pas de restriction de règlement,
  // toutes les bandes/tous les modes radioamateur restent sélectionnables
  // (même si un concours a été choisi ou testé précédemment).
  const filters = getUsageMode() === 'simple' ? null : _resolveContestFilters(contestId);

  if (!filters) {
    // Aucun règlement connu (serveur ou repli) → tout laisser visible, cacher la note
    if(note) note.style.display = 'none';
    return;
  }

  // Chaque axe est traité indépendamment : filters.bands/filters.modes vaut
  // soit un tableau de clés à restreindre, soit null si CET axe est libre
  // (auquel cas on ne touche à rien pour ce type de clé — déjà tout visible
  // depuis la réinitialisation ci-dessus, et les toggles existants restent
  // intacts). Avant ce correctif, filters.bands/.modes étaient toujours des
  // tableaux (jamais null), donc un axe non-restrictif masquait quand même
  // tout puis ne réaffichait rien (voir Problème 4 du correctif).
  const bandKeys = filters.bands;
  const modeKeys = filters.modes;

  // ── 1. Bandes : si l'axe est restreint, tout désactiver/cacher puis ne
  // réafficher/cocher que les autorisées.
  if (bandKeys) {
    document.querySelectorAll('[data-key^="band_"]').forEach(el => {
      el.classList.remove('on');
      state.toggles[el.dataset.key] = false;
      el.style.display = 'none';
    });
    bandKeys.forEach(key => {
      const el = document.querySelector(`[data-key="${key}"]`);
      if(el){ el.style.display = ''; el.classList.add('on'); state.toggles[key] = true; }
    });
  }

  // ── 2. Modes : même traitement, indépendant de l'axe bandes (avant ce
  // correctif, seules les bandes étaient masquées : un mode hors règlement
  // restait cochable librement, juste pré-coché sur les modes autorisés).
  if (modeKeys) {
    document.querySelectorAll('[data-key^="mode_"]').forEach(el => {
      el.classList.remove('on');
      state.toggles[el.dataset.key] = false;
      el.style.display = 'none';
    });
    modeKeys.forEach(key => {
      const el = document.querySelector(`[data-key="${key}"]`);
      if(el){ el.style.display = ''; el.classList.add('on'); state.toggles[key] = true; }
    });
  }

  // ── 3. Masquer les sections HF/VHF entières seulement si l'axe bandes est
  // effectivement restreint (sinon toutes les bandes restent visibles, donc
  // les deux sections aussi).
  if (bandKeys) {
    const hasHF  = bandKeys.some(b => HF_BANDS.includes(b));
    const hasVHF = bandKeys.some(b => VHF_BANDS.includes(b));
    if(secHF)  secHF.style.display  = hasHF  ? '' : 'none';
    if(secVHF) secVHF.style.display = hasVHF ? '' : 'none';
  }

  // ── 4. Notification
  if(note){
    const contest = CONTESTS.find(c => c.id === contestId);
    const name = contest ? contest.name : contestId;
    const bandNames = bandKeys ? bandKeys.map(b => {
      const el = document.querySelector(`[data-key="${b}"]`);
      return el ? el.textContent.trim() : b;
    }).join(' · ') : '';
    const modeNames = modeKeys ? modeKeys.map(m => {
      const el = document.querySelector(`[data-key="${m}"]`);
      return el ? el.textContent.trim() : m;
    }).join(' · ') : '';
    note.innerHTML = `<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><polyline points="3,10 7,14 15,4"/></svg> <strong>${name}</strong>`
      + (bandKeys ? ` — Bandes autorisées par le règlement : ${bandNames}` : '')
      + (modeKeys ? `<br>Modes autorisés : ${modeNames}` : '')
      + `<br><small style="opacity:.8">Seules les bandes/modes du règlement sont affichés. Tu peux en désactiver certains si tu ne les utilises pas.</small>`;
    note.style.display = 'block';
  }
}

// Correctif M3 : les attributs min/max HTML d'un <input type="number"> ne
// contraignent que les flèches du spinner natif — une valeur tapée ou collée
// au clavier (ex. altitude="-500", alert_volume="-10") passait telle quelle
// jusqu'à saveConfig() puis était persistée sans aucun contrôle. Un champ vide
// ou non numérique retombe sur `fallback` (même convention que les anciens
// `parseInt(...) || N` déjà présents ailleurs dans ce fichier).
function _numClamped(id, fallback){
  const el = document.getElementById(id);
  let v = parseInt(el.value, 10);
  if(isNaN(v)) v = fallback;
  if(el.min !== '') v = Math.max(Number(el.min), v);
  if(el.max !== '') v = Math.min(Number(el.max), v);
  return v;
}

// Garde-fou H2 : liste ce qui manque pour atteindre l'étape `forStep` sans
// perte silencieuse (indicatif/locator invalides ou concours non choisi
// laissaient auparavant sauter directement à RÉSUMÉ → LOGGER sans avertissement).
// Chaque entrée est {message, category} -- category est l'ID CONFIG_SECTIONS
// de la carte à ouvrir (switchSection()), utilisé par le bandeau de
// validation (chantier 2, audit accessibilité 09/08/2026) pour transformer
// chaque ligne en lien cliquable direct vers le bon réglage. Les anciens
// libellés référençaient une "étape" (assistant par étapes .step/.panel,
// retiré le 08/08/2026 avec la refonte sidebar) -- remplacés par le nom de
// la section réelle qui existe aujourd'hui.
function _missingStationFields(forStep){
  const missing = [];
  if(forStep >= 2){
    if(!document.getElementById('callsign').value.trim())
      missing.push({message: 'INDICATIF (section Identité)', category: 'identity'});
    const loc = document.getElementById('locator').value.trim();
    if(!loc || !isValidLocator(loc))
      missing.push({message: 'LOCATOR MAIDENHEAD valide, ex. JN15XC (section Identité)', category: 'identity'});
  }
  if(forStep >= 3){
    if(!_contestOptional() && !state.contest){
      missing.push({message: 'un CONCOURS sélectionné (section Sélection du concours)', category: 'contest'});
    }
    // Correctif M2 : selectContest() pose des dates cohérentes à la sélection
    // d'un concours, mais rien n'empêchait ensuite une édition manuelle de
    // casser l'ordre (date de fin antérieure à la date de début), sans
    // aucun avertissement au moment de sauvegarder/lancer.
    const sd = document.getElementById('contest_start_date').value;
    const ed = document.getElementById('contest_end_date').value;
    if(sd && ed && ed < sd){
      missing.push({message: 'DATE FIN doit être postérieure ou égale à DATE DÉBUT (section Dates, bandes & modes)', category: 'filters'});
    }
  }
  // Correctif M4 : aucune sauvegarde explicite ni lancement n'était bloqué
  // même avec zéro bande et zéro mode actifs à l'étape FILTRES — config
  // inexploitable acceptée en silence.
  if(forStep >= 4){
    if(!document.querySelector('[data-key^="band_"].on'))
      missing.push({message: 'au moins une BANDE active (section Dates, bandes & modes)', category: 'filters'});
    if(!document.querySelector('[data-key^="mode_"].on'))
      missing.push({message: 'au moins un MODE actif (section Dates, bandes & modes)', category: 'filters'});
  }
  return missing;
}

// Bandeau de validation non bloquant (chantier 2, audit accessibilité
// 09/08/2026) : remplace l'alert() natif qui gelait toute la page pour un
// simple rappel de champs manquants -- chaque ligne devient un lien direct
// vers la bonne section (switchSection()) au lieu d'obliger l'utilisateur à
// mémoriser la liste et chercher lui-même dans l'arborescence. items :
// [{message, category?}] -- category absente = ligne de texte simple (utilisé
// par les alertes ClubLog/QRZ/SOTA plus bas, un seul item, pas de lien car le
// message dit déjà où agir).
function _showConfigValidationBanner(items){
  const list = document.getElementById('configValidationList');
  list.innerHTML = '';
  items.forEach(item => {
    const li = document.createElement('li');
    if(item.category){
      const a = document.createElement('a');
      a.href = '#';
      a.textContent = item.message;
      a.style.color = 'var(--accent2)';
      a.onclick = e => { e.preventDefault(); _dismissConfigValidationBanner(); switchSection(item.category); };
      li.appendChild(a);
    } else {
      li.textContent = item.message;
    }
    list.appendChild(li);
  });
  document.getElementById('configValidationBanner').style.display = 'block';
}

function _dismissConfigValidationBanner(){
  document.getElementById('configValidationBanner').style.display = 'none';
}

function _warnMissingStation(missing){
  _showConfigValidationBanner(missing);
}

// ─── TOAST + BANDEAU DE CONFIRMATION NON BLOQUANTS (chantier dialogues non
// bloquants, 10/08/2026) : remplacent les alert()/confirm() natifs restants
// de cette page (succès de sauvegarde, profils, géolocalisation, protection
// réseau...) -- un dialogue natif gèle toute la page et déplace le focus
// hors du contrôle de l'app. Même patron que logx_logbook.js
// (_confirmDupBanner()/notify()), dupliqué ici faute de portée JS partagée.
function _configToast(message, ms){
  const t = document.getElementById('configToast');
  t.textContent = message;
  t.style.display = 'block';
  clearTimeout(_configToast._tm);
  _configToast._tm = setTimeout(() => { t.style.display = 'none'; }, ms || Math.min(10000, 2500 + String(message).length * 35));
}

let _pendingConfigConfirmResolve = null;

function _confirmConfigBanner(message, yesLabel, noLabel){
  _cancelPendingConfigConfirm();   // un bandeau resté ouvert d'une tentative précédente ne doit pas s'empiler
  return new Promise(resolve => {
    _pendingConfigConfirmResolve = resolve;
    document.getElementById('configConfirmMsg').textContent = message;
    document.getElementById('configConfirmYesBtn').textContent = yesLabel || 'Confirmer';
    document.getElementById('configConfirmNoBtn').textContent = noLabel || 'Annuler';
    document.getElementById('configConfirmBanner').style.display = 'block';
  });
}

function _resolveConfigConfirm(result){
  document.getElementById('configConfirmBanner').style.display = 'none';
  if(_pendingConfigConfirmResolve){
    const r = _pendingConfigConfirmResolve;
    _pendingConfigConfirmResolve = null;
    r(result);
  }
}

function _cancelPendingConfigConfirm(){
  if(_pendingConfigConfirmResolve) _resolveConfigConfirm(false);
}

// goStep()/state.step (ancien assistant par étapes .step/.panel) retirés le
// 08/08/2026 avec la refonte sidebar : plus aucun élément .step/.panel dans
// le DOM depuis la migration hub/popups déjà ancienne, ces fonctions ne
// pilotaient plus rien de visible (confirmé par investigation avant
// suppression). Seul effet réel qui survivait via des appels internes
// goStep(3,...) — réappliquer les filtres bande/mode du concours quand le
// panneau FILTRES est affiché — est repris directement par les appelants
// (voir applyUsageMode(), plus bas) via _currentOpenCat() === 'filters'.

const LOCATOR_RE = /^[A-R]{2}[0-9]{2}([A-X]{2})?$/;
function isValidLocator(loc){ return LOCATOR_RE.test((loc||'').toUpperCase().trim()); }

function updateLocatorHint() {
  const loc = document.getElementById('locator').value.toUpperCase().trim();
  const hint = document.getElementById('locatorHint');
  const ok = document.getElementById('locHintOk');
  const err = document.getElementById('locHintErr');
  const val = document.getElementById('locHintVal');
  if(loc.length !== 6) {
    // Saisie en cours (< 6) ou champ vide : on ne juge pas une entrée incomplète.
    hint.style.display = 'none';
    hint.classList.remove('error');
    return;
  }
  if(isValidLocator(loc)) {
    val.textContent = loc;
    ok.style.display = '';
    err.style.display = 'none';
    hint.classList.remove('error');
  } else {
    ok.style.display = 'none';
    err.style.display = '';
    hint.classList.add('error');
  }
  hint.style.display = 'block';
}

// ─── SÉLECTEUR DE LOCATOR SUR CARTE ──────────────────────────────────────────
// Leaflet + tuiles OpenStreetMap chargés À LA DEMANDE (première ouverture) : le
// reste de la page reste utilisable hors ligne. Le calcul lat/lon → grille
// Maidenhead se fait en local (aucune API tierce nécessaire pour la conversion).
let _mapLoc = { map:null, marker:null, loc:'', lat:null, lon:null, tileErrorShown:false };

function latLonToLocator(lat, lon){
  lon = Math.max(-179.9999, Math.min(179.9999, lon)) + 180;
  lat = Math.max(-89.9999, Math.min(89.9999, lat)) + 90;
  const U = 'ABCDEFGHIJKLMNOPQRSTUVWX';
  return U[Math.floor(lon/20)] + U[Math.floor(lat/10)]
       + Math.floor((lon%20)/2) + Math.floor(lat%10)
       + U[Math.floor((lon%2)*12)] + U[Math.floor((lat%1)*24)];
}

function locatorToLatLon(loc){
  loc = (loc||'').toUpperCase().trim();
  if(!LOCATOR_RE.test(loc)) return null;
  let lon = (loc.charCodeAt(0)-65)*20 - 180 + parseInt(loc[2])*2;
  let lat = (loc.charCodeAt(1)-65)*10 - 90  + parseInt(loc[3]);
  if(loc.length >= 6){
    lon += (loc.charCodeAt(4)-65)*(2/24) + 1/24;   // centre du sous-carre
    lat += (loc.charCodeAt(5)-65)*(1/24) + 0.5/24;
  } else {
    // CENTRE DU CARRE : +1 deg de longitude, +0,5 deg de latitude.
    // On completait par 'MM' avant de derouler le calcul du sous-carre, ce
    // qui donnait +1,0417 et +0,5208 : le point tombait 3,8 km au NORD-EST
    // du centre, systematiquement. 'M' est la 13e lettre, or le milieu des
    // 24 lettres n'en est aucune (il est entre 'L' et 'M') : aucun
    // complement par lettres ne peut donner le centre, il faut le calculer.
    lon += 1.0;
    lat += 0.5;
  }
  return { lat, lon };
}

function _loadLeaflet(){
  return new Promise((resolve, reject)=>{
    if(window.L){ resolve(); return; }
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css';
    document.head.appendChild(css);
    const js = document.createElement('script');
    js.src = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js';
    js.onload = ()=>resolve();
    js.onerror = ()=>reject(new Error('Leaflet indisponible (connexion Internet requise)'));
    document.head.appendChild(js);
  });
}

async function openLocatorMap(){
  const ov = document.getElementById('mapLocOverlay');
  ov.style.display = 'block';
  document.getElementById('mapLocTileError').style.display = 'none';
  _mapLoc.tileErrorShown = false;
  try{ await _loadLeaflet(); }
  catch(e){ ov.style.display='none'; _configToast(Tf('Carte indisponible : {err}.\nLa sélection sur carte nécessite une connexion Internet ; sinon, saisis le locator à la main.', {err: e.message})); return; }

  let start = [46.6, 2.5], zoom = 5;   // défaut : centre de la France
  const cll = locatorToLatLon(document.getElementById('locator').value);
  if(cll){ start = [cll.lat, cll.lon]; zoom = 10; }

  if(!_mapLoc.map){
    _mapLoc.map = L.map('mapLocMap').setView(start, zoom);
    const tiles = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      { maxZoom:19, attribution:'© OpenStreetMap' }).addTo(_mapLoc.map);
    // Correctif M9 : _loadLeaflet() ne gère que l'échec de chargement du
    // script Leaflet lui-même (hôte cdnjs) — un blocage réseau spécifique aux
    // TUILES (hôte openstreetmap.org, souvent bloqué séparément par un
    // pare-feu) laissait la carte grise sans aucun message. Une seule bannière
    // même si des dizaines de tuiles échouent (pas de spam).
    tiles.on('tileerror', () => {
      if(_mapLoc.tileErrorShown) return;
      _mapLoc.tileErrorShown = true;
      document.getElementById('mapLocTileError').style.display = 'block';
    });
    _mapLoc.map.on('click', e => _mapLocSet(e.latlng.lat, e.latlng.lng, false));
  } else {
    _mapLoc.map.setView(start, zoom);
  }
  // Le conteneur vient d'être rendu visible : Leaflet doit recalculer sa taille.
  setTimeout(()=>{ if(_mapLoc.map) _mapLoc.map.invalidateSize(); }, 120);
  if(cll) _mapLocSet(cll.lat, cll.lon, false);
}

function _mapLocSet(lat, lon, pan){
  _mapLoc.lat = lat; _mapLoc.lon = lon;
  _mapLoc.loc = latLonToLocator(lat, lon);
  document.getElementById('mapLocValue').textContent = _mapLoc.loc;
  const btn = document.getElementById('mapLocUseBtn');
  btn.disabled = false; btn.style.opacity = '1';
  // circleMarker : pas d'image d'icône à charger (robuste hors bundler).
  if(!_mapLoc.marker){
    _mapLoc.marker = L.circleMarker([lat,lon], {radius:8, color:'#00FF88',
      fillColor:'#00FF88', fillOpacity:.6, weight:2}).addTo(_mapLoc.map);
  } else {
    _mapLoc.marker.setLatLng([lat,lon]);
  }
  _mapLoc.marker.bindTooltip(_mapLoc.loc, {permanent:true, direction:'top'}).openTooltip();
  if(pan) _mapLoc.map.panTo([lat,lon]);
}

// Distance (km) + azimut (°) entre deux points — mêmes formules que
// logx_logbook.js (bearing/cardinalDir), dupliquées ici car cette page n'a
// pas de module JS partagé.
function _haversineKm(lat1, lon1, lat2, lon2){
  const R = 6371, toRad = d => d*Math.PI/180;
  const dLat = toRad(lat2-lat1), dLon = toRad(lon2-lon1);
  const a = Math.sin(dLat/2)**2 + Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dLon/2)**2;
  return Math.round(R * 2*Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
}
function _bearingDeg(lat1, lon1, lat2, lon2){
  const φ1=lat1*Math.PI/180, φ2=lat2*Math.PI/180, Δλ=(lon2-lon1)*Math.PI/180;
  const y=Math.sin(Δλ)*Math.cos(φ2);
  const x=Math.cos(φ1)*Math.sin(φ2)-Math.sin(φ1)*Math.cos(φ2)*Math.cos(Δλ);
  return Math.round((Math.atan2(y,x)*180/Math.PI+360)%360);
}
function _cardinalDir(deg){
  const dirs=["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSO","SO","OSO","O","ONO","NO","NNO"];
  return dirs[Math.round(deg/22.5)%16];
}

// Compare le point de référence (le point cliqué sur la carte, ou à défaut le
// locator déjà saisi dans le formulaire) à un locator distant tapé à la main —
// utile pour vérifier une direction/distance sans avoir à cliquer les deux points.
function mapLocCompare(){
  const resEl = document.getElementById('mapLocCompareResult');
  const raw = document.getElementById('mapLocTarget').value.trim();
  const target = locatorToLatLon(raw);
  if(!target){ resEl.textContent = raw ? '⚠ locator invalide' : ''; resEl.style.color = 'var(--red)'; return; }

  let ref = (_mapLoc.lat != null) ? { lat:_mapLoc.lat, lon:_mapLoc.lon }
                                   : locatorToLatLon(document.getElementById('locator').value);
  if(!ref){ resEl.textContent = '⚠ clique d\'abord un point (ou renseigne ton locator)'; resEl.style.color='var(--red)'; return; }

  const km = _haversineKm(ref.lat, ref.lon, target.lat, target.lon);
  const az = _bearingDeg(ref.lat, ref.lon, target.lat, target.lon);
  resEl.style.color = 'var(--accent2)';
  resEl.textContent = `${km} km · ${az}° (${_cardinalDir(az)})`;

  if(_mapLoc.targetMarker) _mapLoc.map.removeLayer(_mapLoc.targetMarker);
  if(_mapLoc.targetLine) _mapLoc.map.removeLayer(_mapLoc.targetLine);
  // Constat de la passe de vérification (09/08/2026) : '#E8964A' était la
  // valeur --accent2 codée en dur (mode NUIT uniquement) -- cassait le
  // contraste en mode jour (--accent2 vaut #8B4F1F). 'var(--accent2)' passé
  // en chaîne fonctionne tel quel avec le rendu SVG de Leaflet (attribut de
  // présentation stroke/fill, résolu via la cascade CSS comme n'importe
  // quelle autre valeur var() sur un élément du DOM) -- même thème que le
  // texte du résultat juste au-dessus (ligne 6244), qui l'utilisait déjà.
  _mapLoc.targetMarker = L.circleMarker([target.lat,target.lon], {radius:7, color:'var(--accent2)',
    fillColor:'var(--accent2)', fillOpacity:.6, weight:2}).addTo(_mapLoc.map)
    .bindTooltip(raw.toUpperCase(), {permanent:true, direction:'top'}).openTooltip();
  _mapLoc.targetLine = L.polyline([[ref.lat,ref.lon],[target.lat,target.lon]],
    {color:'var(--accent2)', weight:2, dashArray:'6,6', opacity:.8}).addTo(_mapLoc.map);
  _mapLoc.map.fitBounds(L.latLngBounds([[ref.lat,ref.lon],[target.lat,target.lon]]).pad(0.3));
}

function mapLocUse(){
  if(!_mapLoc.loc) return;
  document.getElementById('locator').value = _mapLoc.loc;
  updateLocatorHint();
  _reverseGeocodeCity(_mapLoc.lat, _mapLoc.lon);   // remplit VILLE si vide (best-effort)
  closeLocatorMap();
}

function closeLocatorMap(){
  document.getElementById('mapLocOverlay').style.display = 'none';
  // Réinitialise l'outil de comparaison pour la prochaine ouverture : sinon la
  // ligne/le marqueur d'un précédent calcul resteraient affichés à tort.
  if(_mapLoc.targetMarker){ _mapLoc.map.removeLayer(_mapLoc.targetMarker); _mapLoc.targetMarker = null; }
  if(_mapLoc.targetLine){ _mapLoc.map.removeLayer(_mapLoc.targetLine); _mapLoc.targetLine = null; }
  document.getElementById('mapLocTarget').value = '';
  document.getElementById('mapLocCompareResult').textContent = '';
}

async function mapLocSearchGo(){
  const q = document.getElementById('mapLocSearch').value.trim();
  if(!q || !_mapLoc.map) return;
  try{
    const r = await fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&q=' + encodeURIComponent(q),
      { headers:{ 'Accept':'application/json' } });
    const d = await r.json();
    if(d && d[0]){
      const lat = parseFloat(d[0].lat), lon = parseFloat(d[0].lon);
      _mapLoc.map.setView([lat,lon], 12);
      _mapLocSet(lat, lon, false);
    } else { _configToast(T('Lieu introuvable.')); }
  }catch(e){ _configToast(T('Recherche indisponible (connexion Internet requise).')); }
}

function mapLocGeoloc(){
  if(!navigator.geolocation){ _configToast(T('Géolocalisation non disponible sur cet appareil.')); return; }
  navigator.geolocation.getCurrentPosition(p=>{
    const lat = p.coords.latitude, lon = p.coords.longitude;
    if(_mapLoc.map) _mapLoc.map.setView([lat,lon], 13);
    _mapLocSet(lat, lon, false);
  }, ()=>_configToast(T('Position refusée ou indisponible.')), { enableHighAccuracy:true, timeout:8000 });
}

async function _reverseGeocodeCity(lat, lon){
  const cityEl = document.getElementById('city');
  if(!cityEl || cityEl.value.trim()) return;   // ne pas écraser une ville déjà saisie
  try{
    const r = await fetch('https://nominatim.openstreetmap.org/reverse?format=json&zoom=10&lat=' + lat + '&lon=' + lon,
      { headers:{ 'Accept':'application/json' } });
    const a = (await r.json()).address || {};
    const city = a.city || a.town || a.village || a.municipality || a.county;
    if(city) cityEl.value = city;
  }catch(e){ /* géocodage inverse best-effort : silencieux */ }
}

function getActiveModes() {
  const modes = [];
  document.querySelectorAll('[data-key^="mode_"].on').forEach(el => {
    modes.push(el.textContent.trim());
  });
  return modes;
}

function getActiveBands() {
  const bands = [];
  document.querySelectorAll('[data-key^="band_"].on').forEach(el => {
    bands.push(el.textContent.trim());
  });
  return bands;
}

function getActiveFlags() {
  const flags = [];
  document.querySelectorAll('[data-key^="flag_"].on').forEach(el => {
    flags.push(el.textContent.trim());
  });
  return flags;
}

function getActiveProp() {
  const props = [];
  document.querySelectorAll('[data-key^="prop_"].on').forEach(el => {
    props.push(el.textContent.trim());
  });
  return props;
}

function getActiveSources() {
  const srcs = [];
  document.querySelectorAll('[data-key^="src_"].on').forEach(el => {
    srcs.push(el.textContent.trim());
  });
  return srcs;
}

function buildSummary() {
  const call = document.getElementById('callsign').value || '—';
  const callContest = document.getElementById('callsign_contest').value || call;
  const loc = document.getElementById('locator').value || '—';
  const city = document.getElementById('city').value || '—';
  const power = document.getElementById('power').value || '—';
  const record = _dxRecordSummaryText();
  const contest = CONTESTS.find(c=>c.id===state.contest);
  const modes = getActiveModes();
  const bands = getActiveBands();
  const flags = getActiveFlags();
  const props = getActiveProp();

  // call/callContest/loc/city/power sont normalement saisis localement, mais
  // peuvent aussi provenir d'une config PARTAGÉE restaurée (cloudsync/LAN
  // sync) depuis un autre poste du réseau ; contest.name vient potentiellement
  // du flux externe WA7BNM (mergeExternalContests()) — contenu tiers non
  // maîtrisé. escC() neutralise tout HTML/JS avant insertion en innerHTML.
  document.getElementById('summaryBox').innerHTML = `
    <div class="summary-row"><span class="summary-key">Indicatif</span><span class="summary-val accent">${escC(call)}</span></div>
    <div class="summary-row"><span class="summary-key">Contest</span><span class="summary-val accent">${escC(callContest)}</span></div>
    <div class="summary-row"><span class="summary-key">Locator</span><span class="summary-val accent2">${escC(loc)}</span></div>
    <div class="summary-row"><span class="summary-key">QTH</span><span class="summary-val">${escC(city)}</span></div>
    <div class="summary-row"><span class="summary-key">Puissance</span><span class="summary-val">${escC(power)}W</span></div>
    <div class="summary-row"><span class="summary-key">Record DX</span><span class="summary-val green">${escC(record)} km</span></div>
    <div class="summary-row"><span class="summary-key">Concours</span><span class="summary-val accent2">${contest ? escC(contest.name) : '— Non sélectionné'}</span></div>
    <div class="summary-row"><span class="summary-key">Modes actifs</span><span class="summary-val">${modes.map(escC).join(' · ') || '—'}</span></div>
    <div class="summary-row"><span class="summary-key">Bandes actives</span><span class="summary-val">${bands.map(escC).join(' · ') || '—'}</span></div>
    <div class="summary-row"><span class="summary-key">Options</span><span class="summary-val">${flags.map(escC).join(' · ') || '—'}</span></div>
    <div class="summary-row"><span class="summary-key">Propagation</span><span class="summary-val">${props.map(escC).join(' · ') || '—'}</span></div>
    ${document.getElementById('spot_prefix_filter').value ? `<div class="summary-row"><span class="summary-key">Filtre spots</span><span class="summary-val accent2">${escC(document.getElementById('spot_prefix_filter').value)}</span></div>` : ''}
  `;

  generatePrompt(call, callContest, loc, city, power, record, contest, modes, bands, flags, props);
}

function generatePrompt(call, callContest, loc, city, power, record, contest, modes, bands, flags, props) {
  const noDigital = flags.includes('NO-DIGI');
  const prompt = `Tu es un assistant radioamateur expert pour les concours.

STATION :
- Indicatif : ${call} / Contest : ${callContest}
- Locator : ${loc} (${city})
- Puissance : ${power}W | Record DX : ${record} km
- Modes autorisés : ${modes.join(', ') || 'tous'}
- Bandes actives : ${bands.join(', ') || 'toutes'}
${noDigital ? '- AUCUN MODE NUMÉRIQUE (FT8, FT4, JS8, WSPR, PSK) — phonie/CW uniquement' : ''}
${flags.length ? '- Options : ' + flags.join(', ') : ''}

CONCOURS : ${contest ? contest.name + ' (' + contest.org + ')' : 'Non sélectionné'}
${contest ? '- Bandes contest : ' + contest.bands.join(', ') + '\n- Modes contest : ' + contest.modes.join(', ') + '\n- Scoring : ' + contest.score : ''}

PROPAGATION À SURVEILLER : ${props.join(', ') || 'standard'}

RÈGLES DE PRIORITÉ :
1. Distance maximale depuis ${loc} (= points maximum)
2. Fiabilité du spotter et seuil DX exceptionnel : seuil différent PAR BANDE
   (HF = milliers de km, VHF/UHF/SHF = centaines à dizaines de km — la
   propagation n'a rien à voir), appliqué automatiquement par bande du spot
3. Multiplicateurs manquants (zones, depts, locators, DXCC)

FORMAT DE RECOMMANDATION :
📻 [Indicatif] | [Locator] | [Bande] MHz [Mode]
📏 Distance : [X] km = 🏆 [X] pts | 🧭 Cap : [X]° [Cardinal]
👁️ Spoté par [Indicatif] à [X] km | ✅ [Fiabilité]
🎯 Priorité : [NIVEAU] | 🕐 il y a [X] min

Ne jamais recommander de modes numériques si NO-DIGI est actif.
Analyser les données terrain fournies et donner les 5 meilleurs contacts à faire maintenant.`;

  document.getElementById('generatedPrompt').value = prompt;
}

function copyPrompt() {
  const ta = document.getElementById('generatedPrompt');
  ta.select();
  document.execCommand('copy');
  _configToast(T('Prompt copié dans le presse-papiers !'));
}

// ─── FOURNISSEUR IA ──────────────────────────────────────────────────────────
const AI_MODELS = {
  anthropic: [
    {value:'claude-sonnet-4-6',        label:'Claude Sonnet 4.6 (recommandé)'},
    {value:'claude-opus-4-8',          label:'Claude Opus 4.8 (puissant)'},
    {value:'claude-haiku-4-5-20251001',label:'Claude Haiku 4.5 (rapide)'},
  ],
  openai: [
    {value:'gpt-4o',      label:'GPT-4o (recommandé)'},
    {value:'gpt-4o-mini', label:'GPT-4o mini (rapide/économique)'},
    {value:'o1-mini',     label:'o1-mini (raisonnement)'},
  ],
  gemini: [
    {value:'gemini-2.0-flash',  label:'Gemini 2.0 Flash (recommandé)'},
    {value:'gemini-2.5-pro',    label:'Gemini 2.5 Pro (puissant)'},
    {value:'gemini-1.5-flash',  label:'Gemini 1.5 Flash (rapide)'},
  ],
  // Mistral AI, xAI/Grok et DeepSeek : noms de modèles et endpoints vérifiés
  // sur la documentation officielle de chacun (jamais devinés) — cf.
  // OPENAI_COMPATIBLE_ENDPOINTS dans logx_utils.py côté serveur.
  mistral: [
    {value:'mistral-large-latest', label:'Mistral Large (recommandé)'},
    {value:'mistral-small-latest', label:'Mistral Small (rapide/économique)'},
  ],
  xai: [
    {value:'grok-4.5',      label:'Grok 4.5 (recommandé)'},
    {value:'grok-4.3',      label:'Grok 4.3 (contexte long, 1M tokens)'},
    {value:'grok-build-0.1',label:'Grok Build 0.1 (économique)'},
  ],
  deepseek: [
    {value:'deepseek-v4-flash', label:'DeepSeek V4 Flash (recommandé/rapide)'},
    {value:'deepseek-v4-pro',   label:'DeepSeek V4 Pro (puissant)'},
  ],
};
const AI_PLACEHOLDERS = {
  anthropic: 'sk-ant-api03-...',
  openai:    'sk-...',
  gemini:    'AIza...',
  mistral:   'Clé API Mistral...',
  xai:       'xai-...',
  deepseek:  'sk-...',
};

function getSelectedProvider() {
  return document.querySelector('input[name="api_provider"]:checked')?.value || 'anthropic';
}

function onProviderChange() {
  const p = getSelectedProvider();
  // Surligner la carte du fournisseur sélectionné (appelée aussi bien au
  // clic utilisateur qu'à la restauration de config, donc les deux cas
  // reflètent toujours le bon fournisseur visuellement).
  document.querySelectorAll('.ai-provider-card').forEach(card => {
    card.classList.toggle('selected', card.dataset.provider === p);
  });
  // Sauvegarder la clé courante avant de changer
  const prevKey = document.getElementById('api_key').value;
  // Mettre à jour le select modèle
  const sel = document.getElementById('ai_model');
  sel.innerHTML = AI_MODELS[p].map(m => `<option value="${m.value}">${m.label}</option>`).join('');
  // Mettre à jour le placeholder
  document.getElementById('api_key').placeholder = AI_PLACEHOLDERS[p];
  // Charger la clé du nouveau fournisseur
  const savedKey = localStorage.getItem(`logx_apikey_${p}`) || '';
  document.getElementById('api_key').value = savedKey;
}

// Le test ouvre une session avec le boîtier et lit la VERSION de son
// micrologiciel : c'est la seule preuve qu'un WinKeyer est bien au bout du
// câble. Un adaptateur USB sans rien derrière répondrait « port ouvert » sans
// jamais manipuler, et les macros partiraient dans le vide en plein concours.
async function testSo2r(){
  const out = document.getElementById('so2rTestResult');
  const port = document.getElementById('so2r_port')?.value.trim();
  if(!port){ if(out){ out.style.color='var(--yellow)'; out.textContent='⚠ Renseigne le port du boîtier'; } return; }
  if(out){ out.style.color='var(--muted)'; out.textContent='⏳ envoi de TX1…'; }
  try{
    const res = await fetch('/so2r/test', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({port})}).then(r=>r.json());
    if(out){ out.style.color = res.ok ? 'var(--green)' : 'var(--red)';
             out.textContent = res.ok ? '✅ ' + (res.note || 'boîtier joignable') : '❌ ' + (res.error||'échec'); }
  }catch(e){ if(out){ out.style.color='var(--red)'; out.textContent='❌ '+e.message; } }
}

async function testWinKeyer(){
  const out = document.getElementById('winkeyerTestResult');
  const port = document.getElementById('winkeyer_port')?.value.trim();
  if(!port){ if(out){ out.style.color = 'var(--yellow)'; out.textContent = '⚠ Renseigne le port série d\'abord'; } return; }
  if(out){ out.style.color = 'var(--muted)'; out.textContent = '⏳ ouverture…'; }
  try{
    const res = await fetch('/winkeyer/test', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({port, wpm: document.getElementById('winkeyer_wpm')?.value})}).then(r=>r.json());
    if(out){
      out.style.color = res.ok ? 'var(--green)' : 'var(--red)';
      out.textContent = res.ok ? '✅ ' + (res.version_texte || 'WinKeyer détecté')
                               : '❌ ' + (res.error || 'échec');
    }
  }catch(e){ if(out){ out.style.color = 'var(--red)'; out.textContent = '❌ ' + e.message; } }
}

// ─── TRANSVERTERS ────────────────────────────────────────────────────────────
// Bandes FI : celles qu'une radio du commerce couvre réellement. Bandes RF :
// les clés SONT les fréquences nominales des montages (un 144 → 1296 a son
// oscillateur à 1152 MHz), et c'est de là que le serveur déduit le décalage —
// pas des bords d'allocation, qui donneraient 1240 et un log faux de 56 MHz.
const TVTR_FI = ['50', '70', '144', '432'];
const TVTR_RF = ['1296', '2320', '3400', '5760', '10368', '24048', '47088'];
let transverterRows = [];

function renderTransverters(){
  const box = document.getElementById('transverterList');
  if(!box) return;
  if(!transverterRows.length){
    box.innerHTML = '<div style="font-family:var(--font-mono);font-size:12px;color:var(--muted);padding:6px 0">'
                  + 'Aucun transverter — la fréquence de la radio est utilisée telle quelle.</div>';
  } else {
    box.innerHTML = transverterRows.map((t, i) => `
      <div class="form-row" style="align-items:flex-end;gap:10px;margin-bottom:8px">
        <div class="form-group" style="max-width:110px">
          <label>ACTIF</label>
          <select data-tvtr="enabled" data-i="${i}">
            <option value="1"${t.enabled !== false ? ' selected' : ''}>Oui</option>
            <option value="0"${t.enabled === false ? ' selected' : ''}>Non</option>
          </select>
        </div>
        <div class="form-group" style="max-width:130px">
          <label>FI (radio)</label>
          <select data-tvtr="if" data-i="${i}">
            ${TVTR_FI.map(b => `<option value="${b}"${String(t.if) === b ? ' selected' : ''}>${b} MHz</option>`).join('')}
          </select>
        </div>
        <div class="form-group" style="max-width:150px">
          <label>BANDE RÉELLE</label>
          <select data-tvtr="rf" data-i="${i}">
            ${TVTR_RF.map(b => `<option value="${b}"${String(t.rf) === b ? ' selected' : ''}>${b} MHz</option>`).join('')}
          </select>
        </div>
        <div class="form-group" style="max-width:170px">
          <label>OSCILLATEUR (MHz)</label>
          <input type="number" step="0.001" data-tvtr="lo_mhz" data-i="${i}"
                 value="${t.lo_mhz != null ? t.lo_mhz : ''}"
                 placeholder="auto (${(Number(t.rf) || 0) - (Number(t.if) || 0)})">
        </div>
        <div class="form-group" style="max-width:60px">
          <label>&nbsp;</label>
          <button type="button" class="btn btn-secondary" onclick="removeTransverter(${i})" title="Supprimer ce transverteur"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg></button>
        </div>
      </div>`).join('');
    box.querySelectorAll('[data-tvtr]').forEach(el => {
      el.addEventListener('change', () => { readTransverters(); checkTransverters(); });
    });
  }
  checkTransverters();
}

// Lit les champs ET met à jour l'état — appelée aussi par saveConfig(), qui
// doit partir des valeurs actuellement à l'écran (même piège que cloudsyncNow()).
function readTransverters(){
  const box = document.getElementById('transverterList');
  if(box){
    box.querySelectorAll('[data-tvtr]').forEach(el => {
      const i = parseInt(el.dataset.i, 10);
      if(!transverterRows[i]) return;
      const champ = el.dataset.tvtr;
      if(champ === 'enabled')      transverterRows[i].enabled = el.value === '1';
      else if(champ === 'lo_mhz')  transverterRows[i].lo_mhz = el.value === '' ? null : parseFloat(el.value);
      else                         transverterRows[i][champ] = el.value;
    });
  }
  return transverterRows.map(t => ({
    if: String(t.if), rf: String(t.rf),
    enabled: t.enabled !== false,
    ...(t.lo_mhz != null && !isNaN(t.lo_mhz) ? {lo_mhz: t.lo_mhz} : {})
  }));
}

// Même règle que erreurs_config() côté serveur, affichée AVANT la sauvegarde :
// le serveur refuse de toute façon, autant le dire tout de suite.
function checkTransverters(){
  const warn = document.getElementById('transverterWarn');
  if(!warn) return;
  const vus = {};
  let msg = '';
  transverterRows.forEach(t => {
    if(t.enabled === false) return;
    if(vus[t.if]) msg = '⚠ Deux transverters actifs sur la FI ' + t.if
                      + ' MHz : la fréquence lue serait ambiguë, désactivez-en un.';
    vus[t.if] = true;
    if(Number(t.rf) <= Number(t.if)) msg = '⚠ La bande réelle doit être au-dessus de la FI.';
  });
  warn.textContent = msg;
}

// ── AUTO-LANCEMENT DE LOGICIELS TIERS (#17) — même schéma que les
// transverters ci-dessus (lignes vivant dans le DOM, lues à la sauvegarde).
let autostartRows = [];

function renderAutostart(){
  const box = document.getElementById('autostartList');
  if(!box) return;
  if(!autostartRows.length){
    box.innerHTML = '<div style="font-family:var(--font-mono);font-size:12px;color:var(--muted);padding:6px 0">'
                  + 'Aucun programme configuré.</div>';
    return;
  }
  box.innerHTML = autostartRows.map((p, i) => `
    <div class="form-row" style="align-items:flex-end;gap:10px;margin-bottom:8px">
      <div class="form-group" style="max-width:100px">
        <label>ACTIF</label>
        <select data-asr="enabled" data-i="${i}">
          <option value="1"${p.enabled !== false ? ' selected' : ''}>Oui</option>
          <option value="0"${p.enabled === false ? ' selected' : ''}>Non</option>
        </select>
      </div>
      <div class="form-group" style="max-width:150px">
        <label>NOM</label>
        <input type="text" data-asr="name" data-i="${i}" value="${escC(p.name)}" placeholder="WSJT-X">
      </div>
      <div class="form-group" style="flex:2;min-width:220px">
        <label>CHEMIN DE L'EXÉCUTABLE</label>
        <input type="text" data-asr="path" data-i="${i}" value="${escC(p.path)}"
               placeholder="C:\\Program Files\\WSJT-X\\wsjtx.exe">
      </div>
      <div class="form-group" style="flex:1;min-width:140px">
        <label>ARGUMENTS <span style="font-size:11px;color:var(--muted)">— optionnel</span></label>
        <input type="text" data-asr="args" data-i="${i}" value="${escC(p.args)}">
      </div>
      <div class="form-group" style="max-width:60px">
        <label>&nbsp;</label>
        <button type="button" class="btn btn-secondary" title="Lancer ce programme maintenant (sans attendre le prochain démarrage de LogX)" onclick="testAutostartRow(${i}, this)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 3.5v11l9-5.5-9-5.5z"/></svg></button>
      </div>
      <div class="form-group" style="max-width:60px">
        <label>&nbsp;</label>
        <button type="button" class="btn btn-secondary" onclick="removeAutostartRow(${i})" title="Supprimer cette ligne d'auto-lancement"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg></button>
      </div>
      <div id="autostartStatus${i}" style="font-family:var(--font-mono);font-size:12px;flex-basis:100%"></div>
    </div>`).join('');
  box.querySelectorAll('[data-asr]').forEach(el => {
    el.addEventListener('change', readAutostart);
  });
}

// Bouton ▶ par ligne : lance CE programme immédiatement (même fonction que
// le démarrage auto du serveur, voir /autostart/launch), pour vérifier le
// chemin/les arguments sans attendre de relancer LogX en entier.
async function testAutostartRow(i, btn){
  readAutostart();   // synchronise autostartRows avec les champs édités
  const entree = autostartRows[i];
  const st = document.getElementById('autostartStatus' + i);
  if(!entree || !entree.path){
    if(st){ st.textContent = '⚠️ Chemin vide'; st.style.color = 'var(--yellow)'; }
    return;
  }
  if(st){ st.textContent = '⏳ Lancement…'; st.style.color = 'var(--muted)'; }
  try{
    const res = await fetch('/autostart/launch', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(entree),
    });
    const r = await res.json();
    if(!st) return;
    if(!r.ok){ st.textContent = `❌ ${r.error || 'échec'}`; st.style.color = 'var(--red)'; return; }
    st.textContent = r.skipped ? 'ℹ️ Déjà lancé (ignoré)' : '✅ Lancé';
    st.style.color = r.skipped ? 'var(--muted)' : 'var(--green)';
  }catch(e){
    if(st){ st.textContent = '❌ Serveur injoignable'; st.style.color = 'var(--red)'; }
  }
}

function addAutostartRow(){
  autostartRows.push({name:'', path:'', args:'', enabled:true});
  renderAutostart();
}

function removeAutostartRow(i){
  autostartRows.splice(i, 1);
  renderAutostart();
}

// Lit les champs ET met à jour l'état — appelée aussi par saveConfig().
function readAutostart(){
  const box = document.getElementById('autostartList');
  if(box){
    box.querySelectorAll('[data-asr]').forEach(el => {
      const i = parseInt(el.dataset.i, 10);
      if(!autostartRows[i]) return;
      const champ = el.dataset.asr;
      autostartRows[i][champ] = champ === 'enabled' ? el.value === '1' : el.value;
    });
  }
  return autostartRows
    .filter(p => p.path && p.path.trim())
    .map(p => ({name: p.name || '', path: p.path.trim(), args: p.args || '',
               enabled: p.enabled !== false}));
}

function addTransverter(){
  transverterRows.push({if: '144', rf: '1296', enabled: true, lo_mhz: null});
  renderTransverters();
}

function removeTransverter(i){
  readTransverters();
  transverterRows.splice(i, 1);
  renderTransverters();
}

// ═══ PARC D'ANTENNES, DE ROTORS ET D'AMPLIS ══════════════════════════════════
// Une station peut avoir PLUSIEURS de chaque — l'exemple qui a motivé cet
// écran : trois pylônes, trois antennes, trois rotors. Chaque antenne désigne
// SON rotor et SON ampli ; un clic sur un spot ne fait alors tourner que le
// pylône de la bande courante, les autres restent où ils sont.
//
// Le miroir serveur (logx_station.py) fait foi : c'est lui qui normalise,
// attribue les identifiants et reprend les anciennes configurations. Cet écran
// ne fait que saisir.
const PARC_BANDES = ['1.8','3.5','7','10.1','14','18','21','24','28','50','70',
                     '144','432','1296','2320','3400','5760','10368','24048','47088'];
const PARC_TYPES = ['', 'directive', 'omni', 'filaire', 'verticale', 'parabole'];
const PARC_MARQUES_AMPLI = ['', 'elecraft', 'icom', 'spe'];

// ── CATALOGUE ROTORS (miroir de logx_rotor.ROTOR_BRANDS) ─────────────────────
// Marque -> protocole conseillé + modèles (el = azimut/élévation, satellite).
// Statique, aucun numéro Hamlib codé en dur (ils changent de version en
// version) : `el` décide l'affichage de l'élévation, `proto` guide le
// branchement (GS-232 natif, ou rotctld universel).
const ROTOR_CATALOG = [
  {brand:'Yaesu', proto:'gs232', models:[
    {model:'G-450 / G-550', el:false},{model:'G-800DXA / G-1000DXC', el:false},
    {model:'G-2800DXC', el:false},{model:'G-5500 (Az + El)', el:true},
    {model:'GS-232A / GS-232B (boîtier)', el:true}]},
  {brand:'Kenpro', proto:'gs232', models:[
    {model:'KR-2000 / KR-2400', el:false},{model:'KR-5400 / KR-5600 (Az + El)', el:true}]},
  {brand:'Hy-Gain', proto:'rotctld', models:[
    {model:'Ham-IV', el:false},{model:'T2X Tailtwister', el:false},{model:'DCU-1 (contrôleur)', el:false}]},
  {brand:'SPID', proto:'rotctld', models:[
    {model:'BIG-RAS/HR', el:false},{model:'ROT1PROG', el:false},{model:'ROT2PROG (Az + El)', el:true},{model:'RAU / RAK', el:false}]},
  {brand:'Pro.Sis.Tel', proto:'rotctld', models:[
    {model:'PST-2051D', el:false},{model:'PST-61', el:false},{model:'PST-641', el:false},{model:'Combo Az/El (Big/Small)', el:true}]},
  {brand:'M2 Antenna Systems', proto:'rotctld', models:[
    {model:'RC2800', el:false},{model:'RC2800PX (Az + El)', el:true}]},
  {brand:'Alfa Radio', proto:'rotctld', models:[
    {model:'AlfaSpid RAK', el:false},{model:'AlfaSpid RAS (Az + El)', el:true}]},
  {brand:'Autre / générique', proto:'rotctld', models:[
    {model:'Serveur GS-232 en TCP (PstRotator/microHam)', el:true},{model:'via Hamlib rotctld', el:false}]},
];
function _rotorBrand(name){ return ROTOR_CATALOG.find(b => b.brand === name); }
function rotorModelEl(brand, model){
  const b = _rotorBrand(brand); if(!b) return false;
  const m = b.models.find(x => x.model === model); return !!(m && m.el);
}

// ── Rotor UNIQUE (popup 7) : marque -> modèles + protocole ───────────────────
function fillRotorBrandSelect(){
  const sel = document.getElementById('rotor_brand'); if(!sel) return;
  sel.innerHTML = '<option value="">— choisir —</option>'
    + ROTOR_CATALOG.map(b => `<option value="${b.brand}">${b.brand}</option>`).join('');
}
function fillRotorModelSelect(brand){
  const sel = document.getElementById('rotor_model'); if(!sel) return;
  const b = _rotorBrand(brand);
  sel.innerHTML = '<option value="">—</option>'
    + ((b && b.models) || []).map(m => `<option value="${m.model}">${m.model}${m.el ? ' · Az/El' : ''}</option>`).join('');
}
function onRotorBrandChange(){
  const brand = document.getElementById('rotor_brand').value;
  fillRotorModelSelect(brand);
  const b = _rotorBrand(brand);
  if(b){ const p = document.getElementById('rotor_proto'); if(p) p.value = b.proto; }
  onRotorModelChange();
  onRotorProtoChange();
}
function onRotorModelChange(){
  const brand = document.getElementById('rotor_brand').value;
  const model = document.getElementById('rotor_model').value;
  const note = document.getElementById('rotor_model_note');
  if(note) note.textContent = rotorModelEl(brand, model) ? 'Boîtier azimut + élévation (satellite/EME)' : '';
}
function onRotorProtoChange(){
  const p = (document.getElementById('rotor_proto') || {}).value;
  const pn = document.getElementById('rotor_proto_note');
  const hn = document.getElementById('rotor_host_note');
  const port = document.getElementById('rotor_port');
  if(p === 'gs232'){
    if(pn) pn.textContent = 'LogX parle au boîtier/serveur directement — pas besoin de rotctld';
    if(hn) hn.textContent = 'IP du boîtier GS-232, ou du serveur PstRotator/microHam';
    if(port && !port.value) port.placeholder = '4001';
  } else {
    if(pn) pn.textContent = 'Lance rotctld sur le PC relié au boîtier (rotctl -l pour le n°)';
    if(hn) hn.textContent = 'IP du PC où tourne rotctld';
    if(port) port.placeholder = '4533';
  }
}

// ── RELAIS (panneau Station Control, popup 16) : commutation d'antennes/accessoires ──
function updateRelayFieldsVisibility(){
  const kindEl = document.getElementById('relay_kind');
  if(!kindEl) return;
  const isWeb = kindEl.value === 'webswitch';
  document.getElementById('relayPortField').style.display = isWeb ? 'none' : '';
  document.getElementById('relayBaudField').style.display = isWeb ? 'none' : '';
  document.getElementById('relayHostField').style.display = isWeb ? '' : 'none';
  document.getElementById('relayUserField').style.display = isWeb ? '' : 'none';
  document.getElementById('relayPasswordField').style.display = isWeb ? '' : 'none';
}

async function refreshRelayPorts(){
  const sel = document.getElementById('relay_port');
  // Même repli que refreshAmpPorts : le port peut être perdu si la liste
  // arrive du serveur après la restauration de la config.
  const prev = sel.value || (window._cfgRestauree || {}).relay_port || '';
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

async function testRelayConnection(){
  const result = document.getElementById('relayTestResult');
  result.textContent = '⏳ Test en cours...';
  result.style.color = 'var(--muted)';
  try{
    const res = await fetch('/relay/test', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const r = await res.json();
    if (r.ok){
      result.textContent = '✅ Carte relais jointe';
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

async function testPgxlConnection(){
  const result = document.getElementById('pgxlTestResult');
  result.textContent = '⏳ Test en cours...';
  result.style.color = 'var(--muted)';
  const payload = {
    host: document.getElementById('pgxl_host').value.trim(),
    port: parseInt(document.getElementById('pgxl_port').value, 10) || 9008,
    timeout: parseFloat(document.getElementById('pgxl_timeout').value) || 3.0,
  };
  if (!payload.host){
    result.textContent = '⚠️ Adresse IP/hôte manquante';
    result.style.color = 'var(--yellow)';
    return;
  }
  try{
    const res = await fetch('/pgxl/test', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)});
    const r = await res.json();
    if (r.ok){
      result.textContent = `✅ PowerGenius XL joint (${payload.host}:${payload.port})`;
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

async function testTelemetryConnection(){
  const result = document.getElementById('telemetryTestResult');
  const endpoint = document.getElementById('telemetry_endpoint').value.trim();
  if (!endpoint){
    result.textContent = '⚠️ Aucune destination renseignée — rien à tester';
    result.style.color = 'var(--yellow)';
    return;
  }
  result.textContent = '⏳ Envoi en cours...';
  result.style.color = 'var(--muted)';
  try{
    const res = await fetch('/telemetry/test', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({endpoint})});
    const r = await res.json();
    if (r.ok){
      result.textContent = '✅ Heartbeat envoyé';
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

// Grille de boutons manuels : état purement optimiste côté client (aucun
// endpoint de lecture d'état individuel côté serveur pour l'instant) — un
// bouton par relais, clic = bascule ON/OFF et appelle /relay/set.
function renderRelayButtons(){
  const box = document.getElementById('relayButtonsGrid');
  if(!box) return;
  const countEl = document.getElementById('relay_count');
  const count = Math.min(Math.max(parseInt((countEl || {}).value, 10) || 4, 1), 16);
  box.innerHTML = Array.from({length: count}, (_, i) => i + 1).map(n =>
    `<button type="button" class="toggle-btn" data-relaynum="${n}" onclick="toggleRelayManual(${n}, this)">RELAIS ${n}</button>`
  ).join('');
}

async function toggleRelayManual(num, btn){
  const on = !btn.classList.contains('on');
  btn.disabled = true;
  try{
    const res = await fetch('/relay/set', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({relay: num, on})});
    const r = await res.json();
    if (r.ok) btn.classList.toggle('on', on);
    // Échec : on laisse l'état visuel tel quel plutôt que de mentir sur l'état réel.
  }catch(e){
    // Serveur injoignable — idem, pas de bascule visuelle non confirmée.
  }finally{
    btn.disabled = false;
  }
}

// Table BANDE -> n° de relais (auto-pilotage) : une ligne par bande de
// PARC_BANDES (même liste que le parc d'antennes) — vide = pas de mapping.
function renderRelayBandMapRows(map){
  const box = document.getElementById('relayBandMapTable');
  if(!box) return;
  map = map || {};
  box.innerHTML = PARC_BANDES.map(b => `
    <label style="font-family:var(--font-mono);font-size:11px;border:1px solid var(--border);
      color:var(--muted);border-radius:4px;padding:3px 7px;cursor:default;display:inline-flex;
      gap:5px;align-items:center">${b}<input type="number" min="1" max="16" data-relayband="${b}"
      style="width:44px" value="${map[b] != null ? map[b] : ''}"></label>`).join('');
}

function readRelayBandMap(){
  const box = document.getElementById('relayBandMapTable');
  const map = {};
  if(box){
    box.querySelectorAll('[data-relayband]').forEach(el => {
      const v = el.value.trim();
      if(v) map[el.dataset.relayband] = parseInt(v, 10);
    });
  }
  return map;
}

// ── ANNUAIRE DE NŒUDS DX CLUSTER (sélecteur, source serveur /data/clusters) ──
// Remplit une liste groupée par région ; choisir un nœud remplit host+port. Le
// champ texte reste libre — la liste n'est qu'un raccourci.
function fillClusterPicker(){
  var sel = document.getElementById('cluster_spot_pick');
  if(!sel) return;
  fetch('/data/clusters').then(r => r.ok ? r.json() : null).then(function(d){
    if(!d || !d.nodes) return;
    var byReg = {};
    d.nodes.forEach(function(n){ (byReg[n.region] = byReg[n.region] || []).push(n); });
    // Construit en DOM (createElement) plutôt qu'en innerHTML : les libellés de
    // groupe viennent de DONNÉES serveur, pas de chrome d'interface — les poser
    // en propriété .label évite qu'un scanner i18n statique prenne un gabarit
    // « optgroup label="…" » pour une chaîne d'UI à traduire.
    sel.textContent = '';
    var ph = document.createElement('option');
    ph.value = ''; ph.textContent = '— nœud connu (ou saisis le tien ci-dessous) —';
    sel.appendChild(ph);
    Object.keys(byReg).forEach(function(reg){
      var og = document.createElement('optgroup');
      og.label = reg;
      byReg[reg].forEach(function(n){
        var o = document.createElement('option');
        o.value = n.host + '|' + n.port;
        o.textContent = n.label + ' — ' + n.host + ':' + n.port;
        og.appendChild(o);
      });
      sel.appendChild(og);
    });
    syncClusterPick();
  }).catch(function(){});
}
function onClusterPick(){
  var sel = document.getElementById('cluster_spot_pick');
  if(!sel || !sel.value) return;
  var parts = sel.value.split('|');
  document.getElementById('cluster_spot_host').value = parts[0];
  document.getElementById('cluster_spot_port').value = parts[1];
}
// Aligne la liste sur les champs (hôte perso non listé -> liste sur « — »).
function syncClusterPick(){
  var sel = document.getElementById('cluster_spot_pick');
  if(!sel) return;
  var key = (document.getElementById('cluster_spot_host') || {}).value + '|'
          + (document.getElementById('cluster_spot_port') || {}).value;
  sel.value = '';
  for(var i = 0; i < sel.options.length; i++){ if(sel.options[i].value === key){ sel.value = key; break; } }
}

// ── Postes détectés en synchro LAN directe (/log/lan/peers) ──────────────────
function refreshLanPeers(){
  var box = document.getElementById('lanPeersBox');
  if(!box) return;
  fetch('/log/lan/peers').then(r => r.ok ? r.json() : null).then(function(d){
    var peers = (d && d.peers) || [];
    if(!peers.length){ box.textContent = '— aucun poste détecté —'; return; }
    box.innerHTML = peers.map(function(p){
      var call = (p.callsign || '').replace(/[<>&]/g, '');
      var ip = (p.ip || '').replace(/[<>&]/g, '');
      return '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--green)"></span> <b style="color:var(--accent2)">' + (call || ip) + '</b> <span style="color:var(--muted)">' + ip + ':' + p.http_port + '</span>';
    }).join('<br>');
  }).catch(function(){});
}
// Rafraîchissement léger tant que la page config est ouverte (GET local, ~rien).
setInterval(function(){ try{ refreshLanPeers(); }catch(e){} }, 6000);

// ── Réglage SON + VOIX par type d'alerte (#5) ────────────────────────────────
// Les données (types, sons, prefs) viennent de logx_statusbar.js (window.rcAlert*)
// pour rester la SEULE source de vérité — la même que celle qui déclenche les
// alertes. Prefs par poste dans localStorage rc_alerts, enregistrées à chaque
// changement (comme le bouton 🔊 global).
const ALERT_SOUND_LABELS = {
  aucun: 'Aucun (silencieux)', aigu: 'Bip aigu', grave: 'Bip grave',
  double: 'Double bip', montant: 'Deux tons montants',
  carillon: 'Carillon (3 notes)', sirene: 'Sirène courte'
};
function buildAlertTypesGrid(){
  const box = document.getElementById('alertTypesGrid');
  if(!box || !window.rcAlertTypes) return;
  const volSel = document.getElementById('alertBeepVolume');
  if(volSel && window.rcAlertVolume) volSel.value = window.rcAlertVolume();
  const types = window.rcAlertTypes();
  const sounds = window.rcAlertSounds();
  const prefs = window.rcAlertPrefs();
  box.innerHTML = types.map(function(t){
    const p = prefs[t.id] || {voice:false, sound:'aigu'};
    const opts = sounds.map(function(s){
      return '<option value="'+s+'"'+(s===p.sound?' selected':'')+'>'+(ALERT_SOUND_LABELS[s]||s)+'</option>';
    }).join('');
    return '<div class="form-row" data-alert="'+t.id+'" style="align-items:center;gap:12px;margin-bottom:8px">'
      + '<div style="flex:1;font-family:var(--font-mono);font-size:13px">'+t.label+'</div>'
      + '<label style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer">'
      + '<input type="checkbox" data-alert-voice '+(p.voice?'checked':'')+' onchange="saveAlertTypes()"> voix</label>'
      + '<select data-alert-sound onchange="saveAlertTypes()" style="width:190px">'+opts+'</select>'
      + '<button type="button" class="btn btn-secondary" onclick="testAlertType(\''+t.id+'\')" title="Écouter"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 7v4h3l4 3V4L5 7H2z"/><path d="M12.5 6a4 4 0 0 1 0 6"/><path d="M14.7 4a7 7 0 0 1 0 10"/></svg></button>'
      + '</div>';
  }).join('');
}
function saveAlertTypes(){
  const box = document.getElementById('alertTypesGrid');
  if(!box) return;
  const out = {};
  box.querySelectorAll('[data-alert]').forEach(function(row){
    out[row.dataset.alert] = {
      voice: row.querySelector('[data-alert-voice]').checked,
      sound: row.querySelector('[data-alert-sound]').value
    };
  });
  try{ localStorage.setItem('rc_alerts', JSON.stringify(out)); }catch(e){}
}
function testAlertType(id){
  const row = document.querySelector('[data-alert="'+id+'"]');
  if(!row) return;
  try{ if(window.rcTone) window.rcTone(row.querySelector('[data-alert-sound]').value); }catch(e){}
  if(row.querySelector('[data-alert-voice]').checked && window.rcSpeak){
    try{ window.rcSpeak((window.rcAlertVoiceFor && window.rcAlertVoiceFor(id)) || id, true); }catch(e){}
  }
}

let antennesRows = [], rotorsRows = [], amplisRows = [];

function _pOpt(v, sel, lbl){
  return `<option value="${v}"${String(sel) === String(v) ? ' selected' : ''}>${lbl || v || '—'}</option>`;
}

function renderParcStation(){
  const box = document.getElementById('parcStation');
  if(!box) return;
  const rotOpts = ['<option value="">— aucun —</option>'].concat(
    rotorsRows.map((r, i) => `<option value="${escAttrParc(r.id || ('rotor' + (i+1)))}">`
      + `${escAttrParc(r.nom || ('Rotor ' + (i+1)))}</option>`)).join('');
  const ampOpts = ['<option value="">— aucun —</option>'].concat(
    amplisRows.map((m, i) => `<option value="${escAttrParc(m.id || ('ampli' + (i+1)))}">`
      + `${escAttrParc(m.nom || ('Ampli ' + (i+1)))}</option>`)).join('');

  let h = '<div style="font-family:var(--font-mono);font-size:12.5px;color:var(--muted);line-height:1.6;margin-bottom:12px">'
        + "Une ligne par antenne. Coche ses bandes, et dis-lui quel rotor la tourne et quel ampli la précède. "
        + "Une antenne fixe se déclare sans rotor : rien ne tournera pour elle."
        + '</div>';

  // ── Antennes ──
  h += antennesRows.map((a, i) => `
    <div style="border:1px solid var(--border);border-radius:8px;padding:10px 12px;margin-bottom:10px">
      <div class="form-row" style="align-items:flex-end;gap:10px">
        <div class="form-group" style="flex:2;min-width:150px">
          <label>ANTENNE ${i + 1}</label>
          <input type="text" data-parc="ant.nom" data-i="${i}" value="${escAttrParc(a.nom)}"
                 placeholder="Yagi 6 él. 20m">
        </div>
        <div class="form-group" style="max-width:130px">
          <label>TYPE</label>
          <select data-parc="ant.type" data-i="${i}">
            ${PARC_TYPES.map(t => _pOpt(t, a.type, t || '—')).join('')}
          </select>
        </div>
        <div class="form-group" style="max-width:150px">
          <label>ROTOR</label>
          <select data-parc="ant.rotor_id" data-i="${i}">${rotOpts}</select>
        </div>
        <div class="form-group" style="max-width:150px">
          <label>AMPLI</label>
          <select data-parc="ant.ampli_id" data-i="${i}">${ampOpts}</select>
        </div>
        <div class="form-group" style="max-width:60px">
          <label>&nbsp;</label>
          <button type="button" class="btn btn-secondary" onclick="removeAntenne(${i})" title="Supprimer cette antenne"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg></button>
        </div>
      </div>
      <div style="margin-top:6px">
        <div style="font-family:var(--font-mono);font-size:10.5px;color:var(--muted);letter-spacing:1px;margin-bottom:4px">BANDES</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          ${PARC_BANDES.map(b => `<label style="font-family:var(--font-mono);font-size:11px;
            border:1px solid ${(a.bandes||[]).includes(b) ? 'var(--green)' : 'var(--border)'};
            color:${(a.bandes||[]).includes(b) ? 'var(--green)' : 'var(--muted)'};
            border-radius:4px;padding:2px 6px;cursor:pointer;display:inline-flex;gap:3px;align-items:center">
            <input type="checkbox" data-parc="ant.bande" data-i="${i}" data-b="${b}"
              ${(a.bandes||[]).includes(b) ? 'checked' : ''} style="margin:0">${b}</label>`).join('')}
        </div>
      </div>
    </div>`).join('');
  if(!antennesRows.length){
    h += '<div style="font-family:var(--font-mono);font-size:12px;color:var(--muted);padding:4px 0 10px">'
       + 'Aucune antenne déclarée — les champs de description plus bas seront repris automatiquement.</div>';
  }
  h += `<button type="button" class="btn btn-secondary" onclick="addAntenne()">+ ANTENNE</button>`;

  // ── Rotors ──
  h += '<div style="font-family:var(--font-mono);font-size:11px;letter-spacing:2px;color:var(--muted);margin:18px 0 8px;border-top:1px solid var(--border);padding-top:12px">ROTORS</div>';
  h += rotorsRows.map((r, i) => `
    <div class="form-row" style="align-items:flex-end;gap:10px;margin-bottom:8px">
      <div class="form-group" style="max-width:80px">
        <label>ACTIF</label>
        <select data-parc="rot.enabled" data-i="${i}">
          ${_pOpt('1', r.enabled ? '1' : '0', 'Oui')}${_pOpt('0', r.enabled ? '1' : '0', 'Non')}
        </select>
      </div>
      <div class="form-group" style="flex:1;min-width:120px">
        <label>NOM</label>
        <input type="text" data-parc="rot.nom" data-i="${i}" value="${escAttrParc(r.nom)}" placeholder="Pylône 1">
      </div>
      <div class="form-group" style="flex:1;min-width:120px">
        <label>MARQUE</label>
        <select data-parc="rot.brand" data-i="${i}">
          <option value="">—</option>
          ${ROTOR_CATALOG.map(b => _pOpt(b.brand, r.brand || '', b.brand)).join('')}
        </select>
      </div>
      <div class="form-group" style="flex:1;min-width:130px">
        <label>MODÈLE</label>
        <select data-parc="rot.model" data-i="${i}">
          <option value="">—</option>
          ${((_rotorBrand(r.brand) || {}).models || []).map(m => _pOpt(m.model, r.model || '', m.model + (m.el ? ' · Az/El' : ''))).join('')}
        </select>
      </div>
      <div class="form-group" style="max-width:100px">
        <label>PROTOCOLE</label>
        <select data-parc="rot.proto" data-i="${i}">
          ${_pOpt('rotctld', r.proto || 'rotctld', 'rotctld')}${_pOpt('gs232', r.proto || 'rotctld', 'GS-232')}
        </select>
      </div>
      <div class="form-group" style="flex:1;min-width:130px">
        <label>ADRESSE</label>
        <input type="text" data-parc="rot.host" data-i="${i}" value="${escAttrParc(r.host)}" placeholder="192.168.1.20">
      </div>
      <div class="form-group" style="max-width:100px">
        <label>PORT</label>
        <input type="number" data-parc="rot.port" data-i="${i}" value="${escAttrParc(r.port || 4533)}">
      </div>
      <div class="form-group" style="max-width:110px">
        <label>DÉCALAGE °</label>
        <input type="number" step="0.1" data-parc="rot.offset_deg" data-i="${i}" value="${escAttrParc(r.offset_deg || 0)}">
      </div>
      <div class="form-group" style="max-width:60px">
        <label>&nbsp;</label>
        <button type="button" class="btn btn-secondary" onclick="removeRotor(${i})" title="Supprimer ce rotor"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg></button>
      </div>
    </div>`).join('');
  h += `<button type="button" class="btn btn-secondary" onclick="addRotor()">+ ROTOR</button>`;
  h += '<div style="font-family:var(--font-mono);font-size:11.5px;color:var(--muted);margin-top:6px">'
     + 'DÉCALAGE : à renseigner si le zéro mécanique du rotor n\'est pas au nord — sinon tout son pointage est faux du même angle.</div>';

  // ── Amplis ──
  h += '<div style="font-family:var(--font-mono);font-size:11px;letter-spacing:2px;color:var(--muted);margin:18px 0 8px;border-top:1px solid var(--border);padding-top:12px">AMPLIFICATEURS</div>';
  h += amplisRows.map((m, i) => `
    <div class="form-row" style="align-items:flex-end;gap:10px;margin-bottom:8px">
      <div class="form-group" style="max-width:80px">
        <label>ACTIF</label>
        <select data-parc="amp.enabled" data-i="${i}">
          ${_pOpt('1', m.enabled ? '1' : '0', 'Oui')}${_pOpt('0', m.enabled ? '1' : '0', 'Non')}
        </select>
      </div>
      <div class="form-group" style="flex:1;min-width:120px">
        <label>NOM</label>
        <input type="text" data-parc="amp.nom" data-i="${i}" value="${escAttrParc(m.nom)}" placeholder="SPE 2K-FA">
      </div>
      <div class="form-group" style="max-width:130px">
        <label>MARQUE</label>
        <select data-parc="amp.brand" data-i="${i}">
          ${PARC_MARQUES_AMPLI.map(b => _pOpt(b, m.brand, b || '—')).join('')}
        </select>
      </div>
      <div class="form-group" style="max-width:120px">
        <label>PORT</label>
        <input type="text" data-parc="amp.port" data-i="${i}" value="${escAttrParc(m.port)}" placeholder="COM5">
      </div>
      <div class="form-group" style="max-width:60px">
        <label>&nbsp;</label>
        <button type="button" class="btn btn-secondary" onclick="removeAmpli(${i})" title="Supprimer cet amplificateur"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg></button>
      </div>
    </div>`).join('');
  h += `<button type="button" class="btn btn-secondary" onclick="addAmpli()">+ AMPLI</button>`;

  box.innerHTML = h;
  // Les <select> de rotor/ampli sont posés APRÈS coup : leur valeur ne peut pas
  // l'être dans le HTML tant que les options n'existent pas — c'est exactement
  // le défaut qui faisait perdre la radio choisie dans la carte CAT.
  box.querySelectorAll('[data-parc="ant.rotor_id"]').forEach(el => {
    el.value = antennesRows[+el.dataset.i].rotor_id || '';
  });
  box.querySelectorAll('[data-parc="ant.ampli_id"]').forEach(el => {
    el.value = antennesRows[+el.dataset.i].ampli_id || '';
  });
  box.querySelectorAll('[data-parc]').forEach(el => {
    el.addEventListener('change', onParcChange);
  });
}

function escAttrParc(v){
  return String(v == null ? '' : v).replace(/[&<>"']/g,
    c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function onParcChange(e){
  readParcStation();
  const dp = e.target.dataset.parc;
  // Choisir la marque d'un rotor règle son protocole et vide son modèle, puis
  // re-render pour peupler la liste des modèles de cette marque.
  if(dp === 'rot.brand'){
    const i = +e.target.dataset.i;
    const b = _rotorBrand(rotorsRows[i].brand);
    if(b){ rotorsRows[i].proto = b.proto; rotorsRows[i].model = ''; }
    renderParcStation();
    return;
  }
  // Renommer un rotor doit rafraîchir les listes déroulantes des antennes.
  if(/^(rot|amp)\.(nom)$/.test(dp)) renderParcStation();
}

function readParcStation(){
  const box = document.getElementById('parcStation');
  if(!box) return;
  box.querySelectorAll('[data-parc]').forEach(el => {
    const [quoi, champ] = el.dataset.parc.split('.');
    const i = +el.dataset.i;
    const cible = quoi === 'ant' ? antennesRows[i] : quoi === 'rot' ? rotorsRows[i] : amplisRows[i];
    if(!cible) return;
    if(champ === 'bande'){
      const b = el.dataset.b;
      cible.bandes = cible.bandes || [];
      const dedans = cible.bandes.includes(b);
      if(el.checked && !dedans) cible.bandes.push(b);
      if(!el.checked && dedans) cible.bandes = cible.bandes.filter(x => x !== b);
    } else if(champ === 'enabled'){
      cible.enabled = el.value === '1';
    } else if(champ === 'port' && quoi === 'rot'){
      cible.port = parseInt(el.value, 10) || 4533;
    } else if(champ === 'offset_deg'){
      cible.offset_deg = parseFloat(el.value) || 0;
    } else {
      cible[champ] = el.value;
    }
  });
  // Les bandes restent dans l'ordre du plan de bandes, pas dans celui des clics.
  antennesRows.forEach(a => {
    a.bandes = PARC_BANDES.filter(b => (a.bandes || []).includes(b));
  });
}

// Un id LIBRE, jamais un déjà pris. `'rotor'+(length+1)` reforgeait un id
// existant après une suppression (retirer le 1er de deux, en rajouter un ->
// deux fois 'rotor2'), et l'antenne qui pointait sur l'ancien se reliait alors
// au mauvais pylône en silence (revue 01/08/2026).
function _idLibre(prefixe, rows){
  const pris = new Set(rows.map(r => r.id));
  let n = 1;
  while(pris.has(prefixe + n)) n++;
  return prefixe + n;
}
function addAntenne(){ readParcStation(); antennesRows.push({nom:'', bandes:[], type:'', rotor_id:'', ampli_id:''}); renderParcStation(); }
function removeAntenne(i){ readParcStation(); antennesRows.splice(i,1); renderParcStation(); }
function addRotor(){ readParcStation(); rotorsRows.push({id:_idLibre('rotor', rotorsRows), nom:'', enabled:true, host:'', port:4533, proto:'rotctld', brand:'', model:'', offset_deg:0}); renderParcStation(); }
function removeRotor(i){ readParcStation(); rotorsRows.splice(i,1); renderParcStation(); }
function addAmpli(){ readParcStation(); amplisRows.push({id:_idLibre('ampli', amplisRows), nom:'', enabled:true, brand:'', port:''}); renderParcStation(); }
function removeAmpli(i){ readParcStation(); amplisRows.splice(i,1); renderParcStation(); }

function quickSave() {
  // Sauvegarde silencieuse + feedback visuel sur le bouton
  saveConfig(true);
}

// Bouton "💾 Enregistrer" de chaque panneau catégorie : sauvegarde et reste
// ouvert (plus de hub où "revenir" depuis la refonte sidebar du 08/08/2026 —
// changer de section se fait en cliquant une autre entrée de l'arborescence).
// Feedback visuel "ENREGISTRÉ" géré par saveConfig() elle-même sur `btn`.
function saveCategoryPanel(btn){
  saveConfig(true, btn);
}

let _lastConfigSavePromise = Promise.resolve();
function saveConfig(silent = false, feedbackBtn = null) {
  // Garde-fou H2 : une sauvegarde explicite (bouton SAUVEGARDER CONFIG,
  // LOGGER) exige indicatif/locator/concours complets — la sauvegarde rapide
  // silencieuse (💾 flottant, appelée à chaque étape) reste permissive pour
  // ne pas gêner la saisie progressive.
  if(!silent){
    const missing = _missingStationFields(5);
    if(missing.length){ _warnMissingStation(missing); return false; }
    // Correctif B2 : Club Log Live Stream était activable sans qu'aucun
    // identifiant ClubLog ne soit renseigné (juste un texte d'avertissement
    // statique, jamais vérifié) — le serveur pousse alors chaque QSO en tâche
    // de fond (fire-and-forget) et échoue en silence, sans que l'utilisateur
    // ne soit jamais informé que rien n'est réellement remonté vers ClubLog.
    if(document.getElementById('clublog_live').value === '1'){
      const clubLogMissing = ['clublog_email','clublog_callsign','clublog_password','clublog_api_key']
        .some(id => !document.getElementById(id).value.trim());
      if(clubLogMissing){
        _showConfigValidationBanner([{message: T('Club Log Live Stream est activé mais les identifiants ClubLog ne sont pas tous renseignés (email, indicatif, mot de passe, clé API) — section QSL'), category: 'qsl'}]);
        return false;
      }
    }
    // Même garde-fou que ci-dessus (B2), pour l'envoi auto QRZ Logbook.
    if(document.getElementById('qrz_logbook_push').value === '1'
       && !document.getElementById('qrz_logbook_key').value.trim()){
      _showConfigValidationBanner([{message: T("L'envoi auto QRZ Logbook est activé mais la clé API QRZ Logbook est vide — section QSL"), category: 'qsl'}]);
      return false;
    }
    // SOTA : la case d'approbation IA sans clientId n'a pas de sens (rien à
    // approuver) ; le clientId sans case cochée est volontairement TOLÉRÉ ici
    // (post_spot() bloquera lui-même l'appel réseau) pour ne pas empêcher de
    // renseigner le clientId avant d'avoir fini la démarche d'approbation.
    if(document.getElementById('sota_ai_approval_ack')?.checked
       && !document.getElementById('sota_client_id').value.trim()){
      _showConfigValidationBanner([{message: T("La case d'approbation SOTA est cochée mais aucun clientId n'est renseigné — section Expédition"), category: 'expedition'}]);
      return false;
    }
  }
  const provider = getSelectedProvider();
  const apiKey = document.getElementById('api_key').value;
  if(apiKey){
    localStorage.setItem(`logx_apikey_${provider}`, apiKey);
    localStorage.setItem('logx_apikey', apiKey); // compat
  }
  localStorage.setItem('logx_ai_provider', provider);
  localStorage.setItem('logx_ai_model', document.getElementById('ai_model').value);
  const config = {
    usage_mode: document.getElementById('usage_mode').value,
    callsign: document.getElementById('callsign').value,
    callsign_contest: document.getElementById('callsign_contest').value,
    locator: document.getElementById('locator').value,
    city: document.getElementById('city').value,
    altitude: _numClamped('altitude', 0),
    postal: document.getElementById('postal').value,
    op_name: document.getElementById('operator_name').value,
    op_call: document.getElementById('op_call').value,
    club: document.getElementById('club').value,
    email: document.getElementById('email').value,
    section: document.getElementById('section_edi').value,
    contest_start_date: document.getElementById('contest_start_date').value,
    contest_end_date: document.getElementById('contest_end_date').value,
    contest_end_utc: document.getElementById('contest_end_utc').value,
    power: _numClamped('power', 100),
    power_class: document.getElementById('power_class').value,
    log_software: document.getElementById('log_software').value,
    ant_hf: document.getElementById('ant_hf').value,
    ant_144: document.getElementById('ant_144').value,
    ant_432: document.getElementById('ant_432').value,
    ant_shf: document.getElementById('ant_shf').value,
    radio: document.getElementById('radio').value,
    country: (document.getElementById('country').value||'FRA').toUpperCase().slice(0,3),
    active_satellite: document.getElementById('active_satellite').value,
    submit_url: document.getElementById('submit_url').value,
    submit_deadline: document.getElementById('submit_deadline').value,
    contest: state.contest,
    toggles: state.toggles,
    on4kst_callsign: document.getElementById('on4kst_callsign').value.toUpperCase().trim(),
    on4kst_password: document.getElementById('on4kst_password').value,
    qrz_user: document.getElementById('qrz_user').value.trim(),
    qrz_password: document.getElementById('qrz_password').value,
    eqsl_user: document.getElementById('eqsl_user').value.trim(),
    eqsl_password: document.getElementById('eqsl_password').value,
    lotw_user: document.getElementById('lotw_user').value.trim(),
    lotw_password: document.getElementById('lotw_password').value,
    clublog_email: document.getElementById('clublog_email').value.trim(),
    clublog_callsign: document.getElementById('clublog_callsign').value.trim(),
    clublog_password: document.getElementById('clublog_password').value,
    clublog_api_key: document.getElementById('clublog_api_key').value.trim(),
    qrzcq_callsign: document.getElementById('qrzcq_callsign').value.trim(),
    qrzcq_api_key: document.getElementById('qrzcq_api_key').value.trim(),
    hrdlog_callsign: document.getElementById('hrdlog_callsign').value.trim(),
    hrdlog_code: document.getElementById('hrdlog_code').value.trim(),
    qrz_logbook_key: document.getElementById('qrz_logbook_key').value.trim(),
    qrz_logbook_push: document.getElementById('qrz_logbook_push').value,
    sota_client_id: document.getElementById('sota_client_id').value.trim(),
    sota_ai_approval_ack: document.getElementById('sota_ai_approval_ack')?.checked ? '1' : '',
    scoreboard_enabled: document.getElementById('scoreboard_enabled').value,
    scoreboard_interval: _numClamped('scoreboard_interval', 5),
    backup_folder: document.getElementById('backup_folder').value.trim(),
    backup_interval: _numClamped('backup_interval', 15),
    lan_sync_enabled: document.getElementById('lan_sync_enabled').value,
    lan_sync_token: document.getElementById('lan_sync_token').value.trim(),
    cloudsync_mode: document.getElementById('cloudsync_mode').value,
    cloudsync_folder: document.getElementById('cloudsync_folder').value.trim(),
    cloudsync_interval: _numClamped('cloudsync_interval', 3),
    cloudsync_secret: document.getElementById('cloudsync_secret').value,
    mysql_mode: document.getElementById('mysql_mode').value,
    mysql_host: document.getElementById('mysql_host').value.trim(),
    mysql_port: parseInt(document.getElementById('mysql_port').value, 10) || 3306,
    mysql_user: document.getElementById('mysql_user').value.trim(),
    mysql_password: document.getElementById('mysql_password').value,
    mysql_database: document.getElementById('mysql_database').value.trim(),
    rbn_enabled: document.getElementById('rbn_enabled').value,
    clublog_live: document.getElementById('clublog_live').value,
    expedition_mode: document.getElementById('expedition_mode').value,
    activation_program: document.getElementById('activation_program').value,
    my_activation_ref: document.getElementById('my_activation_ref').value.trim().toUpperCase(),
    cluster_spot_enabled: document.getElementById('cluster_spot_enabled').value,
    cluster_spot_host: document.getElementById('cluster_spot_host').value.trim(),
    cluster_spot_port: parseInt(document.getElementById('cluster_spot_port').value, 10) || 7300,
    wall_fields: {
      time:    document.getElementById('wf_time').checked,
      flag:    document.getElementById('wf_flag').checked,
      country: document.getElementById('wf_country').checked,
      name:    document.getElementById('wf_name').checked,
      band:    document.getElementById('wf_band').checked,
      freq:    document.getElementById('wf_freq').checked,
      mode:    document.getElementById('wf_mode').checked,
      rst:     document.getElementById('wf_rst').checked,
      op:      document.getElementById('wf_op').checked,
    },
    // Objectif QSO TOTAL de session pour la barre de progression de l'écran
    // mural — distinct de rc_rate_goal (objectif QSO/HEURE, localStorage).
    wall_qso_goal: _numClamped('wall_qso_goal', 0),
    // Correctif : aucun élément id="rig_enabled" n'existe dans la page (le
    // pilotage rigctld est en fait activé via cat_enabled + cat_mode='rigctld',
    // section RADIO unifiée) — l'ancienne ligne renvoyait donc toujours false,
    // rendant le mode rigctld inopérant côté serveur (logx_rig.py/logx_http.py
    // conditionnent /rig/qsy, /rig/cw, /rig/stop sur ce seul champ).
    rig_enabled: document.getElementById('cat_enabled').value === '1'
                && document.getElementById('cat_mode').value === 'rigctld',
    rig_host: document.getElementById('rig_host')?.value.trim() || '',
    rig_port: parseInt(document.getElementById('rig_port')?.value, 10) || 4532,
    cat_enabled: !!document.getElementById('cat_enabled').value,
    cat_mode: document.getElementById('cat_mode').value,
    cat_brand: document.getElementById('cat_brand').value,
    cat_model: document.getElementById('cat_model').value,
    cat_port: document.getElementById('cat_port').value,
    cat_baudrate: parseInt(document.getElementById('cat_baudrate').value, 10) || 19200,
    cat_civ_addr: document.getElementById('cat_civ_addr').value.trim(),
    tci_host: document.getElementById('tci_host').value.trim(),
    tci_port: parseInt(document.getElementById('tci_port').value, 10) || 50001,
    flrig_host: document.getElementById('flrig_host')?.value.trim() || '',
    flrig_port: parseInt(document.getElementById('flrig_port')?.value, 10) || 12345,
    // omnirig_enabled/flexradio_enabled/icomremote_enabled : dérivés de
    // cat_enabled+cat_mode plutôt qu'un interrupteur séparé dans l'UI (même
    // motif que rig_enabled ci-dessus) — chaque module a son PROPRE champ
    // 'enabled' en ceinture-et-bretelles (voir logx_omnirig.py/logx_flexradio.py/
    // logx_icomremote.py), mais l'opérateur n'a qu'UN SEUL bouton à actionner.
    omnirig_enabled: document.getElementById('cat_enabled').value === '1'
                    && document.getElementById('cat_mode').value === 'omnirig',
    omnirig_rig_num: parseInt(document.getElementById('omnirig_rig_num')?.value, 10) || 1,
    flexradio_enabled: document.getElementById('cat_enabled').value === '1'
                       && document.getElementById('cat_mode').value === 'flex',
    flexradio_host: document.getElementById('flexradio_host')?.value.trim() || '',
    flexradio_port: parseInt(document.getElementById('flexradio_port')?.value, 10) || 4992,
    icomremote_enabled: document.getElementById('cat_enabled').value === '1'
                        && document.getElementById('cat_mode').value === 'icom_remote',
    icomremote_host: document.getElementById('icomremote_host')?.value.trim() || '',
    icomremote_control_port: parseInt(document.getElementById('icomremote_control_port')?.value, 10) || 50001,
    icomremote_civ_port: parseInt(document.getElementById('icomremote_civ_port')?.value, 10) || 50002,
    icomremote_civ_addr: document.getElementById('icomremote_civ_addr')?.value.trim() || '',
    icomremote_username: document.getElementById('icomremote_username')?.value.trim() || '',
    icomremote_password: document.getElementById('icomremote_password')?.value || '',
    pgxl_enabled: !!document.getElementById('pgxl_enabled')?.value,
    pgxl_host: document.getElementById('pgxl_host')?.value.trim() || '',
    pgxl_port: parseInt(document.getElementById('pgxl_port')?.value, 10) || 9008,
    pgxl_timeout: parseFloat(document.getElementById('pgxl_timeout')?.value) || 3.0,
    acom_enabled: !!document.getElementById('acom_enabled')?.value,
    acom_port: document.getElementById('acom_port')?.value || '',
    acom_model: document.getElementById('acom_model')?.value || '',
    acom_timeout: parseFloat(document.getElementById('acom_timeout')?.value) || 3.0,
    telemetry_enabled: !!document.getElementById('telemetry_enabled')?.value,
    telemetry_endpoint: document.getElementById('telemetry_endpoint')?.value.trim() || '',
    wsjtx_enabled: !!document.getElementById('wsjtx_enabled').value,
    wsjtx_port: parseInt(document.getElementById('wsjtx_port').value, 10) || 2237,
    adifnet_mode: document.getElementById('adifnet_mode').value,
    adifnet_port: parseInt(document.getElementById('adifnet_port').value, 10) || 12060,
    adifnet_target: document.getElementById('adifnet_target').value.trim() || '255.255.255.255',
    mqtt_enabled: !!document.getElementById('mqtt_enabled')?.value,
    mqtt_host: document.getElementById('mqtt_host')?.value.trim() || '',
    mqtt_port: parseInt(document.getElementById('mqtt_port')?.value, 10) || 1883,
    mqtt_topic_prefix: document.getElementById('mqtt_topic_prefix')?.value.trim() || 'logx',
    voicekeyer_enabled: !!document.getElementById('voicekeyer_enabled').value,
    voicekeyer_device: document.getElementById('voicekeyer_device').value,
    voicekeyer_device2: document.getElementById('voicekeyer_device2')?.value || '',
    voicekeyer_voice_id: document.getElementById('voicekeyer_voice_id').value,
    voicekeyer_rate: _numClamped('voicekeyer_rate', 175),
    voicekeyer_ai_enabled: !!document.getElementById('voicekeyer_ai_enabled')?.value,
    voicekeyer_ai_provider: 'elevenlabs',
    voicekeyer_ai_api_key: document.getElementById('voicekeyer_ai_api_key')?.value.trim() || '',
    voicekeyer_ai_voice_id: document.getElementById('voicekeyer_ai_voice_id')?.value.trim() || '',
    voicekeyer_piper_enabled: !!document.getElementById('voicekeyer_piper_enabled')?.value,
    voicekeyer_piper_exe: document.getElementById('voicekeyer_piper_exe')?.value.trim() || '',
    voicekeyer_piper_model: document.getElementById('voicekeyer_piper_model')?.value.trim() || '',
    cat2_enabled: document.getElementById('cat2_enabled')?.value || '',
    cat2_mode: document.getElementById('cat2_mode')?.value || 'native',
    cat2_brand: document.getElementById('cat2_brand')?.value || '',
    cat2_port: document.getElementById('cat2_port')?.value.trim() || '',
    cat2_baudrate: parseInt(document.getElementById('cat2_baudrate')?.value, 10) || 0,
    cat2_omnirig_rig_num: parseInt(document.getElementById('cat2_omnirig_rig_num')?.value, 10) || 1,
    so2r_enabled: document.getElementById('so2r_enabled')?.value || '',
    so2r_port: document.getElementById('so2r_port')?.value.trim() || '',
    so2r_stereo: document.getElementById('so2r_stereo')?.value || '1',
    winkeyer_enabled: document.getElementById('winkeyer_enabled')?.value || '',
    winkeyer_port: document.getElementById('winkeyer_port')?.value.trim() || '',
    winkeyer_wpm: _numClamped('winkeyer_wpm', 25),
    transverters: readTransverters(),
    autostart_programs: readAutostart(),
    // Parc de la station. readParcStation() relit les champs à l'instant de la
    // sauvegarde — ne jamais sérialiser l'état mémoire sans cette relecture,
    // sinon une modification non encore validée par un « change » serait perdue.
    ...(function(){ readParcStation(); return {
      antennes: antennesRows, rotors: rotorsRows, amplis: amplisRows}; })(),
    amp_enabled: !!document.getElementById('amp_enabled').value,
    amp_brand: document.getElementById('amp_brand').value,
    amp_conn_mode: document.getElementById('amp_conn_mode').value,
    amp_port: document.getElementById('amp_port').value,
    amp_baudrate: parseInt(document.getElementById('amp_baudrate').value, 10) || 0,
    amp_civ_addr: document.getElementById('amp_civ_addr').value.trim(),
    amp_host: document.getElementById('amp_host').value.trim(),
    amp_net_port: parseInt(document.getElementById('amp_net_port').value, 10) || 0,
    rotor_enabled: !!document.getElementById('rotor_enabled').value,
    rotor_host: document.getElementById('rotor_host').value.trim(),
    rotor_port: parseInt(document.getElementById('rotor_port').value, 10) || 4533,
    rotor_proto: (document.getElementById('rotor_proto') || {}).value || 'rotctld',
    rotor_brand: (document.getElementById('rotor_brand') || {}).value || '',
    rotor_model: (document.getElementById('rotor_model') || {}).value || '',
    relay_enabled: !!document.getElementById('relay_enabled').value,
    relay_kind: document.getElementById('relay_kind').value,
    relay_port: document.getElementById('relay_port').value,
    relay_baud: parseInt(document.getElementById('relay_baud').value, 10) || 0,
    relay_host: document.getElementById('relay_host').value.trim(),
    relay_user: document.getElementById('relay_user').value.trim(),
    relay_password: document.getElementById('relay_password').value,
    relay_count: parseInt(document.getElementById('relay_count').value, 10) || 4,
    relay_auto_band: !!document.getElementById('relay_auto_band').value,
    relay_band_map: readRelayBandMap(),
    alert_dx_km: _numClamped('alert_dx_km', 1200),
    spotter_reliable_km: _numClamped('spotter_reliable_km', 600),
    alert_sound: document.getElementById('alert_sound').value !== '',
    alert_volume: _numClamped('alert_volume', 60),
    refresh_min: _numClamped('refresh_min', 2),
    priority_mode: document.getElementById('priority_mode').value,
    spot_prefix_filter: document.getElementById('spot_prefix_filter').value,
    alert_rules: state.alertRules,
    // Bornée par le plafond du mode courant (1/5/40) même si des lignes OP2+
    // restent en mémoire d'un mode précédent (ex. RADIOCLUB -> LOGBOOK SIMPLE) :
    // la sauvegarde reflète toujours la règle "un seul opérateur" en mode simple.
    // modes : qualifications de l'opérateur (SSB/CW/DIGI), consommées par le
    // planning de l'écran mural pour ne proposer que des créneaux compatibles.
    // Case absente du DOM (ligne pas encore rendue) -> considérée cochée par
    // défaut, jamais un opérateur silencieusement privé d'un mode.
    operators: Array.from({length: Math.min(opRowCount, opRowCap())}, (_, idx) => {
      const modeVal = id => { const el = document.getElementById(id); return el ? el.checked : true; };
      return {
        call: document.getElementById(`op${idx+1}_call`).value.toUpperCase().trim(),
        name: document.getElementById(`op${idx+1}_name`).value.trim(),
        modes: {
          ssb: modeVal(`op${idx+1}_mode_ssb`),
          cw: modeVal(`op${idx+1}_mode_cw`),
          digi: modeVal(`op${idx+1}_mode_digi`),
        },
      };
    }).filter(op => op.call),
    postes: Array.from({length: posteRowCount}, (_, idx) =>
      (document.getElementById(`poste${idx+1}_name`)||{}).value || ''
    ).map(s => s.trim()).filter(Boolean),
    api_provider: provider,
    ai_model: document.getElementById('ai_model').value,
    api_key: apiKey,
    saved_at: new Date().toISOString(), // affiché par la barre de statut
  };
  // Audit sécurité : localStorage n'est PLUS le dépôt des secrets (mots de
  // passe, clés API) — une copie EXPURGÉE de ces champs y est écrite (tout le
  // reste continue d'y être mis en cache normalement, rapide, hors-ligne).
  // Les secrets restent envoyés au serveur ci-dessous (POST /config/save,
  // là où ils sont réellement nécessaires) et sont relus au chargement de la
  // page via GET /config/secrets (voir loadSecretsFromServer()), qui exige le
  // jeton d'authentification — au lieu d'être accessibles à toute lecture de
  // localStorage (un XSS ailleurs dans l'appli, ou un accès physique au
  // profil navigateur, ne suffit plus à tout exfiltrer d'un coup).
  const localCopy = { ...config };
  for (const f of SECRET_CONFIG_FIELDS) delete localCopy[f];
  localStorage.setItem('logx_config', JSON.stringify(localCopy));
  // Pousser aussi au serveur : sinon logx_serveur.py travaille avec une config
  // périmée. Cette page est la SEULE à faire ce POST (la page CARTE le faisait
  // aussi, en silence à chaque chargement : un poste au localStorage périmé
  // imposait alors sa portée concours à tout le réseau — POST retiré).
  // Fire-and-forget pour tous les appelants existants (le contrat synchrone
  // true/false de saveConfig() ne change pas) — _lastConfigSavePromise permet
  // aux appelants qui en ont besoin (testVoiceKeyer()) d'attendre que le
  // serveur ait bien reçu CETTE config avant de tester dessus.
  _lastConfigSavePromise = fetch('/config/save', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(config)
  }).catch(e=>console.warn('[CFG] serveur non joignable :', e));
  // Optimiste (comme le feedback "ENREGISTRÉ" ci-dessous, avant même la
  // réponse serveur) : la section actuellement ouverte n'a plus de
  // modifications "non enregistrées" puisqu'on vient de les envoyer — sinon
  // fermer juste après un Enregistrer redemanderait confirmation à tort.
  try { const cur = _currentOpenCat(); if(cur) _catFormSnapshots[cur] = _snapshotCatForm(cur); } catch(e){}
  if(silent){
    // Feedback visuel sur le bouton effectivement cliqué (le bouton flottant
    // d'en-tête est masqué derrière l'overlay plein écran des popups — cf.
    // .cat-modal{z-index:9000} — donc chaque popup passe SON PROPRE bouton
    // "💾 Enregistrer" via saveConfig(true, this) pour recevoir SON feedback).
    const btn = feedbackBtn || document.querySelector('button[onclick="quickSave()"]');
    if(btn){
      const orig = btn.innerHTML;
      btn.innerHTML = '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><polyline points="3,10 7,14 15,4"/></svg> ENREGISTRÉ';
      btn.style.background = 'var(--green)';
      setTimeout(()=>{ btn.innerHTML = orig; btn.style.background = 'linear-gradient(135deg,#00FF88,#C9822E)'; }, 1500);
    }
  } else {
    _configToast(T('✅ Configuration sauvegardée !'));
  }
  return true;
}

// ─── MONO / MULTI OP ─────────────────────────────────────────────────────────
// ─── LIGNES OPÉRATEUR DYNAMIQUES (OP2+) ──────────────────────────────────────
// OP1 reste une ligne statique du HTML (cf. catbody_operators) ; OP2 et
// au-delà sont générées à la volée ici.
//
// Plafond : 1 en LOGBOOK SIMPLE (pas de multi-op, cf. demande explicite de
// retour en arrière), 40 dans tous les modes multi-op.
//
// CONCOURS/EXPÉDITION étaient historiquement limités à 5, « aligné sur les 2
// emplacements MOpe1/MOpe2 de l'export EDI + Remarks pour le reste ». Ce
// n'était pas une contrainte technique : RADIOCLUB tourne depuis toujours à
// 40 avec le MÊME export (au-delà de 2, tout le monde passe par Remarks, que
// l'on soit 6 ou 30). C'était donc un mur arbitraire, et les effectifs réels
// le dépassent couramment — une DXpédition à 10 opérateurs, une équipe de 9
// en contest IOTA (cas rapportés par des utilisateurs). Un opérateur bloqué
// à 5 n'a AUCUN recours : il ne peut pas déclarer son équipe.
let opRowCount = 1;

function opRowCap(){
  return getUsageMode() === 'simple' ? 1 : 40;
}

// Chaque cellule porte data-op-row="i" : c'est le SEUL lien fiable entre une
// ligne logique et ses cellules, la grille étant en display:contents (les
// cellules sont des enfants directs de #opExtraRows, sans conteneur de ligne).
// removeLastOperatorRow() s'en sert pour retirer la ligne ENTIÈRE : compter les
// cellules à la main a déjà divergé une fois (la 4e colonne QUALIFIÉ a été
// ajoutée après la boucle de suppression, qui en retirait toujours 3).
function operatorRowCells(i){
  return `<div data-op-row="${i}" style="font-family:var(--font-mono);font-size:14px;color:var(--muted);font-weight:700">OP${i}</div>`
       + `<input data-op-row="${i}" type="text" id="op${i}_call" placeholder="Indicatif" style="text-transform:uppercase;font-size:14px">`
       + `<input data-op-row="${i}" type="text" id="op${i}_name" placeholder="Prénom" style="font-size:14px">`
       + `<div data-op-row="${i}" class="op-modes-cell" style="display:flex;gap:10px;font-size:13px;font-family:var(--font-mono);color:var(--text)">`
       + `<label style="display:flex;align-items:center;gap:4px;cursor:pointer"><input type="checkbox" id="op${i}_mode_ssb" checked>SSB</label>`
       + `<label style="display:flex;align-items:center;gap:4px;cursor:pointer"><input type="checkbox" id="op${i}_mode_cw" checked>CW</label>`
       + `<label style="display:flex;align-items:center;gap:4px;cursor:pointer"><input type="checkbox" id="op${i}_mode_digi" checked>DIGI</label>`
       + `</div>`;
}

// Ajout/retrait incrémental : ne touche jamais aux lignes déjà présentes,
// pour ne jamais perdre une saisie en cours en changeant de mode.
function addOperatorRow(){
  if(opRowCount >= opRowCap()) return;
  opRowCount++;
  document.getElementById('opExtraRows').insertAdjacentHTML('beforeend', operatorRowCells(opRowCount));
  updateOpRowControls();
}

function removeLastOperatorRow(){
  if(opRowCount <= 1) return;
  const extra = document.getElementById('opExtraRows');
  // Retirer TOUTES les cellules de la dernière ligne, pas un nombre figé : la
  // version précédente en enlevait 3 alors qu'operatorRowCells() en produit 4
  // depuis l'ajout de la colonne QUALIFIÉ. Une cellule survivante décalait
  // toute la grille d'une colonne, et surtout laissait à l'écran des lignes
  // complètes et éditables qu'opRowCount ne couvrait plus : saveConfig() ne
  // lisant que jusqu'à opRowCount, ces opérateurs bien visibles disparaissaient
  // en silence de la config, de l'export et des boutons OP du logbook.
  extra.querySelectorAll(`[data-op-row="${opRowCount}"]`).forEach(el => el.remove());
  opRowCount--;
  updateOpRowControls();
}

// Une ligne opérateur porte-t-elle une saisie ? Sert à ne jamais supprimer
// en silence un indicatif déjà tapé (voir setOperatorCount).
function operatorRowFilled(i){
  const call = document.getElementById(`op${i}_call`);
  const name = document.getElementById(`op${i}_name`);
  return !!((call && call.value.trim()) || (name && name.value.trim()));
}

// Choix DIRECT du nombre d'opérateurs (champ « Nombre d'opérateurs »). En
// expédition ou en radioclub on connaît l'effectif d'avance : cliquer neuf
// fois sur « Ajouter » pour dix opérateurs n'a aucun sens.
// Passe par addOperatorRow()/removeLastOperatorRow() plutôt que par
// ensureOperatorRows() : celle-ci VIDE la grille avant de la reconstruire, ce
// qui effacerait les lignes déjà remplies. Ici on ajoute ou on retire
// seulement à la fin, les saisies existantes sont préservées.
async function setOperatorCount(valeur){
  const cap = opRowCap();
  let n = parseInt(valeur, 10);
  if(!isFinite(n)) n = opRowCount;              // saisie vide/absurde : on ne touche à rien
  n = Math.max(1, Math.min(n, cap));
  // Réduction : les lignes retirées sont les DERNIÈRES. Si l'une d'elles
  // contient déjà un indicatif ou un prénom, on demande confirmation — perdre
  // une saisie sans prévenir serait la pire des surprises la veille d'un
  // concours.
  if(n < opRowCount){
    const perdues = [];
    for(let i = n + 1; i <= opRowCount; i++){
      if(operatorRowFilled(i)) perdues.push(`OP${i}`);
    }
    if(perdues.length && !(await _confirmConfigBanner(
        `Réduire à ${n} opérateur(s) supprimera ${perdues.join(', ')}, `
        + `qui ${perdues.length > 1 ? 'contiennent' : 'contient'} déjà une saisie.\n\nContinuer ?`,
        'Réduire', 'Annuler'))){
      syncOpCountInput();                       // remet le champ sur la valeur réelle
      return;
    }
  }
  while(opRowCount < n) addOperatorRow();
  while(opRowCount > n) removeLastOperatorRow();
  syncOpCountInput();
}

// Le champ doit toujours refléter le nombre RÉEL de lignes : il est aussi
// modifié par les boutons +/−, par la restauration d'une config et par un
// changement de mode d'utilisation (qui change le plafond).
function syncOpCountInput(){
  const input = document.getElementById('opCountInput');
  if(!input) return;
  input.value = opRowCount;
  input.max = opRowCap();
}

// Reconstruit intégralement les lignes OP2+ pour atteindre `count` — réservé
// au chargement/restauration d'une config (la grille est alors vide, rien à
// préserver). addOperatorRow()/removeLastOperatorRow() ne passent jamais par
// ici, pour ne jamais écraser une saisie utilisateur en cours.
function ensureOperatorRows(count){
  count = Math.max(1, Math.min(count, opRowCap()));
  const extra = document.getElementById('opExtraRows');
  extra.innerHTML = '';
  opRowCount = 1;
  for(let i=2;i<=count;i++){
    opRowCount = i;
    extra.insertAdjacentHTML('beforeend', operatorRowCells(i));
  }
  updateOpRowControls();
}

// Champ SECTION CONCOURS (section_edi, popup Identité, expert-only) : garde
// la lettre S/M synchronisée avec le nombre d'opérateurs déclarés, sans
// jamais toucher à la portée de bande (MB/SB) déjà choisie par l'utilisateur.
function syncSectionEdiFromOpCount(){
  const sel = document.getElementById('section_edi');
  if(!sel) return;
  const isSB = sel.value.endsWith('SB');
  // Compte EFFECTIF (borné au plafond du mode), pas opRowCount brut : en
  // LOGBOOK SIMPLE les lignes OP2+ restent en mémoire mais sont hors-jeu
  // (masquées, exclues de saveConfig()) — l'export EDI doit rester cohérent
  // avec ce qui est réellement sauvegardé, pas avec un historique de saisie.
  const wantMulti = Math.min(opRowCount, opRowCap()) > 1;
  if(wantMulti === sel.value.startsWith('MO')) return;
  sel.value = wantMulti ? (isSB ? 'MOSB' : 'MOMB') : (isSB ? 'SOSB' : 'SOMB');
}

function updateOpRowControls(){
  const cap = opRowCap();
  const extra = document.getElementById('opExtraRows');
  // LOGBOOK SIMPLE (cap=1) : les lignes OP2+ restent en mémoire (au cas où
  // l'utilisateur repasse en CONCOURS/RADIOCLUB) mais disparaissent de l'écran
  // — ce mode ne doit offrir aucune possibilité de saisir plusieurs OP.
  if(extra) extra.style.display = cap <= 1 ? 'none' : 'contents';
  const addBtn = document.getElementById('opAddBtn');
  const rmBtn  = document.getElementById('opRemoveBtn');
  const note   = document.getElementById('opRowsCapNote');
  const title  = document.getElementById('opSectionTitle');
  const sub    = document.getElementById('opSectionNote');
  if(addBtn) addBtn.style.display = (cap <= 1 || opRowCount >= cap) ? 'none' : '';
  if(rmBtn)  rmBtn.style.display  = (cap <= 1 || opRowCount <= 1)   ? 'none' : '';
  if(note)   note.textContent = cap > 1 ? `${opRowCount} / ${cap} opérateurs` : '';
  // Saisie directe de l'effectif : masquée en LOGBOOK SIMPLE (un seul
  // opérateur possible), et tenue à jour ici — c'est le point de passage
  // commun aux boutons +/−, à la restauration d'une config et au changement
  // de mode d'utilisation (qui change le plafond).
  const countLbl = document.getElementById('opCountLabel');
  if(countLbl) countLbl.style.display = cap <= 1 ? 'none' : 'inline-flex';
  syncOpCountInput();
  // LOGBOOK SIMPLE (cap==1) : un seul opérateur possible, un planning de
  // roulement entre opérateurs n'a alors aucun sens — masqué avec le reste
  // du multi-op plutôt que de laisser une section orpheline.
  const shiftsSec = document.getElementById('shiftsSection');
  if(shiftsSec) shiftsSec.style.display = cap <= 1 ? 'none' : '';
  const isMulti = cap > 1 && opRowCount > 1;
  if(title) title.textContent = isMulti ? 'OPÉRATEURS (MULTI-OP)' : 'OPÉRATEUR';
  if(sub)   sub.textContent = isMulti
    ? `Jusqu'à ${cap} opérateurs — leurs indicatifs apparaîtront sur les boutons OP dans le logbook`
    : 'Ton indicatif personnel (Single Op)';
  syncSectionEdiFromOpCount();
  // Le <select> du planning (plus bas) doit refléter tout ajout/retrait/
  // restauration de ligne opérateur, pas seulement l'ouverture du popup.
  if(typeof refreshShiftOperatorSelect === 'function') refreshShiftOperatorSelect();
}

// ─── PLANNING DE ROULEMENT DES OPÉRATEURS (écran mural) ──────────────────────
// Créneaux persistés côté serveur (voir GET/POST /shifts/* dans logx_http.py,
// modèle dans logx_storage.py) — indépendants de la config elle-même, donc
// chargés/rafraîchis à part plutôt que via loadConfig()/saveConfig().
let _shiftsCache = [];   // dernier /shifts/list connu

// Le <select> propose les opérateurs SAISIS dans la grille au-dessus (pas
// forcément encore enregistrés) : recalculé à chaque ouverture du popup —
// voir openCategoryPopup('operators').
function refreshShiftOperatorSelect(){
  const sel = document.getElementById('shiftOpSelect');
  if(!sel) return;
  const cap = opRowCap();
  const rows = [];
  for(let i=1;i<=Math.min(opRowCount, cap);i++){
    const callEl = document.getElementById(`op${i}_call`);
    const call = ((callEl && callEl.value) || '').toUpperCase().trim();
    if(!call) continue;
    const nameEl = document.getElementById(`op${i}_name`);
    rows.push({call, name: ((nameEl && nameEl.value) || '').trim()});
  }
  const prev = sel.value;
  sel.innerHTML = rows.length
    ? rows.map(o => `<option value="${escC(o.call)}">${escC(o.call)}${o.name ? ' — ' + escC(o.name) : ''}</option>`).join('')
    : '<option value="">Configure au moins un opérateur ci-dessus</option>';
  if(rows.some(o => o.call === prev)) sel.value = prev;
}

function _shiftAddStatus(msg, color){
  const el = document.getElementById('shiftAddStatus');
  if(!el) return;
  el.style.display = msg ? '' : 'none';
  el.textContent = msg || '';
  el.style.color = color || 'var(--muted)';
}

async function loadShifts(){
  const list = document.getElementById('shiftsList');
  const emptyNote = document.getElementById('shiftsEmptyNote');
  if(!list) return;
  try{
    const r = await fetch('/shifts/list');
    const d = await r.json();
    _shiftsCache = d.shifts || [];
  }catch(e){
    console.warn('[SHIFTS] chargement impossible :', e);
    list.innerHTML = '';
    if(emptyNote){ emptyNote.textContent = 'Planning indisponible (serveur injoignable).'; emptyNote.style.display = ''; }
    return;
  }
  if(!_shiftsCache.length){
    list.innerHTML = '';
    if(emptyNote){ emptyNote.textContent = 'Aucun créneau planifié.'; emptyNote.style.display = ''; }
    return;
  }
  if(emptyNote) emptyNote.style.display = 'none';
  list.innerHTML = _shiftsCache.map(s => {
    const modeTag = s.mode ? ` <span style="color:var(--accent2)">[${escC(String(s.mode).toUpperCase())}]</span>` : '';
    const dateTag = s.date ? `${escC(s.date)} ` : '';
    const nameTag = s.name ? ` (${escC(s.name)})` : '';
    const noteTag = s.note ? ` — <span style="color:var(--muted)">${escC(s.note)}</span>` : '';
    return `<div style="display:flex;align-items:center;gap:10px;background:var(--bg3);border:1px solid var(--border);border-radius:6px;padding:8px 12px;font-family:var(--font-mono);font-size:13px">
      <span style="flex:1">${dateTag}<strong>${escC(s.start)}–${escC(s.end)}</strong> · ${escC(s.call)}${nameTag}${modeTag}${noteTag}</span>
      <button type="button" class="op-row-btn" onclick="deleteShift(${Number(s.id) || 0})" title="Supprimer ce créneau"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg></button>
    </div>`;
  }).join('');
}

async function addShift(){
  const sel = document.getElementById('shiftOpSelect');
  const call = sel ? sel.value : '';
  if(!call){ _shiftAddStatus('⚠️ Choisis un opérateur (configure-le d’abord ci-dessus).', 'var(--red)'); return; }
  const start = (document.getElementById('shiftStart')||{}).value || '';
  const end = (document.getElementById('shiftEnd')||{}).value || '';
  if(!start || !end){ _shiftAddStatus('⚠️ Heure de début et heure de fin requises.', 'var(--red)'); return; }
  const payload = {
    call, start, end,
    mode: (document.getElementById('shiftMode')||{}).value || '',
    note: (document.getElementById('shiftNote')||{}).value.trim() || '',
  };
  _shiftAddStatus('', '');
  try{
    const r = await fetch('/shifts/add', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const d = await r.json();
    if(!r.ok || !d.ok){
      _shiftAddStatus('❌ ' + (d.error || "Échec de l'ajout"), 'var(--red)');
      return;
    }
    _shiftAddStatus(d.warning ? ('⚠️ ' + d.warning) : '', 'var(--red)');
    const noteEl = document.getElementById('shiftNote');
    if(noteEl) noteEl.value = '';
    await loadShifts();
  }catch(e){
    _shiftAddStatus('❌ Serveur injoignable.', 'var(--red)');
  }
}

async function deleteShift(id){
  try{
    await fetch(`/shifts/delete/${id}`, {method: 'POST'});
  }catch(e){
    console.warn('[SHIFTS] suppression impossible :', e);
  }
  await loadShifts();
}

// ─── POSTES RADIO (mode RADIOCLUB) ───────────────────────────────────────────
const POSTE_ROW_CAP = 20;
let posteRowCount = 0;

function posteRowHtml(i){
  return `<input type="text" id="poste${i}_name" placeholder="Poste ${i} (ex. HF1)" style="font-size:14px">`;
}

function addPosteRow(){
  if(posteRowCount >= POSTE_ROW_CAP) return;
  posteRowCount++;
  document.getElementById('posteRowsGrid').insertAdjacentHTML('beforeend', posteRowHtml(posteRowCount));
  updatePosteRowControls();
}

function removeLastPosteRow(){
  if(posteRowCount <= 0) return;
  const grid = document.getElementById('posteRowsGrid');
  grid.lastElementChild && grid.lastElementChild.remove();
  posteRowCount--;
  updatePosteRowControls();
}

function ensurePosteRows(count){
  count = Math.max(0, Math.min(count, POSTE_ROW_CAP));
  const grid = document.getElementById('posteRowsGrid');
  grid.innerHTML = '';
  posteRowCount = 0;
  for(let i=1;i<=count;i++){
    posteRowCount = i;
    grid.insertAdjacentHTML('beforeend', posteRowHtml(i));
  }
  updatePosteRowControls();
}

function updatePosteRowControls(){
  const addBtn = document.getElementById('posteAddBtn');
  const rmBtn  = document.getElementById('posteRemoveBtn');
  const note   = document.getElementById('posteRowsCapNote');
  if(addBtn) addBtn.style.display = posteRowCount >= POSTE_ROW_CAP ? 'none' : '';
  if(rmBtn)  rmBtn.style.display  = posteRowCount <= 0 ? 'none' : '';
  if(note)   note.textContent = posteRowCount ? `${posteRowCount} / ${POSTE_ROW_CAP} postes` : '';
}

// ─── ÉCRAN D'ACCUEIL (première visite) ───────────────────────────────────────
// Rend explicite ce que getUiMode() devinait jusque-là en silence (voir plus
// bas) : deux questions, une seule fois, jamais reposées ensuite — répondre
// (ou "passer") pose rc_ui_mode, qui sert justement de signal "déjà vu" (pas
// besoin d'un second indicateur dans localStorage rien que pour ça).
const _onbState = {experience: null, usage: null};
let _onbResolve = null;

function onbPick(kind, value){
  _onbState[kind] = value;
  const groupId = kind === 'experience' ? 'onbExperienceChoices' : 'onbUsageChoices';
  document.querySelectorAll('#' + groupId + ' .onb-choice').forEach(function(btn, i){
    // L'ORDRE des boutons dans le DOM suit celui des onclick ci-dessus —
    // comparer au texte serait fragile aux traductions futures, comparer à
    // l'index d'apparition ne l'est pas puisqu'il est fixé par ce même HTML.
    btn.classList.toggle('selected', btn.getAttribute('onclick') === `onbPick('${kind}','${value}')`);
  });
  const startBtn = document.getElementById('onbStartBtn');
  const ready = !!(_onbState.experience && _onbState.usage);
  if (startBtn) startBtn.disabled = !ready;
  const hint = document.getElementById('onbStartHint');
  if (hint) hint.style.display = ready ? 'none' : '';
}

function _closeOnboarding(){
  const overlay = document.getElementById('onboardingOverlay');
  if (overlay) overlay.style.display = 'none';
  if (typeof _onbResolve === 'function') { const r = _onbResolve; _onbResolve = null; r(); }
}

function submitOnboarding(){
  if (!(_onbState.experience && _onbState.usage)) return;   // bouton désactivé sinon, filet de sécurité
  localStorage.setItem('rc_ui_mode', _onbState.experience === 'oui' ? 'expert' : 'simple');
  const sel = document.getElementById('usage_mode');
  if (sel) { sel.value = _onbState.usage; onUsageModeChange(); }
  _closeOnboarding();
}

// "Passer" : ferme sans RIEN choisir explicitement — getUiMode() retombe sur
// son heuristique existante (silencieuse) plutôt que de forcer une valeur.
function skipOnboarding(){
  _closeOnboarding();
}

// Résout dès que l'écran est fermé (répondu ou passé) — ou immédiatement si
// rc_ui_mode existe déjà (visite précédente, ou heuristique déjà tranchée par
// un ancien passage sur cette page avant l'ajout de cet écran).
function maybeShowOnboarding(){
  return new Promise(function(resolve){
    if (localStorage.getItem('rc_ui_mode')) { resolve(); return; }
    const overlay = document.getElementById('onboardingOverlay');
    if (!overlay) { resolve(); return; }
    _onbResolve = resolve;
    overlay.style.display = 'flex';
  });
}

// ─── MODE DÉBUTANT / EXPERT ──────────────────────────────────────────────────
// Le mode débutant masque les réglages avancés (sections .expert-only : IA,
// propagation, clusters, ON4KST, alertes, prompt) et saute l'étape 4.
// Les valeurs par défaut de ces réglages restent actives en arrière-plan.
function getUiMode(){
  const saved = localStorage.getItem('rc_ui_mode');
  if (saved) return saved;
  // Première visite : simple si aucune station configurée, expert sinon
  try{
    const cfg = JSON.parse(localStorage.getItem('logx_config') || '{}');
    return cfg.callsign ? 'expert' : 'simple';
  }catch(e){ return 'simple'; }
}

function applyUiMode(){
  const simple = getUiMode() === 'simple';
  document.body.classList.toggle('simple-mode', simple);
  const btn = document.getElementById('uiModeToggle');
  if (btn){
    btn.textContent = simple ? '🎚 DÉBUTANT' : '🎚 EXPERT';
    btn.style.color = simple ? 'var(--green)' : 'var(--muted)';
  }
  // Ancien correctif H4 (masquage de l'étape 4/PROPAGATION en mode débutant)
  // retiré le 08/08/2026 : ciblait des éléments #step4/#panel3/#panel5 déjà
  // absents du DOM depuis la migration hub/popups, et aucune des catégories
  // concernées (sources/alerts/expedition) n'est expert-only aujourd'hui —
  // elles sont déjà toujours visibles dans l'arborescence, quel que soit le
  // mode débutant/expert.
}

function toggleUiMode(){
  localStorage.setItem('rc_ui_mode', getUiMode() === 'simple' ? 'expert' : 'simple');
  applyUiMode();
}

// ─── MODE D'UTILISATION (logbook simple / concours / expédition) ────────────
// Contrairement au mode débutant/expert (préférence d'affichage locale), ce
// choix est persisté DANS LA CONFIG (station) : logx_logbook.html le
// lit aussi pour adapter la saisie QSO (sélecteur de concours, n° de série,
// score). 'contest' reste la valeur par défaut si absente d'une config plus
// ancienne — comportement inchangé pour les utilisateurs existants.
function getUsageMode(){
  const el = document.getElementById('usage_mode');
  return (el && el.value) || 'contest';
}

// Une activation POTA/SOTA/WWFF... n'a pas de règlement de concours (bandes/
// modes/échange se règlent librement à l'étape FILTRES, cf. section 14) — un
// CONCOURS choisi à l'étape 3 n'a donc pas plus de sens ici qu'en LOGBOOK
// SIMPLE. Seul RADIOCLUB (multi-op qui fait tourner un vrai concours) le
// garde obligatoire.
function _contestOptional(){
  return getUsageMode() === 'simple' || getUsageMode() === 'expedition';
}

function applyUsageMode(){
  const mode = getUsageMode();
  const simple = mode === 'simple';
  const radioclub = mode === 'radioclub';
  document.body.classList.toggle('usage-simple', simple);
  document.body.classList.toggle('usage-radioclub', radioclub);
  // Plafond opérateurs (1/5/40 selon le mode) : rafraîchir les boutons +/-,
  // masquer les lignes OP2+ en LOGBOOK SIMPLE (aucune saisie perdue, juste
  // cachée — cf. updateOpRowControls()).
  updateOpRowControls();
  // Section POSTES RADIO : uniquement pertinente en mode RADIOCLUB.
  const postesSection = document.getElementById('postesSection');
  if (postesSection){
    postesSection.style.display = radioclub ? '' : 'none';
    if (radioclub && posteRowCount === 0) ensurePosteRows(1);
  }
  const note = document.getElementById('usageModeNote');
  if (note) note.textContent = simple
    ? '— catégorie 3. Sélection du concours sans objet, bandes et modes librement réglables dans 4. Dates, bandes & modes'
    : (mode === 'expedition'
        ? '— pense à activer la saisie simplifiée dans la section MODE EXPÉDITION ci-dessous'
        : (radioclub
            ? '— renseigne les postes radio et les opérateurs du club dans la catégorie OPÉRATEURS'
            : ''));
  // Ré-appliquer immédiatement les filtres bande/mode (sans attendre que le
  // panneau FILTRES soit rouvert) : basculer vers/depuis LOGBOOK SIMPLE doit
  // se voir tout de suite si ce panneau est déjà affiché.
  _filtersAppliedFor = null;
  if (_currentOpenCat() === 'filters') applyContestFilters(state.contest);
  applyUiMode();
  renderConfigTree();
}

function onUsageModeChange(){
  const v = document.getElementById('usage_mode').value;
  // Passage en expédition : propose par défaut la saisie simplifiée (juste
  // indicatif + RST) si l'utilisateur n'a pas déjà réglé ce champ lui-même.
  if (v === 'expedition'){
    const em = document.getElementById('expedition_mode');
    if (em && !em.value) em.value = '1';
  }
  // Passage EN LOGBOOK SIMPLE : les bandes/modes forcés par le dernier concours
  // filtré (ex. REF_QRP -> uniquement VHF/UHF/SHF, cf. applyContestFilters()
  // étape "1. Tout désactiver") restent sinon cochés en arrière-plan — le
  // choix manuel de bandes HF de l'utilisateur en mode simple se retrouve
  // alors MÉLANGÉ à ces cases VHF/SHF jamais décochées. On repart d'une page
  // blanche uniquement au moment du changement explicite vers "simple" (pas
  // à chaque rendu, pour ne pas effacer un choix déjà fait en mode simple).
  if (v === 'simple'){
    document.querySelectorAll('[data-key^="band_"], [data-key^="mode_"]').forEach(el => {
      el.classList.remove('on');
      state.toggles[el.dataset.key] = false;
    });
  }
  applyUsageMode();
}

function toggleTheme(){
  const day = document.body.classList.toggle('day-mode');
  localStorage.setItem('rc_theme', day ? 'day' : 'night');
  document.getElementById('themeToggle').textContent = day ? '🌙' : '☀️';
  // Partagé au serveur : les autres postes ouvrant le lien multi-poste pour
  // la 1re fois hériteront de ce thème au lieu de retomber en mode nuit.
  fetch('/ui/theme', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({theme: day ? 'day' : 'night'})}).catch(()=>{});
}
(function applyTheme(){
  if(localStorage.getItem('rc_theme') === 'day'){
    document.body.classList.add('day-mode');
    document.addEventListener('DOMContentLoaded', ()=>{
      const t = document.getElementById('themeToggle');
      if(t) t.textContent = '🌙';
    });
  }
})();
// Suivre le thème jour/nuit choisi dans un autre onglet (ex: logx_logbook.html)
window.addEventListener('storage', e => {
  if(e.key === 'rc_theme'){
    const day = e.newValue === 'day';
    document.body.classList.toggle('day-mode', day);
    const t = document.getElementById('themeToggle');
    if(t) t.textContent = day ? '🌙' : '☀️';
  }
});

// Adresse(s) LAN pour connecter un téléphone (mode terrain/expédition)
async function loadLanUrls(){
  const el = document.getElementById('lanUrls');
  if(!el) return;
  try{
    const d = await (await fetch('/data/lan_url')).json();
    if(d.urls && d.urls.length){
      el.innerHTML = d.urls.map(u =>
        `<div><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="14" x2="4" y2="11"/><line x1="8" y1="14" x2="8" y2="8"/><line x1="12" y1="14" x2="12" y2="5"/><line x1="16" y1="14" x2="16" y2="2"/></svg> <a href="${u}" target="_blank" style="color:var(--accent2);text-decoration:none">${u}</a></div>`).join('');
    } else {
      el.textContent = 'Adresse réseau introuvable — sur le téléphone : http://<IP-du-PC>:' + (d.port||8080) + '/logx_logbook.html';
    }
  }catch(e){ el.textContent = 'Serveur injoignable.'; }
}
window.addEventListener('load', loadLanUrls);

// Restaure les cases « champs de l'écran mural » depuis la config
function applyWallFields(wf){
  if(!wf || typeof wf !== 'object') return;
  ['time','flag','country','name','band','freq','mode','rst','op'].forEach(k=>{
    const el = document.getElementById('wf_'+k);
    if(el && wf[k]!==undefined) el.checked = !!wf[k];
  });
}

function loadSavedConfig() {
  const saved = localStorage.getItem('logx_config');
  if(!saved) return false;
  try {
    const c = JSON.parse(saved);
    applyFullConfigToForm(c);
    return true;
  } catch(e) { console.warn('Config invalide', e); return false; }
}

// Correctif H1 : saveProfile() capture ~90 champs (via saveConfig() complet)
// mais loadProfile() ne réappliquait qu'un sous-ensemble restreint (~40, via
// l'ancienne applyConfigToForm()) — identifiants QRZ/eQSL/LoTW/ClubLog/QRZCQ/
// HRDLog, radio/ampli/rotor, WSJT-X, réseau ADIF, keyer vocal, scoreboard,
// backup, cloud sync et alertes restaient ceux du profil précédent après un
// changement de profil. Un seul chemin de restauration complète, partagé
// entre chargement de page (loadSavedConfig) et changement de profil (loadProfile).
function applyFullConfigToForm(c) {
    // LA CONFIG RESTAURÉE EST MÉMORISÉE, et pas seulement recopiée dans les
    // champs. Trois listes déroulantes (modèle de radio, port CAT, port ampli)
    // sont remplies APRÈS cette restauration — par init(), ou par une réponse
    // du serveur qui arrive plus tard. Poser une valeur sur un <select> qui
    // n'a pas encore ses <option> échoue SANS ERREUR, et reconstruire les
    // options remet le select sur la première. C'est ce qui faisait « perdre »
    // la radio choisie dès qu'on quittait la page et qu'on y revenait. Ces
    // trois fonctions relisent donc ici la valeur voulue.
    window._cfgRestauree = c || {};
    applyWallFields(c.wall_fields);
    if(c.callsign) document.getElementById('callsign').value = c.callsign;
    if(c.callsign_contest) document.getElementById('callsign_contest').value = c.callsign_contest;
    if(c.locator) { document.getElementById('locator').value = c.locator; updateLocatorHint(); }
    if(c.city) document.getElementById('city').value = c.city;
    if(c.altitude) document.getElementById('altitude').value = c.altitude;
    if(c.postal) document.getElementById('postal').value = c.postal;
    if(c.on4kst_callsign) document.getElementById('on4kst_callsign').value = c.on4kst_callsign;
    if(c.on4kst_password) document.getElementById('on4kst_password').value = c.on4kst_password;
    if(c.qrz_user) document.getElementById('qrz_user').value = c.qrz_user;
    if(c.qrz_password) document.getElementById('qrz_password').value = c.qrz_password;
    ['usage_mode','eqsl_user','eqsl_password','lotw_user','lotw_password','clublog_email',
     'clublog_callsign','clublog_password','clublog_api_key',
     'qrzcq_callsign','qrzcq_api_key','hrdlog_callsign','hrdlog_code',
     'qrz_logbook_key','qrz_logbook_push','sota_client_id',
     'scoreboard_enabled','scoreboard_interval','backup_folder','backup_interval',
     'cloudsync_mode','cloudsync_folder','cloudsync_interval','cloudsync_secret',
     'mysql_mode','mysql_host','mysql_port','mysql_user','mysql_password','mysql_database',
     'rbn_enabled','clublog_live','expedition_mode',
     'cluster_spot_enabled','cluster_spot_host','cluster_spot_port','lan_sync_enabled','lan_sync_token',
     'activation_program','my_activation_ref','wall_qso_goal',
     'cat_mode','cat_brand','cat_model','cat_port','cat_baudrate','cat_civ_addr',
     'tci_host','tci_port','flrig_host','flrig_port',
     'omnirig_rig_num','flexradio_host','flexradio_port',
     'icomremote_host','icomremote_control_port','icomremote_civ_port',
     'icomremote_civ_addr','icomremote_username','icomremote_password',
     'pgxl_host','pgxl_port','pgxl_timeout','acom_port','acom_model','acom_timeout',
     'telemetry_endpoint','voicekeyer_rate',
     'voicekeyer_ai_voice_id','voicekeyer_ai_api_key',
     'voicekeyer_piper_exe','voicekeyer_piper_model',
     'winkeyer_enabled','winkeyer_port','winkeyer_wpm',
     'cat2_enabled','cat2_mode','cat2_brand','cat2_port','cat2_baudrate','cat2_omnirig_rig_num',
     'so2r_enabled','so2r_port','so2r_stereo',
     'amp_brand','amp_conn_mode','amp_port','amp_baudrate','amp_civ_addr','amp_host','amp_net_port',
     'relay_kind','relay_port','relay_baud','relay_host','relay_user','relay_password','relay_count'].forEach(k=>{
      if(c[k]!==undefined && document.getElementById(k)) document.getElementById(k).value = c[k];
    });
    fillClusterPicker();   // remplit le sélecteur de nœuds + aligne sur l'hôte chargé
    refreshLanPeers();     // postes détectés en synchro LAN directe
    buildAlertTypesGrid(); // grille son+voix par type d'alerte (#5)
    transverterRows = Array.isArray(c.transverters) ? c.transverters.map(t => ({
      if: String(t.if || '144'), rf: String(t.rf || '1296'),
      enabled: t.enabled !== false,
      lo_mhz: (t.lo_mhz === undefined || t.lo_mhz === null) ? null : Number(t.lo_mhz)
    })) : [];
    renderTransverters();
    autostartRows = Array.isArray(c.autostart_programs) ? c.autostart_programs.map(p => ({
      name: p.name || '', path: p.path || '', args: p.args || '', enabled: p.enabled !== false
    })) : [];
    renderAutostart();
    // Parc de la station. Les listes absentes restent VIDES : le serveur
    // (logx_station.charger) reprend alors les anciens champs ant_hf/rotor_*/
    // amp_* tout seul. Fabriquer ici une reprise côté page la figerait dans la
    // configuration à la première sauvegarde, et l'opérateur ne pourrait plus
    // revenir en arrière.
    antennesRows = Array.isArray(c.antennes) ? c.antennes.map(a => ({
      id: a.id || '', nom: a.nom || '', bandes: Array.isArray(a.bandes) ? a.bandes.slice() : [],
      type: a.type || '', rotor_id: a.rotor_id || '', ampli_id: a.ampli_id || ''})) : [];
    rotorsRows = Array.isArray(c.rotors) ? c.rotors.map(r => ({
      id: r.id || '', nom: r.nom || '', enabled: r.enabled !== false,
      host: r.host || '', port: r.port || 4533, offset_deg: r.offset_deg || 0})) : [];
    amplisRows = Array.isArray(c.amplis) ? c.amplis.map(m => ({
      id: m.id || '', nom: m.nom || '', enabled: m.enabled !== false,
      brand: m.brand || '', port: m.port || ''})) : [];
    renderParcStation();
    if(document.getElementById('sota_ai_approval_ack'))
      document.getElementById('sota_ai_approval_ack').checked = c.sota_ai_approval_ack === '1';
    _updateSotaSectionVisibility();
    refreshSotaStatus();
    applyUsageMode();
    if (c.cat_brand) updateCatModelOptions();
    if (c.cat_model && document.getElementById('cat_model')) document.getElementById('cat_model').value = c.cat_model;
    if(c.op_name) document.getElementById('operator_name').value = c.op_name;
    if(c.op_call) document.getElementById('op_call').value = c.op_call;
    if(c.club) document.getElementById('club').value = c.club;
    if(c.email) document.getElementById('email').value = c.email;
    if(c.section) document.getElementById('section_edi').value = c.section;
    if(c.rig_host) document.getElementById('rig_host').value = c.rig_host;
    if(c.rig_port) document.getElementById('rig_port').value = c.rig_port;
    if(c.cat_enabled) document.getElementById('cat_enabled').value = '1';
    // Migration : config antérieure au pilotage natif (rig_enabled=true,
    // cat_mode jamais défini) -> reste en rigctld, PAS de bascule silencieuse
    // vers le natif (qui n'a ni port ni marque configurés chez ces utilisateurs).
    if (c.rig_enabled && c.cat_mode === undefined){
      document.getElementById('cat_enabled').value = '1';
      document.getElementById('cat_mode').value = 'rigctld';
    }
    updateCatModeVisibility();
    updateCat2ModeVisibility();
    if(c.voicekeyer_enabled) document.getElementById('voicekeyer_enabled').value = '1';
    if(c.voicekeyer_ai_enabled && document.getElementById('voicekeyer_ai_enabled'))
      document.getElementById('voicekeyer_ai_enabled').value = '1';
    if(c.voicekeyer_piper_enabled && document.getElementById('voicekeyer_piper_enabled'))
      document.getElementById('voicekeyer_piper_enabled').value = '1';
    // Périphérique/voix TTS : <select> peuplés une fois au chargement de page
    // par loadVoiceKeyerDevices() (liste dépendante du matériel serveur) — on
    // ne fait que ré-appliquer la valeur sauvegardée sur les <option> déjà là.
    if(c.voicekeyer_device !== undefined){
      const devSel = document.getElementById('voicekeyer_device');
      if(devSel) devSel.value = c.voicekeyer_device;
    }
    if(c.voicekeyer_voice_id !== undefined){
      const voiceSel = document.getElementById('voicekeyer_voice_id');
      if(voiceSel) voiceSel.value = c.voicekeyer_voice_id;
    }
    if(c.voicekeyer_device2 !== undefined){
      const devSel2 = document.getElementById('voicekeyer_device2');
      if(devSel2) devSel2.value = c.voicekeyer_device2;
    }
    if(c.amp_enabled) document.getElementById('amp_enabled').value = '1';
    if (c.amp_brand) updateAmpFieldsVisibility();
    if(c.wsjtx_enabled) document.getElementById('wsjtx_enabled').value = '1';
    if(c.wsjtx_port) document.getElementById('wsjtx_port').value = c.wsjtx_port;
    if(c.adifnet_mode) document.getElementById('adifnet_mode').value = c.adifnet_mode;
    if(c.adifnet_port) document.getElementById('adifnet_port').value = c.adifnet_port;
    if(c.adifnet_target) document.getElementById('adifnet_target').value = c.adifnet_target;
    if(c.mqtt_enabled && document.getElementById('mqtt_enabled')) document.getElementById('mqtt_enabled').value = '1';
    if(c.mqtt_host && document.getElementById('mqtt_host')) document.getElementById('mqtt_host').value = c.mqtt_host;
    if(c.mqtt_port && document.getElementById('mqtt_port')) document.getElementById('mqtt_port').value = c.mqtt_port;
    if(c.mqtt_topic_prefix && document.getElementById('mqtt_topic_prefix'))
      document.getElementById('mqtt_topic_prefix').value = c.mqtt_topic_prefix;
    if(c.rotor_enabled) document.getElementById('rotor_enabled').value = '1';
    if(c.rotor_host) document.getElementById('rotor_host').value = c.rotor_host;
    if(c.rotor_port) document.getElementById('rotor_port').value = c.rotor_port;
    // Marque/modèle/protocole : peupler la liste des marques AVANT de poser la
    // valeur (piège connu : poser .value sur un select pas encore rempli
    // échoue en silence), puis les modèles de la marque, puis les valeurs.
    fillRotorBrandSelect();
    if(c.rotor_brand) document.getElementById('rotor_brand').value = c.rotor_brand;
    fillRotorModelSelect(c.rotor_brand || '');
    if(c.rotor_model) document.getElementById('rotor_model').value = c.rotor_model;
    const _rp = document.getElementById('rotor_proto');
    if(_rp) _rp.value = c.rotor_proto || (_rotorBrand(c.rotor_brand) || {}).proto || 'rotctld';
    onRotorModelChange(); onRotorProtoChange();
    if(c.relay_enabled) document.getElementById('relay_enabled').value = '1';
    if(c.relay_auto_band) document.getElementById('relay_auto_band').value = '1';
    updateRelayFieldsVisibility();
    renderRelayButtons();
    renderRelayBandMapRows(c.relay_band_map && typeof c.relay_band_map === 'object' ? c.relay_band_map : {});
    if(c.pgxl_enabled && document.getElementById('pgxl_enabled')) document.getElementById('pgxl_enabled').value = '1';
    if(c.acom_enabled && document.getElementById('acom_enabled')) document.getElementById('acom_enabled').value = '1';
    // telemetry_enabled : SEUL toggle du projet activé par défaut (opt-out) —
    // contrairement au motif "if(c.xxx) ...value='1'" ci-dessus (qui laisse la
    // valeur par défaut du <select> HTML si c.xxx est absent/faux), il faut ici
    // distinguer explicitement les 3 cas : jamais sauvegardé (config antérieure
    // à cette fonctionnalité) -> reste sur "Activée" (valeur par défaut du
    // <select>) ; sauvegardé `true` -> "Activée" ; sauvegardé `false`
    // (l'opérateur a explicitement coupé le toggle) -> "Désactivée", sinon la
    // popup mentirait sur l'état réel après un rechargement de la page.
    if(c.telemetry_enabled === false && document.getElementById('telemetry_enabled'))
      document.getElementById('telemetry_enabled').value = '';
    if(c.contest_start_date) document.getElementById('contest_start_date').value = c.contest_start_date;
    if(c.contest_end_date) document.getElementById('contest_end_date').value = c.contest_end_date;
    if(c.contest_end_utc) document.getElementById('contest_end_utc').value = c.contest_end_utc;
    if(c.power) document.getElementById('power').value = c.power;
    if(c.power_class) document.getElementById('power_class').value = c.power_class;
    if(c.log_software) document.getElementById('log_software').value = c.log_software;
    if(c.ant_hf) document.getElementById('ant_hf').value = c.ant_hf;
    if(c.ant_144) document.getElementById('ant_144').value = c.ant_144;
    if(c.ant_432) document.getElementById('ant_432').value = c.ant_432;
    if(c.ant_shf) document.getElementById('ant_shf').value = c.ant_shf;
    // Correctif : ces 4 champs étaient envoyés par saveConfig() mais jamais
    // restaurés ici (seule l'ancienne applyConfigToForm(), plus jamais
    // exécutée à cause de la redéclaration de fonction plus bas dans ce
    // fichier, les restaurait) — perte silencieuse au rechargement de page.
    if(c.radio) document.getElementById('radio').value = c.radio;
    if(c.country) document.getElementById('country').value = c.country;
    if(c.active_satellite) document.getElementById('active_satellite').value = c.active_satellite;
    if(c.submit_url) document.getElementById('submit_url').value = c.submit_url;
    if(c.submit_deadline) document.getElementById('submit_deadline').value = c.submit_deadline;
    if(c.contest) selectContest(c.contest, true);
    if(c.toggles) {
      // selectContest() vient de réinitialiser state.toggles aux valeurs par
      // défaut du règlement — on restaure ici le choix réellement sauvegardé,
      // à la fois dans le DOM (cases cochées) ET dans state.toggles (mémoire),
      // sinon un save ultérieur réécrirait les valeurs par défaut.
      state.toggles = Object.assign({}, state.toggles, c.toggles);
      Object.entries(c.toggles).forEach(([key, val]) => {
        const el = document.querySelector(`[data-key="${key}"]`);
        if(el) { if(val) el.classList.add('on'); else el.classList.remove('on'); }
      });
      // Correctif [fuite masquage] : c.toggles peut ramener à true une bande/
      // mode qui n'appartient PAS au règlement du concours sélectionné juste
      // au-dessus (selectContest() a déjà masqué/désactivé la bonne sélection
      // via applyContestFilters(), mais cette restauration écrase state.toggles
      // sans jamais retoucher au masquage) — un save ultérieur re-persisterait
      // alors cette valeur malgré le bouton resté visuellement masqué. On
      // reclame donc explicitement à false tout data-key band_/mode_ resté
      // masqué (display:none) après cette restauration.
      document.querySelectorAll('[data-key^="band_"], [data-key^="mode_"]').forEach(el => {
        if(el.style.display === 'none'){
          el.classList.remove('on');
          state.toggles[el.dataset.key] = false;
        }
      });
    }
    if(c.alert_dx_km) document.getElementById('alert_dx_km').value = c.alert_dx_km;
    if(c.spotter_reliable_km) document.getElementById('spotter_reliable_km').value = c.spotter_reliable_km;
    if(c.alert_sound === false) document.getElementById('alert_sound').value = '';
    if(c.alert_volume != null) document.getElementById('alert_volume').value = c.alert_volume;
    if(c.refresh_min) document.getElementById('refresh_min').value = c.refresh_min;
    if(c.priority_mode) document.getElementById('priority_mode').value = c.priority_mode;
    if(c.spot_prefix_filter !== undefined) document.getElementById('spot_prefix_filter').value = c.spot_prefix_filter;
    state.alertRules = Array.isArray(c.alert_rules) ? c.alert_rules : [];
    renderAlertRules();
    if(c.operators && Array.isArray(c.operators) && c.operators.length){
      ensureOperatorRows(c.operators.length); // crée assez de lignes OP2+ avant de les remplir
      c.operators.forEach((op, i) => {
        const callEl = document.getElementById(`op${i+1}_call`);
        const nameEl = document.getElementById(`op${i+1}_name`);
        if(callEl && op.call) callEl.value = op.call;
        if(nameEl && op.name) nameEl.value = op.name;
        // Config sauvegardée avant l'ajout des qualifications (op.modes absent) :
        // repli sur "qualifié partout", jamais une case décochée par surprise.
        const modes = op.modes || {};
        ['ssb','cw','digi'].forEach(m => {
          const el = document.getElementById(`op${i+1}_mode_${m}`);
          if(el) el.checked = modes[m] !== undefined ? !!modes[m] : true;
        });
      });
    } else {
      ensureOperatorRows(1);
    }
    if(c.postes && Array.isArray(c.postes) && c.postes.length){
      ensurePosteRows(c.postes.length);
      c.postes.forEach((name, i) => {
        const el = document.getElementById(`poste${i+1}_name`);
        if(el && name) el.value = name;
      });
    }
    // Recharger fournisseur IA + clé API
    const savedProvider = c.api_provider || localStorage.getItem('logx_ai_provider') || 'anthropic';
    const savedModel    = c.ai_model     || localStorage.getItem('logx_ai_model')    || '';
    const radio = document.querySelector(`input[name="api_provider"][value="${savedProvider}"]`);
    if(radio){ radio.checked = true; }
    onProviderChange(); // met à jour le select modèle et le placeholder
    if(savedModel){
      const sel = document.getElementById('ai_model');
      const opt = sel.querySelector(`option[value="${savedModel}"]`);
      if(opt) sel.value = savedModel;
    }
    // Charger la clé du fournisseur actif
    const keyForProvider = c.api_key || localStorage.getItem(`logx_apikey_${savedProvider}`) || localStorage.getItem('logx_apikey') || '';
    if(keyForProvider) document.getElementById('api_key').value = keyForProvider;
    // Correctif M5 : refléter l'état Activé/Désactivé sur les champs
    // dépendants après restauration (chargement de page ET changement de
    // profil, qui appellent tous deux cette fonction) — sinon un profil
    // désactivant l'ampli/rotor/cloud sync laissait leurs champs enfants
    // pleinement éditables visuellement malgré le select sur Désactivé.
    updateEnabledFieldsVisibility('amp_enabled', ['amp_brand','amp_conn_mode','amp_port','amp_baudrate','amp_civ_addr','amp_host','amp_net_port']);
    updateEnabledFieldsVisibility('rotor_enabled', ['rotor_brand','rotor_model','rotor_proto','rotor_host','rotor_port']);
    updateEnabledFieldsVisibility('cloudsync_mode', ['cloudsync_folder','cloudsync_interval','cloudsync_secret'], v => v !== '');
    updateEnabledFieldsVisibility('mysql_mode', ['mysql_host','mysql_port','mysql_user','mysql_password','mysql_database'], v => v !== 'off');
    updateEnabledFieldsVisibility('mqtt_enabled', ['mqtt_host','mqtt_port','mqtt_topic_prefix']);
    updateEnabledFieldsVisibility('pgxl_enabled', ['pgxl_host','pgxl_port','pgxl_timeout']);
    updateEnabledFieldsVisibility('telemetry_enabled', ['telemetry_endpoint']);
    renderConfigTree(); // Arborescence de réglages : badges après restauration/changement de profil
}

// Pré-remplissage depuis config.json (fallback si localStorage vide)
async function loadFromServerConfig() {
  try {
    const res = await fetch('/config.json');
    if (!res.ok) return;
    const raw = await res.json();
    const st  = raw.station  || {};
    const ct  = raw.contest  || {};
    const api = raw.api      || {};
    const ops = raw.operators || [];

    const set = (id, val) => {
      if (!val && val !== 0) return;
      const el = document.getElementById(id);
      if (el) el.value = val;
    };

    // Station
    set('callsign',       st.callsign);
    set('callsign_contest', st.callsign_portable || st.callsign);
    set('locator',        st.locator);
    set('city',           st.city);
    set('operator_name',  st.operator_name);
    set('op_call',        st.operator_callsign);
    set('email',          st.operator_email);
    set('club',           st.club);
    set('section_edi',    st.section);
    set('power',          st.power_watts);
    set('power_class',    st.power_class);
    set('ant_144',        (st.antennas || {}).vhf_144);
    set('ant_432',        (st.antennas || {}).vhf_432);
    if (st.locator) updateLocatorHint();

    // Concours
    if (ct.id) selectContest(ct.id, true);
    if (ct.start_date) {
      const sd = ct.start_date.toString().replace(/-/g,'');
      set('contest_start_date', `${sd.slice(0,4)}-${sd.slice(4,6)}-${sd.slice(6,8)}`);
    }
    if (ct.end_date) {
      const ed = ct.end_date.toString().replace(/-/g,'');
      set('contest_end_date', `${ed.slice(0,4)}-${ed.slice(4,6)}-${ed.slice(6,8)}`);
    }
    if (ct.end_utc) {
      const t = ct.end_utc.toString().padStart(4,'0');
      set('contest_end_utc', `${t.slice(0,2)}:${t.slice(2,4)}`);
    }

    // Clé API (seulement si ce n'est pas le placeholder)
    const key = api.anthropic_key || '';
    if (key && key !== 'REMPLACE_PAR_TA_CLE') {
      set('api_key', key);
      localStorage.setItem('logx_apikey', key);
    }

    // Opérateurs
    if(ops.length) ensureOperatorRows(ops.length); // crée les lignes OP2+ avant de les remplir
    ops.forEach((op, i) => {
      set(`op${i+1}_call`, op.callsign || op.call || '');
      set(`op${i+1}_name`, op.name || '');
    });

    console.log('[CFG] Pré-rempli depuis config.json');
  } catch(e) {
    console.warn('[CFG] Impossible de charger config.json :', e);
  }
}

function launchApp(dest) {
  if(!saveConfig()) return;
  const key = document.getElementById('api_key').value;
  if(key) localStorage.setItem('logx_apikey', key);
  // Par défaut : le LOGBOOK (la saisie des QSO) — la carte IA reste à un clic.
  window.location.href = dest || 'logx_logbook.html';
}

// ─── PHASE 3 : ANALYSE IA D'UN RÈGLEMENT + RELECTURE HUMAINE ─────────────────
let _aiProposal = null;   // dernière proposition IA (pour le modal)

// ── Partage communautaire : export/import des concours validés ──────────────
async function exportCustomContests(){
  const st = document.getElementById('shareStatus');
  try{
    const res = await fetch('/rules/export_custom');
    const data = await res.json();
    const n = Object.keys(data.contests || {}).length;
    if (!n){ st.innerHTML = '<span style="color:var(--yellow)">Aucun concours validé à exporter.</span>'; return; }
    const blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `logx_concours_${(data.exported_by||'partage').replace(/\W+/g,'')}_${new Date().toISOString().slice(0,10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    st.innerHTML = `<span style="color:var(--green)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><polyline points="3,10 7,14 15,4"/></svg> ${n} concours exportés — envoie le fichier aux autres stations.</span>`;
  }catch(e){ st.innerHTML = `<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> ${e.message}</span>`; }
}

async function importCustomContests(file){
  const st = document.getElementById('shareStatus');
  if (!file) return;
  try{
    const content = JSON.parse(await file.text());
    st.textContent = '⏳ Validation et import...';
    const res = await fetch('/rules/import_custom', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(content),
    });
    const r = await res.json();
    if (!r.ok){ st.innerHTML = `<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> ${r.error}</span>`; return; }
    const parts = [];
    if (r.imported.length) parts.push(`<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><polyline points="3,10 7,14 15,4"/></svg> ${r.imported.length} importé(s) : ${r.imported.join(', ')}`);
    if (r.updated.length) parts.push(`<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><path d="M3.5 9a5.5 5.5 0 0 1 9.3-4"/><polyline points="12.5,2 12.8,5 9.8,5.3"/><path d="M14.5 9a5.5 5.5 0 0 1-9.3 4"/><polyline points="5.5,16 5.2,13 8.2,12.7"/></svg> ${r.updated.length} mis à jour`);
    if (r.skipped_builtin.length) parts.push(`<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><polyline points="4,4 10,9 4,14"/><line x1="14" y1="4" x2="14" y2="14"/></svg> ${r.skipped_builtin.length} déjà dans la base intégrée`);
    const nbErr = Object.keys(r.errors || {}).length;
    if (nbErr) parts.push(`<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" style="width:14px;height:14px;vertical-align:-2px"><circle cx="9" cy="9" r="6.5"/><line x1="4.5" y1="13.5" x2="13.5" y2="4.5"/></svg> ${nbErr} refusé(s) à la validation (${Object.keys(r.errors).join(', ')})</span>`);
    st.innerHTML = parts.join(' · ') || 'Rien à importer.';
    if (r.imported.length || r.updated.length){
      await mergeServerContests();
      buildContestGrid('');
    }
  }catch(e){ st.innerHTML = `<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> Fichier invalide : ${e.message}</span>`; }
  document.getElementById('importFile').value = '';
}

// ─── BASES D'INDICATIFS EXTERNES (étend logx_callhistory.py — même index
// fusionné que calldb.json, jamais un second système de suggestion) ──────────

async function importMasterScp(file){
  const st = document.getElementById('scpStatus');
  if (!file) return;
  try{
    const text = await file.text();
    st.textContent = '⏳ Import en cours (peut prendre quelques secondes)...';
    const res = await fetch('/callhistory/import_scp', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text}),
    });
    const r = await res.json();
    if (!r.ok){ st.innerHTML = `<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> ${r.error}</span>`; return; }
    st.innerHTML = `<span style="color:var(--green)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><polyline points="3,10 7,14 15,4"/></svg> ${r.imported} indicatif(s) lus, `
      + `${r.added} nouveau(x) — ${r.total} au total</span>`;
    refreshCallHistoryStatus();
  }catch(e){ st.innerHTML = `<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> Fichier invalide : ${e.message}</span>`; }
  document.getElementById('scpFile').value = '';
}

// Même fichier que le bouton d'import manuel ci-dessus, mais récupéré tout
// seul depuis la source publique de référence (supercheckpartial.com) —
// pas besoin de le télécharger et le sélectionner à la main.
async function updateMasterScpFromInternet(){
  const st = document.getElementById('scpStatus');
  st.textContent = '⏳ Téléchargement depuis supercheckpartial.com...';
  st.style.color = 'var(--muted)';
  try{
    const res = await fetch('/callhistory/update_scp', {method: 'POST'});
    const r = await res.json();
    if (!r.ok){ st.innerHTML = `<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> ${r.error}</span>`; return; }
    st.innerHTML = `<span style="color:var(--green)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><polyline points="3,10 7,14 15,4"/></svg> ${r.imported} indicatif(s) lus, `
      + `${r.added} nouveau(x) — ${r.total} au total</span>`;
    refreshCallHistoryStatus();
  }catch(e){ st.innerHTML = `<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> Serveur injoignable : ${e.message}</span>`; }
}

async function importCallHistoryN1mm(file){
  const st = document.getElementById('callHistoryStatus');
  if (!file) return;
  if (!state.contest){
    st.innerHTML = '<span style="color:var(--yellow)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><path d="M9 2.5 16 15H2z"/><line x1="9" y1="7" x2="9" y2="10.5"/><circle cx="9" cy="12.8" r="0.9" fill="currentColor" stroke="none"/></svg> Choisis d\'abord un concours ci-dessus '
      + '(le Call History lui est propre).</span>';
    document.getElementById('callHistoryFile').value = '';
    return;
  }
  try{
    const text = await file.text();
    st.textContent = '⏳ Import en cours...';
    const res = await fetch('/callhistory/import_n1mm', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text, contest: state.contest}),
    });
    const r = await res.json();
    if (!r.ok){ st.innerHTML = `<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> ${r.error}</span>`; return; }
    let msg = `<span style="color:var(--green)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><polyline points="3,10 7,14 15,4"/></svg> ${r.imported} fiche(s) importée(s) pour `
      + `${escC(state.contest)} — ${r.total_for_contest} au total</span>`;
    if (r.errors && r.errors.length) msg += ` · <span style="color:var(--yellow)">${r.errors.length} ligne(s) ignorée(s)</span>`;
    st.innerHTML = msg;
    refreshCallHistoryStatus();
  }catch(e){ st.innerHTML = `<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> Fichier invalide : ${e.message}</span>`; }
  document.getElementById('callHistoryFile').value = '';
}

// Rappel de l'état déjà importé — appelé au chargement de la page, après
// chaque import, ET après un changement de concours (selectContest/
// deselectContest : voir plus loin). ?contest= transmet le concours EN COURS
// DE SÉLECTION côté client (state.contest), qui peut différer de celui
// sauvegardé côté serveur tant que « Enregistrer » n'a pas été cliqué —
// sans lui, changer de concours affichait le compteur du PRÉCÉDENT concours
// jusqu'à la sauvegarde (correctif : selectContest() ne rafraîchissait
// jamais ce statut).
async function refreshCallHistoryStatus(){
  try{
    const qs = state.contest ? ('?contest=' + encodeURIComponent(state.contest)) : '';
    const r = await (await fetch('/callhistory/status' + qs)).json();
    const scpEl = document.getElementById('scpStatus');
    if (scpEl && !scpEl.innerHTML) {
      scpEl.textContent = r.master_scp_count
        ? `${r.master_scp_count} indicatif(s) déjà importés.` : '';
    }
    const chEl = document.getElementById('callHistoryStatus');
    // Rafraîchit si vide OU si le concours affiché a changé depuis le
    // dernier rendu (chEl.dataset.contest) — sinon un changement de concours
    // laissait le compteur du PRÉCÉDENT concours affiché indéfiniment. Ne
    // touche pas à l'affichage si le concours n'a pas bougé : préserve le
    // message de succès qu'un import vient de poser juste avant cet appel.
    if (chEl && (!chEl.innerHTML || chEl.dataset.contest !== (r.contest || ''))) {
      chEl.textContent = r.contest && r.call_history_count
        ? `${r.call_history_count} fiche(s) déjà importées pour ${r.contest}.`
        : (r.contest ? '' : 'Choisis un concours pour voir/importer son Call History.');
      chEl.dataset.contest = r.contest || '';
    }
  }catch(e){ /* hors ligne : silencieux, comme les autres statuts */ }
}
window.addEventListener('load', refreshCallHistoryStatus);

// "Score à battre" : meilleur QSO count / meilleur score déjà réalisés pour
// CE concours parmi les éditions archivées (archives/ permanentes, cf.
// logx_archive.py) -- ne se déclenche qu'à la sélection d'un concours
// (appelé depuis selectContest()/deselectContest() ci-dessous), jamais au
// chargement de page seul (state.contest peut être vide).
async function refreshContestBestScore(id){
  const el = document.getElementById('contest_best_score');
  if (!el) return;
  if (!id) { el.style.display = 'none'; el.innerHTML = ''; return; }
  try{
    const r = await (await fetch('/log/archives/best?contest=' + encodeURIComponent(id))).json();
    if (!r || !r.ok) { el.style.display = 'none'; el.innerHTML = ''; return; }
    const qsoYear = r.best_qso_year ? ` (${r.best_qso_year})` : '';
    const ptsYear = r.best_points_year ? ` (${r.best_points_year})` : '';
    const edText = r.editions > 1 ? `${r.editions} éditions archivées` : '1 édition archivée';
    el.innerHTML = `<svg viewBox="0 0 18 18" width="13" height="13" style="vertical-align:-2px;flex-shrink:0" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11.5v3M6 14.5h6M5 2.5h8l-.6 5.2a3.4 3.4 0 0 1-6.8 0L5 2.5z"/><path d="M5 4H2.8A1.3 1.3 0 0 0 2 6.3 3 3 0 0 0 5 9M13 4h2.2A1.3 1.3 0 0 1 16 6.3 3 3 0 0 1 13 9"/></svg> `
      + `<strong>Score à battre</strong> pour ${escC(id)} (${edText}) — `
      + `Meilleur nombre de QSO : <strong>${r.best_qso}</strong>${qsoYear} · `
      + `Meilleur score : <strong>${r.best_points}</strong> pts${ptsYear}`;
    el.style.display = 'block';
  }catch(e){ el.style.display = 'none'; el.innerHTML = ''; }
}

async function analyzeRules(url, name){
  url  = url  || document.getElementById('aiRulesUrl').value.trim();
  name = name || document.getElementById('aiRulesName').value.trim();
  const status = document.getElementById('aiAnalyzeStatus');
  const btn = document.getElementById('aiAnalyzeBtn');
  if (!url){ _configToast(T('Indique l\'URL du règlement (PDF ou page web).')); return; }
  // Correctif M1 : mémorise le concours actif au lancement de l'analyse — si
  // l'utilisateur en choisit un autre pendant les 30-90s d'analyse IA,
  // saveReviewedDefinition() doit le savoir pour ne pas écraser silencieusement
  // cette sélection manuelle en validant la proposition IA.
  const contestAtLaunch = state.contest;
  // La clé API vit dans la config : la pousser au serveur avant l'analyse
  quickSave();
  status.style.display = 'block';
  status.textContent = '⏳ Téléchargement du règlement + analyse IA en cours (30-90 s)...';
  btn.disabled = true;
  try{
    const res = await fetch('/rules/analyze', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({url, name}),
    });
    const data = await res.json();
    if (!data.ok){
      status.innerHTML = `<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> <span style="color:var(--red)">${data.error || 'Analyse en échec'}</span>`;
      return;
    }
    status.textContent = `✅ Règlement lu (${data.text_chars} caractères via ${data.extractor}) — relis la proposition ci-dessous.`;
    _aiProposal = {...data, source_url: url, _contestAtLaunch: contestAtLaunch};
    openReviewModal(_aiProposal);
  }catch(e){
    status.innerHTML = `<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> <span style="color:var(--red)">Serveur injoignable : ${e.message}</span>`;
  }finally{
    btn.disabled = false;
  }
}

function _revField(id, label, value, citation, placeholder=''){
  const cite = citation
    ? `<div style="font-family:var(--font-mono);font-size:12px;color:var(--muted);margin-top:3px;border-left:2px solid var(--border);padding-left:8px"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><path d="M9 4.5c-1.3-1-3.2-1.3-5.5-1v10c2.3-.3 4.2 0 5.5 1 1.3-1 3.2-1.3 5.5-1v-10c-2.3-.3-4.2 0-5.5 1z"/><line x1="9" y1="4.5" x2="9" y2="14.5"/></svg> « ${String(citation).replace(/</g,'&lt;')} »</div>`
    : `<div style="font-family:var(--font-mono);font-size:12px;color:var(--yellow);margin-top:3px"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><path d="M9 2.5 16 15H2z"/><line x1="9" y1="7" x2="9" y2="10.5"/><circle cx="9" cy="12.8" r="0.9" fill="currentColor" stroke="none"/></svg> aucune citation source — vérifie dans le règlement</div>`;
  return `<div style="margin-bottom:12px">
    <label style="font-family:var(--font-mono);font-size:12px;letter-spacing:2px;color:var(--muted)">${label}</label>
    <input type="text" id="rev_${id}" value="${String(value ?? '').replace(/"/g,'&quot;')}" placeholder="${placeholder}"
      style="width:100%;background:var(--bg3);border:1px solid var(--border);border-radius:6px;color:var(--text);font-family:var(--font-mono);font-size:14px;padding:8px 10px;outline:none;margin-top:3px">
    ${cite}
  </div>`;
}

function _verificationBlock(v){
  if (!v) return '';
  const esc = s => String(s ?? '').replace(/</g, '&lt;');
  if (v.error){
    return `<div style="background:rgba(255,214,10,.07);border:1px solid rgba(255,214,10,.4);border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:14px;color:var(--yellow)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><path d="M9 2.5 16 15H2z"/><line x1="9" y1="7" x2="9" y2="10.5"/><circle cx="9" cy="12.8" r="0.9" fill="currentColor" stroke="none"/></svg> ${esc(v.error)} — la définition n'a eu qu'une seule passe, relis avec plus d'attention.</div>`;
  }
  const nOk = (v.answers || []).length - (v.issues || []).length;
  if (!(v.issues || []).length){
    return `<div style="background:rgba(0,255,136,.06);border:1px solid rgba(0,255,136,.35);border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:14px;color:var(--green)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><circle cx="8" cy="8" r="5"/><line x1="12" y1="12" x2="16" y2="16"/></svg> <strong>Passe de vérification : ${nOk}/${(v.answers||[]).length} points de contrôle conformes</strong> (restrictions participants, off-time, mults pondérés, QTC, échange, dates, deadline).</div>`;
  }
  const items = v.issues.map(i =>
    `<li style="margin-bottom:6px"><strong>${esc(i.question)}</strong><br>
     <span style="color:var(--text)">${esc(i.reponse)}</span>
     ${i.probleme ? `<br><span style="color:var(--red)">→ ${esc(i.probleme)}</span>` : ''}</li>`).join('');
  return `<div style="background:rgba(var(--accent-rgb),.06);border:1px solid rgba(var(--accent-rgb),.35);border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:14px;color:var(--accent2)">
    <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><circle cx="8" cy="8" r="5"/><line x1="12" y1="12" x2="16" y2="16"/></svg> <strong>Passe de vérification : ${v.issues.length} point(s) corrigé(s) ou à surveiller</strong>
    ${v.applied ? ' — <span style="color:var(--green)">corrections appliquées à la définition ci-dessous</span>' : ' — <span style="color:var(--yellow)">corrections NON appliquées, vérifie manuellement</span>'}
    <ul style="margin:8px 0 0 18px">${items}</ul>
  </div>`;
}

function openReviewModal(p){
  const d = p.definition || {};
  const c = p.citations || {};
  const warnings = (p.warnings || []).map(w => `<li>${String(w).replace(/</g,'&lt;')}</li>`).join('');
  const verrs = (p.validation_errors || []).map(e => `<li>${String(e).replace(/</g,'&lt;')}</li>`).join('');
  const confColor = {high: 'var(--green)', medium: 'var(--yellow)', low: 'var(--red)'}[p.confidence] || 'var(--muted)';

  document.getElementById('reviewModalBody').innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px">
      <div>
        <div style="font-family:var(--font-mono);font-size:15px;letter-spacing:2px;color:var(--accent2)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px;vertical-align:-3px"><rect x="3.5" y="6.5" width="11" height="8" rx="1.5"/><line x1="9" y1="6.5" x2="9" y2="3.5"/><circle cx="9" cy="2.5" r="1" fill="currentColor" stroke="none"/><circle cx="6.5" cy="10.5" r="1" fill="currentColor" stroke="none"/><circle cx="11.5" cy="10.5" r="1" fill="currentColor" stroke="none"/><line x1="6" y1="14.5" x2="6" y2="16"/><line x1="12" y1="14.5" x2="12" y2="16"/></svg> PROPOSITION IA — RELECTURE OBLIGATOIRE</div>
        <div style="font-family:var(--font-mono);font-size:12px;color:var(--muted);margin-top:4px">
          Rien n'est enregistré tant que tu n'as pas validé. Confiance IA :
          <span style="color:${confColor};font-weight:700">${String(p.confidence || '?').replace(/</g,'&lt;').toUpperCase()}</span>
          · Extraction : ${String(p.extractor||'').replace(/</g,'&lt;')} (${p.text_chars} car.)
        </div>
      </div>
      <button onclick="document.getElementById('reviewModal').style.display='none'"
        style="background:none;border:none;color:var(--muted);cursor:pointer;font-size:20px"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:16px;height:16px;vertical-align:-3px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg></button>
    </div>

    ${verrs ? `<div style="background:rgba(255,45,85,.08);border:1px solid var(--red);border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:14px;color:var(--red)"><strong><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" style="width:14px;height:14px;vertical-align:-2px"><circle cx="9" cy="9" r="6.5"/><line x1="4.5" y1="13.5" x2="13.5" y2="4.5"/></svg> Erreurs de validation à corriger avant enregistrement :</strong><ul style="margin:6px 0 0 18px">${verrs}</ul></div>` : ''}
    ${_verificationBlock(p.verification)}
    ${warnings ? `<div style="background:rgba(255,214,10,.07);border:1px solid rgba(255,214,10,.4);border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:14px;color:var(--yellow)"><strong><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><path d="M9 2.5 16 15H2z"/><line x1="9" y1="7" x2="9" y2="10.5"/><circle cx="9" cy="12.8" r="0.9" fill="currentColor" stroke="none"/></svg> Signalé par l'IA :</strong><ul style="margin:6px 0 0 18px">${warnings}</ul></div>` : ''}

    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 18px">
      ${_revField('id', 'ID DU CONCOURS', p.suggested_id, null, 'WAEDC_CW')}
      ${_revField('name', 'NOM', d.name, c.name)}
      ${_revField('organizer', 'ORGANISATEUR', d.organizer, c.organizer)}
      ${_revField('date_rule', 'RÈGLE DE DATE', d.date_rule, c.date_rule, 'first_saturday_july')}
      ${_revField('duration_h', 'DURÉE (H)', d.duration_h, c.duration_h)}
      ${_revField('start_utc', 'DÉBUT UTC (HH:MM)', d.start_utc, c.start_utc)}
      ${_revField('bands', 'BANDES (MHz, virgules)', (d.bands || []).join(','), c.bands)}
      ${_revField('modes', 'MODES (virgules)', (d.modes || []).join(','), c.modes)}
      ${_revField('exchange', 'ÉCHANGE', d.exchange, c.exchange)}
      ${_revField('log_format', 'FORMAT LOG (EDI/CABRILLO/ADIF)', d.log_format, c.log_format)}
      ${_revField('log_deadline', 'DEADLINE LOG', d.log_deadline, c.log_deadline)}
      ${_revField('log_submit', 'SOUMISSION LOG (URL/email)', d.log_submit, c.log_submit)}
    </div>
    ${p.date_preview ? `<div style="font-family:var(--font-mono);font-size:13px;color:var(--green);margin-bottom:10px"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><rect x="2.5" y="3.5" width="13" height="11.5" rx="1.5"/><line x1="2.5" y1="7.5" x2="15.5" y2="7.5"/><line x1="6" y1="1.5" x2="6" y2="4.5"/><line x1="12" y1="1.5" x2="12" y2="4.5"/></svg> Prochaine occurrence calculée depuis la règle : <strong>${p.date_preview}</strong></div>` : ''}
    ${_revField('notes', 'NOTES / PARTICULARITÉS', d.notes, c.notes)}

    <div style="margin-bottom:12px">
      <label style="font-family:var(--font-mono);font-size:12px;letter-spacing:2px;color:var(--muted)">SCORING (JSON — type historique ou briques)</label>
      <textarea id="rev_scoring" style="width:100%;height:130px;background:var(--bg3);border:1px solid var(--border);border-radius:6px;color:var(--text);font-family:var(--font-mono);font-size:13px;padding:10px;outline:none;margin-top:3px;resize:vertical">${JSON.stringify(d.scoring || {}, null, 2).replace(/</g,'&lt;')}</textarea>
      ${c.scoring ? `<div style="font-family:var(--font-mono);font-size:12px;color:var(--muted);margin-top:3px;border-left:2px solid var(--border);padding-left:8px"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><path d="M9 4.5c-1.3-1-3.2-1.3-5.5-1v10c2.3-.3 4.2 0 5.5 1 1.3-1 3.2-1.3 5.5-1v-10c-2.3-.3-4.2 0-5.5 1z"/><line x1="9" y1="4.5" x2="9" y2="14.5"/></svg> « ${String(c.scoring).replace(/</g,'&lt;')} »</div>` : ''}
    </div>

    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:16px">
      <button class="btn btn-launch" style="padding:11px 24px" onclick="saveReviewedDefinition()"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><polyline points="3,10 7,14 15,4"/></svg> J'AI RELU — ENREGISTRER LE CONCOURS</button>
      <button class="btn btn-secondary" style="padding:11px 18px" onclick="document.getElementById('reviewModal').style.display='none'"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> Annuler</button>
      ${p.source_url ? `<a class="btn btn-secondary" style="padding:11px 18px;text-decoration:none" href="${p.source_url}" target="_blank"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><path d="M4.5 2.5h6l3 3v10h-9z"/><polyline points="10.5,2.5 10.5,5.5 13.5,5.5"/><line x1="6.5" y1="9.5" x2="11.5" y2="9.5"/><line x1="6.5" y1="12" x2="11.5" y2="12"/></svg> Ouvrir le règlement</a>` : ''}
    </div>
    <div id="reviewSaveStatus" style="margin-top:10px;font-family:var(--font-mono);font-size:13px"></div>`;
  document.getElementById('reviewModal').style.display = 'block';
}

async function saveReviewedDefinition(){
  const g = id => document.getElementById('rev_' + id)?.value.trim() ?? '';
  const status = document.getElementById('reviewSaveStatus');
  let scoring;
  try{ scoring = JSON.parse(document.getElementById('rev_scoring').value); }
  catch(e){ status.innerHTML = `<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" style="width:14px;height:14px;vertical-align:-2px"><circle cx="9" cy="9" r="6.5"/><line x1="4.5" y1="13.5" x2="13.5" y2="4.5"/></svg> Scoring : JSON invalide (${e.message})</span>`; return; }

  const definition = {
    name: g('name'), organizer: g('organizer'), date_rule: g('date_rule'),
    bands: g('bands').split(',').map(s=>s.trim()).filter(Boolean),
    modes: g('modes').split(',').map(s=>s.trim()).filter(Boolean),
    exchange: g('exchange'), scoring, log_format: g('log_format').toUpperCase(),
  };
  // Champs optionnels : n'inclure que s'ils sont renseignés
  if (g('duration_h')) definition.duration_h = parseInt(g('duration_h'), 10);
  if (g('start_utc')) definition.start_utc = g('start_utc');
  if (g('log_deadline')) definition.log_deadline = g('log_deadline');
  if (g('log_submit')) definition.log_submit = g('log_submit');
  if (g('notes')) definition.notes = g('notes');
  if (_aiProposal?.source_url) definition.rules_url = _aiProposal.source_url;

  status.textContent = '⏳ Validation + enregistrement...';
  try{
    const res = await fetch('/rules/save_definition', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id: g('id'), definition,
                            source_url: _aiProposal?.source_url || '',
                            confidence: _aiProposal?.confidence || ''}),
    });
    const data = await res.json();
    if (!data.ok){
      const errs = (data.validation_errors || [data.error]).map(e => String(e).replace(/</g,'&lt;')).join('<br>· ');
      status.innerHTML = `<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" style="width:14px;height:14px;vertical-align:-2px"><circle cx="9" cy="9" r="6.5"/><line x1="4.5" y1="13.5" x2="13.5" y2="4.5"/></svg> ${errs}</span>`;
      return;
    }
    status.innerHTML = `<span style="color:var(--green)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><polyline points="3,10 7,14 15,4"/></svg> ${data.message} — il apparaît maintenant dans la liste.</span>`;
    // Rafraîchir la grille et sélectionner le nouveau concours
    await mergeServerContests();
    buildContestGrid('');
    setTimeout(() => {
      document.getElementById('reviewModal').style.display = 'none';
      // Correctif M1 : ne sauter la confirmation H3 que si le concours actif
      // n'a PAS changé depuis le lancement de l'analyse IA — sinon l'utilisateur
      // a fait un choix manuel entretemps (30-90s d'analyse + relecture) qu'il
      // ne faut pas écraser en silence.
      const contestUnchanged = !_aiProposal || _aiProposal._contestAtLaunch === state.contest;
      selectContest(g('id'), contestUnchanged);
      const card = document.getElementById('card_' + g('id'));
      if (card) card.scrollIntoView({behavior: 'smooth', block: 'center'});
    }, 1200);
  }catch(e){
    status.innerHTML = `<span style="color:var(--red)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" style="width:14px;height:14px;vertical-align:-2px"><circle cx="9" cy="9" r="6.5"/><line x1="4.5" y1="13.5" x2="13.5" y2="4.5"/></svg> Serveur : ${e.message}</span>`;
  }
}

// ─── ASSISTANT "NOUVEAU CONCOURS" ────────────────────────────────────────────
// Arrivée depuis logx_calendrier.html avec ?contest=ID :
//   1. le concours est sélectionné et ses bandes/modes/dates appliqués ;
//   2. la bannière récapitule ce qui a été pré-rempli et ce qui reste à vérifier ;
//   3. un clic sur LANCER sauvegarde et ouvre la carte IA.
async function handleContestParam(){
  const id = new URLSearchParams(location.search).get('contest');
  if (!id) return;
  const banner = document.getElementById('assistantBanner');
  const contest = CONTESTS.find(c => c.id === id);

  // Arriver ici depuis le calendrier avec un concours précis = intention
  // explicite de faire un concours : basculer hors du mode LOGBOOK SIMPLE
  // pour que l'étape CONCOURS (masquée dans ce mode) redevienne accessible.
  const usageSel = document.getElementById('usage_mode');
  if (usageSel && usageSel.value === 'simple'){
    usageSel.value = 'contest';
    applyUsageMode();
  }

  // #assistantBanner vit DANS le panneau catmodal_contest, masqué par défaut
  // — sans ouverture explicite du panneau, tout ce qui suit (bannière
  // récapitulative comme message « introuvable ») serait rempli mais invisible.
  await openCategoryPopup('contest');

  if (!contest){
    banner.style.display = 'block';
    banner.style.borderColor = 'rgba(255,214,10,.4)';
    // Défense en profondeur (id vient de location.search, entièrement
    // contrôlé par quiconque forge le lien) : escC() neutralise tout HTML/JS,
    // slice() borne la longueur affichée dans la bannière.
    banner.innerHTML = `<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><path d="M9 2.5 16 15H2z"/><line x1="9" y1="7" x2="9" y2="10.5"/><circle cx="9" cy="12.8" r="0.9" fill="currentColor" stroke="none"/></svg> <strong>Concours « ${escC(id).slice(0, 120)} » introuvable dans la liste.</strong><br>
      <span style="font-size:14px;color:var(--muted)">Si c'est un concours WA7BNM, le cache externe est peut-être vide — recharge le calendrier, ou choisis un concours ci-dessous.</span>`;
    return;
  }

  selectContest(id, true);
  const card = document.getElementById('card_' + id);
  if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' });

  const cfg = JSON.parse(localStorage.getItem('logx_config') || '{}');
  const stationOk = !!(cfg.callsign && cfg.locator);
  // Dates OK seulement si elles ont été calculées pour CE concours —
  // un champ non vide peut contenir les dates d'une config précédente
  const datesOk = state.datesAutoFor === id && !!document.getElementById('contest_start_date').value;
  const isExternal = !!contest.external;

  // Les contrôles de la bannière ci-dessous pointent vers les entrées de
  // l'arborescence de réglages (openCategoryPopup() gère lui-même la
  // fermeture de la section actuellement ouverte, garde de modifications non
  // enregistrées comprise — plus besoin de fermer explicitement avant
  // d'ouvrir la cible depuis la refonte sidebar du 08/08/2026, l'ancien
  // risque d'empilement à z-index partagé a disparu avec le hub/popup
  // plein écran).
  // contest.name/contest.rules peuvent venir du flux externe WA7BNM (contenu
  // tiers non maîtrisé, cf. commentaire escC() plus haut dans ce fichier) :
  // escC() les neutralise, safeUrl() bloque tout schéma autre que http/https
  // pour le href, et le lien "fais-le lire par l'IA" passe désormais par des
  // attributs data-* lus en JS plutôt que par interpolation dans une chaîne
  // onclick="...('...')" — supprime tout risque de casser le contexte JS
  // avec un guillemet présent dans contest.rules/contest.name.
  const okIco = '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><polyline points="3,10 7,14 15,4"/></svg>';
  const warnIco = '<svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><path d="M9 2.5 16 15H2z"/><line x1="9" y1="7" x2="9" y2="10.5"/><circle cx="9" cy="12.8" r="0.9" fill="currentColor" stroke="none"/></svg>';
  const checks = [
    `${okIco} Concours sélectionné : <strong>${escC(contest.name)}</strong>`,
    stationOk
      ? `${okIco} Station : <strong>${escC(cfg.callsign)}</strong> en <strong>${escC(cfg.locator)}</strong> (profil sauvegardé)`
      : `${warnIco} Station non configurée — <a href="#" onclick="openCategoryPopup('identity');return false" style="color:var(--accent2)">complète l'étape 1 MA STATION</a>`,
    datesOk
      ? `${okIco} Dates calculées automatiquement : <strong>${document.getElementById('contest_start_date').value}</strong> → <strong>${document.getElementById('contest_end_date').value}</strong>`
      : `${warnIco} Dates non calculables — saisis-les à l'étape 2 (encadré DATES DU CONCOURS)`,
    isExternal
      ? `${warnIco} Concours <strong>non vérifié</strong> (source WA7BNM) — contrôle bandes, modes et échange dans le <a href="${escC(safeUrl(contest.rules))}" target="_blank" rel="noopener noreferrer" style="color:var(--accent2)">règlement officiel</a>${safeUrl(contest.rules) ? ` — ou <a href="#" data-analyze-rules data-rules-url="${escC(contest.rules)}" data-rules-name="${escC(contest.name)}" style="color:var(--green)"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px;vertical-align:-2px"><rect x="3.5" y="6.5" width="11" height="8" rx="1.5"/><line x1="9" y1="6.5" x2="9" y2="3.5"/><circle cx="9" cy="2.5" r="1" fill="currentColor" stroke="none"/><circle cx="6.5" cy="10.5" r="1" fill="currentColor" stroke="none"/><circle cx="11.5" cy="10.5" r="1" fill="currentColor" stroke="none"/><line x1="6" y1="14.5" x2="6" y2="16"/><line x1="12" y1="14.5" x2="12" y2="16"/></svg> fais-le lire par l'IA</a>` : ''}`
      : `${okIco} Bandes et modes du règlement appliqués (modifiables à l'étape 3)`,
  ];

  banner.style.display = 'block';
  banner.innerHTML = `
    <div style="font-family:var(--font-mono);font-size:14px;letter-spacing:2px;color:var(--green);margin-bottom:10px"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px;vertical-align:-3px"><circle cx="9" cy="9" r="6.5"/><polygon points="11,6 10,10 7,12 8,8" fill="currentColor" stroke="none"/></svg> ASSISTANT NOUVEAU CONCOURS</div>
    <div style="font-size:14px;line-height:2">${checks.join('<br>')}</div>
    <div style="display:flex;gap:10px;margin-top:12px;flex-wrap:wrap">
      <button class="btn btn-launch" style="padding:10px 22px" onclick="launchApp()"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px;vertical-align:-3px"><path d="M9 2c2 1.5 3 4 3 7.5L9 12l-3-2.5C6 6 7 3.5 9 2z"/><path d="M6.5 9.5 4 11v3l2.5-1.5"/><path d="M11.5 9.5 14 11v3l-2.5-1.5"/><line x1="8" y1="13.5" x2="9" y2="16"/><line x1="10" y1="13.5" x2="9" y2="16"/></svg> TOUT EST BON — LOGGER</button>
      <button class="btn btn-secondary" style="padding:10px 18px" onclick="openCategoryPopup('filters')">Vérifier bandes/modes →</button>
      <button class="btn btn-secondary" style="padding:10px 18px" onclick="document.getElementById('assistantBanner').style.display='none'"><svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:-2px"><line x1="4" y1="4" x2="14" y2="14"/><line x1="14" y1="4" x2="4" y2="14"/></svg> Fermer l'assistant</button>
    </div>`;
  const aiLink = banner.querySelector('[data-analyze-rules]');
  if (aiLink) aiLink.addEventListener('click', e => {
    e.preventDefault();
    analyzeRules(aiLink.dataset.rulesUrl, aiLink.dataset.rulesName);
  });
}

// Correctif B5 : init() n'est jamais attendue (fire-and-forget, pour ne pas
// bloquer l'interactivité de la page pendant le chargement) — mais
// askAssistant() (autre <script>, voir plus haut) lit #api_key AVANT que
// loadFromServerConfig() (async, appelée seulement si aucune config locale)
// ait fini, et concluait à tort à l'absence de clé API. _initReady expose
// la promesse pour que l'assistant puisse l'attendre sans retarder init()
// elle-même ni le reste de la page.
const _initReady = init();
