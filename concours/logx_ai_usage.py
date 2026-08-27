# -*- coding: utf-8 -*-
"""Suivi de consommation IA — des FAITS, pas des prix inventés.

L'opérateur paie ses propres crédits d'API : ce module compte les tokens
RÉELLEMENT renvoyés par les APIs (input/output), par fournisseur et par modèle,
pour lui donner de la VISIBILITÉ sur sa consommation. Aucune valeur de domaine
n'est inventée (règle du dépôt) : un COÛT n'est estimé QUE si l'opérateur a
lui-même configuré ses tarifs — sinon on ne montre que des tokens (des faits).

Journal EN MÉMOIRE, borné dans l'esprit (agrégat, pas d'historique illimité),
thread-safe (comme le journal d'audit TX). N'écrit rien sur disque, ne survit pas
au redémarrage. `enregistrer` ne lève JAMAIS : un défaut de comptage ne doit
jamais casser un appel IA.
"""
import json
import threading

_lock = threading.Lock()
_calls = 0
_in = 0
_out = 0
_par_fournisseur = {}   # provider -> {'calls','in','out','models':{model:{...}}}


def enregistrer(provider, model, in_tokens, out_tokens):
    """Ajoute une utilisation (tokens in/out) pour un fournisseur/modèle. Robuste :
    ignore silencieusement une entrée invalide (jamais d'exception vers l'appelant)."""
    global _calls, _in, _out
    try:
        it = int(in_tokens or 0)
        ot = int(out_tokens or 0)
    except (TypeError, ValueError):
        return
    if it < 0 or ot < 0:
        return
    p = str(provider or 'inconnu')
    m = str(model or '?')
    with _lock:
        _calls += 1
        _in += it
        _out += ot
        d = _par_fournisseur.setdefault(p, {'calls': 0, 'in': 0, 'out': 0, 'models': {}})
        d['calls'] += 1
        d['in'] += it
        d['out'] += ot
        md = d['models'].setdefault(m, {'calls': 0, 'in': 0, 'out': 0})
        md['calls'] += 1
        md['in'] += it
        md['out'] += ot


def enregistrer_reponse(provider, model, data):
    """Extrait les tokens d'une réponse d'API selon la forme du fournisseur, puis
    enregistre. UNE SEULE vérité pour les formes de `usage` des fournisseurs :
      - anthropic : usage.input_tokens / usage.output_tokens
      - gemini    : usageMetadata.promptTokenCount / candidatesTokenCount
      - openai-compatibles : usage.prompt_tokens / usage.completion_tokens
    `data` : dict déjà parsé OU octets/chaîne JSON. Robuste : ignore tout ce qui
    ne correspond pas, ne lève JAMAIS (un défaut de comptage ne casse rien)."""
    try:
        d = data if isinstance(data, dict) else json.loads(data)
        if provider == 'anthropic':
            u = d.get('usage') or {}
            it, ot = u.get('input_tokens'), u.get('output_tokens')
        elif provider == 'gemini':
            u = d.get('usageMetadata') or {}
            it, ot = u.get('promptTokenCount'), u.get('candidatesTokenCount')
        else:
            u = d.get('usage') or {}
            it, ot = u.get('prompt_tokens'), u.get('completion_tokens')
    except Exception:
        return
    enregistrer(provider, model, it, ot)


def resume(prix_usd_par_mtok=None):
    """Résumé FACTUEL : nb d'appels, tokens in/out (total + par fournisseur/modèle).

    `prix_usd_par_mtok` (OPTIONNEL, fourni par l'opérateur) = {provider: {'in': X,
    'out': Y}} en USD par MILLION de tokens. Fourni -> ajoute un coût estimé
    UNIQUEMENT pour les fournisseurs tarifés (jamais de prix par défaut inventé)."""
    with _lock:
        out = {
            'calls': _calls, 'in_tokens': _in, 'out_tokens': _out,
            'par_fournisseur': {
                p: {'calls': d['calls'], 'in': d['in'], 'out': d['out'],
                    'models': {m: dict(md) for m, md in d['models'].items()}}
                for p, d in _par_fournisseur.items()},
        }
    if prix_usd_par_mtok:
        total = 0.0
        tarife = False
        for p, d in out['par_fournisseur'].items():
            tar = prix_usd_par_mtok.get(p) if hasattr(prix_usd_par_mtok, 'get') else None
            if not tar:
                continue
            # Parse DÉFENSIF : un tarif malformé (config opérateur) est ignoré,
            # jamais une exception (aucun 500 sur /ai/usage).
            try:
                c = (d['in'] / 1e6) * float(tar.get('in', 0)) + (d['out'] / 1e6) * float(tar.get('out', 0))
            except (TypeError, ValueError, AttributeError):
                continue
            tarife = True
            d['cout_usd_estime'] = round(c, 4)
            total += c
        if tarife:
            out['cout_usd_estime'] = round(total, 4)
            out['cout_note'] = 'Estimation basée UNIQUEMENT sur les tarifs que vous avez configurés.'
    return out


def _reset():
    """Réinitialise l'agrégat (tests / effacement éventuel)."""
    global _calls, _in, _out
    with _lock:
        _calls = 0
        _in = 0
        _out = 0
        _par_fournisseur.clear()
