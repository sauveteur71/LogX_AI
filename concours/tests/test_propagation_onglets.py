# -*- coding: utf-8 -*-
"""Page PROPAG : quatre onglets (BANDE ACTUELLE / HF / VHF & EME /
M'ENTEND-ON) et, surtout, suspension des rafraichissements des onglets
masques.

BANDE ACTUELLE (ex-FOCUS BANDE, fusionne EV-7 phase 2 increment B PR1,
2026-08-11) est l'onglet PAR DEFAUT -- c'est l'outil operationnel a garder
ouvert en permanence en concours, les trois autres restent des dashboards de
reference consultes ponctuellement.

Pourquoi figer ca par des tests plutot que par une relecture :

1) Le piege du decoupage cosmetique. Masquer des panneaux en CSS est visible
   au premier coup d'oeil ; laisser leurs treize chargeurs tourner ne l'est
   PAS. La page continuerait d'interroger PSK Reporter, RBN, tropo, meteores,
   EME et les balises pendant qu'on regarde la seule colonne HF, sans la
   moindre erreur console — exactement le meme mode d'echec silencieux que le
   code mort laisse derriere un demenagement de panneau.

2) Le piege du panneau orphelin. Un chargeur dont le panneau a change
   d'onglet SANS que sa declaration suive ne leve rien non plus : il se
   rafraichit quand son panneau est cache, et reste fige quand il est
   affiche. C'est une panne 100 % silencieuse, et c'est le defaut le plus
   probable a la prochaine reorganisation. Le test croise donc les identifiants
   DOM ecrits par chaque chargeur avec l'onglet ou ils se trouvent reellement.

3) Le piege du lien ancre. La barre de statut pointe vers
   logx_propagation.html#beaconPanel. Si l'onglet contenant la cible n'est pas
   selectionne a l'arrivee, l'ancre reste techniquement valide et le clic ne
   fait visiblement RIEN.

4) L'i18n fonctionne par correspondance EXACTE du texte francais : un libelle
   d'onglet sans entree dans les 7 langues reste en francais au milieu d'une
   interface traduite, sans erreur.
"""
import os
import re

CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPAG = os.path.join(CONCOURS_DIR, 'logx_propagation.html')
I18N = os.path.join(CONCOURS_DIR, 'logx_i18n.js')

ONGLETS = ('focus', 'hf', 'vhf', 'heard')
LANGUES = ('en', 'de', 'es', 'it', 'pt', 'nl', 'pl')

# Chargeurs qui ne sont volontairement PAS des taches d'onglet.
HORS_PLANIFICATEUR = {
    # Liens externes construits une fois depuis la config (carte PSK filtree
    # sur l'indicatif, passages satellites pour le locator) : ils ne se
    # periment pas, donc pas de rafraichissement a suspendre.
    'loadStationLinks',
    # Rendu pur, sans reseau : alimente par l'evenement 'logx:beacons' de la
    # barre de statut.
    'renderBeacons',
}


def _lire(chemin=PROPAG):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _sans_commentaires(src):
    src = re.sub(r'<!--.*?-->', '', src, flags=re.DOTALL)
    return '\n'.join(l for l in src.split('\n')
                     if not l.lstrip().startswith(('//', '*', '/*')))


def _corps_html(src):
    """Le marquage seul, sans le <script> final (sinon les identifiants cites
    dans le JS seraient pris pour du marquage)."""
    return src.split('<script>')[-2] if src.count('<script>') else src


def _nb_panneaux(frag):
    """Compte les CARTES, pas leurs en-tetes : `<div class="panel-title">`
    commence par la meme chaine et doublerait chaque total."""
    return len(re.findall(r'<div class="panel"[ >]', frag))


def _panes(src):
    """{ nom d'onglet -> fragment HTML de l'onglet }.

    L'invariant verifie ici est « chaque onglet existe et delimite ses
    panneaux », PAS la liste exacte de ses classes CSS : un onglet peut poser
    la maconnerie multi-colonnes sur lui-meme (class="prop-cols prop-pane") ou
    la deleguer a un conteneur interne quand un panneau doit rester en pleine
    largeur au-dessus des autres — c'est le cas de HF depuis qu'OUVERTURES PAR
    REGION, un tableau de 5 colonnes, en est sorti. Figer la chaine complete
    faisait echouer les 5 tests du fichier pour un simple deplacement de
    classe, sans qu'aucun onglet ne soit reellement casse.
    """
    out = {}
    for nom in ONGLETS:
        m = re.search(
            r'<div class="[^"]*\bprop-pane\b[^"]*" id="propPane-%s"(.*?)'
            r'</div><!-- /propPane-%s -->' % (nom, nom), src, flags=re.DOTALL)
        assert m, "onglet introuvable dans logx_propagation.html : " + nom
        out[nom] = m.group(1)
    return out


def _pane_par_id(src):
    """{ identifiant DOM -> onglet qui le contient }."""
    index = {}
    for nom, frag in _panes(src).items():
        for ident in re.findall(r'\bid="([A-Za-z0-9_-]+)"', frag):
            index[ident] = nom
    return index


def _corps_fonction(src, nom):
    """Corps d'une fonction, delimite par comptage d'accolades.

    Surtout PAS « jusqu'a la prochaine accolade en colonne 0 » : les fonctions
    d'une ligne (esc()) se terminent par « ; }` en fin de ligne, et l'heuristique
    avalait alors tout le code suivant jusqu'a la fonction d'apres — le test
    voyait des identifiants qui n'ont rien a voir et accusait le mauvais
    chargeur.
    """
    m = re.search(r'(?:async\s+)?function\s+%s\s*\([^)]*\)\s*\{'
                  % re.escape(nom), src)
    assert m, 'fonction introuvable : ' + nom
    i = m.end() - 1
    profondeur = 0
    for j in range(i, len(src)):
        if src[j] == '{':
            profondeur += 1
        elif src[j] == '}':
            profondeur -= 1
            if profondeur == 0:
                return src[i + 1:j]
    raise AssertionError('accolades desequilibrees dans ' + nom)


def _taches(src):
    """[(nom du chargeur, [onglets declares])] tels que declares en JS."""
    return [(m.group(1), re.findall(r"'([a-z]+)'", m.group(2)))
            for m in re.finditer(r'propTask\(\s*(\w+)\s*,[^,]+,\s*(\[[^\]]*\])',
                                 src)]


# ── Les quatre onglets existent et se partagent tous les panneaux ───────────

def test_les_quatre_onglets_existent():
    src = _lire()
    for nom in ONGLETS:
        assert 'id="propTabBtn-%s"' % nom in src, 'bouton d\'onglet absent : ' + nom
    _panes(src)   # leve si un panneau d'onglet manque


def test_les_libelles_des_onglets():
    """Les quatre questions distinctes que la page traite, dans cet ordre.
    BANDE ACTUELLE (ex-FOCUS BANDE) est en tete : c'est l'onglet par defaut."""
    src = _lire()
    libelles = re.findall(r'<button type="button" role="tab".*?>(.*?)</button>',
                          src, flags=re.DOTALL)
    assert len(libelles) == 4, libelles
    assert 'BANDE ACTUELLE' in libelles[0]
    assert 'HF' in libelles[1]
    assert 'VHF' in libelles[2] and 'EME' in libelles[2]
    assert "M'ENTEND-ON" in libelles[3]


def test_un_seul_onglet_visible_au_chargement():
    """Deux onglets sans `hidden` donneraient une page qui s'ouvre avec deux
    macconneries empilees — c'est-a-dire la page d'avant."""
    src = _lire()
    caches = [nom for nom in ONGLETS
              if re.search(r'id="propPane-%s"[^>]*\bhidden\b' % nom, src)]
    assert sorted(caches) == ['heard', 'hf', 'vhf'], (
        'onglets caches au chargement : %s (attendu : tous sauf BANDE ACTUELLE)' % caches)


def test_aucun_panneau_hors_des_onglets():
    """Un panneau laisse en dehors des trois onglets resterait affiche en
    permanence, sous celui qui est selectionne."""
    corps = _corps_html(_lire())
    dans_onglets = sum(_nb_panneaux(frag) for frag in _panes(_lire()).values())
    assert _nb_panneaux(corps) == dans_onglets, (
        'un panneau au moins est hors des onglets')


def test_repartition_des_panneaux():
    """Repartition attendue : 0 / 5 / 6 / 2.

    Le 13e panneau d'origine, la foudre, est devenu la pastille de la barre de
    statut. Le 6e de l'onglet VHF est le panneau SATELLITES (31/07/2026) :
    l'intitule de l'onglet annoncait deja « satellites » alors que rien ne les
    affichait — l'endpoint /data/sat existait sans aucun ecran pour le lire.
    BANDE ACTUELLE (ex-FOCUS BANDE, fusion EV-7 phase 2 increment B PR1) est a
    0 : son contenu (classement de bandes, cluster, concours actifs...) est
    fait de cartes `.carte`, pas de `.panel` -- un style visuel distinct
    heritee de l'ancienne page autonome, pas un onglet vide.

    Ce test n'est pas un compteur decoratif : il tombe des qu'un panneau est
    ajoute ou deplace, et oblige a verifier qu'il est bien DANS un onglet
    (sinon il resterait affiche en permanence, cf. test ci-dessus)."""
    panes = _panes(_lire())
    compte = {nom: _nb_panneaux(frag) for nom, frag in panes.items()}
    assert compte == {'focus': 0, 'hf': 5, 'vhf': 6, 'heard': 2}, compte


# ── Le coeur : les onglets masques ne rafraichissent plus ───────────────────

def test_aucun_minuteur_n_echappe_au_planificateur():
    """Un setInterval(loadX, ...) survivant rendrait le decoupage cosmetique :
    l'appel reseau partirait quand meme, onglet masque ou pas."""
    js = _sans_commentaires(_lire())
    intervals = re.findall(r'setInterval\(\s*(\w+)', js)
    assert intervals == ['propTick'], (
        'minuteur(s) hors planificateur : %s' % intervals)


def test_le_planificateur_teste_bien_l_onglet_actif():
    corps = _corps_fonction(_lire(), 'propTick')
    assert 'propActivePane' in corps, (
        'propTick() ne consulte pas l\'onglet actif : rien n\'est suspendu')
    assert 'indexOf(propActivePane) < 0' in corps, corps


def test_chaque_chargeur_est_declare_dans_le_bon_onglet():
    """LE test qui compte. Croise les identifiants DOM que chaque chargeur
    ecrit avec l'onglet ou ils se trouvent VRAIMENT dans le marquage. Un
    panneau deplace d'un onglet a l'autre sans mise a jour de sa declaration
    passerait sinon totalement inapercu : il se rafraichirait cache et
    resterait fige affiche."""
    src = _lire()
    index = _pane_par_id(src)
    locales = set(re.findall(r'(?:async\s+)?function\s+(\w+)\s*\(', src))
    for nom, declares in _taches(src):
        corps = _corps_fonction(src, nom)
        # Un niveau d'indirection : loadBeacons() delegue le rendu a
        # renderBeacons(), partage avec l'evenement 'logx:beacons' de la barre
        # de statut. S'arreter au corps direct ne verrait aucun identifiant et
        # le test se croirait content.
        for appelee in set(re.findall(r'\b(\w+)\s*\(', corps)) & locales:
            if appelee != nom:
                corps += _corps_fonction(src, appelee)
        cibles = set(re.findall(r"getElementById\('([A-Za-z0-9_-]+)'\)", corps))
        # Les identifiants hors onglets (en-tete de page, noeuds crees a la
        # volee) ne disent rien sur l'onglet : on ne garde que ceux du marquage.
        panes_reels = {index[i] for i in cibles if i in index}
        assert panes_reels, (
            '%s n\'ecrit dans AUCUN panneau d\'onglet — chargeur orphelin ?'
            % nom)
        assert panes_reels <= set(declares), (
            '%s alimente %s mais n\'est declare que sur %s : ses panneaux se '
            'rafraichiraient masques et resteraient figes affiches'
            % (nom, sorted(panes_reels), sorted(declares)))


def test_tous_les_chargeurs_reseau_sont_des_taches():
    """Non-regression inverse : un chargeur oublie a la declaration ne serait
    jamais appele du tout — panneau definitivement bloque sur « … »."""
    src = _lire()
    definis = set(re.findall(r'(?:async\s+)?function\s+(load\w+|refresh\w+|render\w+)\s*\(',
                             src)) - HORS_PLANIFICATEUR
    declares = {nom for nom, _ in _taches(src)}
    # loadBeacons n'est declare que si la barre de statut est absente (elle
    # rediffuse deja /beacons/now) : sa declaration est sous condition.
    conditionnels = set(re.findall(r'if \(!window\.logxBeaconFeed\) propTask\((\w+)', src))
    manquants = definis - declares - conditionnels
    assert not manquants, (
        'chargeur(s) jamais planifie(s), panneau fige sur « … » : %s'
        % sorted(manquants))


def test_changer_d_onglet_sert_immediatement_ce_qui_a_expire():
    """Sans ce rattrapage, arriver sur un onglet jamais affiche laisserait ses
    panneaux sur « … » jusqu'au prochain tic — jusqu'a 20 minutes pour la
    tropo."""
    corps = _corps_fonction(_lire(), 'propSelectPane')
    assert 'propTick()' in corps, corps


# ── Lien ancre entrant (#beaconPanel depuis la barre de statut) ─────────────

def test_le_lien_ancre_selectionne_l_onglet_de_la_cible():
    src = _lire()
    assert 'propPaneOfHash' in src, (
        "aucune resolution d'ancre : le lien #beaconPanel de la barre de "
        'statut peut tomber sur un panneau masque')
    assert "window.addEventListener('hashchange'" in src, (
        "une 2e arrivee sur la meme page (meme lien reclique) ne recharge pas "
        'la page : sans hashchange, rien ne se passerait')
    assert _pane_par_id(src).get('beaconPanel'), (
        'beaconPanel n\'est dans aucun onglet — la cible du lien de la barre '
        'de statut a disparu')


# ── i18n : les libelles d'onglet existent dans les 7 langues ───────────────

def _blocs_par_langue(src):
    """Decoupe logx_i18n.js en blocs { langue -> [textes des dictionnaires] }.
    Compter les occurrences globales d'une cle ne prouve RIEN : sept
    occurrences peuvent etre sept fois l'anglais."""
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


def test_i18n_libelle_onglet_m_entend_on_dans_les_sept_langues():
    blocs = _blocs_par_langue(_lire(I18N))
    for lang in LANGUES:
        val = _traduction(blocs, lang, r'"M\'ENTEND-ON":\s*"([^"]+)"')
        assert val, "libelle d'onglet \"M'ENTEND-ON\" non traduit en " + lang


def test_i18n_pastille_orage_dans_les_sept_langues():
    """Les deux etats de la pastille de foudre. « ORAGE » non traduit dans une
    interface allemande est une alerte de securite materiel illisible."""
    blocs = _blocs_par_langue(_lire(I18N))
    for lang in LANGUES:
        for motif in (r'"ORAGE":\s*"([^"]+)"', r'"pas d\'orage":\s*"([^"]+)"'):
            assert _traduction(blocs, lang, motif), (
                'pastille orage non traduite en %s (%s)' % (lang, motif))


def test_i18n_infobulles_des_onglets_dans_les_sept_langues():
    blocs = _blocs_par_langue(_lire(I18N))
    debuts = ('"Soleil, MUF, ouvertures par',
              '"Sporadique-E, tropo/ducting,',
              '"Où mon signal est réellement')
    for lang in LANGUES:
        for debut in debuts:
            motif = re.escape(debut) + r'[^"]*":\s*\n?\s*"([^"]+)"'
            assert _traduction(blocs, lang, motif), (
                "infobulle d'onglet non traduite en %s : %s" % (lang, debut))


def test_les_infobulles_des_onglets_sont_bien_dans_la_page():
    """Les cles i18n ci-dessus ne servent a rien si le marquage a change de
    formulation — correspondance EXACTE oblige."""
    src = _lire()
    for texte in ('Soleil, MUF, ouvertures par région, conditions par bande, '
                  'balises NCDXF/IBP',
                  'Sporadique-E, tropo/ducting, météores, rebond lunaire, '
                  'satellites',
                  'Où mon signal est réellement décodé : PSK Reporter et '
                  'skimmers RBN'):
        assert texte in src, 'infobulle absente du marquage : ' + texte
