---
name: piege-faux-dom-stub-et-passes-paires
description: "Quatre pièges de test qui laissent vivre du code faux — stub de faux DOM trop pauvre (bloc jamais exécuté) PUIS trop permissif (dataset accepte un tiret que le vrai DOMStringMap refuse, l'exception avortant la traduction de toute la page), nombre PAIR de passes qui masque une oscillation, et regex littérale compilée paresseusement par V8 (py_mini_racer est sans ICU : \\p{...} y est une SyntaxError)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 85c2258d-a894-47e3-b0c9-47556f9c1e2c
  modified: 2026-07-30T21:29:17.101Z
---

Deux pièges de méthode de test, découverts le 26/07/2026 en corrigeant l'oscillation
fr ⇄ langue cible des attributs `title`/`placeholder` dans `concours/logx_i18n.js`.

**1) Un stub « inoffensif » du faux DOM peut rendre tout un bloc INEXÉCUTABLE en test.**
Dans `concours/tests/test_i18n_dynamic_retranslation.py`, `makeEl()` définissait
`node.querySelectorAll = function(){ return []; }`. Le bloc attributs de `walk()`
commence par `root.querySelectorAll('[title],[placeholder]')` : il n'a donc JAMAIS
tourné une seule fois dans les ~15 tests JS de ce fichier. Le défaut était invisible
non pas faute de tests, mais parce que le harnais garantissait silencieusement zéro
couverture sur ce chemin.

**Why:** un stub qui renvoie une valeur vide ne fait pas échouer de test — il fait
disparaître du code de la mesure, sans aucun signal.

**How to apply:** quand un bloc a un défaut échappé aux tests, ne pas seulement
ajouter un test — vérifier d'abord que le harnais PEUT l'atteindre (compter les
éléments retournés, ou faire échouer volontairement l'assertion). Et traiter tout
stub renvoyant `[]`/`null`/`{}` en dur dans le faux DOM comme une zone d'ombre à
inventorier.

**2) Un nombre PAIR de passes masque une oscillation.**
Le défaut inversait la valeur à CHAQUE passe (DE, FR, DE, FR…). Un test qui appelait
`rcTranslate()` deux fois puis assertait une seule fois à la fin PASSAIT sur le code
buggé : deux inversions ramènent la bonne valeur. C'est la même raison qui a fait que
personne ne l'a jamais vu à l'œil.

**Why:** l'état final d'une bascule ne dit rien sur la stabilité du chemin.

**How to apply:** pour tout défaut de type clignotement/bascule, asserter APRÈS CHAQUE
passe (boucle avec message indiquant le numéro de passe), jamais seulement à la fin ;
et prouver le test en le passant sur le code d'AVANT (`git checkout --` du seul fichier
source, le test restant non commité) — ici 5 tests sur 7 échouaient avant, 0 après.

**3) Une regex littérale invalide peut dormir des mois : V8 ne la compile qu'à sa
PREMIÈRE ÉVALUATION.** (27/07/2026, suite du même chantier.) `logx_i18n.js` contenait
`/^([^\p{L}]+?\s*)(\p{L}.*)$/u` dans `translateText()`, après un `return` qui
aboutissait presque toujours. Or **le V8 embarqué par py_mini_racer est un build SANS
ICU** : `\p{...}` y lève `SyntaxError: Invalid property name in character class`.
Résultat, la règle du « préfixe emoji » n'a jamais tourné une seule fois en test, et
elle aurait fait tomber tout moteur sans ICU dès le premier libellé non traduit. Rendue
visible seulement en factorisant le code : la fonction partagée était appelée pour
CHAQUE attribut, dont un `title` absent du dictionnaire → la ligne s'exécutait enfin, et
les 30 tests du fichier tombaient d'un coup. Remplacé par une boucle
`c.toLowerCase() !== c.toUpperCase()` (portable, testable).

**Why:** une regex littérale n'est PAS validée au chargement du script. Tant que la
ligne n'est pas atteinte, un motif invalide est indistinguable d'un motif correct — et
« les tests passent » ne prouve rien sur ce chemin.

**How to apply:** ne jamais utiliser `\p{...}` (ni aucune propriété Unicode) dans le JS
de ce projet si le chemin doit être couvert par la suite py_mini_racer — le moteur des
tests n'a pas les mêmes capacités que Chrome. Et vérifier l'équivalence d'un tel
remplacement dans un VRAI navigateur, sur un corpus réel : ici 1005 chaînes de
`logx_configuration.html`, 14 divergences toutes multilignes, aucune conséquence (aucun
de ces cœurs n'est une clé du dictionnaire) — c'est cette mesure qui autorise à
conclure, pas le raisonnement seul.

**4) Le même stub peut être plus PERMISSIF que le vrai DOM — et alors il certifie du
code qui ne peut pas tourner.** (30/07/2026, même fichier.) `makeEl()` écrivait
`dataset:{}`, un objet JS ordinaire qui accepte n'importe quelle clé. Or `dataset` est
un **DOMStringMap**, qui REFUSE tout nom contenant un tiret suivi d'une minuscule.
`translateAttr()` fabrique sa clé de mémorisation à partir du NOM de l'attribut : dès
que `aria-label` a été ajouté à la boucle, le navigateur levait `Failed to set a named
property '__i18n_aria-label' on 'DOMStringMap'`. L'exception n'était rattrapée nulle
part → elle avortait le `forEach`, donc la traduction des attributs de tous les
éléments SUIVANTS. **Un seul `aria-label` faisait tomber le reste de la page**, et le
symptôme visible (« ce `title` n'est pas traduit ») envoie chercher dans le
dictionnaire, là où il n'y a rien à trouver. 2152 tests verts pendant ce temps.
Corrigé par une clé assainie (`attr.replace(/[^A-Za-z0-9]/g, '_')`) ; **pas** de
`try/catch` global, qui masquerait le prochain défaut exactement pareil. Le stub est
désormais un `Proxy` qui refuse le tiret comme le navigateur, verrouillé par un test
dédié — sans lui, les tests du défaut redeviendraient incapables de le voir.

**Why:** le piège n°1 était un stub trop pauvre (zéro couverture) ; celui-ci est un
stub trop *gentil* — il exécute le chemin, l'assertion passe, et le verdict est FAUX.
Plus dangereux, parce qu'il ressemble à de la couverture réelle.

**How to apply:** un faux DOM doit reproduire les **refus** de l'API, pas seulement ses
succès (`dataset` sans tiret, `classList` sans espace, `setAttribute` avec nom
invalide…). Et le réflexe qui a tout débloqué : quand le dictionnaire est complet, que
le moteur demande bien la valeur, et que rien ne se traduit quand même — **lire la
console du navigateur avant de relire le code**. Elle nommait le défaut mot pour mot.

**5) `logx_i18n.js` mélange DEUX styles de guillemets — un extracteur qui n'en lit
qu'un est aveugle au dictionnaire principal.** (30/07/2026.) Le dictionnaire de BASE
utilise des **apostrophes simples** et empile **plusieurs paires par ligne**
(`'Départements REF': '…', 'TABLEAU DE CHASSE': '…',`) ; les objets correctifs
(`T_LOGBOOK_FIX`, `T_PARITY_FIX`, `T_LOGBOOK_FIX2`…) utilisent des guillemets doubles,
une paire par ligne. Mon extracteur ne lisait que le second style → il a déclaré
manquantes des dizaines de clés déjà traduites. J'en ai « re-traduit » sept, et comme
les correctifs sont appliqués APRÈS par `Object.assign`, ma formulation **écrasait**
l'ancienne (« TABLEAU DE CHASSE » serait passé de *HUNTING TABLE* à *HUNTING PROGRESS*
dans les 7 langues). Une « lacune allemande » signalée était du même artefact.

Trois autres règles à reproduire sous peine de fausses alertes : `translateKey()` isole
le **cœur après un préfixe non-lettre** (emoji, `(`, `⚠`) ; `translateTitle()` ne
traduit que le **suffixe après ` — `** ; et `walk()` part de `<body>`, donc le contenu
de `<title>` ne doit PAS être compté comme nœud texte.

**Why:** trois fois de suite, c'est l'instrument de mesure qui était faux, pas le code
audité — et un inventaire faux ne se contente pas de rater du travail, il en invente.

**How to apply:** avant tout inventaire i18n sur ce dépôt, vérifier que l'extracteur
reproduit les règles du moteur ET les deux styles de guillemets ; le contrôle qui a
tout révélé est `tests/test_i18n_parite_langues.py` (comparaison du dictionnaire
**effectif après fusion**, jamais objet par objet : le dictionnaire de base est
volontairement asymétrique, l'anglais y porte des clés en plus que `T_PARITY_FIX`
comble ensuite pour les six autres).

Voir aussi [[chantier-nettoyage-i18n-mufmap-fuseaux-2026-07-24.md]] et
[[chantier-feedback-batch2-2026-07-24.md]] (autres défauts i18n), et
[[fix-portee-concours-annee]] (même famille : faire relire par un agent qui EXÉCUTE le
code plutôt qu'un qui le lit).
