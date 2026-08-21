# -*- coding: utf-8 -*-
"""« NOUVEAU LOG » annonçait le compte de la VUE, pas celui du carnet.

LE DÉFAUT. `resetLog()` (logx_outils_autonomes.js) construisait sa demande de
confirmation avec `qsoLog.length` — la liste DÉJÀ FILTRÉE par la portée
concours+année. Or `/log/reset` porte sur `shared_log` ENTIER : le serveur
snapshote `list(shared_log)` avant d'effacer (logx_http.py), et `/log/status`
publie ce même total sous `qso_count = len(shared_log)`.

Conséquence mesurée sur le carnet réel de F4GLD : filtré sur un concours à 50
QSO, le dialogue écrivait « Supprime 50 QSO » alors que 9 870 étaient archivés
puis vidés. Rien n'est perdu — l'archivage précède l'effacement — mais un
compte faux dans une confirmation de suppression est exactement le chiffre sur
lequel un opérateur décide.

POURQUOI CE LOT PASSE AVANT LE CHANTIER « ACTIVITÉ ». Aujourd'hui l'écart
entre la vue et le carnet est l'exception : il faut un concours sélectionné.
Une vue par activité en ferait la norme, sur tous les écrans, tout le temps.
Le plan de ce chantier le classe donc en préalable, pas en amélioration.

CE QUE CES TESTS NE PROUVENT PAS : que le serveur efface bien ce qu'il dit.
Ça, c'est tests/test_storage_garde_fou.py et le garde-fou de logx_storage.py.
Ici on ne teste QUE l'honnêteté de ce qui est affiché avant d'effacer.
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_ft8_sequenceur import _lire  # noqa: E402

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_outils_autonomes.js')
HTTP = os.path.join(CONCOURS, 'logx_http.py')


def _sans_commentaires_js(src):
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'//.*$', '', li) for li in src.splitlines())


def _sans_commentaires_py(src):
    """Dépouilleur PYTHON, et il en fallait un séparé.

    PIÈGE MESURÉ : appliquer le dépouilleur JavaScript à un fichier Python
    détruit le fichier. `logx_http.py` contient « /debug/* » dans un
    commentaire ; avec `re.S`, ce faux ouvrant de bloc a avalé **19 927
    caractères** jusqu'au « */ » suivant — dont la ligne `'qso_count':
    len(shared_log)` que ce test cherche. Le test échouait sur un fichier
    parfaitement correct.

    Le danger n'est pas l'échec, il est l'inverse : une assertion d'ABSENCE
    appliquée à un fichier ainsi charcuté réussirait toujours, et personne ne
    le verrait.

    Ici on ne retire que les lignes entièrement commentées : suffisant pour
    empêcher un commentaire d'imiter du code, et sans risque de couper à
    l'intérieur d'une chaîne contenant un « # ».
    """
    return '\n'.join(li for li in src.splitlines() if not li.lstrip().startswith('#'))


def _extraire(nom):
    """Les DEUX fonctions telles qu'elles sont dans le fichier, sans les
    réécrire : un banc qui recopierait la logique ne contraindrait que sa
    propre copie."""
    src = _lire(JS)
    i = src.index('async function %s(' % nom)
    prof, j, dedans = 0, i, False
    while j < len(src):
        if src[j] == '{':
            prof += 1
            dedans = True
        elif src[j] == '}':
            prof -= 1
            if dedans and prof == 0:
                return src[i:j + 1]
        j += 1
    raise AssertionError('fonction %s non refermée' % nom)


def _banc(qso_count, affiches, status_ok=True):
    """Exécute le VRAI resetLog avec un serveur simulé, et CAPTURE le texte
    réellement soumis à l'opérateur."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
    var __texte = null, __confirme = false, __resetAppele = false;
    var qsoLog = [], serialByBand = {};
    function trT(s){ return s; }
    function trF(s, o){
      return String(s).replace(/\\{(\\w+)\\}/g, function(_, k){
        return (o && o[k] !== undefined) ? o[k] : '';
      });
    }
    function notify(){}
    function resetLogRenderWindow(){}
    function renderLog(){}
    function updateStats(){}
    function updateSerialDisplay(){}
    function prompt(){ return 'RESET'; }
    async function _confirmDupBanner(texte){ __texte = texte; return __confirme; }
    var __status = {ok: true, qso_count: 0};
    function fetch(url){
      if(String(url).indexOf('/log/status') >= 0){
        return Promise.resolve({ok: __status.ok,
          json: function(){ return Promise.resolve({qso_count: __status.qso_count}); }});
      }
      __resetAppele = true;
      return Promise.resolve({ok: true, json: function(){ return Promise.resolve({}); }});
    }
    """)
    ctx.eval('__status = {ok: %s, qso_count: %d};'
             % ('true' if status_ok else 'false', qso_count))
    ctx.eval('qsoLog = new Array(%d);' % affiches)
    ctx.eval(_extraire('_totalCarnetReel'))
    ctx.eval(_extraire('resetLog'))
    ctx.eval('resetLog();')
    ctx.eval('0;')   # laisse les promesses se résoudre
    return ctx


def test_le_dialogue_annonce_le_total_REEL_pas_celui_de_la_vue():
    """LE DÉFAUT, dans sa forme exacte : 50 QSO affichés, 9870 dans le carnet.
    Le dialogue doit dire 9870."""
    ctx = _banc(qso_count=9870, affiches=50)
    texte = ctx.eval('__texte')
    assert texte, 'aucun dialogue de confirmation présenté'
    assert '9870' in texte, 'le total réel du carnet doit être annoncé : %r' % texte
    assert 'Supprime 50 QSO' not in texte, (
        'le compte de la VUE ne doit pas être présenté comme le nombre '
        'supprimé : %r' % texte)


def test_l_ecart_entre_l_ecran_et_le_carnet_est_DIT():
    """Le cœur du correctif. Ce n'est pas le total qui trompait, c'est l'écart
    silencieux entre ce que l'écran montre et ce que le bouton détruit."""
    texte = _banc(qso_count=9870, affiches=50).eval('__texte')
    assert '50' in texte, 'le nombre affiché doit être rappelé : %r' % texte
    assert 'carnet ENTIER' in texte, (
        "l'opérateur doit lire que tout le carnet est concerné : %r" % texte)


def test_aucun_avertissement_inutile_quand_la_vue_montre_tout():
    """Sans filtre actif, vue et carnet coïncident : ajouter un avertissement
    serait du bruit, et le bruit finit par ne plus être lu."""
    texte = _banc(qso_count=120, affiches=120).eval('__texte')
    assert '120' in texte
    assert 'carnet ENTIER' not in texte, (
        'pas de mise en garde quand il n\'y a pas d\'écart : %r' % texte)


def test_serveur_injoignable_on_ne_REMPLACE_PAS_par_le_compte_affiche():
    """Repli SÛR. Retomber sur qsoLog.length en cas d'échec réseau
    reproduirait le défaut exactement, et au pire moment : celui où l'on ne
    peut rien vérifier. On dit qu'on ne sait pas."""
    texte = _banc(qso_count=9870, affiches=50, status_ok=False).eval('__texte')
    assert 'Supprime 50 QSO' not in texte, (
        'le repli ne doit pas ressusciter le compte de la vue : %r' % texte)
    assert 'TOUS les' in texte, (
        "à défaut de chiffre, le dialogue doit dire que TOUT le carnet part : %r"
        % texte)


def test_refuser_le_dialogue_n_efface_rien():
    """Garde-fou évident, mais c'est un bouton de suppression : on le vérifie."""
    ctx = _banc(qso_count=9870, affiches=50)
    assert ctx.eval('__resetAppele') is False, (
        "aucun appel à /log/reset ne doit partir tant que l'opérateur n'a pas "
        'confirmé')


def test_le_compte_publie_par_le_serveur_est_bien_le_carnet_ENTIER():
    """Assertion croisée, côté serveur. Tout le correctif repose sur le fait
    que `qso_count` compte shared_log et non une vue filtrée : si cette clé
    changeait de sens un jour, le dialogue redeviendrait faux sans qu'aucun
    test JS ne bouge."""
    code = _sans_commentaires_py(_lire(HTTP))
    assert re.search(r"'qso_count'\s*:\s*len\(shared_log\)", code), (
        "/log/status doit publier len(shared_log) — c'est la source du total "
        'affiché avant effacement')


def test_le_dialogue_ne_lit_plus_qsoLog_length():
    """Assertion de STRUCTURE sur le corps de resetLog : le compte annoncé ne
    doit plus venir de la liste filtrée. `qsoLog.length` reste autorisé pour
    calculer l'ÉCART, mais pas comme nombre supprimé."""
    corps = _sans_commentaires_js(_extraire('resetLog'))
    i = corps.index('_confirmDupBanner')
    avant = corps[:i]
    assert '_totalCarnetReel()' in avant, (
        'le total doit être demandé au serveur avant de construire le '
        'dialogue :\n' + avant)
    assert not re.search(r'\{n:\s*affiches\}|\{n:\s*qsoLog\.length\}', corps), (
        'le nombre annoncé ne doit pas être celui de la vue :\n' + corps)
