"""Lot 2 — le logiciel se comporte aussi comme un carnet de trafic courant.

Trois chantiers indépendants, réunis parce qu'ils répondent tous à la même
observation : jusqu'ici LogX AI supposait qu'on l'ouvrait POUR un concours.

1. Portée du mode DÉBUTANT. Le mécanisme `.expert-only` vivait entièrement
   dans logx_statusbar.js ; les fenêtres détachées (FT8/RTTY/SSTV) ne
   l'incluent pas, par conception. Elles n'étaient donc pas « en retard de
   marquage » : le mécanisme ne les atteignait pas du tout. D'où le socle
   logx_uimode.js, et les tests qui vérifient qu'il est bien inclus.

2. Nom / QTH / commentaire. Ils transitaient (annuaire) ou n'existaient pas
   (commentaire) et n'atteignaient jamais le carnet ni l'export ADIF.

3. A08 — quatre cases de la page CONFIG (JS8, PSK, AM, D-STAR) existaient
   depuis l'origine sans être reliées à quoi que ce soit : les cocher ne
   produisait aucun bouton de mode. PSK était même rattaché à `mode_rtty`, ce
   qui faisait DÉCOCHER sa propre case au WWA, dont le règlement §5 l'autorise.

Les vérifications passent par le VRAI code quand c'est possible (py_mini_racer
exécute renderModeButtons et callbookPourQso), et par une lecture de source
sinon — jamais par une copie de la logique dans le test.
"""

import json
import os
import re

import pytest

try:
    from py_mini_racer import MiniRacer
except ImportError:  # pragma: no cover - dépend de l'environnement
    MiniRacer = None

_ICI = os.path.dirname(os.path.abspath(__file__))
_CONCOURS = os.path.dirname(_ICI)

LOGBOOK_JS = os.path.join(_CONCOURS, 'logx_logbook.js')
LOGBOOK_HTML = os.path.join(_CONCOURS, 'logx_logbook.html')
CONFIG_JS = os.path.join(_CONCOURS, 'logx_configuration.js')
CONFIG_HTML = os.path.join(_CONCOURS, 'logx_configuration.html')
CALLBOOK_JS = os.path.join(_CONCOURS, 'logx_callbook.js')
UIMODE_JS = os.path.join(_CONCOURS, 'logx_uimode.js')
PAGES_DETACHEES = ['logx_ft8.html', 'logx_rtty.html', 'logx_sstv.html']


def _lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def _extraire_fonction(src, nom):
    """Extrait `function nom(...){...}` par comptage d'accolades — même
    technique que les autres tests JS du dépôt (une regex non gloutonne
    s'arrêterait à la première accolade fermante imbriquée)."""
    debut = src.index('function ' + nom)
    ouvrante = src.index('{', debut)
    prof, i = 0, ouvrante
    while True:
        if src[i] == '{':
            prof += 1
        elif src[i] == '}':
            prof -= 1
            if prof == 0:
                return src[debut:i + 1]
        i += 1


def _extraire_objet(src, marqueur):
    debut = src.index(marqueur)
    ouvrante = src.index('{', debut)
    prof, i = 0, ouvrante
    while True:
        if src[i] == '{':
            prof += 1
        elif src[i] == '}':
            prof -= 1
            if prof == 0:
                return src[debut:i + 1]
        i += 1


# ─── 1. Mode DÉBUTANT : portée du mécanisme expert-only ──────────────────────

def test_le_socle_uimode_injecte_la_regle_de_masquage():
    """logx_uimode.js doit poser la classe ET la règle CSS : poser seulement
    body.simple-mode ne masquerait rien sur une page sans barre de statut,
    qui est précisément le cas d'usage de ce fichier."""
    src = _lire(UIMODE_JS)
    assert "localStorage.getItem('rc_ui_mode')" in src, \
        'le socle doit lire la MÊME clé que CONFIG et la barre de statut'
    assert 'simple-mode' in src
    assert 'body.simple-mode .expert-only{display:none!important}' in src, \
        "sans cette règle injectée, .expert-only ne masque rien sur ces pages"


def test_le_socle_ne_masque_rien_si_le_stockage_est_indisponible():
    """Repli sûr : un localStorage inaccessible (navigation privée stricte,
    politique d'entreprise) ne doit pas amputer l'interface par accident."""
    if MiniRacer is None:
        pytest.skip('py_mini_racer absent')
    ctx = MiniRacer()
    ctx.eval("""
      var __ajouts = [];
      var localStorage = { getItem: function(){ throw new Error('bloqué'); } };
      var document = {
        body: { classList: { add: function(c){ __ajouts.push(c); } } },
        head: { appendChild: function(){ __ajouts.push('style'); } },
        createElement: function(){ return {}; },
        addEventListener: function(){},
      };
      var window = {};
    """)
    ctx.eval(_lire(UIMODE_JS))
    assert json.loads(ctx.eval('JSON.stringify(__ajouts)')) == [], \
        'un stockage inaccessible ne doit RIEN masquer'


@pytest.mark.parametrize('page', PAGES_DETACHEES)
def test_chaque_page_detachee_inclut_le_socle(page):
    """Sans cette inclusion, tout marquage expert-only de la page est
    silencieusement mort : rien ne casse, rien ne se masque non plus."""
    src = _lire(os.path.join(_CONCOURS, page))
    assert 'logx_uimode.js' in src, f'{page} ne charge pas le socle'
    assert src.index('logx_uimode.js') < src.index('logx_i18n.js'), \
        f'{page} doit charger le socle AVANT les scripts qui rendent l\'interface'


@pytest.mark.parametrize('page', PAGES_DETACHEES)
def test_le_socle_reference_existe_bien(page):
    """L'échec inverse serait silencieux : la page s'affiche normalement, seul
    le masquage ne se produit jamais. Aucun symptôme visuel, donc un test."""
    assert os.path.isfile(UIMODE_JS)
    assert 'logx_uimode.js' in _lire(os.path.join(_CONCOURS, page))


def test_les_reglages_de_calage_restent_visibles_en_mode_debutant():
    """Constat de la revue adversariale du 18/08/2026, deux cas distincts :

    - FT8 : la cascade INVITE au clic pour caler le ton (curseur crosshair +
      infobulle) et clicWaterfall() écrit dans #ft8Tone0. Masquer l'affichage
      chiffré en laissant le geste actif rend la fréquence d'émission
      modifiable par accident, sans aucun retour à l'écran.
    - RTTY : #rttyMark/#rttyShift sont les SEULS contrôles de calage de la
      page (ni cascade, ni AFC). Face à un poste réglé autrement (option
      1275/1615 Hz des Icom, chaîne AFSK centrée 1500 Hz), rien ne décode et
      le débutant n'a plus un seul réglage sous la main.

    « Masquer ≠ bloquer » suppose que ce qui est masqué ne soit pas actionnable
    par un geste resté visible."""
    ft8 = _lire(os.path.join(_CONCOURS, 'logx_ft8.html'))
    ligne_ton = next(ln for ln in ft8.splitlines() if 'id="ft8Tone0"' in ln)
    assert 'expert-only' not in ligne_ton

    rtty = _lire(os.path.join(_CONCOURS, 'logx_rtty.html'))
    for champ in ('id="rttyMark"', 'id="rttyShift"'):
        ligne = next(ln for ln in rtty.splitlines() if champ in ln)
        assert 'expert-only' not in ligne, f'{champ} doit rester visible'


# ─── 2. Nom / QTH / commentaire : le carnet garde ce qu'il a reçu ────────────

def _ctx_callbook():
    ctx = MiniRacer()
    ctx.eval('var document = { getElementById: function(){ return null; } };')
    ctx.eval(_extraire_fonction(_lire(CALLBOOK_JS), 'callbookPourQso')
             .replace('function callbookPourQso', 'var _callbookCourant = null;\n'
                      'function callbookPourQso', 1))
    return ctx


def test_le_callbook_ne_rend_rien_sans_fiche():
    if MiniRacer is None:
        pytest.skip('py_mini_racer absent')
    ctx = _ctx_callbook()
    assert json.loads(ctx.eval("JSON.stringify(callbookPourQso('F4GLD'))")) == {}


def test_le_callbook_rend_la_fiche_du_bon_indicatif():
    if MiniRacer is None:
        pytest.skip('py_mini_racer absent')
    ctx = _ctx_callbook()
    ctx.eval("_callbookCourant = {call:'F4GLD', name:'Pascal', qth:'Chalon',"
             " country:'France'};")
    assert json.loads(ctx.eval("JSON.stringify(callbookPourQso('f4gld'))")) == {
        'name': 'Pascal', 'qth': 'Chalon', 'country': 'France',
    }


def test_le_callbook_refuse_une_fiche_qui_ne_correspond_plus():
    """Le scénario réel : l'opérateur tape un indicatif, la fiche s'affiche,
    il efface et tape le bon. Sans cette vérification, le nom du PREMIER
    partirait dans le QSO du second — une donnée fausse est pire qu'absente."""
    if MiniRacer is None:
        pytest.skip('py_mini_racer absent')
    ctx = _ctx_callbook()
    ctx.eval("_callbookCourant = {call:'F4GLD', name:'Pascal', qth:'Chalon',"
             " country:'France'};")
    assert json.loads(ctx.eval("JSON.stringify(callbookPourQso('DL1ABC'))")) == {}


def test_le_champ_commentaire_existe_et_reste_visible_pour_un_debutant():
    """Le champ du trafic courant par excellence — le marquer expert-only le
    réserverait à ceux qui en ont le moins besoin."""
    html = _lire(LOGBOOK_HTML)
    assert 'id="inputComment"' in html
    bloc = html[html.index('id="commentGroup"') - 400:html.index('id="inputComment"') + 200]
    assert 'expert-only' not in bloc, \
        'le commentaire ne doit pas être réservé au mode expert'


def test_le_qso_enregistre_emporte_commentaire_nom_et_qth():
    src = _lire(LOGBOOK_JS)
    assert re.search(r"comment:\s*\(document\.getElementById\('inputComment'\)", src)
    assert 'callbookPourQso(call)' in src, \
        'le QSO doit fusionner la fiche d\'annuaire au moment de l\'enregistrement'


def test_le_champ_commentaire_est_vide_apres_enregistrement():
    """Un commentaire qui resterait collerait la remarque du QSO précédent au
    suivant — exactement le genre de donnée fausse qu'on cherche à éviter."""
    src = _extraire_fonction(_lire(LOGBOOK_JS), 'clearForm')
    assert 'inputComment' in src


def test_l_export_adif_emet_name_qth_et_comment():
    """Stocké mais absent de l'export, le contenu ne serait exploitable que
    dans LogX AI — l'inverse de la promesse du format d'échange."""
    import logx_export
    qsos = [{
        'call': 'F4GLD', 'band': '20m', 'mode': 'SSB',
        'date': '2026-08-18', 'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59',
        'name': 'Pascal', 'qth': 'Chalon-sur-Saone', 'comment': 'Antenne filaire',
    }]
    adif = logx_export.build_adif(qsos, {'callsign': 'F4XXX'})
    # Noms de champs en minuscules comme tout le reste du fichier produit par
    # _adif_field() — la spec ADIF déclare explicitement les noms de champs
    # insensibles à la casse, la longueur annoncée est ce qui compte.
    assert '<name:6>Pascal' in adif
    assert '<qth:16>Chalon-sur-Saone' in adif
    assert '<comment:15>Antenne filaire' in adif


def test_l_export_adif_omet_les_champs_vides():
    """Un log de concours n'a ni nom ni QTH : l'ADIF ne doit pas se remplir de
    champs vides pour autant (comportement de _adif_field, vérifié ici parce
    que c'est le lot qui ajoute ces trois appels)."""
    import logx_export
    adif = logx_export.build_adif(
        [{'call': 'F4GLD', 'band': '20m', 'mode': 'CW', 'date': '2026-08-18',
          'time': '1200', 'rst_sent': '599', 'rst_rcvd': '599'}],
        {'callsign': 'F4XXX'})
    for champ in ('<name:', '<qth:', '<comment:'):
        assert champ not in adif


# ─── 3. A08 : les cases de CONFIG pilotent enfin quelque chose ───────────────

def _cases_mode_de_config():
    """Les vraies cases data-key="mode_*" de la page, pas une liste écrite à la
    main qui divergerait au premier ajout."""
    return set(re.findall(r'data-key="(mode_[a-z0-9_]+)"', _lire(CONFIG_HTML)))


def test_chaque_case_de_mode_de_config_pilote_un_bouton():
    """Le défaut A08 : JS8, PSK, AM et D-STAR avaient une case depuis
    l'origine, absente de MODE_TOGGLE_KEY. Les cocher ne produisait aucun
    bouton — une case qui ne fait rien, sans le moindre message."""
    cles_utilisees = set(re.findall(r"'mode_[a-z0-9_]+'",
                                    _extraire_objet(_lire(LOGBOOK_JS),
                                                    'const MODE_TOGGLE_KEY = {')))
    cles_utilisees = {c.strip("'") for c in cles_utilisees}
    orphelines = _cases_mode_de_config() - cles_utilisees
    assert not orphelines, f'cases de CONFIG sans effet : {sorted(orphelines)}'


def test_les_deux_copies_de_la_table_de_modes_sont_identiques():
    """logx_logbook.js et logx_configuration.js dupliquent la table (pas de
    module partagé dans ce produit). Une divergence rendrait un mode cochable
    d'un côté et invisible de l'autre — sans erreur."""
    def _table(chemin):
        src = _extraire_objet(_lire(chemin), 'const MODE_TOGGLE_KEY = {')
        return dict(re.findall(r"'([A-Z0-9-]+)':\s*'(mode_[a-z0-9_]+)'", src))
    assert _table(LOGBOOK_JS) == _table(CONFIG_JS)


def test_psk_pointe_sur_sa_propre_case_pas_sur_celle_de_rtty():
    """Régression du WWA : son règlement §5 autorise PSK, mais PSK était
    traduit en `mode_rtty`, donc la case PSK ne figurait pas parmi les modes
    autorisés et applyContestFilters() la décochait."""
    src = _extraire_objet(_lire(LOGBOOK_JS), 'const MODE_TOGGLE_KEY = {')
    assert re.search(r"'PSK':\s*'mode_psk'", src)


def test_le_contexte_ia_connait_tous_les_modes_cochables():
    """Un mode coché mais absent de la table de logx_prompts est invisible pour
    l'assistant : il conseillera comme si l'opérateur ne le pratiquait pas."""
    import logx_prompts
    src = _lire(logx_prompts.__file__)
    bloc = src[src.index('mode_map = {'):src.index('}', src.index('mode_map = {'))]
    connues = set(re.findall(r"'(mode_[a-z0-9_]+)'", bloc))
    assert not _cases_mode_de_config() - connues


@pytest.mark.parametrize('mode,cle', [
    ('JS8', 'mode_js8'), ('PSK', 'mode_psk'),
    ('AM', 'mode_am'), ('DSTAR', 'mode_dstar'),
])
def test_cocher_une_case_produit_bien_son_bouton(mode, cle):
    """Exécute le VRAI renderModeButtons : c'est lui qui construit les boutons,
    une vérification sur la seule table ne prouverait pas que la 2e liste (les
    modes proposables) suit. C'est précisément là qu'était le trou."""
    if MiniRacer is None:
        pytest.skip('py_mini_racer absent')
    src = _lire(LOGBOOK_JS)
    ctx = MiniRacer()
    ctx.eval("""
      var __html = '';
      var CONTEST_MODES = {};
      var currentMode = null, _currentVisibleModes = [];
      var localStorage = { _v: '{}', getItem: function(){ return this._v; } };
      var document = { getElementById: function(id){
        return id === 'modePickerPopup'
          ? { set innerHTML(v){ __html = v; }, get innerHTML(){ return __html; } }
          : null;
      }};
      function _setCurrentModeLabel(){}
      function _adapterRSTAuMode(){}
    """)
    ctx.eval(_extraire_objet(src, 'const MODE_TOGGLE_KEY = {')
             .replace('const MODE_TOGGLE_KEY', 'var MODE_TOGGLE_KEY', 1))
    ctx.eval(_extraire_fonction(src, 'renderModeButtons'))
    ctx.eval("localStorage._v = JSON.stringify({toggles: {%s: true}});" % cle)
    ctx.eval("renderModeButtons('DXPEDITION');")
    assert json.loads(ctx.eval('JSON.stringify(_currentVisibleModes)')) == [mode]
    assert 'data-val="%s"' % mode in ctx.eval('__html')


def test_aucune_case_cochee_laisse_les_modes_du_concours():
    """Le filet de sécurité existant : une configuration vide ne doit pas
    aboutir à un sélecteur de modes vide, donc à un QSO impossible à saisir."""
    if MiniRacer is None:
        pytest.skip('py_mini_racer absent')
    src = _lire(LOGBOOK_JS)
    ctx = MiniRacer()
    ctx.eval("""
      var __html = '';
      var CONTEST_MODES = {'REF_CW': ['CW']};
      var currentMode = null, _currentVisibleModes = [];
      var localStorage = { _v: '{}', getItem: function(){ return this._v; } };
      var document = { getElementById: function(){ return null; } };
      function _setCurrentModeLabel(){}
      function _adapterRSTAuMode(){}
    """)
    ctx.eval(_extraire_objet(src, 'const MODE_TOGGLE_KEY = {')
             .replace('const MODE_TOGGLE_KEY', 'var MODE_TOGGLE_KEY', 1))
    ctx.eval(_extraire_fonction(src, 'renderModeButtons'))
    ctx.eval("renderModeButtons('REF_CW');")
    assert json.loads(ctx.eval('JSON.stringify(_currentVisibleModes)')) == ['CW']


def test_une_marque_dampli_dediee_desactive_le_pilotage_generique():
    """PGXL et ACOM ont leur PROPRE bloc de pilotage. Le champ générique était
    seulement MASQUÉ, en gardant sa valeur : /config/save enregistrait
    amp_enabled=true avec amp_brand='pgxl', et _make_driver() (logx_amp.py),
    qui ne connaît que elecraft/icom/spe, répondait « Marque d'ampli inconnue »
    en boucle — un ampli signalé injoignable en permanence."""
    src = _extraire_fonction(_lire(CONFIG_JS), 'updateAmpFieldsVisibility')
    bloc_dediee = src[src.index('if (dediee)'):]
    assert re.search(r"getElementById\('amp_enabled'\)\.value\s*=\s*''", bloc_dediee), \
        "le pilotage générique doit être remis à vide, pas seulement masqué"


def test_logx_amp_ne_sait_toujours_pas_piloter_pgxl_ni_acom():
    """Ancre du test précédent : c'est parce que _make_driver() ne connaît que
    elecraft/icom/spe que laisser amp_enabled à true avec amp_brand='pgxl'
    produit « Marque d'ampli inconnue » en boucle. Si un jour cette fonction
    apprenait 'pgxl', la remise à vide deviendrait discutable — ce test le
    signalera au lieu de laisser le correctif devenir du bruit."""
    import logx_amp
    for marque in ('pgxl', 'acom'):
        assert logx_amp._make_driver(marque, transport=None, civ_addr=0xAA) is None
    assert logx_amp._make_driver('elecraft', transport=None, civ_addr=0xAA) is not None
