/* logx_dept_grid.js — Grille départements 00–99 (clic direct) pour la saisie.
 *
 * Inspiration ergonomique : le pavé départements des logs de terrain (un clic
 * remplit le département reçu, sans lâcher le clavier — demande F4GLD 25/08).
 *
 * PÉRIMÈTRE STRICT (vérifié) : la grille ne sert QUE quand l'échange REÇU EST un
 * département (`currentExchange.label_r` contient 'DEPT' : Coupe du REF / CDF HF,
 * 160 m, F9NL, UFT…). Elle remplit alors `#inputNumRcvd` (le champ « DEPT RCU »,
 * lu par logx_departments.dept_from_exchange). En VHF/UHF l'échange reçu est une
 * SÉRIE et le département vient du LOCATOR (dérivé, jamais saisi) : la grille
 * reste cachée pour ne JAMAIS écrire un département dans une série.
 *
 * Glue PURE et testable (codesMetro / doitAfficher) + rendu DOM. Testé en V8
 * (test_dept_grid.py). Inclusion : <script src="logx_dept_grid.js"></script>.
 */
(function () {
  'use strict';

  // Départements métropolitains français — INSEE, Code officiel géographique :
  // 01–95, la Corse scindée en 2A/2B (remplace le 20). Miroir CLIENT de la liste
  // serveur logx_departments.DEPARTMENTS (métropole) — valeur SOURCÉE, jamais
  // inventée. Les DOM (971–976, 3 chiffres) ne sont pas dans cette grille : ce
  // sont des séries au sens de l'échange (voir _DEPTS_ECHANGE), pas des cases.
  function codesMetro() {
    var out = [];
    for (var i = 1; i <= 95; i++) {
      if (i === 20) { out.push('2A', '2B'); }        // Corse
      else { out.push(String(i).padStart(2, '0')); }
    }
    return out;
  }

  // La grille n'a de sens que si l'échange REÇU est un département (label_r
  // contient 'DEPT'). Sinon (série VHF/UHF), rester cachée.
  function doitAfficher(labelR) {
    return String(labelR || '').toUpperCase().indexOf('DEPT') !== -1;
  }

  // Construit la grille UNE fois dans `container` et câble le clic -> onPick(code).
  // Idempotent (ne re-remplit pas si déjà peuplé). Non testé unitairement (DOM).
  function render(container, onPick) {
    if (!container || container.childElementCount) { return; }
    codesMetro().forEach(function (code) {
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'dept-cell';
      b.textContent = code; b.setAttribute('data-dept', code);
      b.title = 'Département ' + code + ' — remplit le champ reçu';
      b.addEventListener('click', function () { if (typeof onPick === 'function') { onPick(code); } });
      container.appendChild(b);
    });
  }

  // Surligne la case correspondant au département courant (ou aucune si vide).
  function surligner(container, code) {
    if (!container || !container.querySelectorAll) { return; }
    var c = String(code || '').toUpperCase();
    var cells = container.querySelectorAll('.dept-cell');
    for (var i = 0; i < cells.length; i++) {
      cells[i].classList.toggle('on', cells[i].getAttribute('data-dept') === c);
    }
  }

  window.LogxDeptGrid = {
    codesMetro: codesMetro,
    doitAfficher: doitAfficher,
    render: render,
    surligner: surligner
  };
})();
