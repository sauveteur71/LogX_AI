# -*- coding: utf-8 -*-
"""Finding I1 (revue finale, décodage Q65 EME natif) : saveConfig()
(concours/logx_configuration.js) reconstruisait l'objet `eme` avec SEULEMENT
{source, audio_device, submode} — trois champs pilotés par l'UI. Comme
/config/save REMPLACE toute la config (voir logx_http.py, `current_config = cfg`),
les clés `eme.jt9_path`/`eme.tr_period` (concours/config.example.json, aucun
champ UI pour elles) étaient effacées à CHAQUE sauvegarde. jt9_path est
pourtant le seul moyen d'activer le moteur natif tant que le binaire jt9 n'est
pas embarqué (Tâche 8).

Ce test exécute le VRAI extrait de code de saveConfig() qui construit `eme`
(extrait tel quel du fichier source par comptage d'accolades, pas retapé) dans
un moteur JS réel (V8 via py_mini_racer, même technique que
tests/test_config_html_sota_qrz_race.py) — pas un mannequin qui réimplémenterait
la fusion : si le fichier source change de logique, ce test le voit."""
import os

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_configuration.js')

with open(JS_PATH, encoding='utf-8') as _f:
    _JS_SRC = _f.read()


def _extraire_objet_eme(src):
    """Extrait littéralement `{ ...contenu... }` de la propriété `eme:` de
    l'objet `config` construit par saveConfig(), par comptage d'accolades —
    pas une réécriture, le VRAI texte du fichier."""
    marqueur = 'eme: {'
    start = src.index(marqueur)
    brace_open = src.index('{', start)
    depth = 0
    i = brace_open
    while True:
        c = src[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return src[brace_open:i + 1]
        i += 1


_EME_OBJ_SRC = _extraire_objet_eme(_JS_SRC)


def _construire_eme(cfg_restrauree_eme, ui_values):
    """Évalue le VRAI extrait `eme: { ... }` avec un `window._cfgRestauree`
    et un `document.getElementById` stubbés, renvoie l'objet `eme` obtenu.
    `cfg_restrauree_eme=None` simule le premier chargement de page (avant
    tout appel à applyFullConfigToForm() -> window._cfgRestauree reste
    `undefined`, jamais posé)."""
    import json
    ctx = py_mini_racer.MiniRacer()
    if cfg_restrauree_eme is None:
        cfg_line = 'var window = {};'  # _cfgRestauree jamais posé -> undefined
    else:
        cfg_line = 'var window = {_cfgRestauree: {eme: %s}};' % json.dumps(cfg_restrauree_eme)
    ctx.eval(cfg_line + """
      var __ids = %s;
      var document = {
        getElementById: function(id){
          if (Object.prototype.hasOwnProperty.call(__ids, id)) return {value: __ids[id]};
          return null;
        }
      };
    """ % json.dumps(ui_values))
    ctx.eval('var __out = ' + _EME_OBJ_SRC + ';')
    return json.loads(ctx.eval('JSON.stringify(__out)'))


def test_saveconfig_preserve_jt9_path_et_tr_period_non_pilotes_par_lui():
    eme = _construire_eme(
        cfg_restrauree_eme={'source': 'natif', 'audio_device': 'hw:1',
                             'submode': 'A', 'jt9_path': '/opt/jt9/jt9',
                             'tr_period': 30},
        ui_values={'eme_source': 'natif', 'eme_audio_device': 'hw:1', 'eme_submode': 'B'},
    )
    # Les clés SANS champ UI survivent à la sauvegarde.
    assert eme['jt9_path'] == '/opt/jt9/jt9'
    assert eme['tr_period'] == 30


def test_saveconfig_les_champs_pilotes_par_lui_reflent_lui_meme():
    # Les 3 champs pilotés par l'UI doivent malgré tout refléter l'UI, pas
    # rester bloqués sur l'ancienne valeur de window._cfgRestauree.eme.
    eme = _construire_eme(
        cfg_restrauree_eme={'source': 'wsjtx', 'audio_device': 'ANCIEN',
                             'submode': 'A', 'jt9_path': '/opt/jt9/jt9'},
        ui_values={'eme_source': 'natif', 'eme_audio_device': 'NOUVEAU', 'eme_submode': 'C'},
    )
    assert eme['source'] == 'natif'
    assert eme['audio_device'] == 'NOUVEAU'
    assert eme['submode'] == 'C'
    # jt9_path toujours préservé au passage.
    assert eme['jt9_path'] == '/opt/jt9/jt9'


def test_saveconfig_sans_config_eme_connue_ne_plante_pas():
    # Premier chargement de page (localStorage vide) : window._cfgRestauree
    # est {} (voir applyFullConfigToForm) -> pas d'exception, comportement
    # historique (3 champs UI, valeurs par défaut).
    eme = _construire_eme(cfg_restrauree_eme=None, ui_values={})
    assert eme['source'] == 'wsjtx'
    assert eme['audio_device'] == ''
    assert eme['submode'] == 'A'
