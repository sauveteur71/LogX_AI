# -*- coding: utf-8 -*-
"""openReportIssue() (concours/logx_statusbar.js) vs. .github/ISSUE_TEMPLATE/
bug.yml + config.yml — revue adversariale du commit 8194b55 ("Formulaire
d'issue GitHub, CHANGELOG, artefacts versionnes"), défaut [HIGH] vérifié
indépendamment, avec reproduction concrète :

Le commit 8194b55 a ajouté .github/ISSUE_TEMPLATE/bug.yml (un GitHub Issue
Forms, formulaire structuré en YAML) et config.yml (blank_issues_enabled:
false, qui REND CE FORMULAIRE OBLIGATOIRE — impossible d'ouvrir une issue
"vierge" une fois ce fichier présent). Mais openReportIssue(), qui existait
déjà avant ce commit, continuait de construire l'URL au format des issues
"classiques" (?title=...&body=...). Or GitHub Issue Forms n'accepte le
pré-remplissage QUE via ?template=<fichier>&<id_du_champ>=<valeur> ; le
format ?title=/&body= est silencieusement IGNORÉ dès qu'un template YAML
existe pour le dépôt. Résultat concret : cliquer sur « signaler un
problème » ouvrait bien une issue... mais le formulaire guidé (Que
faisiez-vous / Version / OS / Description) s'affichait totalement VIERGE,
sans le moindre message d'erreur — la régression passait inaperçue.

Même technique que tests/test_report_issue_unicode.py et
tests/test_report_issue_error_journal.py : le VRAI code est extrait tel quel
du fichier source (comptage d'accolades), PAS retapé, et exécuté dans un
moteur JS réel (V8 via py_mini_racer). Le test « avant fix » rejoue le code
TEL QU'IL ÉTAIT au commit 8e3fbb5 (HEAD juste avant cette revue — bug.yml/
config.yml existaient déjà à cette révision, ajoutés par 8194b55, un
ancêtre) pour prouver concrètement que l'incompatibilité se produisait
bien à ce moment-là."""
import json
import os
import subprocess
import urllib.parse

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')
yaml = pytest.importorskip('yaml', reason='PyYAML absent (voir requirements.txt)')

CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(CONCOURS_DIR)
JS_PATH = os.path.join(CONCOURS_DIR, 'logx_statusbar.js')
BUG_YML_PATH = os.path.join(REPO_ROOT, '.github', 'ISSUE_TEMPLATE', 'bug.yml')

# HEAD juste avant la correction de ce défaut : bug.yml/config.yml (commit
# 8194b55, un ancêtre) sont déjà présents à cette révision, mais
# openReportIssue() utilise encore l'ancien format ?title=/&body=.
PRE_FIX_REV = '8e3fbb5'


def _extract_report_block(src):
    """Extrait tout le bloc « signaler un problème » — des constantes
    REPORT_REPO_FALLBACK/REPORT_FIELD_MAX jusqu'à la fin de la fonction
    openReportIssue() incluse — par comptage d'accolades, pour récupérer le
    VRAI code, pas une réécriture qui pourrait diverger du bug (même
    technique que tests/test_report_issue_unicode.py)."""
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
        cwd=REPO_ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
    return out.stdout


def _bug_yml_field_ids():
    with open(BUG_YML_PATH, encoding='utf-8') as f:
        tpl = yaml.safe_load(f)
    return {el['id'] for el in tpl['body'] if el['type'] != 'markdown'}


def _bug_yml_os_options():
    with open(BUG_YML_PATH, encoding='utf-8') as f:
        tpl = yaml.safe_load(f)
    champ_os = next(el for el in tpl['body'] if el.get('id') == 'os')
    return set(champ_os['attributes']['options'])


# ─── Contexte JS minimal : pas besoin du DOM complet, juste navigator/
# prompt/alert/window.open mockés, comme les autres tests du module ────────
_HARNESS_PREAMBLE = r"""
// rcT : le VRAI logx_statusbar.js definit ce repli en tete de son IIFE
// (`const rcT = s => (window.rcT ? window.rcT(s) : s)`), au-dessus du bloc que
// ce test extrait. Sans lui ici, le bloc extrait leve « rcT is not defined » —
// un echec du BANC D'ESSAI, pas du produit : en page reelle, le repli est la.
function rcT(s){ return s; }
var navigator = { platform: 'Win32', userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' };
var openedUrl = null;
var window = { open: function(url){ openedUrl = url; return {}; } };
var lastAlert = null;
function alert(msg){ lastAlert = msg; }
var promptReturn = '';
function prompt(msg, def){ return promptReturn; }
var _updState = { current: '0.9-beta2', repo: 'octo/repo' };
var _fastVersion = null;
function fetch(){ return Promise.resolve({ ok:false }); }
"""


def _make_ctx(block_src):
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_HARNESS_PREAMBLE)
    ctx.eval(block_src)
    return ctx


def _set_prompt_return(ctx, py_str):
    ctx.eval('promptReturn = ' + json.dumps(py_str) + ';')


def _set_navigator(ctx, user_agent, platform):
    ctx.eval('navigator = ' + json.dumps({'userAgent': user_agent, 'platform': platform}) + ';')


def _run(ctx, description):
    _set_prompt_return(ctx, description)
    ctx.eval('openReportIssue();')
    assert ctx.eval('lastAlert') is None
    url = ctx.eval('openedUrl')
    assert url is not None
    return url


def _query_params(url):
    """Renvoie les paramètres de la query string sous forme de dict
    (déjà décodés) — GitHub matche les clés de query string aux `id:`
    déclarés dans le formulaire, la casse et l'exactitude comptent."""
    parsed = urllib.parse.urlsplit(url)
    return dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))


# ─── Reproduction concrète du défaut [HIGH] ────────────────────────────────

def test_url_post_fix_utilise_template_et_les_ids_de_bugyml():
    """Après fix : l'URL doit porter ?template=bug.yml et un paramètre par
    id de champ requis de bug.yml (activite excepté, jamais collecté par ce
    bouton — voir commentaire dans openReportIssue). C'est exactement ce
    que GitHub Issue Forms exige pour pré-remplir le formulaire."""
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    url = _run(ctx, 'Le bouton export ADIF ne répond plus.')
    params = _query_params(url)

    assert params.get('template') == 'bug.yml', (
        "sans ?template=bug.yml, GitHub ignore silencieusement tous les autres "
        f"paramètres de pré-remplissage — URL obtenue : {url!r}")

    ids_requis = _bug_yml_field_ids() - {'activite'}  # jamais collecté par ce bouton
    manquants = ids_requis - set(params)
    assert not manquants, f"id(s) de bug.yml absent(s) de l'URL : {manquants}"
    for field_id in ids_requis:
        assert params[field_id], f"le champ '{field_id}' est présent mais vide dans l'URL"


def test_reproduction_avant_fix_commit_8e3fbb5_ni_template_ni_ids_bugyml():
    """Contrôle négatif : rejoue EXACTEMENT le openReportIssue() du commit
    8e3fbb5 (HEAD avant cette revue — bug.yml/config.yml, ajoutés par
    l'ancêtre 8194b55, sont déjà en place à cette révision) — confirme que
    l'URL produite ne comportait ni ?template=, ni aucun des id de champ de
    bug.yml : le formulaire guidé se serait ouvert entièrement vierge."""
    block = _extract_report_block(_pre_fix_src())
    ctx = _make_ctx(block)
    url = _run(ctx, 'Le bouton export ADIF ne répond plus.')
    params = _query_params(url)

    assert 'template' not in params, (
        'le scénario de reproduction n\'est plus valide (template déjà présent '
        'avant le fix) : à revoir')
    ids_bug_yml = _bug_yml_field_ids()
    presents = ids_bug_yml & set(params)
    assert not presents, (
        f"des id de bug.yml apparaissent déjà dans l'URL pré-fix ({presents}) : "
        "le scénario de reproduction n'est plus valide, à revoir")
    # Preuve du format historique effectivement utilisé à cette révision.
    assert 'body' in params and 'title' in params


# ─── Non-régression : titre + repo + labels conservés ──────────────────────

def test_titre_labels_et_repo_restent_corrects_apres_fix():
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    url = _run(ctx, 'Le bouton export ADIF ne répond plus.')
    params = _query_params(url)

    assert url.startswith('https://github.com/octo/repo/issues/new?')
    assert params.get('title') == '[Bug] Le bouton export ADIF ne répond plus.'
    assert params.get('labels') == 'bug'
    assert params.get('version') == 'v0.9-beta2'


# ─── Repli _fastVersion : cas de course où /app/update_check n'a pas encore
# répondu quand l'opérateur clique sur "signaler un problème" ──────────────

def test_repli_fastversion_si_updstate_pas_encore_resolu():
    """_updState reste à null tant que /app/update_check (fetch async) n'a
    pas répondu. Avant ce fix, la version tombait directement sur
    'inconnue' dans ce cas. _fastVersion (rempli par /network/info, une
    sonde plus légère) doit servir de repli intermédiaire."""
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    ctx.eval("_updState = null; _fastVersion = '0.9-beta27';")
    url = _run(ctx, 'Le bouton export ADIF ne répond plus.')
    params = _query_params(url)

    assert params.get('version') == 'v0.9-beta27'


def test_repli_inconnue_si_ni_updstate_ni_fastversion():
    """Aucune des deux sondes n'a encore répondu : repli final 'inconnue',
    comportement historique conservé."""
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    ctx.eval("_updState = null; _fastVersion = null;")
    url = _run(ctx, 'Le bouton export ADIF ne répond plus.')
    params = _query_params(url)

    assert params.get('version') == 'vinconnue'


# ─── detectOsFormOption() : doit renvoyer une option EXACTE de bug.yml ─────

OS_CASES = [
    ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', 'Win32', 'Windows'),
    ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15', 'MacIntel', 'macOS'),
    ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36', 'Linux x86_64', 'Linux'),
    ('Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36', 'Linux armv8l', 'Android (navigateur/PWA)'),
    ('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15', 'iPhone',
     'iPhone / iPad (navigateur/PWA)'),
    ('Mozilla/5.0 (compatible; obscure-bot) FreeBSD', 'FreeBSD', 'Autre / je ne sais pas'),
]


@pytest.mark.parametrize('user_agent,platform,expected', OS_CASES)
def test_detect_os_form_option_correspond_a_une_option_exacte_du_dropdown(user_agent, platform, expected):
    block = _extract_report_block(_current_src())
    ctx = _make_ctx(block)
    _set_navigator(ctx, user_agent, platform)

    result = ctx.eval('detectOsFormOption()')

    assert result in _bug_yml_os_options(), (
        f"'{result}' ne correspond à aucune option du dropdown os de bug.yml "
        "— GitHub ne présélectionnera rien au chargement du formulaire")
    assert result == expected


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    assert 'QSO Director' not in _current_src()
