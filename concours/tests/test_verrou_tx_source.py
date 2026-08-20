# -*- coding: utf-8 -*-
"""Échap ne doit plus libérer le verrou d'émission d'un AUTRE chemin.

LE DÉFAUT, trouvé le 20/08/2026. Échap est le coupe-circuit CW du contesteur :
`logx_theme_shortcuts.js` envoie `/rig/stop` dès qu'un pilote CW existe, sans
regarder le mode courant — c'est délibéré, et une revue adversariale du
18/08/2026 avait justement corrigé l'inverse (le conditionner au mode désarmait
le coupe-circuit en pleine émission).

Mais `/rig/stop` levait le verrou TX **sans regarder qui le détenait**. Or
`/rig/ptt` le prend aussi, et c'est par là que passe le séquenceur FT8. Donc :

    le FT8 émet sur la radio 1 et détient le verrou
    l'opérateur appuie sur Échap pour fermer une popup
    -> le verrou est levé alors que la radio 1 est toujours sur l'air
    -> la radio 2 peut prendre la parole en même temps

Deux porteuses simultanées : exactement ce que ce verrou existe pour empêcher.
En concours, c'est une infraction au règlement, pas un désagrément.

LE CORRECTIF : le verrou retient QUI l'a pris ('cw', 'ptt', 'voix'), et
`/rig/stop` — qui est un arrêt CW — ne lève plus qu'un verrou pris par du CW.

CE QUE CES TESTS NE PROUVENT PAS : que deux porteuses ne partiront jamais. Le
logiciel reste aveugle à un poste qu'il ne pilote pas, et sur une MÊME radio il
n'a jamais refusé deux flux (`verrouiller_tx` ne refuse que si l'autre RADIO
détient le verrou). Ce lot ferme une porte, il n'en ferme pas dix.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_so2r as so2r  # noqa: E402


def _liberer():
    """Repart d'un verrou libre : l'état est un global de module."""
    so2r.deverrouiller_tx(1)
    so2r.deverrouiller_tx(2)


def test_echap_ne_libere_pas_le_verrou_pris_par_le_ptt():
    """LE défaut. Le séquenceur FT8 tient le verrou par /rig/ptt ; un arrêt CW
    ne doit pas y toucher."""
    _liberer()
    assert so2r.verrouiller_tx(1, 'ptt')['ok'] is True
    so2r.deverrouiller_tx(1, 'cw')          # ce que fait /rig/stop
    refus = so2r.verrouiller_tx(2, 'cw')
    assert refus['ok'] is False, (
        "le verrou pris par le PTT a été levé par un arrêt CW : la radio 2 "
        "peut émettre pendant que la radio 1 est sur l'air")
    _liberer()


def test_echap_libere_toujours_un_vrai_verrou_cw():
    """Non-régression du coupe-circuit : Échap doit rester efficace sur ce
    pour quoi il existe. Le corriger en le rendant inopérant serait pire que
    le défaut d'origine."""
    _liberer()
    assert so2r.verrouiller_tx(1, 'cw')['ok'] is True
    so2r.deverrouiller_tx(1, 'cw')
    assert so2r.verrouiller_tx(2, 'cw')['ok'] is True, (
        'un verrou pris par le CW doit bien être levé par un arrêt CW')
    _liberer()


def test_un_relachement_sans_source_leve_quoi_qu_il_arrive():
    """Comportement historique conservé : les chemins qui relâchent LEUR
    PROPRE verrou dans la même requête (fin de message vocal, échec de PTT)
    appellent sans source et ne doivent pas se mettre à échouer."""
    _liberer()
    so2r.verrouiller_tx(1, 'ptt')
    so2r.deverrouiller_tx(1)                # sans source
    assert so2r.verrouiller_tx(2, 'cw')['ok'] is True
    _liberer()


def test_on_ne_leve_jamais_le_verrou_d_une_AUTRE_radio():
    """Propriété déjà tenue avant ce lot, vérifiée ici pour qu'elle ne parte
    pas en ajoutant la source : un relâchement tardif de la radio 1 ne doit
    pas effacer un verrou fraîchement pris par la radio 2."""
    _liberer()
    so2r.verrouiller_tx(2, 'cw')
    so2r.deverrouiller_tx(1, 'cw')
    assert so2r.verrouiller_tx(1, 'cw')['ok'] is False, (
        'le verrou de la radio 2 a été levé par un relâchement de la radio 1')
    _liberer()


def test_le_ptt_du_ft8_est_bien_etiquete_dans_le_serveur():
    """Assertion de STRUCTURE, pas de présence. Les tests ci-dessus portent sur
    logx_so2r ; celui-ci vérifie que le serveur ÉTIQUETTE réellement ses prises
    de verrou — sinon le mécanisme serait juste, mais inutilisé.

    On dépouille les commentaires avant de chercher : un pavé qui EXPLIQUE
    l'étiquette satisferait sinon la recherche sans qu'une seule ligne de code
    ne l'applique.
    """
    import re
    chemin = os.path.join(CONCOURS, 'logx_http.py')
    with open(chemin, encoding='utf-8') as f:
        src = f.read()
    code = '\n'.join(re.sub(r'#.*$', '', ligne) for ligne in src.splitlines())

    assert "verrouiller_tx(radio_active, 'ptt')" in code, (
        "/rig/ptt doit étiqueter son verrou 'ptt', sinon un arrêt CW le lèvera")
    assert "verrouiller_tx(radio_active, 'cw')" in code, (
        "/rig/cw doit étiqueter son verrou 'cw', sinon Échap ne le lèvera plus "
        '— le coupe-circuit deviendrait inopérant')
    assert "deverrouiller_tx(radio_active, 'cw')" in code, (
        "/rig/stop doit restreindre son relâchement au CW")
    # Préfixe `so2r.` OBLIGATOIRE ici : sans lui, la chaîne cherchée est aussi
    # un suffixe de `deverrouiller_tx(radio_active)` et l'assertion échouerait
    # sur du code parfaitement correct. Piège tombé dessus en écrivant ce test.
    assert 'so2r.verrouiller_tx(radio_active)' not in code, (
        'il reste une prise de verrou SANS source dans le serveur : elle '
        "pourra être levée par n'importe quel chemin d'arrêt")
