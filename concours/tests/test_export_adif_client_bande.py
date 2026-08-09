# -*- coding: utf-8 -*-
"""Export ADIF du logbook (bouton « 📥 ADIF ») : <BAND> doit porter un LIBELLÉ
de l'énumération Band d'ADIF, pas la fréquence interne.

exportADIF() écrivait la bande en collant un « M » à la bande interne :

    <BAND:${(q.band+'M').length}>${q.band}M

Or la bande interne du log EST la fréquence en MHz ('14', '144', '3.5'), si
bien que le fichier contenait <BAND>14M, <BAND>144M, <BAND>3.5M là où la norme
attend 20m, 2m, 80m. Aucune des bandes gérées ne produisait une valeur valide,
y compris au regard de logx_adif_enums.ADIF_BANDS — la table officielle ADIF
3.1.7 déjà embarquée dans le projet — et une bande DÉJÀ normalisée par un
import ADIF ('1mm', présent dans le log réel) était corrompue en '1mmM'.

Conséquence terrain : TQSL/LoTW, eQSL et Club Log refusent la valeur de bande.
Ce chemin est le SEUL export ADIF manuel offert à l'opérateur (l'endpoint
correct /log/export/adif n'est appelé par aucune page), et le fichier est un
Blob téléchargé directement sur le disque : aucun passage serveur ne peut le
corriger après coup.

Le test exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer) avec un DOM minimal — même approche que
tests/test_macro_cw_serie_bande.py — et valide le fichier RÉELLEMENT produit
contre la table ADIF officielle du projet, plutôt que de recalculer le format
à côté."""
import os
import re
import subprocess
import sys

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
# EV-7 19e incrément : appel TOP-LEVEL renderVoiceDynPanel() dans
# logx_logbook.js -- ReferenceError au parse sans ce fichier chargé avant.
ESM_CALLBOT_JS_PATH = os.path.join(BASE, 'logx_esm_callbot.js')
# EV-7 20e incrément : appel TOP-LEVEL voiceRefreshSlots() dans
# logx_logbook.js -- même piège que renderVoiceDynPanel() (19e incrément).
VOICE_KEYER_JS_PATH = os.path.join(BASE, 'logx_voice_keyer.js')
# EV-7 23e incrément : buildAdifText()/exportADIF()/ADIF_BAND (JS, exercés
# directement ici) vivent désormais dans logx_export_adif.js -- à charger
# AVANT logx_logbook.js, même convention.
EXPORT_ADIF_JS_PATH = os.path.join(BASE, 'logx_export_adif.js')
# EV-7 33e incrément : appel TOP-LEVEL setInterval(refreshBandMap,...) dans
# logx_logbook.js -- ReferenceError au parse sans ce fichier chargé avant.
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')
sys.path.insert(0, BASE)

from logx_adif_enums import ADIF_BANDS          # noqa: E402  (table officielle)
from logx_export import ADIF_BAND               # noqa: E402  (version Python correcte)

# Commit juste AVANT ce correctif — sert à prouver que le scénario ci-dessous
# échoue bien sur le code d'origine (sinon ce ne serait pas un test de
# non-régression).
REV_AVANT_CORRECTIF = 'ae89b44'

_LIBELLES_OFFICIELS = {b.lower() for b in ADIF_BANDS}

# ─── DOM minimal ──────────────────────────────────────────────────────────────
_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', title:'', style:{}, checked:false, disabled:false, files:[], children:[]};
  var cls = {_s:new Set(), add:function(){}, remove:function(){}, contains:function(){return false;}, toggle:function(){return false;}};
  var handler = {
    get:function(target, prop){
      if(prop === 'classList') return cls;
      if(prop === 'style') return s.style;
      if(prop === 'dataset') return (s.dataset = s.dataset || {});
      if(prop === 'addEventListener') return function(){};
      if(prop === 'removeEventListener') return function(){};
      if(prop === 'appendChild') return function(c){ s.children.push(c); return c; };
      if(prop === 'insertBefore') return function(c){ s.children.unshift(c); return c; };
      if(prop === 'removeChild') return function(){};
      if(prop === 'querySelector') return function(){ return ElProxy(); };
      if(prop === 'querySelectorAll') return function(){ return []; };
      if(prop === 'closest') return function(){ return ElProxy(); };
      if(prop === 'contains') return function(){ return false; };
      if(prop === 'focus') return function(){};
      if(prop === 'select') return function(){};
      if(prop === 'click') return function(){};
      if(prop === 'getContext') return function(){ return null; };
      if(prop === 'getBoundingClientRect') return function(){ return {top:0,left:0,width:0,height:0,bottom:0,right:0}; };
      if(prop === 'setAttribute') return function(){};
      if(prop === 'getAttribute') return function(){ return null; };
      if(prop === 'remove') return function(){};
      if(prop === 'scrollIntoView') return function(){};
      return s[prop];
    },
    set:function(target, prop, val){ s[prop] = val; return true; }
  };
  return new Proxy({}, handler);
}
var document = {
  getElementById: function(id){ if(!__store[id]) __store[id] = ElProxy(); return __store[id]; },
  addEventListener: function(){}, removeEventListener: function(){},
  createElement: function(){ return ElProxy(); },
  querySelectorAll: function(){ return []; },
  querySelector: function(){ return ElProxy(); },
  body: ElProxy(), documentElement: ElProxy(),
};
var window = this;
window.addEventListener = function(){};
window.removeEventListener = function(){};
var console = {log:function(){}, warn:function(){}, error:function(){}, info:function(){}, debug:function(){}};
function setInterval(){ return 0; }
function setTimeout(){ return 0; }
function clearInterval(){}
function clearTimeout(){}
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
function fetch(){ return Promise.resolve({ ok:false, status:0, json: function(){ return Promise.resolve({}); } }); }
function alert(){}
function confirm(){ return false; }
function prompt(){ return null; }
var navigator = { userAgent:'test', mediaDevices: { enumerateDevices: function(){ return Promise.resolve([]); } },
                  clipboard:{ writeText:function(){ return Promise.resolve(); } } };
var location = { protocol:'http:', hostname:'127.0.0.1', href:'http://127.0.0.1/', search:'', reload:function(){} };
window.location = location;
function Notification(){}
Notification.permission = 'denied';
Notification.requestPermission = function(){ return Promise.resolve('denied'); };
function WebSocket(){ this.close = function(){}; }
function Blob(parts, opts){ this.parts = parts; }
window.URL = { createObjectURL:function(){ return 'blob:x'; }, revokeObjectURL:function(){} };
function Image(){ this.src = ''; }
function AudioContext(){}
function MediaRecorder(){}
var L = new Proxy({}, { get:function(){ return function(){ return new Proxy({}, {get:function(){ return function(){ return new Proxy({},{get:function(){ return function(){}; }}); }; }}); }; } });
"""

# ─── Capture du fichier réellement téléchargé ────────────────────────────────
# Seul le Blob est neutralisé (le téléchargement disque n'existe pas ici) : la
# construction du contenu ADIF, elle, reste INTACTE.
_CAPTURE = r"""
var __adif = null;
function Blob(parts, opts){ __adif = parts.join(''); }
function __exporter(qsos){
  myCall = 'F4GLD';
  myLocator = 'JN15WD';
  qsoLog = qsos;
  __adif = null;
  exportADIF();
  return __adif;
}
"""

# QSO tirés du log réel de l'utilisateur (shared_log.json) : la bande interne y
# est bien la fréquence en MHz, et '1mm' provient d'un import ADIF.
_QSOS = [
    {'call': 'F5DJL', 'band': '1.8', 'mode': 'SSB', 'rst_sent': '59', 'rst_rcvd': '59',
     'locator': 'JN18DT', 'date': '20210227', 'time': '22:13', 'num_sent': '001',
     'num_rcvd': '014', 'operator': 'OP1', 'my_locator': 'JN15WD', 'contest': 'REF_CDF_HF_SSB'},
    {'call': 'LZ2LP', 'band': '14', 'mode': 'SSB', 'rst_sent': '59', 'rst_rcvd': '59',
     'locator': '', 'date': '20210227', 'time': '13:02', 'num_sent': '002',
     'num_rcvd': '', 'operator': 'OP2', 'my_locator': 'JN15WD', 'contest': ''},
    {'call': 'F4OQU', 'band': '144', 'mode': 'FT8', 'rst_sent': '-05', 'rst_rcvd': '-11',
     'locator': 'JN03QQ', 'date': '20260101', 'time': '09:00', 'num_sent': '003',
     'num_rcvd': '021', 'operator': 'OP1', 'my_locator': 'JN15WD', 'contest': 'REF_IARU_VHF'},
    {'call': 'ZL3DMH', 'band': '432', 'mode': 'CW', 'rst_sent': '599', 'rst_rcvd': '599',
     'locator': 'JN15WD', 'date': '20260101', 'time': '10:30', 'num_sent': '004',
     'num_rcvd': '007', 'operator': 'OP3', 'my_locator': 'JN15WD', 'contest': 'REF_CDF_THF'},
    {'call': 'YT1AA', 'band': '3.5', 'mode': 'CW', 'rst_sent': '599', 'rst_rcvd': '599',
     'locator': '', 'date': '20260102', 'time': '21:45', 'num_sent': '005',
     'num_rcvd': '', 'operator': 'OP1', 'my_locator': 'JN15WD', 'contest': ''},
    # Bande DÉJÀ au format ADIF (QSO importé) : elle doit ressortir intacte.
    {'call': 'DL0AB', 'band': '1mm', 'mode': 'CW', 'rst_sent': '599', 'rst_rcvd': '599',
     'locator': '', 'date': '20260103', 'time': '08:00', 'num_sent': '006',
     'num_rcvd': '', 'operator': 'OP1', 'my_locator': 'JN15WD', 'contest': ''},
]


def _source(rev=None):
    """Source réelle de logx_logbook.js : HEAD par défaut, ou `rev` pour
    rejouer le scénario tel qu'il était AVANT ce correctif."""
    if rev is None:
        with open(ESM_CALLBOT_JS_PATH, encoding='utf-8') as f:
            src = f.read()
        with open(VOICE_KEYER_JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        with open(EXPORT_ADIF_JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        with open(FILTRE_SPOTS_JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        with open(JS_PATH, encoding='utf-8') as f:
            return src + '\n' + f.read()
    out = subprocess.run(
        ['git', 'show', f'{rev}:concours/logx_logbook.js'],
        cwd=BASE, capture_output=True, text=True, encoding='utf-8', check=True)
    return out.stdout


def _exporter(qsos=None, rev=None):
    """Contenu ADIF réellement produit par le bouton « 📥 ADIF »."""
    import json
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_source(rev))
    ctx.eval(_CAPTURE)     # après la source : remplace le Blob du préambule
    return ctx.eval(f'__exporter({json.dumps(qsos if qsos is not None else _QSOS)});')


def _champs(adif, nom):
    """Valeurs du champ `nom` dans l'ADIF, une par enregistrement (la longueur
    déclarée est vérifiée au passage : <CALL:5>F5DJL)."""
    valeurs = []
    for declaree, valeur in re.findall(rf'<{nom}:(\d+)>(\S*)', adif, re.I):
        assert int(declaree) == len(valeur), f'{nom} : longueur déclarée {declaree} ≠ {valeur!r}'
        valeurs.append(valeur)
    return valeurs


# ─── Reproduction du bug sur le code d'AVANT le correctif ────────────────────

def test_reproduction_bandes_invalides_avant_correctif():
    """Sur le commit d'origine, AUCUNE bande exportée n'est un libellé ADIF."""
    adif = _exporter(rev=REV_AVANT_CORRECTIF)
    bandes = _champs(adif, 'BAND')
    assert bandes == ['1.8M', '14M', '144M', '432M', '3.5M', '1mmM']
    assert [b for b in bandes if b.lower() in _LIBELLES_OFFICIELS] == []


def test_reproduction_toutes_les_bandes_gerees_invalides_avant_correctif():
    """Le défaut ne dépend pas du jeu d'essai : les 20 bandes du sélecteur
    produisaient toutes une valeur hors énumération."""
    qsos = [dict(_QSOS[0], call='F4TEST', band=b) for b in ADIF_BAND]
    adif = _exporter(qsos, rev=REV_AVANT_CORRECTIF)
    bandes = _champs(adif, 'BAND')
    assert len(bandes) == len(ADIF_BAND) == 20
    assert [b for b in bandes if b.lower() in _LIBELLES_OFFICIELS] == []


# ─── Le même scénario sur le code ACTUEL ─────────────────────────────────────

def test_bandes_conformes_a_l_enumeration_adif():
    """Chaque <BAND> exporté appartient à la table ADIF officielle du projet."""
    adif = _exporter()
    bandes = _champs(adif, 'BAND')
    assert bandes == ['160m', '20m', '2m', '70cm', '80m', '1mm']
    for b in bandes:
        assert b in _LIBELLES_OFFICIELS, f'{b} absent de logx_adif_enums.ADIF_BANDS'


def test_toutes_les_bandes_gerees_sont_valides():
    """Les 20 bandes du sélecteur — et pas seulement celles du jeu d'essai."""
    qsos = [dict(_QSOS[0], call='F4TEST', band=b) for b in ADIF_BAND]
    bandes = _champs(_exporter(qsos), 'BAND')
    assert len(bandes) == 20
    assert [b for b in bandes if b not in _LIBELLES_OFFICIELS] == []


def test_meme_traduction_que_la_version_python():
    """La table du client doit rester jumelle de logx_export.ADIF_BAND
    (/log/export/adif), sinon les deux exports du même log divergent."""
    qsos = [dict(_QSOS[0], call='F4TEST', band=b) for b in ADIF_BAND]
    assert _champs(_exporter(qsos), 'BAND') == [ADIF_BAND[b] for b in ADIF_BAND]


def test_bande_deja_normalisee_non_corrompue():
    """Un QSO importé porte déjà un libellé ADIF ('1mm') : le suffixer le
    rendait invalide alors qu'il ne demandait aucune traduction."""
    qsos = [dict(_QSOS[0], call='DL0AB', band='1mm'),
            dict(_QSOS[0], call='DL0AC', band='60m'),
            dict(_QSOS[0], call='DL0AD', band='2190m')]
    assert _champs(_exporter(qsos), 'BAND') == ['1mm', '60m', '2190m']


def test_bande_intraduisible_omise_plutot_qu_inventee():
    """Une valeur hors énumération fait rejeter TOUT l'enregistrement par
    TQSL : mieux vaut omettre le champ (le QSO reste identifiable par FREQ)."""
    qsos = [dict(_QSOS[0], call='F4TEST', band='3.14159', freq='')]
    adif = _exporter(qsos)
    assert _champs(adif, 'BAND') == []
    assert '<CALL:6>F4TEST' in adif        # le reste de l'enregistrement subsiste


def test_champs_indispensables_a_l_import():
    """Sans FREQ ni STATION_CALLSIGN/OPERATOR/CONTEST_ID/STX_SRX, un log
    multi-op n'est pas attribuable et l'échange de concours est perdu.

    OPERATOR : depuis le correctif du 08/08/2026 (signalement F4GLD — le
    tableau LOGBOOK affichait le libellé brut « OP1 » au lieu de l'indicatif
    réel), buildAdifText() résout l'ID opérateur interne via
    _resolveOperatorCallsign() avant de l'écrire dans le champ ADIF — un ID
    brut comme 'OP1' n'a jamais eu de sens pour TQSL/LoTW/ClubLog, qui
    attendent un VRAI indicatif dans OPERATOR. Ce test n'a aucune config
    operators[] en localStorage (DOM minimal), donc le résolveur retombe sur
    l'indicatif de la station (myCall = 'F4GLD') — repli attendu et correct
    pour un log single-op sans opérateurs[] déclarés."""
    qsos = [dict(_QSOS[2], freq='144.300')]
    adif = _exporter(qsos)
    assert _champs(adif, 'FREQ') == ['144.300']
    assert _champs(adif, 'STATION_CALLSIGN') == ['F4GLD']
    assert _champs(adif, 'OPERATOR') == ['F4GLD']
    assert _champs(adif, 'CONTEST_ID') == ['REF_IARU_VHF']
    assert _champs(adif, 'STX_STRING') == ['003']
    assert _champs(adif, 'SRX_STRING') == ['021']
    assert _champs(adif, 'MY_GRIDSQUARE') == ['JN15WD']
    assert _champs(adif, 'GRIDSQUARE') == ['JN03QQ']


def test_structure_adif_preservee():
    """En-tête + un <EOR> par QSO + champs vides omis (pas de <X:0>)."""
    adif = _exporter()
    assert '<EOH>' in adif
    assert adif.index('<ADIF_VER:5>3.1.4') < adif.index('<EOH>')
    assert adif.count('<EOR>') == len(_QSOS)
    assert ':0>' not in adif
    # QSO sans locator ni n° reçu : les champs correspondants sont absents.
    enregistrements = adif.split('<EOR>')
    lz2lp = next(r for r in enregistrements if 'LZ2LP' in r)
    assert '<GRIDSQUARE' not in lz2lp and '<SRX_STRING' not in lz2lp
    assert _champs(adif, 'QSO_DATE')[0] == '20210227'
    assert _champs(adif, 'TIME_ON')[0] == '2213'


def test_aller_retour_avec_l_importateur_du_projet():
    """Preuve de bout en bout : le fichier exporté est relu par l'importateur
    ADIF du projet (logx_import.parse_adif_to_qsos, celui-là même qui lit les
    fichiers des autres logiciels) et rend EXACTEMENT les bandes internes de
    départ, sans une seule erreur."""
    from logx_import import parse_adif_to_qsos
    qsos, erreurs = parse_adif_to_qsos(_exporter())
    assert erreurs == []
    assert [q['band'] for q in qsos] == [q['band'] for q in _QSOS]
    assert [q['call'] for q in qsos] == [q['call'] for q in _QSOS]
    assert [q['num_sent'] for q in qsos] == [q['num_sent'] for q in _QSOS]


def test_aller_retour_impossible_avant_correctif():
    """Avant le correctif, le même aller-retour ramenait des bandes fantômes
    ('14m' au lieu de '14') : même notre propre importateur ne pouvait pas
    retrouver la bande — dupes, score et diplômes faussés à la relecture."""
    from logx_import import parse_adif_to_qsos
    qsos, _ = parse_adif_to_qsos(_exporter(rev=REV_AVANT_CORRECTIF))
    relues = [q['band'] for q in qsos]
    assert relues == ['1.8m', '14m', '144m', '432m', '3.5m', '1mmm']
    assert relues != [q['band'] for q in _QSOS]


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    with open(JS_PATH, encoding='utf-8') as f:
        assert 'QSO Director' not in f.read()
