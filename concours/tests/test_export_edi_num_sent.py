# -*- coding: utf-8 -*-
"""Export EDI (logx_logbook.js:exportEDI) — le n° de série ENVOYÉ écrit dans le
fichier doit être celui réellement transmis sur l'air, jamais un index de boucle.

Avant : `bandQSOs.forEach((q, idx)=>{ const serial = String(idx+1)... })`
renumérotait le log 1..N à l'export et jetait q.num_sent (le numéro alloué par
le serveur, logx_storage.allocate_next_serial, affiché à l'opérateur et passé au
correspondant). Or les trous dans la séquence sont un comportement NOMINAL et
documenté : allocate_next_serial réserve le numéro et « un trou dans la séquence
est toléré », et un QSO supprimé en cours d'épreuve (deleteQSO/undoLastQSO), un
doublon refusé après allocation, une erreur serveur après allocation ou un QSO
incomplet écarté par isValidQSO() en créent un. Dès le premier trou, tout le
reste du log de la bande partait au correcteur avec un numéro décalé — en
cross-check IARU/REF, un n° envoyé qui ne correspond pas au n° reçu par le
correspondant fait tomber le QSO (NIL) des DEUX côtés.

Deux défauts annexes sur la même ligne : `q.num_rcvd||'001'` fabriquait un n°
reçu dans un log de soumission quand le champ était vide, et le mode texte
(SSB/CW) était écrit dans le 13e champ du gabarit REG1TEST (« new WWL ») alors
que le mode est déjà en 4e position sous forme de code numérique.

Ce module exécute le VRAI logx_logbook.js dans un moteur JS réel (V8 via
py_mini_racer) et lit le contenu du fichier réellement produit, avec des
num_sent issus du VRAI allocateur serveur logx_storage.allocate_next_serial."""
import json
import os
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
# EV-7 25e incrément : exportEDI() (testée dans ce fichier) a été extraite
# vers ce fichier -- doit être chargé AVANT logx_logbook.js, même convention.
EXPORT_EDI_JS_PATH = os.path.join(BASE, 'logx_export_edi.js')
# EV-7 29e incrément : exportEDI() appelle getSoapbox() en corps de
# fonction -- getSoapbox() a été extraite vers ce fichier, sans quoi
# l'appel lèverait un ReferenceError pendant l'exécution réelle du test.
SOAPBOX_JS_PATH = os.path.join(BASE, 'logx_soapbox.js')
# EV-7 33e incrément : appel TOP-LEVEL setInterval(refreshBandMap,...) dans
# logx_logbook.js -- ReferenceError au parse sans ce fichier chargé avant.
FILTRE_SPOTS_JS_PATH = os.path.join(BASE, 'logx_filtre_spots.js')
sys.path.insert(0, BASE)

import logx_storage as storage   # noqa: E402  (après sys.path)

# Commit juste AVANT le correctif — sert à prouver que ce module échoue bien
# sur le code d'origine (sinon ce ne serait pas un test de non-régression).
REV_AVANT_FIX = '5e43766'

# ─── DOM minimal ──────────────────────────────────────────────────────────────
# logx_logbook.js est un script de page (pas un module) : il référence document/
# window/localStorage/fetch/... à la volée. Un Proxy générique pour les éléments
# DOM évite d'avoir à lister tous les id du fichier.
_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', style:{}, checked:false, disabled:false, files:[], children:[]};
  var cls = {_s:new Set(), add:function(){for(var i=0;i<arguments.length;i++) this._s.add(arguments[i]);},
             remove:function(){for(var i=0;i<arguments.length;i++) this._s.delete(arguments[i]);},
             contains:function(c){return this._s.has(c);},
             toggle:function(c){ if(this._s.has(c)) this._s.delete(c); else this._s.add(c); return this._s.has(c);}};
  var handler = {
    get:function(target, prop){
      if(prop === 'classList') return cls;
      if(prop === 'style') return s.style;
      if(prop === 'dataset') return (s.dataset = s.dataset || {});
      if(prop === 'addEventListener') return function(){};
      if(prop === 'removeEventListener') return function(){};
      if(prop === 'appendChild') return function(c){ s.children.push(c); return c; };
      if(prop === 'insertBefore') return function(c){ s.children.unshift(c); return c; };
      if(prop === 'removeChild') return function(c){ var i=s.children.indexOf(c); if(i>=0) s.children.splice(i,1); };
      if(prop === 'querySelector') return function(){ return ElProxy(); };
      if(prop === 'querySelectorAll') return function(){ return []; };
      if(prop === 'focus') return function(){};
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
function setInterval(){ return 0; }
function setTimeout(){ return 0; }
function clearInterval(){}
function clearTimeout(){}
var localStorage = {
  _d:{}, getItem:function(k){ return (k in this._d)? this._d[k] : null; },
  setItem:function(k,v){ this._d[k]=String(v); }, removeItem:function(k){ delete this._d[k]; }
};
function fetch(){ return Promise.resolve({ ok:false, json: function(){ return Promise.resolve({}); } }); }
function alert(){}
function confirm(){ return false; }
function prompt(){ return null; }
var navigator = { userAgent:'test', mediaDevices: { enumerateDevices: function(){ return Promise.resolve([]); } }, clipboard:{} };
var location = { protocol:'http:', hostname:'127.0.0.1', href:'http://127.0.0.1/', search:'', reload:function(){} };
window.location = location;
window.open = function(){ return null; };   // popup bloquée : remindSubmitLog() gère déjà ce cas (fallback texte)
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

# Après chargement du script : on capture le contenu des fichiers réellement
# générés (Blob -> URL.createObjectURL) et on rend setTimeout synchrone, car
# exportEDI() espace les téléchargements dans le temps (un fichier par bande).
_CAPTURE = r"""
window.__files = [];
Blob = function(parts, opts){ this.parts = parts; };
window.URL = { createObjectURL:function(b){ window.__files.push(b.parts.join('')); return 'blob:x'; },
               revokeObjectURL:function(){} };
setTimeout = function(fn){ if(typeof fn === 'function') fn(); return 0; };
confirm = function(){ return true; };   // on génère malgré les avertissements
"""


def _real_source(rev=None):
    """Source réelle de logx_logbook.js : HEAD par défaut, ou `rev` (ex. le
    commit d'avant le correctif) pour rejouer le scénario tel qu'il était."""
    if rev is None:
        with open(ESM_CALLBOT_JS_PATH, encoding='utf-8') as f:
            src = f.read()
        with open(VOICE_KEYER_JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        with open(EXPORT_EDI_JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        with open(SOAPBOX_JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        with open(FILTRE_SPOTS_JS_PATH, encoding='utf-8') as f:
            src += '\n' + f.read()
        with open(JS_PATH, encoding='utf-8') as f:
            return src + '\n' + f.read()
    out = subprocess.run(
        ['git', 'show', f'{rev}:concours/logx_logbook.js'],
        cwd=BASE, capture_output=True, text=True, encoding='utf-8', check=True)
    return out.stdout


def _export_edi(qsos, rev=None, contest='REF_RPH'):
    """Exécute le VRAI exportEDI() sur ce log et renvoie la liste des fichiers
    EDI produits (un par bande), sous forme de texte."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_real_source(rev))
    ctx.eval(_CAPTURE)
    ctx.eval(f"""
    myCall = 'F4GLD'; myLocator = 'JN18CX';
    currentContest = {contest!r};
    qsoLog = {_js(qsos)};
    exportEDI();
    """)
    # py_mini_racer ne convertit pas les tableaux JS en listes Python : on passe
    # par JSON (les \r\n des enregistrements EDI y survivent tels quels).
    return json.loads(ctx.eval('JSON.stringify(window.__files)'))


def _js(obj):
    return json.dumps(obj, ensure_ascii=False)


def _records(edi_text):
    """Enregistrements QSO du fichier (tout ce qui suit [QSOrecords;n])."""
    lines = edi_text.split('\r\n')
    start = next(i for i, l in enumerate(lines) if l.startswith('[QSOrecords'))
    end = next(i for i, l in enumerate(lines) if l.startswith('[END'))
    return [l for l in lines[start + 1:end] if l.strip()]


def _champ(record, n):
    """n-ième champ (1-indexé) d'un enregistrement REG1TEST."""
    return record.split(';')[n - 1]


def _qso(call, num_sent, num_rcvd='001', band='144', time='12:00', mode='SSB'):
    return {'id': call, 'call': call, 'band': band, 'mode': mode, 'time': time,
            'date': '20260704', 'rst_sent': '59', 'num_sent': num_sent,
            'rst_rcvd': '59', 'num_rcvd': num_rcvd, 'locator': 'JN18CX',
            'operator': 'F4GLD', 'dist': 100, 'points': 100}


def _log_avec_trou():
    """Scénario 100 % nominal, num_sent produits par le VRAI allocateur serveur :
    5 QSO alloués, l'opérateur en supprime un (mal saisi) -> la séquence
    conservée est 001,002,004,005 et le n° 003 n'est jamais réattribué."""
    storage.shared_log[:] = []
    storage._serial_high_water.clear()
    calls = ['DL1AAA', 'ON4BBB', 'G3CCC', 'PA0DDD', 'EA1EEE']
    alloues = []
    for c in calls:
        n = storage.allocate_next_serial('144')
        alloues.append((c, f'{n:03d}'))
        storage.shared_log.append({'band': '144', 'call': c, 'num_sent': f'{n:03d}'})
    # deleteQSO(G3CCC) : le QSO part du log, son n° n'est jamais réutilisé
    storage.shared_log[:] = [q for q in storage.shared_log if q['call'] != 'G3CCC']
    assert storage.allocate_next_serial('144') == 6      # 003 n'est PAS recyclé
    restants = [(c, n) for c, n in alloues if c != 'G3CCC']
    assert [n for _, n in restants] == ['001', '002', '004', '005']
    return [_qso(c, n, time=f'12:0{i}') for i, (c, n) in enumerate(restants)]


# ─── Le scénario sur le commit d'AVANT le correctif : il doit échouer ────────

def test_reproduction_numero_renumerote_avant_fix():
    """Sur 5e43766, le n° envoyé exporté est l'index de boucle : les QSO qui
    suivent le trou partent avec un numéro que le correspondant n'a jamais reçu."""
    qsos = _log_avec_trou()
    recs = _records(_export_edi(qsos, rev=REV_AVANT_FIX)[0])
    exportes = [_champ(r, 6) for r in recs]
    assert exportes == ['001', '002', '003', '004']          # renumérotation 1..N
    assert exportes != [q['num_sent'] for q in qsos]          # ≠ ce qui est passé sur l'air


def test_reproduction_num_rcvd_invente_avant_fix():
    """Sur 5e43766, un n° reçu vide devient '001' — donnée inventée."""
    recs = _records(_export_edi([_qso('DL1AAA', '001', num_rcvd='')], rev=REV_AVANT_FIX)[0])
    assert _champ(recs[0], 8) == '001'


def test_reproduction_mode_en_champ_13_avant_fix():
    """Sur 5e43766, le champ 13 (« new WWL ») contient le mode en texte."""
    recs = _records(_export_edi([_qso('DL1AAA', '001')], rev=REV_AVANT_FIX)[0])
    assert _champ(recs[0], 13) == 'SSB'


# ─── Le même scénario sur le code ACTUEL ─────────────────────────────────────

def test_le_numero_exporte_est_celui_transmis_sur_l_air():
    """Cœur du correctif : chaque enregistrement porte le num_sent du QSO,
    trou compris — aucun décalage possible avec le log du correspondant."""
    qsos = _log_avec_trou()
    recs = _records(_export_edi(qsos)[0])
    assert [_champ(r, 6) for r in recs] == ['001', '002', '004', '005']
    # et l'indicatif reste bien apparié à son numéro
    assert [(_champ(r, 3), _champ(r, 6)) for r in recs] == \
        [('DL1AAA', '001'), ('ON4BBB', '002'), ('PA0DDD', '004'), ('EA1EEE', '005')]


def test_qso_incomplet_ecarte_ne_decale_pas_les_suivants():
    """isValidQSO() écarte les QSO incomplets de l'export : leur absence ne doit
    pas renuméroter ceux qui restent."""
    qsos = [_qso('DL1AAA', '001', time='12:00'),
            _qso('ON4BBB', '002', time='12:01'),
            _qso('G3CCC',  '003', time='12:02'),
            _qso('PA0DDD', '004', time='12:03')]
    qsos[1]['rst_rcvd'] = ''      # QSO incomplet -> ignoré par isValidQSO()
    recs = _records(_export_edi(qsos)[0])
    assert [(_champ(r, 3), _champ(r, 6)) for r in recs] == \
        [('DL1AAA', '001'), ('G3CCC', '003'), ('PA0DDD', '004')]


def test_chaque_bande_garde_ses_propres_numeros():
    """Un fichier par bande, et chaque bande garde SA séquence (le serveur
    alloue par bande) — le découpage par bande ne renumérote rien."""
    qsos = [_qso('DL1AAA', '001', band='144', time='12:00'),
            _qso('ON4BBB', '007', band='144', time='12:01'),
            _qso('G3CCC',  '003', band='432', time='12:02'),
            _qso('PA0DDD', '009', band='432', time='12:03')]
    files = _export_edi(qsos)
    assert len(files) == 2
    par_bande = {}
    for f in files:
        band = next(l for l in f.split('\r\n') if l.startswith('PBand=')).split('=')[1]
        par_bande[band] = [(_champ(r, 3), _champ(r, 6)) for r in _records(f)]
    assert par_bande['144 MHz'] == [('DL1AAA', '001'), ('ON4BBB', '007')]
    assert par_bande['432 MHz'] == [('G3CCC', '003'), ('PA0DDD', '009')]


def test_numero_non_pade_par_le_serveur_reste_correct():
    """Un num_sent stocké sans zéros de tête (édition manuelle, import) est
    complété à 3 chiffres, mais sa VALEUR est conservée."""
    recs = _records(_export_edi([_qso('DL1AAA', '7'), _qso('ON4BBB', '42', time='12:01')])[0])
    assert [_champ(r, 6) for r in recs] == ['007', '042']


def test_echange_fixe_non_numerique_recopie_tel_quel():
    """Un échange non numérique (type Field Day '1D') ne doit pas être écrasé
    par un numéro fabriqué."""
    recs = _records(_export_edi([_qso('DL1AAA', '1D')])[0])
    assert _champ(recs[0], 6) == '1D'


def test_numero_envoye_absent_reste_vide():
    """Aucun numéro inventé dans un log de soumission : champ vide si le QSO
    n'en a pas (au lieu d'un index de boucle plausible mais faux)."""
    recs = _records(_export_edi([_qso('DL1AAA', '')])[0])
    assert _champ(recs[0], 6) == ''


def test_num_rcvd_vide_reste_vide():
    recs = _records(_export_edi([_qso('DL1AAA', '001', num_rcvd='')])[0])
    assert _champ(recs[0], 8) == ''
    # un n° reçu réel est bien conservé (et normalisé sur 3 chiffres)
    recs = _records(_export_edi([_qso('ON4BBB', '001', num_rcvd='12')])[0])
    assert _champ(recs[0], 8) == '012'


def test_gabarit_reg1test_15_champs_mode_en_champ_4():
    """Le mode est un code numérique en champ 4 ; le champ 13 est l'indicateur
    « new WWL » et doit rester vide, pas porter une 2e copie du mode."""
    qsos = [_qso('DL1AAA', '001', mode='SSB'),
            _qso('ON4BBB', '002', mode='CW', time='12:01'),
            _qso('G3CCC',  '003', mode='FM', time='12:02')]
    recs = _records(_export_edi(qsos)[0])
    assert [_champ(r, 4) for r in recs] == ['1', '2', '6']
    for r in recs:
        assert len(r.split(';')) == 15
        assert _champ(r, 13) == ''
        assert 'SSB' not in r and 'CW' not in r and 'FM' not in r


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    with open(JS_PATH, encoding='utf-8') as f:
        assert 'QSO Director' not in f.read()
    with open(EXPORT_EDI_JS_PATH, encoding='utf-8') as f:
        assert 'QSO Director' not in f.read()
