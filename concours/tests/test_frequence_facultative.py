# -*- coding: utf-8 -*-
"""Concours où la BANDE suffit : champ FRÉQUENCE masqué (F4GLD 24/10/2026).

Règlement CQ WW (cqww.com/rules.htm, vérifié le 24/10/2026) : le log doit
montrer « frequency (or band) ». Demande : « si le concours autorise juste la
bande, ne mettre que la bande ». Vérifié en navigateur (CQ_WW_SSB, sans CAT) :
champ masqué, QSO enregistré avec freq '' (la fréquence d'appel par défaut de
la bande n'est PAS enregistrée), Cabrillo « QSO:  1800 PH … » ; WPX : champ
toujours visible."""
import os
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_logbook.js'), encoding='utf-8').read()
HTML = open(os.path.join(BASE, 'logx_logbook.html'), encoding='utf-8').read()


def _code(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'(?m)//.*$', '', s)


CODE = _code(JS)


def _entree(cid):
    m = re.search(r"'%s'\s*:\s*\{([^}]*)\}" % cid, CODE)
    assert m, cid
    return m.group(1)


def test_seuls_les_concours_au_reglement_verifie_sont_marques():
    for cid in ('CQ_WW_SSB', 'CQ_WW_CW'):
        assert re.search(r'freq_facultative\s*:\s*true', _entree(cid)), cid
    bloc = CODE[CODE.index('const CONTEST_EXCHANGE'):CODE.index('let currentExchange')]
    assert len(re.findall(r'freq_facultative\s*:\s*true', bloc)) == 2   # pas d'extension non sourcée


def test_le_champ_est_masque_selon_le_concours():
    f = CODE[CODE.index('function applyExchangeFormat'):]
    f = f[:f.index('\nfunction ')]
    assert re.search(r"getElementById\('inputFreq'\)\?\.closest\('\.field-group'\)", f)
    assert re.search(r"classList\.toggle\('freq-facultative',\s*!!ex\.freq_facultative\)", f)
    assert re.search(r'\.field-group\.freq-facultative\{display:none!important\}', HTML)


def test_l_enregistrement_n_exige_plus_une_frequence_invisible():
    f = CODE[CODE.index('async function submitQSO'):]
    f = f[:f.index('\nfunction ', 10) if '\nfunction ' in f[10:] else 20000]
    assert re.search(r'if\(!freq && !currentExchange\.freq_facultative\)', f)


def test_la_frequence_par_defaut_n_est_pas_enregistree_sans_cat():
    f = CODE[CODE.index('async function submitQSO'):]
    assert re.search(r"const freqQso = \(currentExchange\.freq_facultative && !catActif\) \? '' : freq;", f)
    assert re.search(r'rigState\.enabled && rigState\.freq_khz > 0', f)
    assert re.search(r'freq:\s*freqQso', f)
