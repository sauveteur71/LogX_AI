# -*- coding: utf-8 -*-
"""VOACAP échouait en silence quand LogX AI est installé trop profond.

LE DÉFAUT, mesuré le 20/08/2026. `voacapl.exe` rend le code 1 avec une sortie
d'erreur VIDE dès que le chemin de son dossier `itshfbc/run` dépasse une
certaine longueur. Côté logiciel ça devenait « Echec du calcul VOACAP
(code 1): » — un message qui n'explique rien, pour une fonction de propagation
qui ne marche tout simplement plus.

LE SEUIL EST MESURÉ, PAS DEVINÉ. Même calcul Paris → New York, mêmes données,
seule la longueur du chemin change (dichotomie entre 120 et 136) :

    longueur de run/     résultat
    120                  OK
    128                  OK       ← dernière qui passe
    129                  ÉCHEC    ← première qui échoue
    132, 136             ÉCHEC

128 tout rond : un tampon de chemin de longueur fixe, classique d'un binaire
Fortran.

POURQUOI ÇA TOUCHE DE VRAIS UTILISATEURS, et pas seulement un arbre de travail
de développement : la racine VOACAP est le dossier d'installation ou le dossier
de données utilisateur. Un OneDrive redirigé, un dossier Documents, un nom
d'utilisateur long — et on dépasse 128 sans rien avoir fait d'anormal. C'est
d'ailleurs ainsi qu'il a été trouvé : `test_voacap.py` passait dans le dépôt
(98 caractères) et échouait dans un arbre de travail (133).

CE QUE CES TESTS TIENNENT : le seuil retenu est bien celui mesuré, la racine
livrée tient dessous, une racine trop longue est ramenée sous le seuil, et le
message d'erreur DIT la cause au lieu de la taire.

CE QU'ILS NE PROUVENT PAS : que 128 soit la limite sur toutes les versions de
voacapl. C'est la limite mesurée sur le binaire embarqué ici, celui que les
utilisateurs reçoivent.
"""
import os
import shutil
import tempfile

import pytest

import logx_voacap as v


def test_le_seuil_est_celui_qui_a_ete_mesure():
    """128 n'est pas un chiffre rond choisi au hasard : c'est la dernière
    longueur qui passe, la 129e échoue. Si quelqu'un le remonte « pour se
    donner de la marge », VOACAP redevient muet."""
    assert v._LONGUEUR_MAX_RUN == 128


def test_la_racine_livree_tient_sous_le_seuil():
    """Garde-fou sur l'installation elle-même : si le dépôt (ou le dossier de
    données) est déjà trop profond, tout le reste est inutile."""
    run = v._run_de(v._VOACAP_ROOT)
    assert len(run) <= v._LONGUEUR_MAX_RUN, (
        'la racine VOACAP livrée donne un run/ de %d caractères, au-delà des '
        '%d supportés par voacapl' % (len(run), v._LONGUEUR_MAX_RUN))


def test_une_racine_trop_longue_est_ramenee_sous_le_seuil():
    """Le cœur du correctif. On fabrique une arborescence délibérément trop
    profonde et on vérifie que le garde-fou rend une racine utilisable.

    On n'utilise PAS le vrai arbre VOACAP (216 fichiers) : la fonction recopie
    ce qu'on lui donne, un dossier jouet suffit et garde le test rapide.
    """
    base = tempfile.mkdtemp(prefix='lx_vc_')
    try:
        profond = os.path.join(base, 'a' * 60, 'b' * 60, 'vc')
        os.makedirs(os.path.join(profond, 'itshfbc', 'run'), exist_ok=True)
        assert len(v._run_de(profond)) > v._LONGUEUR_MAX_RUN, (
            'le chemin fabriqué doit dépasser le seuil, sinon ce test ne '
            'vérifie rien (longueur %d)' % len(v._run_de(profond)))

        corrigee = v._racine_assez_courte(profond)
        assert len(v._run_de(corrigee)) <= v._LONGUEUR_MAX_RUN, (
            'le garde-fou a rendu une racine encore trop longue : %d caractères'
            % len(v._run_de(corrigee)))
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_une_racine_deja_courte_n_est_pas_deplacee():
    """« Ne rien faire » est le bon comportement dans le cas courant : recopier
    l'arbre VOACAP sans nécessité coûterait des dizaines de mégaoctets et une
    divergence possible entre deux copies."""
    base = tempfile.mkdtemp(prefix='lx_vc_')
    try:
        os.makedirs(os.path.join(base, 'itshfbc', 'run'), exist_ok=True)
        assert len(v._run_de(base)) <= v._LONGUEUR_MAX_RUN
        assert v._racine_assez_courte(base) == base, (
            'une racine déjà assez courte doit être rendue telle quelle')
    finally:
        shutil.rmtree(base, ignore_errors=True)


def test_le_message_d_erreur_nomme_la_cause_quand_le_chemin_est_trop_long():
    """Le vrai coût du défaut n'était pas l'échec, c'était le SILENCE : « code
    1: » sans rien d'autre. L'opérateur doit pouvoir agir sur ce qu'il lit.

    On force _RUN_DIR trop long et on regarde ce que predict() répond. Le
    binaire échouera de toute façon — c'est le MESSAGE qu'on teste.
    """
    if not v.voacap_available():
        pytest.skip('voacapl indisponible sur cette plateforme')
    ancien = v._RUN_DIR
    base = tempfile.mkdtemp(prefix='lx_vc_')
    try:
        faux = os.path.join(base, 'c' * 60, 'd' * 60, 'itshfbc', 'run')
        assert len(faux) > v._LONGUEUR_MAX_RUN
        v._RUN_DIR = faux
        r = v.predict(tx_lat=48.85, tx_lon=2.35, rx_lat=40.71, rx_lon=-74.00,
                      month=8, year=2026, ssn=110.0, mode='CW',
                      freqs_mhz=[7.0], tx_label='P', rx_label='N')
        assert r.get('ok') is False
        msg = str(r.get('error', ''))
        assert 'trop long' in msg, (
            "le message doit nommer la longueur de chemin comme cause, or il "
            "dit seulement : %r" % msg[:200])
        assert str(v._LONGUEUR_MAX_RUN) in msg, (
            "le message doit donner la limite pour que l'opérateur sache "
            "jusqu'où raccourcir : %r" % msg[:200])
    finally:
        v._RUN_DIR = ancien
        shutil.rmtree(base, ignore_errors=True)
