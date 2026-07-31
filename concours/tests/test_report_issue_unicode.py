# -*- coding: utf-8 -*-
"""openReportIssue() (concours/logx_statusbar.js, commit f20799a — bouton
« signaler un problème » de la barre de statut) — revue adversariale de ce
commit, deux défauts vérifiés indépendamment :

1. [HIGH] Les .slice() du titre/corps comptent des unités UTF-16 brutes sans
   se soucier des paires de substitution (emoji, etc.). Si la coupe tombe
   pile au milieu d'une paire, il reste un demi-caractère orphelin ;
   encodeURIComponent() lève alors une URIError NON interceptée (aucun
   try/catch autour) et le bouton « signaler un problème » échoue en
   silence — aucune Issue GitHub ne s'ouvre, aucun message d'erreur.

2. [MEDIUM] REPORT_BODY_MAX=1500 borne body.length (longueur BRUTE), pas la
   longueur réellement envoyée dans l'URL après encodeURIComponent(). Un
   texte français accentué encode chaque caractère non-ASCII sur 6
   caractères (é -> %C3%A9) : un corps de 1400 caractères accentués passe le
   test `body.length > REPORT_BODY_MAX` sans être tronqué, alors que l'URL
   finale envoyée fait ~8400 caractères, largement au-dessus de la marge
   prévue contre le 414 URI Too Long visée par REPORT_BODY_MAX.

Depuis la revue du commit 8194b55 (passage aux GitHub Issue Forms,
tests/test_report_issue_form_prefill.py), REPORT_BODY_MAX est devenu
REPORT_FIELD_MAX et le paramètre `body` a été remplacé par plusieurs
paramètres d'URL (`description`, `journal-technique`, etc.) : les tests
« post-fix » ci-dessous lisent désormais `description`. Les tests « avant
fix » rejouent le code historique de f20799a (qui prédate 8194b55) et
utilisent donc toujours `body`.

Ce module exécute le VRAI code de openReportIssue() — extrait tel quel du
fichier source par comptage d'accolades (même technique que
tests/test_config_html_sota_qrz_race.py), PAS retapé — dans un moteur JS réel
(V8 via py_mini_racer, même technique que tests/test_awards_clublog_realtime_blocked_js.py).
window.open()/prompt()/alert() sont mockés pour piloter et observer
l'exécution sans navigateur. Chaque test « post-fix » a son pendant qui
rejoue le code TEL QU'IL ÉTAIT au commit f20799a (avant ce fix, via
`git show f20799a:concours/logx_statusbar.js`) pour prouver concrètement que
le scénario se produisait bien à l'époque."""
import json
import os
import re
import subprocess

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')
try:
    from py_mini_racer import JSEvalException
except ImportError:  # versions plus anciennes : la classe vit dans le sous-module
    from py_mini_racer.py_mini_racer import JSEvalException

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_statusbar.js')

PRE_FIX_REV = 'f20799a'


def _extract_report_block(src):
    """Extrait tout le bloc « signaler un problème » — des constantes
    REPORT_REPO_FALLBACK/REPORT_BODY_MAX jusqu'à la fin de la fonction
    openReportIssue() incluse — par comptage d'accolades, pour récupérer le
    VRAI code (y compris les fonctions utilitaires dont il dépend), pas une
    réécriture qui pourrait diverger du bug."""
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
# touche jamais le DOM), juste navigator/prompt/alert/window.open mockés ────
_HARNESS_PREAMBLE = r"""
// rcT : le VRAI logx_statusbar.js definit ce repli en tete de son IIFE
// (`const rcT = s => (window.rcT ? window.rcT(s) : s)`), au-dessus du bloc que
// ce test extrait. Sans lui ici, le bloc extrait leve « rcT is not defined » —
// un echec du BANC D'ESSAI, pas du produit : en page reelle, le repli est la.
function rcT(s){ return s; }
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


def _url_param(url, name):
    """Extrait la valeur BRUTE (encore encodée) d'un paramètre de query
    string — pas de décodage ici, on veut mesurer/valider exactement ce que
    JS a produit avec encodeURIComponent()."""
    m = re.search(r'[?&]' + name + r'=(.*?)(?:&|$)', url)
    assert m, f"paramètre {name} introuvable dans {url!r}"
    return m.group(1)


EMOJI = '\U0001F600'  # 😀 — paire de substitution UTF-16 (2 unités)


# ─── Problème 1 : coupe en plein milieu d'une paire de substitution ────────

def test_titre_avec_emoji_pile_sur_la_coupe_a_80_ne_leve_pas_duriexception():
    """firstLine = 79 'a' + un emoji (2 unités UTF-16) : l'ancien
    firstLine.slice(0,80) coupait pile après la première moitié de l'emoji.
    Après fix, le titre doit rester valide et contenir l'emoji ENTIER."""
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    description = 'a' * 79 + EMOJI + ' reste du texte après la coupe'
    _set_prompt_return(ctx, description)

    ctx.eval('openReportIssue();')  # ne doit lever aucune exception JS

    assert ctx.eval('lastAlert') is None, "le filet try/catch n'aurait pas dû se déclencher ici"
    url = ctx.eval('openedUrl')
    assert url is not None

    title_encoded = _url_param(url, 'title')
    title_decoded = __import__('urllib.parse', fromlist=['unquote']).unquote(title_encoded)
    assert title_decoded == '[Bug] ' + 'a' * 79 + EMOJI, (
        "l'emoji doit être conservé ENTIER (troncature en points de code, "
        "pas en unités UTF-16) : " + title_decoded)


def test_reproduction_avant_fix_commit_f20799a_leve_uriexception_non_interceptee():
    """Contrôle négatif : rejoue EXACTEMENT le openReportIssue() du commit
    f20799a (avant ce fix) avec le même emoji pile sur la coupe à 80 — sans
    try/catch, encodeURIComponent() plante et l'exception JS remonte non
    interceptée (le bouton échoue en silence côté navigateur)."""
    block = _extract_report_block(_pre_fix_src())
    ctx = _make_ctx(block)
    description = 'a' * 79 + EMOJI + ' reste du texte après la coupe'
    _set_prompt_return(ctx, description)

    with pytest.raises(JSEvalException, match='URIError'):
        ctx.eval('openReportIssue();')


def test_emoji_en_toute_fin_de_texte_reste_valide():
    """Cas limite supplémentaire : l'emoji tombe exactement sur l'avant-
    dernier/dernier point de code retenu (aucune marge après)."""
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    description = 'b' * 78 + EMOJI  # 78 + 1 code point (emoji) = 79 <= 80
    _set_prompt_return(ctx, description)

    ctx.eval('openReportIssue();')

    assert ctx.eval('lastAlert') is None
    url = ctx.eval('openedUrl')
    title_encoded = _url_param(url, 'title')
    title_decoded = __import__('urllib.parse', fromlist=['unquote']).unquote(title_encoded)
    assert title_decoded == '[Bug] ' + 'b' * 78 + EMOJI


# ─── Problème 2 : REPORT_FIELD_MAX doit borner la longueur ENCODÉE ────────
# (REPORT_BODY_MAX à l'époque de f20799a ; renommé REPORT_FIELD_MAX par la
# revue du commit 8194b55, qui a aussi éclaté l'unique paramètre `body` en
# plusieurs paramètres d'URL — voir tests/test_report_issue_form_prefill.py.
# Le paramètre `description` de l'URL est celui qui porte désormais le texte
# libre de l'opérateur, donc la même protection contre le 414 URI Too Long.)

def test_corps_tres_accentue_reste_sous_report_field_max_une_fois_encode():
    """1400 caractères accentués : la longueur BRUTE reste sous
    REPORT_FIELD_MAX=1500, donc un contrôle naïf `str.length > REPORT_FIELD_MAX`
    ne se déclencherait jamais — alors que la longueur ENCODÉE (chaque
    'é' -> %C3%A9, x6) explose largement au-dessus. Après fix, le paramètre
    `description` de l'URL doit rester <= REPORT_FIELD_MAX caractères ENCODÉS."""
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    description = 'é' * 1400
    _set_prompt_return(ctx, description)

    ctx.eval('openReportIssue();')

    assert ctx.eval('lastAlert') is None
    url = ctx.eval('openedUrl')
    description_encoded = _url_param(url, 'description')
    assert len(description_encoded) <= 1500, (
        f"description encodée fait {len(description_encoded)} caractères, largement au-dessus "
        "de REPORT_FIELD_MAX=1500 — la marge anti 414 URI Too Long n'est plus respectée")


def test_reproduction_avant_fix_commit_f20799a_corps_encode_depasse_largement_1500():
    """Contrôle négatif : rejoue le openReportIssue() du commit f20799a
    (avant ce fix) avec le même texte très accentué — le body.length BRUT
    (~1420) passe sous le seuil de 1500 sans être tronqué, donc le body
    ENCODÉ envoyé dans l'URL dépasse très largement 1500 caractères."""
    block = _extract_report_block(_pre_fix_src())
    ctx = _make_ctx(block)
    description = 'é' * 1400
    _set_prompt_return(ctx, description)

    ctx.eval('openReportIssue();')  # ne plante pas (pas de caractère invalide ici)

    url = ctx.eval('openedUrl')
    body_encoded = _url_param(url, 'body')
    # Preuve concrète du bug : largement au-dessus de la marge visée (1500).
    assert len(body_encoded) > 3000, (
        f"le body pré-fix ne faisait que {len(body_encoded)} caractères encodés : "
        "le scénario de reproduction n'est plus valide, à revoir")


def test_corps_court_non_accentue_nest_pas_tronque_inutilement():
    """Non-régression : un rapport court et simple ne doit pas être touché
    par la nouvelle logique de troncature basée sur la longueur encodée."""
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    description = 'Le bouton export ADIF ne répond plus après un import.'
    _set_prompt_return(ctx, description)

    ctx.eval('openReportIssue();')

    assert ctx.eval('lastAlert') is None
    url = ctx.eval('openedUrl')
    description_encoded = _url_param(url, 'description')
    assert '…(tronqu' not in __import__('urllib.parse', fromlist=['unquote']).unquote(description_encoded)


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    assert 'QSO Director' not in _current_src()
