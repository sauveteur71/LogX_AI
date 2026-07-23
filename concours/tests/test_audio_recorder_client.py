# -*- coding: utf-8 -*-
"""Enregistreur audio par QSO (tampon glissant) — logx_logbook.js/html.

Fonctionnalité 100% navigateur (MediaRecorder, getUserMedia, Web Audio,
File System Access), mais py_mini_racer (déjà une dépendance du projet, voir
requirements.txt et test_logbook_render_window_reset.py) permet d'exécuter le
VRAI logx_logbook.js dans un moteur JS réel (V8) avec un DOM minimal — donc de
tester la logique pour de vrai, pas seulement par grep sur le texte source.

Les tests ci-dessous sont répartis en deux familles :
- Garde-fous statiques (présence des briques clés, branchement dans
  submitQSO, absence de la chaîne interdite) : rapides, déclenchent si
  quelqu'un supprime la fonctionnalité ou casse son branchement.
- Tests d'EXÉCUTION RÉELLE (moteur V8) : rejouent le scénario concret sur le
  commit d'origine 5a2c452 pour prouver le bug (reproduction), puis sur le
  code ACTUEL pour prouver le correctif — encodage WAV, découpe des dernières
  secondes, auto-démarrage en mode UI simple, resynchronisation localStorage,
  et micro ouvert une seule fois."""
import json
import os
import subprocess

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — tests JS réels ignorés')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS_PATH = os.path.join(BASE, 'logx_logbook.js')
HTML_PATH = os.path.join(BASE, 'logx_logbook.html')


def _read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def test_pas_de_qso_director():
    """Interdiction absolue (nom d'un concurrent) — jamais dans le code."""
    assert 'QSO Director' not in _read(JS_PATH)
    assert 'QSO Director' not in _read(HTML_PATH)


def test_briques_enregistreur_presentes_dans_le_js():
    js = _read(JS_PATH)
    for marker in (
        'function startAudioRecorder', 'function stopAudioRecorder',
        'async function toggleAudioRecorder', 'async function captureQsoAudioClip',
        'function _recStartSegment', 'function _recFinishCurrentSegment',
        'function _encodeWavFromBuffers', 'function _floatChannelsToWav',
        'function _recClipName', 'function _recSaveClip', 'function chooseRecDir',
        'async function loadAudioInputDevices',
    ):
        assert marker in js, f'{marker!r} manquant dans logx_logbook.js'


def test_pas_de_flux_continu_sans_decoupage_en_segments():
    """Piège connu : un WebM/Ogg découpé en plein milieu d'un flux continu
    n'est pas rejouable (seul le tout premier fragment porte l'en-tête du
    conteneur) — la fonctionnalité DOIT redémarrer périodiquement le
    MediaRecorder pour produire des segments autonomes décodables un par un."""
    js = _read(JS_PATH)
    assert 'REC_SEGMENT_MS' in js
    assert '_recRestartSegment' in js
    assert 'setInterval(_recRestartSegment' in js


def test_capture_clip_branchee_dans_les_trois_chemins_de_succes_submitQSO():
    """Le clip doit se déclencher à chaque QSO réellement enregistré : succès
    serveur direct, doublon confirmé par l'opérateur, ET repli hors-ligne —
    sinon un des trois modes de validation resterait silencieusement sans
    enregistrement audio."""
    js = _read(JS_PATH)
    start = js.index('async function submitQSO')
    end = js.index('function clearForm', start)
    submit_body = js[start:end]
    assert submit_body.count('captureQsoAudioClip(') == 3


def test_capture_clip_ignoree_si_desactivee():
    """Garde-fou explicite en tête de captureQsoAudioClip : ne rien faire
    (ni ouverture de flux, ni notification) si l'enregistreur est éteint."""
    js = _read(JS_PATH)
    start = js.index('async function captureQsoAudioClip')
    end = js.index('\n}', start)
    body = js[start:end]
    assert 'if(!recEnabled || !_recStream) return;' in body


def test_panneau_html_present_avec_ses_controles():
    """Les deux contrôles demandés (activer/désactiver + choix du micro),
    plus le choix de dossier (File System Access)."""
    html = _read(HTML_PATH)
    assert 'id="qsoRecPanel"' in html
    assert 'onclick="toggleAudioRecorder()"' in html
    assert 'id="qsoRecDevice"' in html and 'onchange="onRecDeviceChange()"' in html
    assert 'onclick="chooseRecDir()"' in html


def test_wav_pas_de_concatenation_naive_de_conteneurs():
    """Piège connu : concaténer plusieurs fichiers WebM/Ogg bout à bout ne
    rejoue souvent que le premier auprès du lecteur — le code doit décoder
    chaque segment en PCM (decodeAudioData) puis ré-encoder un seul WAV."""
    js = _read(JS_PATH)
    assert 'decodeAudioData' in js
    assert "type: 'audio/wav'" in js


# ═══════════════════════════════════════════════════════════════════════════
# ─── Exécution réelle (V8 via py_mini_racer) ────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════
# DOM minimal (même principe que test_logbook_render_window_reset.py) : un
# Proxy générique pour les éléments DOM évite d'avoir à lister tous les id.
# Étendu ici avec un MediaRecorder et un getUserMedia réellement fonctionnels
# (état, compteur d'appels, échec configurable) — pas de simples coquilles
# vides — pour pouvoir faire tourner startAudioRecorder()/initAudioRecorder
# Panel() pour de vrai, jusqu'au bout de leurs chemins async.
_DOM_PREAMBLE = r"""
var __store = {};
function ElProxy(){
  var s = {value:'', textContent:'', innerHTML:'', style:{}, checked:false, disabled:false, files:[], children:[], name:''};
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
var __getUserMediaCalls = 0;
var __getUserMediaShouldFail = false;
function _fakeMicStream(){ return { getTracks: function(){ return [{stop:function(){}}]; } }; }
var navigator = {
  userAgent:'test',
  mediaDevices: {
    enumerateDevices: function(){ return Promise.resolve([{kind:'audioinput', deviceId:'d1', label:'Mic test'}]); },
    getUserMedia: function(constraints){
      __getUserMediaCalls++;
      return __getUserMediaShouldFail
        ? Promise.reject(new Error('Permission refusée (test)'))
        : Promise.resolve(_fakeMicStream());
    }
  },
  clipboard:{}
};
var location = { protocol:'http:', hostname:'127.0.0.1', href:'http://127.0.0.1/', search:'', reload:function(){} };
window.location = location;
function Notification(){}
Notification.permission = 'denied';
Notification.requestPermission = function(){ return Promise.resolve('denied'); };
function WebSocket(){ this.close = function(){}; }
function Blob(parts, opts){ this.parts = parts; this.type = opts && opts.type; }
window.URL = { createObjectURL:function(){ return 'blob:x'; }, revokeObjectURL:function(){} };
function Image(){ this.src = ''; }
function AudioContext(){}
// MediaRecorder réellement fonctionnel (état + onstop synchrone), pas une
// coquille vide : startAudioRecorder()/_recStartSegment() doivent pouvoir
// tourner jusqu'au bout sans lever d'exception (rec.start()/stop() réels).
function MediaRecorder(stream, opts){
  this.state = 'inactive'; this.stream = stream; this.mimeType = (opts && opts.mimeType) || '';
  this.ondataavailable = null; this.onstop = null;
}
MediaRecorder.isTypeSupported = function(){ return false; };
MediaRecorder.prototype.start = function(){ this.state = 'recording'; };
MediaRecorder.prototype.stop = function(){
  if(this.state === 'inactive') return;
  this.state = 'inactive';
  if(this.ondataavailable) this.ondataavailable({data: {size: 1}});
  if(this.onstop) this.onstop();
};
var L = new Proxy({}, { get:function(){ return function(){ return new Proxy({}, {get:function(){ return function(){ return new Proxy({},{get:function(){ return function(){}; }}); }; }}); }; } });
"""


def _real_source(rev=None):
    """Source réelle de logx_logbook.js : HEAD (répertoire de travail) par
    défaut, ou `rev` (ex. le commit d'origine 5a2c452) pour rejouer le
    scénario tel qu'il était AVANT ce correctif."""
    if rev is None:
        return _read(JS_PATH)
    out = subprocess.run(
        ['git', 'show', f'{rev}:concours/logx_logbook.js'],
        cwd=BASE, capture_output=True, text=True, encoding='utf-8', check=True)
    return out.stdout


def _make_ctx(rev=None, storage=None, gum_should_fail=False):
    """Contexte V8 chargé du VRAI logx_logbook.js. `storage` préseede
    localStorage AVANT le chargement du script (le script lit
    'logx_rec_enabled'/'rc_ui_mode' dès ses premières lignes ET appelle
    initAudioRecorderPanel() tout en bas, sans attendre un DOMContentLoaded —
    donc charger le script EST le scénario « ouverture de la page »)."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    seed = ['__getUserMediaShouldFail = %s;' % ('true' if gum_should_fail else 'false')]
    for k, v in (storage or {}).items():
        seed.append('localStorage.setItem(%s, %s);' % (json.dumps(k), json.dumps(v)))
    ctx.eval('\n'.join(seed))
    ctx.eval(_real_source(rev))
    return ctx


# ─── Problème 1 (HIGH) : auto-démarrage en mode UI simple ───────────────────
# Le panneau #qsoRecPanel (bouton marche/arrêt inclus) est masqué par
# .expert-only quand rc_ui_mode==='simple' (voir logx_statusbar.js) — un
# enregistrement démarré quand même y serait invisible et incontrôlable.

def test_reproduction_bug_sur_5a2c452_auto_demarre_en_mode_simple():
    """Sur le commit d'origine, l'auto-démarrage IGNORE rc_ui_mode : le micro
    s'ouvre même en mode UI simple, sans aucun contrôle visible possible."""
    ctx = _make_ctx(rev='5a2c452', storage={'logx_rec_enabled': 'on', 'rc_ui_mode': 'simple'})
    # Le bug : getUserMedia a bien été appelé malgré le mode simple.
    assert ctx.eval('__getUserMediaCalls') >= 1
    assert ctx.eval('recEnabled') is True


def test_auto_demarrage_bloque_en_mode_simple():
    """Sur le code actuel : même préconditions, le micro NE s'ouvre PAS, et
    l'état 'on' persisté est corrigé en 'off' (pas seulement en mémoire)."""
    ctx = _make_ctx(storage={'logx_rec_enabled': 'on', 'rc_ui_mode': 'simple'})
    assert ctx.eval('__getUserMediaCalls') == 0
    assert ctx.eval('recEnabled') is False
    assert ctx.eval("localStorage.getItem('logx_rec_enabled')") == 'off'


def test_auto_demarrage_toujours_actif_en_mode_expert():
    """Non-régression : le mode expert (rc_ui_mode absent ou 'expert') doit
    toujours auto-démarrer l'enregistreur quand il était activé."""
    ctx = _make_ctx(storage={'logx_rec_enabled': 'on'})
    assert ctx.eval('__getUserMediaCalls') >= 1
    assert ctx.eval('recEnabled') is True
    assert ctx.eval("localStorage.getItem('logx_rec_enabled')") == 'on'


def test_rec_auto_start_allowed_fonction_pure():
    """_recAutoStartAllowed() isolée : testable sans DOM ni micro réel."""
    ctx = _make_ctx(storage={'logx_rec_enabled': 'on', 'rc_ui_mode': 'simple'})
    # initAudioRecorderPanel() a déjà tourné au chargement (mode simple) et a
    # corrigé recEnabled à false — on le repasse à true pour isoler ici
    # uniquement la fonction pure, indépendamment de ce qui l'a appelée avant.
    ctx.eval('recEnabled = true;')
    assert ctx.eval('_recAutoStartAllowed()') is False
    ctx.eval("localStorage.setItem('rc_ui_mode', 'expert');")
    assert ctx.eval('_recAutoStartAllowed()') is True
    ctx.eval('recEnabled = false;')
    assert ctx.eval('_recAutoStartAllowed()') is False


# ─── Problème 3 (MEDIUM) : localStorage jamais resynchronisé après échec ────

def test_reproduction_bug_sur_5a2c452_localstorage_pas_resynchronise():
    """Sur le commit d'origine : micro refusé au chargement -> recEnabled (JS)
    corrigé à false, mais 'logx_rec_enabled' reste 'on' dans localStorage."""
    ctx = _make_ctx(rev='5a2c452', storage={'logx_rec_enabled': 'on'}, gum_should_fail=True)
    assert ctx.eval('recEnabled') is False
    # Le bug : localStorage n'a jamais été corrigé, contrairement à la variable JS.
    assert ctx.eval("localStorage.getItem('logx_rec_enabled')") == 'on'


def test_localstorage_resynchronise_apres_echec_auto_demarrage():
    """Sur le code actuel : même scénario, localStorage suit désormais l'état
    réel — sinon un rechargement de page retenterait indéfiniment le même
    auto-démarrage voué à l'échec."""
    ctx = _make_ctx(storage={'logx_rec_enabled': 'on'}, gum_should_fail=True)
    assert ctx.eval('recEnabled') is False
    assert ctx.eval("localStorage.getItem('logx_rec_enabled')") == 'off'


# ─── Problème 5 (LOW) : deuxième flux micro concurrent inutile ─────────────

def test_reproduction_bug_sur_5a2c452_deuxieme_flux_micro_concurrent():
    """Sur le commit d'origine, startAudioRecorder() ouvre DEUX flux micro :
    le sien, puis un second via loadAudioInputDevices() rien que pour les
    libellés — alors que la permission est déjà acquise globalement."""
    ctx = _make_ctx(rev='5a2c452', storage={'logx_rec_enabled': 'on'})
    assert ctx.eval('__getUserMediaCalls') == 2


def test_un_seul_flux_micro_ouvert_au_demarrage():
    """Sur le code actuel : un seul getUserMedia() au total — le second est
    supprimé, loadAudioInputDevices() réutilise la permission déjà acquise."""
    ctx = _make_ctx(storage={'logx_rec_enabled': 'on'})
    assert ctx.eval('__getUserMediaCalls') == 1
    assert ctx.eval('!!_recStream') is True


# ─── Problème 2 (HIGH) : collision de nom de fichier (même minute UTC) ──────

def test_reproduction_bug_sur_5a2c452_collision_nom_de_fichier():
    """Sur le commit d'origine, deux QSO même indicatif+bande dans la même
    minute UTC (mais à des secondes différentes) produisent EXACTEMENT le
    même nom de fichier — le second écraserait silencieusement le premier."""
    ctx = _make_ctx(rev='5a2c452')
    qso1 = {'call': 'F4ABC', 'band': '144', 'date': '20260723', 'time': '14:32',
            'id': 1784817125000}   # 2026-07-23T14:32:05Z
    qso2 = {'call': 'F4ABC', 'band': '144', 'date': '20260723', 'time': '14:32',
            'id': 1784817170000}   # 2026-07-23T14:32:50Z (même minute, autre seconde)
    name1 = ctx.eval(f'_recClipName({json.dumps(qso1)})')
    name2 = ctx.eval(f'_recClipName({json.dumps(qso2)})')
    assert name1 == name2   # le bug : collision malgré des QSO distincts


def test_nom_de_fichier_inclut_les_secondes_pas_de_collision():
    """Sur le code actuel : les mêmes deux QSO produisent des noms distincts
    (secondes dérivées de qso.id, précision milliseconde)."""
    ctx = _make_ctx()
    qso1 = {'call': 'F4ABC', 'band': '144', 'date': '20260723', 'time': '14:32',
            'id': 1784817125000}   # 2026-07-23T14:32:05Z
    qso2 = {'call': 'F4ABC', 'band': '144', 'date': '20260723', 'time': '14:32',
            'id': 1784817170000}   # 2026-07-23T14:32:50Z
    name1 = ctx.eval(f'_recClipName({json.dumps(qso1)})')
    name2 = ctx.eval(f'_recClipName({json.dumps(qso2)})')
    assert name1 != name2
    assert name1 == 'F4ABC_144_20260723_143205.wav'
    assert name2 == 'F4ABC_144_20260723_143250.wav'


# ─── Problème 4 (MEDIUM) : encodage WAV jamais réellement exécuté ──────────
# _encodeWavFromBuffers()/_floatChannelsToWav() ne dépendent que d'ArrayBuffer/
# DataView/Float32Array (standard ECMAScript, pas de DOM) — exécutables tels
# quels dans V8. Seul `Blob` est une API navigateur, déjà shimmée ci-dessus.

def test_encodage_wav_reel_troncature_entete_et_interleaving():
    """Exécute pour de vrai _encodeWavFromBuffers/_floatChannelsToWav : vérifie
    l'en-tête RIFF/WAVE, la troncature aux dernières `maxSeconds` (queue des
    segments les plus anciens conservée, comme documenté), ET l'entrelacement
    stéréo correct (canal 0 / canal 1 alternés par trame)."""
    ctx = _make_ctx()
    ctx.eval(r"""
    function makeBuffer(sampleRate, channelsData){
      return {
        sampleRate: sampleRate,
        numberOfChannels: channelsData.length,
        length: channelsData[0].length,
        getChannelData: function(ch){ return channelsData[ch] || channelsData[0]; }
      };
    }
    function inspectWav(blob){
      var buf = blob.parts[0];
      var dv = new DataView(buf);
      function s4(off){ return String.fromCharCode(dv.getUint8(off), dv.getUint8(off+1), dv.getUint8(off+2), dv.getUint8(off+3)); }
      var numChannels = dv.getUint16(22, true);
      var sampleAt = function(frame, ch){ return dv.getInt16(44 + (frame*numChannels+ch)*2, true); };
      return JSON.stringify({
        riff: s4(0), wave: s4(8), fmtTag: s4(12), dataTag: s4(36),
        audioFormat: dv.getUint16(20, true),
        numChannels: numChannels, sampleRate: dv.getUint32(24, true),
        bitsPerSample: dv.getUint16(34, true), dataSize: dv.getUint32(40, true),
        totalBytes: buf.byteLength, type: blob.type,
        s0_0: sampleAt(0,0), s0_1: sampleAt(0,1),
        s10999_0: sampleAt(10999,0), s10999_1: sampleAt(10999,1),
        s11000_0: sampleAt(11000,0), s11000_1: sampleAt(11000,1),
        s15999_0: sampleAt(15999,0), s15999_1: sampleAt(15999,1)
      });
    }
    // Segment le plus ANCIEN : 30000 échantillons (dépasse largement la fenêtre
    // voulue -> seule sa QUEUE doit être conservée).
    var older = makeBuffer(8000, [new Float32Array(30000).fill(0.5), new Float32Array(30000).fill(-0.25)]);
    // Segment le plus RÉCENT : 5000 échantillons, entièrement conservé.
    var newer = makeBuffer(8000, [new Float32Array(5000).fill(-0.75), new Float32Array(5000).fill(0.9)]);
    var wav = _encodeWavFromBuffers([older, newer], 2);   // maxSeconds=2 -> 16000 échantillons @8000Hz
    var __result = inspectWav(wav);
    """)
    result = json.loads(ctx.eval('__result'))

    assert result['riff'] == 'RIFF'
    assert result['wave'] == 'WAVE'
    assert result['fmtTag'] == 'fmt '
    assert result['dataTag'] == 'data'
    assert result['audioFormat'] == 1        # PCM
    assert result['numChannels'] == 2
    assert result['sampleRate'] == 8000
    assert result['bitsPerSample'] == 16
    assert result['type'] == 'audio/wav'

    # 16000 échantillons/canal, 2 canaux, 16 bits = 2 octets -> 64000 octets de data.
    assert result['dataSize'] == 16000 * 2 * 2
    assert result['totalBytes'] == 44 + result['dataSize']

    # Troncature : les 11000 premières trames viennent de la QUEUE du segment
    # ancien (0.5/-0.25), les 5000 dernières du segment récent (-0.75/0.9) —
    # PCM16 exact (valeurs choisies pour une conversion sans arrondi ambigu).
    assert result['s0_0'] == int(0.5 * 0x7FFF)      # 16383
    assert result['s0_1'] == int(-0.25 * 0x8000)    # -8192
    assert result['s10999_0'] == int(0.5 * 0x7FFF)
    assert result['s10999_1'] == int(-0.25 * 0x8000)
    assert result['s11000_0'] == int(-0.75 * 0x8000)   # -24576 : bascule vers le segment récent
    assert result['s11000_1'] == int(0.9 * 0x7FFF)     # 29490
    assert result['s15999_0'] == int(-0.75 * 0x8000)
    assert result['s15999_1'] == int(0.9 * 0x7FFF)
