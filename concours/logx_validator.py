# -*- coding: utf-8 -*-
"""Validateur de log AVANT soumission — spécial concours REF.

Passe le log du concours actif au crible et retourne des constats classés :
  erreur     : coûtera des points ou invalidera le QSO (à corriger)
  attention  : suspect, à vérifier (busted call probable, distance anormale)
  info       : mineur (RST manquant…)

Contrôles :
  - doublons (même indicatif + même bande — règle REF : 1 QSO/station/bande)
  - indicatif plausible (motif + préfixe connu de cty.dat)
  - concours à LOCATOR (THF, km × locators) : locator présent et valide,
    distance plausible pour la bande (tropo/Es rares au-delà des seuils)
  - concours à DÉPARTEMENT (REF HF) : département reçu valide pour les
    stations françaises, numéro de série pour les étrangères
  - QSO hors de la fenêtre du concours
  - bande hors concours, champs essentiels vides

Aucune écriture : lecture seule, appelable à tout moment.
"""
import re

from logx_utils import locator_to_latlon, haversine, _LOCATOR_RE, utcnow
# IA-1 : contrôles de cohérence DÉTERMINISTES indépendants de l'activité
# (freq/bande, date/heure, RST/mode, réf d'activation), appliqués à TOUT QSO
# — y compris hors concours et en mode simple. logx_controles n'importe que
# logx_scoring/logx_activation : pas de cycle avec ce module.
from logx_controles import controles_coherence as _controles_coherence

# Indicatif de BASE : préfixe 1-3 alphanum + un chiffre + suffixe lettres.
_BASE_CALL_RE = re.compile(r'^[A-Z0-9]{1,3}[0-9][A-Z0-9]{0,5}[A-Z]$')
# Préfixe de LIEU d'un indicatif portable (EA/, F/, 9A/, PJ2/, VP2E/…).
_PREFIX_RE = re.compile(r'^[A-Z0-9]{1,4}$')
# Suffixe portable (/P /M /MM /AM /QRP /A /LH ou /chiffre(s)).
_PORT_SUFFIX_RE = re.compile(r'^(P|M|MM|AM|QRP|A|LH|[0-9]{1,2})$')


def _plausible_call(call):
    """Indicatif plausible, y compris PORTABLE avec préfixe de lieu
    (EA/F4GLD = F4GLD opérant depuis l'Espagne), suffixe (F4GLD/P, W1AW/4)
    ou les deux (EA/F4GLD/P). L'ancien motif n'acceptait qu'un suffixe et
    signalait à tort tout indicatif à préfixe étranger comme « busted call »."""
    parts = [p for p in str(call).split('/') if p]
    if not parts:
        return False
    if len(parts) == 1:
        return bool(_BASE_CALL_RE.match(parts[0]))
    # Au moins une partie doit être un indicatif complet ; les autres sont des
    # préfixes de lieu ou des suffixes portables.
    if not any(_BASE_CALL_RE.match(p) for p in parts):
        return False
    return all(_BASE_CALL_RE.match(p) or _PREFIX_RE.match(p) or _PORT_SUFFIX_RE.match(p)
               for p in parts)

# Distance au-delà de laquelle un QSO est SUSPECT sur la bande (km).
# Tropo/Es exceptionnels possibles — c'est un signal « à vérifier », pas un rejet.
MAX_KM_BY_BAND = {
    '50': 2500, '70': 1800, '144': 1400, '432': 1000,
    '1296': 800, '2320': 600, '3400': 500, '5760': 400, '10368': 300,
}
MAX_FINDINGS = 200


def _f(findings, level, code, msg, q=None, index=None):
    # Le plafond borne la liste, MAIS ne doit JAMAIS évincer une 'erreur' : ce
    # sont les constats bloquants (0 point, QSO invalide) sur lesquels s'appuie
    # `ok`/resume_controle. Sans cette exception, un volume de findings
    # attention/info (IA-1 : contrôles de cohérence) pouvait remplir le plafond
    # avant les erreurs de QSO plus tardifs -> resume_controle annonçait ok=True
    # sur un log réellement en erreur. Les erreurs restent rares : la liste ne
    # dépasse le plafond que de leur nombre.
    if len(findings) >= MAX_FINDINGS and level != 'erreur':
        return
    item = {'level': level, 'code': code, 'msg': msg}
    if q is not None:
        item['call'] = str(q.get('call', '')).upper()
        item['band'] = str(q.get('band', ''))
        item['at'] = f"{q.get('date', '')} {q.get('time', '')}".strip()
        # id du QSO : permet à l'interface d'offrir « Corriger »/« Supprimer »
        # directement sur le constat.
        if q.get('id') is not None:
            item['id'] = q.get('id')
    if index is not None:
        item['index'] = index
    findings.append(item)


def _loc_latlon(loc):
    """lat/lon d'un locator 4 ou 6 caractères (centre du carré en 4)."""
    loc = str(loc or '').strip().upper()
    if len(loc) == 4:
        loc += 'MM'
    lat, lon = locator_to_latlon(loc[:6])
    return lat, lon


def validate_log(qsos, contest_id='', cfg=None):
    """Analyse le log d'un concours. Retourne
    {contest, qso_count, findings[], counts{}, ok}."""
    cfg = cfg or {}
    # LOGBOOK SIMPLE : aucun concours actif — les contraintes propres à UN
    # concours (bandes autorisées, échange locator/département obligatoire,
    # fenêtre temporelle) n'ont pas de sens et ne doivent pas s'appliquer,
    # même si `contest` garde la trace d'un concours précédent en config.
    simple_mode = cfg.get('usage_mode') == 'simple'
    if simple_mode:
        contest_id = ''
    # Portée QSO (contest+année, voir logx_storage.cfg_scope_id), dérivée de
    # `cfg` plutôt que du seul `contest_id` brut — sans elle un QSO non tagué
    # (import générique, log perso) passait le filtre de N'IMPORTE QUEL
    # concours vérifié, et un même concours d'une année précédente non purgée
    # s'y mélangeait aussi.
    from logx_storage import qso_scope_id, cfg_scope_id
    scope_id = cfg_scope_id(cfg)
    qsos = [q for q in (qsos or [])
            if not scope_id or qso_scope_id(q) == scope_id]

    from logx_definitions import CONTEST_DEFINITIONS, bandes_du_concours
    cdef = CONTEST_DEFINITIONS.get(contest_id, {}) if contest_id else {}
    from logx_callhistory import exchange_wants
    wants = exchange_wants(cdef)
    bands_ok = set(bandes_du_concours(contest_id)) if contest_id else set()

    try:
        import logx_dxcc as dxcc
    except Exception:
        dxcc = None
    try:
        from logx_departments import dept_from_exchange
    except Exception:
        dept_from_exchange = None

    # Fenêtre du concours (mêmes sources que le coach) — non pertinente en
    # logbook simple, même si des dates de concours précédent traînent en config.
    start = end = None
    if not simple_mode:
        from logx_coach import _parse_dt
        start = _parse_dt(cfg.get('contest_start_date', ''), cdef.get('start_utc', ''))
        end = _parse_dt(cfg.get('contest_end_date', ''), cfg.get('contest_end_utc', ''))
        if start and end and end <= start:
            import datetime
            end += datetime.timedelta(days=1)

    my_lat, my_lon = _loc_latlon(cfg.get('locator', ''))

    findings = []
    seen = {}   # (call, band) -> premier index
    # IA-1 : jour UTC courant (YYYYMMDD) pour controle_date_future — calculé UNE
    # fois ici (fonction pure : l'horloge est injectée, jamais lue dedans).
    _auj_utc = utcnow().strftime('%Y%m%d')

    for i, q in enumerate(qsos):
        call = str(q.get('call', '')).strip().upper()
        band = str(q.get('band', '')).strip()

        # Champs essentiels
        if not call:
            _f(findings, 'erreur', 'indicatif_vide',
               "QSO sans indicatif", q, i)
            continue

        # IA-1 : contrôles de cohérence indépendants de l'activité — s'appliquent
        # à CHAQUE QSO, sans garde contest_id/simple_mode (ils ne dépendent
        # d'aucun règlement). `_auj_utc` calculé une seule fois avant la boucle.
        for level, code, msg in _controles_coherence(q, _auj_utc):
            _f(findings, level, code, msg, q, i)

        # Doublon même station + même bande (règle REF : 1 QSO/station/bande
        # PENDANT le concours) — n'a pas de sens en logbook simple, où l'on
        # recontacte normalement la même station sur la même bande au fil
        # des années.
        if not simple_mode:
            key = (call, band)
            if key in seen:
                _f(findings, 'erreur', 'doublon',
                   f"{call} déjà travaillé sur {band} MHz (QSO n°{seen[key] + 1}) — 0 point",
                   q, i)
            else:
                seen[key] = i

        # Indicatif plausible (préfixe/suffixe portable inclus) + préfixe connu
        if not _plausible_call(call):
            _f(findings, 'attention', 'indicatif_suspect',
               f"{call} : format inhabituel — busted call probable", q, i)
        country = None
        if dxcc:
            # Indicatif COMPLET passé à lookup() : sa gestion des « / » choisit
            # le bon pays d'émission (EA/F4GLD → Espagne, pas France).
            info = dxcc.lookup(call)
            if not info:
                _f(findings, 'attention', 'prefixe_inconnu',
                   f"{call} : préfixe inconnu de cty.dat — vérifie l'indicatif", q, i)
            else:
                country = info.get('country')

        # Bande dans le concours
        if bands_ok and band and band not in bands_ok:
            _f(findings, 'attention', 'bande_hors_concours',
               f"{band} MHz n'est pas une bande de ce concours", q, i)

        # Échange à LOCATOR (THF : pas de locator = pas de km = pas de points)
        if wants.get('locator'):
            loc = str(q.get('locator', '')).strip().upper()
            if not loc:
                _f(findings, 'erreur', 'locator_manquant',
                   f"{call} : locator absent — le QSO ne rapportera aucun km", q, i)
            elif not _LOCATOR_RE.match(loc):
                _f(findings, 'erreur', 'locator_invalide',
                   f"{call} : locator « {loc} » invalide", q, i)
            elif my_lat is not None:
                lat, lon = _loc_latlon(loc)
                if lat is not None:
                    km = haversine(my_lat, my_lon, lat, lon)
                    limit = MAX_KM_BY_BAND.get(band)
                    if limit and km > limit:
                        _f(findings, 'attention', 'distance_suspecte',
                           f"{call} : {km} km sur {band} MHz — exceptionnel "
                           f"(> {limit} km), vérifie le locator", q, i)

        # Échange à DÉPARTEMENT (REF HF)
        if wants.get('dept'):
            exch = str(q.get('num_rcvd', '')).strip()
            if country in ('France', 'Corsica'):
                dept = dept_from_exchange(exch) if dept_from_exchange else None
                if not dept:
                    _f(findings, 'erreur', 'dept_invalide',
                       f"{call} : département reçu « {exch or '—'} » invalide "
                       f"(station française)", q, i)
            elif country and not re.search(r'\d', exch):
                _f(findings, 'info', 'serie_manquante',
                   f"{call} : numéro de série reçu vide (station étrangère)", q, i)

        # Fenêtre temporelle
        if start and end:
            dt = _parse_dt(q.get('date', ''), q.get('time', ''))
            if dt and not (start <= dt < end):
                _f(findings, 'erreur', 'hors_fenetre',
                   f"{call} : QSO hors de la fenêtre du concours "
                   f"({dt.strftime('%d/%m %H:%M')})", q, i)

        # RST manquant
        if not str(q.get('rst_rcvd', q.get('rst_recu', ''))).strip():
            _f(findings, 'info', 'rst_manquant',
               f"{call} : RST reçu vide", q, i)

    order = {'erreur': 0, 'attention': 1, 'info': 2}
    findings.sort(key=lambda x: order.get(x['level'], 3))
    counts = {'erreur': 0, 'attention': 0, 'info': 0}
    for x in findings:
        counts[x['level']] = counts.get(x['level'], 0) + 1

    # Séparation SAISI / IMPORTÉ. Un log IMPORTÉ (`source == 'adif_import'`,
    # posé par logx_import) peut apporter des dizaines de milliers de QSO
    # hérités d'un autre logiciel : ils déclenchent des milliers de constats
    # LÉGITIMES mais non actionnables « ici et maintenant ». On ventile pour que
    # le badge n'alarme que sur les QSO saisis DANS LogX — sans jamais cacher
    # l'historique importé (il reste dans `findings`, consultable dans VÉRIFIER).
    # Clé de QSO NAMESPACÉE : un même log peut mêler des QSO avec id (assignés
    # par le stockage) et sans id (findings repérés par index). Mélanger les deux
    # espaces dans un set provoquerait des collisions (un id numériquement égal à
    # l'index d'un autre QSO) — un QSO saisi serait alors classé « importé ». On
    # préfixe donc ('id', …) vs ('idx', …). Même clé côté qsos et côté finding.
    def _cle(qid, index):
        return ('id', qid) if qid is not None else ('idx', index)

    _importe_keys = set()
    for i, q in enumerate(qsos):
        if (q.get('source') or '') == 'adif_import':
            _importe_keys.add(_cle(q.get('id'), i))

    def _est_importe(x):
        return _cle(x.get('id'), x.get('index')) in _importe_keys

    counts_saisi = {'erreur': 0, 'attention': 0, 'info': 0}
    counts_importe = {'erreur': 0, 'attention': 0, 'info': 0}
    # « N QSO à vérifier » = nombre de QSO DISTINCTS portant ≥1 constat
    # erreur/attention — et NON le nombre de constats. Un même QSO peut en
    # cumuler plusieurs (locator manquant + département invalide + …) : sommer
    # les constats donnait un total pouvant DÉPASSER le nombre de QSO (vu après
    # un import massif sans locator : « 15073 à vérifier » pour 10067 QSO). Borné
    # par qso_count. (Les 'erreur' ne sont jamais plafonnées, cf. _f ; le compte
    # est donc exact pour elles — la seule perte possible touche des 'attention'
    # au-delà du plafond d'affichage, cas marginal.)
    a_verifier = set()
    a_verifier_saisi = set()
    a_verifier_importe = set()
    for x in findings:
        importe = _est_importe(x)
        (counts_importe if importe else counts_saisi)[x['level']] += 1
        if x['level'] in ('erreur', 'attention'):
            k = _cle(x.get('id'), x.get('index'))
            if k != ('idx', None):
                a_verifier.add(k)
                (a_verifier_importe if importe else a_verifier_saisi).add(k)
    return {
        'contest': contest_id,
        'qso_count': len(qsos),
        'findings': findings,
        'counts': counts,
        'counts_saisi': counts_saisi,
        'counts_importe': counts_importe,
        'qso_a_verifier': len(a_verifier),
        'qso_a_verifier_saisi': len(a_verifier_saisi),
        'qso_a_verifier_importe': len(a_verifier_importe),
        'ok': counts['erreur'] == 0,
        'truncated': len(findings) >= MAX_FINDINGS,
    }


def resume_controle(qsos, contest_id='', cfg=None):
    """Résumé compact des contrôles pour le PRÉ-VOL avant export/LoTW :
    {erreurs, attentions, infos, ok}. INFORMATIF — ne bloque rien (masquer !=
    bloquer). S'appuie sur validate_log : même vérité que le panneau VÉRIFIER
    (même portée), pas une 2e définition. `ok` = aucune erreur bloquante."""
    res = validate_log(qsos, contest_id, cfg)
    c = res['counts']
    return {'erreurs': c.get('erreur', 0), 'attentions': c.get('attention', 0),
            'infos': c.get('info', 0), 'ok': c.get('erreur', 0) == 0}


# ─── AUDIT IA DU LOG AVANT DÉPÔT ─────────────────────────────────────────────
# En COMPLÉMENT de validate_log (déterministe), une passe IA relit le log scopé
# et repère ce qu'aucune règle ne code. Les constats sortent au MÊME format que
# validate_log ({level, msg, id}) : la fenêtre VÉRIFIER et ses boutons
# Corriger/Supprimer les affichent tels quels. L'appel LLM lui-même est lancé
# côté serveur en tâche de fond (voir /log/audit) — jamais dans le thread HTTP.

MAX_AUDIT_QSOS = 400   # plafond de contexte : au-delà on audite les plus récents

AUDIT_SYSTEM = (
    "Tu es un correcteur de log de concours radioamateur. On te donne les QSO "
    "d'UN concours (déjà filtrés, chacun avec un id). Repère UNIQUEMENT les "
    "anomalies qu'un contrôle automatique de format ne voit pas, chacune "
    "RATTACHÉE à l'id EXACT d'un QSO fourni :\n"
    "- indicatif très probablement mal copié (busté) au vu des autres QSO ;\n"
    "- échange incohérent avec l'indicatif (zone CQ, État, préfixe manifestement "
    "faux pour ce pays) ;\n"
    "- même indicatif logué avec DEUX échanges DIFFÉRENTS et contradictoires ;\n"
    "- QSO propagativement très improbable à cette heure/bande ;\n"
    "- série de numéros reçus manifestement incohérente (bond ou retour massif) ;\n"
    "- multiplicateur qui semble compté deux fois.\n"
    "N'invente RIEN et ne signale PAS ce qu'un contrôle de format couvre déjà "
    "(doublon exact, RST manquant, champ vide). Dans le DOUTE, ABSTIENS-toi — "
    "un faux positif fait perdre confiance. Chaque constat porte un niveau "
    "('erreur' seulement si c'est presque sûr, sinon 'attention' ou 'info'), un "
    "message COURT en français nommant l'indicatif, et le qso_id d'un QSO fourni."
)

AUDIT_SCHEMA = {
    'type': 'object',
    'properties': {
        'findings': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'level': {'type': 'string', 'enum': ['erreur', 'attention', 'info']},
                    'message': {'type': 'string'},
                    'qso_id': {'type': 'integer'},
                },
                'required': ['level', 'message', 'qso_id'],
            },
        },
    },
    'required': ['findings'],
}


def build_audit_input(qsos, contest_id='', cfg=None):
    """Prépare l'entrée de l'audit IA : QSO scopés (contest+année, MÊME portée
    que validate_log) sérialisés en une liste compacte avec leur id, plus
    l'ensemble des id valides (pour rejeter tout constat visant un id absent).
    Retourne {system, user_text, valid_ids, truncated, count}."""
    cfg = cfg or {}
    if cfg.get('usage_mode') == 'simple':
        contest_id = ''
    from logx_storage import qso_scope_id, cfg_scope_id
    scope_id = cfg_scope_id(cfg)
    scoped = [q for q in (qsos or [])
              if (not scope_id or qso_scope_id(q) == scope_id) and q.get('id') is not None]
    truncated = len(scoped) > MAX_AUDIT_QSOS
    lot = scoped[-MAX_AUDIT_QSOS:] if truncated else scoped
    valid_ids = {int(q['id']) for q in lot}

    from logx_definitions import CONTEST_DEFINITIONS
    cdef = CONTEST_DEFINITIONS.get(contest_id, {}) if contest_id else {}
    name = cdef.get('name', contest_id or 'log')
    lignes = []
    for q in lot:
        lignes.append('%s | %s | %s | %s | recu=%s | env=%s | %s %s' % (
            q['id'], str(q.get('call', '')).upper(), q.get('band', ''),
            q.get('mode', ''), q.get('num_rcvd', ''), q.get('num_sent', ''),
            q.get('date', ''), q.get('time', '')))
    user_text = ('Concours : %s\nQSO (id | indicatif | bande MHz | mode | échange '
                 'reçu | échange envoyé | date heure UTC) :\n%s' % (name, '\n'.join(lignes)))
    return {'system': AUDIT_SYSTEM, 'user_text': user_text,
            'valid_ids': valid_ids, 'truncated': truncated, 'count': len(lot)}


def normalize_audit_findings(raw, valid_ids):
    """Filtre/normalise les constats bruts de l'IA au format de validate_log.
    REJETTE tout constat dont le qso_id n'appartient pas au lot envoyé : sans
    cible réelle, les boutons Corriger/Supprimer n'ont rien sur quoi agir."""
    out = []
    for f in (raw or []):
        if not isinstance(f, dict):
            continue
        qid = f.get('qso_id')
        try:
            qid = int(qid)
        except (TypeError, ValueError):
            continue
        if qid not in valid_ids:
            continue
        level = f.get('level')
        if level not in ('erreur', 'attention', 'info'):
            level = 'attention'
        msg = str(f.get('message') or f.get('msg') or '').strip()
        if not msg:
            continue
        out.append({'level': level, 'code': 'ia', 'msg': msg[:300], 'id': qid, 'ai': True})
    order = {'erreur': 0, 'attention': 1, 'info': 2}
    out.sort(key=lambda x: order.get(x['level'], 3))
    return out[:MAX_FINDINGS]
