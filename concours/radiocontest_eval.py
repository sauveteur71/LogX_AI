# -*- coding: utf-8 -*-
"""Corpus d'évaluation de l'extraction IA de règlements (Phase 3).

Rejoue des règlements RÉELS dont les champs attendus ont été vérifiés à la
main, et note chaque extraction champ par champ. À lancer après toute
modification du prompt ou du pipeline pour mesurer (et non deviner) le gain.

Usage :
  set ANTHROPIC_API_KEY=sk-...          (ou clé du provider configuré)
  python eval_extraction.py             — tout le corpus
  python eval_extraction.py --no-verify — sans la passe de vérification
                                          (mesure l'apport de la vérification)
  python eval_extraction.py --mock      — teste le harnais sans appel réseau

Ajouter un cas : une entrée dans CORPUS avec 'url' OU 'file', et 'expect' =
liste de contrôles {path, equals|contains|exists|matches}.
Les chemins sont en notation pointée : 'scoring.bricks.validity'.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── CORPUS — champs attendus vérifiés à la main ─────────────────────────────
CORPUS = [
    {
        'name': 'REF Rallye des Points Hauts (PDF local, français)',
        'file': os.path.join('..', 'reg_rph_fr_20250312.pdf'),
        'expect': [
            # _14h optionnel : le RPH démarre à 14h00 UTC, la précision est un plus
            {'path': 'date_rule', 'matches': r'^first_saturday_july(_14h)?$'},
            {'path': 'organizer', 'matches': 'REF'},
            {'path': 'modes', 'contains': ['SSB']},
            {'path': 'log_format', 'equals': 'EDI'},
            {'path': 'duration_h', 'equals': 24},
            # 1 pt/km : type historique 'km' OU briques per_km
            {'path': 'scoring', 'any_of': [
                {'path': 'scoring.type', 'equals': 'km'},
                {'path': 'scoring.bricks.points.0.points', 'equals': 'per_km'},
            ]},
        ],
    },
    {
        'name': 'DARC WAE DX Contest (page HTML, anglais)',
        'url': 'https://www.darc.de/der-club/referate/conteste/wae-dx-contest/en/wae-rules/',
        'expect': [
            {'path': 'date_rule', 'equals': 'second_full_weekend_august'},
            {'path': 'organizer', 'matches': 'DARC'},
            {'path': 'bands', 'contains': ['3.5', '7', '14', '21', '28']},
            {'path': 'duration_h', 'equals': 48},
            {'path': 'log_format', 'equals': 'CABRILLO'},
            # Le piège découvert en usage réel : la restriction EU↔DX doit être ENCODÉE
            {'path': 'scoring.bricks.validity', 'equals': 'different_continent'},
            # Les mults pondérés par bande doivent être encodés
            {'path': 'scoring.bricks.mult_weight_by_band', 'exists': True},
        ],
    },
    {
        'name': 'CQ World Wide DX (page HTML, anglais)',
        'url': 'https://www.cqww.com/rules.htm',
        'expect': [
            {'path': 'date_rule', 'matches': 'last_full_weekend_(october|november)'},
            {'path': 'bands', 'contains': ['14']},
            {'path': 'duration_h', 'equals': 48},
            {'path': 'log_format', 'equals': 'CABRILLO'},
            {'path': 'exchange', 'matches': '(?i)zone'},
            {'path': 'scoring', 'any_of': [
                {'path': 'scoring.type', 'equals': 'zone_country_per_band'},
                {'path': 'scoring.bricks.multiplier.kind', 'equals': 'zone_dxcc'},
            ]},
        ],
    },
]

# ─── MOTEUR DU HARNAIS ───────────────────────────────────────────────────────

def _get_path(obj, path):
    cur = obj
    for part in path.split('.'):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None, False
        elif isinstance(cur, dict):
            if part not in cur:
                return None, False
            cur = cur[part]
        else:
            return None, False
    return cur, True

def _check(definition, rule):
    """Retourne (ok, détail)."""
    import re as _re
    if 'any_of' in rule:
        results = [_check(definition, r) for r in rule['any_of']]
        ok = any(r[0] for r in results)
        return ok, ' OU '.join(r[1] for r in results)
    path = rule['path']
    val, found = _get_path(definition, path)
    if 'exists' in rule:
        ok = found == rule['exists']
        return ok, f"{path} {'présent' if found else 'absent'}"
    if not found:
        return False, f"{path} absent"
    if 'equals' in rule:
        ok = val == rule['equals']
        return ok, f"{path}={val!r} (attendu {rule['equals']!r})"
    if 'contains' in rule:
        missing = [x for x in rule['contains'] if x not in (val or [])]
        return not missing, f"{path} manque {missing}" if missing else f"{path} ok"
    if 'matches' in rule:
        ok = bool(_re.search(rule['matches'], str(val)))
        return ok, f"{path}={val!r} (~ /{rule['matches']}/)"
    return False, f"règle inconnue pour {path}"

def _mock_analyze(**kwargs):
    """Cas de test du harnais : renvoie une définition volontairement imparfaite."""
    return {'ok': True, 'suggested_id': 'MOCK', 'confidence': 'high',
            'validation_errors': [], 'warnings': [], 'citations': {},
            'verification': {'issues': [], 'applied': False, 'answers': []},
            'extractor': 'mock', 'text_chars': 999, 'date_preview': '',
            'definition': {
                'name': 'Mock', 'organizer': 'REF', 'date_rule': 'first_saturday_july',
                'duration_h': 24, 'bands': ['144', '432'], 'modes': ['SSB'],
                'exchange': 'RS + N°serie + locator6', 'log_format': 'EDI',
                'scoring': {'type': 'km', 'unit': '1 pt/km'},
            }}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mock', action='store_true', help='teste le harnais sans réseau')
    ap.add_argument('--no-verify', action='store_true', help='désactive la passe de vérification')
    ap.add_argument('--only', help='ne joue que les cas dont le nom contient ce texte')
    args = ap.parse_args()

    from radiocontest_rules_ai import analyze_rules
    analyze = _mock_analyze if args.mock else analyze_rules

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    cfg = {'api_provider': 'anthropic', 'api_key': api_key}
    if not args.mock and not api_key:
        print("⚠ ANTHROPIC_API_KEY non défini — exporte ta clé ou utilise --mock")
        sys.exit(2)

    total_ok = total = 0
    for case in CORPUS:
        if args.only and args.only.lower() not in case['name'].lower():
            continue
        print(f"\n═══ {case['name']} ═══")
        kwargs = {'cfg': cfg, 'verify': not args.no_verify,
                  'contest_name': case['name']}
        if 'file' in case:
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), case['file'])
            from radiocontest_rules import extract_document_text
            with open(path, 'rb') as f:
                raw = f.read()
            if args.mock:
                kwargs['url'] = 'mock://file'
            elif raw[:5] == b'%PDF-':
                # Passer par le pipeline complet en écrivant l'URL fictive ?
                # Non : donner le texte extrait (le PDF natif nécessite une URL) —
                # sauf provider anthropic où on veut le PDF natif : analyze_rules
                # accepte les bytes via _download_bytes seulement. On extrait.
                text, _ = extract_document_text(raw, path)
                kwargs['rules_text'] = text
            else:
                text, _ = extract_document_text(raw, path)
                kwargs['rules_text'] = text
        else:
            kwargs['url'] = case['url']

        res = analyze(**kwargs)
        if not res.get('ok'):
            print(f"  ❌ ANALYSE EN ÉCHEC : {res.get('error')}")
            total += len(case['expect'])
            continue
        d = res['definition']
        print(f"  extracteur={res.get('extractor')} confiance={res.get('confidence')} "
              f"validation={'OK' if not res.get('validation_errors') else res['validation_errors']}")
        v = res.get('verification') or {}
        if v.get('issues'):
            print(f"  🔍 vérification : {len(v['issues'])} correction(s), appliquées={v.get('applied')}")
        for rule in case['expect']:
            ok, detail = _check(d, rule)
            total += 1
            total_ok += ok
            print(f"  {'✅' if ok else '❌'} {detail}")

    print(f"\n════ SCORE GLOBAL : {total_ok}/{total} champs corrects "
          f"({100*total_ok//max(total,1)}%) ════")
    sys.exit(0 if total_ok == total else 1)

if __name__ == '__main__':
    main()
