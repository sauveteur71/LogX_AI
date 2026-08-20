# -*- coding: utf-8 -*-
"""Un QSO sans identifiant était INDÉLÉBILE.

LE DÉFAUT, trouvé le 20/08/2026 dans le carnet réel de F4GLD. Une entrée
`{"band":"144","call":"DL1AAA","num_sent":"001"}` — sans date, sans heure,
**sans identifiant** — s'y était glissée. Impossible de l'effacer :

  - `/log/delete/<id>` fait `int()` sur l'URL puis compare `q.get('id') == qso_id` ;
  - `/log/update` cible de la même façon ;
  - le bouton de suppression de LOGBOOK appelle le premier avec `q.id`.

Aucun de ces chemins ne peut viser un QSO qui n'a pas d'identifiant.
L'opérateur n'avait AUCUN moyen de le supprimer depuis le logiciel — il aurait
fallu éditer ses fichiers de données à la main, sur trois couches de
persistance, dans le module même qui a détruit un carnet complet une fois.

Ce n'est pas un cas d'école : un ADIF mal formé, un import partiel ou un outil
tiers suffisent à produire une telle entrée chez n'importe quel utilisateur.

LE CORRECTIF : au chargement, tout QSO sans identifiant en reçoit un. Il
redevient alors supprimable par le chemin normal, comme les autres.

CE QUE CES TESTS NE PROUVENT PAS : que l'identifiant survive au redémarrage
sans autre action. L'attribution est faite EN MÉMOIRE, délibérément — voir la
docstring de `_attribuer_ids_manquants()`. Elle devient persistante à la
première écriture qui concerne le QSO, typiquement sa suppression.
"""
import os
import sys

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if CONCOURS not in sys.path:
    sys.path.insert(0, CONCOURS)

import logx_storage as st  # noqa: E402


def _remplacer_log(qsos):
    """Mutation EN PLACE : le module expose shared_log par référence, une
    réassignation laisserait les autres pointer sur l'ancienne liste."""
    st.shared_log[:] = qsos


def test_un_qso_sans_identifiant_en_recoit_un():
    """Le cas exact rencontré : l'entrée DL1AAA, telle qu'elle était."""
    ancien = list(st.shared_log)
    try:
        _remplacer_log([
            {'id': 100, 'call': 'F4GLD', 'band': '14'},
            {'band': '144', 'call': 'DL1AAA', 'num_sent': '001'},
        ])
        assert st._attribuer_ids_manquants() == 1
        orphelin = [q for q in st.shared_log if q['call'] == 'DL1AAA'][0]
        assert orphelin.get('id'), (
            "le QSO sans identifiant doit en recevoir un, sinon il reste "
            'impossible à supprimer depuis le logiciel')
        assert isinstance(orphelin['id'], int)
    finally:
        _remplacer_log(ancien)


def test_l_identifiant_attribue_n_entre_jamais_en_collision():
    """Une collision serait pire que le défaut : supprimer l'un effacerait
    l'autre. On se cale au-dessus du plus grand identifiant déjà pris."""
    ancien = list(st.shared_log)
    try:
        _remplacer_log([
            {'id': 5, 'call': 'A'},
            {'id': 9, 'call': 'B'},
            {'call': 'SANS1'},
            {'call': 'SANS2'},
        ])
        st._attribuer_ids_manquants()
        ids = [q['id'] for q in st.shared_log]
        assert len(ids) == len(set(ids)), 'identifiants en collision : %r' % ids
        assert all(q['id'] > 9 for q in st.shared_log
                   if q['call'].startswith('SANS')), (
            'les nouveaux identifiants doivent se placer au-dessus du plus '
            'grand déjà pris, pour ne pas heurter un QSO existant ni un '
            'identifiant réservé plus tard')
    finally:
        _remplacer_log(ancien)


def test_un_carnet_deja_sain_n_est_pas_touche():
    """« Ne rien faire » est le bon comportement dans le cas courant : on ne
    réécrit pas des identifiants existants, ce serait casser les références
    (QSL scannées, tombstones de synchro, doublons)."""
    ancien = list(st.shared_log)
    try:
        _remplacer_log([{'id': 1, 'call': 'A'}, {'id': 2, 'call': 'B'}])
        assert st._attribuer_ids_manquants() == 0
        assert [q['id'] for q in st.shared_log] == [1, 2]
    finally:
        _remplacer_log(ancien)


def test_un_identifiant_vide_ou_nul_compte_comme_absent():
    """Les variantes rencontrées en vrai : champ absent, chaîne vide, None,
    zéro. Toutes rendent le QSO inatteignable par /log/delete, toutes doivent
    donc être traitées."""
    ancien = list(st.shared_log)
    try:
        for valeur in ('', None, 0):
            _remplacer_log([{'id': 50, 'call': 'REF'},
                            {'id': valeur, 'call': 'ORPHELIN'}])
            assert st._attribuer_ids_manquants() == 1, (
                'id=%r doit compter comme absent' % valeur)
            orph = [q for q in st.shared_log if q['call'] == 'ORPHELIN'][0]
            assert isinstance(orph['id'], int) and orph['id'] > 50
    finally:
        _remplacer_log(ancien)


def test_le_correctif_est_branche_sur_les_DEUX_chemins_de_chargement():
    """Assertion de STRUCTURE. Les tests ci-dessus appellent la fonction à la
    main : ils passeraient même si elle n'était câblée nulle part.

    Le carnet se charge par DEUX chemins — la base SQLite, et la migration
    one-shot depuis shared_log.json. N'en câbler qu'un laisserait le défaut
    entier pour l'autre. Commentaires dépouillés avant recherche.
    """
    import re
    chemin = os.path.join(CONCOURS, 'logx_storage.py')
    with open(chemin, encoding='utf-8') as f:
        src = f.read()
    code = '\n'.join(re.sub(r'#.*$', '', li) for li in src.splitlines())
    appels = code.count('_attribuer_ids_manquants()')
    # 1 définition + 2 appels
    assert appels >= 3, (
        'le correctif doit être appelé sur les DEUX chemins de chargement '
        '(base SQLite ET migration JSON) — trouvé %d occurrence(s)' % appels)
