# -*- coding: utf-8 -*-
"""Bandeaux défilants — étape 2 : DÉFINITIONS concrètes (logx_bandeaux_defs.js).

Ces bandeaux transforment les données DÉJÀ récupérées par la page (forme réelle
des endpoints /data/dxpeditions_active et /data/propagation) en items de ticker.
Règle de contenu F4GLD : diffuser du LIVE en priorité ; DXpéditions filtrées aux
7 prochains jours. Testé en V8 comme le framework (tests/test_bandeaux.py).

Les résultats JS transitent par JSON.stringify -> json.loads : py_mini_racer
rend sinon un JSObject opaque (pas de len(), pas d'indexation Python)."""
import json
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMEWORK = os.path.join(CONCOURS, 'logx_bandeaux.js')
DEFS = os.path.join(CONCOURS, 'logx_bandeaux_defs.js')
py_mini_racer = pytest.importorskip('py_mini_racer')

NOW_MS = 1_756_000_000_000  # ancrage fixe (~2025-08-24) pour un filtre 7j déterministe
JOUR = 86_400_000


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("var window = {}; var module = undefined;")
    with open(FRAMEWORK, encoding='utf-8') as f:
        ctx.eval(f.read())
    with open(DEFS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


def _j(ctx, expr):
    """Évalue `expr` (qui rend un objet/tableau JS) et le ramène en Python."""
    return json.loads(ctx.eval("JSON.stringify(" + expr + ")"))


def _dxped_expr(expeditions, now=NOW_MS):
    return ("window.LogxBandeaux.REGISTRE.dxped.construire({maintenant:%d},"
            "{dxpeditions:{expeditions:%s}})" % (now, json.dumps(expeditions)))


def test_les_deux_bandeaux_sont_enregistres():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxBandeaux.REGISTRE.dxped") == 'object'
    assert ctx.eval("typeof window.LogxBandeaux.REGISTRE.propag") == 'object'


def test_dxped_live_dabord_meme_sans_date_lisible():
    """Une expédition ACTIVE (repérée sur le cluster) doit passer même si ses
    dates NG3K sont illisibles : le LIVE prime (règle F4GLD)."""
    ctx = _ctx()
    items = _j(ctx, _dxped_expr([
        {'callsign': 'TX9A', 'entity': 'Chatham', 'status': 'active',
         'starts': None, 'ends': None, 'freq_khz': 14074, 'spot_band': '20m'},
    ]))
    assert len(items) == 1
    assert 'TX9A' in items[0]['texte']
    assert '14.074' in items[0]['texte']      # fréquence live affichée


def test_dxped_a_venir_dans_7_jours_gardee_au_dela_ecartee():
    ctx = _ctx()
    # Dates ISO calculées en JS relativement à NOW pour éviter toute dépendance
    # au fuseau : proche = +3 j (gardée), loin = +30 j (écartée).
    js = (
        "(function(){var now=%d;var iso=function(off){return new Date(now+off*%d)"
        ".toISOString().slice(0,10);};"
        "var d=[{callsign:'A1B',entity:'Proche',status:'upcoming',starts:iso(3),ends:iso(9)},"
        "{callsign:'C2D',entity:'Loin',status:'upcoming',starts:iso(30),ends:iso(40)}];"
        "return window.LogxBandeaux.REGISTRE.dxped.construire({maintenant:now},"
        "{dxpeditions:{expeditions:d}});})()" % (NOW_MS, JOUR)
    )
    items = json.loads(ctx.eval("JSON.stringify(" + js + ")"))
    calls = ''.join(i['texte'] for i in items)
    assert 'A1B' in calls        # commence dans 3 jours -> gardée
    assert 'C2D' not in calls    # commence dans 30 jours -> écartée


def test_dxped_terminee_exclue():
    ctx = _ctx()
    items = _j(ctx, _dxped_expr([
        {'callsign': 'END', 'entity': 'Finie', 'status': 'ended',
         'starts': '2025-01-01', 'ends': '2025-01-10'},
    ]))
    assert items == []


def test_dxped_echappe_le_contenu_reseau():
    """entity vient d'un flux externe (NG3K) : passé en {texte}, le framework
    doit l'échapper au rendu (pas d'injection)."""
    ctx = _ctx()
    d = [{'callsign': 'X', 'entity': '<img src=x onerror=alert(1)>',
          'status': 'active', 'freq_khz': 0}]
    html = ctx.eval(
        "window.LogxBandeaux.rendreTicker(['dxped'],{maintenant:%d},"
        "{dxpeditions:{expeditions:%s}})" % (NOW_MS, json.dumps(d))
    )
    assert '<img' not in html           # échappé
    assert '&lt;img' in html            # présent sous forme échappée


def test_dxped_actif_porte_data_fiche_cliquable():
    """Item ACTIF -> data.fiche + call/freq/band/mode : la page ouvre un popup
    « fiche » au clic (indicatif, fréquence cluster, QSY...)."""
    ctx = _ctx()
    items = _j(ctx, _dxped_expr([
        {'callsign': 'TX9A', 'entity': 'Chatham', 'status': 'active',
         'freq_khz': 14074, 'spot_band': '20m', 'spot_mode': 'CW',
         'worked_status': 'new'},
    ]))
    d = items[0].get('data')
    assert d, "un item actif doit porter data (fiche cliquable)"
    assert d.get('fiche') == '1'
    assert d.get('call') == 'TX9A'
    assert d.get('freq') == '14074'
    assert d.get('band') == '20m' and d.get('mode') == 'CW'
    assert d.get('entity') == 'Chatham'      # pays affiché dans la fiche
    assert d.get('neuf') == '1'              # « nouveau pays » signalé dans la fiche


def test_dxped_actif_sans_frequence_pas_de_freq_fantome():
    """freq_khz = 0 (actif mais pas de fréquence cluster) -> data.freq VIDE :
    sinon la fiche afficherait « QSY 0 kHz » / « 0.000 MHz »."""
    ctx = _ctx()
    items = _j(ctx, _dxped_expr([
        {'callsign': 'TX0', 'entity': 'X', 'status': 'active', 'freq_khz': 0},
    ]))
    assert items[0]['data']['freq'] == ''        # pas de '0' fantôme
    assert '0.000' not in items[0]['texte']


def test_dxped_a_venir_nest_pas_cliquable():
    """Une expédition à VENIR (gardée car ≤7j) reste un simple lien, pas une
    fiche : on ne peut pas QSY sur une station pas encore active."""
    ctx = _ctx()
    js = (
        "(function(){var now=%d;var iso=function(off){return new Date(now+off*%d)"
        ".toISOString().slice(0,10);};"
        "var d=[{callsign:'A1B',entity:'Proche',status:'upcoming',starts:iso(3),ends:iso(9)}];"
        "return window.LogxBandeaux.REGISTRE.dxped.construire({maintenant:now},"
        "{dxpeditions:{expeditions:d}});})()" % (NOW_MS, JOUR)
    )
    items = json.loads(ctx.eval("JSON.stringify(" + js + ")"))
    assert items and 'A1B' in items[0]['texte']
    assert 'data' not in items[0]        # à venir -> pas de fiche cliquable


def _propag_expr(bandes):
    return ("window.LogxBandeaux.REGISTRE.propag.construire({},"
            "{propagation:{etat_bandes:{bandes:%s,muf_mhz:21.0,soleil_deg:30}}})"
            % json.dumps(bandes))


def test_propag_ne_montre_que_les_bandes_exploitables():
    ctx = _ctx()
    items = _j(ctx, _propag_expr([
        # Clés RÉELLES du serveur (MHz) : '14' = 20 m, '7' = 40 m, '28' = 10 m.
        {'band': '14', 'etat': 'ouverte', 'score': 80, 'raison': 'DX'},
        {'band': '7', 'etat': 'possible', 'score': 50, 'raison': 'régional'},
        {'band': '28', 'etat': 'fermee', 'score': 10, 'raison': 'au-dessus MUF'},
    ]))
    txt = ''.join(i['texte'] for i in items)
    assert '20 m' in txt        # ouverte -> montrée
    assert '40 m' in txt        # possible -> montrée
    assert '10 m' not in txt    # fermee -> masquée


def test_propag_aucune_bande_ouverte_pas_de_ligne_morte():
    ctx = _ctx()
    items = _j(ctx, _propag_expr([
        {'band': '10', 'etat': 'fermee', 'score': 5, 'raison': 'nuit'},
    ]))
    assert items == []


def test_propag_met_en_avant_la_bande_courante():
    """Adaptation bande (ctx.band) : la bande en cours de saisie passe EN TÊTE
    et est marquée ; les autres restent normales. ctx.band en clé MHz ('14',
    comme currentBand du logbook) ou en mètres ('20m') : les deux reconnus."""
    ctx = _ctx()
    for cur in ('14', '20m'):
        expr = ("window.LogxBandeaux.REGISTRE.propag.construire({band:%s},"
                "{propagation:{etat_bandes:{bandes:%s}}})" % (json.dumps(cur), json.dumps([
                    {'band': '7', 'etat': 'ouverte'},
                    {'band': '14', 'etat': 'possible'},
                ])))
        items = _j(ctx, expr)
        assert '20 m' in items[0]['texte'] and 'ta bande' in items[0]['texte'], cur   # courante en tête + marquée
    assert 'ta bande' not in items[1]['texte']                             # les autres non marquées


def test_propag_sans_bande_courante_inchange():
    ctx = _ctx()
    items = _j(ctx, _propag_expr([
        {'band': '7', 'etat': 'ouverte'}, {'band': '14', 'etat': 'ouverte'},
    ]))
    txt = ''.join(i['texte'] for i in items)
    assert 'ta bande' not in txt          # aucun ctx.band -> pas de marquage
    assert '40 m' in items[0]['texte']    # ordre d'origine préservé


# ─── Bandeau SPOTS DX (source : /data/spots_ranked) ─────────────────────────

def _spots_expr(spots):
    return ("window.LogxBandeaux.REGISTRE.spots.construire({},"
            "{spots_ranked:{spots:%s}})" % json.dumps(spots))


def test_spots_enregistre():
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxBandeaux.REGISTRE.spots") == 'object'


def test_spots_rend_call_freq_et_badge_credit():
    """Item = indicatif + fréquence + bande + mode, badge = credit_raison (texte
    serveur) quand credit_score > 0 ; cliquable -> fiche (data-*)."""
    ctx = _ctx()
    items = _j(ctx, _spots_expr([
        {'call': 'K1ABC', 'band': '20m', 'freq': 14074, 'mode': 'CW',
         'dx_country': 'USA', 'credit_raison': 'Nouveau pays !', 'credit_score': 1000},
    ]))
    assert len(items) == 1
    t = items[0]['texte']
    assert 'K1ABC' in t and '14.074' in t and 'Nouveau pays' in t
    d = items[0]['data']
    assert d['fiche'] == '1' and d['call'] == 'K1ABC' and d['freq'] == '14074'
    assert d['band'] == '20m' and d['mode'] == 'CW' and d['entity'] == 'USA'


def test_spots_sans_credit_pas_de_badge_parasite():
    ctx = _ctx()
    items = _j(ctx, _spots_expr([
        {'call': 'F1XYZ', 'band': '40m', 'freq': 7100, 'mode': 'SSB', 'credit_score': 0},
    ]))
    t = items[0]['texte']
    assert 'F1XYZ' in t
    assert 'undefined' not in t and 'None' not in t     # pas de champ manquant recraché


def test_spots_borne_le_nombre_affiche():
    ctx = _ctx()
    many = [{'call': 'C%d' % i, 'band': '20m', 'freq': 14000 + i, 'mode': 'CW'} for i in range(30)]
    items = _j(ctx, _spots_expr(many))
    assert len(items) == 15         # borné pour ne pas noyer le ticker


def test_spots_vide_pas_de_ligne_morte():
    ctx = _ctx()
    assert _j(ctx, _spots_expr([])) == []


def test_spots_sans_frequence_pas_de_freq_fantome():
    """freq = 0 -> ni « 0.000 MHz » dans le texte, ni data.freq='0' (fiche)."""
    ctx = _ctx()
    items = _j(ctx, _spots_expr([{'call': 'K0', 'band': '20m', 'freq': 0, 'mode': 'CW'}]))
    assert '0.000' not in items[0]['texte']
    assert items[0]['data']['freq'] == ''


def test_spots_echappe_le_call_reseau():
    ctx = _ctx()
    d = [{'call': '<img src=x onerror=1>', 'band': '20m', 'freq': 14074}]
    html = ctx.eval("window.LogxBandeaux.rendreTicker(['spots'],{},"
                    "{spots_ranked:{spots:%s}})" % json.dumps(d))
    assert '<img' not in html and '&lt;img' in html


# ─── Bandeau MULTS (concours uniquement) — source : /data/spots_ranked ───────

def _mults_expr(spots):
    return ("window.LogxBandeaux.REGISTRE.mults.construire({},"
            "{spots_ranked:{spots:%s}})" % json.dumps(spots))


def test_mults_reserve_au_concours():
    """Le bandeau MULTS n'a de sens qu'en concours (contextes:['concours']) :
    bandeauxAffichables l'écarte hors concours (« le jaune hors concours »)."""
    ctx = _ctx()
    assert ctx.eval("typeof window.LogxBandeaux.REGISTRE.mults") == 'object'
    assert ctx.eval("window.LogxBandeaux.bandeauxAffichables(['mults'],'normal').length") == 0
    assert ctx.eval("window.LogxBandeaux.bandeauxAffichables(['mults'],'concours').length") == 1


def test_mults_ne_garde_que_les_nouveaux_multiplicateurs():
    ctx = _ctx()
    items = _j(ctx, _mults_expr([
        {'call': 'K1ABC', 'band': '20m', 'freq': 14074, 'mode': 'CW',
         'new_mult': True, 'mult_type': 'zone 5', 'dx_country': 'USA'},
        {'call': 'F5ZZZ', 'band': '20m', 'freq': 14090, 'new_mult': False},  # pas un nouveau mult -> écarté
    ]))
    assert len(items) == 1
    t = items[0]['texte']
    assert 'K1ABC' in t and 'zone 5' in t and '14.074' in t
    d = items[0]['data']
    assert d['fiche'] == '1' and d['call'] == 'K1ABC' and d['entity'] == 'USA'


def test_mults_vide_si_aucun_nouveau_mult():
    ctx = _ctx()
    items = _j(ctx, _mults_expr([{'call': 'A', 'band': '20m', 'new_mult': False}]))
    assert items == []


def test_mults_borne_le_nombre():
    ctx = _ctx()
    many = [{'call': 'C%d' % i, 'band': '20m', 'freq': 14000 + i, 'new_mult': True, 'mult_type': 'z'} for i in range(20)]
    items = _j(ctx, _mults_expr(many))
    assert len(items) == 12


# ─── Libellés de bande : FORME RÉELLE des endpoints (correctif 23/10/2026) ───
# Défaut signalé par plusieurs utilisateurs : les bandeaux PROPAG / MULTS / SPOTS
# affichaient la CLÉ INTERNE en MHz suivie de « m » (« 21 m », « 28 m » — bandes
# inexistantes ; « 10 m » pour 10 MHz = bande des 30 m). Les tests ci-dessus
# n'avaient rien vu : leurs données étaient des mannequins DÉJÀ en mètres
# ('20m', band '20'). Ici les données viennent du VRAI producteur serveur.

LONGUEURS_REELLES = {'160 m', '80 m', '60 m', '40 m', '30 m', '20 m', '17 m', '15 m',
                     '12 m', '10 m', '6 m', '4 m', '2 m', '70 cm', '23 cm'}


def _bandes_reelles_serveur():
    """Sortie RÉELLE de logx_paths.etat_bandes_hf (producteur de /data/propagation),
    toutes bandes forcées « ouverte » pour que le bandeau les affiche toutes."""
    import sys
    sys.path.insert(0, CONCOURS)
    import logx_paths
    eb = logx_paths.etat_bandes_hf(45.1, 3.9)
    bandes = eb['bandes'] if isinstance(eb, dict) else eb
    assert bandes, 'etat_bandes_hf ne rend plus de bandes — adapter ce test'
    return [dict(b, etat='ouverte') for b in bandes]


def test_propag_libelles_sur_la_vraie_sortie_serveur():
    ctx = _ctx()
    bandes = _bandes_reelles_serveur()
    items = _j(ctx, _propag_expr(bandes))
    assert len(items) == len(bandes)
    for it in items:
        lib = it['texte'].split('● ', 1)[1].split(' · ')[0]
        assert lib in LONGUEURS_REELLES, 'libellé de bande impossible : %r' % it['texte']
    txt = ' | '.join(i['texte'] for i in items)
    assert '21 m' not in txt and '28 m' not in txt and '14 m' not in txt


@pytest.mark.parametrize('cle,attendu', [
    ('1.8', '160 m'), ('3.5', '80 m'), ('7', '40 m'), ('10', '30 m'), ('10.1', '30 m'),
    ('14', '20 m'), ('18', '17 m'), ('21', '15 m'), ('24', '12 m'), ('28', '10 m'),
    ('50', '6 m'), ('144', '2 m'), ('432', '70 cm'), ('20m', '20 m'),
])
def test_propag_cle_mhz_vers_longueur_d_onde(cle, attendu):
    ctx = _ctx()
    items = _j(ctx, _propag_expr([{'band': cle, 'etat': 'ouverte'}]))
    assert items[0]['texte'] == '● ' + attendu + ' · ouverte'


def test_propag_ta_bande_avec_currentBand_reel():
    """currentBand du logbook est une clé MHz ('7', '10.1') — et le serveur
    propag dit '10' pour 30 m : les deux doivent se reconnaître."""
    ctx = _ctx()
    for cur, cle in (('7', '7'), ('10.1', '10'), ('14', '14')):
        expr = ("window.LogxBandeaux.REGISTRE.propag.construire({band:%s},"
                "{propagation:{etat_bandes:{bandes:%s}}})" % (json.dumps(cur), json.dumps([
                    {'band': '21', 'etat': 'ouverte'}, {'band': cle, 'etat': 'possible'}])))
        items = _j(ctx, expr)
        assert 'ta bande' in items[0]['texte'], (cur, items)
        assert 'ta bande' not in items[1]['texte']


def test_propag_item_cliquable_vers_page_propag():
    """Sans href, le lien rendu valait '#' : un clic renvoyait en haut de la page."""
    ctx = _ctx()
    items = _j(ctx, _propag_expr([{'band': '14', 'etat': 'ouverte'}]))
    assert items[0]['href'] == 'logx_propagation.html'


def test_mults_et_spots_bande_reelle_et_type_lisible():
    """Forme réelle de /data/spots_ranked : band = clé MHz ('7'), mult_type =
    identifiant interne de logx_scoring ('zone_cq')."""
    ctx = _ctx()
    spot = {'call': 'YB9CQN', 'band': '7', 'freq': '7163', 'mode': 'SSB',
            'new_mult': True, 'mult_type': 'zone_cq', 'dx_country': 'Indonesia'}
    t = _j(ctx, _mults_expr([spot]))[0]['texte']
    assert t == '★ YB9CQN · zone CQ · 7.163 MHz · 40 m', t
    t2 = _j(ctx, _spots_expr([spot]))[0]['texte']
    assert '40 m' in t2 and '7 m' not in t2.replace('7.163', '')


def test_mults_tous_les_types_du_moteur_sont_traduits():
    """Chaque mult_type émis par logx_scoring.py a un libellé sans underscore."""
    import re
    src = open(os.path.join(CONCOURS, 'logx_scoring.py'), encoding='utf-8').read()
    types = set(re.findall(r"mult_type'\]\s*=\s*'([a-z_]+)'", src))
    types |= set(re.findall(r"\bmult_type\s*=\s*'([a-z_]+)'", src))
    types |= set(re.findall(r"'(zone_cq|dxcc)' if", src))
    assert {'zone_cq', 'grand_carre', 'etat_province'} <= types, types
    ctx = _ctx()
    for ty in sorted(types):
        t = _j(ctx, _mults_expr([{'call': 'X1X', 'band': '14', 'new_mult': True, 'mult_type': ty}]))[0]['texte']
        assert '_' not in t, (ty, t)
