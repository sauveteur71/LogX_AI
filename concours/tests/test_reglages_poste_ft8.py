# -*- coding: utf-8 -*-
"""FT8 : afficher les réglages à adopter sur LE poste déclaré.

LA DEMANDE (F4GLD, 20/08/2026) : « si je démarre la page ft8 la configuration
qui doit être adoptée sur la radio sélectionnée soit affichée ».

CE QU'IL Y AVAIT AVANT : une liste de conseils génériques, dans un panneau
REPLIÉ, à 90 lignes du panneau d'émission, qui ne savait pas quel poste
l'opérateur avait déclaré — alors que la configuration le sait. Un débutant y
lisait « mets ton poste en mode données » sans savoir où appuyer.

LE RISQUE PROPRE À CE LOT, et la raison de la plupart des tests ci-dessous :
c'est le seul endroit du logiciel où une approximation se paie en matériel et
en brouillage des voisins. Un chemin de menu inventé envoie l'opérateur régler
un menu qui n'existe pas ; une valeur de niveau fausse lui fait écrêter son
signal. D'où la règle de constitution du module de données, que ces tests
FONT RESPECTER : chaque ligne porte sa source ET une citation vérifiable.

CE QUE CES TESTS NE PROUVENT PAS : que les citations soient fidèles aux
manuels. Ça ne se vérifie qu'en ouvrant les manuels — ce qui a été fait à la
main pour les lignes les plus lourdes (mode et niveau de l'IC-7300, socle
WSJT-X extrait du PDF officiel de 105 pages et cherché mot à mot). Un test ne
peut garantir que la PRÉSENCE d'une source, jamais son exactitude.
"""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_ft8_sequenceur import _lire  # noqa: E402

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(CONCOURS, 'logx_reglages_poste.js')
PAGE = os.path.join(CONCOURS, 'logx_ft8.html')


def _sans_commentaires(src):
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'//.*$', '', li) for li in src.splitlines())


def _banc():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval('var window = {};')
    ctx.eval(_lire(MODULE))
    return ctx


def _toutes_les_lignes(ctx):
    """Toutes les lignes affichables du module, quelle que soit leur origine."""
    return json.loads(ctx.eval("""
    JSON.stringify(
      REGLAGES_UNIVERSELS
        .concat(Object.keys(REGLAGES_PAR_MODELE).reduce(function(a,k){
          return a.concat(REGLAGES_PAR_MODELE[k].map(function(l){
            l = Object.assign({}, l); l.__ou = k; return l; })); }, []))
        .concat(Object.keys(REGLAGES_PAR_MARQUE).reduce(function(a,k){
          return a.concat(REGLAGES_PAR_MARQUE[k].map(function(l){
            l = Object.assign({}, l); l.__ou = k; return l; })); }, []))
    )"""))


# ─── la règle de constitution : rien sans source ─────────────────────────────

def test_chaque_reglage_porte_une_source_ET_une_citation():
    """LE test de ce lot. Une consigne de réglage d'émission sans source est
    une consigne inventée, et elle s'entend sur l'air. La citation est exigée
    en plus de la source : « Manuel IC-7300 » sans phrase citée ne permet à
    personne d'aller vérifier, et n'empêche personne d'écrire n'importe quoi."""
    manquants = []
    for l in _toutes_les_lignes(_banc()):
        ou = l.get('__ou', 'universel')
        if not (l.get('source') or '').strip():
            manquants.append('%s / %s : SOURCE absente' % (ou, l.get('intitule')))
        if not (l.get('citation') or '').strip():
            manquants.append('%s / %s : CITATION absente' % (ou, l.get('intitule')))
        if not (l.get('url') or '').startswith('https://'):
            manquants.append('%s / %s : URL absente ou non https' % (ou, l.get('intitule')))
    assert not manquants, 'réglage(s) sans source vérifiable :\n' + '\n'.join(manquants)


def test_chaque_reglage_dit_quelque_chose_d_actionnable():
    """Un intitulé sans valeur n'aide personne à régler son poste."""
    vides = [l.get('intitule') for l in _toutes_les_lignes(_banc())
             if not (l.get('valeur') or '').strip()]
    assert not vides, 'réglage(s) sans valeur : %s' % vides


# ─── ce que le module sait, et ce qu'il avoue ignorer ────────────────────────

def test_un_poste_source_est_annonce_comme_couvert():
    ctx = _banc()
    r = json.loads(ctx.eval("JSON.stringify(reglagesPoste('icom','IC-7300'))"))
    assert r['couvert'] is True
    assert len(r['modeleLignes']) >= 3
    assert len(r['marqueLignes']) >= 1, 'la consigne CI-V Transceive doit remonter'


def test_un_poste_INCONNU_est_annonce_comme_NON_couvert():
    """LE point d'honnêteté. Sans ce drapeau, l'opérateur d'un poste non sourcé
    lirait les règles universelles en croyant qu'elles sont propres à sa radio,
    et chercherait un menu qui n'existe pas chez lui. Extrapoler d'un IC-7300
    vers un IC-7610 serait faux : leurs menus diffèrent réellement."""
    ctx = _banc()
    for marque, modele in (('yaesu', 'FTDX101D'), ('icom', 'IC-746'), ('', '')):
        r = json.loads(ctx.eval("JSON.stringify(reglagesPoste(%s,%s))"
                                % (json.dumps(marque), json.dumps(modele))))
        assert r['couvert'] is False, '%s %s ne devrait pas être annoncé couvert' % (marque, modele)
        assert r['modeleLignes'] == []


def test_le_socle_universel_est_rendu_dans_tous_les_cas():
    """Même sans poste déclaré : ces règles-là valent pour tout le monde."""
    ctx = _banc()
    r = json.loads(ctx.eval("JSON.stringify(reglagesPoste('',''))"))
    assert len(r['universels']) >= 5


def test_le_modele_est_reconnu_quelle_que_soit_l_ecriture():
    """CONFIG écrit « IC-7300 », mais rien ne garantit la casse ni les espaces
    d'une saisie future ou d'un import. Un modèle non reconnu retomberait en
    silence sur « non couvert » — l'opérateur perdrait ses réglages sans
    comprendre pourquoi."""
    ctx = _banc()
    for ecriture in ('IC-7300', 'ic-7300', 'IC7300', ' IC-7300 ', 'Ic 7300'):
        r = json.loads(ctx.eval("JSON.stringify(reglagesPoste('icom',%s))"
                                % json.dumps(ecriture)))
        assert r['couvert'] is True, 'écriture %r non reconnue' % ecriture


# ─── le socle universel dit ce que le guide officiel dit, et rien de plus ────

def test_le_critere_de_niveau_est_celui_du_guide_officiel():
    """Décision de F4GLD du 20/08/2026, prise après vérification : le critère
    affiché est celui de WSJT-X — descendre jusqu'à ce que la puissance HF
    commence tout juste à baisser. Il se lit au wattmètre, donc il vaut aussi
    quand le poste est commuté par VOX, cas où l'ALC ne permet PAS de
    distinguer un réglage propre d'un poste qui ne se déclenche plus."""
    ctx = _banc()
    niveau = json.loads(ctx.eval(
        "JSON.stringify(REGLAGES_UNIVERSELS.filter(function(l){return l.cle==='niveau';})[0])"))
    assert 'RF output from your transmitter falls slightly' in niveau['citation']
    assert 'wsjt' in niveau['url'].lower()
    assert 'puissance HF' in niveau['valeur']


def test_aucune_consigne_ALC_n_est_attribuee_au_guide_WSJT_X():
    """MESURÉ, pas supposé : le mot « ALC » n'apparaît NULLE PART dans le guide
    officiel WSJT-X 2.7.0. Vérifié en extrayant le PDF (105 pages) et en
    cherchant le mot entier — les seules correspondances étaient à l'intérieur
    de « calculated ». La consigne « ALC à zéro », très répandue, ne vient donc
    pas de là. On peut la donner comme repère ou comme usage ; on ne peut pas
    la mettre dans la bouche du guide."""
    ctx = _banc()
    for l in json.loads(ctx.eval('JSON.stringify(REGLAGES_UNIVERSELS)')):
        if 'wsjt' in (l.get('url') or '').lower():
            assert 'ALC' not in (l.get('citation') or ''), (
                'citation attribuée à WSJT-X contenant « ALC » : %r' % l.get('citation'))


# ─── câblage de la page ──────────────────────────────────────────────────────

def test_la_page_charge_le_module_ET_l_affiche_au_chargement():
    """La demande était de voir la configuration EN ARRIVANT sur la page.
    Charger le module sans appeler le rendu n'afficherait rien ; appeler le
    rendu sans charger le module échouerait en silence."""
    src = _lire(PAGE)
    assert '<script src="logx_reglages_poste.js"></script>' in src
    code = _sans_commentaires(src)
    i = code.index('function cablerReglagesPoste')
    corps = code[i:code.index('})();', i)]
    assert 'majReglagesPoste()' in corps, corps


def test_le_rendu_dit_ce_qu_il_ignore():
    """Structure, pas présence : la branche « non couvert » doit exister DANS
    le rendu, et pas seulement le mot quelque part dans le fichier."""
    code = _sans_commentaires(_lire(PAGE))
    i = code.index('function majReglagesPoste()')
    corps = code[i:code.index('\n  window.majReglagesPoste', i)]
    assert 'r.couvert' in corps, corps
    assert 'regl-inconnu' in corps, (
        "le cas du poste non sourcé doit produire un avertissement visible")


def test_le_panneau_ne_s_ouvre_QUE_si_on_a_de_quoi_le_remplir():
    """Ouvrir d'office un pavé générique à chaque visite serait imposer la
    complexité au lieu de la rendre disponible — l'inverse du maître mot du
    projet. Le panneau ne s'ouvre que quand on a du propre au poste à dire."""
    code = _sans_commentaires(_lire(PAGE))
    i = code.index('function majReglagesPoste()')
    corps = code[i:code.index('\n  window.majReglagesPoste', i)]
    assert re.search(r'if\s*\(\s*det\s*&&\s*r\.couvert', corps), (
        "l'ouverture doit rester conditionnée à r.couvert :\n" + corps)


def test_le_panneau_ne_se_rouvre_pas_si_deja_ferme_pour_ce_poste():
    """Retour F4GLD (21/08/2026) : « si mes réglages sont déjà faits je n'ai
    pas besoin de ça » — le panneau se rouvrait de force à CHAQUE visite,
    même après que l'opérateur l'ait explicitement refermé une fois ses
    réglages appliqués. L'ouverture forcée doit désormais être également
    conditionnée à l'ABSENCE d'une fermeture déjà mémorisée pour CE poste
    précis (marque+modèle) — un changement de poste redonnant une bonne
    raison de la revoir."""
    code = _sans_commentaires(_lire(PAGE))
    i = code.index('function majReglagesPoste()')
    corps = code[i:code.index('\n  window.majReglagesPoste', i)]
    assert "localStorage.getItem('logx_aide_poste_vue') !== cleVu" in corps, corps
    assert "cleVu = marque + '|' + modele" in corps, corps


def test_la_fermeture_du_panneau_est_memorisee_par_poste():
    """Le pendant de l'ouverture conditionnelle ci-dessus : sans écriture au
    moment de la fermeture, la condition de non-réouverture ne trouverait
    jamais de clé mémorisée et le panneau se rouvrirait quand même à chaque
    visite — le bug resterait entier malgré la garde ajoutée dans
    majReglagesPoste()."""
    code = _sans_commentaires(_lire(PAGE))
    i = code.index('function cablerFermetureReglagesPoste')
    corps = code[i:code.index('})();', i) + len('})();')]
    assert "addEventListener('toggle'" in corps, corps
    assert 'if(det.open) return' in corps, (
        "seule une FERMETURE (det.open devenu false) doit écrire la mémoire, "
        "pas une réouverture manuelle :\n" + corps)
    assert "localStorage.setItem('logx_aide_poste_vue'" in corps, corps


def test_le_rendu_echappe_ce_qu_il_injecte():
    """Les données viennent du dépôt, pas d'un tiers — mais elles passent par
    innerHTML, et le modèle vient de la CONFIGURATION de l'opérateur, donc
    d'une saisie. Échapper coûte une fonction ; ne pas le faire ouvre une
    injection sur un champ que l'utilisateur remplit lui-même."""
    code = _sans_commentaires(_lire(PAGE))
    i = code.index('function majReglagesPoste()')
    corps = code[i:code.index('\n  window.majReglagesPoste', i)]
    assert '_echapper(nom)' in corps, (
        'le modèle affiché vient de la config : il doit être échappé')


def test_la_consigne_ALC_de_la_page_ne_contredit_plus_les_sources():
    """La page affirmait en gras « ALC à ZÉRO […] Pas "dans la zone" », ce qui
    contredit frontalement le manuel de l'IC-7300 (« adjust the device's output
    level within the ALC zone ») et n'est pas dans le guide WSJT-X. Formulation
    revue le 20/08/2026 sur décision de F4GLD."""
    code = _sans_commentaires(_lire(PAGE))
    assert 'Pas « dans la zone »' not in code, (
        "la page ne doit plus opposer catégoriquement « dans la zone », que le "
        'manuel du poste prescrit')
    assert 'puissance HF commence tout' in code, (
        'la page doit porter le critère du guide officiel')
