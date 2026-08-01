# -*- coding: utf-8 -*-
"""Archivage des logs de concours dans un dossier permanent.

Chaque concours terminé est conservé dans son propre sous-dossier de
`archives/`, INDÉPENDAMMENT du log actif : passer à un autre concours ou
réinitialiser le log n'y touche plus jamais. Chaque archive contient :
  - log.json           : les QSO bruts (ré-importables)
  - <call>_<id>.cbr    : Cabrillo prêt pour la soumission
  - <call>_<id>.adi    : ADIF (import dans QRZ, LoTW, autre logiciel)
  - resume.txt         : score, nombre de QSO, dates, répartition par bande

Le dossier `archives/` vit dans le répertoire de travail (le dossier de
données utilisateur en mode application, cf. logx_bootstrap).
"""
import os
import json
import re
from logx_utils import utcnow

ARCHIVE_DIR = 'archives'


def _safe(s):
    return re.sub(r'[^A-Za-z0-9_.-]', '_', str(s or ''))[:40]


def archive_log(qsos, contest_id, cfg=None, qtc_series=None):
    """Écrit une archive permanente du log d'un concours. Retourne un dict
    {ok, folder, qso_count, files} ou {ok: False, error}.
    qtc_series : séries QTC (WAE, voir logx_storage.qtc_log) déjà filtrées par
    l'appelant sur LA MÊME portée que `qsos` — sans quoi le Cabrillo archivé
    n'a aucune ligne "QTC:" (règlement WAE : la moitié des points possibles)."""
    qsos = list(qsos or [])
    if not qsos:
        return {'ok': False, 'error': 'Aucun QSO à archiver pour ce concours'}
    cfg = cfg or {}
    now = utcnow()
    call = (cfg.get('callsign_contest') or cfg.get('callsign') or 'LOG').upper()
    name = f"{_safe(contest_id or 'CONTEST')}_{now.strftime('%Y%m%d-%H%M')}"
    folder = os.path.join(ARCHIVE_DIR, name)
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception as e:
        return {'ok': False, 'error': f"Création du dossier impossible : {e}"}

    files = []
    # 1. Log brut JSON (ré-importable)
    _write(os.path.join(folder, 'log.json'),
           json.dumps(qsos, ensure_ascii=False, indent=1))
    files.append('log.json')

    # 2. Cabrillo + ADIF (réutilise le moteur d'export)
    try:
        import logx_export as export
        from logx_definitions import CONTEST_DEFINITIONS
        cdef = CONTEST_DEFINITIONS.get(contest_id, {})
        base = f"{_safe(call)}_{_safe(contest_id or 'ALL')}"
        _write(os.path.join(folder, base + '.cbr'),
               export.build_cabrillo(qsos, cdef, cfg, qtc_series))
        _write(os.path.join(folder, base + '.adi'),
               export.build_adif(qsos, cfg))
        files += [base + '.cbr', base + '.adi']
    except Exception as e:
        print(f"[ARCHIVE] Exports non générés : {e}")

    # 3. Résumé lisible
    _write(os.path.join(folder, 'resume.txt'), _summary(qsos, contest_id, call, now))
    files.append('resume.txt')

    print(f"[ARCHIVE] {len(qsos)} QSO archives dans {folder}")
    return {'ok': True, 'folder': folder, 'name': name,
            'qso_count': len(qsos), 'files': files}


def _write(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def _summary(qsos, contest_id, call, now):
    by_band = {}
    score = 0
    for q in qsos:
        b = str(q.get('band', '?'))
        by_band[b] = by_band.get(b, 0) + 1
        score += q.get('points', 0) or 0
    dates = sorted({str(q.get('date', '')) for q in qsos if q.get('date')})
    lines = [
        f"LogX AI — archive de concours",
        f"Concours   : {contest_id}",
        f"Station    : {call}",
        f"Archivé le : {now.strftime('%Y-%m-%d %H:%M')} UTC",
        f"Dates QSO  : {', '.join(dates) if dates else '?'}",
        f"QSO totaux : {len(qsos)}",
        f"Score      : {score} points",
        "",
        "Répartition par bande :",
    ]
    for b, n in sorted(by_band.items()):
        lines.append(f"  {b} MHz : {n} QSO")
    return '\n'.join(lines) + '\n'


def list_archives():
    """Liste les archives existantes (plus récentes d'abord)."""
    out = []
    if not os.path.isdir(ARCHIVE_DIR):
        return out
    for name in os.listdir(ARCHIVE_DIR):
        folder = os.path.join(ARCHIVE_DIR, name)
        if not os.path.isdir(folder):
            continue
        info = {'name': name, 'folder': folder, 'qso_count': 0, 'files': []}
        try:
            info['files'] = sorted(os.listdir(folder))
            logp = os.path.join(folder, 'log.json')
            if os.path.exists(logp):
                with open(logp, encoding='utf-8') as f:
                    info['qso_count'] = len(json.load(f))
        except Exception:
            pass
        m = re.match(r'(.+)_(\d{8})-(\d{4})$', name)
        if m:
            info['contest'] = m.group(1)
            info['date'] = f"{m.group(2)[:4]}-{m.group(2)[4:6]}-{m.group(2)[6:8]} {m.group(3)[:2]}:{m.group(3)[2:]}"
        out.append(info)
    out.sort(key=lambda a: a['name'], reverse=True)
    return out
