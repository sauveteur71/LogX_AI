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
    assert '<option value="copilote">' in src            # niveau 1 : confirmation à la main
    assert '<option value="copilote_auto">' in src       # niveau 2 : émet après délai sauf annulation
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


def test_prendre_suivant_file_ne_peut_pas_auto_emettre():
    """La prise de la station suivante en file (pile-up) est aussi propose-only :
    le seul envoyerMessage est dans le callback ÉMETTRE."""
    src = _src()
    m = re.search(r'function _prendreSuivantFile\(.*?\n  \}', src, re.S)
    assert m, "_prendreSuivantFile introuvable"
    corps = m.group(0)
    assert 'LogxTxBar.proposer(' in corps
    for ligne in corps.splitlines():
        if 'envoyerMessage(' in ligne:
            assert 'function(){' in ligne or 'function () {' in ligne, (
                "file d'attente : envoyerMessage doit être DANS le callback "
                "ÉMETTRE, jamais un appel direct : %r" % ligne.strip())


def test_copilote_clic_cq_ne_peut_pas_auto_emettre():
    """Même invariant pour la branche copilote de repondreEtEnvoyer (réponse à un
    CQ au double-clic, gatée par doitProposer -> couvre 'copilote' ET
    'copilote_auto') : le seul envoyerMessage est dans le callback ÉMETTRE.
    Ancrée sur appelInitial(cible, unique à cette branche."""
    src = _src()
    m = re.search(r"LogxFt8Copilote\.appelInitial\(cible.*?LogxTxBar\.proposer\(.*?\n      return;\n    \}", src, re.S)
    assert m, "branche copilote de repondreEtEnvoyer introuvable"
    branche = m.group(0)
    assert 'LogxTxBar.proposer(' in branche
    for ligne in branche.splitlines():
        if 'envoyerMessage(' in ligne:
            assert 'function(){' in ligne or 'function () {' in ligne, (
                "réponse CQ copilote : envoyerMessage doit être DANS le callback "
                "ÉMETTRE, jamais un appel direct : %r" % ligne.strip())


def test_copilote_auto_passe_le_delai_aux_trois_sites():
    """Niveau 2 : chaque proposition copilote (réponse auto, réponse CQ, station
    suivante de la file) passe le délai d'auto-émission via delaiAutoMs(seqNiveau,
    …) en 3e argument de LogxTxBar.proposer — sinon copilote_auto n'émettrait
    jamais tout seul. delaiAutoMs renvoie 0 hors 'copilote_auto' (niveau 1
    inchangé), la sûreté est donc préservée."""
    src = _src()
    sites = [ligne.strip() for ligne in src.splitlines()
             if 'LogxTxBar.proposer(p, function(){' in ligne]
    assert len(sites) == 3, "attendu 3 sites de proposition copilote, vu %d" % len(sites)
    for ligne in sites:
        assert 'LogxFt8Copilote.delaiAutoMs(seqNiveau' in ligne, (
            "proposition copilote sans délai d'auto-émission (3e arg) : %r" % ligne)
