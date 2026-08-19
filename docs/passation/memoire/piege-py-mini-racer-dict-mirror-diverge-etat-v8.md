---
name: piege-py-mini-racer-dict-mirror-diverge-etat-v8
description: "PIÈGE tests JS py_mini_racer : un dict Python sérialisé en JSON pour seeder le contexte V8 n'est qu'un instantané figé — les mutations JS ultérieures (classList.toggle...) ne se répercutent JAMAIS dans le dict Python ; toujours relire l'état via ctx.eval(), jamais via le miroir Python. Et ctx.eval() sur un array JS renvoie un JSObject sans len(), passer par JSON.stringify+json.loads"
metadata: 
  node_type: memory
  type: project
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-16T12:19:56.167Z
---

Trouvé le 16/08/2026 en écrivant `tests/test_config_secret_dots.py`
([[chantier-config-panel-plein-ecran-fermeture-uniforme-secrets-2026-08-16]]).
Même famille que [[piege-intl-absent-py-mini-racer]] (limites de
l'infrastructure de test `py_mini_racer`, pas un bug du code produit).

## Le piège n°1 — miroir Python périmé dès la construction

Conception initiale : un dict Python (ex. `{'lotw_password': {'value': '',
'_classes': []}}`) sert à la fois à construire le DOM factice (`ctx.eval('var
_els = %s;' % json.dumps(els))`) ET à être relu côté Python pour les
assertions (`assert 'set' in els['lotw_password_dot']['_classes']`). Ça ne
marche JAMAIS : `json.dumps()` ne fait qu'un instantané au moment de la
construction du contexte — toute mutation faite ENSUITE côté JS
(`classList.toggle('set')` appelée par le code sous test) modifie l'objet
`_els` qui vit dans le moteur V8, complètement déconnecté du dict Python
d'origine. Toutes les assertions échouaient silencieusement (pas d'erreur,
juste un état toujours "avant mutation").

**Contournement** : ne jamais relire l'état via le dict Python. Écrire un
helper qui interroge TOUJOURS le JS via `ctx.eval(...)`, ex. :
```python
def _is_set(ctx, field):
    return ctx.eval("_els['%s_dot']._classes.indexOf('set')" % field) != -1
```

## Le piège n°2 — JSObject n'a pas de len()

`ctx.eval("SOME_JS_ARRAY")` renvoie un objet-proxy `JSObject` côté Python,
pas une vraie liste — `len(...)` lève. Contournement : repasser par une
sérialisation JSON explicite :
```python
fields = json.loads(ctx.eval("JSON.stringify(SOME_JS_ARRAY)"))
```

## Comment l'appliquer

Avant d'écrire un futur test `py_mini_racer` qui a besoin de lire un état
DOM/JS construit dynamiquement par le code sous test (classes CSS, valeurs
de champs modifiées en cours de test, tableaux JS) : écrire le helper de
lecture d'état AVANT les assertions, et le faire systématiquement passer par
`ctx.eval()` (avec `JSON.stringify`/`json.loads` si c'est une collection).
Ne jamais faire confiance à un dict Python utilisé pour le seed initial une
fois le test entré dans sa phase d'exécution.
