# -*- coding: utf-8 -*-
"""Décodeur SSTV (Martin/Scottie/Robot/PD) dans le navigateur.

Activations, ISS (PD120), dimanches SSTV : jusqu'ici il fallait ouvrir MMSSTV
ou RX-SSTV à côté de LogX AI. Ici le décodage se fait dans la page, comme le
CW et le RTTY : rien à installer.

POURQUOI CES TESTS SONT REPRÉSENTATIFS, comme ceux du RTTY : la SSTV est
générée par machine à timing FIXE (spec N7CXI — chaque pixel a sa fenêtre
temporelle à la microseconde près). Un signal synthétique est donc un vrai
signal SSTV. On encode une image de référence, on la décode, et on mesure
l'erreur moyenne par pixel (MAE) — le décodeur est exercé de bout en bout,
démodulation FM et détection VIS comprises, sans radio.

Le MAE n'est jamais nul : le filtre du démodulateur adoucit les transitions
entre pixels, et les modes Robot/PD sous-échantillonnent la chrominance.
L'image de test est un dégradé lisse, l'erreur admise est de quelques niveaux
sur 255.

Ce que ces tests NE prouvent PAS : le comportement sous QRM/QSB réel et les
signaux hors spec de certains logiciels exotiques. Ça reste à éprouver sur
l'air.

Fréquence d'échantillonnage des tests : 11025 Hz (Nyquist 5512 Hz, largement
au-dessus des 2300 Hz du blanc). Une image Martin M1 dure 114 s : à 44,1 kHz
chaque aller-retour manipulerait 5 millions d'échantillons, à 11025 c'est
4 fois moins pour une couverture identique.
"""
import json
import os
import re

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_sstvdecoder.js')
LOGBOOK_JS = os.path.join(CONCOURS, 'logx_logbook.js')
LOGBOOK_HTML = os.path.join(CONCOURS, 'logx_logbook.html')
CONFIG_HTML = os.path.join(CONCOURS, 'logx_configuration.html')

py_mini_racer = pytest.importorskip('py_mini_racer')

FS = 11025

# Tous les modes de la table — un oubli ici laisserait un mode non testé.
TOUS_MODES = ['M1', 'M2', 'S1', 'S2', 'SDX', 'R36', 'R72',
              'PD50', 'PD90', 'PD120', 'PD160', 'PD180', 'PD240', 'PD290']


@pytest.fixture(scope='module')
def moteur():
    ctx = py_mini_racer.MiniRacer()
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    ctx.eval("""
    // Dégradé lisse en x (rouge), en y (vert) et diagonal inversé (bleu) :
    // chaque pixel a une valeur unique, une erreur de timing (ligne décalée,
    // canal permuté) fait donc EXPLOSER le MAE au lieu de passer inaperçue
    // comme sur une mire à aplats.
    function imageTestSstv(l, h){
      var px = new Uint8ClampedArray(l*h*3);
      for(var y=0;y<h;y++) for(var x=0;x<l;x++){
        var i=(y*l+x)*3;
        var r=Math.round(x*255/(l-1)), g=Math.round(y*255/(h-1));
        px[i]=r; px[i+1]=g; px[i+2]=Math.round(255-(r+g)/2);
      }
      return px;
    }
    // Bruit blanc reproductible (générateur à graine) : un échec se rejoue.
    function avecBruitSstv(sig, niveau, graine){
      var s = graine || 1, out = new Float32Array(sig.length);
      for(var i=0;i<sig.length;i++){
        s = (s*1103515245 + 12345) & 0x7fffffff;
        out[i] = sig[i] + ((s/0x7fffffff)*2-1)*niveau;
      }
      return out;
    }
    // Erreur absolue moyenne par composante, sur les lignes effectivement
    // émises (les signaux tronqués n'émettent pas la dernière ligne).
    function maeSstv(dec, px, l, lignes){
      var s=0, n=0;
      for(var y=0;y<lignes;y++) for(var x=0;x<l;x++){
        var i=y*l+x;
        s += Math.abs(dec.rgba[i*4]-px[i*3])
           + Math.abs(dec.rgba[i*4+1]-px[i*3+1])
           + Math.abs(dec.rgba[i*4+2]-px[i*3+2]);
        n += 3;
      }
      return s/n;
    }
    function allerRetourSstv(nomMode, optsEnc, optsDec){
      optsEnc = optsEnc || {}; optsDec = optsDec || {};
      var m = SSTV_MODES_PAR_NOM[nomMode];
      var px = imageTestSstv(m.largeur, m.hauteur);
      var sig = sstvEncodeSamples(Object.assign(
        {mode: nomMode, pixels: px, sampleRate: %d}, optsEnc));
      if(optsEnc.bruit) sig = avecBruitSstv(sig, optsEnc.bruit, 7);
      var d = sstvDecodeSamples(sig, Object.assign({sampleRate: %d}, optsDec));
      var r = d.resume();
      r.mae = (r.mode === nomMode && r.lignesEmises > 0)
            ? maeSstv(d, px, m.largeur, r.lignesEmises) : null;
      return r;
    }""" % (FS, FS))
    return ctx


def _aller_retour(moteur, mode, enc=None, dec=None):
    # JSON.stringify côté JS : py_mini_racer renvoie les objets JS sous forme
    # de poignées opaques, pas de dicts.
    return json.loads(moteur.eval('JSON.stringify(allerRetourSstv(%s, %s, %s))' % (
        json.dumps(mode), json.dumps(enc or {}), json.dumps(dec or {}))))


# ─── Détection VIS et tables de timing ───────────────────────────────────────

@pytest.mark.parametrize('mode', TOUS_MODES)
def test_vis_et_timing_de_chaque_mode(moteur, mode):
    """Signal tronqué à 8 balayages : suffisant pour vérifier que l'en-tête
    VIS identifie le bon mode ET que la table de timing est juste — une durée
    de balayage fausse de 1 % décale les pixels et fait exploser le MAE."""
    r = _aller_retour(moteur, mode, {'lignes': 8})
    assert r['mode'] == mode
    assert r['lignesEmises'] >= 6
    assert r['mae'] is not None and r['mae'] < 15, 'MAE %s : %s' % (mode, r['mae'])


# ─── Aller-retour complet ────────────────────────────────────────────────────

@pytest.mark.parametrize('mode', ['M1', 'S1', 'R36', 'PD90'])
def test_une_image_complete_se_decode_fidelement(moteur, mode):
    """Image entière (256 ou 240 lignes) : couvre une famille de chaque type
    de balayage — Martin (synchro en tête), Scottie (synchro au milieu),
    Robot 36 (chroma alternée) et PD (deux lignes par balayage)."""
    r = _aller_retour(moteur, mode)
    assert r['mode'] == mode
    assert r['complete'] is True
    assert r['lignesEmises'] == r['hauteur']
    assert r['mae'] < 12, 'MAE %s : %s' % (mode, r['mae'])


def test_la_derive_d_horloge_est_compensee(moteur):
    """Le décodeur croit à une fréquence d'échantillonnage fausse de 0,03 %
    (écart courant entre deux cartes son grand public). Sans le recalage sur
    les impulsions de synchro, l'erreur cumulée atteindrait 34 ms en fin
    d'image Martin M1 — 7 fois la largeur d'une impulsion — et l'image serait
    penchée au point d'être illisible (MAE > 60 sur le dégradé)."""
    r = _aller_retour(moteur, 'M1', None, {'sampleRate': FS * (1 - 3e-4)})
    assert r['mode'] == 'M1'
    assert r['complete'] is True
    assert r['mae'] < 20, 'MAE avec dérive : %s' % r['mae']


def test_le_bruit_n_empeche_pas_le_decodage(moteur):
    """Bruit blanc à 30 % de l'amplitude du signal : le VIS doit toujours
    accrocher et l'image rester exploitable (le filtre I/Q du démodulateur
    moyenne le bruit sur chaque fenêtre de pixel)."""
    r = _aller_retour(moteur, 'R36', {'bruit': 0.15})
    assert r['mode'] == 'R36'
    assert r['complete'] is True
    assert r['mae'] < 20, 'MAE avec bruit : %s' % r['mae']


# ─── Rejet des en-têtes invalides ────────────────────────────────────────────

def test_un_code_vis_inconnu_est_rejete(moteur):
    """Code VIS 1 : parité correcte mais mode absent de la table. Le décodeur
    doit rester en attente au lieu d'inventer une image avec un timing
    quelconque."""
    r = _aller_retour(moteur, 'M1', {'lignes': 2, 'visCode': 1})
    assert r['mode'] is None
    assert r['vis'] == 1          # le code a bien été LU, puis refusé

def test_une_parite_fausse_est_rejetee(moteur):
    """Bit de parité inversé : c'est la protection contre un bit de mode lu
    de travers dans le bruit — accepter l'en-tête ferait décoder 2 minutes de
    garbage avec le timing du mauvais mode."""
    r = _aller_retour(moteur, 'M1', {'lignes': 2, 'pariteFausse': True})
    assert r['mode'] is None
    assert r['vis'] is None       # jamais validé, donc jamais retenu


# ─── Intégration UI : chaque décodeur n'apparaît que dans SON mode ──────────
# Vérifications par lecture de source (même modèle que
# test_cw_panel_consolidation.py) : demande utilisateur explicite — « pas la
# peine d'afficher CW et SSTV si pas sélectionnés dans les modes ».

def _lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


def test_updateKeyerPanels_pilote_les_panneaux_cw_et_sstv():
    """updateKeyerPanels() doit décider de la visibilité des DEUX panneaux
    décodeurs : cwPanel en mode CW (avant, il restait affiché dans tous les
    modes sauf RTTY) — ou via le forçage manuel cwPanelForcedOpen (bouton
    dédié du band map, F4GLD 05/08/2026 : accès exceptionnel au décodeur CW
    même si CW n'est pas dans les modes activés) —, sstvPanel seulement en
    mode SSTV."""
    src = _lire(LOGBOOK_JS)
    m = re.search(r'function\s+updateKeyerPanels\s*\([^)]*\)\s*\{(.*?)\n\}', src, re.S)
    assert m, 'updateKeyerPanels() introuvable'
    corps = m.group(1)
    assert 'sstvPanel' in corps
    assert 'cwPanel' in corps
    assert re.search(r'cwDec\.style\.display\s*=\s*\(?\s*cw\b', corps), \
        'cwPanel doit suivre le mode CW (éventuellement OR forçage manuel), pas « tout sauf RTTY »'


def test_panneaux_decodeurs_masques_par_defaut_dans_le_html():
    """Les panneaux partent masqués dans le HTML : c'est updateKeyerPanels()
    (appelé dès renderModeButtons) qui les montre dans leur mode. Sans ça, un
    panneau flasherait à l'écran au chargement dans les modes phonie."""
    html = _lire(LOGBOOK_HTML)
    for panneau in ('cwPanel', 'sstvPanel'):
        m = re.search(r'<div[^>]*id="%s"[^>]*>' % panneau, html)
        assert m, panneau + ' introuvable dans le HTML'
        assert 'display:none' in m.group(0), panneau + ' doit partir masqué'


def test_le_mode_sstv_est_declare_partout():
    """Le mode SSTV doit exister dans les trois endroits qui se répondent :
    la case de la page CONFIG (mode_sstv), la table MODE_TOGGLE_KEY du
    logbook, et la liste des modes proposables du sélecteur — en oublier un
    rendrait le décodeur inaccessible sans qu'aucune erreur n'apparaisse."""
    assert 'data-key="mode_sstv"' in _lire(CONFIG_HTML)
    src = _lire(LOGBOOK_JS)
    assert re.search(r"'SSTV':\s*'mode_sstv'", src)
    assert re.search(r"'RTTY','SSTV'\]", src), \
        'SSTV absent de la liste des modes du sélecteur (renderModeButtons)'


# ─── Conversions couleur ─────────────────────────────────────────────────────

def test_la_conversion_ycc_est_reversible(moteur):
    """RGB → YCrCb → RGB (coefficients BT.601 de la spec N7CXI) : l'erreur
    d'arrondi doit rester sous 2 niveaux sur 255 — au-delà, les couleurs des
    modes Robot/PD dérivent visiblement (teint verdâtre classique quand les
    matrices ne sont pas inverses l'une de l'autre)."""
    err = moteur.eval("""
    (function(){
      var pire = 0;
      var essais = [[0,0,0],[255,255,255],[255,0,0],[0,255,0],[0,0,255],
                    [128,64,200],[10,250,30],[200,200,10],[77,148,255]];
      for(var i=0;i<essais.length;i++){
        var e = essais[i];
        var ycc = sstvRgbVersYcc(e[0], e[1], e[2]);
        var rgb = sstvYccVersRgb(ycc[0], ycc[1], ycc[2]);
        for(var c=0;c<3;c++) pire = Math.max(pire, Math.abs(rgb[c]-e[c]));
      }
      return pire;
    })()""")
    assert err <= 2, 'erreur YCC max : %s' % err
