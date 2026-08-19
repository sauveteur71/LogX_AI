---
name: chantier-audit-securite-94-correctifs-2026-08-02
description: "Audit sécurité/qualité complet (3 axes) puis application des 94 correctifs — TOCTOU, XSS, SSRF, DNS non borné, secrets localStorage — fusionné sur main"
metadata: 
  node_type: memory
  type: project
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-02T15:30:37.465Z
---

F4GLD a demandé un audit technique complet en 3 axes (robustesse, sécurité OWASP,
qualité/maintenabilité) avec un prompt d'expert explicite, puis « applique toutes
les correction necessaires ». Résultat : 94 constats confirmés, tous corrigés,
fusionnés sur `main` (commit `c158117`, 02/08/2026).

**Méthode** : Workflow à 28 agents (finder + vérificateur adversarial par
constat) pour l'audit, puis Workflow à 17 agents pour appliquer les correctifs
— **partitionnés par FICHIER, pas par constat**, pour qu'aucun agent n'écrive
jamais dans un fichier qu'un autre modifie en parallèle. Conséquence attendue :
4 correctifs touchant DEUX fichiers n'ont eu que leur moitié « domicile »
faite par les agents (auto-signalés `status: 'adapted'`/`'skipped'` avec note
claire) — j'ai fermé les 4 manuellement après coup (jeton LAN serveur+UI,
`get_scoring_info` côté appelant, `extra_hosts` côté appelant, endpoint
`/config/secrets` pour la migration localStorage).

**Correctifs marquants** : TOCTOU sur `add_qso_to_log`/`apply_update_and_relaunch` ;
XSS sur `logx_calendrier.html`/`logx_configuration.html` (`?contest=` reflété) ;
SSRF sur `logx_rules_ai._download_bytes()` (liste blanche schéma + résolution IP) ;
secrets (mots de passe QRZ, jeton LAN...) qui ne transitent plus en clair par
`localStorage` (redaction à l'écriture + migration auto-guérissante + endpoint
`/config/secrets` authentifié) ; jeton HMAC-SHA256 optionnel sur la synchro LAN.

**16 régressions de tests** — toutes des conséquences ATTENDUES d'un
comportement plus strict (auth désormais requise sur `/log/next_serial`,
signatures de fonctions changées) — jamais des bugs dans les correctifs eux-mêmes.

**Vérification navigateur SANS toucher au serveur de prod (port 8080)** :
technique réutilisable — copier tout l'arbo `concours/` dans le scratchpad,
patcher `PORT` dans la copie, lancer cette copie sur un port différent
(8199), vérifier en navigateur, puis `Stop-Process` UNIQUEMENT ce PID de
test (confirmé via `Get-NetTCPConnection -LocalPort ... | OwningProcess`
avant de tuer quoi que ce soit). Voir [[contrainte-jamais-toucher-port-8080]]
si cette mémoire existe, sinon : ne jamais killer/redémarrer le process du
port 8080 sans vérifier qui l'a lancé — leçon d'une session antérieure.

**Suite** : voir [[piege-time-monotonic-nest-pas-epoch]] pour le piège de test
découvert EN COURS DE ROUTE (2 échecs CI consécutifs après un 1er correctif
de test qui semblait bon en local).
