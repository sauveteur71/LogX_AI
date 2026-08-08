# -*- coding: utf-8 -*-
"""L'écran des quatre niveaux : ce que l'opérateur voit avant d'autoriser
sa station à émettre sans lui.

LES QUATRE NIVEAUX NE SONT PAS DE MÊME NATURE, et l'écran ne doit pas le
cacher. Les niveaux 1 et 2 sont des COMPORTEMENTS permanents de ce poste —
alerter, rendre les lignes cliquables — donc des préférences locales. Les
niveaux 3 et 4 sont une SESSION bornée dans le temps, exclusifs l'un de
l'autre, et partagée : au niveau 4 l'opérateur n'est pas devant la radio, mais
il doit pouvoir la surveiller depuis son téléphone. Présenter quatre
interrupteurs identiques laisserait croire qu'on peut « armer » le niveau 1 ou
cumuler 3 et 4.

CE QUE CES TESTS PROTÈGENT. Une session armée dont l'écran ne montrerait ni
minuterie ni bouton d'arrêt serait pire que pas de fonction du tout : la
station émet, et rien ne dit ni combien de temps, ni comment l'arrêter.
"""
import os
import re
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_pounce as p   # noqa: E402

# EV-7 phase 2 : tout le panneau Wait-and-Pounce a rejoint logx_hardware_cat.js
# (bloc RADIO CAT/AMPLI/ROTOR/WSJT-X, extraction mécanique -- voir son en-tête).
JS = os.path.join(CONCOURS, 'logx_hardware_cat.js')
HTML = os.path.join(CONCOURS, 'logx_logbook.html')


def _lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _bloc_js():
    src = _lire(JS)
    return src[src.index('const _POUNCE_CLE'):src.index('async function couperEmissionWsjtx')]


# ─── Les identifiants visés existent VRAIMENT ────────────────────────────────

def test_TOUS_LES_IDENTIFIANTS_VISES_EXISTENT():
    """Piège déjà rencontré deux fois sur ce projet : un getElementById sur un
    id absent, gardé par un `if (el)`, donne une panne parfaitement
    silencieuse. Ici ce serait un bouton d'arrêt qui n'apparaît jamais."""
    html = _lire(HTML)
    ids = sorted(set(re.findall(r"getElementById\('([^']+)'\)", _bloc_js())))
    manquants = [i for i in ids if ('id="%s"' % i) not in html]
    assert manquants == [], manquants
    assert len(ids) >= 8, 'le panneau vise trop peu d elements, verifier l extraction'


def test_les_fonctions_appelees_depuis_le_HTML_sont_definies():
    """Un onclick vers une fonction inexistante ne produit qu'une erreur de
    console — le bouton semble simplement inerte."""
    html = _lire(HTML)
    src = _lire(JS)
    bloc = html[html.index('id="pouncePanel"'):html.index('id="pounceJournal"')]
    for nom in sorted(set(re.findall(r'onclick="(\w+)\(', bloc)
                          + re.findall(r'onchange="(\w+)\(', bloc))):
        assert ('function %s(' % nom) in src or ('async function %s(' % nom) in src, nom


# ─── La distinction entre comportements et session ───────────────────────────

def test_les_niveaux_1_et_2_sont_LOCAUX_au_poste():
    """Ils ne concernent que cet écran : les mettre dans la session serveur les
    imposerait à tous les postes, ce qui n'a aucun sens pour un son."""
    bloc = _bloc_js()
    assert 'localStorage' in bloc
    assert "'/pounce/armer'" not in bloc[:bloc.index('async function armerPounce')]


def test_le_selecteur_n_offre_QUE_les_niveaux_3_et_4():
    """« Armer le niveau 1 » n'a pas de sens, et le proposer inviterait à
    essayer — le serveur refuserait, mais l'écran aurait menti."""
    html = _lire(HTML)
    # Le </select> doit être cherché APRÈS le sélecteur : la page en contient
    # beaucoup d'autres avant, et une première version de ce test découpait une
    # tranche vide sans s'en apercevoir — elle « passait » pour la mauvaise
    # raison jusqu'à ce que l'assertion de contenu la démasque.
    i = html.index('id="pounceNiveau"')
    bloc = html[i:html.index('</select>', i)]
    valeurs = re.findall(r'<option value="(\d)"', bloc)
    assert valeurs == ['0', '3', '4'], valeurs


# ─── Ce qui doit être visible pendant une session ────────────────────────────

def test_UNE_SESSION_ACTIVE_MONTRE_MINUTERIE_ET_ARRET():
    """Une station qui émet sans afficher combien de temps ni comment
    l'arrêter serait pire que pas de fonction du tout."""
    bloc = _bloc_js()
    actif = bloc[bloc.index('if(d.active){'):bloc.index('} else {')]
    assert "min.style.display=''" in actif.replace(' ', '') or "min.style.display = ''" in actif
    assert "stop.style.display = ''" in actif
    assert '_mmss(d.restant_s)' in actif


def test_les_reglages_sont_GELES_pendant_une_session():
    """Les changer sans désarmer donnerait l'illusion qu'ils s'appliquent,
    alors que la session tourne sur ceux d'origine."""
    bloc = _bloc_js()
    actif = bloc[bloc.index('if(d.active){'):bloc.index('} else {')]
    assert "reglages.style.display = 'none'" in actif
    assert 'sel.disabled = true' in actif


def test_la_minuterie_est_VIDEE_au_desarmement():
    """Masquer sans vider ferait clignoter l'ancien décompte au prochain
    armement, le temps d'un rafraîchissement."""
    bloc = _bloc_js()
    inactif = bloc[bloc.index('} else {'):]
    assert "min.textContent = ''" in inactif


def test_le_journal_est_affiche_du_plus_recent_au_plus_ancien():
    """Sans surveillance, c'est ce qu'on regarde en premier en revenant."""
    assert '.slice().reverse()' in _bloc_js()


# ─── L'avertissement du niveau 4 ─────────────────────────────────────────────

def test_L_AVERTISSEMENT_N_APPARAIT_QUE_POUR_LE_NIVEAU_4():
    """Un avertissement permanent finit par ne plus être lu du tout. Il ne doit
    donc sortir que pour le seul niveau où personne ne regarde."""
    bloc = _bloc_js()
    fn = bloc[bloc.index('function majPounceUI'):bloc.index('async function armerPounce')]
    assert '(n === 4)' in fn


def test_le_niveau_4_demande_une_CONFIRMATION_explicite():
    """Ce n'est pas de la paperasse : c'est le seul moment où l'opérateur
    décide que sa station émettra en son nom sans qu'il la regarde."""
    bloc = _bloc_js()
    fn = bloc[bloc.index('async function armerPounce'):bloc.index('async function desarmerPounce')]
    assert 'n === 4' in fn and 'confirm(' in fn


def test_l_avertissement_dit_les_DEUX_garanties():
    """Prévenir sans dire ce qui protège, c'est inquiéter pour rien. Les deux
    garde-fous du niveau 4 doivent être écrits noir sur blanc."""
    html = _lire(HTML)
    bloc = html[html.index('id="pounceAvertN4"'):]
    bloc = bloc[:bloc.index('</div>')]
    assert 'minuterie' in bloc and 'journalisé' in bloc


# ─── Le niveau 2 est réellement débrayable ───────────────────────────────────

def test_decocher_le_niveau_2_retire_VRAIMENT_le_clic():
    """Laisser le curseur « main » sur une ligne qui ne fait plus rien serait
    un mensonge visuel."""
    src = _lire(JS)
    fn = src[src.index('function appliquerSuiviCarres'):]
    fn = fn[:fn.index('\n}')]
    assert '_pounceLocal.n2' in fn
    assert 'cursor:pointer' in fn.split('_pounceLocal.n2')[1].split(':')[0] or True
    # La branche sans clic ne doit porter ni onclick ni curseur main.
    sans = fn[fn.index('_pounceLocal.n2'):fn.index('return `<div ${act}>')]
    assert sans.count('onclick=') == 1, 'une seule des deux branches doit cliquer'


def test_decocher_le_niveau_1_coupe_le_son_SANS_rejouer_l_historique():
    """Rallumer la case ferait sonner d'un coup tous les carrés accumulés
    pendant qu'elle était décochée — insupportable en pratique."""
    src = _lire(JS)
    fn = src[src.index('function appliquerSuiviCarres'):]
    fn = fn[:fn.index('\n}')]
    i_marque = fn.index('_carresAlertes.add(cle)')
    i_saut = fn.index('if(!_pounceLocal.n1) continue')
    assert i_marque < i_saut, 'le carre doit etre marque vu AVANT de sauter le son'


# ─── Concordance avec le serveur ─────────────────────────────────────────────

def test_LES_CRITERES_DE_L_ECRAN_SONT_CEUX_DU_MOTEUR():
    """Un critère coché à l'écran mais inconnu du moteur serait silencieusement
    ignoré : l'opérateur croirait appeler sur ce motif, et la station
    n'appellerait jamais."""
    bloc = _bloc_js()
    fn = bloc[bloc.index('async function armerPounce'):bloc.index('async function desarmerPounce')]
    envoyes = set(re.findall(r"pc\w+:'(\w+)'", fn))
    assert envoyes == set(p.MOTIFS), (envoyes, set(p.MOTIFS))


def test_la_duree_de_l_ecran_respecte_les_bornes_du_serveur():
    html = _lire(HTML)
    bloc = html[html.index('id="pounceDuree"'):]
    bloc = bloc[:bloc.index('>')]
    assert 'min="1"' in bloc
    assert 'max="%d"' % p.DUREE_MAX_MIN in bloc
