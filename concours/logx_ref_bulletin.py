# -*- coding: utf-8 -*-
"""Bulletin hebdomadaire du REF (F8REF) — extraction de la rubrique
« Commission des concours » (soirées d'activité THF + concours DX du
prochain week-end), cache local rafraîchi une fois par semaine.

Bulletin publié en version texte allégée sur
https://f8ref.r-e-f.org/bulletins/bulref.txt, écrasé à chaque nouvelle
édition (généralement le mercredi — la rédaction ferme les contributions
« le mardi à 24h dernier délai », vu dans le pied de page du bulletin
lui-même). Un cache de 7 jours colle donc naturellement au rythme réel de
publication sans avoir à connaître le jour exact.

Piège vérifié en le faisant : le serveur d'Apache renvoie 403 Forbidden à
un User-Agent générique (`curl`, `python-requests`...) mais 200 à un
User-Agent de navigateur — fetch_url() (logx_utils) envoie déjà un
User-Agent de type navigateur pour tous les appels sortants de LogX AI,
donc rien de spécifique à faire ici, mais un test/débogage local avec
`curl` nu donnera un faux négatif si on ne sait pas ça.

Important : la rubrique concours de ce bulletin est elle-même sourcée de
WA7BNM (« Source: WA7BNM », vérifié dans le texte) — déjà couvert par
logx_rules.fetch_wa7bnm_calendar()/l'onglet MONDIAL WA7BNM du calendrier.
Le vrai contenu propre au REF (pas une redite) est la partie « soirées
d'activité THF », spécifique à la France. On affiche quand même la rubrique
entière telle quelle (plus honnête et plus simple qu'un tri fin qui
duppliquerait la logique du parseur WA7BNM existant), avec ce contexte
donné à l'utilisateur côté frontend.
"""
import datetime
import json
import os
import re
import threading

REF_BULLETIN_URL = 'https://f8ref.r-e-f.org/bulletins/bulref.txt'
REF_BULLETIN_CACHE_FILE = 'ref_bulletin_cache.json'
REF_BULLETIN_TTL_DAYS = 7

REF_BULLETIN_CACHE = {}

# "Bulletin F8REF – 2026 Semaine 33" -- le tiret vu dans le bulletin est un
# tiret demi-cadratin (U+2013 EN DASH), mais on reste tolérant à un tiret
# ASCII simple au cas où la rédaction change un jour d'éditeur de texte.
# Échappes \u explicites (jamais le glyphe brut dans la source) pour éviter
# toute confusion visuelle entre tirets qui se ressemblent à l'oeil.
WEEK_RE = re.compile(r'Bulletin\s+F8REF\s*[\-‐-―]\s*(\d{4})\s+Semaine\s+(\d+)', re.I)

# Sentinelles stables d'une semaine à l'autre (vérifié sur le bulletin
# Semaine 33/2026) : englobent les soirées d'activité THF ET les concours DX
# du week-end. Extraire le BLOC entier entre ces deux phrases est plus
# robuste qu'un parseur ligne à ligne de chaque concours, qui casserait au
# moindre concours ajouté/retiré ou changement de mise en forme d'une
# semaine à l'autre.
SECTION_START = 'Commission des concours.'
SECTION_END = '73 la commission des concours.'


def _extract_concours_section(text):
    """Isole le bloc entre les deux sentinelles. Renvoie '' si la rubrique
    est introuvable (mise en forme du bulletin changée, ou section absente
    cette semaine-là) — jamais d'exception."""
    start = text.find(SECTION_START)
    if start == -1:
        return ''
    end = text.find(SECTION_END, start)
    if end == -1:
        section = text[start:]
    else:
        section = text[start:end + len(SECTION_END)]
    return section.strip().replace('\r\n', '\n')  # CRLF côté source, normalisé pour l'affichage


def fetch_ref_bulletin():
    """Télécharge le bulletin texte et en extrait la rubrique concours.
    Renvoie None si injoignable ou si la rubrique n'a pas pu être isolée —
    l'appelant (refresh_ref_bulletin) ne doit alors jamais écraser un cache
    déjà valide avec ce résultat vide."""
    from logx_utils import fetch_url  # import local : mockable par les tests (voir logx_dxpeditions.py)
    content = fetch_url(REF_BULLETIN_URL, timeout=15)
    if not content:
        return None
    section = _extract_concours_section(content)
    if not section:
        return None
    m = WEEK_RE.search(content)
    return {
        'year': int(m.group(1)) if m else None,
        'week': int(m.group(2)) if m else None,
        'text': section,
        'source_url': REF_BULLETIN_URL,
    }


def load_ref_bulletin():
    """Charge le cache disque au démarrage ; rafraîchit en arrière-plan si
    absent ou vieux de plus de REF_BULLETIN_TTL_DAYS jours (même logique que
    logx_rules.load_external_contests)."""
    global REF_BULLETIN_CACHE
    try:
        stale = True
        if os.path.exists(REF_BULLETIN_CACHE_FILE):
            with open(REF_BULLETIN_CACHE_FILE, 'r', encoding='utf-8') as f:
                REF_BULLETIN_CACHE = json.load(f)
            try:
                updated = datetime.datetime.fromisoformat(
                    REF_BULLETIN_CACHE.get('updated', '1970-01-01'))
                age_days = (datetime.datetime.now() - updated).days
                stale = age_days > REF_BULLETIN_TTL_DAYS or not REF_BULLETIN_CACHE.get('text')
            except Exception:
                stale = True
        if stale:
            threading.Thread(target=refresh_ref_bulletin, daemon=True).start()
    except Exception as e:
        print(f"[REF] Erreur chargement cache bulletin: {e}")


def refresh_ref_bulletin():
    """Met à jour le cache depuis f8ref.r-e-f.org. Une réponse vide/injoignable
    ne doit jamais écraser un cache déjà valide (même garde que
    logx_rules.refresh_external_contests)."""
    global REF_BULLETIN_CACHE
    data = fetch_ref_bulletin()
    if not data:
        print("[REF] Bulletin injoignable ou rubrique introuvable — cache existant conservé")
        return REF_BULLETIN_CACHE
    data['updated'] = datetime.datetime.now().isoformat()
    REF_BULLETIN_CACHE = data
    try:
        from logx_storage import save_json_atomic
        save_json_atomic(REF_BULLETIN_CACHE_FILE, data)
        print(f"[REF] Bulletin Semaine {data.get('week')}/{data.get('year')} mis en cache")
    except Exception as e:
        print(f"[REF] Erreur sauvegarde cache bulletin: {e}")
    return data
