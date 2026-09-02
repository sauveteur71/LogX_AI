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
    # Charger d'abord le copilote FT8 (dépendance)
    copilote_path = os.path.join(CONCOURS, 'logx_ft8_copilote.js')
    with open(copilote_path, encoding='utf-8') as f:
        c.eval(f.read())
    # Puis la session
    with open(JS, encoding='utf-8') as f:
        c.eval(f.read())
    # rendre l'API accessible au niveau global pour c.eval()
    c.eval('var LogxFt8Session = window.LogxFt8Session;')
    c.eval('var LogxFt8Copilote = window.LogxFt8Copilote;')
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


# --- Driver N3 : prochaineTrameQso (enchaînement QSO complet) ---

def test_qso_repond_a_un_appel(ctx):
    # « F4GLD DL1ABC JO31 » (on m'appelle avec grille) -> je réponds report
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineTrameQso(s,"
                 "{message:'F4GLD DL1ABC JO31',snr:-12,dx:'DL1ABC'},'F4GLD'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'emettre'
    assert d['message'] == 'DL1ABC F4GLD -12'
    assert d['dx'] == 'DL1ABC'


def test_qso_accuse_report(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineTrameQso(s,"
                 "{message:'F4GLD DL1ABC R-08',snr:-10,dx:'DL1ABC'},'F4GLD'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'emettre'
    assert d['message'] == 'DL1ABC F4GLD RR73'


def test_qso_cloture_donne_loguer(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineTrameQso(s,"
                 "{message:'F4GLD DL1ABC 73',snr:-10,dx:'DL1ABC'},'F4GLD'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'loguer'
    assert d['dx'] == 'DL1ABC'


def test_qso_ignore_pas_pour_moi(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineTrameQso(s,"
                 "{message:'CQ SP9XYZ KO02',snr:-5,dx:'SP9XYZ'},'F4GLD'))" % EMP)
    import json
    assert json.loads(r)['action'] == 'ignorer'


# --- Driver N4 : prochaineAction (CQ + pile-up) ---

def test_n4_appelle_cq_si_personne(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_cq',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineAction(s,[],'F4GLD','JN15'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'cq'
    assert d['message'] == 'CQ F4GLD JN15'


def test_n4_engage_un_appelant(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_cq',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineAction(s,"
                 "[{message:'F4GLD IK2ABC JN45',snr:-9,dx:'IK2ABC'}],'F4GLD','JN15'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'emettre'
    assert d['dx'] == 'IK2ABC'
    assert d['engager'] == 'IK2ABC'
    assert d['message'] == 'IK2ABC F4GLD -09'


def test_n4_poursuit_le_qso_en_cours(ctx):
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_cq',%s,'x');s.qsoActifDx='IK2ABC';"
                 "JSON.stringify(LogxFt8Session.prochaineAction(s,"
                 "[{message:'F4GLD IK2ABC R-11',snr:-9,dx:'IK2ABC'}],'F4GLD','JN15'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'emettre'
    assert d['message'] == 'IK2ABC F4GLD RR73'


def test_n3_attend_si_aucun_appel(ctx):
    # niveau QSO (pas CQ) : sans QSO engagé ni appel pour moi -> attendre (pas de CQ)
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_qso',%s,'x');"
                 "JSON.stringify(LogxFt8Session.prochaineAction(s,[],'F4GLD','JN15'))" % EMP)
    import json
    assert json.loads(r)['action'] == 'attendre'


def test_n4_un_qso_a_la_fois_pile_up(ctx):
    # Pile-up : QSO en cours avec IK2ABC ET un NOUVEL appelant OTHER99 dans le
    # même cycle. La priorité au bloc « QSO en cours » doit être verrouillée :
    # on POURSUIT IK2ABC (RR73), on n'engage PAS OTHER99. Sans le bloc 1, le
    # fallback engagerait OTHER99 (premier décode qui m'appelle).
    r = ctx.eval("var s=LogxFt8Session.creerSession('copilote_cq',%s,'x');s.qsoActifDx='IK2ABC';"
                 "JSON.stringify(LogxFt8Session.prochaineAction(s,"
                 "[{message:'F4GLD OTHER99 JN00',snr:-5,dx:'OTHER99'},"
                 "{message:'F4GLD IK2ABC R-11',snr:-9,dx:'IK2ABC'}],'F4GLD','JN15'))" % EMP)
    import json
    d = json.loads(r)
    assert d['action'] == 'emettre'
    assert d['dx'] == 'IK2ABC'
    assert d['message'] == 'IK2ABC F4GLD RR73'
    assert d['engager'] == ''
