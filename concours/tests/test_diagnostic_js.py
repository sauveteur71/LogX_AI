# -*- coding: utf-8 -*-
"""Écran « Santé de la station » (logx_diagnostic.js) — testé en V8.

Les états viennent d'endpoints EXISTANTS (/hardware/state, /data/network_status,
/tx/audit, /dxcc/status) — lecture seule. Ici on teste la couche présentation :
construireTuiles() traduit ces états bruts en tuiles {id, couleur, detail}, et
_rendre() produit un HTML XSS-safe. Aucun démarrage auto dans le harnais.
"""
import os

import pytest

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(CONCOURS, 'logx_diagnostic.js')
py_mini_racer = pytest.importorskip('py_mini_racer')


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval("""
      var window = {};
      var __c = { innerHTML: '' };
      var __prog = { innerHTML: '' };
      var __gal = { innerHTML: '' };
      var document = { getElementById: function(id){
          if(id === 'diagTuiles') return __c;
          if(id === 'diagProgression') return __prog;
          if(id === 'diagGalerie') return __gal;
          return null; } };
    """)
    with open(JS, encoding='utf-8') as f:
        ctx.eval(f.read())
    return ctx


_DATA_OK = """{
  hardware: {rig:{enabled:true, ok:true, freq_khz:14074, mode:'USB'},
             rotor:{enabled:false}, wsjtx:{enabled:true, connected:true}},
  network:  {callbook:{open:false, wait_s:0}, cloudsync:{enabled:true, last_error:null},
             mysql_sync:{enabled:false}},
  tx:       {tx_locked:false},
  dxcc:     {available:true}
}"""


def _couleur(ctx, tid):
    return ctx.eval(
        "(function(){var t=window.LogxDiagnostic.construireTuiles(%s);"
        "for(var i=0;i<t.length;i++){if(t[i].id==='%s')return t[i].couleur;}return null;})()"
        % (_DATA_OK, tid))


def test_radio_verte_si_cat_repond():
    ctx = _ctx()
    assert _couleur(ctx, 'radio') == 'green'


def test_radio_rouge_si_activee_mais_muette():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({hardware:{rig:{enabled:true, ok:false}}}).filter(function(t){return t.id==='radio';})[0].couleur")
    assert c == 'red'


def test_radio_muette_si_non_configuree():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({hardware:{rig:{enabled:false}}}).filter(function(t){return t.id==='radio';})[0].couleur")
    assert c == 'muted'


def test_ft8_jaune_si_active_sans_decodage():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({hardware:{wsjtx:{enabled:true, connected:false}}}).filter(function(t){return t.id==='ft8';})[0].couleur")
    assert c == 'yellow'


def test_tx_rouge_si_verrouille():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({tx:{tx_locked:true}}).filter(function(t){return t.id==='tx';})[0].couleur")
    assert c == 'red'


def test_dxcc_rouge_si_indisponible():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({dxcc:{available:false}}).filter(function(t){return t.id==='dxcc';})[0].couleur")
    assert c == 'red'


def test_ssdv_kiss_mute_si_desactive():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({hardware:{ssdv_kiss:{enabled:false}}}).filter(function(t){return t.id==='ssdv';})[0].couleur")
    assert c == 'muted'


def test_ssdv_kiss_verte_si_connecte():
    ctx = _ctx()
    data = "{hardware:{ssdv_kiss:{enabled:true, connected:true, paquets_recus:7}}}"
    couleur = ctx.eval("window.LogxDiagnostic.construireTuiles(%s).filter(function(t){return t.id==='ssdv';})[0].couleur" % data)
    detail = ctx.eval("window.LogxDiagnostic.construireTuiles(%s).filter(function(t){return t.id==='ssdv';})[0].detail" % data)
    assert couleur == 'green'
    assert '7' in detail


def test_ssdv_kiss_jaune_si_active_mais_deconnecte():
    ctx = _ctx()
    data = "{hardware:{ssdv_kiss:{enabled:true, connected:false, derniere_erreur:'connexion refusee'}}}"
    couleur = ctx.eval("window.LogxDiagnostic.construireTuiles(%s).filter(function(t){return t.id==='ssdv';})[0].couleur" % data)
    detail = ctx.eval("window.LogxDiagnostic.construireTuiles(%s).filter(function(t){return t.id==='ssdv';})[0].detail" % data)
    assert couleur == 'yellow'
    assert 'connexion refusee' in detail


def test_ssdv_kiss_absent_ne_plante_pas():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({}).filter(function(t){return t.id==='ssdv';})[0].couleur")
    assert c == 'muted'


def test_callbook_jaune_si_disjoncteur_ouvert():
    ctx = _ctx()
    c = ctx.eval("window.LogxDiagnostic.construireTuiles({network:{callbook:{open:true, wait_s:30}}}).filter(function(t){return t.id==='callbook';})[0].couleur")
    assert c == 'yellow'


def test_ia_verte_avec_conso_muette_sans():
    ctx = _ctx()
    assert ctx.eval("window.LogxDiagnostic.construireTuiles({aiUsage:{calls:5, in_tokens:100, out_tokens:20}}).filter(function(t){return t.id==='ia';})[0].couleur") == 'green'
    d = ctx.eval("window.LogxDiagnostic.construireTuiles({aiUsage:{calls:5, in_tokens:100, out_tokens:20}}).filter(function(t){return t.id==='ia';})[0].detail")
    assert '5 appels' in d
    # Absent (endpoint non dispo / aucun appel) -> muté, jamais planté.
    assert ctx.eval("window.LogxDiagnostic.construireTuiles({}).filter(function(t){return t.id==='ia';})[0].couleur") == 'muted'


def test_rendre_produit_les_tuiles_et_echappe():
    ctx = _ctx()
    ctx.eval("window.LogxDiagnostic._rendre(window.LogxDiagnostic.construireTuiles(%s));" % _DATA_OK)
    html = ctx.eval("__c.innerHTML")
    assert 'diag-tuile' in html and 'diag-dot' in html
    # détail radio (fréquence) présent
    assert '14074' in html


def test_rendre_echappe_le_detail_xss():
    ctx = _ctx()
    ctx.eval("window.LogxDiagnostic._rendre([{id:'x', nom:'X', couleur:'green', detail:'<img src=x onerror=1>'}]);")
    html = ctx.eval("__c.innerHTML")
    assert '<img' not in html and '&lt;img' in html


def test_progression_mappe_les_diplomes():
    ctx = _ctx()
    ctx.eval("""window.__p = window.LogxDiagnostic.construireProgression({
      dxcc:{worked:137, confirmed:120, total:340},
      departments:{metro_worked:80, metro_total:96},
      wac:{worked:5, confirmed:5, total:6},
      waz:{worked:30, confirmed:28, total:40},
      qso_total:5000});""")
    txt = ctx.eval("window.__p.map(function(l){return l.label+'='+l.valeur;}).join('|')")
    assert 'DXCC (pays)=137 / 340 (conf. 120)' in txt
    assert 'Départements FR=80 / 96' in txt
    assert 'Continents (WAC)=5 / 6 (conf. 5)' in txt
    assert 'QSO au total=5000' in txt


def test_progression_tolere_sections_absentes():
    ctx = _ctx()
    ctx.eval("window.__p = window.LogxDiagnostic.construireProgression({});")
    assert ctx.eval("window.__p.length") == 0


def test_rendre_progression_produit_le_html():
    ctx = _ctx()
    ctx.eval("window.LogxDiagnostic._rendreProgression([{label:'DXCC (pays)', valeur:'137 / 340'}]);")
    html = ctx.eval("__prog.innerHTML")
    assert 'diag-prog' in html and 'DXCC' in html and '137 / 340' in html


def test_cablage_page():
    with open(os.path.join(CONCOURS, 'logx_diagnostic.html'), encoding='utf-8') as f:
        h = f.read()
    assert 'src="logx_diagnostic.js"' in h
    assert 'id="diagTuiles"' in h
    assert 'id="diagProgression"' in h
    assert 'id="diagGaleriePanel"' in h
    assert 'id="diagGalerie"' in h
    assert 'logx_theme.css' in h            # tokens mutualisés
    assert 'logx_statusbar.js' in h         # barre de statut + expert-only


# ─── Galerie SSDV (clic sur la tuile -> vignettes des images reçues) ────────

def test_ssdv_tuile_est_un_bouton_cliquable():
    ctx = _ctx()
    ctx.eval("window.LogxDiagnostic._rendre(window.LogxDiagnostic.construireTuiles("
             "{hardware:{ssdv_kiss:{enabled:true, connected:true, paquets_recus:2}}}));")
    html = ctx.eval("__c.innerHTML")
    assert '<button' in html
    assert 'diag-tuile-clic' in html
    assert 'data-id="ssdv"' in html


def test_construire_galerie_formate_indicatif_image_id_et_date():
    ctx = _ctx()
    src = ("window.LogxDiagnostic.construireGalerie("
           "[{fichier:'F4GLD_1_1700000000.jpg', indicatif:'F4GLD', image_id:1, recu_le:1700000000}])[0].")
    assert ctx.eval(src + "fichier") == 'F4GLD_1_1700000000.jpg'
    libelle = ctx.eval(src + "libelle")
    assert 'F4GLD' in libelle
    assert '#1' in libelle
    assert 'UTC' in libelle


def test_construire_galerie_tolere_liste_absente():
    ctx = _ctx()
    assert ctx.eval("window.LogxDiagnostic.construireGalerie(null).length") == 0


def test_rendre_galerie_vide_affiche_un_message():
    ctx = _ctx()
    ctx.eval("window.LogxDiagnostic._rendreGalerie([]);")
    html = ctx.eval("__gal.innerHTML")
    assert 'Aucune image' in html


def test_rendre_galerie_produit_une_vignette_avec_url_echappee():
    ctx = _ctx()
    ctx.eval("window.LogxDiagnostic._rendreGalerie(window.LogxDiagnostic.construireGalerie("
             "[{fichier:'F4GLD_1_1700000000.jpg', indicatif:'F4GLD', image_id:1, recu_le:1700000000}]));")
    html = ctx.eval("__gal.innerHTML")
    assert '/ssdv_images/F4GLD_1_1700000000.jpg' in html
    assert '<img' in html
    assert 'diag-ssdv-vignette' in html


def test_rendre_galerie_encode_les_caracteres_speciaux_de_lurl():
    # esc() seul n'échappe pas espace/#/? -- caractères qui casseraient
    # l'URL (pas le HTML) s'ils passaient bruts. encodeURIComponent() est
    # ce qui protège CE cas précis.
    ctx = _ctx()
    ctx.eval("window.LogxDiagnostic._rendreGalerie(window.LogxDiagnostic.construireGalerie("
             "[{fichier:'F4 GLD_1_1.jpg', indicatif:'X', image_id:1, recu_le:1}]));")
    html = ctx.eval("__gal.innerHTML")
    assert '/ssdv_images/F4%20GLD_1_1.jpg' in html
    assert '/ssdv_images/F4 GLD_1_1.jpg' not in html


def test_rendre_galerie_echappe_un_indicatif_hostile():
    # indicatif alimente le libellé affiché -- jamais passé par
    # encodeURIComponent (contrairement à fichier, qui vit dans l'URL) --
    # c'est esc() seul qui doit empêcher l'injection ici.
    ctx = _ctx()
    ctx.eval("window.LogxDiagnostic._rendreGalerie(window.LogxDiagnostic.construireGalerie("
             "[{fichier:'F4GLD_1_1.jpg', indicatif:'<img onerror=alert(1)>', image_id:1, recu_le:1}]));")
    html = ctx.eval("__gal.innerHTML")
    assert '<img onerror=alert(1)>' not in html
    assert '&lt;img onerror=alert(1)&gt;' in html
