# -*- coding: utf-8 -*-
"""Valide CONTEST_DEFINITIONS contre contest_schema.json.

Usage : python logx_validate.py
Sort avec le code 0 si tout est conforme, 1 sinon.

Utilise la lib 'jsonschema' si elle est installée (validation complète),
sinon un contrôle minimal maison (champs requis, enums, types de base).
C'est le garde-fou des Phases 2/3 : toute définition ajoutée à la main,
importée de WA7BNM ou extraite par l'IA doit passer ce contrôle.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from logx_definitions import CONTEST_DEFINITIONS

with open(os.path.join(HERE, 'contest_schema.json'), encoding='utf-8') as f:
    SCHEMA = json.load(f)


def validate_with_jsonschema():
    import jsonschema
    errors = []
    validator = jsonschema.Draft202012Validator(SCHEMA)
    for cid, cdef in CONTEST_DEFINITIONS.items():
        for err in validator.iter_errors(cdef):
            path = '.'.join(str(p) for p in err.absolute_path) or '(racine)'
            errors.append(f"{cid}: {path}: {err.message}")
    return errors


def _check_scoring(sc, props):
    """Vérifie un bloc scoring : forme 'type' historique OU 'bricks' Phase 2.
    Les briques sont validées contre le moteur lui-même (logx_scoring.py) pour
    qu'un prédicat ou une famille de multiplicateur inconnus soient refusés."""
    errs = []
    bricks = sc.get('bricks')
    st = sc.get('type')
    if bricks is None and st is None:
        errs.append("scoring doit avoir 'type' (historique) ou 'bricks' (Phase 2)")
        return errs
    if st is not None:
        st_enum = props['scoring']['properties']['type']['enum']
        if st not in st_enum:
            errs.append(f"scoring.type '{st}' absent de l'enum du schema")
    if bricks is not None:
        from logx_scoring import PREDICATES, MULT_EVALUATORS
        if not isinstance(bricks, dict):
            return errs + ["scoring.bricks doit être un objet"]
        rules = bricks.get('points')
        if not isinstance(rules, list) or not rules:
            errs.append("bricks.points doit être une liste non vide de règles")
        else:
            for i, rule in enumerate(rules):
                when = rule.get('when', 'always')
                when_list = when if isinstance(when, (list, tuple)) else [when]
                # `not isinstance(w, str)` d'ABORD : un 'when' malformé (dict,
                # liste imbriquée…) rendait `w not in PREDICATES` (un dict)
                # TypeError: unhashable, faisant PLANTER la validation d'une
                # définition importée/extraite par l'IA au lieu de la refuser
                # proprement. Tout prédicat non-chaîne est simplement « inconnu ».
                unknown = [w for w in when_list if not isinstance(w, str) or w not in PREDICATES]
                if unknown:
                    errs.append(f"bricks.points[{i}].when {unknown} inconnu du moteur "
                                f"(connus : {sorted(PREDICATES)})")
                v = rule.get('points')
                ok = (isinstance(v, (int, float)) or v == 'per_km'
                      or (isinstance(v, dict) and 'param' in v))
                if not ok:
                    errs.append(f"bricks.points[{i}].points invalide : {v!r}")
                b = rule.get('bands')
                if b is not None and (not isinstance(b, list)
                                      or not all(isinstance(x, str) for x in b)):
                    errs.append(f"bricks.points[{i}].bands doit être une liste de chaînes MHz")
                p = rule.get('prefix_in')
                if p is not None and (not isinstance(p, list)
                                      or not all(isinstance(x, str) for x in p)):
                    errs.append(f"bricks.points[{i}].prefix_in doit être une liste de préfixes")
                m = rule.get('modes')
                if m is not None and (not isinstance(m, list)
                                      or not all(isinstance(x, str) for x in m)):
                    errs.append(f"bricks.points[{i}].modes doit être une liste de modes (ex. ['CW'])")
        weights = bricks.get('mult_weight_by_band')
        if weights is not None:
            if not isinstance(weights, dict) or not all(
                    isinstance(k, str) and isinstance(v, (int, float))
                    for k, v in weights.items()):
                errs.append("bricks.mult_weight_by_band doit être {'bande': poids} "
                            "(ex. {'3.5': 4, '7': 3})")
        mult = bricks.get('multiplier')
        if isinstance(mult, dict):
            kind = mult.get('kind')
            if kind not in MULT_EVALUATORS:
                errs.append(f"bricks.multiplier.kind '{kind}' inconnu du moteur "
                            f"(connus : {sorted(MULT_EVALUATORS)})")
        elif mult is not None:
            errs.append("bricks.multiplier doit être un objet {'kind': ...} ou null")
        validity = bricks.get('validity')
        if validity is not None:
            if isinstance(validity, dict):
                p = validity.get('prefix_in')
                if not isinstance(p, list) or not all(isinstance(x, str) for x in p):
                    errs.append("bricks.validity objet : clé 'prefix_in' (liste de préfixes) requise")
            elif validity not in PREDICATES:
                errs.append(f"bricks.validity '{validity}' inconnu du moteur")
    return errs


def validate_definition(cdef, cid='?'):
    """Valide UNE définition de concours (dict) contre le schema/moteur.
    Retourne la liste des erreurs (vide = conforme). C'est le garde-fou
    appelé sur les propositions de l'IA (Phase 3) avant relecture humaine."""
    props = SCHEMA['properties']
    required = SCHEMA['required']
    known = set(props)
    errors = []
    if not isinstance(cdef, dict):
        return [f"{cid}: la définition doit être un objet JSON"]
    for k in required:
        if k not in cdef:
            errors.append(f"{cid}: champ requis manquant '{k}'")
    for k in cdef:
        if k not in known:
            errors.append(f"{cid}: champ inconnu '{k}' (ajouter au schema ?)")
    dr = cdef.get('date_rule')
    if dr is not None:
        from logx_rules import DATE_RULE_RE
        if not isinstance(dr, str) or not DATE_RULE_RE.match(dr):
            errors.append(f"{cid}: date_rule '{dr}' hors grammaire "
                          "(voir logx_rules.py:DATE_RULE_PATTERN)")
    lf = cdef.get('log_format')
    if lf is not None and lf not in props['log_format']['enum']:
        errors.append(f"{cid}: log_format '{lf}' absent de l'enum du schema")
    if lf == 'CABRILLO' and not cdef.get('cabrillo_name'):
        errors.append(f"{cid}: log_format='CABRILLO' mais 'cabrillo_name' absent — "
                       "le CONTEST: du fichier exporté portera l'identifiant interne "
                       "et risque d'être rejeté par le robot de dépôt (voir A04)")
    sc = cdef.get('scoring')
    if not isinstance(sc, dict):
        errors.append(f"{cid}: scoring doit être un objet")
    else:
        errors.extend(f"{cid}: {e}" for e in _check_scoring(sc, props))
    for k, typ in [('bands', list), ('modes', list), ('name', str),
                   ('organizer', str), ('exchange', str)]:
        if k in cdef and not isinstance(cdef[k], typ):
            errors.append(f"{cid}: '{k}' devrait être {typ.__name__}")
    return errors


def validate_minimal():
    """Contrôle réduit sans dépendance : requis, enums, types simples."""
    errors = []
    for cid, cdef in CONTEST_DEFINITIONS.items():
        errors.extend(validate_definition(cdef, cid))
    return errors


if __name__ == '__main__':
    try:
        errors = validate_with_jsonschema()
        mode = 'jsonschema (validation complète)'
    except ImportError:
        errors = validate_minimal()
        mode = 'minimal (pip install jsonschema pour la validation complète)'

    print(f"Validation de {len(CONTEST_DEFINITIONS)} concours — mode {mode}")
    if errors:
        for e in errors:
            print(f"  ERREUR  {e}")
        print(f"\n{len(errors)} erreur(s).")
        sys.exit(1)
    print("Tout est conforme au schema.")
    sys.exit(0)
