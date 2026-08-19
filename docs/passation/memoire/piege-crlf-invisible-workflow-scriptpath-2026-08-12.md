---
name: piege-crlf-invisible-workflow-scriptpath
description: "Workflow(scriptPath) rejette un script avec \"control characters\" si du JSON généré par Python sur Windows a été écrit en mode texte (CRLF) — invisible à toute relecture Python normale"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 98b0707f-1a89-40bf-8422-4ab7b88ba78a
  modified: 2026-08-12T08:35:39.219Z
---

En générant par script Python le fichier `.js` d'un Workflow (findings embarqués en
littéral, motif déjà utilisé pour [[chantier-triage-et-correctifs-majeur-2026-08-12]]
et pour le triage des 162 mineur), l'appel `Workflow({scriptPath})` a échoué avec :
`"script contains control characters that would be hidden in the approval dialog"`.

**Cause** : `open(path, 'w', encoding='utf-8')` sur Windows, SANS `newline=''`,
traduit chaque `\n` écrit en `\r\n` (mode texte par défaut). Les fichiers JSON
intermédiaires (`json.dump(...)` puis relus/réécrits, ou simplement écrits avec
`open(...,'w')`) accumulaient donc des `\r` réels — 1368 dans un cas. Une fois
concaténés dans le `.js` final, ces `\r` sont des caractères de contrôle Unicode
(Cc, U+000D) au milieu de littéraux JS, ce que le validateur du dialogue de
permission refuse à raison (un `\r` en milieu de ligne peut faire disparaître du
texte à l'affichage).

**Pourquoi c'est resté invisible à toute vérification Python** : `open(path,
encoding='utf-8')` en LECTURE (sans préciser `newline=`) active la traduction
« universal newlines » de Python — `\r\n` est silencieusement renormalisé en
`\n` à la lecture. Un script de scan qui ouvre le fichier normalement (comme un
premier essai de diagnostic ici) ne trouve donc RIEN, alors que le fichier sur
disque contient bel et bien des `\r` bruts. Seule une lecture en mode binaire
(`open(path, 'rb')` puis `data.count(b'\r')`) révèle le problème.

**Fix** : à chaque écriture ET lecture de fichier texte intermédiaire par script
Python sur Windows (JSON de données, script `.js` final), passer explicitement
`newline=''` à `open()` — empêche toute traduction dans les deux sens. Vérifier
ensuite avec une lecture binaire (`'rb'` + `.count(b'\r')`) plutôt qu'une lecture
texte, qui masquerait un résidu.

**Comment appliquer** : réflexe systématique pour tout futur script Python qui
génère un fichier destiné à `Workflow({scriptPath})` sur ce poste Windows —
`newline=''` sur CHAQUE `open(..., 'w', ...)` de la chaîne de génération, pas
seulement sur l'écriture finale (le pipeline `.json` → relecture → `.js` propage
le `\r` à chaque étape texte si une seule étape l'introduit).
