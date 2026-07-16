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
