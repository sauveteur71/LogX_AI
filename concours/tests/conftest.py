# -*- coding: utf-8 -*-
"""Isolation de l'état module de logx_storage entre les tests.

`ecriture_bloquee` et `load_failed` sont des drapeaux COLLANTS pour toute la
vie du processus — c'est voulu en exploitation : un refus de persistance ne
doit pas se rejouer à chaque QSO jusqu'à finir par passer (voir
logx_storage._bloquer_ecriture).

Mais un processus pytest exécute des centaines de tests à la suite. Le premier
test qui déclenche légitimement un refus gèlerait alors la persistance pour
TOUS les suivants, dans TOUS les fichiers — et les échecs apparaîtraient loin
du test fautif, sans rapport visible avec lui. Constaté exactement ainsi le
19/08/2026 : `test_storage.py` et `test_storage_ecriture_incrementale.py`
verts isolément, rouges en suite complète.

On remet donc l'état à neuf avant CHAQUE test. Ce n'est pas masquer un défaut :
c'est donner à chaque test le même point de départ que celui qu'il aurait en
s'exécutant seul, exactement comme les fixtures qui vident déjà `shared_log`.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def _persistance_neuve(request):
    """Avant chaque test : aucune persistance gelée héritée du test précédent."""
    import logx_storage as st
    st.load_failed = False
    st.ecriture_bloquee = None
    st._journal_ids = set()
    yield
    # DIAGNOSTIC TEMPORAIRE : nommer les tests qui déclenchent réellement le
    # garde-fou, pour vérifier qu'aucun ne le fait par accident (consentement
    # oublié sur un chemin de suppression légitime).
    if os.environ.get('LOGX_TRACER_GEL') and st.ecriture_bloquee:
        with open(os.environ['LOGX_TRACER_GEL'], 'a', encoding='utf-8') as f:
            f.write('%s | %r\n' % (request.node.nodeid,
                                   {k: v for k, v in st.ecriture_bloquee.items()
                                    if k in ('sur_disque', 'en_memoire', 'ou')}))
