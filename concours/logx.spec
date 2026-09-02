# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller — LogX AI en exécutable autonome (Windows/macOS).

Build :
  Windows :  pyinstaller logx.spec       (produit dist/LogXAI.exe)
  macOS   :  pyinstaller logx.spec       (produit dist/LogXAI)

Mono-fichier : tout (Python, pages HTML/JS, base DXCC, GeoJSON) est embarqué.
Le premier lancement recopie les données de référence dans le dossier
utilisateur (voir logx_bootstrap.py) — aucune installation de Python
requise sur la machine cible.
"""
import glob
import os

# Fichiers embarqués : pages, scripts front, données de référence.
# manifest/icône/logo : requis par les pages ET pré-cachés par le service
# worker (logx_sw.js) — sans eux, logo cassé et cache.addAll échoue en 404,
# donc la PWA ne s'installe jamais dans l'exécutable (alors que tout marche
# en mode développeur, où les fichiers sont dans le dossier).
_datas = [(f, '.') for f in glob.glob('*.html')]
_datas += [(f, '.') for f in glob.glob('*.js')]
# Feuilles de style (logx_theme.css) : SANS elles dans le bundle, l'exe gelé ne
# peut ni servir le <link> ni l'inliner (logx_http._theme_css_inline_style lit
# _MEIPASS/logx_theme.css) -> page sans thème chez l'utilisateur de l'exe (F4GLD
# ne le voit pas : il tourne depuis les sources). L'inlining est la défense
# anti-Avast, mais il était inopérant en release faute de ce glob.
_datas += [(f, '.') for f in glob.glob('*.css')]
for ref in ('contest_schema.json', 'cty.dat', 'france_departements.geojson',
            'custom_contests.json', 'external_contests.json',
            'manifest.webmanifest', 'logx_icon.svg', 'logx_logo.png'):
    if os.path.exists(ref):
        _datas.append((ref, '.'))

# Moteur VOACAP (voacapl.exe + arbre de données itshfbc/) : un dossier
# profond (coeffs/database/geocity/geonatio/geostate/antennas/areadata/
# area_inv), pas juste quelques fichiers plats — glob() ne le couvrirait
# pas récursivement, d'où Tree() plutôt qu'un ajout ligne par ligne comme
# ci-dessus. Sans ceci, logx_voacap.voacap_available() renverrait False
# dans l'exécutable distribué alors que tout fonctionne en mode développeur
# (piège classique PyInstaller : les données hors .py/.html/.js du dépôt ne
# sont jamais embarquées automatiquement).
# Tree() renvoie des entrées à 3 champs (dest, src, typecode) — le format
# TOC déjà traité, PAS le format brut (src, dest) attendu par Analysis(
# datas=...). Les mélanger dans _datas casse Analysis() avec "too many
# values to unpack" (trouvé au 1er build après l'ajout de VOACAP, tag
# v0.9-beta27 : succès local du dépôt masqué tant qu'aucun build release
# n'avait tourné depuis). Le TOC de Tree() doit être combiné avec a.datas
# (même format 3-champs, déjà traité) APRÈS Analysis(), pas avant.
_voacap_tree = Tree('voacap', prefix='voacap') if os.path.isdir('voacap') else []

# Binaire jt9 embarqué (Tâche 8 — décodage Q65 EME natif hors-ligne) : jt9 et
# ses dépendances runtime (fftw3f, libgfortran, DLL MinGW, dylibs…) sont
# déposés dans vendor/jt9/ par l'étape CI « Récupérer jt9 » (action
# fetch-jt9), AVANT ce build. On les embarque en `binaries=` (PAS `datas=`)
# pour préserver le bit exécutable à l'extraction onefile — un fichier en
# datas ne serait pas exécutable sous Unix, jt9 ne se lancerait pas.
# resoudre_jt9() (logx_q65_natif.py) les cherche sous _MEIPASS/vendor/jt9/,
# soit exactement ce chemin relatif. Absent en dev/local : embarquement vide,
# repli PATH/jt9_path assuré par resoudre_jt9() (aucun impact sur le build).
_jt9 = []
if os.path.isdir(os.path.join('vendor', 'jt9')):
    for _f in glob.glob(os.path.join('vendor', 'jt9', '*')):
        if os.path.isfile(_f) and not _f.lower().endswith(('.md', '.gitignore')):
            _jt9.append((_f, 'vendor/jt9'))

# Modules importés paresseusement (dans des fonctions) que l'analyse statique
# de PyInstaller peut manquer : on les déclare explicitement.
_hidden = ['logx_' + m for m in (
    'utils', 'definitions', 'storage', 'rules', 'scoring', 'clusters',
    'prompts', 'http', 'rules_ai', 'coach', 'validate', 'dxcc', 'departments',
    'export', 'beacons', 'psk', 'weather', 'rig', 'rotor', 'wsjtx', 'qrz',
    'bootstrap', 'cat', 'tci', 'websdr', 'pota',
    'activation_db', 'eme', 'iota', 'wca', 'wwff', 'wwa',
    'update', 'version', 'errorlog', 'singleton', 'crypto')]
# pyserial (logx_cat) : sous-modules non toujours détectés par
# l'analyse statique (list_ports selon l'OS cible).
_hidden += ['serial', 'serial.tools.list_ports', 'serial.tools.list_ports_common',
           'serial.tools.list_ports_windows', 'serial.tools.list_ports_posix',
           'serial.tools.list_ports_osx']

a = Analysis(
    ['logx_serveur.py'],
    pathex=[os.path.abspath('.')],
    binaries=_jt9,
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'numpy', 'matplotlib'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas + _voacap_tree, [],
    name='LogXAI',
    debug=False,
    strip=False,
    upx=True,
    console=True,          # fenêtre serveur visible (logs + Ctrl+C pour arrêter)
    disable_windowed_traceback=False,
    icon=None,
)
