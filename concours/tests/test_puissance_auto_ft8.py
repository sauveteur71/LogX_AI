# -*- coding: utf-8 -*-
"""Protection du final en numérique : elle ne s'appliquait pas là où on émet.

LE DÉFAUT. Le réglage « puissance TX automatique par mode » existe depuis le
16/08 : coché dans CONFIG > RADIO, il pousse `cat_power_digital_w` vers la
radio pour protéger le final, parce qu'un mode numérique émet à 100 % du cycle
de service quand la phonie et la CW n'y sont pas.

Sauf qu'il n'était poussé QUE par le sélecteur de bande/mode du LOGBOOK :
`_puissanceAutoVersRadio()` n'avait qu'un seul site d'appel, `_qsyVersRadio()`.
Vérifié par recherche exhaustive avant d'écrire une ligne. Or c'est la page FT8
qui émet réellement en FT8, et elle ne contenait AUCUN appel à
`/rig/set_power`. Un opérateur qui ouvre MODE NUMÉRIQUE → FT8 directement — le
chemin naturel depuis la barre de navigation — n'avait donc rien : son poste
restait sur son réglage phonie et chaque créneau partait à cette puissance-là,
en porteuse à rapport cyclique 100 % pendant 12,6 s. Exactement ce que le
réglage existe pour éviter, pendant que la page lui présentait le curseur
NIVEAU TX comme LE réglage de puissance du mode.

DEUX PROPRIÉTÉS QUI COMPTENT ICI, chacune tenue par un test :

  - **Une seule table de modes.** Elle vivait dans logx_logbook.js ; deux
    copies divergeraient au premier mode ajouté, en silence — un mode oublié
    d'un côté ne lève aucune erreur, il laisse passer la pleine puissance.
  - **Le refus doit être DIT.** L'ancien appel partait en
    `fetch().catch(()=>{})`. Or le refus est le cas le plus COURANT :
    `cat.set_power()` refuse explicitement Icom/Xiegu (la commande CI-V règle
    un niveau relatif, pas des watts) et tout mode CAT autre que le pilotage
    natif. Un opérateur d'IC-7300 croyait donc son final protégé alors que
    rien n'était jamais parti.

CE QUE CES TESTS NE PROUVENT PAS : que la radio obéit. Ça se vérifie sur le
poste, en regardant le wattmètre — pas dans un banc.
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent — test JS réel ignoré')

from test_ft8_sequenceur import _lire  # noqa: E402

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(CONCOURS, 'logx_puissance_auto.js')
PAGE_FT8 = os.path.join(CONCOURS, 'logx_ft8.html')
PAGE_LOG = os.path.join(CONCOURS, 'logx_logbook.html')
JS_LOG = os.path.join(CONCOURS, 'logx_logbook.js')


def _sans_commentaires(src):
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    return '\n'.join(re.sub(r'//.*$', '', li) for li in src.splitlines())


def _banc(config=None, reponse=None):
    """Exécute le VRAI module avec un faux fetch qui enregistre les appels.

    Le point important : le fetch est OBSERVÉ, pas neutralisé. Un test qui se
    contenterait de vérifier que le module ne lève pas d'exception passerait
    avec un module qui n'envoie jamais rien.
    """
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
    var __config = '{}';
    var localStorage = {getItem: function(){ return __config; }, setItem: function(){}};
    var __appels = [];
    var __reponse = {ok: true, corps: {ok: true, watts: 0}};
    var fetch = function(url, opts){
      __appels.push({url: url, corps: JSON.parse(opts.body)});
      return Promise.resolve({
        ok: __reponse.ok,
        json: function(){ return Promise.resolve(__reponse.corps); }
      });
    };
    var window = {};
    var __resultat = null;
    """)
    if config is not None:
        import json
        ctx.eval('__config = %s;' % json.dumps(json.dumps(config)))
    if reponse is not None:
        import json
        ctx.eval('__reponse = %s;' % json.dumps(reponse).replace('"corps"', '"corps"'))
        ctx.eval('__reponse = %s;' % json.dumps(reponse))
    ctx.eval(_lire(MODULE))
    return ctx


def _appliquer(ctx, mode):
    """Déroule la promesse jusqu'au bout — sans quoi on n'observerait rien."""
    ctx.eval('__resultat = null;'
             ' window.appliquerPuissanceAuto(%r).then(function(r){ __resultat = r; });' % mode)
    # py_mini_racer vide la file de microtâches à chaque eval : une évaluation
    # triviale suffit à laisser la promesse se résoudre.
    ctx.eval('0;')
    return ctx.eval('JSON.stringify(__resultat)')


CFG_ACTIVE = {'cat_power_auto_enabled': True,
              'cat_power_digital_w': '30', 'cat_power_phone_w': '100'}


# ─── le module décide bien, et ne pousse rien quand rien n'est demandé ───────

def test_rien_n_est_pousse_si_la_protection_n_est_pas_cochee():
    """DÉSACTIVÉE PAR DÉFAUT : ce lot ne doit changer le comportement de
    personne tant que l'opérateur n'a rien demandé."""
    ctx = _banc(config={'cat_power_digital_w': '30'})
    _appliquer(ctx, 'FT8')
    assert ctx.eval('__appels.length') == 0, (
        'aucune commande ne doit partir vers la radio')


def test_rien_n_est_pousse_si_la_puissance_n_est_pas_UTILISABLE():
    """Un champ vide ne doit JAMAIS se traduire par 0 W poussé sur l'air.

    La valeur négative est dans la liste pour une raison mesurée : elle est le
    SEUL cas qui distingue un vrai garde-fou d'un `watts || 0`. Chaîne vide,
    « 0 » et texte donnent tous NaN ou 0, deux valeurs fausses au sens de `||`
    — une implémentation bâclée les arrête donc par accident, et un test qui
    s'arrêterait là serait satisfait par elle. « -5 » passe au travers.
    """
    for mauvaise in ('', '0', 'abc', '-5', None):
        cfg = {'cat_power_auto_enabled': True, 'cat_power_digital_w': mauvaise}
        ctx = _banc(config=cfg)
        _appliquer(ctx, 'FT8')
        assert ctx.eval('__appels.length') == 0, (
            'valeur %r a déclenché un envoi vers la radio' % mauvaise)


def test_le_mode_numerique_recoit_la_puissance_numerique():
    ctx = _banc(config=CFG_ACTIVE)
    _appliquer(ctx, 'FT8')
    assert ctx.eval('__appels.length') == 1
    assert ctx.eval('__appels[0].url') == '/rig/set_power'
    assert ctx.eval('__appels[0].corps.watts') == 30


def test_la_phonie_recoit_la_puissance_phonie():
    """Le module sert aussi le LOGBOOK, qui lui passe le mode courant : il ne
    doit pas rabattre toute la station sur la puissance numérique."""
    ctx = _banc(config=CFG_ACTIVE)
    _appliquer(ctx, 'SSB')
    assert ctx.eval('__appels[0].corps.watts') == 100


def test_le_mode_est_reconnu_quelle_que_soit_la_casse():
    """rigMode arrive en majuscules côté FT8, currentMode aussi côté LOGBOOK —
    mais rien ne le garantit pour un appelant futur, et se tromper ici pousse
    la puissance PHONIE sur un mode numérique : l'inverse de la protection."""
    ctx = _banc(config=CFG_ACTIVE)
    _appliquer(ctx, 'ft8')
    assert ctx.eval('__appels[0].corps.watts') == 30


# ─── le refus est DIT, pas avalé ─────────────────────────────────────────────

def test_un_refus_de_la_radio_est_rapporte_avec_son_motif():
    """LE POINT DE CE LOT. cat.set_power() refuse Icom/Xiegu et tout mode CAT
    non natif, en répondant 400 avec un message explicite. Ce message doit
    remonter : sinon l'opérateur d'un IC-7300 croit son final protégé."""
    ctx = _banc(config=CFG_ACTIVE,
                reponse={'ok': False,
                         'corps': {'ok': False,
                                   'error': 'Réglage de puissance indisponible en CI-V'}})
    r = _appliquer(ctx, 'FT8')
    assert '"applique":0' in r.replace(' ', ''), r
    assert 'CI-V' in r, ('le motif du refus doit être rendu à l\'appelant : ' + r)


def test_un_succes_rapporte_les_watts_reellement_appliques():
    ctx = _banc(config=CFG_ACTIVE,
                reponse={'ok': True, 'corps': {'ok': True, 'watts': 25}})
    r = _appliquer(ctx, 'FT8')
    assert '"applique":25' in r.replace(' ', ''), r


# ─── câblage : une seule table, et la page FT8 l'utilise vraiment ────────────

def test_la_table_des_modes_n_existe_qu_a_UN_endroit():
    """Deux copies divergeraient au premier mode ajouté, sans lever d'erreur :
    le mode oublié laisserait simplement passer la pleine puissance."""
    porteurs = []
    for nom in os.listdir(CONCOURS):
        if not (nom.endswith('.js') or nom.endswith('.html')):
            continue
        chemin = os.path.join(CONCOURS, nom)
        if not os.path.isfile(chemin):
            continue
        code = _sans_commentaires(_lire(chemin))
        if re.search(r'MODES_NUMERIQUES_PUISSANCE\s*=\s*new Set', code):
            porteurs.append(nom)
    assert porteurs == ['logx_puissance_auto.js'], (
        'la table doit être déclarée une seule fois, dans le module partagé ; '
        'trouvée dans : %s' % porteurs)


def test_la_page_ft8_charge_le_module_ET_l_appelle():
    """Assertion de STRUCTURE en deux temps, et les deux sont nécessaires :
    charger le module sans l'appeler ne protège rien, et l'appeler sans le
    charger échoue en silence (l'appel est gardé par un typeof)."""
    src = _lire(PAGE_FT8)
    assert '<script src="logx_puissance_auto.js"></script>' in src, (
        'la page FT8 doit charger le module partagé')
    code = _sans_commentaires(src)
    assert 'appliquerPuissanceAuto(' in code, (
        "la page FT8 doit appeler la protection, pas seulement charger le module")


def test_la_protection_part_a_l_ARMEMENT_de_l_emission():
    """Le moment choisi n'est pas indifférent : c'est le geste par lequel
    l'opérateur autorise l'émission, donc le seul où l'avertissement a une
    chance d'être lu. Assertion structurelle sur le corps de onArmChange, et
    non sur la présence de l'appel ailleurs dans le fichier."""
    code = _sans_commentaires(_lire(PAGE_FT8))
    i = code.index('window.onArmChange = function()')
    corps = code[i:code.index('};', i)]
    assert 'appliquerProtectionPuissance()' in corps, (
        "onArmChange doit déclencher la protection :\n" + corps)


def test_le_logbook_charge_le_module_AVANT_son_script():
    """L'appel du LOGBOOK est gardé par un typeof : dans le mauvais ordre, rien
    ne lève — la protection redevient simplement muette, ce que ce lot corrige.
    L'ordre est donc une propriété à tenir, pas un détail."""
    src = _lire(PAGE_LOG)
    i_mod = src.index('logx_puissance_auto.js')
    i_log = src.index('<script src="logx_logbook.js">')
    assert i_mod < i_log, (
        'logx_puissance_auto.js doit être chargé avant logx_logbook.js')


def test_le_logbook_delegue_au_module_et_ne_reimplemente_rien():
    """Sinon les deux chemins divergent : celui du LOGBOOK garderait son propre
    fetch, et une correction faite dans le module ne le toucherait pas."""
    code = _sans_commentaires(_lire(JS_LOG))
    i = code.index('function _puissanceAutoVersRadio()')
    corps = code[i:code.index('\n}', i)]
    assert 'appliquerPuissanceAuto(' in corps, corps
    assert 'set_power' not in corps, (
        'le LOGBOOK ne doit plus appeler /rig/set_power lui-même :\n' + corps)


def test_l_ecran_dit_ce_qui_s_est_reellement_passe():
    """Intuitivité, et sûreté : les trois cas doivent être distinguables à
    l'écran — protection appliquée, radio non pilotée, refus de la radio. Un
    seul message générique laisserait croire à une protection dans les trois."""
    code = _sans_commentaires(_lire(PAGE_FT8))
    i = code.index('function appliquerProtectionPuissance()')
    corps = code[i:code.index('\n  }', i)]
    assert "n'est pas pilotée" in corps, (
        'le cas « radio non pilotée » doit avoir son propre message :\n' + corps)
    assert 'NON limitée' in corps, (
        'le refus de la radio doit être annoncé comme tel :\n' + corps)
    assert 'limitée à' in corps, (
        'le succès doit annoncer les watts réellement appliqués :\n' + corps)


def test_le_message_de_refus_est_visible_et_pas_gris():
    """La classe .err doit exister dans la feuille de style de la page : sans
    règle, elle retombe sur --muted et l'avertissement le plus important de la
    rangée s'affiche en gris, moins visible qu'un statut ordinaire."""
    src = _lire(PAGE_FT8)
    assert re.search(r'\.tx-status\.err\s*\{[^}]*color\s*:', src), (
        'la classe .tx-status.err doit être définie avec une couleur')
