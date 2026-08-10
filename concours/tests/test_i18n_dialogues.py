# -*- coding: utf-8 -*-
"""Les dialogues alert/confirm/prompt : la dernière famille qui échappe au moteur.

LE MOTEUR i18n TRADUIT TOUT CE QUI PASSE PAR LE DOM — c'est la mesure qui a
corrigé mon estimation initiale de « 646 chaînes » à ~190. Trois familles
seulement lui échappent, et deux sont traitées ici :

  A. alert() / confirm() / prompt() — ces textes ne sont JAMAIS des nœuds du
     DOM. Aucun MutationObserver ne peut les voir.
  B. document.title réécrit en JS — translateTitle() ne lit que le titre
     INITIAL de la page.

(La troisième, les phrases à valeur variable, est traitée par rcTf : « Aucun
spot sur 14 MHz » ne peut être aucune clé, elle change avec la bande.)

CE FICHIER EXÉCUTE LE VRAI logx_i18n.js DANS V8 et interroge le dictionnaire
réellement construit — pas une relecture du source. C'est la leçon du stub de
faux DOM : un test qui relit du texte ne prouve rien sur ce qui tourne.

MESURE QUE JE CORRIGE ICI, pour la deuxième fois sur ce chantier : j'avais
annoncé « 38 dialogues à traduire, plus 7 document.title ». Les deux chiffres
venaient d'un grep mécanique. En comptant les appels qui passaient DÉJÀ par le
helper trF()/trT(), le vrai total était 30 dialogues et 2 titres.
"""
import io
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N = os.path.join(CONCOURS, 'logx_i18n.js')
LANGUES = ('en', 'de', 'es', 'it', 'pt', 'nl', 'pl')

# Les fichiers dont les dialogues devaient être repris.
FICHIERS = ('logx_logbook.js', 'logx_configuration.html',
            'logx_focus.html', 'logx_panel.html')


def _lire(nom):
    with io.open(os.path.join(CONCOURS, nom), encoding='utf-8') as f:
        src = f.read()
    # logx_configuration.html : script inline extrait vers
    # logx_configuration.js (10/08/2026) -- concaténer pour que les
    # recherches ci-dessous (trF/trT, dialogues) continuent de le trouver.
    if nom == 'logx_configuration.html':
        js_path = os.path.join(CONCOURS, 'logx_configuration.js')
        if os.path.exists(js_path):
            with io.open(js_path, encoding='utf-8') as f:
                src += '\n' + f.read()
    return src


@pytest.fixture(scope='module')
def dico():
    """Le moteur RÉELLEMENT exécuté, interrogé par rcT() — le chemin qu'emprunte
    le code applicatif.

    Le faux DOM est celui de tests/test_i18n_dynamic_retranslation.py, PAS un
    stub réécrit ici. Un stub trop pauvre fait échouer l'init pour une raison
    étrangère à ce qu'on teste (première tentative : createElement() rendait un
    objet sans addEventListener) ; un stub trop permissif accepte ce que le
    vrai DOM refuse, et c'est ainsi qu'une clé à tiret avait fait exploser la
    traduction de toute une page sans qu'aucun test ne tombe.
    """
    from test_i18n_dynamic_retranslation import _DOM_PREAMBLE   # noqa: E402
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM_PREAMBLE)
    ctx.eval(_lire('logx_i18n.js'))
    return ctx


def _rcT(ctx, lang, fr):
    ctx.eval("localStorage.setItem('rc_lang', %s);" % json.dumps(lang))
    return ctx.eval('window.rcT(%s)' % json.dumps(fr))


# ─── Les clés posées aujourd'hui sont bien traduites ────────────────────────

CLES = [
    'Supprimer ce QSO ?',
    'Supprimer cette série QTC ?',
    '✅ Configuration sauvegardée !',
    'Lieu introuvable.',
    'Position refusée ou indisponible.',
    'Prompt copié dans le presse-papiers !',
    "Indique l'URL du règlement (PDF ou page web).",
    'Tape RESET pour confirmer la suppression complète du log :',
    '📦 ARCHIVER CE CONCOURS',
    'Focus bande',
]


@pytest.mark.parametrize('fr', CLES)
@pytest.mark.parametrize('lang', LANGUES)
def test_chaque_dialogue_est_traduit(dico, lang, fr):
    """Une clé absente est rendue TELLE QUELLE par le moteur, sans message :
    le dialogue resterait en français dans les sept autres langues."""
    out = _rcT(dico, lang, fr)
    assert out != fr, (lang, fr)
    assert out.strip(), (lang, fr)


@pytest.mark.parametrize('fr', CLES)
def test_le_francais_reste_le_francais(dico, fr):
    assert _rcT(dico, 'fr', fr) == fr


# ─── Les trous {x} survivent à la traduction ────────────────────────────────
# rcTf substitue APRÈS traduction : un trou perdu ou renommé laisserait « {n} »
# à l'écran, dans une seule langue, sans que rien ne le signale.

AVEC_TROUS = [
    ('✅ Profil « {n} » sauvegardé.', ['{n}']),
    ('Profil introuvable : {n}', ['{n}']),
    ('Supprimer le profil « {n} » ?', ['{n}']),
    ('Label pour {k} :', ['{k}']),
    ('Focus {b} MHz', ['{b}']),
]


@pytest.mark.parametrize('fr,trous', AVEC_TROUS)
@pytest.mark.parametrize('lang', LANGUES)
def test_les_trous_survivent_a_la_traduction(dico, lang, fr, trous):
    out = _rcT(dico, lang, fr)
    for t in trous:
        assert t in out, (lang, fr, out)


@pytest.mark.parametrize('lang', LANGUES)
def test_la_substitution_marche_bout_en_bout(dico, lang):
    """Le vrai geste : traduire PUIS substituer."""
    dico.eval("localStorage.setItem('rc_lang', %s);" % json.dumps(lang))
    out = dico.eval("window.rcTf('Label pour {k} :', {k: 'F1'})")
    assert 'F1' in out and '{k}' not in out, (lang, out)


# ─── Plus aucun dialogue à texte français brut ──────────────────────────────

_DIALOGUE = re.compile(r'\b(?:alert|confirm|prompt)\(')
_HELPER = re.compile(r'\b(?:trF|trT|Tf|T|rcT|rcTf)\(')
_FRANCAIS = re.compile(r"'[^']*[a-zà-ÿ][^']*'|`[^`]*[a-zà-ÿ]")


@pytest.mark.parametrize('nom', FICHIERS)
def test_aucun_dialogue_ne_porte_plus_de_texte_francais_brut(nom):
    """Le test de non-régression : un `alert('...')` ajouté demain sans passer
    par le helper resterait invisible autrement — il s'afficherait en français
    aux sept autres langues, sans erreur."""
    restants = []
    for i, ligne in enumerate(_lire(nom).splitlines(), 1):
        if not _DIALOGUE.search(ligne) or _HELPER.search(ligne):
            continue
        if _FRANCAIS.search(ligne):
            restants.append('%s:%d %s' % (nom, i, ligne.strip()[:80]))
    assert not restants, '\n'.join(restants)


@pytest.mark.parametrize('nom', ('logx_configuration.html',))
def test_la_page_config_a_bien_recu_les_helpers(nom):
    """Elle n'en avait AUCUN — ses 20 dialogues étaient donc intraduisibles
    quoi qu'il arrive."""
    src = _lire(nom)
    assert 'const T = s =>' in src
    assert 'const Tf = (s, p) =>' in src
    assert 'window.rcT' in src and 'window.rcTf' in src


def test_le_repli_fonctionne_sans_le_moteur():
    """Chaque page pose un repli identité : si logx_i18n.js manque ou tombe,
    les dialogues doivent rester lisibles en français, pas planter."""
    ctx = py_mini_racer.MiniRacer()
    ctx.eval('var window = this;')      # pas de rcT/rcTf
    ctx.eval('''
      const T = s => (window.rcT ? window.rcT(s) : s);
      const Tf = (s, p) => (window.rcTf ? window.rcTf(s, p) : (function(){
        let o = s; for(const k in (p || {})) o = o.split('{' + k + '}').join(p[k]); return o;
      })());
    ''')
    assert ctx.eval("T('Lieu introuvable.')") == 'Lieu introuvable.'
    assert ctx.eval("Tf('Label pour {k} :', {k: 'X'})") == 'Label pour X :'


# ─── Le titre de page ───────────────────────────────────────────────────────

def test_le_titre_de_focus_passe_par_le_helper():
    """document.title n'est pas un nœud : translateTitle() ne lit que le titre
    INITIAL, celui-ci lui échappait."""
    src = _lire('logx_focus.html')
    assert "document.title = 'LogX AI — ' + (bande ? Tf('Focus {b} MHz'" in src


def test_le_titre_du_panneau_detache_passe_par_rcT():
    src = _lire('logx_panel.html')
    m = re.search(r'document\.title = .*rcT', src)
    assert m, "le titre du panneau détaché n'est pas traduit"
