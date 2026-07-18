# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller — RadioContest AI en exécutable autonome (Windows/macOS).

Build :
  Windows :  pyinstaller radiocontest.spec       (produit dist/RadioContestAI.exe)
  macOS   :  pyinstaller radiocontest.spec       (produit dist/RadioContestAI)

Mono-fichier : tout (Python, pages HTML/JS, base DXCC, GeoJSON) est embarqué.
Le premier lancement recopie les données de référence dans le dossier
utilisateur (voir radiocontest_bootstrap.py) — aucune installation de Python
requise sur la machine cible.
"""
import glob
import os

# Fichiers embarqués : pages, scripts front, données de référence
_datas = [(f, '.') for f in glob.glob('*.html')]
_datas += [(f, '.') for f in glob.glob('*.js')]
for ref in ('contest_schema.json', 'cty.dat', 'france_departements.geojson',
            'custom_contests.json'):
    if os.path.exists(ref):
        _datas.append((ref, '.'))

# Modules importés paresseusement (dans des fonctions) que l'analyse statique
# de PyInstaller peut manquer : on les déclare explicitement.
_hidden = ['radiocontest_' + m for m in (
    'utils', 'definitions', 'storage', 'rules', 'scoring', 'clusters',
    'prompts', 'http', 'rules_ai', 'coach', 'validate', 'dxcc', 'departments',
    'export', 'beacons', 'psk', 'weather', 'rig', 'rotor', 'wsjtx', 'qrz',
    'bootstrap', 'cat', 'tci')]
# pyserial (radiocontest_cat) : sous-modules non toujours détectés par
# l'analyse statique (list_ports selon l'OS cible).
_hidden += ['serial', 'serial.tools.list_ports', 'serial.tools.list_ports_common',
           'serial.tools.list_ports_windows', 'serial.tools.list_ports_posix',
           'serial.tools.list_ports_osx']

a = Analysis(
    ['radiocontest_serveur.py'],
    pathex=[os.path.abspath('.')],
    binaries=[],
    datas=_datas,
    hiddenimports=_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'numpy', 'matplotlib'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='RadioContestAI',
    debug=False,
    strip=False,
    upx=True,
    console=True,          # fenêtre serveur visible (logs + Ctrl+C pour arrêter)
    disable_windowed_traceback=False,
    icon=None,
)
