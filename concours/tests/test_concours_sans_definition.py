# -*- coding: utf-8 -*-
"""Les 25 concours proposés dans l'interface sans définition serveur.

DÉFAUT MESURÉ le 19/08/2026 : `CONTEST_DEFINITIONS` a 43 entrées,
`CONTEST_SCORING` 43 aussi, mais 25 identifiants de `CONTEST_SCORING` n'ont
AUCUNE entrée dans `CONTEST_DEFINITIONS` — alors que le catalogue client
(`logx_configuration.js`) les propose tous à la sélection. Presque tous sont
des concours THF français.

`…get('bands', [])` rendait donc `[]`, et une douzaine de sites lisent
'bands' ainsi, tous avec un défaut à `[]` : dégradation SILENCIEUSE partout,
sans exception ni trace. C'est pour ça que personne ne l'a vue.

Ce banc tient quatre propriétés :

1. les 15 concours dont le barème donne une liste EXPLICITE de bandes en
   retrouvent ;
2. les 10 dont le barème donne une PLAGE ou un mot n'en retrouvent PAS —
   développer une plage serait décider quelles bandes en font partie, donc
   inventer une valeur de domaine ;
3. 🔒 la liste de ces 10 est VERROUILLÉE : elle peut rétrécir (quelqu'un a lu
   un règlement et écrit une vraie définition), jamais grandir en silence.
   C'est ce filet-là qui a manqué pendant tout ce temps ;
4. `CONTEST_DEFINITIONS` reste prioritaire et intact — on n'a pas remplacé
   une source relue à la main par une conversion.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_definitions as D          # noqa: E402


# Les 10 concours dont le barème ne permet PAS de déduire les bandes.
# « 438MHz+ TVA », « 144MHz-47GHz », « HF », « Au choix » : ce sont des
# plages ou des mots. Cette liste ne doit que RÉTRÉCIR — pour en retirer un,
# il faut une vraie définition dans CONTEST_DEFINITIONS, écrite depuis le
# règlement, pas devinée.
AMBIGUS_CONNUS = {
    'CUSTOM',              # « Au choix » — par construction
    'F9NL',                # « HF »
    'UFT_RENCONTRES',      # « HF »
    'REF_CDF_TVA',         # « 438MHz+ TVA »
    'REF_IARU_TVA',        # « 438MHz+ TVA »
    'REF_NAT_TVA',         # « 438MHz+ TVA »
    'REF_NAT_TVA_DEC',     # « 438MHz+ TVA »
    'REF_CHALLENGE_THF',   # « 144MHz-47GHz »
    'REF_F8TD',            # « 1296MHz-47GHz »
    'REF_IARU_UHF',        # « 432MHz-47GHz »
}


# Photographie prise à l'IMPORT du module, donc AVANT que le moindre test
# n'ait pu appeler l'accesseur. C'est la seule référence fiable pour prouver
# qu'il ne matérialise rien : une référence prise dans le corps d'un test se
# compare à un état déjà contaminé par les tests précédents du fichier.
DEFINITIONS_AU_DEMARRAGE = frozenset(D.CONTEST_DEFINITIONS)


def _orphelins():
    return {c for c in D.CONTEST_SCORING if c not in D.CONTEST_DEFINITIONS}


# ── 1. Les concours convertibles retrouvent leurs bandes ──────────────────
def test_les_concours_orphelins_convertibles_ont_des_bandes():
    manquants = sorted(c for c in _orphelins() - AMBIGUS_CONNUS
                       if not D.bandes_du_concours(c))
    assert not manquants, (
        f"ces concours sont proposés dans l'interface et ne rendent aucune "
        f"bande : {manquants}")


def test_marconi_est_bien_sur_144():
    """Cas concret : REF_MARCONI rendait [] avant ce correctif."""
    assert D.bandes_du_concours('REF_MARCONI') == ['144']


def test_un_bareme_multibande_donne_toutes_les_bandes():
    assert D.bandes_du_concours('REF_CCD_JAN1') == ['432', '1296', '2320']


def test_les_bandes_sont_en_MHz_comme_les_definitions_existantes():
    """Piège du dépôt : le format est '144', jamais '2m'/'70cm'."""
    for cid in _orphelins() - AMBIGUS_CONNUS:
        for b in D.bandes_du_concours(cid):
            float(b)          # lève si ce n'est pas un nombre en MHz


# ── 2 et 3. Les ambigus restent vides, et la liste est verrouillée ────────
def test_les_ambigus_ne_rendent_aucune_bande():
    """Mieux vaut [] qu'une plage développée au jugé."""
    bavards = sorted(c for c in AMBIGUS_CONNUS
                     if c in D.CONTEST_SCORING and D.bandes_du_concours(c))
    assert not bavards, (
        f"des bandes ont été DEVINÉES pour : {bavards} — leur barème est une "
        'plage ou un mot, il faut lire le règlement, pas extrapoler')


def test_aucun_nouveau_concours_ambigu_ne_passe_en_silence():
    """🔒 Le verrou. La liste ne peut que rétrécir.

    Si ce test rougit avec des identifiants EN TROP, c'est qu'un concours a
    été ajouté au barème sans définition et sans bandes exploitables : soit
    lui écrire une vraie définition, soit l'ajouter ici en connaissance de
    cause. Ne pas élargir la liste par réflexe pour faire passer la suite."""
    sans_bandes = {c for c in _orphelins() if not D.bandes_du_concours(c)}
    nouveaux = sorted(sans_bandes - AMBIGUS_CONNUS)
    assert not nouveaux, (
        f'nouveaux concours sans bandes exploitables : {nouveaux}')


def test_la_liste_verrouillee_ne_contient_pas_de_concours_disparu():
    """L'autre sens : un ambigu résolu doit SORTIR de la liste."""
    fantomes = sorted(c for c in AMBIGUS_CONNUS if c not in D.CONTEST_SCORING)
    assert not fantomes, (
        f'ces concours ne sont plus au barème, retirer de AMBIGUS_CONNUS : '
        f'{fantomes}')

    resolus = sorted(c for c in AMBIGUS_CONNUS if D.bandes_du_concours(c))
    assert not resolus, (
        f'ces concours ont maintenant des bandes, les retirer de '
        f'AMBIGUS_CONNUS : {resolus}')


# ── 4. CONTEST_DEFINITIONS reste la source prioritaire ────────────────────
def test_une_definition_relue_a_la_main_gagne_sur_le_bareme():
    """REF_RPH a une vraie définition : elle doit primer, intacte."""
    assert 'REF_RPH' in D.CONTEST_DEFINITIONS
    assert D.bandes_du_concours('REF_RPH') == \
        [str(b) for b in D.CONTEST_DEFINITIONS['REF_RPH']['bands']]


def test_l_accesseur_n_ajoute_rien_a_CONTEST_DEFINITIONS():
    """Le contrat public (contest_schema.json) exige 8 champs et refuse
    toute clé supplémentaire ; la CI le valide de façon bloquante. On ne
    fabrique donc AUCUNE entrée — mesuré : une définition dérivée produit
    6 erreurs de validation.

    ⚠️ La référence est prise à l'IMPORT du module, pas dans le test. Une
    première version capturait `set(D.CONTEST_DEFINITIONS)` en début de test :
    banc VACANT, trouvé par contre-épreuve. Un test précédent du même fichier
    appelle déjà l'accesseur, donc une éventuelle contamination était déjà
    présente dans la référence, qui se comparait à elle-même."""
    for cid in list(D.CONTEST_SCORING):
        D.bandes_du_concours(cid)

    apparus = sorted(set(D.CONTEST_DEFINITIONS) - DEFINITIONS_AU_DEMARRAGE)
    assert not apparus, (
        f'bandes_du_concours a matérialisé des entrées dans '
        f'CONTEST_DEFINITIONS : {apparus} — elles seraient rejetées par '
        'contest_schema.json, que la CI valide de façon bloquante')


def test_les_concours_lus_au_bareme_restent_hors_des_definitions():
    """Formulation structurelle du même invariant, lisible isolément."""
    for cid in ('REF_MARCONI', 'REF_CCD_JAN1', 'REF_DDFM_50', 'REF_IARU_VHF'):
        bandes = D.bandes_du_concours(cid)
        assert bandes, f'{cid} devrait rendre des bandes'
        assert cid not in DEFINITIONS_AU_DEMARRAGE, (
            f'{cid} a maintenant une vraie définition — très bien, mais '
            'retirer ce cas du test, il ne prouve plus rien')
        assert cid not in D.CONTEST_DEFINITIONS, (
            f'{cid} a été matérialisé dans CONTEST_DEFINITIONS par la simple '
            'lecture de ses bandes')


def test_concours_inconnu_rend_une_liste_vide():
    assert D.bandes_du_concours('CE_CONCOURS_N_EXISTE_PAS') == []
    assert D.bandes_du_concours('') == []
    assert D.bandes_du_concours(None) == []


# ── L'analyseur lui-même, cas par cas ─────────────────────────────────────
def test_analyseur_bareme_cas_limites():
    f = D._bandes_depuis_bareme
    assert f('144MHz') == ['144']
    assert f('432 1296 2320MHz') == ['432', '1296', '2320']
    assert f('50MHz') == ['50']
    assert f('1.8 3.5 7 14 21 28MHz') == ['1.8', '3.5', '7', '14', '21', '28']
    # Ambigus : plage, mot, format libre, vide
    assert f('144MHz-47GHz') == []
    assert f('432MHz-47GHz') == []
    assert f('438MHz+ TVA') == []
    assert f('HF') == []
    assert f('Au choix') == []
    assert f('') == []
    assert f(None) == []
