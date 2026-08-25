/* logx_dept_todo.js — Tri du panneau « départements À FAIRE » (chasse au mult).
 *
 * Décisions F4GLD (25/08) :
 *  - tri par FRÉQUENCE par défaut (le département dont le donneur spotté est le
 *    plus proche de ta fréquence courante en tête -> minimise le QSY en run) ;
 *  - bascule vers RARETÉ (départements avec le moins de stations connues d'abord
 *    -> les plus durs à décrocher passent devant).
 *
 * Glue PURE et testable (le rendu DOM + le clic bandmapClick restent dans
 * logx_filtre_spots.js). Testé en V8 (test_dept_todo.py).
 */
(function () {
  'use strict';

  // Fréquence d'un donneur spotté en MHz (le cluster la donne en kHz).
  function _giverMhz(sp) { return (parseFloat(sp && sp.freq) || 0) / 1000; }

  // Écart de fréquence (MHz) le plus PETIT entre `freqMhz` et un donneur spotté
  // du département — mesure « à quel point ce dept est à portée de QSY ». Sans
  // rig (`freqMhz` absent), on classe par fréquence absolue (ordre stable).
  function _ecartMin(t, freqMhz) {
    var sp = (t && t.spotted) || [];
    var best = Infinity;
    for (var i = 0; i < sp.length; i++) {
      var m = _giverMhz(sp[i]);
      if (!m) { continue; }
      var e = freqMhz ? Math.abs(m - freqMhz) : m;
      if (e < best) { best = e; }
    }
    return best;
  }

  // Trie une liste de cibles-département. PURE : renvoie une nouvelle liste (les
  // donneurs de chaque dept sont clonés puis triés). `mode` : 'freq' (défaut) |
  // 'rarete'. `freqMhz` : fréquence courante du poste (MHz) pour la proximité.
  function trier(targets, mode, freqMhz) {
    var out = (targets || []).map(function (t) {
      return { dept: t.dept, name: t.name, known: t.known, spotted: ((t.spotted || []).slice()) };
    });
    if (mode === 'rarete') {
      // Rareté : moins il y a de stations connues dans ce dept, plus il est rare.
      out.sort(function (a, b) {
        return ((a.known || []).length) - ((b.known || []).length)
          || String(a.dept).localeCompare(String(b.dept));
      });
    } else {
      // Fréquence : le dept dont le donneur le plus proche minimise le QSY d'abord.
      out.sort(function (a, b) {
        return _ecartMin(a, freqMhz) - _ecartMin(b, freqMhz)
          || String(a.dept).localeCompare(String(b.dept));
      });
      // Et à l'intérieur d'un dept, les donneurs par proximité de fréquence.
      out.forEach(function (t) {
        t.spotted.sort(function (x, y) {
          var ex = freqMhz ? Math.abs(_giverMhz(x) - freqMhz) : _giverMhz(x);
          var ey = freqMhz ? Math.abs(_giverMhz(y) - freqMhz) : _giverMhz(y);
          return ex - ey;
        });
      });
    }
    return out;
  }

  window.LogxDeptTodo = { trier: trier };
})();
