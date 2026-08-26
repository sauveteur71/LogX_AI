# -*- coding: utf-8 -*-
"""Voice keyer — fuite du flux micro au changement de slot (audit 26/08).

voiceRecord(key) : si un AUTRE slot enregistre déjà (l'opérateur clique REC sur
un second slot sans arrêter le premier), l'ancien code créait un nouveau
MediaRecorder en ÉCRASANT _mediaRec/_recSlot SANS arrêter l'ancien flux ->
micro laissé ouvert (fuite) + les chunks de l'ancien se mélangeaient au nouveau
slot. Ce test exécute la VRAIE fonction voiceRecord (extraite du fichier) sous
stubs, et vérifie qu'au changement de slot le flux du PREMIER enregistrement
est bien fermé (tracks stop()).

py_mini_racer draine les microtâches ENTRE les eval : on lance voiceRecord dans
un eval, puis on relit l'état dans un eval suivant (les await/onstop sont alors
résolus)."""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_voice_keyer.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _extraire_voiceRecord():
    """Extrait le texte EXACT de la fonction voiceRecord (pas un mannequin)."""
    src = open(JS, encoding='utf-8').read()
    i = src.index('async function voiceRecord(key){')
    j = src.index('{', i)
    prof = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            prof += 1
        elif src[k] == '}':
            prof -= 1
            if prof == 0:
                return src[i:k + 1]
    raise AssertionError('accolade fermante de voiceRecord introuvable')


_STUBS = r"""
  var _mediaRec = null, _recSlot = null, _recChunks = [], _vkStream = null;
  var _audioCtx = null;
  var _streams = [], _stopped = {}, _sid = 0;
  function _makeStream(){
    var id = ++_sid;
    var tracks = [{ stop: function(){ _stopped[id] = true; } }];
    var s = { _id: id, getTracks: function(){ return tracks; } };
    _streams.push(s); return s;
  }
  var navigator = { mediaDevices: { getUserMedia: function(){ return Promise.resolve(_makeStream()); } } };
  function MediaRecorder(stream){
    this.stream = stream; this.mimeType = 'audio/webm';
    this.start = function(){};
    // Le vrai MediaRecorder appelle onstop de façon ASYNCHRONE : on l'imite via
    // une microtâche (drainée au prochain eval), c'est là tout l'enjeu du bug.
    this.stop = function(){ var self = this; Promise.resolve().then(function(){ if(self.onstop) self.onstop(); }); };
  }
  function _elt(){ return { textContent: '', style: {} }; }
  var document = { getElementById: function(){ return _elt(); } };
  function notify(){}
  function trF(s){ return s; }
  function so2rRafraichir(){}
  function voiceRefreshSlots(){ return Promise.resolve(); }
  function _floatChannelsToWav(){ return new Uint8Array(0); }
  function _blobToBase64(){ return Promise.resolve(''); }
  function Blob(){}
  var fetch = function(){ return Promise.resolve({ json: function(){ return Promise.resolve({ ok: true }); } }); };
"""


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_STUBS)
    ctx.eval(_extraire_voiceRecord())
    return ctx


def test_changer_de_slot_ferme_le_flux_du_premier():
    ctx = _ctx()
    ctx.eval("voiceRecord('F1');")          # démarre F1 (await drainé en fin d'eval)
    assert ctx.eval("String(_recSlot)") == 'F1'
    assert ctx.eval("_streams.length") == 1

    ctx.eval("voiceRecord('F2');")          # clic REC sur F2 SANS arrêter F1
    # Le flux du PREMIER enregistrement doit être fermé (pas de micro fantôme).
    assert ctx.eval("_stopped[_streams[0]._id] === true"), \
        "fuite : le flux micro du premier slot n'a pas été fermé au changement de slot"
    # Le nouvel enregistrement est bien en place et non écrasé par l'onstop de l'ancien.
    assert ctx.eval("String(_recSlot)") == 'F2'
    assert ctx.eval("_mediaRec !== null")


def test_deuxieme_clic_meme_slot_arrete_normalement():
    """Non-régression : recliquer le MÊME slot arrête proprement (2e clic = stop)."""
    ctx = _ctx()
    ctx.eval("voiceRecord('F1');")
    ctx.eval("voiceRecord('F1');")          # 2e clic même slot -> stop -> onstop
    assert ctx.eval("_stopped[_streams[0]._id] === true")
    assert ctx.eval("_mediaRec === null")   # onstop a bien remis à zéro
