# -*- coding: utf-8 -*-
"""Une persistance suspendue doit se VOIR, sur toutes les pages.

load_failed existe depuis longtemps et protège correctement le carnet — mais
il n'a JAMAIS été visible : un seul print() vers une console que personne ne
regarde (le logiciel se lance sur une fenêtre de navigateur). Conséquence
mesurable : l'opérateur continue à logger dans un carnet qui ne s'écrit plus,
parfois des heures, et perd tout à la coupure.

Le nouveau garde-fou anti-destruction ne devait surtout pas refaire ça.

Deuxième défaut couvert ici, d'intuitivité pure : la barre affichait
« Sauvegarde : log 11:43 UTC ». Cet horodatage vient de
localStorage.rc_log_backup_time, une copie faite par la PAGE Logbook, qui vit
dans le navigateur et part avec le cache. La sauvegarde DISQUE, elle, ne tourne
que si un dossier est renseigné dans CONFIG — et elle est vide par défaut. La
ligne se lisait donc « ton carnet est sauvegardé » alors que rien n'avait
jamais quitté le navigateur.
"""
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BARRE = os.path.join(CONCOURS, 'logx_statusbar.js')
HTTP = os.path.join(CONCOURS, 'logx_http.py')


def _lire(p):
    with open(p, encoding='utf-8') as f:
        return f.read()


def _sans_commentaires(src):
    return '\n'.join(l for l in src.split('\n')
                     if not l.strip().startswith('//'))


# ═══════════════════════════════════════════════════════════════════════════
# §1. LE SERVEUR PUBLIE L'ÉTAT
# ═══════════════════════════════════════════════════════════════════════════

def test_log_status_publie_l_etat_de_persistance():
    """/log/status est le seul point que TOUTES les pages interrogent déjà."""
    src = _sans_commentaires(_lire(HTTP))
    i = src.index("if path == '/log/status'")
    zone = src[i:i + 2500]
    assert re.search(r"'persistance':\s*storage_etat_persistance\(\)", zone), (
        "/log/status doit publier l'état de la persistance : %r" % zone[-600:])


# ═══════════════════════════════════════════════════════════════════════════
# §2. LA BARRE PARTAGÉE L'AFFICHE
# ═══════════════════════════════════════════════════════════════════════════

def test_la_barre_interroge_l_etat_periodiquement():
    src = _sans_commentaires(_lire(BARRE))
    assert 'function refreshPersistance()' in src
    assert re.search(r'rcPoll\(\s*refreshPersistance\s*,\s*\d+\s*\)', src), (
        'la vérification doit être périodique, et via rcPoll pour être '
        "suspendue quand l'onglet est masqué")
    # ET tout de suite au chargement : attendre le premier tick laisserait
    # l'opérateur devant un écran normal alors que rien ne s'écrit.
    i = src.index('rcPoll(refreshPersistance')
    assert 'refreshPersistance();' in src[max(0, i - 300):i], (
        "l'état doit être lu dès le chargement, pas seulement au 1er tick")


def test_l_alarme_est_PERMANENTE_et_non_ignorable():
    """Un carnet qui ne s'écrit plus est un ÉTAT, pas une notification. Le
    bandeau de signalement existant (coin bas droit, bouton « Ignorer »,
    auto-masqué à 30 s) serait le mauvais véhicule."""
    src = _sans_commentaires(_lire(BARRE))
    i = src.index('function _majAlarmePersistance')
    corps = src[i:i + 2600]
    assert 'setTimeout' not in corps, (
        "l'alarme ne doit jamais se masquer toute seule : %r" % corps[:400])
    assert 'Ignorer' not in corps, (
        "on ne masque pas une perte de données d'un clic")
    assert "role', 'alert'" in corps or 'role="alert"' in corps, (
        'doit être annoncée aux lecteurs d\'écran')
    assert 'position:fixed;top:0' in corps, (
        'doit occuper le haut de la page, pas un coin')


def test_l_alarme_n_est_JAMAIS_expert_only():
    """Le mode simple est celui du débutant — exactement celui qui ne saura pas
    diagnostiquer seul. Le masquer là serait le pire des choix."""
    src = _lire(BARRE)
    i = src.index('function _majAlarmePersistance')
    assert 'expert-only' not in src[i:i + 2600]


def test_l_alarme_DISPARAIT_quand_tout_va_bien():
    """Une alarme collée à l'écran après le redémarrage ferait douter de tous
    les QSO suivants."""
    src = _sans_commentaires(_lire(BARRE))
    i = src.index('function _majAlarmePersistance')
    corps = src[i:i + 900]
    assert re.search(r'if\s*\(\s*!ko\s*\)', corps), corps[:400]
    assert re.search(r"display\s*=\s*'none'", corps), (
        "l'alarme doit être masquée quand l'état redevient bon : %r"
        % corps[:400])


def test_l_alarme_reprend_le_message_du_SERVEUR():
    """C'est le serveur qui connaît les deux nombres et le remède. Réécrire un
    message côté client ferait diverger les deux."""
    src = _sans_commentaires(_lire(BARRE))
    i = src.index('function _majAlarmePersistance')
    corps = src[i:i + 2600]
    assert re.search(r'textContent\s*=\s*\n?\s*etat\.message', corps), (
        'le texte affiché doit venir de etat.message : %r' % corps[-700:])


def test_l_alarme_DECALE_la_page_au_lieu_de_la_RECOUVRIR():
    """DÉFAUT TROUVÉ EN NAVIGATEUR, invisible au test structurel précédent :
    posé en position:fixed, le bandeau masquait la barre de navigation
    (CONFIG, LOGBOOK, le sélecteur de langue) de façon PERMANENTE — il n'est
    pas fermable, et c'est voulu. Une alarme qui prend le logiciel en otage
    n'est pas une alarme, c'est une panne de plus.

    Mesuré après correctif sur une instance réelle : bandeau de 121 px, haut
    de la navigation à 193 px — plus aucun recouvrement."""
    src = _sans_commentaires(_lire(BARRE))
    i = src.index('function _majAlarmePersistance')
    corps = src[i:i + 2600]
    assert re.search(
        r'document\.body\.style\.paddingTop\s*=\s*_persistBanner\.offsetHeight',
        corps), ('le contenu doit être poussé de la hauteur RÉELLE du bandeau '
                 '(elle dépend du message et de la largeur) : %r' % corps[-800:])
    # ET restauré : un décalage qui reste après le retour à la normale
    # laisserait un trou blanc en haut de toutes les pages.
    j = corps.index('if (!ko)')
    assert 'paddingTop = _padAvant' in corps[j:j + 400], (
        'le décalage doit être annulé quand la persistance repart : %r'
        % corps[j:j + 400])


def test_le_titre_passe_par_le_moteur_de_TRADUCTION():
    """Constaté en navigateur : la page de test était en allemand et le titre
    du bandeau restait en français. Le logiciel est traduit en 7 langues ; une
    alarme de perte de données est la dernière chose à laisser en VO."""
    src = _sans_commentaires(_lire(BARRE))
    i = src.index('function _majAlarmePersistance')
    corps = src[i:i + 2600]
    assert re.search(r"rcT\(\s*'CARNET NON ENREGISTRÉ'\s*\)", corps), (
        'le titre doit passer par rcT() : %r' % corps[:900])


def test_les_couleurs_passent_par_les_VARIABLES_de_theme():
    """La page existe en thème JOUR et en thème NUIT. Un fond codé en dur
    serait illisible dans l'un des deux."""
    src = _lire(BARRE)
    i = src.index('#rcsbPersistBanner{')
    regle = src[i:src.index('</style>', i)]
    assert 'var(--bg2' in regle and 'var(--text' in regle, regle[:300]
    # Le liseré rouge est ce qui distingue une ALARME d'une simple information.
    # Chercher « var(--red » n'importe où dans la règle restait vert quand on
    # remplaçait la bordure par un gris : la couleur du titre, plus bas dans la
    # même règle, suffisait à satisfaire l'assertion. Trouvé par contre-épreuve
    # — on vise donc la DÉCLARATION, pas la présence de la variable.
    assert re.search(r'border-bottom:\s*3px solid var\(--red', regle), (
        "l'alarme doit porter un liseré rouge épais : %r" % regle[:400])
    assert re.search(r'#rcsbPersistBanner b\{color:var\(--red', regle), regle[:400]


# ═══════════════════════════════════════════════════════════════════════════
# §3. L'INDICATEUR « SAUVEGARDE » NE DOIT PLUS MENTIR
# ═══════════════════════════════════════════════════════════════════════════

def test_l_horodatage_nomme_sa_SOURCE():
    """« log 11:43 UTC » se lisait comme « carnet sauvegardé ». La valeur vient
    du navigateur ; il faut le dire."""
    src = _sans_commentaires(_lire(BARRE))
    i = src.index("localStorage.getItem('rc_log_backup_time')")
    zone = src[i:i + 400]
    assert 'navigateur' in zone, (
        "la source de l'horodatage doit être nommée : %r" % zone[:300])
    assert not re.search(r'`log \$\{logBackup\}`', zone), (
        "l'ancien libellé trompeur est de retour : %r" % zone[:300])


def test_l_infobulle_distingue_navigateur_et_disque():
    """C'est là que l'opérateur va chercher ce que la ligne veut dire."""
    src = _lire(BARRE)
    m = re.search(r'<div class="rcsb-item[^"]*" id="rcsbSaveItem" title="([^"]*)"', src)
    assert m, 'infobulle introuvable'
    t = m.group(1).lower()
    assert 'navigateur' in t and 'disque' in t, (
        'doit distinguer la copie navigateur de la sauvegarde disque : %r'
        % m.group(1))
    assert 'config' in t, (
        "doit dire où activer la vraie sauvegarde : %r" % m.group(1))
