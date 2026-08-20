# -*- coding: utf-8 -*-
"""Décimation audio avant décodage FT8 : gain réel, sans perte de décodage.

POURQUOI CE CHANTIER. F4GLD, 18/08/2026 : « le waterfall continue à se figer »,
et le diagnostic affichait « 81 resynchro. audio ». Les deux ont la même cause.

ft8DecodeAudioAll est appelée de façon SYNCHRONE sur le thread principal à
chaque fin de créneau de 15 s. Pendant toute sa durée, le navigateur ne peut ni
redessiner la cascade, ni exécuter le ScriptProcessorNode qui collecte l'audio.
Les blocs sautés font dériver l'horloge du tampon, que pousserEchantillons doit
alors reprendre sur l'horloge réelle — d'où le compteur qui grimpe. Le décodage
se sabotait lui-même : plus il durait, plus il perdait d'audio, donc plus il
devait resynchroniser.

Or le signal FT8 tient tout entier sous 3 kHz, alors que la carte son livre à
48 kHz : les trois quarts des échantillons ne portaient AUCUNE information
utile et coûtaient pourtant leur temps plein.

CE QUE CES TESTS EXIGENT, dans cet ordre d'importance :
  1. AUCUNE perte de décodage — une accélération qui perd des stations n'en est
     pas une ;
  2. le DT reste juste (c'est lui qui dit à l'opérateur si son horloge dérive) ;
  3. le filtre anti-repliement fait réellement son travail ;
  4. le gain est réel.
"""
import json
import os
import time

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DSP = os.path.join(CONCOURS, 'logx_ft8_dsp.js')
CODEC = os.path.join(CONCOURS, 'logx_ft8_codec.js')
FT8_HTML = os.path.join(CONCOURS, 'logx_ft8.html')

py_mini_racer = pytest.importorskip('py_mini_racer')

SR_CARTE = 48000          # cadence des codecs USB de la quasi-totalité des postes
MESSAGES = ['CQ F4ABC JN18', 'F4GLD F4ABC -07', 'DL1XYZ F4GLD RRR']
TONS = [800, 1500, 2200]
DT_VRAIS = [0.0, 0.3, -0.4]
MARGE_S = 1.5             # ce que extraireFenetre ajoute de chaque côté


def _lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return f.read()


@pytest.fixture(scope='module')
def ctx():
    c = py_mini_racer.MiniRacer()
    c.eval(_lire(CODEC))
    c.eval(_lire(DSP))
    c.eval('''
      var HT = ft8CreateHashTable();
      // Bruit REPRODUCTIBLE : générateur congruentiel, jamais Math.random —
      // une mesure qui change à chaque exécution ne se compare à rien, et un
      // test qui échoue une fois sur dix finit par être ignoré.
      function __bruiteur(graine){
        var etat = graine >>> 0;
        return function(){
          etat = (etat * 1664525 + 1013904223) >>> 0;
          return (etat / 4294967296) * 2 - 1;
        };
      }
      function fabriquerFenetre(messages, sr, tons, dts, bruit, graine, parasiteHz){
        var n = Math.round(16.5 * sr);
        var buf = new Float32Array(n);
        var alea = __bruiteur(graine);
        for(var i = 0; i < n; i++) buf[i] = alea() * bruit;
        if(parasiteHz){
          // Un sifflement HORS bande utile : c'est lui que le filtre
          // anti-repliement doit écarter. Sans filtre il se replierait dans la
          // bande FT8 et deviendrait indissociable du signal.
          for(var i2 = 0; i2 < n; i2++){
            buf[i2] += 0.9 * Math.sin(2 * Math.PI * parasiteHz * i2 / sr);
          }
        }
        for(var m = 0; m < messages.length; m++){
          var enc = ft8EncodeMessage(messages[m], HT);
          if(!enc) throw new Error('non encodable : ' + messages[m]);
          var w = ft8SynthesizeGfsk(enc.symbols, {sampleRate: sr, toneHz0: tons[m]});
          var off = Math.round((1.5 + dts[m]) * sr);
          for(var k = 0; k < w.length && off + k < n; k++) buf[off + k] += w[k] * 0.5;
        }
        return buf;
      }
      function decoder(samples, sr){
        var ht = ft8CreateHashTable();
        var r = ft8DecodeAudioAll(samples, sr, ht, {centerSample: 1.5 * sr});
        return JSON.stringify(r.map(function(x){
          return {texte: x.text, dt: (x.startSample / sr) - 1.5,
                  freq: x.freqHz};
        }));
      }
    ''')
    return c


def _decoder(ctx, expr_samples, sr):
    return json.loads(ctx.eval('decoder(%s, %s)' % (expr_samples, sr)))


# ─── 1. Le facteur de décimation ────────────────────────────────────────────

@pytest.mark.parametrize('entree,attendu', [
    (48000, 4),      # le cas de très loin le plus courant : 12 kHz pile
    (96000, 8),      # 12 kHz pile
    (44100, 3),      # 14,7 kHz — rapport non entier vers 12 kHz, on ne force pas
    (24000, 2),
    (12000, 1),      # déjà à la bonne cadence : ne rien faire
    (8000, 1),       # en dessous : surtout ne pas décimer davantage
])
def test_le_facteur_est_entier_et_ne_descend_jamais_sous_12_khz(ctx, entree, attendu):
    """On décime par un facteur ENTIER, jamais par rééchantillonnage à rapport
    quelconque : une interpolation apporterait sa propre distorsion pour un
    gain nul. 44,1 kHz descend donc à 14,7 kHz et non à 12 kHz — le décodeur
    prend sa cadence en paramètre, il n'a que faire d'un chiffre rond."""
    assert ctx.eval('ft8FacteurDecimation(%d)' % entree) == attendu


def test_une_cadence_absurde_ne_fait_pas_exploser_le_calcul(ctx):
    """Une cadence nulle, négative ou non finie ne doit pas produire un facteur
    nul ou infini : on n'a alors plus aucun échantillon, ou une boucle sans
    fin. Repli sur 1 — ne rien faire est toujours un comportement valable."""
    for mauvaise in ('0', '-48000', 'NaN', 'Infinity'):
        assert ctx.eval('ft8FacteurDecimation(%s)' % mauvaise) == 1


# ─── 2. Le filtre anti-repliement ───────────────────────────────────────────

def test_le_noyau_a_un_gain_unite_en_continu(ctx):
    """Sans normalisation, le niveau de sortie dépendrait de la longueur du
    noyau, et tous les seuils réglés en aval (score de synchro, détection de
    silence) deviendraient faux sans que rien ne le signale."""
    somme = ctx.eval('(function(){var h = ft8NoyauAntiRepliement(4);'
                     'var s = 0; for(var i=0;i<h.length;i++) s += h[i];'
                     'return s;})()')
    assert abs(somme - 1.0) < 1e-6


def test_le_noyau_ecrase_ce_qui_se_replierait(ctx):
    """LA propriété qui justifie le filtre. On mesure sa réponse à 3 kHz (dans
    la bande FT8, doit passer) et au-delà de la nouvelle demi-cadence (doit
    être écrasé) : tout ce qui dépasse 6 kHz après décimation par 4 ne
    disparaît pas, il se REPLIE au milieu des tons FT8."""
    rep = ctx.eval('''(function(){
      var h = ft8NoyauAntiRepliement(4), sr = 48000;
      function gain(f){
        var re = 0, im = 0;
        for(var i = 0; i < h.length; i++){
          var w = 2 * Math.PI * f * i / sr;
          re += h[i] * Math.cos(w); im -= h[i] * Math.sin(w);
        }
        return Math.sqrt(re*re + im*im);
      }
      return JSON.stringify({utile: gain(3000), nyquist: gain(6000),
                             haut: gain(9000), tres_haut: gain(15000)});
    })()''')
    g = json.loads(rep)
    assert g['utile'] > 0.7, 'le filtre mange le signal FT8 lui-même : %r' % g
    assert g['haut'] < 0.02, 'ce qui se replierait passe encore : %r' % g
    assert g['tres_haut'] < 0.02, g


def test_un_parasite_hors_bande_ne_detruit_pas_le_decodage(ctx):
    """Contre-épreuve VIVANTE du test précédent : un sifflement à 20 kHz, très
    au-dessus de la bande utile, replierait à 4 kHz après décimation par 4 s'il
    n'était pas filtré. Le décodage doit y survivre."""
    ctx.eval('var PARASITE = fabriquerFenetre(%s, %d, %s, %s, 0.02, 999, 20000);'
             % (json.dumps(MESSAGES), SR_CARTE, json.dumps(TONS),
                json.dumps(DT_VRAIS)))
    res = _decoder(ctx, 'ft8Decimer(PARASITE, %d).samples' % SR_CARTE,
                   'ft8Decimer(PARASITE, %d).sampleRate' % SR_CARTE)
    textes = {r['texte'] for r in res}
    assert set(MESSAGES).issubset(textes), (
        'un parasite hors bande a fait perdre des décodages : %r' % (textes,))


# ─── 3. Aucune perte de décodage, et le DT reste juste ──────────────────────

@pytest.fixture(scope='module')
def fenetre(ctx):
    ctx.eval('var FEN = fabriquerFenetre(%s, %d, %s, %s, 0.02, 12345, 0);'
             % (json.dumps(MESSAGES), SR_CARTE, json.dumps(TONS),
                json.dumps(DT_VRAIS)))
    return True


def test_la_decimation_ne_fait_perdre_aucun_decodage(ctx, fenetre):
    """LA condition de livraison. Une accélération qui perd des stations n'est
    pas une accélération : c'est une régression déguisée en optimisation."""
    avant = {r['texte'] for r in _decoder(ctx, 'FEN', SR_CARTE)}
    apres = {r['texte'] for r in _decoder(
        ctx, 'ft8Decimer(FEN, %d).samples' % SR_CARTE,
        'ft8Decimer(FEN, %d).sampleRate' % SR_CARTE)}
    assert set(MESSAGES).issubset(avant), (
        'le témoin lui-même ne décode pas tout — la mesure ne prouverait '
        'rien : %r' % (avant,))
    assert avant == apres, (
        'la décimation change ce qui est décodé.\n  avant : %r\n  après : %r'
        % (sorted(avant), sorted(apres)))


def test_le_dt_reste_juste_apres_decimation(ctx, fenetre):
    """Le DT dit à l'opérateur si son horloge dérive : un DT faux ferait courir
    après un problème d'horloge qui n'existe pas. La résolution temporelle
    tombe de 1/48000 s à 1/12000 s, ce qui reste 150 fois plus fin que le
    dixième de seconde affiché."""
    apres = _decoder(ctx, 'ft8Decimer(FEN, %d).samples' % SR_CARTE,
                     'ft8Decimer(FEN, %d).sampleRate' % SR_CARTE)
    par_texte = {r['texte']: r['dt'] for r in apres}
    for msg, dt_vrai in zip(MESSAGES, DT_VRAIS):
        assert msg in par_texte, msg
        assert abs(par_texte[msg] - dt_vrai) < 0.1, (
            '%s : DT mesuré %.2f s au lieu de %.2f s'
            % (msg, par_texte[msg], dt_vrai))


def test_les_frequences_audio_sont_conservees(ctx, fenetre):
    """La fréquence affichée sert à se caler sur une station (clic sur la
    cascade). Décimer ne doit pas la déplacer."""
    apres = _decoder(ctx, 'ft8Decimer(FEN, %d).samples' % SR_CARTE,
                     'ft8Decimer(FEN, %d).sampleRate' % SR_CARTE)
    par_texte = {r['texte']: r['freq'] for r in apres}
    for msg, ton in zip(MESSAGES, TONS):
        assert abs(par_texte[msg] - ton) < 15, (
            '%s : %.0f Hz au lieu de %d Hz' % (msg, par_texte[msg], ton))


# ─── 3bis. LA SENSIBILITÉ — la seule question qui pouvait tout annuler ──────

def test_la_decimation_ne_coute_aucune_sensibilite_au_seuil(ctx):
    """FT8 sert à travailler des stations À LA LIMITE : une accélération qui
    rendrait le décodeur plus sourd serait une régression déguisée.

    Les autres tests de ce fichier n'essaient qu'un rapport signal/bruit
    confortable — ils ne prouvent donc rien sur ce point. Une première mesure
    de contrôle décodait d'ailleurs 8/8 des deux côtés à tous les niveaux
    essayés : elle ne disait rien, faute d'avoir atteint le seuil du décodeur.

    On balaie ici JUSQU'À L'ÉCHEC FRANC, et on compare là où ça compte.
    Mesure de référence (8 tirages de bruit reproductibles par point) :

        bruit    sans décim.   avec décim.
          12         8/8           8/8
          16         3/8           4/8      <- la zone de transition
          24         0/8           0/8

    Total 35/64 contre 36/64. Un cas d'écart sur 64, en faveur de la
    décimation : ce n'est PAS une amélioration démontrable — l'écart tient dans
    le bruit d'échantillonnage — mais c'est une réfutation nette de la crainte
    inverse. Physiquement, le filtre anti-repliement retire du bruit hors
    bande, donc un très léger avantage n'aurait rien de surprenant.

    Le seuil est volontairement LARGE (pas plus de 2 décodages perdus au
    total) : ce test protège contre une régression franche de sensibilité, pas
    contre une fluctuation d'un tirage."""
    perdus = 0
    for bruit in (12.0, 16.0, 20.0):
        for graine in range(1, 7):
            ctx.eval('var S = fabriquerFenetre(%s, %d, %s, %s, %g, %d, 0);'
                     % (json.dumps([MESSAGES[0]]), SR_CARTE, json.dumps([TONS[0]]),
                        json.dumps([DT_VRAIS[0]]), bruit, graine))
            sans = _decoder(ctx, 'S', SR_CARTE)
            avec = _decoder(ctx, 'ft8Decimer(S, %d).samples' % SR_CARTE,
                            'ft8Decimer(S, %d).sampleRate' % SR_CARTE)
            a = MESSAGES[0] in {r['texte'] for r in sans}
            b = MESSAGES[0] in {r['texte'] for r in avec}
            if a and not b:
                perdus += 1
    assert perdus <= 2, (
        '%d décodages perdus par la décimation dans la zone de seuil — '
        'ce serait une régression de sensibilité, pas une optimisation'
        % perdus)


# ─── 4. Le gain est réel ────────────────────────────────────────────────────

def test_le_decodage_est_nettement_plus_rapide(ctx, fenetre):
    """Mesuré sous le V8 de py_mini_racer, PAS dans un navigateur : c'est le
    RAPPORT qui a du sens ici, pas la valeur absolue. Le travail (banc de
    Goertzel, recherche de synchro) est linéaire en nombre d'échantillons, donc
    le rapport se transporte.

    Seuil volontairement bas (x2) alors que la mesure donne x3,8 : ce test
    protège contre une RÉGRESSION (quelqu'un qui décâblerait la décimation),
    il n'a pas à rougir parce qu'une machine d'intégration est chargée."""
    def duree(expr_samples, expr_sr):
        best = None
        for _ in range(3):     # la 1re passe paie la compilation JIT
            t0 = time.perf_counter()
            ctx.eval('decoder(%s, %s)' % (expr_samples, expr_sr))
            d = time.perf_counter() - t0
            best = d if best is None else min(best, d)
        return best

    sans = duree('FEN', SR_CARTE)
    avec = duree('ft8Decimer(FEN, %d).samples' % SR_CARTE,
                 'ft8Decimer(FEN, %d).sampleRate' % SR_CARTE)
    assert avec * 2 < sans, (
        'la décimation ne fait plus gagner de temps : %.0f ms -> %.0f ms'
        % (sans * 1000, avec * 1000))


# ─── 5. Le câblage dans la page ─────────────────────────────────────────────

def test_la_page_decime_avant_de_decoder():
    """Le gain ne sert à rien si la page continue d'appeler le décodeur sur
    l'audio brut."""
    src = _lire(FT8_HTML)
    # `= ft8DecodeAudioAll(` et non `ft8DecodeAudioAll(` : la première
    # occurrence du nom nu est dans un COMMENTAIRE (celui de
    # pousserEchantillons, qui explique pourquoi cet appel fait sauter des
    # blocs audio). Chercher le nom seul faisait échouer ce test sur du texte
    # explicatif alors que le code était juste — le piège que ce chantier
    # documente par ailleurs : ne jamais analyser du code sans écarter la prose.
    i = src.index('= ft8DecodeAudioAll(')
    zone = src[max(0, i - 900):i]
    assert 'ft8Decimer(' in zone, (
        "la page appelle ft8DecodeAudioAll sans décimer d'abord")
    apres = src[i:i + 200]
    assert 'dec.samples' in apres and 'dec.sampleRate' in apres, (
        'le décodeur doit recevoir les échantillons DÉCIMÉS et leur cadence')


def test_le_dt_est_calcule_avec_la_cadence_reellement_utilisee():
    """Le piège exact de ce chantier : startSample est exprimé dans la cadence
    DÉCIMÉE. Réutiliser la cadence de la carte son diviserait le DT par le
    facteur de décimation — silencieusement, et sans que rien à l'écran ne le
    dise. Le bandeau d'alerte d'horloge deviendrait muet."""
    src = _lire(FT8_HTML)
    i = src.index('calculerDt(fenetre.debutMs')
    appel = src[i:i + 200]
    # Le 4e argument porte la cadence. Depuis le passage du décodage dans un
    # Web Worker, ce n'est plus `dec.sampleRate` (variable locale du chemin
    # synchrone) mais `decSampleRate`, paramètre de conclureCreneau — les DEUX
    # chemins y passent la cadence DÉCIMÉE. Le test tient donc désormais la
    # PROPRIÉTÉ (« pas la cadence de la carte son ») au lieu d'un nom, ce qui
    # le rend plus strict : il refuse explicitement `sr`.
    args = appel[appel.index('(') + 1:appel.index(')')]
    cadence = [a.strip() for a in args.split(',')][-1]
    assert cadence != 'sr', (
        'calculerDt reçoit la cadence de la CARTE SON : le DT serait divisé '
        'par le facteur de décimation, silencieusement')
    assert 'ampleRate' in cadence, (
        f'calculerDt doit recevoir une cadence décimée explicite, reçoit '
        f'« {cadence} »')
