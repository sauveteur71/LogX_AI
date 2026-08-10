# -*- coding: utf-8 -*-
"""Retirer un opérateur doit retirer la ligne ENTIÈRE (grille CONFIG > OPÉRATEURS).

La grille des opérateurs est en `grid-template-columns:80px 1fr 1fr 1.6fr` et
`#opExtraRows` est en `display:contents` : les cellules sont des enfants DIRECTS
de la grille, il n'existe aucun conteneur « ligne ». `operatorRowCells(i)` produit
donc QUATRE cellules par opérateur (étiquette OPi, indicatif, prénom, et depuis
l'ajout de la colonne QUALIFIÉ la cellule SSB/CW/DIGI).

`removeLastOperatorRow()` n'en retirait que TROIS — la boucle avait été écrite
avant la 4e colonne et n'a jamais été mise à jour. Deux dégâts, aucun message
d'erreur nulle part :

1) une ligne complète et éditable SURVIT au-delà d'`opRowCount`, avec l'indicatif
   que l'utilisateur vient d'accepter de supprimer ; `saveConfig()` n'itérant que
   jusqu'à `Math.min(opRowCount, opRowCap())`, cet opérateur bien visible à
   l'écran est écarté en silence de la config, de l'export EDI/Cabrillo, du
   planning de roulement et des boutons OP du logbook ;
2) le nombre de cellules n'est plus multiple de 4 : toute la grille glisse d'une
   colonne à partir de la ligne amputée.

Un simple « + Ajouter un opérateur » après coup recrée les MÊMES ids : le champ
que l'utilisateur voit et remplit n'est plus celui que lit `getElementById()`,
qui renvoie le fantôme.

Le défaut était atteignable par le bouton « － Retirer le dernier » ; depuis que
`setOperatorCount()` appelle `removeLastOperatorRow()` en boucle, passer de 12 à
3 enchaîne neuf suppressions partielles.

Le VRAI code est extrait du fichier livré et exécuté dans un moteur JS réel (V8
via py_mini_racer) sur un DOM minimal, comme tests/test_operateurs_nombre.py :
grepper une chaîne ne prouverait rien ici, c'est le comptage des cellules qui
est en cause.
"""
import os
import re

import pytest

py_mini_racer = pytest.importorskip(
    'py_mini_racer', reason='py_mini_racer absent (voir requirements.txt) — test JS réel ignoré')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(BASE, 'logx_configuration.html')

# Cellules de grille produites par operatorRowCells() pour UN opérateur :
# étiquette OPi, indicatif, prénom, qualifications SSB/CW/DIGI.
CELLULES_PAR_LIGNE = 4


def _source():
    with open(HTML, encoding='utf-8') as f:
        return f.read()


def _extraire(nom, src):
    """Extrait `function <nom>(...){...}` par comptage d'accolades."""
    # (?:async\s+)? : setOperatorCount() est devenue async (chantier dialogues
    # non bloquants, 10/08/2026 -- _confirmConfigBanner() remplace confirm()
    # natif) -- sans ce préfixe dans le match, m.start() pointerait après
    # "async " et le snippet extrait contiendrait un await hors fonction async.
    m = re.search(r'(?:async\s+)?function\s+' + re.escape(nom) + r'\s*\(', src)
    assert m, '%s() introuvable dans logx_configuration.html' % nom
    i = src.index('{', m.end() - 1)
    profondeur = 0
    for j in range(i, len(src)):
        if src[j] == '{':
            profondeur += 1
        elif src[j] == '}':
            profondeur -= 1
            if profondeur == 0:
                return src[m.start():j + 1]
    raise AssertionError('accolade fermante de %s() introuvable' % nom)


# ─── DOM minimal ──────────────────────────────────────────────────────────────
# On ne modélise que ce dont les fonctions extraites ont besoin : le conteneur
# #opExtraRows (display:contents -> ses enfants SONT les cellules de la grille),
# l'insertion de fragments HTML, la suppression d'un élément, et un
# getElementById() qui ne voit QUE ce qui est réellement dans le DOM — c'est
# précisément ce que lit saveConfig().
_DOM = r"""
var __STATIQUES = { op1_call:{value:''}, op1_name:{value:''},
                    op1_mode_ssb:{checked:true}, op1_mode_cw:{checked:true},
                    op1_mode_digi:{checked:true} };

function __attr(html, nom){
  var m = html.match(new RegExp(nom + '="([^"]*)"'));
  return m ? m[1] : null;
}
function __idsDe(html){
  var out = [], re = /id="([^"]+)"/g, m;
  while((m = re.exec(html))) out.push(m[1]);
  return out;
}
// Découpe un fragment en éléments de PREMIER NIVEAU, comme le ferait
// insertAdjacentHTML() dans un navigateur (<input> est auto-fermant).
function __decouper(html){
  var cells = [], depth = 0, start = 0, i = 0;
  while(i < html.length){
    if(html[i] !== '<'){ i++; continue; }
    var fin = html.indexOf('>', i);
    if(fin < 0) break;
    var balise = html.slice(i, fin + 1);
    var nom = (balise.match(/^<\/?\s*([a-zA-Z0-9-]+)/) || [])[1] || '';
    if(balise[1] === '/'){
      depth--;
      if(depth === 0) cells.push(html.slice(start, fin + 1));
    } else if(/^(input|br|img|hr|meta|link)$/i.test(nom) || /\/>$/.test(balise)){
      if(depth === 0) cells.push(balise);
    } else {
      if(depth === 0) start = i;
      depth++;
    }
    i = fin + 1;
  }
  return cells;
}
function __Cell(outer){
  var cell = { outerHTML: outer, opRow: __attr(outer, 'data-op-row'), champs: {} };
  __idsDe(outer).forEach(function(id){ cell.champs[id] = { id:id, value:'', checked:true }; });
  cell.remove = function(){
    var i = __extra._enfants.indexOf(cell);
    if(i >= 0) __extra._enfants.splice(i, 1);
  };
  return cell;
}

var __extra = { _enfants: [], style: {}, innerHTML: '' };
__extra.insertAdjacentHTML = function(pos, html){
  if(pos !== 'beforeend') throw new Error('position non gérée : ' + pos);
  __decouper(html).forEach(function(o){ __extra._enfants.push(__Cell(o)); });
};
__extra.querySelectorAll = function(sel){
  var m = sel.match(/^\[data-op-row="([^"]+)"\]$/);
  if(!m) throw new Error('sélecteur non géré : ' + sel);
  // NodeList statique, comme dans un navigateur : la suppression pendant
  // l'itération ne saute aucun élément.
  return __extra._enfants.filter(function(c){ return c.opRow === m[1]; });
};
Object.defineProperty(__extra, 'lastElementChild', { get: function(){
  return __extra._enfants.length ? __extra._enfants[__extra._enfants.length - 1] : null;
}});
Object.defineProperty(__extra, 'childElementCount', { get: function(){
  return __extra._enfants.length;
}});

var document = {
  getElementById: function(id){
    if(id === 'opExtraRows') return __extra;
    for(var i = 0; i < __extra._enfants.length; i++){
      if(__extra._enfants[i].champs[id]) return __extra._enfants[i].champs[id];
    }
    return __STATIQUES[id] || null;
  }
};

// Hors sujet ici : neutralisés pour ne tester que le retrait de ligne.
function updateOpRowControls(){}
function syncOpCountInput(){}
function getUsageMode(){ return 'contest'; }
var __confirmations = [];
function confirm(msg){ __confirmations.push(msg); return true; }
// setOperatorCount() appelle désormais _confirmConfigBanner() (bandeau non
// bloquant, chantier dialogues non bloquants, 10/08/2026) au lieu de confirm()
// natif -- stub Promise, même compteur __confirmations que ci-dessus.
function _confirmConfigBanner(msg){ __confirmations.push(msg); return Promise.resolve(true); }

var opRowCount = 1;

// ─── sondes ───────────────────────────────────────────────────────────────────
function __remplir(n){
  for(var i = 1; i <= n; i++){
    var el = document.getElementById('op' + i + '_call');
    if(el) el.value = 'F4AB' + i;
  }
}
// Étiquettes OPi encore affichées, dans l'ordre. Lues dans le HTML rendu (pas
// via un attribut du correctif) : la sonde reste valable sur l'ancien code.
function __etiquettesAffichees(){
  var out = [];
  __extra._enfants.forEach(function(c){
    var m = c.outerHTML.match(/>OP(\d+)<\/div>$/);
    if(m) out.push(parseInt(m[1], 10));
  });
  return out;
}
// Position des étiquettes OPi dans la grille. Une grille alignée les place
// toutes en colonne POSTE, donc aux indices 0, 4, 8... Toute autre valeur
// signifie que les cellules suivantes ont glissé sous les mauvais en-têtes.
function __indicesEtiquettes(){
  var out = [];
  __extra._enfants.forEach(function(c, i){
    if(/>OP\d+<\/div>$/.test(c.outerHTML)) out.push(i);
  });
  return out;
}
function __idsDupliques(){
  var vus = {}, dup = [];
  __extra._enfants.forEach(function(c){
    Object.keys(c.champs).forEach(function(id){
      vus[id] = (vus[id] || 0) + 1;
      if(vus[id] === 2) dup.push(id);
    });
  });
  return dup;
}
// Ce que saveConfig() enregistrerait réellement (même expression, ligne ~5136).
function __operateursEnregistres(){
  var n = Math.min(opRowCount, opRowCap()), out = [];
  for(var i = 1; i <= n; i++){
    var el = document.getElementById('op' + i + '_call');
    var v = el ? String(el.value).toUpperCase().trim() : '';
    if(v) out.push(v);
  }
  return out;
}
// Indicatifs encore VISIBLES à l'écran (présents dans la grille, éditables).
function __indicatifsAffiches(){
  var out = [];
  __extra._enfants.forEach(function(c){
    Object.keys(c.champs).forEach(function(id){
      if(/_call$/.test(id) && c.champs[id].value) out.push(c.champs[id].value);
    });
  });
  return out;
}
"""

_FONCTIONS = ('opRowCap', 'operatorRowCells', 'addOperatorRow',
              'removeLastOperatorRow', 'operatorRowFilled', 'setOperatorCount')


def _contexte():
    ctx = py_mini_racer.MiniRacer()
    ctx.eval(_DOM)
    src = _source()
    for nom in _FONCTIONS:
        ctx.eval(_extraire(nom, src))
    return ctx


def _alignement_attendu(lignes_extra):
    """Indices attendus des étiquettes OPi : une par ligne, en colonne POSTE."""
    return str([i * CELLULES_PAR_LIGNE for i in range(lignes_extra)]).replace(' ', '')


def test_grille_saine_avant_tout_retrait():
    """Garde-fou du test lui-même : la construction, elle, a toujours été juste."""
    ctx = _contexte()
    ctx.eval('setOperatorCount(6)')
    assert ctx.eval('opRowCount') == 6
    assert ctx.eval('__extra.childElementCount') == 5 * CELLULES_PAR_LIGNE
    assert ctx.eval('JSON.stringify(__indicesEtiquettes())') == _alignement_attendu(5)


def test_retrait_enleve_la_ligne_entiere():
    """Une seule cellule oubliée décale toute la grille d'une colonne."""
    ctx = _contexte()
    ctx.eval('setOperatorCount(6)')
    ctx.eval('removeLastOperatorRow()')
    assert ctx.eval('opRowCount') == 5
    assert ctx.eval('__extra.childElementCount') == 4 * CELLULES_PAR_LIGNE, (
        'cellules orphelines laissées par removeLastOperatorRow() : la grille '
        'glisse d\'une colonne à partir de la ligne amputée')
    assert ctx.eval('JSON.stringify(__etiquettesAffichees())') == '[2,3,4,5]'
    assert ctx.eval('JSON.stringify(__indicesEtiquettes())') == _alignement_attendu(4)


def test_reduction_en_boucle_ne_laisse_aucune_ligne_fantome():
    """12 -> 3 : neuf retraits d'affilée (champ « Nombre d'opérateurs »)."""
    ctx = _contexte()
    ctx.eval('setOperatorCount(12)')
    ctx.eval('__remplir(12)')
    ctx.eval('setOperatorCount(3)')
    assert ctx.eval('opRowCount') == 3
    assert ctx.eval('__confirmations.length') == 1, (
        'la suppression de lignes remplies doit être confirmée une fois')
    assert ctx.eval('__extra.childElementCount') == 2 * CELLULES_PAR_LIGNE
    assert ctx.eval('JSON.stringify(__etiquettesAffichees())') == '[2,3]', (
        'des lignes opérateur survivent au-delà d\'opRowCount')
    for i in (4, 5, 6, 12):
        assert ctx.eval('document.getElementById("op%d_call") === null' % i), (
            'op%d_call est encore dans le DOM, éditable, alors que '
            'l\'utilisateur a accepté sa suppression' % i)


def test_aucun_operateur_affiche_n_est_ecarte_de_la_config():
    """Le cœur du dégât : ce qui est à l'écran doit être ce qui est enregistré.

    saveConfig() n'itère que jusqu'à Math.min(opRowCount, opRowCap()) — toute
    ligne survivante au-delà est un opérateur visible, éditable, et absent de la
    config enregistrée, de l'export EDI/Cabrillo et des boutons OP du logbook.
    """
    ctx = _contexte()
    ctx.eval('setOperatorCount(12)')
    ctx.eval('__remplir(12)')
    ctx.eval('setOperatorCount(3)')
    affiches = ctx.eval('JSON.stringify(__indicatifsAffiches())')
    enregistres = ctx.eval('JSON.stringify(__operateursEnregistres())')
    assert affiches == '["F4AB2","F4AB3"]', (
        'indicatifs encore affichés après réduction : %s' % affiches)
    assert enregistres == '["F4AB1","F4AB2","F4AB3"]'
    # OP1 est une ligne statique de la page, hors #opExtraRows.
    assert ctx.eval('__indicatifsAffiches().every(function(c){'
                    ' return __operateursEnregistres().indexOf(c) >= 0; })'), (
        'un indicatif visible à l\'écran n\'est pas enregistré')


def test_ajout_apres_retrait_ne_duplique_pas_les_ids():
    """« Retirer le dernier » puis « Ajouter » : le champ que l'utilisateur
    remplit doit être celui que lit saveConfig(). Avec une ligne fantôme, les
    ids sont recréés en double et getElementById() renvoie le fantôme —
    l'indicatif tapé n'est jamais enregistré, remplacé par celui que
    l'utilisateur croyait avoir supprimé."""
    ctx = _contexte()
    ctx.eval('setOperatorCount(6)')
    ctx.eval('__remplir(6)')
    ctx.eval('removeLastOperatorRow()')
    ctx.eval('addOperatorRow()')
    assert ctx.eval('opRowCount') == 6
    assert ctx.eval('JSON.stringify(__idsDupliques())') == '[]', (
        'ids dupliqués après retrait puis ajout')
    assert ctx.eval('__extra.childElementCount') == 5 * CELLULES_PAR_LIGNE
    # La ligne recréée est vierge : l'ancienne saisie a bien été supprimée.
    assert ctx.eval('document.getElementById("op6_call").value') == ''
    # Et ce que l'utilisateur tape dans la ligne visible est bien ce qui est lu.
    ctx.eval('__extra._enfants[__extra._enfants.length - 3].champs.op6_call.value = "NOUVEAU6"')
    assert ctx.eval('document.getElementById("op6_call").value') == 'NOUVEAU6'
    assert ctx.eval('__operateursEnregistres().indexOf("NOUVEAU6") >= 0'), (
        'l\'indicatif saisi dans la ligne visible n\'est pas celui enregistré')


def test_retraits_et_ajouts_repetes_gardent_la_grille_alignee():
    """Ajustements à l'unité la veille d'un concours : la grille doit rester un
    multiple exact de 4 cellules, sans quoi les en-têtes POSTE/INDICATIF/
    PRÉNOM/QUALIFIÉ ne correspondent plus à rien."""
    ctx = _contexte()
    for sequence in ('setOperatorCount(8)', 'removeLastOperatorRow()',
                     'addOperatorRow()', 'setOperatorCount(2)',
                     'setOperatorCount(5)', 'removeLastOperatorRow()',
                     'removeLastOperatorRow()', 'addOperatorRow()'):
        ctx.eval(sequence)
        n = ctx.eval('__extra.childElementCount')
        lignes = ctx.eval('opRowCount')
        assert n == (lignes - 1) * CELLULES_PAR_LIGNE, (
            '%s -> %d cellules pour %d opérateurs (attendu %d)'
            % (sequence, n, lignes, (lignes - 1) * CELLULES_PAR_LIGNE))
        assert (ctx.eval('JSON.stringify(__indicesEtiquettes())')
                == _alignement_attendu(lignes - 1)), (
            'grille décalée après %s' % sequence)
