# -*- coding: utf-8 -*-
"""Separation PROPAG / CHASSE : les cinq panneaux de « cibles de trafic »
vivent sur logx_chasse.html, plus du tout sur logx_propagation.html.

Pourquoi figer ca par des tests plutot que se fier a une relecture :

1) Le piege du getElementById silencieux. Partout dans ce projet, un
   `document.getElementById(...)` sur un id disparu est garde par un
   `if (el)` ou avale par un `try/catch` — laisser du JS de chargement
   POTA/SOTA/WWFF/WCA/cluster sur la page propagation ne produirait AUCUNE
   erreur visible : juste des requetes reseau inutiles toutes les minutes et
   du code mort que la relecture suivante croira encore utile. Les tests
   ci-dessous verifient donc l'ABSENCE du marquage ET l'ABSENCE du code qui
   l'alimentait.

2) Le piege de la barre de navigation dupliquee. La nav est recopiee a la
   main dans CHAQUE page .html : ajouter une entree sur six pages sur sept
   donne une navigation qui change d'une page a l'autre, ce qui ne casse rien
   techniquement et passe donc inapercu en relecture.

3) L'i18n fonctionne par correspondance EXACTE du texte francais : un libelle
   de nav sans entree dans les 7 langues reste en francais au milieu d'une
   interface traduite, sans la moindre erreur.
"""
import os
import re

CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHASSE = os.path.join(CONCOURS_DIR, 'logx_chasse.html')
PROPAG = os.path.join(CONCOURS_DIR, 'logx_propagation.html')
I18N = os.path.join(CONCOURS_DIR, 'logx_i18n.js')

# Les pages qui portent la barre de navigation applicative (celles-la et pas
# d'autres : mobile/wall/scope/panel sont des vues autonomes sans nav).
PAGES_AVEC_NAV = [
    'logx_calendrier.html', 'logx_carte.html', 'logx_chasse.html',
    'logx_configuration.html', 'logx_departements.html', 'logx_logbook.html',
    'logx_propagation.html', 'logx_websdr.html',
]

# Titres exacts des cinq panneaux deplaces (accents et emojis compris).
TITRES_DEPLACES = [
    '\U0001F3DE️ ACTIVATEURS POTA EN DIRECT',
    '\U0001F3D4️ ACTIVATEURS SOTA EN DIRECT',
    '\U0001F333 ACTIVATEURS WWFF EN DIRECT',
    '\U0001F3F0 CHÂTEAUX WCA/COTA — ANNONCÉS',
    '\U0001F3AF CLUSTER — NEED LIST',
]

# Identifiants DOM que le JS de ces panneaux manipule.
IDS_DEPLACES = [
    'potaList', 'potaMeta', 'sotaList', 'sotaMeta', 'wwffList', 'wwffMeta',
    'wcaList', 'wcaMeta', 'spotList', 'spotsMeta',
]

# Fonctions/endpoints qui alimentaient ces panneaux.
SYMBOLES_DEPLACES = [
    'loadPota', 'loadSota', 'loadWwff', 'loadWca', 'loadSpots', 'renderSpots',
    'setFilter', 'spotsData', 'PRIO_COLORS',
]
ENDPOINTS_DEPLACES = [
    '/data/pota_spots', '/data/sota_spots', '/data/wwff_spots',
    '/data/wca_planned', '/data/spots_ranked',
]

LANGUES = ('en', 'de', 'es', 'it', 'pt', 'nl', 'pl')


def _lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _sans_commentaires_html(src):
    """Retire les commentaires HTML et les commentaires JS pleine ligne : un
    commentaire qui explique le demenagement n'est pas une reference vivante."""
    src = re.sub(r'<!--.*?-->', '', src, flags=re.DOTALL)
    return '\n'.join(l for l in src.split('\n')
                     if not l.lstrip().startswith(('//', '*', '/*')))


# ── La page CHASSE existe et contient bien les cinq panneaux ────────────────

def test_page_chasse_existe():
    assert os.path.isfile(CHASSE), 'logx_chasse.html manquante'


def test_les_cinq_panneaux_sont_sur_la_page_chasse():
    src = _lire(CHASSE)
    for titre in TITRES_DEPLACES:
        assert titre in src, 'panneau absent de logx_chasse.html : ' + titre


def test_le_js_qui_alimente_les_panneaux_a_suivi():
    """Deplacer le marquage sans le code donnerait cinq panneaux figes sur
    « … » : visuellement present, definitivement vide."""
    src = _lire(CHASSE)
    for sym in SYMBOLES_DEPLACES:
        assert sym in src, 'fonction/variable absente de logx_chasse.html : ' + sym
    for url in ENDPOINTS_DEPLACES:
        assert url in src, 'endpoint absent de logx_chasse.html : ' + url


# ── La page PROPAG n'en garde AUCUNE trace ─────────────────────────────────

def test_propagation_n_a_plus_le_marquage_des_panneaux_deplaces():
    src = _lire(PROPAG)
    for titre in TITRES_DEPLACES:
        assert titre not in src, (
            'panneau encore present dans logx_propagation.html : ' + titre)


def test_propagation_n_a_plus_les_ids_des_panneaux_deplaces():
    src = _sans_commentaires_html(_lire(PROPAG))
    for ident in IDS_DEPLACES:
        assert ident not in src, (
            "id encore reference dans logx_propagation.html : %s — c'est "
            'exactement le piege du getElementById silencieux' % ident)


def test_propagation_n_a_plus_le_js_ni_les_appels_reseau_deplaces():
    """Du code mort ici ne leverait aucune erreur mais continuerait a
    interroger POTA/SOTA/WWFF/WCA/cluster en boucle pour rien."""
    src = _sans_commentaires_html(_lire(PROPAG))
    for sym in SYMBOLES_DEPLACES:
        assert sym not in src, (
            'code mort dans logx_propagation.html : ' + sym)
    for url in ENDPOINTS_DEPLACES:
        assert url not in src, (
            'appel reseau orphelin dans logx_propagation.html : ' + url)


def test_propagation_garde_ses_propres_panneaux():
    """Non-regression inverse : on ne doit pas avoir emporte la propagation
    elle-meme dans le demenagement."""
    src = _lire(PROPAG)
    for reste in ('solarGrid', 'mufVal', 'beaconList', 'pskList', 'rbnList',
                  'tropoPanel', 'meteorPanel', 'emeBody', 'openingsBody'):
        assert reste in src, 'panneau de propagation perdu : ' + reste


# ── Navigation : la meme barre partout ─────────────────────────────────────

def _nav(src):
    m = re.search(r'<nav class="app-nav">(.*?)</nav>', src, flags=re.DOTALL)
    return m.group(1) if m else None


def test_toutes_les_pages_a_nav_ont_l_entree_chasse():
    manquantes = []
    for page in PAGES_AVEC_NAV:
        nav = _nav(_lire(os.path.join(CONCOURS_DIR, page)))
        assert nav is not None, 'barre de navigation introuvable dans ' + page
        if 'logx_chasse.html' not in nav:
            manquantes.append(page)
    assert not manquantes, (
        'entree CHASSE absente de la nav de : %s — la navigation devient '
        'incoherente d\'une page a l\'autre' % ', '.join(manquantes))


def test_la_nav_est_identique_partout():
    """Meme liste de destinations, dans le meme ordre, sur toutes les pages."""
    reference = None
    for page in PAGES_AVEC_NAV:
        nav = _nav(_lire(os.path.join(CONCOURS_DIR, page)))
        cibles = re.findall(r'<a href="([^"]+)"', nav)
        if reference is None:
            reference, page_ref = cibles, page
        assert cibles == reference, (
            'nav differente entre %s et %s :\n  %s\n  %s'
            % (page_ref, page, reference, cibles))


def test_chasse_est_juste_apres_propag():
    """Place logique : l'etat de la propagation, puis qui contacter."""
    for page in PAGES_AVEC_NAV:
        cibles = re.findall(r'<a href="([^"]+)"',
                            _nav(_lire(os.path.join(CONCOURS_DIR, page))))
        i_prop = cibles.index('logx_propagation.html')
        assert cibles[i_prop + 1] == 'logx_chasse.html', (
            'ordre de nav inattendu dans ' + page)


def test_la_page_chasse_se_marque_active():
    nav = _nav(_lire(CHASSE))
    assert re.search(r'<a href="logx_chasse\.html" class="active"', nav), (
        "logx_chasse.html doit surligner sa propre entree de nav")


# ── i18n : le nouveau libelle existe dans les 7 langues ────────────────────

def _blocs_par_langue(src):
    """Decoupe logx_i18n.js en blocs { langue -> [textes des dictionnaires] }.

    Le fichier empile plusieurs dictionnaires (T, puis des blocs T_*_FIX
    fusionnes par-dessus), chacun ouvrant une section par langue sous la forme
    `    en: {`. Compter les occurrences globales d'une cle ne prouve donc
    RIEN : sept occurrences peuvent tres bien etre sept fois l'anglais. On
    verifie langue par langue.
    """
    ouvertures = [(m.start(), m.group(1))
                  for m in re.finditer(r'^ {4}([a-z]{2}): \{', src,
                                       flags=re.MULTILINE)]
    blocs = {}
    for i, (pos, lang) in enumerate(ouvertures):
        fin = ouvertures[i + 1][0] if i + 1 < len(ouvertures) else len(src)
        blocs.setdefault(lang, []).append(src[pos:fin])
    return blocs


def _traduction(blocs, lang, motif):
    for bloc in blocs.get(lang, []):
        m = re.search(motif, bloc)
        if m:
            return m.group(1)
    return None


def test_i18n_libelle_nav_chasse_dans_les_sept_langues():
    blocs = _blocs_par_langue(_lire(I18N))
    for lang in LANGUES:
        val = _traduction(blocs, lang, r"'CHASSE':\s*'([^']+)'")
        assert val, "libelle de nav 'CHASSE' non traduit en " + lang


def test_i18n_titre_de_page_chasse_dans_les_sept_langues():
    blocs = _blocs_par_langue(_lire(I18N))
    for lang in LANGUES:
        val = _traduction(blocs, lang, r'"Chasse & Cibles":\s*"([^"]+)"')
        assert val, "titre de page 'Chasse & Cibles' non traduit en " + lang


def test_i18n_ecran_file_de_la_page_chasse_traduit():
    """Le garde-fou file:// affiche une URL : elle doit pointer vers la BONNE
    page dans chaque langue, sinon on renvoie l'operateur sur la propagation."""
    blocs = _blocs_par_langue(_lire(I18N))
    cle = re.escape('"Ouvre cette page via le serveur : '
                    'http://127.0.0.1:8080/logx_chasse.html"')
    for lang in LANGUES:
        val = _traduction(blocs, lang, cle + r':\s*\n\s*"([^"]+)"')
        assert val, 'ecran file:// de la page CHASSE non traduit en ' + lang
        assert 'logx_chasse.html' in val, (
            'la traduction %s renvoie vers la mauvaise page : %s' % (lang, val))


# ── Mise en page : aucun defilement vertical possible par construction ─────

def test_chasse_ne_peut_pas_defiler_verticalement():
    """Verifie dans un navigateur reel a 1920x1080 et 1366x768 (scrollHeight
    == innerHeight dans les deux cas). Ce test fige la construction qui le
    garantit : body en flex colonne avec overflow:hidden, et chaque liste qui
    defile dans SON panneau plutot que d'allonger la page."""
    src = _lire(CHASSE)
    assert re.search(r'body\{[^}]*overflow:hidden', src), (
        'body sans overflow:hidden : la page CHASSE peut de nouveau defiler')
    assert re.search(r'\.container\{[^}]*overflow:hidden', src)
    assert re.search(r'\.scroll-list\{[^}]*overflow-y:auto', src), (
        'les listes doivent defiler en interne, pas allonger la page')
