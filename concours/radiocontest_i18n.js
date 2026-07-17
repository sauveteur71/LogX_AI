/* ─────────────────────────────────────────────────────────────────────────────
   RadioContest AI — Internationalisation (i18n)
   Traduction de l'interface par CORRESPONDANCE du texte source français :
   pas besoin de baliser chaque élément, le moteur parcourt les nœuds de texte,
   les attributs title/placeholder et les valeurs de boutons, et remplace ce
   qui figure dans le dictionnaire T. Le français reste la source de vérité.

   Langues traduites à la main (jargon radioamateur respecté). Pour toute AUTRE
   langue, l'option « 🌐 Auto (navigateur) » balise la page (lang=fr) pour que
   le navigateur propose sa propre traduction.

   Inclusion : <script src="radiocontest_i18n.js"></script> sur chaque page.
   ──────────────────────────────────────────────────────────────────────────── */
(function () {
  'use strict';

  // Langues proposées (l'ordre = ordre du menu). 'auto' = traduction navigateur.
  const LANGS = [
    { code: 'fr', label: '🇫🇷 Français' },
    { code: 'en', label: '🇬🇧 English' },
    { code: 'de', label: '🇩🇪 Deutsch' },
    { code: 'es', label: '🇪🇸 Español' },
    { code: 'it', label: '🇮🇹 Italiano' },
    { code: 'pt', label: '🇵🇹 Português' },
    { code: 'nl', label: '🇳🇱 Nederlands' },
    { code: 'pl', label: '🇵🇱 Polski' },
    { code: 'auto', label: '🌐 Autre (navigateur)' },
  ];

  // Dictionnaire : T[langue][texte_français] = traduction.
  // Couvre le châssis visible (navigation, en-têtes, boutons, libellés clés).
  const T = {
    en: {
      // Navigation
      'CONFIG': 'CONFIG', 'LOGBOOK': 'LOGBOOK', 'CARTE IA': 'AI MAP',
      'PROPAG': 'PROPAG', 'DÉPARTEMENTS': 'DEPARTMENTS', 'CALENDRIER': 'CALENDAR',
      // Logbook — colonnes / libellés
      'SAISIE QSO': 'QSO ENTRY', 'OPÉRATEUR': 'OPERATOR', 'BANDE': 'BAND',
      'MODE': 'MODE', 'INDICATIF CORRESPONDANT': 'CALLSIGN', 'RST ENVOYÉ': 'RST SENT',
      'RST REÇU': 'RST RCVD', 'N° ENVOYÉ': 'NR SENT', 'N° REÇU': 'NR RCVD',
      'LOCATOR': 'LOCATOR', 'SCORE TOTAL': 'TOTAL SCORE', 'QSO TOTAL': 'TOTAL QSO',
      'MEILLEUR DX': 'BEST DX', 'LOCATORS UNIQUES': 'UNIQUE LOCATORS',
      'DOUBLONS': 'DUPES', 'TEMPS RESTANT': 'TIME LEFT', 'DERNIER QSO': 'LAST QSO',
      'HEURE UTC': 'UTC TIME', 'INDICATIF': 'CALLSIGN', 'ENVOYÉ': 'SENT',
      'REÇU': 'RCVD', 'DIST / CAP': 'DIST / BRG', 'PTS': 'PTS', 'OP': 'OP',
      // Boutons / actions
      'IMPORTER': 'IMPORT', 'NOUVEAU LOG': 'NEW LOG', 'ARCHIVER': 'ARCHIVE',
      'STATS': 'STATS', 'CHECKLIST': 'CHECKLIST', 'COPIER': 'COPY',
      'RE-VÉRIFIER': 'RE-CHECK', 'DÉMARRER': 'START', 'PRÉPARER': 'PREPARE',
      'Règlement': 'Rules', 'CONNECTÉ AU SERVEUR': 'CONNECTED TO SERVER',
      'Connecté au serveur': 'Connected to server', 'Postes connectés :': 'Connected stations:',
      'Serveur :': 'Server:', 'Autres postes (même WiFi) :': 'Other stations (same WiFi):',
      // Propagation
      'SOLEIL & IONOSPHÈRE': 'SUN & IONOSPHERE', 'CONDITIONS PAR BANDE': 'BAND CONDITIONS',
      'BALISES NCDXF/IBP': 'NCDXF/IBP BEACONS', 'OÙ MON SIGNAL EST ENTENDU — PSK REPORTER': 'WHERE I AM HEARD — PSK REPORTER',
      'CLUSTER TRIÉ PAR INTÉRÊT — NEED LIST': 'CLUSTER SORTED BY VALUE — NEED LIST',
      'TOUS': 'ALL', 'NOUVEAUX MULTS': 'NEW MULTS', 'SANS DOUBLONS': 'NO DUPES',
      // Calendrier
      'À VENIR (31 j)': 'UPCOMING (31 d)', 'VÉRIFIER LES RÈGLEMENTS': 'CHECK RULES',
      'MONDIAL WA7BNM': 'WORLDWIDE WA7BNM',
      // Départements
      'Départements REF': 'REF Departments', 'TABLEAU DE CHASSE': 'HUNTING TABLE',
      'OUTRE-MER': 'OVERSEAS', 'Contacté': 'Worked', 'À faire': 'To do',
      // Config
      'IDENTITÉ DE LA STATION': 'STATION IDENTITY', 'COMMENCER À LOGGER': 'START LOGGING',
      'PARAMÈTRES D\'ALERTE': 'ALERT SETTINGS', 'VILLE / QTH': 'CITY / QTH',
      'LOCATOR MAIDENHEAD': 'MAIDENHEAD LOCATOR',
    },
    de: {
      'CONFIG': 'KONFIG', 'LOGBOOK': 'LOGBUCH', 'CARTE IA': 'KI-KARTE',
      'PROPAG': 'AUSBREITUNG', 'DÉPARTEMENTS': 'DEPARTEMENTS', 'CALENDRIER': 'KALENDER',
      'SAISIE QSO': 'QSO-EINGABE', 'OPÉRATEUR': 'OPERATOR', 'BANDE': 'BAND',
      'MODE': 'MODUS', 'INDICATIF CORRESPONDANT': 'RUFZEICHEN', 'RST ENVOYÉ': 'RST GEGEBEN',
      'RST REÇU': 'RST ERHALTEN', 'N° ENVOYÉ': 'NR GEGEBEN', 'N° REÇU': 'NR ERHALTEN',
      'LOCATOR': 'LOCATOR', 'SCORE TOTAL': 'GESAMTPUNKTE', 'QSO TOTAL': 'QSO GESAMT',
      'MEILLEUR DX': 'BESTES DX', 'LOCATORS UNIQUES': 'LOCATOREN', 'DOUBLONS': 'DUPES',
      'TEMPS RESTANT': 'RESTZEIT', 'DERNIER QSO': 'LETZTES QSO', 'HEURE UTC': 'UTC-ZEIT',
      'INDICATIF': 'RUFZEICHEN', 'ENVOYÉ': 'GEGEBEN', 'REÇU': 'ERHALTEN',
      'DIST / CAP': 'DIST / RICHT', 'IMPORTER': 'IMPORTIEREN', 'NOUVEAU LOG': 'NEUES LOG',
      'ARCHIVER': 'ARCHIVIEREN', 'STATS': 'STATISTIK', 'CHECKLIST': 'CHECKLISTE',
      'COPIER': 'KOPIEREN', 'DÉMARRER': 'START', 'PRÉPARER': 'VORBEREITEN',
      'Règlement': 'Regeln', 'Connecté au serveur': 'Mit Server verbunden',
      'Postes connectés :': 'Verbundene Stationen:', 'Serveur :': 'Server:',
      'SOLEIL & IONOSPHÈRE': 'SONNE & IONOSPHÄRE', 'CONDITIONS PAR BANDE': 'BANDBEDINGUNGEN',
      'BALISES NCDXF/IBP': 'NCDXF/IBP-BAKEN', 'TOUS': 'ALLE', 'NOUVEAUX MULTS': 'NEUE MULTIS',
      'SANS DOUBLONS': 'OHNE DUPES', 'À VENIR (31 j)': 'DEMNÄCHST (31 T)',
      'TABLEAU DE CHASSE': 'JAGD-TABELLE', 'OUTRE-MER': 'ÜBERSEE',
      'Contacté': 'Gearbeitet', 'À faire': 'Zu tun', 'COMMENCER À LOGGER': 'LOGGEN STARTEN',
      'IDENTITÉ DE LA STATION': 'STATIONSDATEN', 'VILLE / QTH': 'STADT / QTH',
    },
    es: {
      'CONFIG': 'CONFIG', 'LOGBOOK': 'CUADERNO', 'CARTE IA': 'MAPA IA',
      'PROPAG': 'PROPAG', 'DÉPARTEMENTS': 'DEPARTAMENTOS', 'CALENDRIER': 'CALENDARIO',
      'SAISIE QSO': 'ENTRADA QSO', 'OPÉRATEUR': 'OPERADOR', 'BANDE': 'BANDA',
      'MODE': 'MODO', 'INDICATIF CORRESPONDANT': 'INDICATIVO', 'RST ENVOYÉ': 'RST ENVIADO',
      'RST REÇU': 'RST RECIBIDO', 'N° ENVOYÉ': 'Nº ENVIADO', 'N° REÇU': 'Nº RECIBIDO',
      'LOCATOR': 'LOCALIZADOR', 'SCORE TOTAL': 'PUNTUACIÓN TOTAL', 'QSO TOTAL': 'QSO TOTAL',
      'MEILLEUR DX': 'MEJOR DX', 'DOUBLONS': 'DUPLICADOS', 'TEMPS RESTANT': 'TIEMPO RESTANTE',
      'DERNIER QSO': 'ÚLTIMO QSO', 'HEURE UTC': 'HORA UTC', 'INDICATIF': 'INDICATIVO',
      'ENVOYÉ': 'ENVIADO', 'REÇU': 'RECIBIDO', 'IMPORTER': 'IMPORTAR',
      'NOUVEAU LOG': 'NUEVO LOG', 'ARCHIVER': 'ARCHIVAR', 'STATS': 'ESTADÍSTICAS',
      'CHECKLIST': 'LISTA', 'COPIER': 'COPIAR', 'DÉMARRER': 'INICIAR',
      'PRÉPARER': 'PREPARAR', 'Règlement': 'Reglas', 'Connecté au serveur': 'Conectado al servidor',
      'Postes connectés :': 'Estaciones conectadas:', 'Serveur :': 'Servidor:',
      'SOLEIL & IONOSPHÈRE': 'SOL E IONOSFERA', 'CONDITIONS PAR BANDE': 'CONDICIONES POR BANDA',
      'BALISES NCDXF/IBP': 'BALIZAS NCDXF/IBP', 'TOUS': 'TODOS', 'NOUVEAUX MULTS': 'NUEVOS MULT',
      'SANS DOUBLONS': 'SIN DUPES', 'À VENIR (31 j)': 'PRÓXIMOS (31 d)',
      'TABLEAU DE CHASSE': 'TABLA DE CAZA', 'OUTRE-MER': 'ULTRAMAR',
      'Contacté': 'Contactado', 'À faire': 'Pendiente', 'COMMENCER À LOGGER': 'EMPEZAR A REGISTRAR',
      'IDENTITÉ DE LA STATION': 'IDENTIDAD DE LA ESTACIÓN', 'VILLE / QTH': 'CIUDAD / QTH',
    },
    it: {
      'CONFIG': 'CONFIG', 'LOGBOOK': 'LOGBOOK', 'CARTE IA': 'MAPPA IA',
      'PROPAG': 'PROPAG', 'DÉPARTEMENTS': 'DIPARTIMENTI', 'CALENDRIER': 'CALENDARIO',
      'SAISIE QSO': 'INSERIMENTO QSO', 'OPÉRATEUR': 'OPERATORE', 'BANDE': 'BANDA',
      'MODE': 'MODO', 'INDICATIF CORRESPONDANT': 'NOMINATIVO', 'RST ENVOYÉ': 'RST INVIATO',
      'RST REÇU': 'RST RICEVUTO', 'N° ENVOYÉ': 'N° INVIATO', 'N° REÇU': 'N° RICEVUTO',
      'LOCATOR': 'LOCATORE', 'SCORE TOTAL': 'PUNTEGGIO TOTALE', 'QSO TOTAL': 'QSO TOTALI',
      'MEILLEUR DX': 'MIGLIOR DX', 'DOUBLONS': 'DOPPI', 'TEMPS RESTANT': 'TEMPO RIMASTO',
      'DERNIER QSO': 'ULTIMO QSO', 'HEURE UTC': 'ORA UTC', 'INDICATIF': 'NOMINATIVO',
      'ENVOYÉ': 'INVIATO', 'REÇU': 'RICEVUTO', 'IMPORTER': 'IMPORTA',
      'NOUVEAU LOG': 'NUOVO LOG', 'ARCHIVER': 'ARCHIVIA', 'STATS': 'STATISTICHE',
      'CHECKLIST': 'CHECKLIST', 'COPIER': 'COPIA', 'DÉMARRER': 'AVVIA',
      'PRÉPARER': 'PREPARA', 'Règlement': 'Regole', 'Connecté au serveur': 'Connesso al server',
      'Postes connectés :': 'Stazioni connesse:', 'Serveur :': 'Server:',
      'SOLEIL & IONOSPHÈRE': 'SOLE E IONOSFERA', 'CONDITIONS PAR BANDE': 'CONDIZIONI PER BANDA',
      'BALISES NCDXF/IBP': 'FARI NCDXF/IBP', 'TOUS': 'TUTTI', 'NOUVEAUX MULTS': 'NUOVI MULT',
      'SANS DOUBLONS': 'SENZA DOPPI', 'À VENIR (31 j)': 'PROSSIMI (31 g)',
      'TABLEAU DE CHASSE': 'TABELLA DI CACCIA', 'OUTRE-MER': 'OLTREMARE',
      'Contacté': 'Contattato', 'À faire': 'Da fare', 'COMMENCER À LOGGER': 'INIZIA A REGISTRARE',
      'IDENTITÉ DE LA STATION': 'IDENTITÀ STAZIONE', 'VILLE / QTH': 'CITTÀ / QTH',
    },
    pt: {
      'CONFIG': 'CONFIG', 'LOGBOOK': 'DIÁRIO', 'CARTE IA': 'MAPA IA',
      'PROPAG': 'PROPAG', 'DÉPARTEMENTS': 'DEPARTAMENTOS', 'CALENDRIER': 'CALENDÁRIO',
      'SAISIE QSO': 'ENTRADA QSO', 'OPÉRATEUR': 'OPERADOR', 'BANDE': 'BANDA',
      'MODE': 'MODO', 'INDICATIF CORRESPONDANT': 'INDICATIVO', 'RST ENVOYÉ': 'RST ENVIADO',
      'RST REÇU': 'RST RECEBIDO', 'N° ENVOYÉ': 'Nº ENVIADO', 'N° REÇU': 'Nº RECEBIDO',
      'LOCATOR': 'LOCALIZADOR', 'SCORE TOTAL': 'PONTUAÇÃO TOTAL', 'QSO TOTAL': 'QSO TOTAL',
      'MEILLEUR DX': 'MELHOR DX', 'DOUBLONS': 'DUPLICADOS', 'TEMPS RESTANT': 'TEMPO RESTANTE',
      'DERNIER QSO': 'ÚLTIMO QSO', 'HEURE UTC': 'HORA UTC', 'INDICATIF': 'INDICATIVO',
      'ENVOYÉ': 'ENVIADO', 'REÇU': 'RECEBIDO', 'IMPORTER': 'IMPORTAR',
      'NOUVEAU LOG': 'NOVO LOG', 'ARCHIVER': 'ARQUIVAR', 'STATS': 'ESTATÍSTICAS',
      'CHECKLIST': 'LISTA', 'COPIER': 'COPIAR', 'DÉMARRER': 'INICIAR',
      'PRÉPARER': 'PREPARAR', 'Règlement': 'Regras', 'Connecté au serveur': 'Ligado ao servidor',
      'Postes connectés :': 'Estações ligadas:', 'Serveur :': 'Servidor:',
      'SOLEIL & IONOSPHÈRE': 'SOL E IONOSFERA', 'CONDITIONS PAR BANDE': 'CONDIÇÕES POR BANDA',
      'BALISES NCDXF/IBP': 'BALIZAS NCDXF/IBP', 'TOUS': 'TODOS', 'NOUVEAUX MULTS': 'NOVOS MULT',
      'SANS DOUBLONS': 'SEM DUPES', 'À VENIR (31 j)': 'PRÓXIMOS (31 d)',
      'TABLEAU DE CHASSE': 'TABELA DE CAÇA', 'OUTRE-MER': 'ULTRAMAR',
      'Contacté': 'Contactado', 'À faire': 'A fazer', 'COMMENCER À LOGGER': 'COMEÇAR A REGISTAR',
      'IDENTITÉ DE LA STATION': 'IDENTIDADE DA ESTAÇÃO', 'VILLE / QTH': 'CIDADE / QTH',
    },
    nl: {
      'CONFIG': 'CONFIG', 'LOGBOOK': 'LOGBOEK', 'CARTE IA': 'AI-KAART',
      'PROPAG': 'PROPAG', 'DÉPARTEMENTS': 'DEPARTEMENTEN', 'CALENDRIER': 'KALENDER',
      'SAISIE QSO': 'QSO-INVOER', 'OPÉRATEUR': 'OPERATOR', 'BANDE': 'BAND',
      'MODE': 'MODE', 'INDICATIF CORRESPONDANT': 'ROEPLETTERS', 'RST ENVOYÉ': 'RST GEGEVEN',
      'RST REÇU': 'RST ONTVANGEN', 'N° ENVOYÉ': 'NR GEGEVEN', 'N° REÇU': 'NR ONTVANGEN',
      'LOCATOR': 'LOCATOR', 'SCORE TOTAL': 'TOTAALSCORE', 'QSO TOTAL': 'QSO TOTAAL',
      'MEILLEUR DX': 'BESTE DX', 'DOUBLONS': 'DUPES', 'TEMPS RESTANT': 'RESTTIJD',
      'DERNIER QSO': 'LAATSTE QSO', 'HEURE UTC': 'UTC-TIJD', 'INDICATIF': 'ROEPLETTERS',
      'ENVOYÉ': 'GEGEVEN', 'REÇU': 'ONTVANGEN', 'IMPORTER': 'IMPORTEREN',
      'NOUVEAU LOG': 'NIEUW LOG', 'ARCHIVER': 'ARCHIVEREN', 'STATS': 'STATISTIEK',
      'CHECKLIST': 'CHECKLIST', 'COPIER': 'KOPIËREN', 'DÉMARRER': 'START',
      'PRÉPARER': 'VOORBEREIDEN', 'Règlement': 'Regels', 'Connecté au serveur': 'Verbonden met server',
      'Postes connectés :': 'Verbonden stations:', 'Serveur :': 'Server:',
      'SOLEIL & IONOSPHÈRE': 'ZON & IONOSFEER', 'CONDITIONS PAR BANDE': 'BANDCONDITIES',
      'BALISES NCDXF/IBP': 'NCDXF/IBP-BAKENS', 'TOUS': 'ALLE', 'NOUVEAUX MULTS': 'NIEUWE MULTS',
      'SANS DOUBLONS': 'ZONDER DUPES', 'À VENIR (31 j)': 'BINNENKORT (31 d)',
      'TABLEAU DE CHASSE': 'JACHTTABEL', 'OUTRE-MER': 'OVERZEE',
      'Contacté': 'Gewerkt', 'À faire': 'Te doen', 'COMMENCER À LOGGER': 'BEGIN MET LOGGEN',
      'IDENTITÉ DE LA STATION': 'STATIONGEGEVENS', 'VILLE / QTH': 'STAD / QTH',
    },
    pl: {
      'CONFIG': 'KONFIG', 'LOGBOOK': 'DZIENNIK', 'CARTE IA': 'MAPA AI',
      'PROPAG': 'PROPAG', 'DÉPARTEMENTS': 'DEPARTAMENTY', 'CALENDRIER': 'KALENDARZ',
      'SAISIE QSO': 'WPIS QSO', 'OPÉRATEUR': 'OPERATOR', 'BANDE': 'PASMO',
      'MODE': 'EMISJA', 'INDICATIF CORRESPONDANT': 'ZNAK', 'RST ENVOYÉ': 'RST NADANY',
      'RST REÇU': 'RST ODEBRANY', 'N° ENVOYÉ': 'NR NADANY', 'N° REÇU': 'NR ODEBRANY',
      'LOCATOR': 'LOKATOR', 'SCORE TOTAL': 'WYNIK ŁĄCZNY', 'QSO TOTAL': 'QSO RAZEM',
      'MEILLEUR DX': 'NAJLEPSZY DX', 'DOUBLONS': 'DUPLIKATY', 'TEMPS RESTANT': 'POZOSTAŁY CZAS',
      'DERNIER QSO': 'OSTATNIE QSO', 'HEURE UTC': 'CZAS UTC', 'INDICATIF': 'ZNAK',
      'ENVOYÉ': 'NADANY', 'REÇU': 'ODEBRANY', 'IMPORTER': 'IMPORTUJ',
      'NOUVEAU LOG': 'NOWY LOG', 'ARCHIVER': 'ARCHIWIZUJ', 'STATS': 'STATYSTYKI',
      'CHECKLIST': 'LISTA', 'COPIER': 'KOPIUJ', 'DÉMARRER': 'START',
      'PRÉPARER': 'PRZYGOTUJ', 'Règlement': 'Regulamin', 'Connecté au serveur': 'Połączono z serwerem',
      'Postes connectés :': 'Połączone stacje:', 'Serveur :': 'Serwer:',
      'SOLEIL & IONOSPHÈRE': 'SŁOŃCE I JONOSFERA', 'CONDITIONS PAR BANDE': 'WARUNKI NA PASMACH',
      'BALISES NCDXF/IBP': 'BEAKONY NCDXF/IBP', 'TOUS': 'WSZYSTKIE', 'NOUVEAUX MULTS': 'NOWE MNOŻNIKI',
      'SANS DOUBLONS': 'BEZ DUPLIKATÓW', 'À VENIR (31 j)': 'WKRÓTCE (31 dni)',
      'TABLEAU DE CHASSE': 'TABELA ŁOWÓW', 'OUTRE-MER': 'ZAMORSKIE',
      'Contacté': 'Zrobione', 'À faire': 'Do zrobienia', 'COMMENCER À LOGGER': 'ZACZNIJ LOGOWAĆ',
      'IDENTITÉ DE LA STATION': 'DANE STACJI', 'VILLE / QTH': 'MIASTO / QTH',
    },
  };

  // Libellés DYNAMIQUES de l'agent IA et du coach (page CARTE IA / mobile) :
  // messages injectés par JS, boutons, placeholder, horloge/rythme du coach.
  // Fusionnés dans T pour la traduction par correspondance de texte source.
  const T_AGENT = {
    en: {
      "AGENT": "AGENT", "ANALYSER": "ANALYZE", "Analyse en cours": "Analyzing",
      "Analyse les clusters et mon log maintenant.": "Analyze the clusters and my log now.",
      "Bandes :": "Bands:", "CHANGE DE BANDE": "CHANGE BAND", "COACH": "COACH",
      "Chargement de la configuration...": "Loading configuration...",
      "Chargement de ta configuration...": "Loading your configuration...",
      "Clique sur 📡 ANALYSER pour démarrer.": "Click 📡 ANALYZE to start.",
      "Coach indisponible — vérifie que radiocontest_serveur.py tourne.": "Coach unavailable — check that radiocontest_serveur.py is running.",
      "Concours :": "Contest:", "Conditions de propagation actuelles ?": "Current propagation conditions?",
      "Configuration chargée !": "Configuration loaded!",
      "Envoie un message à l'agent...": "Send a message to the agent...",
      "MULTS": "MULTS", "Modes :": "Modes:", "PROP": "PROP", "QSO dernière heure": "QSO last hour",
      "Quel est mon score actuel et ma progression ?": "What's my current score and progress?",
      "Quels multiplicateurs me manquent encore ?": "Which multipliers am I still missing?",
      "RÉSUMÉ": "SUMMARY", "Résumé complet de la session.": "Full summary of the session.",
      "SCORE": "SCORE", "SPOTS": "SPOTS",
      "Si tu arrives ici directement, retourne d'abord sur la page de configuration pour paramétrer ta station et ton concours.": "If you landed here directly, go back to the configuration page first to set up your station and your contest.",
      "Suis-je spoté sur les clusters ?": "Am I spotted on the clusters?", "VEILLE AUTO": "AUTO WATCH",
      "départ dans {h} h": "start in {h} h", "moyenne": "average", "mults → score": "mults → score",
      "pas de concours actif": "no active contest", "pts": "pts", "reste {h}h{mm}": "{h}h{mm} left",
      "terminé": "over", "total": "total",
      "🧠 Conseil stratégique demandé (état du concours transmis)": "🧠 Strategic advice requested (contest status sent)",
      "VÉRIFIER": "VERIFY", "DÉBRIEF": "DEBRIEF", "VÉRIFICATION DU LOG": "LOG CHECK",
      "DÉJÀ VU": "SEEN BEFORE", "CIBLES — QUI PEUT LES DONNER": "TARGETS — WHO CAN GIVE THEM",
      "🎓 Débrief post-concours demandé (déroulé transmis)": "🎓 Post-contest debrief requested (timeline sent)",
      "Aucun QSO dans le log de ce concours — rien à débriefer pour l'instant.": "No QSO in this contest log — nothing to debrief yet.",
    },
    de: {
      "AGENT": "AGENT", "ANALYSER": "ANALYSIEREN", "Analyse en cours": "Analyse läuft",
      "Analyse les clusters et mon log maintenant.": "Analysiere jetzt die Cluster und mein Log.",
      "Bandes :": "Bänder :", "CHANGE DE BANDE": "BAND WECHSELN", "COACH": "COACH",
      "Chargement de la configuration...": "Konfiguration wird geladen...",
      "Chargement de ta configuration...": "Deine Konfiguration wird geladen...",
      "Clique sur 📡 ANALYSER pour démarrer.": "Klick auf 📡 ANALYSIEREN, um zu starten.",
      "Coach indisponible — vérifie que radiocontest_serveur.py tourne.": "Coach nicht verfügbar — prüf, ob radiocontest_serveur.py läuft.",
      "Concours :": "Contest :", "Conditions de propagation actuelles ?": "Aktuelle Ausbreitungsbedingungen?",
      "Configuration chargée !": "Konfiguration geladen!",
      "Envoie un message à l'agent...": "Sende eine Nachricht an den Agenten...",
      "MULTS": "MULTS", "Modes :": "Modi :", "PROP": "PROP", "QSO dernière heure": "QSO letzte Stunde",
      "Quel est mon score actuel et ma progression ?": "Wie ist mein aktueller Score und mein Fortschritt?",
      "Quels multiplicateurs me manquent encore ?": "Welche Multiplikatoren fehlen mir noch?",
      "RÉSUMÉ": "ZUSAMMENFASSUNG", "Résumé complet de la session.": "Vollständige Zusammenfassung der Session.",
      "SCORE": "SCORE", "SPOTS": "SPOTS",
      "Si tu arrives ici directement, retourne d'abord sur la page de configuration pour paramétrer ta station et ton concours.": "Wenn du direkt hier landest, geh zuerst zurück auf die Konfigurationsseite, um deine Station und deinen Contest einzurichten.",
      "Suis-je spoté sur les clusters ?": "Bin ich in den Clustern gespottet?", "VEILLE AUTO": "AUTO-ÜBERWACHUNG",
      "départ dans {h} h": "Start in {h} h", "moyenne": "Durchschnitt", "mults → score": "Mults → Score",
      "pas de concours actif": "kein aktiver Contest", "pts": "Pkt.", "reste {h}h{mm}": "noch {h}h{mm}",
      "terminé": "beendet", "total": "gesamt",
      "🧠 Conseil stratégique demandé (état du concours transmis)": "🧠 Strategischer Rat angefragt (Contest-Status übermittelt)",
      "VÉRIFIER": "PRÜFEN", "DÉBRIEF": "DEBRIEF", "VÉRIFICATION DU LOG": "LOG-PRÜFUNG",
      "DÉJÀ VU": "BEKANNT", "CIBLES — QUI PEUT LES DONNER": "ZIELE — WER SIE GEBEN KANN",
      "🎓 Débrief post-concours demandé (déroulé transmis)": "🎓 Debrief nach dem Contest angefragt (Verlauf übermittelt)",
      "Aucun QSO dans le log de ce concours — rien à débriefer pour l'instant.": "Kein QSO im Log dieses Contests — noch nichts zu debriefen.",
    },
    es: {
      "AGENT": "AGENTE", "ANALYSER": "ANALIZAR", "Analyse en cours": "Análisis en curso",
      "Analyse les clusters et mon log maintenant.": "Analiza los clusters y mi log ahora.",
      "Bandes :": "Bandas :", "CHANGE DE BANDE": "CAMBIA DE BANDA", "COACH": "COACH",
      "Chargement de la configuration...": "Cargando la configuración…",
      "Chargement de ta configuration...": "Cargando tu configuración…",
      "Clique sur 📡 ANALYSER pour démarrer.": "Haz clic en 📡 ANALIZAR para empezar.",
      "Coach indisponible — vérifie que radiocontest_serveur.py tourne.": "Coach no disponible — verifica que radiocontest_serveur.py esté en ejecución.",
      "Concours :": "Concurso :", "Conditions de propagation actuelles ?": "¿Condiciones de propagación actuales ?",
      "Configuration chargée !": "¡Configuración cargada!",
      "Envoie un message à l'agent...": "Envía un mensaje al agente…",
      "MULTS": "MULTS", "Modes :": "Modos :", "PROP": "PROP", "QSO dernière heure": "QSO última hora",
      "Quel est mon score actuel et ma progression ?": "¿Cuál es mi puntaje actual y mi progresión ?",
      "Quels multiplicateurs me manquent encore ?": "¿Qué multiplicadores me faltan todavía ?",
      "RÉSUMÉ": "RESUMEN", "Résumé complet de la session.": "Resumen completo de la sesión.",
      "SCORE": "PUNTAJE", "SPOTS": "SPOTS",
      "Si tu arrives ici directement, retourne d'abord sur la page de configuration pour paramétrer ta station et ton concours.": "Si llegas aquí directamente, vuelve primero a la página de configuración para ajustar tu estación y tu concurso.",
      "Suis-je spoté sur les clusters ?": "¿Estoy spotado en los clusters ?", "VEILLE AUTO": "VIGILANCIA AUTO",
      "départ dans {h} h": "salida en {h} h", "moyenne": "media", "mults → score": "mults → puntaje",
      "pas de concours actif": "sin concurso activo", "pts": "pts", "reste {h}h{mm}": "quedan {h}h{mm}",
      "terminé": "terminado", "total": "total",
      "🧠 Conseil stratégique demandé (état du concours transmis)": "🧠 Consejo estratégico solicitado (estado del concurso transmitido)",
      "VÉRIFIER": "VERIFICAR", "DÉBRIEF": "DEBRIEF", "VÉRIFICATION DU LOG": "VERIFICACIÓN DEL LOG",
      "DÉJÀ VU": "YA VISTO", "CIBLES — QUI PEUT LES DONNER": "OBJETIVOS — QUIÉN PUEDE DARLOS",
      "🎓 Débrief post-concours demandé (déroulé transmis)": "🎓 Debrief post-concurso solicitado (desarrollo transmitido)",
      "Aucun QSO dans le log de ce concours — rien à débriefer pour l'instant.": "Ningún QSO en el log de este concurso — nada que analizar por ahora.",
    },
    it: {
      "AGENT": "AGENTE", "ANALYSER": "ANALIZZA", "Analyse en cours": "Analisi in corso",
      "Analyse les clusters et mon log maintenant.": "Analizza i cluster e il mio log adesso.",
      "Bandes :": "Bande :", "CHANGE DE BANDE": "CAMBIA BANDA", "COACH": "COACH",
      "Chargement de la configuration...": "Caricamento della configurazione...",
      "Chargement de ta configuration...": "Caricamento della tua configurazione...",
      "Clique sur 📡 ANALYSER pour démarrer.": "Clicca su 📡 ANALIZZA per iniziare.",
      "Coach indisponible — vérifie que radiocontest_serveur.py tourne.": "Coach non disponibile — verifica che radiocontest_serveur.py sia in esecuzione.",
      "Concours :": "Contest :", "Conditions de propagation actuelles ?": "Condizioni di propagazione attuali ?",
      "Configuration chargée !": "Configurazione caricata!",
      "Envoie un message à l'agent...": "Invia un messaggio all'agente...",
      "MULTS": "MULTS", "Modes :": "Modi :", "PROP": "PROP", "QSO dernière heure": "QSO ultima ora",
      "Quel est mon score actuel et ma progression ?": "Qual è il mio punteggio attuale e la mia progressione ?",
      "Quels multiplicateurs me manquent encore ?": "Quali moltiplicatori mi mancano ancora ?",
      "RÉSUMÉ": "RIEPILOGO", "Résumé complet de la session.": "Riepilogo completo della sessione.",
      "SCORE": "PUNTEGGIO", "SPOTS": "SPOTS",
      "Si tu arrives ici directement, retourne d'abord sur la page de configuration pour paramétrer ta station et ton concours.": "Se arrivi qui direttamente, torna prima alla pagina di configurazione per impostare la tua stazione e il tuo contest.",
      "Suis-je spoté sur les clusters ?": "Sono spottato sui cluster ?", "VEILLE AUTO": "MONITOR AUTO",
      "départ dans {h} h": "partenza tra {h} h", "moyenne": "media", "mults → score": "mults → punteggio",
      "pas de concours actif": "nessun contest attivo", "pts": "pt", "reste {h}h{mm}": "restano {h}h{mm}",
      "terminé": "terminato", "total": "totale",
      "🧠 Conseil stratégique demandé (état du concours transmis)": "🧠 Consiglio strategico richiesto (stato del contest trasmesso)",
      "VÉRIFIER": "VERIFICA", "DÉBRIEF": "DEBRIEF", "VÉRIFICATION DU LOG": "VERIFICA DEL LOG",
      "DÉJÀ VU": "GIÀ VISTO", "CIBLES — QUI PEUT LES DONNER": "OBIETTIVI — CHI PUÒ DARLI",
      "🎓 Débrief post-concours demandé (déroulé transmis)": "🎓 Debrief post-contest richiesto (andamento trasmesso)",
      "Aucun QSO dans le log de ce concours — rien à débriefer pour l'instant.": "Nessun QSO nel log di questo contest — niente da analizzare per ora.",
    },
    pt: {
      "AGENT": "AGENTE", "ANALYSER": "ANALISAR", "Analyse en cours": "Análise em curso",
      "Analyse les clusters et mon log maintenant.": "Analisa os clusters e o meu log agora.",
      "Bandes :": "Bandas :", "CHANGE DE BANDE": "MUDA DE BANDA", "COACH": "COACH",
      "Chargement de la configuration...": "A carregar a configuração...",
      "Chargement de ta configuration...": "A carregar a tua configuração...",
      "Clique sur 📡 ANALYSER pour démarrer.": "Clica em 📡 ANALISAR para começar.",
      "Coach indisponible — vérifie que radiocontest_serveur.py tourne.": "Coach indisponível — verifica que o radiocontest_serveur.py está a correr.",
      "Concours :": "Concurso :", "Conditions de propagation actuelles ?": "Condições de propagação atuais?",
      "Configuration chargée !": "Configuração carregada!",
      "Envoie un message à l'agent...": "Envia uma mensagem ao agente...",
      "MULTS": "MULTS", "Modes :": "Modos :", "PROP": "PROP", "QSO dernière heure": "QSO última hora",
      "Quel est mon score actuel et ma progression ?": "Qual é a minha pontuação atual e a minha progressão?",
      "Quels multiplicateurs me manquent encore ?": "Que multiplicadores ainda me faltam?",
      "RÉSUMÉ": "RESUMO", "Résumé complet de la session.": "Resumo completo da sessão.",
      "SCORE": "PONTUAÇÃO", "SPOTS": "SPOTS",
      "Si tu arrives ici directement, retourne d'abord sur la page de configuration pour paramétrer ta station et ton concours.": "Se chegaste aqui diretamente, volta primeiro à página de configuração para configurar a tua estação e o teu concurso.",
      "Suis-je spoté sur les clusters ?": "Estou spotado nos clusters?", "VEILLE AUTO": "VIGIA AUTO",
      "départ dans {h} h": "início em {h} h", "moyenne": "média", "mults → score": "mults → pontuação",
      "pas de concours actif": "sem concurso ativo", "pts": "pts", "reste {h}h{mm}": "restam {h}h{mm}",
      "terminé": "terminado", "total": "total",
      "🧠 Conseil stratégique demandé (état du concours transmis)": "🧠 Conselho estratégico solicitado (estado do concurso transmitido)",
      "VÉRIFIER": "VERIFICAR", "DÉBRIEF": "DEBRIEF", "VÉRIFICATION DU LOG": "VERIFICAÇÃO DO LOG",
      "DÉJÀ VU": "JÁ VISTO", "CIBLES — QUI PEUT LES DONNER": "ALVOS — QUEM PODE DÁ-LOS",
      "🎓 Débrief post-concours demandé (déroulé transmis)": "🎓 Debrief pós-concurso solicitado (desenrolar transmitido)",
      "Aucun QSO dans le log de ce concours — rien à débriefer pour l'instant.": "Nenhum QSO no log deste concurso — nada a analisar por agora.",
    },
    nl: {
      "AGENT": "AGENT", "ANALYSER": "ANALYSEREN", "Analyse en cours": "Analyse bezig",
      "Analyse les clusters et mon log maintenant.": "Analyseer nu de clusters en mijn log.",
      "Bandes :": "Banden:", "CHANGE DE BANDE": "WISSEL VAN BAND", "COACH": "COACH",
      "Chargement de la configuration...": "Configuratie wordt geladen...",
      "Chargement de ta configuration...": "Je configuratie wordt geladen...",
      "Clique sur 📡 ANALYSER pour démarrer.": "Klik op 📡 ANALYSEREN om te starten.",
      "Coach indisponible — vérifie que radiocontest_serveur.py tourne.": "Coach niet beschikbaar — controleer of radiocontest_serveur.py draait.",
      "Concours :": "Contest:", "Conditions de propagation actuelles ?": "Huidige propagatieomstandigheden?",
      "Configuration chargée !": "Configuratie geladen!",
      "Envoie un message à l'agent...": "Stuur een bericht naar de agent...",
      "MULTS": "MULTS", "Modes :": "Modes:", "PROP": "PROP", "QSO dernière heure": "QSO laatste uur",
      "Quel est mon score actuel et ma progression ?": "Wat is mijn huidige score en mijn voortgang?",
      "Quels multiplicateurs me manquent encore ?": "Welke multipliers ontbreken mij nog?",
      "RÉSUMÉ": "SAMENVATTING", "Résumé complet de la session.": "Volledige samenvatting van de sessie.",
      "SCORE": "SCORE", "SPOTS": "SPOTS",
      "Si tu arrives ici directement, retourne d'abord sur la page de configuration pour paramétrer ta station et ton concours.": "Als je hier rechtstreeks belandt, ga dan eerst terug naar de configuratiepagina om je station en je contest in te stellen.",
      "Suis-je spoté sur les clusters ?": "Ben ik gespot op de clusters?", "VEILLE AUTO": "AUTO-BEWAKING",
      "départ dans {h} h": "start over {h} u", "moyenne": "gemiddelde", "mults → score": "mults → score",
      "pas de concours actif": "geen actieve contest", "pts": "pt", "reste {h}h{mm}": "nog {h}u{mm}",
      "terminé": "afgelopen", "total": "totaal",
      "🧠 Conseil stratégique demandé (état du concours transmis)": "🧠 Strategisch advies gevraagd (conteststatus doorgegeven)",
      "VÉRIFIER": "CONTROLEER", "DÉBRIEF": "DEBRIEF", "VÉRIFICATION DU LOG": "LOGCONTROLE",
      "DÉJÀ VU": "AL GEZIEN", "CIBLES — QUI PEUT LES DONNER": "DOELEN — WIE ZE KAN GEVEN",
      "🎓 Débrief post-concours demandé (déroulé transmis)": "🎓 Debrief na de contest gevraagd (verloop doorgegeven)",
      "Aucun QSO dans le log de ce concours — rien à débriefer pour l'instant.": "Geen QSO in het log van deze contest — nog niets te debriefen.",
    },
    pl: {
      "AGENT": "AGENT", "ANALYSER": "ANALIZUJ", "Analyse en cours": "Analiza w toku",
      "Analyse les clusters et mon log maintenant.": "Przeanalizuj klastry i mój log teraz.",
      "Bandes :": "Pasma :", "CHANGE DE BANDE": "ZMIEŃ PASMO", "COACH": "COACH",
      "Chargement de la configuration...": "Wczytywanie konfiguracji...",
      "Chargement de ta configuration...": "Wczytywanie twojej konfiguracji...",
      "Clique sur 📡 ANALYSER pour démarrer.": "Kliknij 📡 ANALIZUJ, aby rozpocząć.",
      "Coach indisponible — vérifie que radiocontest_serveur.py tourne.": "Coach niedostępny — sprawdź, czy radiocontest_serveur.py działa.",
      "Concours :": "Zawody :", "Conditions de propagation actuelles ?": "Aktualne warunki propagacji?",
      "Configuration chargée !": "Konfiguracja wczytana!",
      "Envoie un message à l'agent...": "Wyślij wiadomość do agenta...",
      "MULTS": "MNOŻNIKI", "Modes :": "Tryby :", "PROP": "PROP", "QSO dernière heure": "QSO w ostatniej godzinie",
      "Quel est mon score actuel et ma progression ?": "Jaki jest mój aktualny wynik i postęp?",
      "Quels multiplicateurs me manquent encore ?": "Których mnożników jeszcze mi brakuje?",
      "RÉSUMÉ": "PODSUMOWANIE", "Résumé complet de la session.": "Pełne podsumowanie sesji.",
      "SCORE": "WYNIK", "SPOTS": "SPOTY",
      "Si tu arrives ici directement, retourne d'abord sur la page de configuration pour paramétrer ta station et ton concours.": "Jeśli trafiłeś tu bezpośrednio, wróć najpierw na stronę konfiguracji, aby ustawić swoją stację i zawody.",
      "Suis-je spoté sur les clusters ?": "Czy jestem zaspotowany na klastrach?", "VEILLE AUTO": "AUTO-NASŁUCH",
      "départ dans {h} h": "start za {h} h", "moyenne": "średnia", "mults → score": "mnożniki → wynik",
      "pas de concours actif": "brak aktywnych zawodów", "pts": "pkt", "reste {h}h{mm}": "zostało {h}h{mm}",
      "terminé": "zakończone", "total": "razem",
      "🧠 Conseil stratégique demandé (état du concours transmis)": "🧠 Poproszono o poradę strategiczną (stan zawodów przekazany)",
      "VÉRIFIER": "SPRAWDŹ", "DÉBRIEF": "DEBRIEF", "VÉRIFICATION DU LOG": "SPRAWDZENIE LOGU",
      "DÉJÀ VU": "JUŻ ZNANY", "CIBLES — QUI PEUT LES DONNER": "CELE — KTO MOŻE JE DAĆ",
      "🎓 Débrief post-concours demandé (déroulé transmis)": "🎓 Poproszono o debrief po zawodach (przebieg przekazany)",
      "Aucun QSO dans le log de ce concours — rien à débriefer pour l'instant.": "Brak QSO w logu tych zawodów — na razie nie ma czego podsumować.",
    },
  };
  Object.keys(T_AGENT).forEach(function (l) {
    if (T[l]) Object.assign(T[l], T_AGENT[l]);
  });

  // Directive de langue pour l'agent IA (ajoutée au prompt système côté client
  // avant l'appel /proxy/ai). Vide en fr/auto (le navigateur traduit la page).
  const LLM_DIRECTIVE = {
    en: "IMPORTANT: reply EXCLUSIVELY in English, whatever the language of the provided context or the question.",
    de: "WICHTIG: Antworte AUSSCHLIESSLICH auf Deutsch, unabhängig von der Sprache des bereitgestellten Kontexts oder der Frage.",
    es: "IMPORTANTE: responde EXCLUSIVAMENTE en español, sea cual sea el idioma del contexto proporcionado o de la pregunta.",
    it: "IMPORTANTE: rispondi ESCLUSIVAMENTE in italiano, qualunque sia la lingua del contesto fornito o della domanda.",
    pt: "IMPORTANTE: responde EXCLUSIVAMENTE em português, seja qual for a língua do contexto fornecido ou da pergunta.",
    nl: "BELANGRIJK: antwoord UITSLUITEND in het Nederlands, ongeacht de taal van de aangeleverde context of van de vraag.",
    pl: "WAŻNE: odpowiadaj WYŁĄCZNIE po polsku, niezależnie od języka podanego kontekstu lub pytania.",
  };

  function getLang() { return localStorage.getItem('rc_lang') || 'fr'; }

  // Sauvegarde des textes français d'origine pour pouvoir revenir en arrière
  const ORIG = new WeakMap();

  function setNode(node, raw, value) {
    if (!ORIG.has(node)) ORIG.set(node, raw);
    node.nodeValue = value;
  }

  function translateText(dict, node) {
    // Toujours partir du FRANÇAIS d'origine (sinon on tenterait de traduire
    // depuis la langue précédente — ex. anglais → allemand échouerait).
    const raw = ORIG.has(node) ? ORIG.get(node) : node.nodeValue;
    const key = raw.trim();
    if (!key) return;
    // 1) correspondance directe
    if (dict[key] !== undefined) {
      setNode(node, raw, raw.replace(key, dict[key]));
      return;
    }
    // 2) le texte a un préfixe emoji/symbole (« 🗺️ CARTE IA ») : on isole le
    //    cœur alphabétique et on ne traduit que lui, en gardant l'emoji.
    const m = key.match(/^([^\p{L}]+?\s*)(\p{L}.*)$/u);
    if (m && dict[m[2].trim()] !== undefined) {
      setNode(node, raw, raw.replace(key, m[1] + dict[m[2].trim()]));
      return;
    }
    // 3) rien à traduire → restaure le français d'origine si besoin
    if (ORIG.has(node)) node.nodeValue = ORIG.get(node);
  }

  function walk(dict, root) {
    // Nœuds de texte
    const it = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(n) {
        const p = n.parentNode;
        if (!p) return NodeFilter.FILTER_REJECT;
        const tag = p.nodeName;
        if (tag === 'SCRIPT' || tag === 'STYLE' || tag === 'OPTION') return NodeFilter.FILTER_REJECT;
        if (p.id === 'rcLangSelect' || (p.closest && p.closest('#rcLangSelect'))) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    const nodes = [];
    let n; while ((n = it.nextNode())) nodes.push(n);
    nodes.forEach(node => translateText(dict, node));
    // Attributs title / placeholder
    root.querySelectorAll('[title],[placeholder]').forEach(el => {
      ['title', 'placeholder'].forEach(attr => {
        const v = el.getAttribute(attr);
        if (v && dict[v.trim()] !== undefined) {
          const okey = '__i18n_' + attr;
          if (!el.dataset[okey]) el.dataset[okey] = v;
          el.setAttribute(attr, dict[v.trim()]);
        } else if (el.dataset['__i18n_' + attr]) {
          el.setAttribute(attr, el.dataset['__i18n_' + attr]);
        }
      });
    });
  }

  function applyLang(lang) {
    localStorage.setItem('rc_lang', lang);
    if (lang === 'fr' || lang === 'auto') {
      // Restaure le français source (le mode 'auto' laisse le navigateur agir)
      const dict = {};
      walk(dict, document.body);   // dict vide → ORIG restauré
      document.documentElement.lang = 'fr';
      return;
    }
    const dict = T[lang] || {};
    document.documentElement.lang = 'fr';   // source réelle = FR (aide le navigateur)
    walk(dict, document.body);
  }

  // Exposé pour re-traduire après un rendu dynamique
  window.rcTranslate = function () {
    const lang = getLang();
    if (lang !== 'fr' && lang !== 'auto') walk(T[lang] || {}, document.body);
  };

  // Langue courante, pour les autres scripts (carte, mobile).
  window.rcGetLang = getLang;

  // Traduit une chaîne source française CONNUE vers la langue courante.
  // Retourne le français tel quel en fr/auto ou si la clé est absente.
  // Sert à construire les messages injectés par JS (agent, coach).
  window.rcT = function (fr) {
    const l = getLang();
    if (l === 'fr' || l === 'auto') return fr;
    const d = T[l] || {};
    return d[fr] !== undefined ? d[fr] : fr;
  };

  // Comme rcT mais avec des placeholders {clé} remplacés par params.clé.
  window.rcTf = function (fr, params) {
    let s = window.rcT(fr);
    if (params) for (const k in params) s = s.split('{' + k + '}').join(params[k]);
    return s;
  };

  // Directive « réponds dans cette langue » à ajouter au prompt système IA.
  // Vide en fr/auto : l'IA répond en français (le navigateur traduit la page).
  window.rcLangDirective = function () {
    return LLM_DIRECTIVE[getLang()] || '';
  };

  function injectSelector() {
    if (document.getElementById('rcLangSelect')) return;
    const sel = document.createElement('select');
    sel.id = 'rcLangSelect';
    sel.title = 'Langue / Language';
    sel.style.cssText = 'font-family:var(--font-mono,monospace);font-size:12px;' +
      'background:var(--bg3,#13152A);color:var(--text,#E9ECF5);border:1px solid var(--border,#2B2F4A);' +
      'border-radius:5px;padding:3px 6px;cursor:pointer;margin-left:10px';
    LANGS.forEach(l => {
      const o = document.createElement('option');
      o.value = l.code; o.textContent = l.label;
      sel.appendChild(o);
    });
    sel.value = getLang();
    sel.addEventListener('change', () => applyLang(sel.value));
    // Insertion : dans le header s'il existe, sinon dans la nav
    const header = document.querySelector('header');
    const nav = document.querySelector('nav.app-nav') || document.querySelector('.nav-links');
    if (header) header.appendChild(sel);
    else if (nav) nav.appendChild(sel);
    else document.body.insertBefore(sel, document.body.firstChild);
  }

  function init() {
    injectSelector();
    const lang = getLang();
    if (lang !== 'fr') applyLang(lang);

    // Traduit le contenu injecté APRÈS le chargement (messages de l'agent IA,
    // panneau coach, listes de spots…). On n'observe QUE l'ajout de nœuds
    // (childList) : walk() ne modifie que des nodeValue/attributs (non observés),
    // donc pas de boucle. Débouncé par setTimeout — et NON requestAnimationFrame,
    // qui est gelé quand l'onglet est en arrière-plan (cas courant en concours :
    // WSJT-X ou le log au premier plan, la carte derrière).
    let pending = null;
    const obs = new MutationObserver(muts => {
      const l = getLang();
      if (l === 'fr' || l === 'auto') return;
      if (pending) return;
      let added = false;
      for (const m of muts) { if (m.addedNodes && m.addedNodes.length) { added = true; break; } }
      if (!added) return;
      pending = setTimeout(() => { pending = null; window.rcTranslate(); }, 60);
    });
    obs.observe(document.body, { childList: true, subtree: true });

    // Suit les changements faits dans un autre onglet
    window.addEventListener('storage', e => {
      if (e.key === 'rc_lang') {
        const s = document.getElementById('rcLangSelect');
        if (s) s.value = e.newValue || 'fr';
        applyLang(e.newValue || 'fr');
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
