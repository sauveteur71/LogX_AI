# -*- coding: utf-8 -*-
"""FT8 — toggleRx ne doit pas lancer deux démarrages RX concurrents (audit
STRATE-3). demarrerRx() est async et ne pose rxActif=true qu'à la FIN, après
`await getUserMedia`. Un double-clic sur « Écouter » PENDANT l'invite de
permission passait deux fois le test `if(rxActif)` (toujours false) et lançait
demarrerRx() deux fois : deux getUserMedia, deux AudioContext, et les variables
module (ctx/stream/source/proc) écrasées par le second appel — le premier
pipeline fuit (jamais fermé). Le panadapter gère déjà ce cas via un drapeau
`demarrageEnCours` (logx_panadapter.html:972) ; toggleRx doit faire pareil.

La garde vit DANS toggleRx : on teste le vrai toggleRx avec un demarrerRx
factice compteur (le mannequin ne porte aucune des propriétés testées)."""
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(CONCOURS, 'logx_ft8.html')


def _fn(nom):
    """Extrait `function nom(...){...}` OU `window.nom = function(...){...}`."""
    src = open(HTML, encoding='utf-8').read()
    # Forme assignée : window.nom = [async] function(...){...}
    m = re.search(r'\n\s*window\.' + re.escape(nom) + r'\s*=\s*(async\s+)?function\s*\(', src)
    if m:
        prefix = 'window.%s = %sfunction' % (nom, 'async ' if m.group(1) else '')
    else:
        # Forme déclarée : [async] function nom(...){...}
        m = re.search(r'\n\s*(async\s+)?function ' + re.escape(nom) + r'\s*\(', src)
        assert m, 'fonction %s introuvable' % nom
        prefix = ('async ' if m.group(1) else '') + 'function'
    i = src.index('function', m.start())
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                # Remplace l'en-tête d'origine par le préfixe reconstruit.
                body = src[src.index('(', i):k + 1]
                return prefix + body
    raise AssertionError('accolade fermante introuvable')


# demarrerRx factice : compte les appels, renvoie une promesse dont on garde
# resolve ET reject sous la main (simule getUserMedia bloqué sur l'invite).
_HARNESS = """
var rxActif = false;
var rxDemarrageEnCours = false;   // état module réel (garde à ajouter)
var demarreCount = 0, arreteCount = 0;
var _resolveDem = null, _rejectDem = null;
function demarrerRx(){ demarreCount++; return new Promise(function(res, rej){ _resolveDem = res; _rejectDem = rej; }); }
function arreterRx(){ arreteCount++; rxActif = false; }
var _el = { textContent:'', classList:{ add:function(){}, remove:function(){} } };
var document = { getElementById:function(){ return _el; } };
var window = {};
"""


def _ctx():
    racer = pytest.importorskip('py_mini_racer')
    c = racer.MiniRacer()
    c.eval(_HARNESS)
    c.eval(_fn('toggleRx'))   # définit window.toggleRx
    return c


def test_double_clic_pendant_le_demarrage_ne_lance_qu_une_ecoute():
    c = _ctx()
    c.eval("window.toggleRx();")   # premier clic : démarre (getUserMedia en attente)
    assert c.eval("demarreCount") == 1
    c.eval("window.toggleRx();")   # second clic pendant l'invite : doit être ignoré
    assert c.eval("demarreCount") == 1, "ré-entrance : demarrerRx lancé deux fois en concurrence"


def test_redemarrable_apres_echec_du_demarrage():
    c = _ctx()
    c.eval("window.toggleRx();")
    assert c.eval("demarreCount") == 1
    # Le démarrage échoue (permission refusée) : la garde doit se relâcher pour
    # qu'un nouveau clic puisse relancer une écoute.
    c.eval("if(_rejectDem) _rejectDem(new Error('permission refusée'));")
    for _ in range(4):
        c.eval("0")
    c.eval("window.toggleRx();")
    assert c.eval("demarreCount") == 2, "garde coincée après échec : impossible de relancer l'écoute"
