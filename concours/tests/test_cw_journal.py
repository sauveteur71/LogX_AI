# -*- coding: utf-8 -*-
"""Journal TX CW structuré (logx_cw_journal) : enregistrement borné + horodaté."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logx_cw_journal as j


def setup_function(_):
    j._vider()


def test_enregistre_texte_backend_wpm_et_horodatage():
    j.enregistrer('CQ TEST F4GLD', 'winkeyer', wpm=28,
                  _horloge=lambda: 1_700_000_000)   # instant fixe -> horodatage stable
    e = j.entrees()
    assert len(e) == 1
    assert e[0]['text'] == 'CQ TEST F4GLD'
    assert e[0]['backend'] == 'winkeyer' and e[0]['wpm'] == 28
    assert e[0]['time'].endswith('Z') and 'T' in e[0]['time']   # ISO UTC


def test_ordre_plus_recent_en_dernier():
    for i in range(3):
        j.enregistrer('msg%d' % i, 'cat')
    textes = [x['text'] for x in j.entrees()]
    assert textes == ['msg0', 'msg1', 'msg2']


def test_borne_a_200_entrees():
    for i in range(250):
        j.enregistrer('x%d' % i, 'winkeyer')
    e = j.entrees(1000)
    assert len(e) == 200                       # plafonné
    assert e[0]['text'] == 'x50'               # les 50 plus anciennes évincées
    assert e[-1]['text'] == 'x249'


def test_limite_retourne_les_derniers():
    for i in range(10):
        j.enregistrer('n%d' % i, 'cat')
    e = j.entrees(3)
    assert [x['text'] for x in e] == ['n7', 'n8', 'n9']


def test_http_cable_le_journal_aux_deux_succes_et_expose_le_get():
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            'logx_http.py'), encoding='utf-8').read()
    # appels RÉELS aux deux chemins de succès (chaîne exacte, pas un commentaire)
    assert "cwj.enregistrer(res.get('text'), 'winkeyer', wpm=res.get('wpm'))" in src
    assert "cwj.enregistrer(res.get('text'), 'cat')" in src
    # endpoint GET de lecture exposé
    assert "path == '/rig/cw/journal'" in src


def test_texte_tronque_et_ne_leve_jamais():
    j.enregistrer('A' * 500, 'winkeyer')
    assert len(j.entrees()[-1]['text']) == 200
    # entrée aberrante : ne doit pas lever
    j.enregistrer(None, None, wpm='?', _horloge=lambda: (_ for _ in ()).throw(RuntimeError()))
    # le compteur n'a pas augmenté à cause de l'horloge qui lève -> 1 seule entrée
    assert len(j.entrees()) == 1
