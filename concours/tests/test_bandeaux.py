# -*- coding: utf-8 -*-
"""Framework des bandeaux défilants (logx_bandeaux.js) — étape 1. On teste la
MÉCANIQUE PURE en V8 : filtrage live/7-jours des DXpéditions (règle F4GLD
26/08), disponibilité par activité, rendu HTML, config persistée. Les sources
de données réelles sont branchées par les pages (étapes 2-3), pas ici."""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_bandeaux.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx(localstorage=True):
    ctx = py_mini_racer.MiniRacer()
    if localstorage:
        ctx.eval("""
          var __ls = {};
          var localStorage = {
            getItem:function(k){ return (k in __ls) ? __ls[k] : null; },
            setItem:function(k,v){ __ls[k] = String(v); },
          };
        """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


# ─── Règle de contenu : DXpéditions limitées aux 7 prochains jours ──────────

def _expes_json():
    # base « maintenant » = 2026-09-01T12:00Z ; on met des débuts variés
    return """[
      {call:'A', debut:'2026-09-03T00:00Z'},                         /* dans 2 j : GARDÉ */
      {call:'B', debut:'2026-09-07T23:00Z'},                         /* dans ~6.5 j : GARDÉ */
      {call:'C', debut:'2026-09-15T00:00Z'},                         /* dans 14 j : ÉCARTÉ */
      {call:'D', debut:'2026-08-25T00:00Z', fin:'2026-08-28T00:00Z'},/* déjà finie : ÉCARTÉ */
      {call:'E', debut:'2026-08-30T00:00Z', fin:'2026-09-05T00:00Z'},/* EN COURS : GARDÉ */
      {call:'F', debut:'date invalide'}                              /* illisible : ÉCARTÉ */
    ]"""


def test_filtre_expeditions_7_jours():
    ctx = _ctx()
    now = "Date.parse('2026-09-01T12:00Z')"
    gardes = ctx.eval(
        "LogxBandeaux.filtrerExpeditions(%s, %s, 7).map(function(e){return e.call}).join(',')"
        % (_expes_json(), now))
    assert gardes == 'A,B,E'          # dans 7 j OU en cours ; ni lointain, ni fini, ni illisible


def test_filtre_expeditions_fenetre_configurable():
    ctx = _ctx()
    now = "Date.parse('2026-09-01T12:00Z')"
    # fenêtre 21 j -> C (dans 14 j) entre aussi
    gardes = ctx.eval(
        "LogxBandeaux.filtrerExpeditions(%s, %s, 21).map(function(e){return e.call}).join(',')"
        % (_expes_json(), now))
    assert gardes == 'A,B,C,E'


# ─── Disponibilité par activité ─────────────────────────────────────────────

def _registre_test(ctx):
    ctx.eval("""
      LogxBandeaux.enregistrerBandeau({id:'propag', cat:'PROPAG', contextes:'*',
        construire:function(){ return [{texte:'SFI 143'}]; }});
      LogxBandeaux.enregistrerBandeau({id:'concours', cat:'CONCOURS', contextes:['concours'],
        construire:function(c){ return [{texte:'mults: '+(c.mults||0)}]; }});
      LogxBandeaux.enregistrerBandeau({id:'ft8', cat:'NUMERIQUE', contextes:['numerique'],
        construire:function(){ return []; }});   // pas de données -> aucune ligne
    """)


def test_disponibles_par_activite():
    ctx = _ctx()
    _registre_test(ctx)
    assert ctx.eval("LogxBandeaux.bandeauxDisponibles('accueil').join(',')") == 'propag'
    assert ctx.eval("LogxBandeaux.bandeauxDisponibles('concours').sort().join(',')") == 'concours,propag'


def test_affichables_filtre_une_liste_par_contexte():
    """bandeauxAffichables(ids, activite) : garde, DANS l'ordre de `ids`, ceux
    dont le contexte matche l'activité (adaptation par activité). Un id inconnu
    est écarté. Base du driver activity-aware."""
    ctx = _ctx()
    ctx.eval("""
      LogxBandeaux.enregistrerBandeau({id:'uni', cat:'U', contextes:'*',
        construire:function(){ return []; }});
      LogxBandeaux.enregistrerBandeau({id:'cc', cat:'C', contextes:['concours'],
        construire:function(){ return []; }});
    """)
    # activité 'normal' : seul l'universel passe (cc réservé au concours)
    assert ctx.eval("LogxBandeaux.bandeauxAffichables(['uni','cc'],'normal').join(',')") == 'uni'
    # activité 'concours' : les deux, dans l'ordre fourni
    assert ctx.eval("LogxBandeaux.bandeauxAffichables(['cc','uni'],'concours').join(',')") == 'cc,uni'
    # id inconnu écarté, pas de plantage
    assert ctx.eval("LogxBandeaux.bandeauxAffichables(['uni','xxx'],'normal').join(',')") == 'uni'


def test_affichables_accepte_plusieurs_tags():
    """Le contexte peut être un TABLEAU de tags (deux axes : classe de bande +
    concours). Un bandeau passe si '*' OU si son contexte croise un des tags."""
    ctx = _ctx()
    ctx.eval("""
      LogxBandeaux.enregistrerBandeau({id:'hf', cat:'HF', contextes:['hf'],
        construire:function(){ return []; }});
      LogxBandeaux.enregistrerBandeau({id:'cc', cat:'C', contextes:['concours'],
        construire:function(){ return []; }});
      LogxBandeaux.enregistrerBandeau({id:'uni', cat:'U', contextes:'*',
        construire:function(){ return []; }});
    """)
    ids = "['hf','cc','uni']"
    # VHF + concours : cc (concours) et uni ('*') ; le bandeau HF est écarté
    assert ctx.eval(
        "LogxBandeaux.bandeauxAffichables(%s,['vhf','concours']).sort().join(',')" % ids) == 'cc,uni'
    # HF sans concours : hf et uni ; cc (concours) écarté
    assert ctx.eval(
        "LogxBandeaux.bandeauxAffichables(%s,['hf']).sort().join(',')" % ids) == 'hf,uni'


# ─── Rendu HTML ─────────────────────────────────────────────────────────────

def test_rendu_produit_les_lignes_et_double_le_bloc():
    ctx = _ctx()
    _registre_test(ctx)
    html = ctx.eval("LogxBandeaux.rendreTicker(['concours','propag'], {mults:18}, {})")
    assert 'CONCOURS' in html and 'mults: 18' in html and 'PROPAG' in html
    # boucle sans couture : le bloc d'items est dupliqué -> 'SFI 143' apparaît 2x
    assert html.count('SFI 143') == 2


def test_rendu_saute_un_bandeau_sans_donnees():
    ctx = _ctx()
    _registre_test(ctx)
    # ft8 renvoie [] -> pas de ligne vide (règle : pas de bandeau mort à l'écran)
    html = ctx.eval("LogxBandeaux.rendreTicker(['ft8','propag'], {}, {})")
    assert 'NUMERIQUE' not in html and 'PROPAG' in html


def test_rendu_echappe_les_donnees_texte():
    ctx = _ctx()
    ctx.eval("""LogxBandeaux.enregistrerBandeau({id:'x', cat:'X', contextes:'*',
      construire:function(){ return [{texte:'<img src=x onerror=1>'}]; }});""")
    html = ctx.eval("LogxBandeaux.rendreTicker(['x'], {}, {})")
    assert '<img' not in html and '&lt;img' in html     # pas d'injection via champ texte


def test_rendu_expose_les_data_attributs():
    """Un item peut porter it.data -> attributs data-* sur le <a> (support du
    clic « fiche » côté page : data-call/freq/band/mode/fiche). Valeurs vides
    ou nulles omises (pas d'attribut mort)."""
    ctx = _ctx()
    ctx.eval("""LogxBandeaux.enregistrerBandeau({id:'d', cat:'D', contextes:'*',
      construire:function(){ return [{texte:'V51WH',
        data:{call:'V51WH', freq:'14074', mode:'', fiche:'1'}}]; }});""")
    html = ctx.eval("LogxBandeaux.rendreTicker(['d'], {}, {})")
    assert 'data-call="V51WH"' in html
    assert 'data-freq="14074"' in html
    assert 'data-fiche="1"' in html
    assert 'data-mode=' not in html          # valeur vide -> attribut omis


def test_rendu_echappe_les_data_attributs():
    """Les valeurs data-* (indicatif cluster/NG3K = source externe) sont
    échappées comme le reste — pas d'évasion d'attribut."""
    ctx = _ctx()
    ctx.eval("""LogxBandeaux.enregistrerBandeau({id:'d', cat:'D', contextes:'*',
      construire:function(){ return [{texte:'x',
        data:{call:'\\"><img src=x onerror=1>'}}]; }});""")
    html = ctx.eval("LogxBandeaux.rendreTicker(['d'], {}, {})")
    assert '<img' not in html                 # pas d'injection via une valeur data-*
    assert '&quot;' in html and '&lt;img' in html


# ─── Config persistée ───────────────────────────────────────────────────────

def test_config_persiste_les_bandeaux_actifs():
    ctx = _ctx()
    ctx.eval("LogxBandeaux.enregistrerConfig({parActivite:{chasse:['propag','dx']}, masque:false});")
    assert ctx.eval("LogxBandeaux.bandeauxActifs('chasse', {}).join(',')") == 'propag,dx'


def test_config_repli_sur_defauts_activite():
    ctx = _ctx()
    # rien de persisté pour 'numerique' -> repli sur les défauts fournis
    val = ctx.eval("LogxBandeaux.bandeauxActifs('numerique', {numerique:['ft8','propag']}).join(',')")
    assert val == 'ft8,propag'


def test_basculer_retire_puis_reajoute_et_persiste():
    """basculerBandeau = point d'entrée du ⚙ « afficher/masquer » : flippe
    l'appartenance d'un bandeau à l'activité, persiste, renvoie la liste à jour.
    Part d'abord des défauts de l'activité (rien encore persisté)."""
    ctx = _ctx()
    d = "{chasse:['dxped','propag']}"
    # dxped actif par défaut -> bascule = retrait
    a1 = ctx.eval("LogxBandeaux.basculerBandeau('chasse','dxped',%s).join(',')" % d)
    assert a1 == 'propag'
    # persisté : la relecture reflète le retrait (pas un repli sur les défauts)
    assert ctx.eval("LogxBandeaux.bandeauxActifs('chasse',%s).join(',')" % d) == 'propag'
    # re-bascule -> ré-ajout
    a2 = ctx.eval("LogxBandeaux.basculerBandeau('chasse','dxped',%s).join(',')" % d)
    assert 'dxped' in a2.split(',')


def test_basculer_naffecte_pas_les_autres_activites():
    ctx = _ctx()
    ctx.eval("LogxBandeaux.basculerBandeau('chasse','dxped',{chasse:['dxped']});")
    # 'accueil' n'a jamais été touché -> repli intact sur ses défauts
    assert ctx.eval("LogxBandeaux.bandeauxActifs('accueil',{accueil:['dxped','propag']}).join(',')") == 'dxped,propag'


def test_a_reglage_activite_detecte_un_choix_persiste():
    """aReglageActivite : vrai seulement si l'opérateur a PERSISTÉ un choix pour
    cette activité (sert à distinguer « tout masqué exprès » de « vide par
    défaut/contexte » -> ne pas afficher de strip ⚙ parasite)."""
    ctx = _ctx()
    assert ctx.eval("LogxBandeaux.aReglageActivite('vuhf')") is False   # rien persisté
    ctx.eval("LogxBandeaux.basculerBandeau('vuhf','spots',{vuhf:[]});")  # l'opérateur touche vuhf
    assert ctx.eval("LogxBandeaux.aReglageActivite('vuhf')") is True     # choix persisté
    assert ctx.eval("LogxBandeaux.aReglageActivite('normal')") is False  # autre activité intacte
