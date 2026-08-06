# -*- coding: utf-8 -*-
"""Codec FT8 (logx_ft8_codec.js) — empaquetage/CRC/LDPC/Costas.

Comme le décodeur RTTY (test_rtty_decodeur.py) : le protocole FT8 est fixé
par la norme (pas par nous), donc les vecteurs de test viennent directement
de l'implémentation de référence open-source kgoba/ft8_lib (licence MIT) —
voir en-tête de logx_ft8_codec.js pour la source exacte de chaque table.

Les 15 indicatifs et le tableau de grilles/reports ci-dessous sont recopiés
tels quels depuis test/test.c de kgoba/ft8_lib (fonction main()) : c'est le
test croisé QUE ft8_lib fait tourner sur SA PROPRE implémentation C. Le faire
tourner ici, sur le portage JS, teste exactement la même surface — bien plus
fort qu'un vecteur isolé.

Le type 4 (indicatifs non standard, ex. "EA8/G5LSI") n'est PAS implémenté
dans ce portage (portée volontairement limitée aux types 1/2 standard et 0.0
texte libre pour cette première version) : test_msg() de test.c qui exerce
ce cas est donc volontairement absent d'ici.

PIÈGE ÉVITÉ (trouvé en le faisant) : py_mini_racer renvoie un objet/tableau
JS sous forme de JSObject opaque, PAS un dict/list Python — un premier jet de
ce fichier comparait `moteur.eval('FT8_COSTAS_PATTERN') == [3,1,4,0,6,5,2]`
ou indexait `d['callTo']` directement, ce qui plante systématiquement
(TypeError: 'JSObject' object is not subscriptable), sur ~4670 tests d'un
coup — à ne PAS confondre avec un vrai bug de codec. Toujours faire
transiter les objets/tableaux par JSON.stringify() côté JS + json.loads()
côté Python (fonction _eval_json ci-dessous), comme test_rtty_decodeur.py
le fait déjà pour ses propres retours composites.

PIÈGE ÉVITÉ #2 : test.c contient un test3() avec un vecteur CRC "attendu
0x0708" — mais test1/test2/test3 sont entièrement dans un bloc /* commenté
*/, appellent des fonctions qui n'existent plus dans l'API actuelle
(packmsg/unpack/encode174, remplacées par ftx_message_encode_std/etc.), et
calculent le CRC sur 76 bits alors que le pipeline actuel (ftx_add_crc) en
utilise 82 — c'est un vecteur d'une VERSION ANTÉRIEURE du protocole, mort de
code, pas une référence valide pour crc.c actuel. Volontairement absent
d'ici ; la validation du CRC passe par les tests de bout en bout ci-dessous
(un message altéré doit être rejeté, un message valide doit survivre).
"""
import json
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_ft8_codec.js')

py_mini_racer = pytest.importorskip('py_mini_racer')


@pytest.fixture(scope='module')
def moteur():
    ctx = py_mini_racer.MiniRacer()
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def _eval_json(moteur, expr):
    """Évalue une expression JS renvoyant un objet/tableau/null et le
    ramène en valeur Python native via JSON — jamais de JSObject opaque."""
    return json.loads(moteur.eval(f'JSON.stringify(({expr}) ?? null)'))


# ─── Costas / Gray : cohérence interne ───────────────────────────────────────

def test_costas_pattern_exact(moteur):
    assert _eval_json(moteur, 'FT8_COSTAS_PATTERN') == [3, 1, 4, 0, 6, 5, 2]


def test_gray_map_exact(moteur):
    assert _eval_json(moteur, 'FT8_GRAY_MAP') == [0, 1, 3, 2, 5, 6, 4, 7]


def test_gray_map_inverse_est_une_bijection(moteur):
    moteur.eval("""
    function verifieBijection(){
      for(var v=0; v<8; v++){
        var tone = FT8_GRAY_MAP[v];
        if(FT8_GRAY_MAP_INV[tone] !== v) return false;
      }
      return true;
    }""")
    assert moteur.eval('verifieBijection()') is True


# ─── LDPC : auto-cohérence encode -> vérif de parité ─────────────────────────
# Un encodage correct DOIT satisfaire les 83 équations de parité — si la
# matrice génératrice ou les tables Nm/Mn sont mal indexées, ça ne colle
# JAMAIS par hasard (83 équations indépendantes).

def test_ldpc_encode_satisfait_toujours_la_parite(moteur):
    # Math.imul() est INDISPENSABLE ici : `s*1103515245` en JS perd des bits
    # de précision dès que `s` dépasse ~2^24 (le produit dépasse
    # Number.MAX_SAFE_INTEGER en float64) — trouvé en debuggant un faux échec
    # où la graine 1 dégénérait silencieusement en 91 bits à zéro, ce qui a
    # légitimement déclenché le refus de bp_decode de converger vers le mot
    # de code tout-zéro (comportement voulu, voir ft8BpDecode). Math.imul()
    # fait la multiplication en 32 bits avec un vrai wraparound, comme en C.
    moteur.eval("""
    function essaiAleatoire(graine){
      var s = graine;
      var bits91 = [];
      for(var i=0;i<91;i++){ s=(Math.imul(s,1103515245)+12345)&0x7fffffff; bits91.push(s&1); }
      var codeword = ft8LdpcEncode(bits91);
      return ft8LdpcCheckErrors(codeword);
    }""")
    for graine in range(1, 30):
        erreurs = moteur.eval(f'essaiAleatoire({graine})')
        assert erreurs == 0, f'graine {graine} : {erreurs} équations de parité en échec'


def test_ldpc_encode_puis_decode_recupere_les_bits(moteur):
    """Décodage à décision dure (LLR = +/-4 selon le bit) : doit toujours
    retomber sur exactement les mêmes 91 bits sur un canal sans bruit."""
    moteur.eval("""
    function essaiRoundTrip(graine){
      var s = graine;
      var bits91 = [];
      for(var i=0;i<91;i++){ s=(Math.imul(s,1103515245)+12345)&0x7fffffff; bits91.push(s&1); }
      var codeword = ft8LdpcEncode(bits91);
      var llr = codeword.map(function(b){ return b ? 4.0 : -4.0; });
      var res = ft8BpDecode(llr, 20);
      if(res.errors !== 0) return {ok:false, reason:'errors='+res.errors};
      for(var i=0;i<91;i++){
        if(res.bits[i] !== bits91[i]) return {ok:false, reason:'bit '+i+' differe'};
      }
      return {ok:true};
    }""")
    for graine in range(1, 15):
        res = _eval_json(moteur, f'essaiRoundTrip({graine})')
        assert res['ok'], f'graine {graine} : {res.get("reason")}'


# ─── Empaquetage/dépaquetage standard (type 1/2) — cross-product de test.c ──

CALLSIGNS = ['YL3JG', 'W1A', 'W1A/R', 'W5AB', 'W8ABC', 'DE6ABC', 'DE6ABC/R',
             'DE7AB', 'DE9A', '3DA0X', '3DA0XYZ', '3DA0XYZ/R', '3XZ0AB',
             '3XZ0A', 'CQ1CQ']
TOKENS = ['CQ', 'QRZ', 'CQ 123', 'CQ 000', 'CQ POTA', 'CQ SA', 'CQ O', 'CQ ASD']
GRIDS = ['KO26', 'RR99', 'AA00', 'RR09', 'AA01', 'RRR', 'RR73', '73',
         'R+10', 'R+05', 'R-12', 'R-02', '+10', '+05', '-02', '-02', '']


def _round_trip_std(moteur, call_to, call_de, extra):
    return _eval_json(moteur, f"""
    (function(){{
      var payload = ft8EncodeStdMessage({json.dumps(call_to)}, {json.dumps(call_de)}, {json.dumps(extra)}, null);
      if(!payload) return null;
      var d = ft8DecodeStdMessage(payload, null);
      return d;
    }})()""")


@pytest.mark.parametrize('call_to', CALLSIGNS)
@pytest.mark.parametrize('call_de', CALLSIGNS)
@pytest.mark.parametrize('extra', GRIDS)
def test_std_message_callsign_callsign_grid(moteur, call_to, call_de, extra):
    d = _round_trip_std(moteur, call_to, call_de, extra)
    assert d is not None, f'encodage échoué pour {call_to}/{call_de}/{extra}'
    assert d['callTo'] == call_to
    assert d['callDe'] == call_de
    assert d['extra'] == extra


@pytest.mark.parametrize('token', TOKENS)
@pytest.mark.parametrize('call_de', CALLSIGNS)
@pytest.mark.parametrize('extra', ['KO26', 'RRR', 'RR73', '73', 'R+10', '-02', ''])
def test_std_message_token_callsign_grid(moteur, token, call_de, extra):
    d = _round_trip_std(moteur, token, call_de, extra)
    assert d is not None, f'encodage échoué pour {token}/{call_de}/{extra}'
    assert d['callTo'] == token
    assert d['callDe'] == call_de
    assert d['extra'] == extra


# ─── Texte libre (type 0.0) ───────────────────────────────────────────────────

@pytest.mark.parametrize('texte', ['TNX BOB 73 GL', 'HELLO WORLD', '73', '', 'A B C D E'])
def test_texte_libre_aller_retour(moteur, texte):
    r = moteur.eval(f"""
    (function(){{
      var p = ft8EncodeFreeText({json.dumps(texte.upper())});
      if(!p) return null;
      return ft8DecodeFreeText(p);
    }})()""")
    assert r == texte.upper().rstrip()


# ─── Pipeline complet : texte -> 79 symboles -> texte (sans bruit) ───────────
# QSO documenté dans l'article QEX 2020 (Franke/Somerville/Taylor), section
# exemple : CQ K1JT FN20 / K1JT K9AN EN50 / K9AN K1JT -10 / K1JT K9AN R-12 /
# K9AN K1JT RRR / K1JT K9AN 73.

@pytest.mark.parametrize('texte', [
    'CQ K1JT FN20',
    'K1JT K9AN EN50',
    'K9AN K1JT -10',
    'K1JT K9AN R-12',
    'K9AN K1JT RRR',
    'K1JT K9AN 73',
])
def test_pipeline_complet_texte_vers_symboles_vers_texte(moteur, texte):
    r = _eval_json(moteur, f"""
    (function(){{
      var enc = ft8EncodeMessage({json.dumps(texte)}, null);
      if(!enc) return {{ok:false, reason:'encode a echoue'}};
      if(enc.symbols.length !== 79) return {{ok:false, reason:'79 symboles attendus, eu '+enc.symbols.length}};
      var dec = ft8DecodeSymbols(enc.symbols, null, 20);
      return {{ok: dec === {json.dumps(texte)}, decode: dec}};
    }})()""")
    assert r['ok'], f'{texte!r} -> {r.get("decode")!r}'


def test_symboles_de_synchro_costas_presents_trois_fois(moteur):
    r = _eval_json(moteur, """
    (function(){
      var enc = ft8EncodeMessage('CQ K1JT FN20', null);
      var s = enc.symbols;
      var ok1 = JSON.stringify(s.slice(0,7)) === JSON.stringify(FT8_COSTAS_PATTERN);
      var ok2 = JSON.stringify(s.slice(36,43)) === JSON.stringify(FT8_COSTAS_PATTERN);
      var ok3 = JSON.stringify(s.slice(72,79)) === JSON.stringify(FT8_COSTAS_PATTERN);
      return {ok1: ok1, ok2: ok2, ok3: ok3};
    })()""")
    assert r['ok1'] and r['ok2'] and r['ok3']


# ─── CRC : un message altéré doit être rejeté, pas décodé silencieusement ────

def test_decode_rejette_un_message_corrompu(moteur):
    r = moteur.eval("""
    (function(){
      var enc = ft8EncodeMessage('CQ K1JT FN20', null);
      var s = enc.symbols.slice();
      // Corrompt plusieurs symboles de données (hors synchro) pour garantir
      // un dépassement de la capacité de correction du LDPC.
      for(var i=10; i<34; i++) s[i] = (s[i] + 4) % 8;
      return ft8DecodeSymbols(s, null, 20);
    })()""")
    assert r is None
