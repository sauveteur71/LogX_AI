# -*- coding: utf-8 -*-
"""Session autonome FT8 (logique pure) : validité = reflet de l'état radio."""
import os
import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_ft8_session.js')


@pytest.fixture()
def ctx():
    from py_mini_racer import py_mini_racer
    c = py_mini_racer.MiniRacer()
    c.eval('var window = {};')
    with open(JS, encoding='utf-8') as f:
        c.eval(f.read())
    # rendre l'API accessible au niveau global pour c.eval()
    c.eval('var LogxFt8Session = window.LogxFt8Session;')
    return c


EMP = "{band:'20m',dial_hz:14074000,mode:'USB-D',power_w:20}"
ETAT_OK = "{stop:false,cat_ok:true,horloge_ok:true,dial_tol_hz:50}"


def test_creer_session_armee(ctx):
    s = ctx.eval("JSON.stringify(LogxFt8Session.creerSession('copilote_qso',%s,'sid1'))" % EMP)
    import json
    d = json.loads(s)
    assert d['armed'] is True
    assert d['niveau'] == 'copilote_qso'
    assert d['sessionId'] == 'sid1'
    assert d['txCount'] == 0
    assert d['qsoActifDx'] is None


def test_session_valide_quand_tout_va(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,%s,%s).ok" % (EMP, EMP, ETAT_OK))
    assert r is True


def test_stop_invalide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,%s,{stop:true,cat_ok:true,horloge_ok:true,dial_tol_hz:50}).raison"
                 % (EMP, EMP))
    assert r == 'stop'


def test_changement_bande_invalide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,{band:'40m',dial_hz:14074000,mode:'USB-D',power_w:20},%s).raison"
                 % (EMP, ETAT_OK))
    assert r == 'radio'


def test_dial_hors_tolerance_invalide(ctx):
    # 14074000 -> 14074200 (200 Hz > tol 50) = changement de fréquence TX
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,{band:'20m',dial_hz:14074200,mode:'USB-D',power_w:20},%s).raison"
                 % (EMP, ETAT_OK))
    assert r == 'radio'


def test_dial_dans_tolerance_reste_valide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,{band:'20m',dial_hz:14074030,mode:'USB-D',power_w:20},%s).ok"
                 % (EMP, ETAT_OK))
    assert r is True


def test_cat_perdu_invalide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,%s,{stop:false,cat_ok:false,horloge_ok:true,dial_tol_hz:50}).raison"
                 % (EMP, EMP))
    assert r == 'cat'


def test_horloge_desync_invalide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,%s,{stop:false,cat_ok:true,horloge_ok:false,dial_tol_hz:50}).raison"
                 % (EMP, EMP))
    assert r == 'horloge'


def test_desarmee_invalide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');s.armed=false;"
                 "LogxFt8Session.sessionValide(s,%s,%s).raison" % (EMP, EMP, ETAT_OK))
    assert r == 'desarmee'


# --- Ordre de priorité par causes COMBINÉES ---
# Sans ces tests, une inversion de l'ordre des `if` passerait tous les
# tests à cause unique. On force ici la priorité relative.

def test_stop_prime_sur_desarmee(ctx):
    # stop:true ET session désarmée -> 'stop' doit primer sur 'desarmee'
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');s.armed=false;"
                 "LogxFt8Session.sessionValide(s,%s,{stop:true,cat_ok:true,horloge_ok:true,dial_tol_hz:50}).raison"
                 % (EMP, EMP))
    assert r == 'stop'


def test_cat_prime_sur_horloge(ctx):
    # cat_ok:false ET horloge_ok:false -> 'cat' doit primer sur 'horloge'
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,%s,{stop:false,cat_ok:false,horloge_ok:false,dial_tol_hz:50}).raison"
                 % (EMP, EMP))
    assert r == 'cat'


# --- Invalidation radio par composante SEULE ---
# Seuls bande + dial étaient testés ; on couvre mode et puissance isolés.

def test_changement_mode_seul_invalide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,{band:'20m',dial_hz:14074000,mode:'LSB-D',power_w:20},%s).raison"
                 % (EMP, ETAT_OK))
    assert r == 'radio'


def test_changement_puissance_seul_invalide(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,{band:'20m',dial_hz:14074000,mode:'USB-D',power_w:40},%s).raison"
                 % (EMP, ETAT_OK))
    assert r == 'radio'


def test_dial_pile_a_la_tolerance_reste_valide(ctx):
    # 14074000 -> 14074050 (drift exactement 50 = tol) : > tol est faux -> OK
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "LogxFt8Session.sessionValide(s,{band:'20m',dial_hz:14074050,mode:'USB-D',power_w:20},%s).ok"
                 % (EMP, ETAT_OK))
    assert r is True
