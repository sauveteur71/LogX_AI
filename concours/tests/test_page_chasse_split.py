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

# Titres exacts des cinq panneaux deplaces (accents compris).
# Libelles renommes le 30/07/2026 a la demande de l'utilisateur : « activateur »
# et « activation » ont disparu des ecrans francais, au profit du vocabulaire
# radioamateur (voir tests/test_vocabulaire_portable.py, qui verrouille aussi la
# correspondance avec les cles de traduction). Les identifiants DOM ci-dessous
# n'ont PAS bouge : ils ne sont jamais vus par l'operateur.
#
# Prefixe emoji retire le 03/08/2026 (chantier icones monochromes, cf.
# CLAUDE.md) : chaque titre est desormais precede d'un <svg> plutot que d'un
# caractere emoji. On verifie le TEXTE, qui n'a pas bouge, plutot que de figer
# un prefixe decoratif appele a changer a nouveau.
TITRES_DEPLACES = [
    'STATIONS POTA EN DIRECT',
    'STATIONS SOTA EN DIRECT',
    'STATIONS WWFF EN DIRECT',
    'CHÂTEAUX WCA/COTA — ANNONCÉS',
    'CLUSTER — NEED LIST',
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


def test_i18n_message_file_de_chasse_est_bien_la_cle_du_dictionnaire():
    """Le test precedent verifie que la CLE existe — mais il retape la chaine
    a la main. Si le message de logx_chasse.html derive (une espace, un
    deux-points), la cle reste presente dans le dictionnaire et le test
    continue de passer alors que plus rien ne correspond a l'execution :
    l'i18n fonctionne par correspondance EXACTE. On extrait donc la chaine
    de la PAGE et on exige qu'elle soit la cle."""
    page = _lire(CHASSE)
    m = re.search(r"document\.body\.innerHTML = '<div[^>]*>([^<]+)</div>';", page)
    assert m, 'garde-fou file:// introuvable dans logx_chasse.html'
    message = m.group(1)
    blocs = _blocs_par_langue(_lire(I18N))
    for lang in LANGUES:
        val = _traduction(blocs, lang,
                          re.escape('"' + message + '"') + r':\s*\n\s*"([^"]+)"')
        assert val, (
            'le message affiche par logx_chasse.html n\'est pas une cle du '
            'dictionnaire %s : %r' % (lang, message))


def test_i18n_langue_retombe_sur_le_navigateur_en_file():
    """Les 7 traductions ci-dessus sont INATTEIGNABLES sans ce repli.

    La langue choisie par l'operateur est rangee dans localStorage sous
    `rc_lang`, et localStorage est CLOISONNE PAR ORIGINE : `file://` est une
    origine distincte de `http://127.0.0.1:8080`. Une page ouverte par
    double-clic ne peut donc PAS lire ce choix — `rc_lang` y vaut toujours
    null, et un getLang() ecrit `localStorage.getItem('rc_lang') || 'fr'`
    renvoie 'fr' quoi qu'il arrive : l'ecran « ouvre cette page via le
    serveur » reste en francais meme avec l'application reglee en allemand,
    et les 7 traductions ne servent jamais. Le seul signal disponible dans
    cette origine est la langue du navigateur.

    Verifie en navigateur reel (Chrome, file:///…/logx_chasse.html, rc_lang
    absent) : navigateur allemand -> « Öffne diese Seite über den Server: … »,
    navigateur russe -> francais, et en http:// avec navigateur allemand ->
    francais (le repli reste bien confine a file://)."""
    src = _lire(I18N)
    # Corps de getLang() SEUL : le negatif (?!\n  function ) empeche la capture
    # de deborder sur les fonctions suivantes — sans lui, un getLang() ecrit
    # sur une seule ligne (la version fautive, justement) ferait capturer tout
    # le code d'apres et les assertions passeraient sur du texte etranger.
    corps = re.search(r'\n  function getLang\(\)\s*\{'
                      r'((?:(?!\n  function )[\s\S])*?)\n  \}', src)
    assert corps, 'getLang() introuvable (ou reduit a une seule ligne)'
    corps = corps.group(1)
    assert "location.protocol === 'file:'" in corps and 'typeof location' in corps, (
        "getLang() ne traite pas le cas file:// : la langue de l'application "
        "n'y est PAS lisible (autre origine de stockage), l'ecran d'erreur "
        'restera en francais dans les 7 langues')
    # Le repli doit venir de la langue du NAVIGATEUR, pas d'une constante.
    repli = re.search(r'\n  function browserLang\(\)\s*\{(.*?)\n  \}', src, re.S)
    assert repli, 'browserLang() introuvable'
    assert 'navigator' in repli.group(1) and '.languages' in repli.group(1), (
        'le repli file:// doit lire la langue du navigateur')
    # …et rester CONFINE a file:// : en http, l'absence de choix veut dire
    # « pas encore choisi » et doit continuer de donner le francais.
    assert re.search(r"location\.protocol === 'file:'\)\s*\{\s*\n"
                     r"\s*return browserLang\(\);\s*\n"
                     r"\s*\}\s*\n"
                     r"\s*return 'fr';", corps), (
        'le repli navigateur doit etre reserve a file:// (sinon il change la '
        "langue par defaut de toute l'application au premier lancement)")


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
