# -*- coding: utf-8 -*-
"""Non-régression (signalé par F4GLD le 23/10/2026, capture CQ WW SSB) :
l'enregistrement d'un concours analysé par l'IA était REFUSÉ avec
« log_format='CABRILLO' mais 'cabrillo_name' absent (voir A04) ».

Cause : le formulaire de relecture (openReviewModal) n'avait AUCUN champ
cabrillo_name, et saveReviewedDefinition ne le renvoyait jamais — même quand
l'IA l'avait extrait. Le validateur serveur (logx_validate) l'exige pour tout
log_format CABRILLO : aucun concours Cabrillo ne pouvait passer.

Ces tests exécutent les VRAIES fonctions de logx_configuration.js dans V8
(extraites du fichier, pas réimplémentées), avec un DOM minimal et un fetch
espion qui capture le corps POSTé à /rules/save_definition."""
import json
import os
import re

import pytest

py_mini_racer = pytest.importorskip('py_mini_racer')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = open(os.path.join(BASE, 'logx_configuration.js'), encoding='utf-8').read()


def _fonction(nom):
    """Source d'une fonction de premier niveau (de sa déclaration jusqu'à la
    prochaine déclaration de premier niveau)."""
    m = re.search(r'^(?:async )?function %s\(' % re.escape(nom), JS, re.M)
    assert m, '%s introuvable dans logx_configuration.js' % nom
    fin = re.search(r'^(?:async )?function \w+\(|^// ─── ', JS[m.end():], re.M)
    return JS[m.start(): m.end() + (fin.start() if fin else len(JS) - m.end())]


DOM = r"""
var _els = {}, _posted = null;
function _el(id){
  if(!_els[id]) _els[id] = {id:id, value:'', textContent:'', style:{},
    set innerHTML(h){ this._h = h;
      var re = /<input[^>]*id="rev_([a-z_]+)"[^>]*value="([^"]*)"/g, m;
      while((m = re.exec(h))) _el('rev_' + m[1]).value = m[2].replace(/&quot;/g,'"');
      var t = /<textarea id="rev_scoring"[^>]*>([\s\S]*?)<\/textarea>/.exec(h);
      if(t) _el('rev_scoring').value = t[1].replace(/&lt;/g,'<'); },
    get innerHTML(){ return this._h || ''; }};
  return _els[id];
}
var document = { getElementById: function(id){ return _el(id); } };
function escC(s){ return String(s == null ? '' : s); }
function safeUrl(u){ return u; }
var _aiProposal = null, state = {contest:''};
function mergeServerContests(){ return Promise.resolve(); }
function buildContestGrid(){} function selectContest(){} function setTimeout(){}
function fetch(url, opts){ _posted = {url:url, body:JSON.parse(opts.body)};
  return Promise.resolve({json:function(){ return Promise.resolve({ok:false, error:'stop'}); }}); }
"""


def _ctx():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(DOM)
    for f in ('_revField', '_verificationBlock', 'openReviewModal', 'saveReviewedDefinition'):
        ctx.eval(_fonction(f))
    return ctx


def _proposition(**defn):
    d = {'name': 'CQ WW DX Contest', 'organizer': 'CQ Magazine',
         'date_rule': 'last_full_weekend_october', 'bands': ['1.8', '3.5', '7', '14', '21', '28'],
         'modes': ['SSB'], 'exchange': 'RS + zone CQ', 'log_format': 'CABRILLO',
         'scoring': {'type': 'cqww'}}
    d.update(defn)
    return {'suggested_id': 'CQWW_SSB', 'definition': d, 'citations': {}, 'confidence': 'high',
            'warnings': [], 'extractor': 'test', 'text_chars': 1}


def _enregistrer(ctx, prop, saisie=None):
    ctx.eval('_aiProposal = %s; openReviewModal(_aiProposal);' % json.dumps(prop))
    if saisie is not None:
        ctx.eval('_el("rev_cabrillo_name").value = %s;' % json.dumps(saisie))
    ctx.eval('saveReviewedDefinition();')
    ctx.eval('0')   # laisse tourner la file des promesses
    posted = json.loads(ctx.eval('JSON.stringify(_posted)'))
    assert posted and posted['url'] == '/rules/save_definition'
    return posted['body']['definition']


def test_le_formulaire_propose_le_champ_cabrillo_name():
    ctx = _ctx()
    ctx.eval('openReviewModal(%s)' % json.dumps(_proposition(cabrillo_name='CQ-WW-SSB')))
    html = ctx.eval('_el("reviewModalBody").innerHTML')
    assert re.search(r'<input[^>]*id="rev_cabrillo_name"[^>]*value="CQ-WW-SSB"', html)


def test_le_nom_trouve_par_l_ia_est_transmis_a_l_enregistrement():
    ctx = _ctx()
    d = _enregistrer(ctx, _proposition(cabrillo_name='CQ-WW-SSB'))
    assert d.get('cabrillo_name') == 'CQ-WW-SSB'


def test_le_nom_saisi_a_la_relecture_est_transmis():
    ctx = _ctx()
    d = _enregistrer(ctx, _proposition(), saisie='  CQ-WW-SSB ')
    assert d.get('cabrillo_name') == 'CQ-WW-SSB'


def test_champ_vide_pas_de_cabrillo_name_parasite():
    ctx = _ctx()
    d = _enregistrer(ctx, _proposition(log_format='EDI'))
    assert 'cabrillo_name' not in d


def test_la_definition_envoyee_passe_le_validateur_serveur():
    """Bout en bout : ce que le formulaire POSTe est accepté par le VRAI
    validateur (celui qui produisait l'erreur de la capture)."""
    import sys
    sys.path.insert(0, BASE)
    from logx_validate import validate_definition
    ctx = _ctx()
    d = _enregistrer(ctx, _proposition(), saisie='CQ-WW-SSB')
    errs = [e for e in validate_definition(d, 'CQWW_SSB') if 'cabrillo_name' in e]
    assert errs == [], errs


def test_le_prompt_d_extraction_demande_cabrillo_name():
    import sys
    sys.path.insert(0, BASE)
    import logx_rules_ai
    p = logx_rules_ai.build_extraction_system()
    assert 'cabrillo_name' in p and 'CONTEST:' in p
