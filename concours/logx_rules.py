# -*- coding: utf-8 -*-
"""Règlements et calendrier : calcul des dates, mise à jour annuelle, cache règlements, concours externes WA7BNM."""

import json
import os
import re
import datetime
import threading
import time

from logx_utils import CURRENT_YEAR, fetch_url
from logx_definitions import CONTEST_DEFINITIONS, CONTEST_RULES_URLS

# ─── FICHIER DE CACHE DES RÈGLEMENTS ─────────────────────────────────────────
RULES_CACHE_FILE = 'rules_cache.json'
rules_db = {}          # base de données règlements chargée en mémoire
rules_lock = threading.Lock()

# ─── BASE CONCOURS EXTERNES (WA7BNM + autres) ────────────────────────────────
# Concours importants non couverts par CONTEST_DEFINITIONS
# Chargés dynamiquement depuis contestcalendar.com
EXTERNAL_CONTESTS_CACHE = {}
EXTERNAL_CACHE_FILE = 'external_contests.json'

def fetch_wa7bnm_calendar(year=None):
    """Récupère le calendrier WA7BNM pour l'année donnée"""
    if year is None:
        year = CURRENT_YEAR
    url = f'https://www.contestcalendar.com/perpetualcal.php?year={year}'
    print(f"[WA7BNM] Récupération calendrier {year}...")
    content = fetch_url(url, timeout=15)
    if not content:
        print("[WA7BNM] Impossible de récupérer le calendrier")
        return []

    # Le calendrier perpétuel est servi en HTML :
    #   <tr><td ...><strong>January 2026</strong></td></tr>            ← mois
    #   <tr...><td>...<a ... href="contestdetails.php?ref=466">+</a></span>
    #     AGB New Year Snowball Contest</td><td>0000Z-0100Z, Jan 1</td></tr>
    contests = []
    current_month = ''
    month_re = re.compile(r'<strong>([A-Za-z]+ \d{4})</strong>')
    row_re = re.compile(
        r'href="contestdetails\.php\?ref=(\d+)"[^>]*>[^<]*</a></span>\s*'
        r'([^<]+)</td>\s*<td>([^<]*)</td>', re.I)

    # Parcours séquentiel : on suit le mois courant au fil du document
    events = sorted(
        [(m.start(), 'month', m.group(1)) for m in month_re.finditer(content)] +
        [(m.start(), 'row', m) for m in row_re.finditer(content)])
    for _, kind, val in events:
        if kind == 'month':
            current_month = val
            continue
        ref_id, name, when = val.group(1), val.group(2).strip(), val.group(3).strip()
        dates = re.findall(r'[A-Z][a-z]{2}\s+\d{1,2}', when)
        times = re.findall(r'\d{4}Z(?:-\d{4}Z)?', when)
        contests.append({
            'ref': ref_id,
            'name': name,
            'month': current_month,
            'date_str': ', '.join(dates[:2]) if dates else current_month,
            'time_str': times[0] if times else '',
            'url': f'https://www.contestcalendar.com/contestdetails.php?ref={ref_id}',
            'year': year,
        })

    print(f"[WA7BNM] {len(contests)} concours trouvés pour {year}")
    return contests

def load_external_contests():
    """Charge le cache des concours externes. Rafraîchit en arrière-plan si
    le cache est absent, vide, d'une autre année ou vieux de plus de 7 jours."""
    global EXTERNAL_CONTESTS_CACHE
    try:
        stale = True
        if os.path.exists(EXTERNAL_CACHE_FILE):
            with open(EXTERNAL_CACHE_FILE, 'r', encoding='utf-8') as f:
                EXTERNAL_CONTESTS_CACHE = json.load(f)
            n = len(EXTERNAL_CONTESTS_CACHE.get('contests', []))
            print(f"[EXT] {n} concours externes chargés")
            try:
                updated = datetime.datetime.fromisoformat(
                    EXTERNAL_CONTESTS_CACHE.get('updated', '1970-01-01'))
                age_days = (datetime.datetime.now() - updated).days
                stale = (n == 0
                         or EXTERNAL_CONTESTS_CACHE.get('year') != CURRENT_YEAR
                         or age_days > 7)
                if stale:
                    print(f"[EXT] Cache périmé (n={n}, âge={age_days}j) — rafraîchissement...")
            except Exception:
                stale = (n == 0)
        if stale:
            threading.Thread(target=refresh_external_contests, daemon=True).start()
    except Exception as e:
        print(f"[EXT] Erreur chargement: {e}")

def refresh_external_contests():
    """Met à jour le cache des concours externes depuis WA7BNM"""
    global EXTERNAL_CONTESTS_CACHE
    contests_this = fetch_wa7bnm_calendar(CURRENT_YEAR)
    contests_next = fetch_wa7bnm_calendar(CURRENT_YEAR + 1)
    # Une réponse vide (réseau en panne, page tronquée) ne doit jamais
    # écraser un cache déjà valide — fetch_wa7bnm_calendar() renvoie []
    # justement dans ce cas, sans lever d'exception.
    if not contests_this and not contests_next:
        print("[EXT] Réponse vide/injoignable — cache existant conservé")
        return
    data = {
        'year': CURRENT_YEAR,
        'updated': datetime.datetime.now().isoformat(),
        'contests': contests_this,
        'contests_next': contests_next,
    }
    EXTERNAL_CONTESTS_CACHE = data
    try:
        from logx_storage import save_json_atomic
        save_json_atomic(EXTERNAL_CACHE_FILE, data)
        print(f"[EXT] Cache sauvegardé: {len(contests_this)} concours {CURRENT_YEAR}")
    except Exception as e:
        print(f"[EXT] Erreur sauvegarde: {e}")
    return data

# ─── CALCUL AUTOMATIQUE DES DATES PAR RÈGLE ──────────────────────────────────
# Grammaire des règles de dates — source de vérité unique, utilisée par
# calc_contest_date (interprétation), logx_validate.py (validation)
# et le prompt d'extraction IA (logx_rules_ai.py).
_MONTHS_RE = ('january|february|march|april|may|june|july|august|september|'
              'october|november|december')
DATE_RULE_PATTERN = (
    r'^(permanent'
    rf'|(first|second|third|fourth|last)_(saturday|sunday)_({_MONTHS_RE})(_\d{{2}}h)?'
    rf'|(first|second|third|fourth|last)_full_weekend_({_MONTHS_RE})(_\d{{2}}h)?)$'
)
DATE_RULE_RE = re.compile(DATE_RULE_PATTERN)

def calc_contest_date(date_rule, year=None):
    """Calcule la date exacte d'un concours pour une année donnée"""
    if year is None:
        year = CURRENT_YEAR
    if date_rule == 'permanent':
        return f"Permanent ({year})"

    import calendar

    def nth_weekday(year, month, weekday, n):
        """Retourne le n-ième jour de la semaine d'un mois (1-based)"""
        c = calendar.monthcalendar(year, month)
        days = [w[weekday] for w in c if w[weekday] != 0]
        return days[n-1] if n <= len(days) else days[-1]

    def last_weekday(year, month, weekday):
        """Retourne le dernier jour de la semaine d'un mois"""
        c = calendar.monthcalendar(year, month)
        days = [w[weekday] for w in c if w[weekday] != 0]
        return days[-1]

    def last_full_weekend(year, month):
        """Dernier weekend complet (sam+dim) du mois"""
        c = calendar.monthcalendar(year, month)
        sat_days = [w[calendar.SATURDAY] for w in c if w[calendar.SATURDAY] != 0]
        last_sat = sat_days[-1]
        # Vérifier que le dimanche est dans le même mois
        last_sun = last_sat + 1
        _, days_in_month = calendar.monthrange(year, month)
        if last_sun > days_in_month:
            last_sat = sat_days[-2] if len(sat_days) >= 2 else sat_days[-1]
        return last_sat

    MONTHS = {
        'january':1,'february':2,'march':3,'april':4,'may':5,'june':6,
        'july':7,'august':8,'september':9,'october':10,'november':11,'december':12
    }

    def nth_full_weekend(year, month, n):
        """N-ième weekend complet (sam+dim dans le même mois), 1-based"""
        c = calendar.monthcalendar(year, month)
        _, days_in_month = calendar.monthrange(year, month)
        sats = [w[calendar.SATURDAY] for w in c
                if w[calendar.SATURDAY] != 0 and w[calendar.SATURDAY] + 1 <= days_in_month]
        return sats[n-1] if n <= len(sats) else sats[-1]

    try:
        r = date_rule.lower()

        # Nth/last full weekend (sam+dim) — heure de début optionnelle (_13h)
        def _fmt_weekend(d):
            hour_match = re.search(r'_(\d{2})h$', r)
            suffix = f" à {hour_match.group(1)}h00 UTC" if hour_match else ''
            return (f"{d.strftime('%d/%m/%Y')} → "
                    f"{(d + datetime.timedelta(days=1)).strftime('%d/%m/%Y')}{suffix}")
        ordinals_fw = {'first':1,'second':2,'third':3,'fourth':4}
        for mon_name, mon_num in MONTHS.items():
            if r.startswith(f'last_full_weekend_{mon_name}'):
                sat = last_full_weekend(year, mon_num)
                return _fmt_weekend(datetime.date(year, mon_num, sat))
            for ord_name, ord_num in ordinals_fw.items():
                if r.startswith(f'{ord_name}_full_weekend_{mon_name}'):
                    sat = nth_full_weekend(year, mon_num, ord_num)
                    return _fmt_weekend(datetime.date(year, mon_num, sat))

        # Nth saturday/sunday
        ordinals = {'first':1,'second':2,'third':3,'fourth':4,'last':-1}
        for ord_name, ord_num in ordinals.items():
            for mon_name, mon_num in MONTHS.items():
                for day_name, day_num in [('saturday', calendar.SATURDAY), ('sunday', calendar.SUNDAY)]:
                    pattern = f'{ord_name}_{day_name}_{mon_name}'
                    if r.startswith(pattern):
                        if ord_num == -1:
                            day = last_weekday(year, mon_num, day_num)
                        else:
                            day = nth_weekday(year, mon_num, day_num, ord_num)
                        d = datetime.date(year, mon_num, day)
                        # Extraire heure si présente
                        hour_match = re.search(r'_(\d{2})h', r)
                        hour_str = hour_match.group(1)+'h00 UTC' if hour_match else '14h00 UTC'
                        return f"{d.strftime('%d/%m/%Y')} à {hour_str}"

    except Exception as e:
        return f"Calcul impossible: {e}"

    return date_rule

def get_next_contest_date(date_rule):
    """Retourne la prochaine occurrence d'un concours (cette année ou l'année prochaine si passé)"""
    if date_rule == 'permanent':
        return "Permanent", CURRENT_YEAR

    today = datetime.date.today()

    # Essayer cette année d'abord
    date_this_year = calc_contest_date(date_rule, CURRENT_YEAR)
    # Extraire la date du texte formaté
    m = re.search(r'(\d{2})/(\d{2})/(\d{4})', date_this_year)
    if m:
        d = datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if d >= today:
            return date_this_year, CURRENT_YEAR
    # Concours passé → prendre l'année prochaine
    date_next_year = calc_contest_date(date_rule, CURRENT_YEAR + 1)
    return date_next_year, CURRENT_YEAR + 1

def calc_all_dates(year=None):
    """Calcule les dates pour tous les concours.

    year=None : prochaine occurrence de chaque concours (repli sur l'année
    suivante si déjà passée cette année — voir get_next_contest_date).
    year=<valeur> : date calculée POUR CETTE ANNÉE PRÉCISE (calc_contest_date),
    sans le repli "prochaine occurrence" — c'est le comportement attendu par
    run_annual_update(), qui appelle calc_all_dates(CURRENT_YEAR) PUIS
    calc_all_dates(CURRENT_YEAR + 1) pour obtenir deux jeux de dates
    RÉELLEMENT différents (avant ce correctif, `year` était ignoré et les
    deux appels renvoyaient un résultat identique)."""
    dates = {}
    for cid, cdef in CONTEST_DEFINITIONS.items():
        date_rule = cdef.get('date_rule', 'permanent')
        if year is None:
            date_str, actual_year = get_next_contest_date(date_rule)
        else:
            date_str, actual_year = calc_contest_date(date_rule, year), year
        dates[cid] = {
            'name': cdef['name'],
            'date': date_str,
            'year': actual_year,
            'next_year': actual_year > CURRENT_YEAR,
        }
    return dates

# ─── VÉRIFICATION AUTOMATIQUE DES RÈGLEMENTS EN LIGNE ────────────────────────
def check_rules_update(contest_id):
    """Vérifie si un règlement a été mis à jour en ligne"""
    cdef = CONTEST_DEFINITIONS.get(contest_id)
    if not cdef or not cdef.get('check_url'):
        return None

    try:
        content = fetch_url(cdef['check_url'], timeout=8)
        if not content:
            return None

        # Détecter UNIQUEMENT les années plausibles pour des règlements
        # L'année doit apparaître près d'un mot-clé de règlement
        rule_keywords = ['rules', 'règlement', 'contest', 'concours', 'regulation', 'update']
        plausible_years = []
        for kw in rule_keywords:
            # Chercher l'année dans un rayon de 100 caractères autour du mot-clé
            for m in re.finditer(kw, content, re.IGNORECASE):
                context_slice = content[max(0, m.start()-50):m.end()+50]
                years_near = re.findall(r'\b(20[2-3]\d)\b', context_slice)
                for y in years_near:
                    yi = int(y)
                    if CURRENT_YEAR <= yi <= CURRENT_YEAR + 2:
                        plausible_years.append(yi)
        latest_year = max(plausible_years) if plausible_years else CURRENT_YEAR

        # Chercher les nouvelles dates sur la page
        date_patterns = []
        # Dates françaises DD/MM/YYYY
        dates_fr = re.findall(r'\d{1,2}/\d{1,2}/20[2-3]\d', content)
        date_patterns.extend(dates_fr)

        # Chercher mention du concours
        contest_name = cdef['name']
        contest_found = contest_name.lower()[:10] in content.lower()

        return {
            'contest_id': contest_id,
            'check_url': cdef['check_url'],
            'latest_year_found': latest_year,
            'dates_found': date_patterns[:5],
            'contest_mentioned': contest_found,
            'rules_url': cdef.get('rules_url', ''),
            'checked_at': datetime.datetime.now().isoformat(),
        }
    except Exception as e:
        return {'contest_id': contest_id, 'error': str(e)}

def run_annual_update():
    """Lance la vérification complète annuelle des règlements"""
    print(f"\n[UPDATE] Vérification annuelle des règlements — Année {CURRENT_YEAR}")
    print("[UPDATE] Calcul des dates pour toutes les compétitions...")

    # Calculer les dates
    dates_this_year = calc_all_dates(CURRENT_YEAR)
    dates_next_year = calc_all_dates(CURRENT_YEAR + 1)

    results = {
        'last_update': datetime.datetime.now().isoformat(),
        'year': CURRENT_YEAR,
        'dates': dates_this_year,
        'dates_next_year': dates_next_year,
        'rules_checks': {},
        'alerts': [],
    }

    # Vérifier les règlements prioritaires en ligne
    priority_contests = ['REF_RPH', 'REF_NAT_THF', 'REF_PRINTEMPS', 'REF_ETE',
                         'IARU_VHF', 'IARU_UHF', 'CQ_WW_SSB', 'CQ_WW_CW']

    for cid in priority_contests:
        print(f"[UPDATE] Vérification {cid}...")
        check = check_rules_update(cid)
        if check:
            results['rules_checks'][cid] = check
            # Alerte uniquement si année FUTURE et plausible détectée
            if check.get('latest_year_found', 0) > CURRENT_YEAR + 1:
                results['alerts'].append(
                    f"⚠️ {cid}: règlement {check['latest_year_found']} détecté — vérifier mise à jour"
                )
        time.sleep(0.5)  # Ne pas surcharger les serveurs

    # Sauvegarder
    with rules_lock:
        global rules_db
        rules_db = results
        try:
            from logx_storage import save_json_atomic
            save_json_atomic(RULES_CACHE_FILE, results)
            print(f"[UPDATE] Cache sauvegardé dans {RULES_CACHE_FILE}")
        except Exception as e:
            print(f"[UPDATE] Erreur sauvegarde: {e}")

    if results['alerts']:
        print("\n[UPDATE] [!] ALERTES:")
        for a in results['alerts']:
            print(f"  {a}")

    print(f"[UPDATE] Terminé — {len(dates_this_year)} concours calculés\n")
    return results

def load_rules_cache():
    """Charge le cache des règlements au démarrage"""
    global rules_db
    try:
        if os.path.exists(RULES_CACHE_FILE):
            with open(RULES_CACHE_FILE, 'r', encoding='utf-8') as f:
                rules_db = json.load(f)
            cache_year = rules_db.get('year', 0)
            print(f"[RULES] Cache chargé (année {cache_year})")
            # Si le cache est d'une autre année → mettre à jour
            if cache_year != CURRENT_YEAR:
                print(f"[RULES] Cache périmé ({cache_year} -> {CURRENT_YEAR}) — mise à jour...")
                threading.Thread(target=run_annual_update, daemon=True).start()
        else:
            print("[RULES] Pas de cache — première initialisation...")
            threading.Thread(target=run_annual_update, daemon=True).start()
    except Exception as e:
        print(f"[RULES] Erreur chargement cache: {e}")
        rules_db = {'dates': calc_all_dates(), 'year': CURRENT_YEAR}

def schedule_annual_check():
    """Vérifie chaque jour si une mise à jour annuelle est nécessaire"""
    while True:
        time.sleep(86400)  # Toutes les 24h
        if rules_db.get('year', 0) != datetime.datetime.now().year:
            print("[RULES] Nouvelle année détectée — mise à jour automatique...")
            run_annual_update()

# ─── EXTRACTION DE TEXTE DES RÈGLEMENTS (PDF / HTML) ────────────────────────
# Essaie les vraies libs PDF dans l'ordre (pymupdf, pdfplumber, pypdf) et ne
# retombe sur l'ancienne regex maison (flux PDF bruts) qu'en dernier recours.

def _pdf_text_pymupdf(pdf_bytes):
    import fitz  # pymupdf
    with fitz.open(stream=pdf_bytes, filetype='pdf') as doc:
        return '\n'.join(page.get_text() for page in doc)

def _pdf_text_pdfplumber(pdf_bytes):
    import io
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return '\n'.join((page.extract_text() or '') for page in pdf.pages)

def _pdf_text_pypdf(pdf_bytes):
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return '\n'.join((page.extract_text() or '') for page in reader.pages)

def _pdf_text_legacy(pdf_bytes):
    """Extraction regex maison sur les flux PDF bruts — dernier recours."""
    text = ''
    raw = pdf_bytes.decode('latin-1', errors='ignore')
    bt_blocks = re.findall(r'BT(.*?)ET', raw, re.DOTALL)
    for block in bt_blocks:
        strings = re.findall(r'\(([^)]{2,})\)', block)
        text += ' '.join(s for s in strings if s.isprintable()) + ' '
    return text

def _html_to_text(data_bytes):
    """Règlement publié en page HTML : suppression grossière des balises."""
    html = data_bytes.decode('utf-8', errors='ignore')
    html = re.sub(r'(?is)<(script|style|nav|header|footer)[^>]*>.*?</\1>', ' ', html)
    text = re.sub(r'(?s)<[^>]+>', ' ', html)
    import html as html_mod
    return html_mod.unescape(text)

def extract_document_text(data_bytes, url=''):
    """Extrait le texte d'un règlement (PDF ou HTML).
    Retourne (texte, extracteur_utilisé)."""
    is_pdf = data_bytes[:5] == b'%PDF-' or url.lower().endswith('.pdf')
    if not is_pdf:
        text = _html_to_text(data_bytes)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text).strip()
        return text, 'html'
    for name, extractor in (('pymupdf', _pdf_text_pymupdf),
                            ('pdfplumber', _pdf_text_pdfplumber),
                            ('pypdf', _pdf_text_pypdf)):
        try:
            text = extractor(data_bytes)
            if text and len(text.strip()) > 50:
                text = re.sub(r'[ \t]+', ' ', text)
                text = re.sub(r'\n\s*\n+', '\n\n', text).strip()
                return text, name
        except ImportError:
            continue
        except Exception as e:
            print(f"[RULES] Extracteur {name} en échec : {e}")
    text = re.sub(r'\s+', ' ', _pdf_text_legacy(data_bytes)).strip()
    return text, 'legacy-regex'

def download_rules_document(url, timeout=20):
    """Télécharge un règlement et retourne (texte, extracteur). Lève en cas d'échec."""
    from logx_rules_ai import _download_bytes
    data = _download_bytes(url, timeout=timeout)
    return extract_document_text(data, url)

# Cache règlements en mémoire
rules_cache = {}

def fetch_contest_rules(contest_id):
    if contest_id in rules_cache:
        return rules_cache[contest_id]
    cdef = CONTEST_DEFINITIONS.get(contest_id, {})
    # Source primaire : rules_url déjà présent et à jour sur CHAQUE concours
    # (40/40) — CONTEST_RULES_URLS n'est gardée qu'en repli de compatibilité
    # pour un éventuel appelant externe qui la lirait directement.
    url = cdef.get('rules_url') or CONTEST_RULES_URLS.get(contest_id)
    if not url:
        return None
    try:
        text, extractor = download_rules_document(url, timeout=15)
        # Garder les 3000 premiers caractères pour le contexte de chat
        result = {
            'contest': contest_id,
            'url': url,
            'text_extract': text[:3000] if text else 'Extraction impossible',
            'ok': bool(text),
            'extractor': extractor,
        }
        rules_cache[contest_id] = result
        print(f"[RULES] Règlement {contest_id} chargé ({len(text)} chars, via {extractor})")
        return result
    except Exception as e:
        print(f"[RULES] Erreur {contest_id}: {e}")
        return {'contest': contest_id, 'url': url, 'text_extract': f'Erreur: {e}', 'ok': False}
