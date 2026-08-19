# -*- coding: utf-8 -*-
"""FT8 : un même QSO ne doit pas entrer DEUX FOIS au carnet.

DÉFAUT RÉEL, 19/08/2026, station F4GLD, 14,074 MHz. CT1END/P enregistré deux
fois à 68 s d'écart :

    10:46:32   rst_sent='-10'  rst_rcvd='+08'   (fiche complète, séquenceur)
    10:47:40   rst_sent=''     rst_rcvd=''      (fiche vide)

Les deux avec source='ft8_natif'. Deux causes indépendantes, toutes deux
nécessaires au défaut :

 1. offrirLogQso(call, infos) posait « qsoInfosEnAttente = infos || null » SANS
    CONDITION. Sa garde anti-écrasement ne compare que l'INDICATIF : pour le
    même indicatif elle ne se déclenche pas, et un second appel sans reports
    détruisait en silence ceux du premier.
 2. Le second bandeau était RIGOUREUSEMENT IDENTIQUE au premier — même texte,
    même bouton, aucune mention du fait que ce QSO venait d'être enregistré.
    Rien à l'écran ne distinguait « valide ce QSO » de « enregistre-le une
    seconde fois ».

Et AUCUN filet côté serveur : add_qso_to_log saute intégralement la détection
de doublon quand usage_mode vaut 'simple' (logx_http.py, « if not
simple_mode ») — or 'simple' est le mode du carnet perso, le plus courant.
Vérifié en lisant le code, pas supposé.

CE QUE CES TESTS VÉRIFIENT SUR LA PAGE RÉELLE. Le banc de
test_ft8_sequenceur.py RÉIMPLÉMENTE offrirLogQso dans son mannequin : un test
de comportement écrit contre ce mannequin ne contraindrait que le mannequin
(piège déjà payé trois fois dans ce dépôt). Les propriétés sont donc tenues
ici par des assertions STRUCTURELLES sur le texte de logx_ft8.html, et par
l'exécution des fonctions RÉELLEMENT EXTRAITES du fichier.
"""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')

py_mini_racer = pytest.importorskip('py_mini_racer')


def _lire():
    with open(FT8_HTML, encoding='utf-8') as f:
        return f.read()


def _extraire_fonction(src, nom):
    debut = src.index('function ' + nom)
    prof, i = 0, src.index('{', debut)
    while True:
        if src[i] == '{':
            prof += 1
        elif src[i] == '}':
            prof -= 1
            if prof == 0:
                return src[debut:i + 1]
        i += 1


def _sans_commentaires(src):
    """Retire les lignes de commentaire // AVANT toute analyse.

    Ce fichier est très commenté, et ses pavés citent les identifiants qu'ils
    expliquent : chercher « qsoInfosEnAttente = infos » dans le texte brut est
    satisfait par le commentaire qui décrit le défaut CORRIGÉ."""
    return '\n'.join(l for l in src.split('\n')
                     if not l.strip().startswith('//'))


@pytest.fixture(scope='module')
def src():
    return _lire()


@pytest.fixture(scope='module')
def fusion(src):
    """Exécute fusionnerInfos EXTRAITE de la page — pas une réécriture."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_extraire_fonction(src, 'fusionnerInfos'))
    return ctx


# ═══════════════════════════════════════════════════════════════════════════
# §1. LA PROPRIÉTÉ CENTRALE — une valeur vide n'écrase jamais une valeur connue
# ═══════════════════════════════════════════════════════════════════════════

CAS_APPAUVRISSANTS = [
    ('rien du tout', 'undefined'),
    ('objet vide', '{}'),
    ('null', 'null'),
    ('reports vides', "{rst_sent:'', rst_rcvd:''}"),
    ('branche « elle a déjà conclu »', "{rst_rcvd:'', locator:'', dist:0}"),
    ('rst_sent codé en dur à vide', "{rst_sent:'', rst_rcvd:'+08'}"),
]


@pytest.mark.parametrize('nom,appauvri', CAS_APPAUVRISSANTS)
def test_une_offre_complete_survit_a_une_offre_appauvrie(fusion, nom, appauvri):
    """LA propriété. C'est exactement ce qui a produit la fiche vide du 19/08 :
    les reports réellement échangés avec CT1END/P ont été remplacés par des
    chaînes vides, sans que l'écran change d'un pixel."""
    r = fusion.eval(
        "JSON.stringify(fusionnerInfos("
        "{rst_sent:'-10', rst_rcvd:'+08', locator:'IM58', dist:1234}, "
        + appauvri + "))")
    assert '-10' in r and '+08' in r, (
        'cas « %s » : les reports ont été perdus -> %s' % (nom, r))
    assert 'IM58' in r, 'cas « %s » : la grille a été perdue -> %s' % (nom, r)
    assert '1234' in r, 'cas « %s » : la distance a été perdue -> %s' % (nom, r)


def test_une_offre_plus_riche_ENRICHIT_bien_l_ancienne(fusion):
    """L'inverse doit rester vrai, sinon on aurait juste figé la première
    offre : une information NOUVELLE doit entrer. C'est le cas de la branche
    « elle a déjà conclu », qui apporte parfois un rst_rcvd utile."""
    r = fusion.eval(
        "JSON.stringify(fusionnerInfos({rst_sent:'-10'}, "
        "{rst_rcvd:'+08', locator:'IM58JQ'}))")
    assert '-10' in r and '+08' in r and 'IM58JQ' in r, r


def test_une_valeur_plus_recente_et_NON_vide_remplace_bien_l_ancienne(fusion):
    """Une correction délibérée doit passer : on garde l'ancienne valeur
    seulement quand la nouvelle est VIDE, jamais quand elle est différente."""
    r = fusion.eval(
        "JSON.stringify(fusionnerInfos({rst_sent:'-10'}, {rst_sent:'-15'}))")
    assert '-15' in r and '-10' not in r, r


def test_la_fusion_rend_toujours_les_quatre_champs(fusion):
    """confirmerLogQso lit inf.rst_sent/rst_rcvd/locator/dist : un champ absent
    partirait en undefined dans le POST."""
    import json
    d = json.loads(fusion.eval('JSON.stringify(fusionnerInfos(null, null))'))
    assert set(d) == {'rst_sent', 'rst_rcvd', 'locator', 'dist'}, d


# ═══════════════════════════════════════════════════════════════════════════
# §2. LA STRUCTURE — le défaut ne doit pas pouvoir revenir par la porte
# ═══════════════════════════════════════════════════════════════════════════

def test_offrirLogQso_ne_pose_PLUS_les_infos_sans_condition(src):
    """L'affectation d'origine, « qsoInfosEnAttente = infos || null », est LE
    défaut. La chercher dans le texte brut ne suffit pas : le pavé qui explique
    le correctif la cite. On analyse donc le CORPS de la fonction, commentaires
    retirés."""
    corps = _sans_commentaires(_extraire_fonction(src, 'offrirLogQso'))
    assert not re.search(r'qsoInfosEnAttente\s*=\s*infos\b', corps), (
        "offrirLogQso repose les infos telles quelles — l'écrasement "
        'appauvrissant est de retour : %r' % corps[:400])


def test_offrirLogQso_FUSIONNE_avec_ce_qui_est_deja_en_attente(src):
    """Exiger une STRUCTURE, pas une présence : l'appel doit passer l'ancienne
    valeur ET la nouvelle, dans cet ordre. « fusionnerInfos(infos) » seul
    compilerait et perdrait tout."""
    corps = _sans_commentaires(_extraire_fonction(src, 'offrirLogQso'))
    assert re.search(
        r'qsoInfosEnAttente\s*=\s*fusionnerInfos\(\s*qsoInfosEnAttente\s*,\s*infos\s*\)',
        corps), ('offrirLogQso doit fusionner l\'ancienne offre avec la '
                 'nouvelle : %r' % corps[:400])


def test_changer_d_indicatif_remet_bien_les_infos_a_zero(src):
    """La fusion ne doit JAMAIS traverser un changement de station : coller les
    reports de CT1END/P sur le QSO suivant serait pire que la fiche vide."""
    corps = _sans_commentaires(_extraire_fonction(src, 'offrirLogQso'))
    i = corps.index('qsoEnAttente !== call')
    zone = corps[i:i + 300]
    assert re.search(r'qsoInfosEnAttente\s*=\s*null', zone), (
        'un autre indicatif doit repartir de zéro : %r' % zone[:250])


def test_le_bandeau_DIT_que_le_QSO_vient_d_etre_enregistre(src):
    """Le cœur du défaut n'était pas technique mais d'INTUITIVITÉ : les deux
    offres étaient indiscernables à l'écran. Le second bandeau doit nommer
    l'état, sinon l'opérateur revalide de bonne foi."""
    corps = _sans_commentaires(_extraire_fonction(src, 'offrirLogQso'))
    assert 'ficheDejaEcrite(' in corps, (
        'offrirLogQso doit consulter ce qui a déjà été écrit : %r' % corps[:400])
    assert 'DÉJÀ ENREGISTRÉ' in corps, (
        "le bandeau doit le DIRE, pas seulement le savoir : %r" % corps[:400])
    # Et l'avertissement doit être REMIS À BLANC quand il ne s'applique pas —
    # un avertissement collant ferait douter de tous les QSO suivants.
    i = corps.index('ficheDejaEcrite(')
    zone = corps[i:i + 900]
    assert re.search(r'else\s*\{[^}]*display\s*=\s*.none.', zone, re.S), (
        "l'avertissement doit disparaître quand il ne s'applique plus : %r"
        % zone[:400])


def test_l_element_d_avertissement_existe_et_est_masque_au_depart(src):
    """Un bandeau permanent « DÉJÀ ENREGISTRÉ » au chargement serait un
    contresens."""
    m = re.search(r'<span id="qsoPromptDeja"[^>]*>', src)
    assert m, 'élément d\'avertissement introuvable dans le HTML'
    assert 'display:none' in m.group(0), (
        'il doit être masqué à la livraison : %r' % m.group(0))
    assert 'role="alert"' in m.group(0), (
        'il apparaît en cours de session : il doit être annoncé aux lecteurs '
        "d'écran : %r" % m.group(0))


# ═══════════════════════════════════════════════════════════════════════════
# §3. LA MÉMOIRE DES FICHES ÉCRITES
# ═══════════════════════════════════════════════════════════════════════════

def test_seule_une_ecriture_REUSSIE_est_memorisee(src):
    """Mémoriser une fiche qui n'est jamais partie ferait refuser la seule
    chose à faire : la ressaisir. L'enregistrement doit être DANS la branche de
    succès, aux côtés du journal de session qui obéit déjà à cette règle."""
    corps = _sans_commentaires(_extraire_fonction(src, 'confirmerLogQso')
                               if 'function confirmerLogQso' in src
                               else src)
    i = corps.index('ajouterAuJournalSession(')
    zone = corps[i:i + 500]
    assert 'dejaEcrits.push(' in zone, (
        "la mémoire doit être posée dans la branche de succès, juste après le "
        'journal de session : %r' % zone[:400])
    # Structure, pas présence : ce qui est poussé doit porter la CLÉ, sans quoi
    # ficheDejaEcrite ne retrouvera jamais rien.
    assert re.search(r'dejaEcrits\.push\(\{\s*cle:\s*cleFiche\(', zone), zone[:400]


def test_la_fenetre_de_relog_est_lue_et_raisonnable(src):
    """Trop courte, elle ne protège rien ; trop longue, elle empêche un vrai
    second QSO. On LIT la valeur au lieu de reconnaître un motif : « 1 * 60 *
    1000 » satisfaisait une regex qui ne vérifiait que la forme."""
    m = re.search(r'RELOG_FENETRE_MS\s*=\s*(\d+)\s*\*\s*60\s*\*\s*1000', src)
    assert m, 'constante de fenêtre introuvable'
    minutes = int(m.group(1))
    assert 5 <= minutes <= 60, (
        'fenêtre de %d min : hors de la plage défendable' % minutes)


def test_la_memoire_ne_croit_pas_indefiniment(src):
    """Quinze jours d'expédition non-stop : une liste qui ne se purge jamais
    finit par coûter à chaque offre."""
    corps = _sans_commentaires(_extraire_fonction(src, 'ficheDejaEcrite'))
    assert 'filter(' in corps and 'limite' in corps, (
        'ficheDejaEcrite doit purger les entrées périmées : %r' % corps)


def test_la_cle_distingue_les_bandes(src):
    """Le même correspondant sur 20 m puis sur 40 m, ce sont DEUX QSO. Une clé
    sur le seul indicatif refuserait le second."""
    corps = _sans_commentaires(_extraire_fonction(src, 'cleFiche'))
    assert 'band' in corps, corps
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_extraire_fonction(src, 'cleFiche'))
    assert ctx.eval("cleFiche('CT1END/P','14')") != ctx.eval("cleFiche('CT1END/P','7')")
    # Et l'indicatif doit être normalisé : 'ct1end/p' est le même QSO.
    assert ctx.eval("cleFiche('ct1end/p','14')") == ctx.eval("cleFiche('CT1END/P','14')")


# ═══════════════════════════════════════════════════════════════════════════
# §4. LA COURSE AVEC LE SÉQUENCEUR
# ═══════════════════════════════════════════════════════════════════════════

def test_pas_d_offre_concurrente_pendant_une_sequence_sur_la_meme_station(src):
    """La branche « elle a déjà conclu » est placée AVANT la garde « une seule
    séquence à la fois » et rend null sans rien arrêter : elle pouvait ouvrir
    une offre creuse pendant que le séquenceur travaillait la même station.
    Selon l'ordre d'arrivée, c'est l'offre creuse qui gagnait."""
    zone = _sans_commentaires(src[src.index('if(qsoDejaConclu'):][:900])
    assert re.search(
        r'if\(\s*qsoDejaConclu\s*&&\s*seq\s*&&\s*seq\.cible\s*===\s*call\s*\)',
        zone), ('la branche doit céder le pas à la séquence en cours : %r'
                % zone[:400])
    # Et elle doit SORTIR, pas seulement afficher quelque chose.
    sortie = zone[:zone.index('offrirLogQso')]
    assert 'return null;' in sortie, (
        'elle doit rendre la main avant toute offre : %r' % sortie[-300:])


def test_la_branche_conclue_ne_code_plus_rst_sent_a_vide(src):
    """« rst_sent: '' » codé en dur fabriquait structurellement une fiche sans
    report, et écrasait une offre plus riche. Champ OMIS plutôt que vidé : la
    fusion peut alors le compléter."""
    i = src.index('if(qsoDejaConclu){')
    zone = _sans_commentaires(src[i:i + 700])
    j = zone.index('offrirLogQso(')
    objet = zone[j:j + 260]
    assert "rst_sent" not in objet, (
        'rst_sent ne doit plus être posé ici, même à vide : %r' % objet)
