# -*- coding: utf-8 -*-
"""formatLastErrorForReport() (concours/logx_statusbar.js) — revue
adversariale du commit a1bc360 ("Journal d'erreurs local"), deux défauts
vérifiés indépendamment :

1. [MEDIUM] La dernière erreur connue du journal local était TOUJOURS jointe
   au corps de l'issue GitHub pré-remplie, même si elle datait de plusieurs
   heures et n'avait aucun rapport avec le problème que l'opérateur est en
   train de signaler maintenant.

2. [MEDIUM] e.message n'était jamais borné avant d'entrer dans le corps de
   l'issue, contrairement à `tail` (le traceback) qui l'est déjà à 400
   caractères. Un message d'exception anormalement long pouvait à lui seul
   dépasser REPORT_BODY_MAX : comme le bloc erreur est placé AVANT la
   description libre de l'opérateur (voir commentaire dans openReportIssue),
   la troncature finale de sécurité supprimait alors la description
   ENTIÈRE, ne laissant que la trace technique.

Depuis la revue du commit 8194b55 (passage aux GitHub Issue Forms,
tests/test_report_issue_form_prefill.py), `body` a été remplacé par des
paramètres d'URL séparés (`description`, `journal-technique`, etc.) :
REPORT_BODY_MAX est devenu REPORT_FIELD_MAX, et les tests « post-fix »
ci-dessous vérifient ces nouveaux paramètres. Les tests « avant fix », eux,
rejouent le code historique du commit a1bc360 (qui prédate 8194b55) et
utilisent donc toujours l'ancien paramètre `body`.

Même technique que tests/test_report_issue_unicode.py : le VRAI code est
extrait tel quel du fichier source (comptage d'accolades), PAS retapé, et
exécuté dans un moteur JS réel (V8 via py_mini_racer). Chaque test « post-fix »
a son pendant qui rejoue le code TEL QU'IL ÉTAIT au commit a1bc360 (avant ce
fix) pour prouver concrètement que le scénario se produisait bien à l'époque."""
import datetime
import json
import os
import re
import subprocess
import urllib.parse

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_statusbar.js')

PRE_FIX_REV = 'a1bc360'


def _extract_report_block(src):
    """Extrait tout le bloc « signaler un problème » — des constantes
    REPORT_REPO_FALLBACK/REPORT_FIELD_MAX jusqu'à la fin de la fonction
    openReportIssue() incluse (donc aussi _errState/formatLastErrorForReport/
    refreshErrorsCheck, situés entre les deux) — par comptage d'accolades,
    pour récupérer le VRAI code, pas une réécriture qui pourrait diverger
    du bug (même technique que tests/test_report_issue_unicode.py)."""
    start = src.index('const REPORT_REPO_FALLBACK')
    func_start = src.index('function openReportIssue(', start)
    brace_open = src.index('{', func_start)
    depth = 0
    i = brace_open
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1


def _current_src():
    with open(JS_PATH, encoding='utf-8') as f:
        return f.read()


def _pre_fix_src():
    out = subprocess.run(
        ['git', 'show', f'{PRE_FIX_REV}:concours/logx_statusbar.js'],
        cwd=BASE, capture_output=True, text=True, encoding='utf-8', check=True)
    return out.stdout


# ─── Contexte JS minimal : pas besoin du DOM complet (le bloc extrait ne
# touche jamais le DOM), juste navigator/prompt/alert/window.open mockés,
# comme tests/test_report_issue_unicode.py ────────────────────────────────
_HARNESS_PREAMBLE = r"""
var navigator = { platform: 'TestPlatform', userAgent: 'TestUA/1.0' };
var openedUrl = null;
var window = { open: function(url){ openedUrl = url; return {}; } };
var lastAlert = null;
function alert(msg){ lastAlert = msg; }
var promptReturn = '';
function prompt(msg, def){ return promptReturn; }
var _updState = { current: '1.2.3', repo: 'octo/repo' };
function fetch(){ return Promise.resolve({ ok:false }); }
"""


def _make_ctx(block_src):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_HARNESS_PREAMBLE)
    ctx.eval(block_src)
    return ctx


def _set_prompt_return(ctx, py_str):
    ctx.eval('promptReturn = ' + json.dumps(py_str) + ';')


def _set_err_state(ctx, ts, err_type, message, traceback_text, thread='MainThread'):
    """Simule le résultat d'un GET /debug/errors déjà reçu par
    refreshErrorsCheck() — `_errState` est un `let` du bloc extrait, mais un
    `let` de premier niveau reste accessible depuis un eval() ultérieur dans
    le même contexte V8 (vérifié : c'est le mécanisme que refreshErrorsCheck
    utilise réellement en tâche de fond)."""
    payload = {'errors': [{'ts': ts, 'thread': thread, 'type': err_type,
                            'message': message, 'traceback': traceback_text}]}
    ctx.eval('_errState = ' + json.dumps(payload) + ';')


def _url_param(url, name):
    m = re.search(r'[?&]' + name + r'=(.*?)(?:&|$)', url)
    assert m, f"paramètre {name} introuvable dans {url!r}"
    return m.group(1)


def _url_param_optional(url, name):
    """Comme _url_param, mais renvoie None au lieu d'échouer si absent — le
    paramètre `journal-technique` n'existe que si une erreur récente a été
    trouvée (voir openReportIssue), contrairement à l'ancien `body` qui
    existait toujours."""
    m = re.search(r'[?&]' + name + r'=(.*?)(?:&|$)', url)
    return m.group(1) if m else None


def _run_and_get_journal(ctx, description):
    """Le contenu autrefois placé dans le paramètre `body` (plateforme +
    dernière erreur) part désormais dans le champ `journal-technique` du
    formulaire GitHub Issue Forms (bug.yml) — voir revue du commit 8194b55."""
    _set_prompt_return(ctx, description)
    ctx.eval('openReportIssue();')
    assert ctx.eval('lastAlert') is None
    url = ctx.eval('openedUrl')
    assert url is not None
    raw = _url_param_optional(url, 'journal-technique')
    return urllib.parse.unquote(raw) if raw is not None else None


def _run_and_get_description(ctx, description):
    _set_prompt_return(ctx, description)
    ctx.eval('openReportIssue();')
    assert ctx.eval('lastAlert') is None
    url = ctx.eval('openedUrl')
    assert url is not None
    return urllib.parse.unquote(_url_param(url, 'description'))


def _run_and_get_body(ctx, description):
    """Réservé aux tests « avant fix » (code historique du commit
    PRE_FIX_REV, qui prédate le passage aux GitHub Issue Forms du commit
    8194b55) : à cette époque, tout partait dans un unique paramètre `body`."""
    _set_prompt_return(ctx, description)
    ctx.eval('openReportIssue();')
    assert ctx.eval('lastAlert') is None
    url = ctx.eval('openedUrl')
    assert url is not None
    return urllib.parse.unquote(_url_param(url, 'body'))


SAMPLE_TRACEBACK = ('Traceback (most recent call last):\n'
                     '  File "logx_serveur.py", line 42, in <module>\n'
                     'ValueError: panne réseau')


# ─── Problème 1 (MEDIUM, statusbar) : dernière erreur non bornée dans le temps

def test_erreur_recente_est_jointe_au_rapport():
    """Non-régression : une erreur qui vient tout juste de se produire reste
    jointe (c'est tout l'intérêt du mécanisme) — dans le champ
    `journal-technique` du formulaire Issue Forms (voir 8194b55)."""
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    recent_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _set_err_state(ctx, recent_ts, 'ValueError', 'panne réseau', SAMPLE_TRACEBACK)

    journal = _run_and_get_journal(ctx, 'Le bouton export ADIF ne répond plus.')

    assert journal is not None
    assert 'panne réseau' in journal


def test_erreur_ancienne_nest_pas_jointe_au_rapport():
    """Reproduction concrète du problème [MEDIUM] : une erreur vieille de 3
    heures (thread de fond mort il y a longtemps, sans rapport avec ce que
    l'opérateur signale maintenant) ne doit plus polluer le rapport. Le champ
    `journal-technique` reste donc réduit à la plateforme (pas d'erreur)."""
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    old_ts = (datetime.datetime.now() - datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
    _set_err_state(ctx, old_ts, 'ValueError', 'panne réseau', SAMPLE_TRACEBACK)

    journal = _run_and_get_journal(ctx, 'Le bouton export ADIF ne répond plus.')

    assert journal is not None  # toujours présent (plateforme), mais sans l'erreur
    assert 'panne réseau' not in journal


def test_reproduction_avant_fix_commit_a1bc360_erreur_ancienne_est_quand_meme_jointe():
    """Contrôle négatif : rejoue EXACTEMENT le code du commit a1bc360 (avant
    ce fix) avec la même erreur vieille de 3 heures — confirme que le
    scénario se produisait bien à l'époque (aucun filtre de fraîcheur)."""
    block = _extract_report_block(_pre_fix_src())
    ctx = _make_ctx(block)
    old_ts = (datetime.datetime.now() - datetime.timedelta(hours=3)).strftime('%Y-%m-%d %H:%M:%S')
    _set_err_state(ctx, old_ts, 'ValueError', 'panne réseau', SAMPLE_TRACEBACK)

    body = _run_and_get_body(ctx, 'Le bouton export ADIF ne répond plus.')

    assert 'Dernière erreur du journal local' in body
    assert 'panne réseau' in body


# ─── Problème 2 (MEDIUM, statusbar) : e.message jamais borné ──────────────

def test_message_derreur_tres_long_ne_supprime_pas_la_description():
    """Reproduction concrète du problème [MEDIUM] : un message d'exception
    de 3000 caractères ne doit ni apparaître intégralement dans le rapport,
    ni faire disparaître la description libre de l'opérateur. Depuis
    8194b55/le passage aux Issue Forms, `description` et `journal-technique`
    sont deux paramètres d'URL DISTINCTS (donc deux troncatures
    indépendantes) : ce scénario est désormais structurellement impossible,
    pas seulement évité par un bon ordre de concaténation."""
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    recent_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    long_message = 'X' * 3000
    _set_err_state(ctx, recent_ts, 'ValueError', long_message, SAMPLE_TRACEBACK)
    description = 'Le bouton export ADIF ne répond plus après un import de gros fichier.'

    _set_prompt_return(ctx, description)
    ctx.eval('openReportIssue();')
    assert ctx.eval('lastAlert') is None
    url = ctx.eval('openedUrl')
    journal = urllib.parse.unquote(_url_param(url, 'journal-technique'))
    got_description = urllib.parse.unquote(_url_param(url, 'description'))

    assert long_message not in journal, 'le message doit être tronqué, pas recopié en entier'
    assert got_description == description, (
        'la description opérateur a été altérée alors que rien ne justifie sa troncature ici')


def test_reproduction_avant_fix_commit_a1bc360_message_tres_long_supprime_la_description():
    """Contrôle négatif : rejoue EXACTEMENT le code du commit a1bc360 (avant
    ce fix) avec le même message de 3000 caractères — confirme que la
    troncature finale supprimait bien la description utilisateur à l'époque."""
    block = _extract_report_block(_pre_fix_src())
    ctx = _make_ctx(block)
    recent_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    long_message = 'X' * 3000
    _set_err_state(ctx, recent_ts, 'ValueError', long_message, SAMPLE_TRACEBACK)
    description = 'Le bouton export ADIF ne répond plus après un import de gros fichier.'

    body = _run_and_get_body(ctx, description)

    assert description not in body, (
        'le scénario de reproduction n\'est plus valide (la description survit déjà '
        'avant le fix) : à revoir')


def test_message_court_reste_intact():
    """Non-régression : un message d'exception court et normal n'est pas
    tronqué inutilement."""
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    recent_ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    _set_err_state(ctx, recent_ts, 'ValueError', 'panne réseau', SAMPLE_TRACEBACK)

    journal = _run_and_get_journal(ctx, 'Description normale.')

    assert journal is not None
    assert 'ValueError: panne réseau' in journal


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    assert 'QSO Director' not in _current_src()
