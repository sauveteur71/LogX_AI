# -*- coding: utf-8 -*-
"""Longueur des champs ADIF en OCTETS UTF-8 (pas en caractères).

Un champ accentué (COMMENT/NAME/QTH « café ») compte plus d'octets que de
caractères ; un lecteur ADIF strict (POTA, autres loggers) lit ce nombre
d'octets. Les trois jumeaux doivent être alignés : export serveur
(_adif_field), export client (adifField, logx_export_adif.js), parseur d'import
(_parse_adif_records, logx_qsl.py). Sans quoi un accent décale tout le record.
"""
import os
import re
import sys

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CONCOURS)

import logx_export as export   # noqa: E402
import logx_qsl as qsl         # noqa: E402


# ── Export serveur (_adif_field) ─────────────────────────────────────────────

def test_export_longueur_octets_accent():
    # « café » = 4 caractères mais 5 octets UTF-8 (é = 2 octets).
    assert export._adif_field('COMMENT', 'café') == '<COMMENT:5>café'


def test_export_ascii_inchange():
    # ASCII : octets == caractères, aucun changement de comportement.
    assert export._adif_field('CALL', 'F4GLD') == '<CALL:5>F4GLD'


def test_export_caractere_3_octets():
    # '€' = 3 octets ; 'a€' = 1 + 3 = 4 octets pour 2 caractères.
    assert export._adif_field('COMMENT', 'a€') == '<COMMENT:4>a€'


# ── Import (_parse_adif_records) : tranche sur les octets ─────────────────────

def test_import_tranche_sur_octets_sans_decaler():
    recs = qsl._parse_adif_records('<CALL:5>F4GLD<COMMENT:5>café<BAND:2>2m<EOR>')
    assert recs[0]['CALL'] == 'F4GLD'
    assert recs[0]['COMMENT'] == 'café'       # 5 octets lus correctement
    assert recs[0]['BAND'] == '2m'            # le champ suivant N'EST PAS décalé


def test_roundtrip_accent_export_puis_import():
    champ = export._adif_field('COMMENT', 'château café €')
    recs = qsl._parse_adif_records(champ + '<EOR>')
    assert recs[0]['COMMENT'] == 'château café €'


# ── Export client (adifField, logx_export_adif.js) — même règle ──────────────

def _js_adiffield():
    racer = pytest.importorskip('py_mini_racer')
    src = open(os.path.join(CONCOURS, 'logx_export_adif.js'), encoding='utf-8').read()

    def _fn(nom):
        m = re.search(r'\nfunction ' + re.escape(nom) + r'\s*\(', src)
        assert m, nom
        i = src.index('function', m.start())
        prof = 0
        j = src.index('{', i)
        for k in range(j, len(src)):
            if src[k] == '{':
                prof += 1
            elif src[k] == '}':
                prof -= 1
                if prof == 0:
                    return src[i:k + 1]
        raise AssertionError(nom)

    c = racer.MiniRacer()
    c.eval(_fn('_adifByteLen'))
    c.eval(_fn('adifField'))
    return c


def test_client_adiffield_longueur_octets():
    c = _js_adiffield()
    # <COMMENT:5>café + espace final (format du jumeau client).
    assert c.eval("adifField('COMMENT','café')") == '<COMMENT:5>café '
    assert c.eval("adifField('CALL','F4GLD')") == '<CALL:5>F4GLD '


def test_client_byte_len_reste_coherent_avec_python():
    c = _js_adiffield()
    for s in ['café', 'a€', 'château', 'F4GLD', 'DL/F4GLD/P']:
        assert c.eval("_adifByteLen(%r)" % s) == len(s.encode('utf-8')), s
