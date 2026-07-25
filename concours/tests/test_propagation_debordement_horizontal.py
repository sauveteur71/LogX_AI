# -*- coding: utf-8 -*-
"""PROPAG : la maconnerie multi-colonnes ne doit JAMAIS partager sa boite avec
une hauteur definie ou un ascenseur.

Le defaut qu'on fige ici. `.prop-main` a porte, sur la MEME boite :

    height:100% ; overflow-y:auto ; column-width:330px

Combinaison qui a l'air anodine et qui ne l'est pas. Une multi-colonne dont la
hauteur est DEFINIE est un fragmentainer ferme : le contenu qui ne tient pas ne
rallonge PAS la boite vers le bas, le navigateur fabrique des colonnes
supplementaires vers la DROITE (« overflow columns », CSS Multicol § 3.3). Et
comme overflow-y:auto force overflow-x a auto, la page recuperait une barre de
defilement HORIZONTALE : les panneaux etaient hors ecran, pas plus bas.

Mesure en navigateur reel (onglet HF, image MUF chargee), avant -> apres la
separation en deux boites :

    1366x768  : 449 px de debordement horizontal, barre de 15 px, 3 panneaux
                sur 5 atteignables      ->  0 px, defilement vertical 154 px, 5/5
    1280x720  : 840 px, 3/5             ->  0 px, defilement vertical 215 px, 5/5
    1100x700  : 720 px, 3/5             ->  0 px, defilement vertical 247 px, 5/5
    1536x864  : deja bon                ->  inchange
    1920x1080 : deja bon                ->  inchange, aucun defilement

Pourquoi ce test ne ressemble pas aux autres tests de mise en page du depot.
Le controle habituel — `document.documentElement.scrollHeight == innerHeight` —
vaut 768 == 768 dans TOUS les cas ci-dessus : la coque de l'application ne
defile effectivement jamais, c'est la zone interne qui deportait ses panneaux
hors ecran. Chercher `overflow:hidden` dans la source CSS a exactement le meme
angle mort : aucune largeur n'y est jamais comparee. Les deux controles passent
sur une page amputee des deux tiers de ses panneaux.

Faute d'un navigateur en integration continue, on fige donc la CAUSE et non le
symptome : aucune boite ne doit cumuler column-* et (hauteur definie ou
ascenseur), et le marquage ne doit pas reunir les deux roles sur un seul div.
"""
import os
import re

CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPAG = os.path.join(CONCOURS_DIR, 'logx_propagation.html')

# Proprietes qui font d'une boite une multi-colonne (le raccourci `columns` est
# ramene a ces deux-la par _developpe()).
MULTICOL = ('column-width', 'column-count')
# Valeurs de ces proprietes qui, au contraire, la desactivent.
MULTICOL_NEUTRE = ('auto', 'normal', 'initial', 'unset', '')
# Valeurs de height/max-height qui laissent la boite s'allonger librement.
HAUTEUR_LIBRE = ('auto', 'none', 'initial', 'unset', 'fit-content', 'max-content')
# Valeurs d'overflow qui font de la boite un conteneur de defilement.
OVERFLOW_ASCENSEUR = ('auto', 'scroll')


def _lire(chemin=PROPAG):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _feuille(src):
    """Contenu concatene des blocs <style> de la page, commentaires retires."""
    css = '\n'.join(re.findall(r'<style>(.*?)</style>', src, flags=re.DOTALL))
    assert css.strip(), 'aucun bloc <style> trouve dans la page'
    return re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)


def _fin_bloc(css, i):
    """Index du '}' fermant le bloc ouvert par css[i] == '{'."""
    profondeur = 0
    for j in range(i, len(css)):
        if css[j] == '{':
            profondeur += 1
        elif css[j] == '}':
            profondeur -= 1
            if profondeur == 0:
                return j
    raise AssertionError('accolades desequilibrees dans la feuille de style')


def _regles(css, contexte='base'):
    """Liste de (contexte, selecteur brut, {propriete: valeur}).

    Les groupes conditionnels (@media, @supports) sont explores avec leur
    condition pour contexte ; les autres at-rules (@import, @keyframes,
    @font-face) sont ignorees : un pourcentage d'animation n'est pas une boite.
    """
    out = []
    i = 0
    while i < len(css):
        c = css[i]
        if c.isspace():
            i += 1
            continue
        if c == '@':
            fin_prelude = min([p for p in (css.find('{', i), css.find(';', i))
                               if p != -1] or [len(css)])
            if fin_prelude >= len(css) or css[fin_prelude] == ';':
                i = fin_prelude + 1          # @import ... ;
                continue
            prelude = css[i:fin_prelude].strip()
            fin = _fin_bloc(css, fin_prelude)
            if prelude.split()[0].lower() in ('@media', '@supports'):
                out += _regles(css[fin_prelude + 1:fin], prelude)
            i = fin + 1
            continue
        ouvre = css.find('{', i)
        if ouvre == -1:
            break
        fin = _fin_bloc(css, ouvre)
        selecteur = css[i:ouvre].strip()
        decls = {}
        for morceau in css[ouvre + 1:fin].split(';'):
            if ':' in morceau:
                prop, _, val = morceau.partition(':')
                decls[prop.strip().lower()] = val.strip().lower()
        out.append((contexte, selecteur, decls))
        i = fin + 1
    return out


def _classes_sujet(selecteur):
    """Classes de la boite REELLEMENT visee par le selecteur.

    Seul le dernier compose compte : dans « .container .panel », c'est .panel
    qui recoit les declarations, pas .container.
    """
    classes = set()
    for variante in selecteur.split(','):
        sujet = re.split(r'[\s>+~]+', variante.strip())[-1]
        classes |= set(re.findall(r'\.([A-Za-z0-9_-]+)', sujet))
    return classes


def _developpe(decls):
    """Developpe les raccourcis en proprietes longues.

    Sans ca, la fusion se trompe dans le sens qui ACCUSE a tort : une regle de
    base `overflow-y:auto` suivie d'un `overflow:visible` dans un @media reste
    vue comme un ascenseur, alors que le raccourci a bel et bien remis les deux
    axes a visible. Le meme raisonnement vaut pour `columns`.
    """
    sortie = dict(decls)
    if 'overflow' in decls:
        parts = decls['overflow'].split()
        sortie['overflow-x'] = parts[0]
        sortie['overflow-y'] = parts[1] if len(parts) > 1 else parts[0]
    if 'columns' in decls:
        sortie['column-width'] = sortie['column-count'] = decls['columns']
    return sortie


def _par_classe(regles, contexte):
    """{classe -> declarations cumulees} telles qu'elles s'appliquent dans un
    contexte donne : les regles de base d'abord, puis celles du groupe
    conditionnel qui les remplacent (c'est l'ordre de la cascade ici)."""
    fusion = {}
    for ctx in ('base', contexte) if contexte != 'base' else ('base',):
        for c, selecteur, decls in regles:
            if c != ctx:
                continue
            for classe in _classes_sujet(selecteur):
                fusion.setdefault(classe, {}).update(_developpe(decls))
    return fusion


def _est_multicol(decls):
    return any(decls.get(p, '') not in MULTICOL_NEUTRE for p in MULTICOL)


def _hauteur_definie(decls):
    for prop in ('height', 'max-height'):
        val = decls.get(prop)
        if val is not None and val not in HAUTEUR_LIBRE:
            return '%s:%s' % (prop, val)
    return None


def _ascenseur(decls):
    for prop in ('overflow-y', 'overflow-x'):
        val = decls.get(prop)
        if val is not None and val in OVERFLOW_ASCENSEUR:
            return '%s:%s' % (prop, val)
    return None


def _contextes(regles):
    return ['base'] + sorted({c for c, _, _ in regles if c != 'base'})


# ── L'invariant : column-* et hauteur/ascenseur sur des boites separees ────

def test_aucune_multicolonne_a_hauteur_definie():
    """C'est LE defaut : hauteur definie => colonnes en trop vers la droite."""
    regles = _regles(_feuille(_lire()))
    fautes = []
    for contexte in _contextes(regles):
        for classe, decls in _par_classe(regles, contexte).items():
            if _est_multicol(decls):
                hauteur = _hauteur_definie(decls)
                if hauteur:
                    fautes.append('.%s (%s) : %s' % (classe, contexte, hauteur))
    assert not fautes, (
        'boite(s) multi-colonnes a hauteur definie : %s\n'
        'Une multi-colonne dont la hauteur est fixee ne s\'allonge pas vers le '
        'bas : elle fabrique des colonnes supplementaires vers la DROITE, hors '
        'ecran. La zone qui defile et la zone en colonnes doivent rester deux '
        'boites distinctes (.prop-main / .prop-cols).' % ', '.join(fautes))


def test_aucune_multicolonne_ne_porte_l_ascenseur():
    """L'autre moitie du piege : overflow-y:auto sur la multi-colonne force
    overflow-x a auto, donc une barre HORIZONTALE des qu'une colonne deborde."""
    regles = _regles(_feuille(_lire()))
    fautes = []
    for contexte in _contextes(regles):
        for classe, decls in _par_classe(regles, contexte).items():
            if _est_multicol(decls):
                asc = _ascenseur(decls)
                if asc:
                    fautes.append('.%s (%s) : %s' % (classe, contexte, asc))
    assert not fautes, (
        'boite(s) multi-colonnes portant un ascenseur : %s\n'
        'Le defilement appartient a la boite PARENTE, jamais a celle qui porte '
        'column-*.' % ', '.join(fautes))


def test_le_marquage_ne_reunit_pas_les_deux_roles_sur_un_seul_div():
    """Le CSS peut etre correct et le marquage le defaire : il suffit de
    recoller les deux classes sur le meme element."""
    src = _lire()
    regles = _regles(_feuille(src))
    base = _par_classe(regles, 'base')
    multicol = {c for c, d in base.items() if _est_multicol(d)}
    porteuses = {c for c, d in base.items()
                 if _hauteur_definie(d) or _ascenseur(d)}
    fautes = []
    for attr in re.findall(r'class="([^"]*)"', src):
        portees = set(attr.split())
        if portees & multicol and portees & porteuses:
            fautes.append(attr)
    assert not fautes, (
        'element(s) cumulant la maconnerie et la zone qui defile : %s'
        % ', '.join(sorted(set(fautes))))


def test_la_maconnerie_multicolonne_existe_toujours():
    """Garde-fou anti-test-vide : sans multi-colonne dans la page, les trois
    tests ci-dessus passeraient sans rien verifier. Si la maconnerie est
    remplacee un jour (grille, flex), c'est une decision a prendre en
    conscience — et ce fichier est alors a revoir, pas a laisser vert."""
    base = _par_classe(_regles(_feuille(_lire())), 'base')
    multicol = sorted(c for c, d in base.items() if _est_multicol(d))
    assert multicol, (
        'plus aucune boite multi-colonnes dans logx_propagation.html : la '
        'maconnerie de largeur uniforme a disparu, ou ce test ne surveille '
        'plus rien')


def test_la_zone_qui_defile_est_bien_la_boite_parente():
    """Verifie le montage attendu : une boite qui defile, et a l'interieur une
    boite en colonnes de hauteur libre."""
    src = _lire()
    base = _par_classe(_regles(_feuille(src)), 'base')
    multicol = {c for c, d in base.items() if _est_multicol(d)}
    scrollers = {c for c, d in base.items() if _ascenseur(d)}
    assert scrollers, 'aucune zone de defilement : la page ne peut plus defiler'
    # Chaque boite en colonnes doit se trouver dans le marquage a l'interieur
    # d'un element portant une classe de defilement.
    for classe in sorted(multicol):
        motif = r'class="[^"]*\b%s\b[^"]*"' % re.escape(classe)
        m = re.search(motif, src)
        assert m, 'classe %s declaree en CSS mais absente du marquage' % classe
        avant = src[:m.start()]
        ouvert = [c for c in scrollers
                  if re.search(r'class="[^"]*\b%s\b[^"]*"' % re.escape(c), avant)]
        assert ouvert, (
            'la boite en colonnes .%s n\'est imbriquee dans aucune zone de '
            'defilement : le debordement n\'a nulle part ou aller' % classe)
