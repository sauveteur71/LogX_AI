# -*- coding: utf-8 -*-
"""Non-régression STRUCTURELLE du câblage de SÛRETÉ de la session autonome
(niveaux 3/4 : copilote_qso/copilote_cq) dans logx_ft8.html.

Cette zone a PRODUIT deux portes dérobées (revue T8, tx-human-consent) :
  1. le double-clic (repondreEtEnvoyer) qui, aux niveaux autonomes, retombait
     sur l'ANCIEN séquenceur (seqDemarrer) SANS session armée ;
  2. le bouton STOP ÉMISSION (stopEmission) qui coupait la trame mais laissait
     la session ARMÉE, donc réémettait au cycle suivant.

Même approche que test_ft8_copilote_wiring.py : on LIT le HTML et on assère la
STRUCTURE du câblage, on n'exécute pas le DOM (intégration non testable en banc
pur — règle du dépôt).

MÉTHODE DU DÉPÔT respectée :
  - on exige une STRUCTURE, pas une simple présence de chaîne (un
    `assert 'estSessionAutonome' in html` serait satisfait par un COMMENTAIRE) ;
  - on confine l'extraction au CORPS de chaque fonction (jamais tout le
    fichier) ;
  - on DÉPOUILLE LES COMMENTAIRES avant d'analyser l'ORDRE — le pavé qui
    EXPLIQUE le garde mentionne « seqDemarrer » AVANT le garde lui-même, et un
    test naïf sur le texte brut se tromperait d'occurrence ;
  - garde-fou anti-test-vacant : un test TÉMOIN vérifie que les deux fonctions
    existent bien (sinon les extractions vides passeraient en silence).
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT8 = os.path.join(BASE, 'logx_ft8.html')


def _src():
    with open(FT8, encoding='utf-8') as f:
        return f.read()


def _sans_commentaires(txt):
    """Retire les blocs /* */ et les lignes de commentaire //. Sans ça, l'ordre
    « garde avant seqDemarrer » serait faussé par le pavé explicatif en tête de
    repondreEtEnvoyer, qui nomme seqDemarrer bien avant le code du garde."""
    sans_bloc = re.sub(r'/\*.*?\*/', ' ', txt, flags=re.S)
    return '\n'.join(l for l in sans_bloc.split('\n')
                     if not l.strip().startswith('//'))


def _corps(entete_regex):
    """Extrait le CORPS d'une fonction : de son en-tête jusqu'à la première
    accolade fermante indentée de 2 espaces (le style de ce fichier place les
    fonctions à ce niveau ; tout `}` interne est indenté de 4+ espaces). Rend
    None si l'en-tête est introuvable — ce que les tests vérifient AVANT
    d'analyser, pour ne jamais assertions sur une chaîne vide."""
    src = _src()
    m = re.search(entete_regex, src, re.S)
    return m.group(0) if m else None


# ── TÉMOIN : les deux fonctions existent (anti-test-vacant) ─────────────────

def test_temoin_les_deux_fonctions_existent():
    """Si un refactor renomme/supprime l'une des deux, les extractions ci-dessous
    deviendraient vides et les regex passeraient en silence. Ce témoin ROUGIT
    d'abord dans ce cas."""
    src = _src()
    assert 'function repondreEtEnvoyer(' in src, 'repondreEtEnvoyer a disparu'
    assert 'window.stopEmission = async function(' in src, 'stopEmission a disparu'
    # et les extractions confinées trouvent bien un corps non trivial
    assert _corps(r'function repondreEtEnvoyer\(.*?\n  \}'), \
        "corps de repondreEtEnvoyer non extractible (accolade fermante 2-espaces ?)"
    assert _corps(r'window\.stopEmission = async function\(\)\{.*?\n  \};'), \
        "corps de stopEmission non extractible (accolade fermante 2-espaces ?)"


# ── 1. Le double-clic ne peut PAS atteindre le séquenceur en session autonome ─

def test_repondre_garde_session_autonome_avant_seqDemarrer():
    """Porte 1 (CRITIQUE) : dans repondreEtEnvoyer, le garde
    estSessionAutonome(seqNiveau) doit précéder — et court-circuiter par un
    return — l'appel à seqDemarrer. Sinon, aux niveaux copilote_qso/copilote_cq
    (où doitProposer() est faux), le double-clic tomberait dans le séquenceur
    SANS session armée."""
    corps = _corps(r'function repondreEtEnvoyer\(.*?\n  \}')
    assert corps, 'corps de repondreEtEnvoyer introuvable'
    corps = _sans_commentaires(corps)

    # Le CODE (pas un commentaire) appelle bien le garde ET le séquenceur.
    assert 'estSessionAutonome(seqNiveau)' in corps, \
        "le garde estSessionAutonome(seqNiveau) a disparu du CODE de repondreEtEnvoyer"
    assert 'seqDemarrer(' in corps, \
        "seqDemarrer n'est plus appelé dans repondreEtEnvoyer (structure inattendue)"

    i_garde = corps.index('estSessionAutonome(seqNiveau)')
    i_seqdem = corps.index('seqDemarrer(')
    assert i_garde < i_seqdem, (
        "le garde estSessionAutonome doit être AVANT seqDemarrer — sinon le "
        "double-clic atteint l'ancien séquenceur en session autonome")

    # …et il court-circuite : un return; sépare le garde de seqDemarrer.
    assert 'return;' in corps[i_garde:i_seqdem], (
        "aucun return; entre le garde estSessionAutonome et seqDemarrer : le "
        "garde ne bloque pas réellement le chemin vers le séquenceur")


def test_repondre_garde_est_une_vraie_condition():
    """Le garde doit être une CONDITION (if …){ … return; }, pas une ligne
    morte. On vérifie la forme : estSessionAutonome(seqNiveau) refermée par `){`
    (donc bien un test de `if`) et suivie, avant la fin du bloc, d'un return."""
    corps = _corps(r'function repondreEtEnvoyer\(.*?\n  \}')
    assert corps, 'corps de repondreEtEnvoyer introuvable'
    corps = _sans_commentaires(corps)
    assert re.search(r'estSessionAutonome\(seqNiveau\)\)\s*\{', corps), (
        "estSessionAutonome(seqNiveau) n'ouvre pas un bloc if(...){ : le garde "
        "n'est pas une condition exécutable")


# ── 2. STOP ÉMISSION désarme la session ─────────────────────────────────────

def test_stopEmission_desarme_la_session():
    """Porte 2 (IMPORTANT) : stopEmission doit désarmer la session
    (_sessionArreter), et de façon gardée par sessionCourante — sinon le bouton
    STOP existant coupait la trame mais laissait la session réémettre."""
    corps = _corps(r'window\.stopEmission = async function\(\)\{.*?\n  \};')
    assert corps, 'corps de stopEmission introuvable'
    corps = _sans_commentaires(corps)
    # STRUCTURE : `if(… sessionCourante){ _sessionArreter( … )` — pas une simple
    # mention. La condition sur sessionCourante ET l'appel de désarmement.
    assert re.search(r'sessionCourante\)\s*\{\s*_sessionArreter\(', corps), (
        "stopEmission n'appelle pas _sessionArreter sous garde sessionCourante : "
        "le Stop ne désarmerait pas la session autonome")


# ── 3. (facultatif) La boucle de décodes route les niveaux autonomes vers la
#       session, pas vers le hook propose-only ─────────────────────────────

def test_boucle_decodes_route_session_par_estSessionAutonome():
    """La seule porte d'émission autonome est la boucle _sessionTraiterCycle,
    gardée par estSessionAutonome(seqNiveau). Prouve que les niveaux autonomes
    sont traités par le chemin SESSION (validité + armement), pas par le hook
    copilote propose-only (doitProposer, qui est faux pour ces niveaux)."""
    corps = _corps(r'function _sessionTraiterCycle\(.*?\n  \}')
    assert corps, 'corps de _sessionTraiterCycle introuvable'
    corps = _sans_commentaires(corps)
    assert 'estSessionAutonome(seqNiveau)' in corps, (
        "_sessionTraiterCycle n'est plus gardée par estSessionAutonome : la "
        "boucle de décodes ne route plus les niveaux autonomes vers la session")
    # et c'est bien la validité de session qui décide de l'émission
    assert 'sessionValide(' in corps, (
        "_sessionTraiterCycle n'appelle plus sessionValide : la porte de sûreté "
        "de l'émission autonome a sauté")


# ── 4. (M4) L'armement rappelle l'état de la case maîtresse « Activer l'émission »

def test_armement_consulte_txArmed():
    """M4 (revue finale) : sessionAutonomeArmer DOIT consulter `txArmed` (la case
    maîtresse « Activer l'émission ») et l'afficher — sinon une session « armée »
    reste silencieuse (envoyerMessage refuse sur `!txArmed`) sans que l'opérateur
    comprenne pourquoi. On assère la STRUCTURE (référence dans le CODE, pas un
    commentaire) et on confine au corps de la fonction."""
    corps = _corps(r'window\.sessionAutonomeArmer = function\(\)\{.*?\n  \};')
    assert corps, "corps de sessionAutonomeArmer non extractible"
    sans = _sans_commentaires(corps)
    assert 'txArmed' in sans, \
        "sessionAutonomeArmer ne consulte pas txArmed (rappel M4 absent)"
