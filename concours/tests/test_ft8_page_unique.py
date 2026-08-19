# -*- coding: utf-8 -*-
"""Une seule page FT8 à la fois, et retour sur celle qui est déjà ouverte.

Signalé par F4GLD (19/08/2026) : « le programme est capable d'ouvrir plusieurs
page ft8 [...] si une page ft8 est ouverte et si je clic sur numerique FT8 je
dois arriver sur la page deja ouverte », puis, sur la question de savoir ce que
devrait faire une seconde page : « ben elle ne devrait pas s'ouvrir tout
simplement, ça ne devrait pas être possible d'ouvrir deux pages ft8, quel
intérêt ? ».

IL N'Y EN A AUCUN, ET IL Y A UN DANGER. Deux pages FT8, ce sont deux décodeurs
qui se disputent la carte son, et surtout DEUX COMMANDES DE PTT sur la même
radio, chacune ignorant l'existence de l'autre.

DEUX DÉFAUTS DISTINCTS, tous deux réels :

1. Le hub appelait window.open(url, nom) à chaque clic. Le nom suffit au
   navigateur pour RÉUTILISER la fenêtre, mais passer l'URL la fait aussi
   NAVIGUER : la page était rechargée, donc le décodeur relancé, l'audio coupé
   et les décodages de la session perdus. Sans focus(), rien ne la ramenait au
   premier plan — de l'extérieur ça ressemble à « il ne s'est rien passé », ce
   qui pousse à ouvrir autrement. C'est ainsi qu'on se retrouve à deux.

2. Rien n'empêchait deux pages vivantes atteintes par des chemins différents
   (un onglet ordinaire + une fenêtre détachée).

CE QUE CES TESTS NE PROUVENT PAS : le comportement réel du navigateur. Les
quatre scénarios ont été éprouvés en navigateur (Chrome, serveur local) :
1re page vivante ; 2e page refusée, décodeur absent ; F5 sur la page vivante
qui RESTE vivante (pas de verrouillage) ; fermeture de la 1re et reprise par
la 2e. Ces assertions-ci figent la structure qui produit ce comportement.
"""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')
HUB_HTML = os.path.join(CONCOURS, 'logx_modes_numeriques.html')


def _lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _extraire_fonction(src, nom):
    """Comptage d'accolades — une regex non gloutonne s'arrêterait à la
    première accolade fermante imbriquée."""
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
    """Un test qui cherche un identifiant dans du texte brut est satisfait par
    le pavé qui l'EXPLIQUE — piège payé plusieurs fois dans ce dépôt."""
    return '\n'.join(l for l in src.split('\n')
                     if not l.strip().startswith('//'))


@pytest.fixture(scope='module')
def ft8():
    return _lire(FT8_HTML)


@pytest.fixture(scope='module')
def hub():
    return _lire(HUB_HTML)


# ═══════════════════════════════════════════════════════════════════════════
# §1. LE HUB — revenir sur la page ouverte, sans la recharger
# ═══════════════════════════════════════════════════════════════════════════

def test_le_hub_n_impose_pas_l_URL_a_une_fenetre_existante(hub):
    """LE défaut d'origine. window.open(url, nom) réutilise la fenêtre MAIS la
    fait naviguer : décodeur relancé, audio coupé, session perdue. On ouvre
    donc sans URL, et on ne charge la page que si la fenêtre est neuve."""
    corps = _sans_commentaires(_extraire_fonction(hub, 'ouvrirFenetreDetachee'))
    assert re.search(r"window\.open\(\s*''\s*,\s*nom", corps), (
        "le hub doit ouvrir SANS URL pour ne pas recharger une fenêtre "
        'existante : %r' % corps[:300])
    assert 'window.open(url, nom' not in corps, (
        "l'URL ne doit plus être passée d'emblée : %r" % corps[:300])


def test_le_hub_ne_charge_la_page_que_si_la_fenetre_est_neuve(hub):
    """Sans cette condition, on ouvrirait sans URL puis on naviguerait quand
    même — le rechargement reviendrait par la fenêtre."""
    corps = _sans_commentaires(_extraire_fonction(hub, 'ouvrirFenetreDetachee'))
    assert 'about:blank' in corps, (
        'une fenêtre neuve se reconnaît à about:blank : %r' % corps[:300])
    assert re.search(r'if\s*\(\s*neuve\s*\)\s*w\.location\.href\s*=\s*url',
                     corps), (
        'la navigation doit être CONDITIONNELLE à une fenêtre neuve : %r'
        % corps[:400])


def test_le_hub_ramene_la_fenetre_au_premier_plan(hub):
    """Sans focus(), la fenêtre réutilisée reste derrière : de l'extérieur ça
    ressemble à « il ne s'est rien passé », et c'est ce qui pousse à ouvrir
    la page autrement."""
    corps = _sans_commentaires(_extraire_fonction(hub, 'ouvrirFenetreDetachee'))
    assert 'w.focus()' in corps, corps[:300]


# ═══════════════════════════════════════════════════════════════════════════
# §2. LA PAGE FT8 — une seule instance vivante
# ═══════════════════════════════════════════════════════════════════════════

def test_le_garde_fou_agit_AVANT_que_quoi_que_ce_soit_ne_demarre(ft8):
    """Un garde-fou posé après le démarrage du décodeur ou des minuteurs ne
    servirait à rien : la seconde page aurait déjà ouvert la carte son."""
    i_garde = ft8.index('rc_ft8_vivant')
    for demarrage in ("setInterval(horloge", "pollRig()",
                      "setInterval(verifierCycle"):
        assert i_garde < ft8.index(demarrage), (
            'le garde-fou doit précéder %r' % demarrage)


def test_une_seconde_page_ne_demarre_NI_decodeur_NI_emission(ft8):
    """La demande était explicite : « elle ne devrait pas s'ouvrir tout
    simplement ». On sort de la fonction — pas de décodeur, pas de PTT."""
    i = ft8.index('rc_ft8_vivant')
    zone = ft8[i:i + 4000]
    assert 'ft8AutreInstance()' in zone, zone[:400]
    m = re.search(r'if\(ft8AutreInstance\(\)\)\{(.*?)\n  \}', zone, re.S)
    assert m, 'le refus doit être un bloc conditionnel : %r' % zone[:400]
    assert 'return;' in m.group(1), (
        'la page refusée doit SORTIR, pas continuer à moitié : %r'
        % m.group(1)[-300:])


def test_la_page_refusee_explique_le_danger_et_offre_une_sortie(ft8):
    """Un écran vide serait pire que le défaut corrigé. Intuitivité : on dit
    ce qui se passe, pourquoi, et ce qu'on peut faire."""
    i = ft8.index('FT8 est déjà ouvert')
    zone = ft8[i:i + 1800]
    assert 'PTT' in zone, (
        'la raison doit être dite : deux PTT sur la même radio')
    assert 'ft8AllerVers' in zone, 'un bouton pour rejoindre la page ouverte'
    assert 'logx_modes_numeriques.html' in zone, 'un retour vers le hub'


def test_un_rechargement_ne_verrouille_PAS_l_operateur_dehors(ft8):
    """LE risque de ce correctif — pire que le défaut. Sans identité stable,
    un simple F5 se verrait lui-même comme « une autre page ». sessionStorage
    survit au rechargement mais pas à la fermeture : c'est exactement la durée
    de vie voulue."""
    # On exige la LECTURE, pas la simple présence de sessionStorage : le
    # bloc écrit AUSSI l'identifiant, et un test qui cherchait juste
    # « sessionStorage » restait vert quand on remplaçait la lecture par
    # `let ft8MonId = null` — c'est-à-dire quand un F5 se voyait lui-même
    # comme une autre page. Trouvé par contre-épreuve ; piège « présence au
    # lieu de structure » déjà payé plusieurs fois ici.
    assert "sessionStorage.getItem('rc_ft8_id')" in ft8, (
        "l'identité doit être RELUE au chargement (survit au F5, pas à la "
        'fermeture) — sans quoi un rechargement se verrouille dehors')
    assert "sessionStorage.setItem('rc_ft8_id'" in ft8, (
        "et mémorisée au premier chargement")
    corps = _sans_commentaires(_extraire_fonction(ft8, 'ft8AutreInstance'))
    assert 'ft8MonId' in corps, (
        'une instance portant MON identifiant n\'est pas « une autre » : %r'
        % corps)


def test_une_fermeture_libere_la_place_immediatement(ft8):
    """Sinon il faudrait attendre la péremption avant de pouvoir rouvrir, ce
    qui ressemblerait à un blocage."""
    assert "addEventListener('pagehide'" in ft8, (
        'la libération doit se faire sur pagehide')
    i = ft8.index("addEventListener('pagehide'")
    zone = _sans_commentaires(ft8[i:i + 600])
    assert 'removeItem' in zone, zone[:300]
    assert 'lu.id === ft8MonId' in zone, (
        'on ne libère que SA propre place, jamais celle d\'une autre : %r'
        % zone[:300])


def test_un_plantage_ne_condamne_pas_FT8_pour_toujours(ft8):
    """Un navigateur qui plante n'exécute pas pagehide. Sans péremption, la
    clé resterait et FT8 serait inaccessible à jamais."""
    m = re.search(r'FT8_PEREMPTION_MS\s*=\s*(\d+)', ft8)
    assert m, 'aucune péremption définie'
    peremption = int(m.group(1))
    b = re.search(r'FT8_BATTEMENT_MS\s*=\s*(\d+)', ft8)
    assert b, 'aucun battement défini'
    battement = int(b.group(1))
    assert peremption > 2 * battement, (
        'la péremption (%d ms) doit laisser passer plusieurs battements '
        '(%d ms) : une page occupée par un décodage peut en rater un'
        % (peremption, battement))
    assert peremption <= 15000, (
        'péremption de %d ms : trop long après un plantage, l\'opérateur '
        'croirait à un blocage' % peremption)
    corps = _sans_commentaires(_extraire_fonction(ft8, 'ft8AutreInstance'))
    assert 'FT8_PEREMPTION_MS' in corps, (
        'la péremption doit être RÉELLEMENT appliquée à la lecture : %r'
        % corps)


def test_la_page_refusee_ne_reclame_pas_la_place(ft8):
    """Si elle battait aussi, les deux se voleraient la place à tour de rôle."""
    i = ft8.index('if(ft8AutreInstance())')
    j = ft8.index('function ft8Battre()')
    assert i < j, 'le refus doit précéder la prise de place'
    zone = ft8[i:j]
    assert 'ft8Battre' not in zone, (
        'la page refusée ne doit pas battre : %r' % zone[-400:])


def test_le_bouton_de_retour_n_ouvre_pas_une_fenetre_de_plus(ft8):
    """Piège évité : window.open('', 'rc_ft8') CRÉERAIT une fenêtre vide si la
    page vivante n'a pas été ouverte sous ce nom (onglet ordinaire) — soit
    exactement ce qu'on cherche à empêcher. On demande à l'instance vivante de
    se mettre au premier plan elle-même."""
    i = ft8.index('ft8AllerVers')
    zone = _sans_commentaires(ft8[i:i + 1200])
    assert 'window.open' not in zone, (
        'le bouton de retour ne doit ouvrir aucune fenêtre : %r' % zone[:400])
    assert 'FT8_CLE_FOCUS' in zone, zone[:400]
    assert "addEventListener('storage'" in ft8, (
        'la page vivante doit écouter la demande de premier plan')
