# -*- coding: utf-8 -*-
"""Onglet masque : aucun minuteur ne doit continuer a interroger le serveur.

Mesure a l'origine du correctif (Chrome, page ouverte puis onglet masque) :
CHASSE 46 s masquee -> 12 requetes, PROPAGATION 68 s -> 27. Aucune n'etait
regardee par personne. Depuis la scission PROPAG/CHASSE l'operateur garde
naturellement les DEUX pages ouvertes a cote du log, donc deux jeux complets
de minuteurs + deux barres de statut.

Le correctif est un ordonnanceur unique, window.rcPoll (logx_statusbar.js) :
il ARRETE les minuteurs (clearInterval) sur document.hidden et rejoue au
retour ceux dont l'echeance est passee.

Pourquoi figer ca par des tests plutot que se fier a une relecture :

1) Un `setInterval` en trop ne casse RIEN de visible. La page s'affiche, les
   donnees sont fraiches, les tests fonctionnels passent : le seul symptome
   est du trafic permanent vers le serveur et les sources externes (cluster,
   POTA/SOTA/WWFF, PSK Reporter, RBN), invisible sans mesure dediee. C'est
   exactement le genre de regression qu'une relecture laisse passer.

2) La regle n'est pas « tout suspendre » mais « suspendre ce qui appelle le
   reseau ». Les minuteurs purement locaux (compte a rebours, extrapolation
   du timer de changement de bande, horodatage de sauvegarde) restent en
   setInterval nu. Ce test verifie donc AUSSI l'inverse : qu'aucun de ces
   trois-la ne s'est mis a faire un fetch() entre-temps — sinon la
   justification de les laisser tourner tombe, en silence.
"""
import os
import re

CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATUSBAR = os.path.join(CONCOURS_DIR, 'logx_statusbar.js')
CHASSE = os.path.join(CONCOURS_DIR, 'logx_chasse.html')

# Rafraichisseurs de la barre de statut qui APPELLENT LE SERVEUR : tous doivent
# passer par rcPoll (suspendus onglet masque).
POLLS_RESEAU = [
    'refreshRate',           # /coach/state
    'refreshSolar',          # /data/propagation
    'refreshBeacon',         # /beacons/now  (5 s : le plus bavard)
    'refreshNetworkStatus',  # /data/network_status
    'refreshRules',          # /data/rules_status
    'refreshUpdateCheck',    # /app/update_check
    'refreshErrorsCheck',    # /debug/errors
]

# Rafraichisseurs purement locaux : setInterval nu autorise, A CONDITION qu'ils
# ne fassent aucune requete (verifie plus bas).
TICKS_LOCAUX = ['refreshCountdown', 'tickBandChange', 'refreshSave']

# Chargeurs periodiques de la page CHASSE (tous font un fetch).
CHARGEURS_CHASSE = ['loadSpots', 'loadPota', 'loadSota', 'loadWwff', 'loadWca']


def lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def corps_fonction(source, nom):
    """Corps d'une `function nom(...){...}`, par appariement d'accolades."""
    m = re.search(r'function\s+' + re.escape(nom) + r'\s*\([^)]*\)\s*\{', source)
    assert m, "fonction %s introuvable" % nom
    i = m.end() - 1
    profondeur = 0
    for j in range(i, len(source)):
        if source[j] == '{':
            profondeur += 1
        elif source[j] == '}':
            profondeur -= 1
            if profondeur == 0:
                return source[i:j + 1]
    raise AssertionError("accolades non appariees pour %s" % nom)


def test_rcpoll_expose_et_arrete_les_minuteurs_quand_masque():
    src = lire(STATUSBAR)
    assert 'window.rcPoll = rcPoll' in src, \
        "rcPoll doit etre expose aux pages (window.rcPoll)"
    assert "addEventListener('visibilitychange'" in src, \
        "sans ecoute de visibilitychange, rien n'est jamais suspendu"
    # Un simple `if (document.hidden) return;` a l'interieur du tic ne suffit
    # pas : le minuteur continue de reveiller l'onglet. On exige clearInterval.
    assert 'clearInterval' in src, \
        "les minuteurs doivent etre ARRETES (clearInterval), pas seulement ignores"


def test_rcpoll_est_defini_avant_le_garde_fou_file():
    """Les pages font `window.rcPoll || repli` : si rcPoll n'existait pas en
    file://, elles retomberaient silencieusement sur du setInterval nu."""
    src = lire(STATUSBAR)
    assert src.index('window.rcPoll = rcPoll') < src.index("location.protocol === 'file:'"), \
        "rcPoll doit etre defini avant le retour anticipe file:"


def test_rcpoll_rejoue_les_echeances_depassees_au_retour():
    """Sans rattrapage, revenir sur l'onglet afficherait des donnees perimees
    jusqu'au prochain tic (jusqu'a 20 min pour la tropo)."""
    src = lire(STATUSBAR)
    assert re.search(r'now\s*-\s*p\.last\s*>=\s*p\.ms', src), \
        "le retour a l'ecran doit rejouer les polls dont l'echeance est passee"


def test_tous_les_polls_reseau_de_la_barre_passent_par_rcpoll():
    src = lire(STATUSBAR)
    for nom in POLLS_RESEAU:
        assert re.search(r'rcPoll\(\s*' + nom + r'\s*,', src), \
            "%s doit etre enregistre via rcPoll" % nom
        assert not re.search(r'setInterval\(\s*' + nom + r'\s*,', src), \
            "%s tourne encore en setInterval nu : jamais suspendu" % nom


def test_les_ticks_locaux_ne_font_aucune_requete():
    """Justification de les laisser en setInterval nu — a re-verifier a chaque
    evolution, sinon un fetch() ajoute la-dedans reintroduirait le defaut."""
    src = lire(STATUSBAR)
    for nom in TICKS_LOCAUX:
        corps = corps_fonction(src, nom)
        assert 'fetch(' not in corps, (
            "%s fait desormais une requete : il doit passer par rcPoll "
            "(ou perdre son setInterval nu)" % nom)


def test_chasse_n_a_plus_aucun_minuteur_de_chargement_nu():
    src = lire(CHASSE)
    for nom in CHARGEURS_CHASSE:
        assert not re.search(r'setInterval\(\s*' + nom + r'\s*,', src), \
            "%s : minuteur non suspendu quand l'onglet est masque" % nom
        assert re.search(r'rcPollOr\(\s*' + nom + r'\s*,', src), \
            "%s doit etre enregistre via rcPollOr (rcPoll + repli)" % nom


def test_chasse_ne_garde_setinterval_que_pour_le_repli():
    """Le seul setInterval() tolere sur la page est celui du repli utilise
    quand la barre de statut (donc rcPoll) est absente."""
    src = lire(CHASSE)
    occurrences = re.findall(r'setInterval\([^)]*\)', src)
    assert len(occurrences) == 1, \
        "setInterval attendu une seule fois (repli), trouve : %r" % occurrences
    assert 'window.rcPoll ||' in src, \
        "le repli doit etre conditionne a l'absence de rcPoll"
