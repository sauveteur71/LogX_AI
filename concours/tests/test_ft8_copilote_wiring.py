# -*- coding: utf-8 -*-
"""Câblage du copilote FT8 dans logx_ft8.html (approche X : piloté par les
décodes). Vérifie la présence du niveau + des inclusions, ET verrouille la
propriété de SÛRETÉ centrale : au niveau 'copilote', on ne fait que PROPOSER —
la seule émission (envoyerMessage) est DANS le callback de confirmation
(ÉMETTRE), jamais un appel direct qui émettrait tout seul.
"""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT8 = os.path.join(BASE, 'logx_ft8.html')


def _src():
    with open(FT8, encoding='utf-8') as f:
        return f.read()


def test_option_copilote_et_inclusions_presentes():
    src = _src()
    assert '<option value="copilote">' in src            # niveau proposé à l'opérateur
    assert 'logx_tx_bar.js' in src                       # barre de consentement incluse
    assert 'logx_ft8_copilote.js' in src                 # module copilote inclus


def test_copilote_appele_seulement_sur_decode_pour_moi():
    src = _src()
    # le hook n'est déclenché que pour un décode qui M'EST ADRESSÉ (adresseAMoi)
    assert re.search(r'if\(adresseAMoi\)\s*_copiloteProposer\(', src)


def test_copilote_ne_peut_pas_auto_emettre():
    """SÛRETÉ : dans _copiloteProposer, le SEUL envoyerMessage doit être à
    l'intérieur du callback passé à LogxTxBar.proposer (déclenché par ÉMETTRE),
    jamais un appel direct. Verrouille l'invariant 'l'IA prépare, l'humain
    déclenche' contre une future régression."""
    src = _src()
    m = re.search(r'function _copiloteProposer\(.*?\n  \}', src, re.S)
    assert m, "_copiloteProposer introuvable"
    corps = m.group(0)
    # il y a bien une émission possible, mais UNIQUEMENT via le callback proposer()
    assert 'LogxTxBar.proposer(' in corps
    # chaque occurrence de envoyerMessage( doit être précédée, sur la même ligne,
    # de 'function(){ ' (le callback de confirmation) — jamais en tête d'instruction.
    for ligne in corps.splitlines():
        if 'envoyerMessage(' in ligne:
            assert 'function(){' in ligne or 'function () {' in ligne, (
                "envoyerMessage doit être DANS le callback ÉMETTRE, pas un appel "
                "direct (sinon auto-émission) : %r" % ligne.strip())
