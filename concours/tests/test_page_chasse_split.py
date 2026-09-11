# -*- coding: utf-8 -*-
"""Separation PROPAG / CHASSE, puis fusion CHASSE -> activité « activation
portable » (incr. 5c, 11/09/2026, D2 F4GLD « fusion totale »).

Historique de ce fichier : il verrouillait d'abord le déménagement des cinq
panneaux de « cibles de trafic » de PROPAG vers une page CHASSE dédiée
(11/08/2026). Ce même contenu vient d'être déménagé UNE SECONDE FOIS, de
CHASSE vers l'activité "activation portable" de l'accueil (fusion CHASSE→
activité, incréments 1 à 5b, tous mergés et vérifiés en navigateur réel avant
celui-ci). CHASSE elle-même devient une page de REDIRECTION pure — plus un
seul octet de son ancien contenu n'y reste.

Pourquoi figer ça par des tests plutot que se fier a une relecture :

1) Le piège du contenu mort laissé derrière. Rien ne garantit qu'un futur
   commit ne réintroduise pas par erreur un fragment de l'ancien contenu de
   CHASSE (copier-coller d'un diff, restauration partielle) : les tests
   ci-dessous vérifient l'ABSENCE des identifiants/endpoints déjà migrés,
   comme au premier déménagement (PROPAG->CHASSE).

2) Le piège du lien mort. CHASSE reste une URL PUBLIQUE (bookmarks,
   liens externes, 13 pages qui y pointent dans leur nav) : la page doit
   TOUJOURS rediriger, jamais rendre un 404 ni un contenu vide.

3) Le piège du bouton Retour. Une redirection posée avec `location.href`
   (plutôt que `.replace()`) laisse une entrée d'historique morte : Retour
   ramènerait sur une page qui se redirige aussitôt -- boucle perçue comme un
   bug par l'utilisateur.

4) Le piège de la barre de navigation dupliquée (toujours valable) : la nav
   est recopiee a la main dans CHAQUE page .html qui la porte. CHASSE n'en a
   plus besoin (elle ne s'affiche jamais) -- mais les 13 AUTRES pages, qui
   pointent toujours vers "logx_chasse.html" dans leur propre nav, doivent
   rester identiques entre elles.

5) L'i18n fonctionne par correspondance EXACTE du texte francais : le libelle
   de nav "CHASSE" (utilisé par les 13 autres pages) doit rester traduit dans
   les 7 langues même si CHASSE elle-même n'affiche plus rien.
"""
import os
import re

CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CHASSE = os.path.join(CONCOURS_DIR, 'logx_chasse.html')
PROPAG = os.path.join(CONCOURS_DIR, 'logx_propagation.html')
ACCUEIL_JS = os.path.join(CONCOURS_DIR, 'logx_accueil.js')
I18N = os.path.join(CONCOURS_DIR, 'logx_i18n.js')

# Les pages qui portent la barre de navigation applicative. logx_chasse.html
# EN EST SORTIE (incr. 5c) : elle ne s'affiche plus jamais, donc plus de nav
# propre à vérifier -- mais elle reste une CIBLE de la nav des autres pages
# (voir ORDRE_NAV_ATTENDU, inchangé : aucune des 13 pages n'a été modifiée).
PAGES_AVEC_NAV = [
    'logx_accueil.html', 'logx_calendrier.html', 'logx_carte.html',
    'logx_configuration.html', 'logx_cw.html', 'logx_departements.html',
    'logx_diagnostic.html', 'logx_eme.html', 'logx_logbook.html',
    'logx_modes_numeriques.html', 'logx_propagation.html', 'logx_session.html',
    'logx_websdr.html',
]

# Ordre de nav fige le 11/08/2026 (reorg nav + fusion PROPAG/FOCUS BANDE) :
# CONFIG, LOGBOOK, CHASSE, MODE NUMERIQUE, PROPAG, CARTE IA, ZONES TRAVAILLEES
# (ex-DEPARTEMENTS), PANADAPTER (popout javascript:void(0)), CALENDRIER,
# WEBSDR, ECOLE CW. Refonte nav approche A (27/08) puis EME (01/09) : voir
# git blame pour le détail historique. INCHANGÉ par l'incr. 5c : les 13 pages
# pointent toujours vers "logx_chasse.html", qui redirige en interne.
ORDRE_NAV_ATTENDU = [
    'logx_configuration.html', 'logx_logbook.html', 'logx_chasse.html',
    'logx_propagation.html', 'logx_diagnostic.html', 'logx_session.html',
    'logx_modes_numeriques.html', 'logx_carte.html', 'logx_departements.html',
    'javascript:void(0)', 'logx_calendrier.html', 'logx_websdr.html',
    'logx_eme.html', 'logx_cw.html',
]

# Titres des cinq panneaux, DEUX FOIS déménagés : PROPAG -> CHASSE (11/08),
# puis CHASSE -> l'activité (11/09, ce fichier). Toujours utiles pour vérifier
# qu'aucun des deux anciens emplacements n'en garde une trace.
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

# Fonctions/endpoints qui alimentaient ces panneaux DANS CHASSE (son ancienne
# implémentation inline, avant l'incr. 5c). L'activité utilise ses PROPRES
# noms (renderActivationRows, _revelerCiblesChasse, etc. dans logx_accueil.js
# + logx_chasse_panneaux.js) -- ces symboles-ci sont donc doublement morts
# maintenant : ni dans PROPAG, ni dans CHASSE.
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


# ── CHASSE existe toujours et redirige (incr. 5c) ────────────────────────

def test_page_chasse_existe():
    assert os.path.isfile(CHASSE), 'logx_chasse.html manquante'


def test_chasse_redirige_vers_lactivite_en_mode_chasse():
    """Les deux mécanismes de redirection (meta-refresh ET JS) doivent
    pointer vers la MÊME destination — logx_accueil.js::init() sait
    reconnaitre ?chasse=1 et révéler directement les cibles en direct
    (incr. 5b, déjà mergé et vérifié en navigateur réel)."""
    src = _lire(CHASSE)
    assert re.search(
        r'<meta http-equiv="refresh" content="0;\s*url=logx_accueil\.html\?chasse=1"',
        src), 'meta-refresh absente ou mal ciblée (marche même sans JS)'
    assert "location.replace('logx_accueil.html?chasse=1')" in src, (
        'redirection JS absente ou mal ciblée')


def test_chasse_utilise_replace_jamais_href():
    """.href laisserait une entrée d'historique morte -- Retour ramènerait
    sur cette page qui se redirige aussitôt (boucle perçue comme un bug)."""
    src = _lire(CHASSE)
    assert 'location.href' not in src
    assert '.replace(' in src


def test_chasse_a_un_repli_sans_javascript():
    """<meta http-equiv=refresh> suffit déjà sans JS, mais un lien explicite
    reste plus honnête qu'une page blanche si le user-agent ignore aussi le
    meta-refresh (certains lecteurs d'écran/proxies)."""
    src = _lire(CHASSE)
    assert '<noscript>' in src
    assert 'href="logx_accueil.html?chasse=1"' in src


# ── CHASSE ne garde AUCUNE trace de son ancien contenu ───────────────────

def test_chasse_na_plus_les_cinq_panneaux():
    src = _lire(CHASSE)
    for titre in TITRES_DEPLACES:
        assert titre not in src, (
            'panneau encore présent dans logx_chasse.html (devrait être '
            'entièrement migré vers activité) : ' + titre)


def test_chasse_na_plus_les_ids_des_panneaux():
    src = _sans_commentaires_html(_lire(CHASSE))
    for ident in IDS_DEPLACES:
        assert ident not in src, (
            "id encore reference dans logx_chasse.html : %s — page censée "
            "être un pur redirect" % ident)


def test_chasse_na_plus_le_js_ni_les_appels_reseau():
    src = _sans_commentaires_html(_lire(CHASSE))
    for sym in SYMBOLES_DEPLACES:
        assert sym not in src, 'code mort dans logx_chasse.html : ' + sym
    for url in ENDPOINTS_DEPLACES:
        assert url not in src, (
            'appel reseau orphelin dans logx_chasse.html : ' + url)


def test_chasse_ne_porte_plus_sa_propre_nav():
    """La nav applicative (.app-nav) n'a plus de raison d'être ici : la page
    ne s'affiche jamais assez longtemps pour qu'on clique dedans."""
    src = _lire(CHASSE)
    assert 'app-nav' not in src


# ── La destination (activité) porte bien le contenu migré ────────────────

def test_lactivite_alimente_bien_les_panneaux_migres():
    """Non-régression inverse : le contenu n'a pas juste disparu, il vit
    dans logx_accueil.js (+ logx_chasse_panneaux.js, testés à part) —
    couverture déjà faite par test_accueil_panneaux_4b.py/test_accueil_
    redirect_chasse.py ; ici on vérifie juste que les ENDPOINTS attendus
    sont bien référencés quelque part dans le nouveau chemin."""
    src = _lire(ACCUEIL_JS)
    for url in ENDPOINTS_DEPLACES:
        assert url in src, (
            'endpoint absent de logx_accueil.js après la fusion : ' + url)


# ── PROPAG n'en garde AUCUNE trace non plus (inchangé depuis 11/08) ──────

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


# ── Navigation : les 13 AUTRES pages restent identiques entre elles ──────

def _nav(src):
    m = re.search(r'<nav class="app-nav"[^>]*>(.*?)</nav>', src, flags=re.DOTALL)
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


def test_ordre_de_nav_fige():
    """Ordre complet fige (pas juste une adjacence isolee, plus robuste a un
    futur reordonnancement) : voir ORDRE_NAV_ATTENDU."""
    for page in PAGES_AVEC_NAV:
        cibles = re.findall(r'<a href="([^"]+)"',
                            _nav(_lire(os.path.join(CONCOURS_DIR, page))))
        assert cibles == ORDRE_NAV_ATTENDU, (
            'ordre de nav inattendu dans %s :\n  attendu : %s\n  obtenu  : %s'
            % (page, ORDRE_NAV_ATTENDU, cibles))


# ── i18n : le libelle de nav CHASSE reste traduit (utilise par 13 pages) ──

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
    """Le libellé "CHASSE" reste utilisé par les 13 AUTRES pages, même si
    CHASSE elle-même ne l'affiche plus (elle n'a plus de nav du tout)."""
    blocs = _blocs_par_langue(_lire(I18N))
    for lang in LANGUES:
        val = _traduction(blocs, lang, r"'CHASSE':\s*'([^']+)'")
        assert val, "libelle de nav 'CHASSE' non traduit en " + lang


# ── Garde-fous du banc d'essai ─────────────────────────────────────────

def test_l_extraction_du_nav_est_bien_le_vrai_code():
    nav = _nav(_lire(os.path.join(CONCOURS_DIR, 'logx_logbook.html')))
    assert nav is not None and 'logx_chasse.html' in nav
