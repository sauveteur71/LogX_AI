# -*- coding: utf-8 -*-
"""Auto-calage FT8 : en arrivant sur une bande, la page FT8 cale la radio sur la
fréquence d'appel FT8 de cette bande (demandé par F4GLD).

Côté SERVEUR : /rig/qsy accepte {band, dial_mode} et calcule la fréquence via la
SOURCE UNIQUE logx_frequences.dial_freq (jamais une table dupliquée côté client).
Côté CLIENT : pollRig déclenche le QSY une seule fois par ARRIVÉE sur une bande.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_frequences as fq     # noqa: E402
import logx_http as httpmod      # noqa: E402

FT8_HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'logx_ft8.html')


# ─── Correspondance clé interne -> label longueur d'onde (source unique) ─────

def test_label_bande_interne_vers_longueur_onde():
    assert fq.label_bande('14') == '20m'
    assert fq.label_bande('144') == '2m'
    assert fq.label_bande('432') == '70cm'
    assert fq.label_bande('7') == '40m'
    assert fq.label_bande('20m') == '20m'      # idempotent (déjà un label)


# ─── Helper serveur : résolution de la fréquence de QSY ──────────────────────

def test_freq_explicite_prioritaire():
    assert httpmod._qsy_freq_hz_depuis_payload({'freq_hz': 14074000}) == 14074000
    assert httpmod._qsy_freq_hz_depuis_payload({'freq_khz': 7074}) == 7074000
    # une fréquence explicite prime sur band (jamais recalculée à tort)
    assert httpmod._qsy_freq_hz_depuis_payload({'freq_khz': 7074, 'band': '14'}) == 7074000


def test_band_interne_donne_la_frequence_ft8():
    # clé interne de la page FT8 -> fréquence d'appel FT8 réelle
    assert httpmod._qsy_freq_hz_depuis_payload({'band': '14', 'dial_mode': 'FT8'}) == 14074000
    assert httpmod._qsy_freq_hz_depuis_payload({'band': '144', 'dial_mode': 'FT8'}) == 144174000
    # dial_mode par défaut = FT8
    assert httpmod._qsy_freq_hz_depuis_payload({'band': '28'}) == 28074000


def test_band_label_accepte_aussi():
    assert httpmod._qsy_freq_hz_depuis_payload({'band': '20m', 'dial_mode': 'FT8'}) == 14074000


def test_band_inconnue_rend_zero():
    assert httpmod._qsy_freq_hz_depuis_payload({'band': 'ZZ'}) == 0
    assert httpmod._qsy_freq_hz_depuis_payload({}) == 0


# ─── Client : le QSY part sur CHANGEMENT de bande, une seule fois ────────────

def _sans_commentaires(src):
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'//.*$', '', li) for li in src.splitlines())


def test_pollrig_cale_sur_ft8_au_changement_de_bande():
    code = _sans_commentaires(open(FT8_HTML, encoding='utf-8').read())
    i = code.index('async function pollRig()')
    corps = code[i:code.index('\n  }', i)]
    # QSY conditionné au CHANGEMENT de bande (pas à chaque sondage -> pas de boucle)
    assert re.search(r"b\s*&&\s*b\s*!==\s*_dernierBandeFt8", corps), (
        'le calage doit être conditionné au changement de bande :\n' + corps)
    # mémorise la bande calée AVANT d'émettre la requête (anti-rafale)
    assert '_dernierBandeFt8 = b' in corps
    # appelle /rig/qsy avec la bande et le mode FT8 (jamais une fréquence en dur ici)
    assert "/rig/qsy" in corps and "dial_mode" in corps and "'FT8'" in corps, corps
    # dans la branche CAT actif uniquement (rigActif) — pas quand le CAT est off
    assert corps.index('d.enabled') < corps.index('_dernierBandeFt8 = b')
