# -*- coding: utf-8 -*-
"""Tests de cohérence des fichiers méta CI/release (.github/, hors dépôt
concours/) : formulaire d'issue GitHub et nommage versionné des artefacts de
build-release.yml. Ce ne sont pas des fichiers Python, mais une régression ici
(id renommé, validations retirées, tag oublié dans le nom de l'artefact) ne se
verrait qu'au prochain vrai tag poussé — sans ces tests, aucun filet avant."""
import os

import pytest

yaml = pytest.importorskip('yaml', reason='PyYAML absent (voir requirements.txt)')

# .github/ vit à la racine du dépôt, un niveau au-dessus de concours/.
CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(CONCOURS_DIR)
GITHUB_DIR = os.path.join(REPO_ROOT, '.github')


def _load_yaml(*parts):
    with open(os.path.join(GITHUB_DIR, *parts), encoding='utf-8') as f:
        return yaml.safe_load(f)


# ── bug.yml (formulaire de bug) ──────────────────────────────────────────────

def test_bug_yml_champs_attendus_presents():
    """Les 4 champs guidés demandés aux bêta-testeurs non techniques doivent
    rester présents avec ces id précis (logx_statusbar.js pourrait un jour
    les utiliser pour pré-remplir le formulaire via ?template=&<id>=...)."""
    tpl = _load_yaml('ISSUE_TEMPLATE', 'bug.yml')
    assert tpl['name']
    assert tpl['description']
    ids = {el['id'] for el in tpl['body'] if el['type'] != 'markdown'}
    assert {'activite', 'version', 'os', 'description'} <= ids


def test_bug_yml_types_et_ids_valides():
    """Types conformes au schema officiel GitHub Issue Forms + aucun id
    duplique (deux champs avec le meme id, le second ecraserait le premier)."""
    tpl = _load_yaml('ISSUE_TEMPLATE', 'bug.yml')
    types_valides = {'markdown', 'input', 'textarea', 'dropdown', 'checkboxes'}
    ids = []
    for el in tpl['body']:
        assert el['type'] in types_valides
        if el['type'] == 'markdown':
            assert 'value' in el['attributes']
            continue
        assert 'id' in el and 'label' in el['attributes']
        ids.append(el['id'])
    assert len(ids) == len(set(ids)), 'id de champ duplique dans bug.yml'


def test_bug_yml_champs_essentiels_obligatoires():
    """Que faisiez-vous / version / OS / description doivent rester
    'validations: required: true' - sinon un rapport peut arriver vide."""
    tpl = _load_yaml('ISSUE_TEMPLATE', 'bug.yml')
    requis = {el['id'] for el in tpl['body']
              if el['type'] != 'markdown' and el.get('validations', {}).get('required')}
    assert {'activite', 'version', 'os', 'description'} <= requis


def test_bug_yml_dropdown_os_couvre_les_plateformes_courantes():
    tpl = _load_yaml('ISSUE_TEMPLATE', 'bug.yml')
    champ_os = next(el for el in tpl['body'] if el.get('id') == 'os')
    assert champ_os['type'] == 'dropdown'
    options = champ_os['attributes']['options']
    assert any('windows' in o.lower() for o in options)
    assert any('linux' in o.lower() for o in options)
    assert any('mac' in o.lower() for o in options)


# ── config.yml (chooser d'issues) ────────────────────────────────────────────

def test_config_yml_bloque_les_issues_vierges():
    cfg = _load_yaml('ISSUE_TEMPLATE', 'config.yml')
    assert cfg['blank_issues_enabled'] is False


# ── build-release.yml (nommage versionne des artefacts) ─────────────────────

def test_build_release_matrice_3_os_avec_noms_distincts():
    wf = _load_yaml('workflows', 'build-release.yml')
    matrice = wf['jobs']['build']['strategy']['matrix']['include']
    assert len(matrice) == 3
    combinaisons = {(m['suffix'], m['ext']) for m in matrice}
    assert len(combinaisons) == 3  # 3 OS -> 3 noms de fichiers distincts
    windows = next(m for m in matrice if m['ext'] == '.exe')
    assert windows['suffix'] == ''  # seul l'OS Windows n'a pas de suffixe de nom


def test_build_release_utilise_le_tag_resolu_dans_le_nom_final():
    """Régression clé de cette fonctionnalité : le nom de l'artefact renommé
    doit inclure le tag résolu (steps.version) + le suffixe/extension de la
    matrice, sinon on retombe sur le nom fixe LogXAI.exe pour toute version
    (le problème d'origine : impossible de distinguer 2 versions téléchargées)."""
    wf = _load_yaml('workflows', 'build-release.yml')
    etapes = wf['jobs']['build']['steps']
    etape_renommage = next(s for s in etapes if s.get('id') == 'artefact')
    script = etape_renommage['run']
    assert 'steps.version.outputs.tag' in script
    assert 'matrix.suffix' in script
    assert 'matrix.ext' in script

    # L'etape d'attachement doit consommer le nom genere (source unique de
    # verite), jamais un nom recopie a la main qui pourrait diverger.
    etape_attache = next(s for s in etapes if s.get('name', '').startswith('Attacher'))
    assert 'steps.artefact.outputs.name' in etape_attache['with']['files']
