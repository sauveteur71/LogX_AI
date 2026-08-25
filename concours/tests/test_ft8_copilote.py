# -*- coding: utf-8 -*-
"""Copilote FT8 (concours/logx_ft8_copilote.js) — glue PURE et testable du
niveau « copilote » du séquenceur FT8. Le séquenceur existant (logx_ft8.html,
#179) reste la source de vérité : il calcule le message suivant + logue. Ce
module ne décide QUE (a) faut-il proposer plutôt qu'auto-émettre, (b) comment
emballer la proposition pour LogxTxBar.proposer(), (c) l'anti-spam (idempotence).

Exécute le VRAI logx_ft8_copilote.js dans un moteur JS réel (V8 via py_mini_racer).
"""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_ft8_copilote.js')

_PREAMBLE = "var window = {};\n"


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_PREAMBLE)
    with open(JS_PATH, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def test_api_exposee():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxFt8Copilote") == 'object'
    for fn in ('doitProposer', 'messagePropose', 'cle'):
        assert ctx.eval(f"typeof window.LogxFt8Copilote.{fn}") == 'function', fn


def test_doit_proposer_seulement_au_niveau_copilote():
    ctx = _ctx()
    assert ctx.eval("window.LogxFt8Copilote.doitProposer('copilote')") is True
    # les autres niveaux gardent leur comportement (auto/manuel/etc.) : PAS de proposition
    for niv in ('manuel', 'assiste', 'sequenceur', 'auto', ''):
        assert ctx.eval(f"window.LogxFt8Copilote.doitProposer('{niv}')") is False, niv


def test_message_propose_emballe_pour_la_barre():
    ctx = _ctx()
    ctx.eval("var p = window.LogxFt8Copilote.messagePropose('F4ABC F1XYZ -12', 'F4ABC', 14074000, 'F1XYZ');")
    assert ctx.eval("p.mode") == 'FT8'
    assert ctx.eval("p.message") == 'F4ABC F1XYZ -12'   # message calculé par le séquenceur, tel quel
    assert ctx.eval("p.frequency_hz") == 14074000
    assert ctx.eval("p.operator") == 'F1XYZ'            # MON indicatif
    # la voix ne concerne pas le FT8 : source neutre
    assert ctx.eval("p.voice_source") == 'auto'


def test_reponse_ft8_selon_le_protocole():
    # Table de protocole SOURCÉE (doc F4GLD). Je suis F1XYZ (monCall).
    ctx = _ctx()
    def rep(msg, snr):
        ctx.eval(f"var r = window.LogxFt8Copilote.reponseFt8({msg!r}, {snr}, 'F1XYZ');")
        return None if ctx.eval("r === null") else ctx.eval("r.message")
    # (2) on me répond avec une grille -> j'envoie SON report (le SNR reçu)
    assert rep('F1XYZ F4ABC JN03', -12) == 'F4ABC F1XYZ -12'
    # SNR positif -> format +NN
    assert rep('F1XYZ F4ABC JN03', 3) == 'F4ABC F1XYZ +03'
    # on m'appelle SANS grille (grille déjà connue) -> report aussi
    assert rep('F1XYZ F4ABC', -5) == 'F4ABC F1XYZ -05'
    # (4) on m'accuse réception + son report (R-18) -> je clos par RR73
    assert rep('F1XYZ F4ABC R-18', -12) == 'F4ABC F1XYZ RR73'
    # on m'envoie un report nu (-12) -> j'accuse avec R + mon report
    assert rep('F1XYZ F4ABC -12', -8) == 'F4ABC F1XYZ R-08'
    # (6) fin de QSO reçue -> plus rien à proposer
    assert rep('F1XYZ F4ABC 73', -12) is None
    assert rep('F1XYZ F4ABC RR73', -12) is None
    assert rep('F1XYZ F4ABC RRR', -12) is None
    # décode PAS adressé à moi (QSO entre tiers) -> rien
    assert rep('F4ABC DL1XX JN03', -12) is None
    # CQ (pas un appel qui m'est adressé) -> rien (répondre à un CQ = hors scope v1)
    assert rep('CQ F4ABC JN03', -12) is None


def test_appel_initial_repondre_a_un_cq():
    # Répondre à un CQ (ou appeler une station) : message initial standard
    # « CIBLE MONCALL MONGRILLE4 ». La grille est tronquée à 4 caractères.
    ctx = _ctx()
    assert ctx.eval("window.LogxFt8Copilote.appelInitial('F4ABC', 'F1XYZ', 'JN18DT')") == 'F4ABC F1XYZ JN18'
    # sans grille configurée : appel valide sans grille (indicatifs seuls)
    assert ctx.eval("window.LogxFt8Copilote.appelInitial('F4ABC', 'F1XYZ', '')") == 'F4ABC F1XYZ'
    # cible ou mon indicatif manquant -> null (rien à proposer)
    assert ctx.eval("window.LogxFt8Copilote.appelInitial('', 'F1XYZ', 'JN18') === null") is True
    assert ctx.eval("window.LogxFt8Copilote.appelInitial('F4ABC', '', 'JN18') === null") is True


def test_extraire_report_grille_fin():
    # Helpers d'extraction pour la journalisation copilote (données à enregistrer).
    ctx = _ctx()
    R = lambda m: ctx.eval(f"window.LogxFt8Copilote.extraireReport({m!r})")
    G = lambda m: ctx.eval(f"window.LogxFt8Copilote.extraireGrille({m!r})")
    F = lambda m: ctx.eval(f"window.LogxFt8Copilote.estFinQso({m!r}, 'F1XYZ')")
    # report : dernier jeton report, R retiré
    assert R('F4ABC F1XYZ -12') == '-12'
    assert R('F1XYZ F4ABC R-18') == '-18'
    assert R('F4ABC F1XYZ +03') == '+03'
    assert R('F1XYZ F4ABC JN03') is None          # une grille n'est pas un report
    assert R('F1XYZ F4ABC RR73') is None          # RR73 n'est pas un report
    # grille : 4 car AR-dd, MAIS jamais 'RR73' (piège connu du séquenceur)
    assert G('F1XYZ F4ABC JN03') == 'JN03'
    assert G('F4ABC F1XYZ RR73') is None          # RR73 satisfait la regex grille -> exclu
    assert G('F4ABC F1XYZ -12') is None
    # fin de QSO : RRR/RR73/73 ADRESSÉ à moi
    assert F('F1XYZ F4ABC RR73') is True
    assert F('F1XYZ F4ABC 73') is True
    assert F('F1XYZ F4ABC RRR') is True
    assert F('F1XYZ F4ABC -12') is False          # échange en cours, pas la fin
    assert F('F4ABC DL1XX 73') is False           # fin d'un QSO entre tiers -> pas moi


def test_pile_up_premier_appelant_dabord():
    # Pile-up : ne PAS écraser une proposition en attente par un AUTRE appelant.
    # On reste sur le QSO en cours (un QSO à la fois) ; le tri fin des appelants
    # (prioriser) est un item séparé (décision produit F4GLD).
    ctx = _ctx()
    I = lambda prep, actif, dx: ctx.eval(
        f"window.LogxFt8Copilote.doitIgnorerPileup({str(prep).lower()}, {actif!r}, {dx!r})")
    # proposition en attente pour F4ABC, un AUTRE (DL1XX) appelle -> on l'ignore
    assert I(True, 'F4ABC', 'DL1XX') is True
    # même station (suite du QSO) -> jamais ignoré
    assert I(True, 'F4ABC', 'F4ABC') is False
    # rien en attente -> on peut proposer (aucun QSO actif)
    assert I(False, 'F4ABC', 'DL1XX') is False
    assert I(False, '', 'DL1XX') is False
    # en attente mais pas de QSO actif tracé -> ne bloque pas
    assert I(True, '', 'DL1XX') is False


def test_cle_anti_spam_idempotente():
    ctx = _ctx()
    # même DX + même message TX -> même clé (un seul push par cycle 15 s malgré re-décodes)
    a = ctx.eval("window.LogxFt8Copilote.cle('F4ABC', 'F4ABC F1XYZ -12')")
    b = ctx.eval("window.LogxFt8Copilote.cle('F4ABC', 'F4ABC F1XYZ -12')")
    c = ctx.eval("window.LogxFt8Copilote.cle('F4ABC', 'F4ABC F1XYZ RR73')")
    assert a == b
    assert a != c            # message différent (étape suivante) -> clé différente
