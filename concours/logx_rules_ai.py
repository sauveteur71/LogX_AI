# -*- coding: utf-8 -*-
"""Extraction IA d'un règlement de concours vers une définition CONTEST_SCHEMA.

Pipeline Phase 3 (v2) :
  1. téléchargement du règlement — PDF envoyé NATIVEMENT au modèle quand le
     fournisseur le permet (Anthropic) : tableaux, scans et mise en page
     compris ; sinon extraction texte (logx_rules.py) — règlements HTML gérés aussi
  2. appel d'extraction à SORTIE JSON FORCÉE (tool use Anthropic / json_object
     OpenAI / responseMimeType Gemini) — plus d'échec de parsing possible
  3. PASSE DE VÉRIFICATION adversariale : une checklist fermée (restrictions de
     participants, off-time, multiplicateurs pondérés, QTC...) relit le
     règlement contre la définition proposée et corrige ce qui manque
  4. validation contre le schema ET le moteur de score
  5. retour proposition + citations + rapport de vérification
     → RELECTURE HUMAINE OBLIGATOIRE (l'enregistrement passe uniquement
       par /rules/save_definition, jamais par ce module)

Les règlements peuvent être dans n'importe quelle langue (DE, EN, ES, JA, RU...) —
la définition produite est toujours en français.
"""
import base64
import copy
import json
import os
import re
import urllib.request

from logx_rules import extract_document_text, DATE_RULE_PATTERN, calc_contest_date
from logx_validate import validate_definition
from logx_utils import OPENAI_COMPATIBLE_ENDPOINTS

MAX_RULES_CHARS = 40000        # garde-fou taille prompt en mode texte
MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_PDF_PAGES = 90

# ─── SCHEMAS DES SORTIES FORCÉES ─────────────────────────────────────────────

def _contest_schema():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, 'contest_schema.json'), encoding='utf-8') as f:
        return json.load(f)

def _extraction_envelope_schema():
    """Schema de l'enveloppe d'extraction — la définition embarque le
    contest_schema.json réel (source de vérité unique)."""
    cdef_schema = _contest_schema()
    cdef_schema.pop('$schema', None)
    cdef_schema.pop('$id', None)
    return {
        'type': 'object',
        'required': ['suggested_id', 'definition', 'citations', 'warnings', 'confidence'],
        'properties': {
            'suggested_id': {
                'type': 'string',
                'description': "ID court en majuscules, ex. WAEDC_CW, UBA_SSB, JIDX_CW",
            },
            'definition': cdef_schema,
            'citations': {
                'type': 'object',
                'description': "Pour chaque champ de definition : passage EXACT du règlement "
                               "(≤ 200 caractères, dans la langue d'origine) qui justifie la valeur",
                'additionalProperties': {'type': 'string'},
            },
            'warnings': {
                'type': 'array', 'items': {'type': 'string'},
                'description': "Tout ce qui est ambigu, absent du texte, ou déduit avec incertitude",
            },
            'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']},
        },
    }

# Checklist de vérification — chaque question cible un piège réel d'extraction
VERIFICATION_CHECKLIST = [
    "Restrictions de participants : le règlement limite-t-il QUI peut contacter QUI "
    "(continents, pays, membres d'une association) ? Si oui, la brique 'validity' de la "
    "définition l'encode-t-elle ?",
    "Périodes de repos (off-time) obligatoires ou durée d'opération limitée ?",
    "Les multiplicateurs ont-ils un poids différent selon la bande "
    "(devrait être encodé dans 'mult_weight_by_band') ?",
    "Les points par QSO diffèrent-ils selon la bande (règles 'points' avec 'bands') "
    "ou selon le mode ?",
    "Le contenu EXACT de l'échange : RST ? numéro de série ? zone ? département/état ? âge ?",
    "La date, l'heure de début UTC et la durée sont-elles exactes ? "
    "(attention aux heures locales converties). Si le règlement parle de "
    "« weekend », date_rule doit être en *_full_weekend_* et non *_saturday_* "
    "(un samedi de fin de mois peut ne pas appartenir au dernier week-end complet).",
    "Y a-t-il des QTC ou d'autres mécanismes de points additionnels non modélisables ? "
    "(à signaler en notes)",
    "La deadline d'envoi du log et le format exigé (EDI/Cabrillo/ADIF) sont-ils corrects ?",
]

def _verification_schema():
    cdef_schema = _contest_schema()
    cdef_schema.pop('$schema', None)
    cdef_schema.pop('$id', None)
    return {
        'type': 'object',
        'required': ['answers', 'definition_corrigee'],
        'properties': {
            'answers': {
                'type': 'array',
                'description': "Une réponse par question de la checklist, dans l'ordre",
                'items': {
                    'type': 'object',
                    'required': ['question', 'reponse', 'definition_conforme'],
                    'properties': {
                        'question': {'type': 'string', 'description': "Rappel court de la question"},
                        'reponse': {'type': 'string', 'description': "Ce que dit le règlement (avec citation)"},
                        'definition_conforme': {'type': 'boolean'},
                        'probleme': {'type': 'string', 'description': "Si non conforme : ce qui manque/est faux"},
                    },
                },
            },
            'definition_corrigee': {
                'oneOf': [{'type': 'null'}, cdef_schema],
                'description': "La définition complète CORRIGÉE si au moins un point n'était pas "
                               "conforme, sinon null. Repartir de la définition proposée et ne "
                               "changer que ce qui doit l'être.",
            },
        },
    }

# ─── PROMPTS ─────────────────────────────────────────────────────────────────

def build_extraction_system():
    return f"""Tu es un expert des règlements de concours radioamateur (REF, IARU, CQ, ARRL, DARC, UBA, JARL...).
Ta mission : lire un règlement et produire une définition de concours STRICTEMENT conforme au schema de l'outil.

Le règlement peut être dans N'IMPORTE QUELLE LANGUE (français, anglais, allemand, espagnol, japonais, russe...).
Les textes libres de la définition (exchange, notes) sont TOUJOURS en français ; les citations restent dans la langue d'origine.

RÈGLES IMPÉRATIVES :
1. N'INVENTE RIEN. Un champ optionnel absent du règlement → omets-le et signale-le en warning.
   Un champ requis introuvable → meilleure hypothèse + warning explicite.
2. date_rule doit matcher cette grammaire (regex) : {DATE_RULE_PATTERN}
   Exemples : first_saturday_july, third_saturday_november_17h, last_full_weekend_october, permanent.
   Attention : les heures sont en UTC — convertis si le règlement donne une heure locale.
   PIÈGE : si le règlement dit « weekend » (full weekend, dernier week-end complet...),
   utilise IMPÉRATIVEMENT la forme *_full_weekend_*, jamais *_saturday_*. Elles divergent
   quand le dernier samedi du mois n'est pas suivi d'un dimanche du même mois
   (ex. CQWW octobre 2026 : last_saturday_october → 31/10, mais le dernier week-end
   COMPLET est le 24-25/10). Réserve *_saturday_*/*_sunday_* aux concours d'un seul jour
   ou dont le règlement désigne explicitement ce jour précis.
3. bands : chaînes en MHz ('1.8','3.5','7','14','21','28','50','144','432','1296'...).
4. scoring : si un type historique correspond EXACTEMENT, utilise-le avec ses paramètres.
   Sinon compose des 'bricks' (prédicats, familles de multiplicateurs, options — tout est
   documenté dans le schema). Ne force jamais un type historique qui ne colle pas.
   ATTENTION aux restrictions de participants : beaucoup de concours DX ne valident que
   certains contacts (WAE : Europe↔hors-Europe uniquement ; ARRL DX : W/VE uniquement...).
   Dans ce cas, ENCODE la restriction avec la brique 'validity' (+ 'validity_fail_explanation'),
   ne te contente pas de la mentionner dans les notes.
   De même : multiplicateurs pondérés par bande → 'mult_weight_by_band' ;
   points différents selon la bande → règles 'points' avec le filtre 'bands'.
5. citations : cite pour CHAQUE champ de definition le passage source exact.
   C'est ce qui permet la relecture humaine — c'est obligatoire."""

def build_verification_system():
    return """Tu es un VÉRIFICATEUR adversarial de définitions de concours radioamateur.
On te donne un règlement et une définition extraite par une première passe.
Ton travail : chercher ce que la première passe a RATÉ ou mal encodé, en répondant
à chaque question de la checklist à partir du RÈGLEMENT (pas de la définition).
Si tout est conforme, definition_corrigee = null. Sinon, produis la définition
complète corrigée (repars de la proposition, ne change que le nécessaire).
Le règlement peut être dans n'importe quelle langue. Sois exigeant : un point
'conforme' doit être PROUVÉ par le règlement, pas supposé."""

# ─── APPELS FOURNISSEURS À SORTIE FORCÉE ─────────────────────────────────────

def _http_json(url, payload, headers, timeout):
    from logx_utils import SSL_CTX
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers=headers, method='POST')
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        return json.loads(resp.read())

def call_ai_structured(provider, model, api_key, system, user_text, output_schema,
                       pdf_bytes=None, max_tokens=8000, timeout=180):
    """Appelle le fournisseur IA et retourne un OBJET (sortie JSON forcée).
    pdf_bytes : si fourni et provider=anthropic, le PDF est envoyé nativement
    (vision : tableaux, scans, mise en page)."""
    if provider == 'anthropic':
        content = []
        if pdf_bytes:
            content.append({'type': 'document',
                            'source': {'type': 'base64', 'media_type': 'application/pdf',
                                       'data': base64.standard_b64encode(pdf_bytes).decode()}})
        content.append({'type': 'text', 'text': user_text})
        payload = {
            'model': model or 'claude-sonnet-4-6',
            'max_tokens': max_tokens,
            'system': system,
            'messages': [{'role': 'user', 'content': content}],
            'tools': [{'name': 'resultat', 'description': "Enregistre le résultat structuré",
                       'input_schema': output_schema}],
            'tool_choice': {'type': 'tool', 'name': 'resultat'},
        }
        data = _http_json('https://api.anthropic.com/v1/messages', payload,
                          {'Content-Type': 'application/json', 'x-api-key': api_key,
                           'anthropic-version': '2023-06-01'}, timeout)
        for block in data.get('content', []):
            if block.get('type') == 'tool_use':
                return block.get('input', {})
        raise ValueError("Réponse Anthropic sans bloc tool_use")
    elif provider in OPENAI_COMPATIBLE_ENDPOINTS:
        # OpenAI, Mistral AI (api.mistral.ai), xAI/Grok (api.x.ai) et DeepSeek
        # (api.deepseek.com) partagent le même contrat d'API — response_format
        # json_object est confirmé sur la doc officielle d'OpenAI et de Mistral ;
        # pour xAI/DeepSeek c'est le même paramètre standard des API compatibles
        # OpenAI, et parse_ai_json() reste le filet de sécurité si un fournisseur
        # l'ignore et renvoie du texte autour du JSON.
        base_url, default_model = OPENAI_COMPATIBLE_ENDPOINTS[provider]
        payload = {
            'model': model or default_model,
            'max_tokens': max_tokens,
            'response_format': {'type': 'json_object'},
            'messages': [
                {'role': 'system', 'content': system +
                 "\n\nRéponds UNIQUEMENT par un objet JSON conforme à ce schema :\n" +
                 json.dumps(output_schema, ensure_ascii=False)},
                {'role': 'user', 'content': user_text},
            ],
        }
        data = _http_json(base_url, payload,
                          {'Content-Type': 'application/json',
                           'Authorization': f'Bearer {api_key}'}, timeout)
        return parse_ai_json(data.get('choices', [{}])[0].get('message', {}).get('content', ''))
    elif provider == 'gemini':
        payload = {
            'contents': [{'role': 'user', 'parts': [{'text': user_text}]}],
            'systemInstruction': {'parts': [{'text': system +
                "\n\nRéponds UNIQUEMENT par un objet JSON conforme à ce schema :\n" +
                json.dumps(output_schema, ensure_ascii=False)}]},
            'generationConfig': {'responseMimeType': 'application/json'},
        }
        data = _http_json(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model or "gemini-2.0-flash"}:generateContent?key={api_key}',
            payload, {'Content-Type': 'application/json'}, timeout)
        return parse_ai_json(data.get('candidates', [{}])[0].get('content', {})
                                 .get('parts', [{}])[0].get('text', ''))
    raise ValueError(f"Fournisseur IA inconnu : {provider}")

def parse_ai_json(text):
    """Extrait l'objet JSON d'une réponse texte (tolère les clôtures ```json)."""
    text = (text or '').strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end <= start:
        raise ValueError("Aucun objet JSON dans la réponse de l'IA")
    return json.loads(text[start:end + 1])

# ─── TÉLÉCHARGEMENT DU DOCUMENT ──────────────────────────────────────────────

def _download_bytes(url, timeout=20):
    from logx_utils import SSL_CTX
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
        return resp.read()

def _pdf_page_count(pdf_bytes):
    try:
        import fitz
        with fitz.open(stream=pdf_bytes, filetype='pdf') as doc:
            return doc.page_count
    except Exception:
        return None

# ─── PIPELINE COMPLET ────────────────────────────────────────────────────────

def analyze_rules(url='', rules_text='', contest_name='', cfg=None, verify=True):
    """Analyse un règlement. Retourne un dict prêt pour la relecture humaine :
    {ok, suggested_id, definition, citations, warnings, confidence,
     validation_errors, verification, date_preview, extractor, text_chars}"""
    cfg = cfg or {}
    provider = cfg.get('api_provider', 'anthropic')
    model = cfg.get('ai_model', '')
    api_key = cfg.get('api_key', '') or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return {'ok': False, 'error': "Clé API non configurée (page CONFIG → ASSISTANT IA)"}

    # ── 1. Document : PDF natif si possible, sinon texte extrait ────────────
    pdf_bytes = None
    extractor = 'texte fourni'
    if not rules_text:
        if not url:
            return {'ok': False, 'error': "Ni URL ni texte de règlement fournis"}
        try:
            raw = _download_bytes(url)
        except Exception as e:
            return {'ok': False, 'error': f"Téléchargement impossible : {e}"}
        is_pdf = raw[:5] == b'%PDF-' or url.lower().endswith('.pdf')
        if is_pdf and provider == 'anthropic' and len(raw) <= MAX_PDF_BYTES:
            pages = _pdf_page_count(raw)
            if pages is None or pages <= MAX_PDF_PAGES:
                pdf_bytes = raw
                extractor = f'pdf-natif ({pages or "?"} pages)'
        try:
            rules_text, text_extractor = extract_document_text(raw, url)
            if not pdf_bytes:
                extractor = text_extractor
        except Exception as e:
            if not pdf_bytes:
                return {'ok': False, 'error': f"Extraction impossible : {e}"}
            rules_text = ''
    if not pdf_bytes and len(rules_text.strip()) < 200:
        return {'ok': False, 'error': f"Texte du règlement trop court ({len(rules_text)} caractères) "
                                      f"— extraction '{extractor}' probablement en échec"}

    doc_for_prompt = '' if pdf_bytes else \
        f"\n\n=== DÉBUT DU RÈGLEMENT ===\n{rules_text[:MAX_RULES_CHARS]}\n=== FIN DU RÈGLEMENT ==="

    # ── 2. Extraction (sortie JSON forcée) ──────────────────────────────────
    user_extract = (f"Analyse ce règlement{' : ' + contest_name if contest_name else ''}"
                    f"{' (' + url + ')' if url else ''} et produis l'extraction structurée."
                    + doc_for_prompt)
    try:
        proposal = call_ai_structured(provider, model, api_key,
                                      build_extraction_system(), user_extract,
                                      _extraction_envelope_schema(), pdf_bytes=pdf_bytes)
    except Exception as e:
        return {'ok': False, 'error': f"Appel IA (extraction) en échec : {e}"}

    definition = proposal.get('definition') or {}
    warnings = list(proposal.get('warnings') or [])
    citations = proposal.get('citations') or {}
    confidence = proposal.get('confidence', '')

    # ── 3. Passe de vérification adversariale (checklist) ───────────────────
    verification = None
    if verify:
        checklist = '\n'.join(f"{i+1}. {q}" for i, q in enumerate(VERIFICATION_CHECKLIST))
        user_verify = (f"RÈGLEMENT{' : ' + contest_name if contest_name else ''} ci-joint."
                       f"{doc_for_prompt}\n\n"
                       f"DÉFINITION PROPOSÉE PAR LA PREMIÈRE PASSE :\n"
                       f"{json.dumps(definition, ensure_ascii=False, indent=1)}\n\n"
                       f"CHECKLIST À VÉRIFIER :\n{checklist}")
        try:
            vres = call_ai_structured(provider, model, api_key,
                                      build_verification_system(), user_verify,
                                      _verification_schema(), pdf_bytes=pdf_bytes)
            issues = [a for a in vres.get('answers', [])
                      if not a.get('definition_conforme', True)]
            corrected = vres.get('definition_corrigee')
            applied = False
            if corrected and isinstance(corrected, dict):
                # N'appliquer la correction que si elle est valide — sinon on
                # garde la proposition initiale et on signale
                if not validate_definition(corrected, 'verif'):
                    definition = corrected
                    applied = True
                else:
                    warnings.append("La passe de vérification a proposé une correction "
                                    "NON VALIDE — conservée en l'état, à relire de près")
            verification = {'issues': issues, 'applied': applied,
                            'answers': vres.get('answers', [])}
        except Exception as e:
            verification = {'error': f"Passe de vérification en échec : {e}",
                            'issues': [], 'applied': False, 'answers': []}

    # ── 4. Validation finale ─────────────────────────────────────────────────
    suggested_id = re.sub(r'[^A-Z0-9_]', '',
                          str(proposal.get('suggested_id', 'NOUVEAU_CONCOURS')).upper()) or 'NOUVEAU_CONCOURS'
    errors = validate_definition(definition, suggested_id)

    date_preview = ''
    if definition.get('date_rule'):
        try:
            date_preview = calc_contest_date(definition['date_rule'])
        except Exception:
            pass

    return {
        'ok': True,
        'suggested_id': suggested_id,
        'definition': definition,
        'citations': citations,
        'warnings': warnings,
        'confidence': confidence,
        'validation_errors': errors,
        'verification': verification,
        'date_preview': date_preview,
        'extractor': extractor,
        'text_chars': len(rules_text),
    }
