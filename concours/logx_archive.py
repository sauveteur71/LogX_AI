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
import datetime
import os
import json
import re
from logx_utils import utcnow, safe_filename
# A10 (docs/FEUILLE_DE_ROUTE.md) : calc_total_score() applique le compte de
# multiplicateurs au "score à battre" — sans quoi une édition archivée d'un
# concours à multiplicateur (CQ WW, WPX, ARRL DX...) affichait juste la
# somme des points par QSO, jamais multipliée.
from logx_definitions import CONTEST_DEFINITIONS
from logx_scoring import calc_total_score

ARCHIVE_DIR = 'archives'


def _safe(s):
    return safe_filename(s, 40)


def archive_log(qsos, contest_id, cfg=None, qtc_series=None, when=None, declared_score=None,
                date_reliable=True):
    """Écrit une archive permanente du log d'un concours. Retourne un dict
    {ok, folder, qso_count, files} ou {ok: False, error}.
    qtc_series : séries QTC (WAE, voir logx_storage.qtc_log) déjà filtrées par
    l'appelant sur LA MÊME portée que `qsos` — sans quoi le Cabrillo archivé
    n'a aucune ligne "QTC:" (règlement WAE : la moitié des points possibles).
    when : date à inscrire dans le nom du dossier (et donc dans `date`/l'année
    retournés par list_archives()) — par défaut l'instant présent (archivage
    normal, juste après un concours tenu en direct). import_external_log()
    passe ici la VRAIE date du log importé, sans quoi une édition de 2019
    importée aujourd'hui se ferait passer pour un record de cette année.
    declared_score : score total DÉCLARÉ de cette édition (import_external_log
    : CLAIMED-SCORE du fichier importé, ou score saisi à la main) — écrit
    dans meta.json et utilisé tel quel (Cabrillo archivé, resume.txt,
    best_for_contest()) plutôt que recalculé depuis des QSO reconstruits sans
    toutes leurs données d'origine (pas de locator, échange minimal — voir
    logx_scoring.calc_total_score, qui suppose un log natif complet). None
    pour un archivage natif (juste après un concours tenu en direct dans
    LogX AI) : le score est alors calculé normalement depuis les QSO."""
    qsos = list(qsos or [])
    if not qsos:
        return {'ok': False, 'error': 'Aucun QSO à archiver pour ce concours'}
    cfg = cfg or {}
    now = when or utcnow()
    call = (cfg.get('callsign_contest') or cfg.get('callsign') or 'LOG').upper()
    name = f"{_safe(contest_id or 'CONTEST')}_{now.strftime('%Y%m%d-%H%M%S')}"
    folder = os.path.join(ARCHIVE_DIR, name)
    i = 2
    while os.path.isdir(folder):
        folder = os.path.join(ARCHIVE_DIR, f"{name}-{i}")
        i += 1
    name = os.path.basename(folder)
    try:
        os.makedirs(folder)
    except Exception as e:
        return {'ok': False, 'error': f"Création du dossier impossible : {e}"}

    files = []
    # 1. Log brut JSON (ré-importable)
    _write(os.path.join(folder, 'log.json'),
           json.dumps(qsos, ensure_ascii=False, indent=1))
    files.append('log.json')

    # 1b. Score déclaré (import d'un log externe) : préservé tel quel plutôt
    # que recalculé — voir docstring declared_score ci-dessus.
    # date_reliable=False : import d'un log SANS date exploitable — le dossier
    # porte la date du JOUR faute de mieux, mais on le TRACE dans meta.json pour
    # que best_for_contest n'en déduise AUCUNE année (sinon une édition de 2019
    # sans QSO_DATE passe pour un record de l'année courante).
    if declared_score is not None or not date_reliable:
        meta = {}
        if declared_score is not None:
            meta['declared_score'] = declared_score
        if not date_reliable:
            meta['date_reliable'] = False
        _write(os.path.join(folder, 'meta.json'),
               json.dumps(meta, ensure_ascii=False))
        files.append('meta.json')

    # 2. Cabrillo + ADIF (réutilise le moteur d'export)
    try:
        import logx_export as export
        from logx_definitions import CONTEST_DEFINITIONS
        cdef = CONTEST_DEFINITIONS.get(contest_id, {})
        base = f"{_safe(call)}_{_safe(contest_id or 'ALL')}"
        _write(os.path.join(folder, base + '.cbr'),
               export.build_cabrillo(qsos, cdef, cfg, qtc_series, claimed_override=declared_score))
        try:
            import logx_awards as awards
            _conf = awards._load_confirmations()
        except Exception:
            _conf = None
        _write(os.path.join(folder, base + '.adi'),
               export.build_adif(qsos, cfg, confirmations=_conf, completer=True))
        # CSV (tableur / récupération) — jumeau serveur du CSV client.
        _write(os.path.join(folder, base + '.csv'), export.build_csv(qsos, cfg))
        files += [base + '.cbr', base + '.adi', base + '.csv']
    except Exception as e:
        print(f"[ARCHIVE] Exports non générés : {e}")

    # 3. Résumé lisible
    _write(os.path.join(folder, 'resume.txt'),
           _summary(qsos, contest_id, call, now, declared_score=declared_score))
    files.append('resume.txt')

    print(f"[ARCHIVE] {len(qsos)} QSO archives dans {folder}")
    return {'ok': True, 'folder': folder, 'name': name,
            'qso_count': len(qsos), 'files': files}


def _write(path, text):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def _summary(qsos, contest_id, call, now, declared_score=None):
    by_band = {}
    for q in qsos:
        b = str(q.get('band', '?'))
        by_band[b] = by_band.get(b, 0) + 1
    if declared_score is not None:
        score = declared_score
    else:
        cdef = CONTEST_DEFINITIONS.get(contest_id, {})
        score = calc_total_score(qsos, cdef)
    dates = sorted({str(q.get('date', '')) for q in qsos if q.get('date')})
    lines = [
        "LogX AI — archive de concours",
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


def load_archive_qsos(folder):
    """QSO bruts d'une archive (log.json d'un dossier retourné par
    list_archives()), ou None si absent/illisible -- même pattern de lecture
    que celui déjà écrit en ligne dans best_for_contest(), factorisé ici pour
    build_memory_digest() (logx_coach.py) qui doit le faire deux fois par
    appel (digest du concours + digest d'une entité DXCC sur TOUTES les
    archives)."""
    logp = os.path.join(folder, 'log.json')
    if not os.path.exists(logp):
        return None
    try:
        with open(logp, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _load_meta(folder):
    """meta.json d'une archive (voir archive_log:declared_score), ou None si
    absent/illisible — absent pour toute archive NATIVE (juste après un
    concours tenu en direct dans LogX AI), présent seulement pour un log
    externe importé avec un score déclaré."""
    metap = os.path.join(folder, 'meta.json')
    if not os.path.exists(metap):
        return None
    try:
        with open(metap, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def best_for_contest(contest_id):
    """Meilleur nombre de QSO et meilleur score déjà réalisés pour CE concours,
    toutes éditions archivées confondues (pas forcément la même année pour les
    deux records) -- "score à battre" affiché à la sélection du concours en
    CONFIG. None si contest_id est vide ou qu'aucune archive ne correspond."""
    if not contest_id:
        return None
    best_qso, best_qso_year = 0, None
    best_points, best_points_year = 0, None
    editions = 0
    cdef = CONTEST_DEFINITIONS.get(contest_id, {})
    for info in list_archives():
        if info.get('contest') != contest_id:
            continue
        qsos = load_archive_qsos(info['folder'])
        if qsos is None:
            continue
        editions += 1
        # Score déclaré (import d'un log externe) préservé tel quel, jamais
        # recalculé depuis des QSO reconstruits sans toutes leurs données
        # d'origine — voir docstring declared_score de archive_log().
        meta = _load_meta(info['folder'])
        if meta and meta.get('declared_score') is not None:
            points = meta['declared_score']
        else:
            points = calc_total_score(qsos, cdef)
        # Une archive dont la date n'est PAS fiable (import sans QSO_DATE : le
        # dossier porte la date du jour faute de mieux) ne revendique AUCUNE
        # année, sinon elle fausse le « record de l'année ».
        if meta and meta.get('date_reliable') is False:
            year = None
        else:
            year = (info.get('date') or '')[:4] or None
        if len(qsos) > best_qso:
            best_qso, best_qso_year = len(qsos), year
        if points > best_points:
            best_points, best_points_year = points, year
    if editions == 0:
        return None
    return {'ok': True, 'contest': contest_id, 'editions': editions,
            'best_qso': best_qso, 'best_qso_year': best_qso_year,
            'best_points': best_points, 'best_points_year': best_points_year}


_CABRILLO_FREQ_TO_BAND = {}  # rempli au 1er appel (voir _cabrillo_freq_to_band)


def _cabrillo_freq_to_band(freq):
    """Inverse de logx_export.CABRILLO_FREQ (fréquence Cabrillo → bande
    interne). Import tardif pour éviter un cycle logx_export→logx_archive
    (aucun des deux n'importe l'autre aujourd'hui, mais autant rester
    prudent -- logx_export importe déjà pas mal de choses)."""
    if not _CABRILLO_FREQ_TO_BAND:
        from logx_export import CABRILLO_FREQ
        _CABRILLO_FREQ_TO_BAND.update({v: k for k, v in CABRILLO_FREQ.items()})
    return _CABRILLO_FREQ_TO_BAND.get(freq, freq)


_CABRILLO_MODE_TO_INTERNAL = {'PH': 'SSB', 'CW': 'CW', 'RY': 'RTTY', 'DG': 'FT8', 'FM': 'FM'}


def _parse_cabrillo(text):
    """Parseur minimal de Cabrillo (lecture seule), symétrique de
    logx_export.build_cabrillo() côté écriture : QSO: freq mode date time
    mycall <échange envoyé> dxcall <échange reçu>. Les 4 premiers jetons
    après "QSO:" sont à POSITION FIXE (norme Cabrillo v3) -- fiables. Le
    reste (indicatif DX, détail de l'échange) est de longueur VARIABLE selon
    le règlement (cabrillo_exchange) et volontairement IGNORÉ : ce parseur ne
    sert qu'à alimenter archive_log() pour le "score à battre"
    (best_for_contest() ne lit que le NOMBRE de QSO et leurs `points`, jamais
    l'indicatif/l'échange d'une archive). Renvoie (qsos, claimed_score,
    contest_name) -- contest_name : valeur brute de la ligne CONTEST: de
    l'en-tête (ex. "CQ-WW-CW"), '' si absente, à passer à guess_contest_id()."""
    qsos = []
    claimed = None
    contest_name = ''
    for line in (text or '').splitlines():
        line = line.strip()
        upper = line.upper()
        if upper.startswith('CLAIMED-SCORE:'):
            digits = re.sub(r'[^0-9]', '', line.split(':', 1)[1])
            if digits:
                claimed = int(digits)
        elif upper.startswith('CONTEST:'):
            contest_name = line.split(':', 1)[1].strip()
        elif upper.startswith('QSO:'):
            parts = line.split()
            if len(parts) < 5:
                continue
            freq, mode, date, time = parts[1], parts[2], parts[3], parts[4]
            qsos.append({
                'band': _cabrillo_freq_to_band(freq),
                'mode': _CABRILLO_MODE_TO_INTERNAL.get(mode.upper(), mode.upper()),
                'date': date.replace('-', ''), 'time': time,
            })
    return qsos, claimed, contest_name


def _normalize_contest_key(s):
    """Normalise un identifiant de concours pour comparaison entre
    conventions de nommage différentes (espaces/underscores -> tiret, casse
    ignorée) : 'REF 160M', 'ref_160m' et 'REF-160M' doivent tous se
    reconnaître."""
    return re.sub(r'[\s_]+', '-', str(s or '').strip().upper())


def guess_contest_id(raw_name):
    """Devine l'identifiant interne LogX AI d'un concours à partir d'un nom
    brut lu dans un fichier externe (ligne CONTEST: d'un Cabrillo, tag
    CONTEST_ID d'un ADIF) -- chaque logiciel a sa propre convention pour ce
    champ, jamais garantie identique à l'identifiant interne. Comparaison
    normalisée contre CONTEST_DEFINITIONS : soit la clé interne elle-même
    (la grande majorité des concours n'ont pas de cabrillo_name distinct --
    voir build_cabrillo(), qui retombe alors sur le nom interne), soit le
    cabrillo_name explicite (une douzaine de concours dont le code officiel
    diverge, ex. CQ-WW-CW). None si rien ne correspond -- l'appelant doit
    alors demander une sélection manuelle, jamais deviner au hasard."""
    key = _normalize_contest_key(raw_name)
    if not key:
        return None
    from logx_definitions import CONTEST_DEFINITIONS
    for cid, cdef in CONTEST_DEFINITIONS.items():
        if _normalize_contest_key(cid) == key:
            return cid
        cab = (cdef or {}).get('cabrillo_name')
        if cab and _normalize_contest_key(cab) == key:
            return cid
    return None


def import_external_log(text, fmt, contest_id=None, cfg=None, manual_score=None):
    """Importe un log EXTERNE (ADIF ou Cabrillo) d'une édition passée d'un
    concours jamais logguée dans LogX AI, comme archive permanente -- pour
    que best_for_contest() en tienne compte dans le "score à battre" (demande
    F4GLD 10/08/2026 : « j'ai des logs de concours que je n'ai pas encore
    importé en stock »). N'écrit QUE dans archives/, jamais dans le log
    actif -- sans rapport avec /log/import_adif/* (qui fusionne dans la
    session en cours).

    fmt : 'adif' ou 'cabrillo'.
    contest_id : optionnel (demande F4GLD 10/08/2026 : « sans avoir à
    choisir le concours »). Si absent/vide, tenté automatiquement depuis le
    fichier lui-même (ligne CONTEST: d'un Cabrillo, tag CONTEST_ID d'un
    ADIF) via guess_contest_id() -- jamais une déduction hasardeuse : sans
    ce champ dans le fichier, ou si sa valeur ne correspond à aucun concours
    connu, l'appel échoue explicitement (needs_manual=True) plutôt que
    d'archiver sous un concours probablement faux.
    manual_score : impose le score total de cette édition. Obligatoire en
    pratique pour l'ADIF (qui ne transporte pas de points par QSO côté LogX
    AI) ; en Cabrillo, sert de correctif si CLAIMED-SCORE est absent ou
    erroné -- sinon le CLAIMED-SCORE du fichier fait foi."""
    contest_id = (contest_id or '').strip()
    fmt = (fmt or '').strip().lower()
    detected = False
    if fmt == 'adif':
        from logx_import import parse_adif_to_qsos
        qsos, _errors = parse_adif_to_qsos(text or '')
        claimed = None
        raw_contest_name = next((q.get('contest') for q in qsos if q.get('contest')), '')
    elif fmt == 'cabrillo':
        qsos, claimed, raw_contest_name = _parse_cabrillo(text or '')
    else:
        return {'ok': False, 'error': f"Format non pris en charge : {fmt!r}"}
    if not qsos:
        hint = ''
        if fmt == 'adif' and re.search(r'(?im)^(START-OF-LOG:|CONTEST:)', text or ''):
            hint = ' -- ce fichier ressemble a un Cabrillo, verifie le format selectionne'
        elif fmt == 'cabrillo' and re.search(r'(?i)<eoh>|<adif_ver', text or ''):
            hint = ' -- ce fichier ressemble a un ADIF, verifie le format selectionne'
        return {'ok': False, 'error': 'Aucun QSO reconnu dans ce fichier' + hint}

    if not contest_id:
        guessed = guess_contest_id(raw_contest_name)
        if not guessed:
            return {'ok': False, 'needs_manual': True,
                    'error': 'Concours non détecté automatiquement -- choisis-le dans la liste'}
        contest_id, detected = guessed, True

    score = manual_score if manual_score is not None else (claimed or 0)
    # Le détail par-QSO du score réel de l'époque est perdu (ADIF n'en a
    # jamais eu, Cabrillo ne donne qu'un total) : `score` est le seul total
    # connu et fiable pour cette édition -- transmis tel quel à archive_log()
    # (declared_score), jamais reconstitué en points par QSO puis re-multiplié
    # par calc_total_score() (qui suppose un log natif complet, avec locator
    # et échange réels -- absents ici). q['points'] reste à 0 partout : ces
    # QSO n'ont individuellement aucun score connu, seul le TOTAL l'est.
    for q in qsos:
        q.setdefault('points', 0)

    dates = sorted({str(q.get('date', '')) for q in qsos if q.get('date')})
    when = None
    if dates:
        try:
            when = datetime.datetime.strptime(dates[0][:8], '%Y%m%d')
        except ValueError:
            when = None
    res = archive_log(qsos, contest_id, cfg or {}, when=when, declared_score=score,
                      date_reliable=when is not None)
    if res.get('ok'):
        res['contest'] = contest_id
        res['detected'] = detected
        # Aucune date exploitable dans le log importé : l'archive est datée du
        # jour faute de mieux — on le SIGNALE (plus de silence) pour que l'UI
        # puisse proposer à l'opérateur de saisir la vraie date.
        if when is None:
            res['date_missing'] = True
    return res


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
        # (?:-\d+)? : suffixe de désambiguïsation ajouté par archive_log() en
        # cas de collision (2 imports du même concours à la même date de 1er
        # QSO, ex. '..._20260810-000000-2') — sans lui, le regex exigeant une
        # fin exacte en HHMMSS ($) ne matchait plus jamais, et l'archive
        # perdait silencieusement son contest/date affichés.
        m = re.match(r'(.+)_(\d{8})-(\d{6})(?:-\d+)?$', name)
        if m:
            info['contest'] = m.group(1)
            info['date'] = f"{m.group(2)[:4]}-{m.group(2)[4:6]}-{m.group(2)[6:8]} {m.group(3)[:2]}:{m.group(3)[2:4]}"
        out.append(info)
    out.sort(key=lambda a: a['name'], reverse=True)
    return out
