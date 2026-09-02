# Peut-on alléger le code ? — analyse vérifiée (nuit du 30/08/2026)

Demandé par F4GLD (« regarde s'il est possible d'alléger le code »). Travail
autonome, avec la règle de sécurité de la nuit : **ne rien retirer sans preuve
exhaustive et sans ton arbitrage** — un retrait à l'aveugle sur un dépôt que tu
distribues est trop risqué (cf. `PASSATION.md`).

## Conclusion courte

**Le code Python est déjà serré. Il n'y a AUCUN allègement mécaniquement sûr à
faire seul.** Mesuré :

- **Lint CI (E9 + F, pyflakes) déjà propre** : zéro import, variable ou f-string
  inutilisés en production (la CI le refuserait sinon).
- **Zéro code inatteignable** (`vulture --min-confidence 80`, filtre `unreachable` = 0).
- **Zéro attribut/propriété jamais lu** en confiance haute.
- **Zéro module `.py` orphelin** : chaque fichier est importé quelque part.

Ce que `vulture` signale comme « unused function » (37 candidats à 60 %) n'est
**pas du code mort** : ce sont soit des faux positifs de framework, soit du code
**sécurité gelé**, soit de l'**API testée non encore câblée** — dont le retrait
est un **jugement produit qui t'appartient**, pas un nettoyage automatique.

## Les 37 candidats `vulture`, classés (vérifiés un par un)

### A. Faux positifs — NE PAS toucher (appelés par un framework)
Ces méthodes sont appelées par réflexion/héritage, jamais par un `nom()` visible :
- `logx_http.py` : `do_GET`, `do_POST`, `do_OPTIONS`, `do_DELETE`, `log_message`
  — surcharges de `BaseHTTPRequestHandler`, appelées par `http.server`.
- `logx_rules_ai.py` : `http_open`, `https_open` — handlers `urllib` appelés par
  l'opener.

### B. Sécurité émission / radio — ZONE GELÉE, ne pas toucher
Retirer ou déplacer ceci touche à la sûreté d'émission (verrous documentés
`PASSATION.md` #251/#255) — hors périmètre d'un travail autonome :
- `logx_tx_consent.py` : `lock_tx`, `vider_audit`
- `logx_ft2.py` : `envoyer_reply_decodium`, `envoyer_halt_tx_decodium`
- `logx_tci.py` : `send_cw_message`
- `logx_cat.py` : `get_ptt`, `get_smeter`, `etat_ptt_ligne` (état PTT/S-mètre)

### C. API testée mais NON câblée dans un chemin vivant — TON ARBITRAGE
**Vérifié** : chacune est définie en production et référencée **uniquement par
ses tests** (aucun appelant de production). Ce sont probablement des accesseurs
publics de module ou des restes d'une fonctionnalité dont l'usage a été retiré.
Les supprimer = retirer la fonction **et ses tests**. À toi de dire, pour chacune,
« API que je garde » ou « reste à purger » :

| Fonction | Fichier | Note |
|---|---|---|
| `modes_de_bande` | logx_frequences.py | accesseur ; le module expose déjà `digital_table`/`ft2_decodium` (eux, câblés via `/freq/*`) |
| `segment_for` | logx_frequences.py | idem, accesseur alternatif |
| `centres_activite` | logx_bandplan_vhf.py | accesseur du plan de bande VHF (famille `segments`/`centres_activite`) |
| `bornes`, `segment_a`, `alternatives_nb`, `contraintes_puissance` | logx_bandplan_vhf.py | accesseurs du même module (noms courants → vérifier le contexte avant tout retrait) |
| `RigManager` + `list_active` | logx_cat.py | **classe multi-radio** testée (test_cat + test_cat_basse_solides) — ressemble à une **fonctionnalité** (SO2R/multi-poste), pas à un déchet : je recommande de GARDER |
| `radio_pour_bande` | logx_station.py | sélection radio par bande |
| `suggest` | logx_callhistory.py | suggestion Call History |
| `kpa_parse_vi` | logx_amp.py | parse V/I ampli KPA (testé) |
| `duree_totale_ms` | logx_cw_serial.py | durée CW (testé) — adjacent CW, prudence |
| `valider` | logx_satellites.py | validation satellites (nom courant → vérifier) |
| `fermer` | logx_so2r.py, logx_winkeyer.py | fermeture ressource (nom très courant → vérifier) |

### D. Aides de test (reset/clear) — GARDER
Servent à l'isolation entre tests, retrait sans valeur de production :
- `_reset` (logx_ai_usage.py), `_vider` (logx_cw_journal.py),
  `reset_key_cache` (logx_crypto.py), `reset_history` (logx_es_opening.py).

## La seule vraie « lourdeur » : `logx_http.py` (9244 lignes)

C'est le seul point où le mot « alléger » a un sens **structurel** : ce fichier
mélange le routage HTTP, des dizaines de handlers d'endpoints et de la logique
métier. Le scinder par domaine (ex. `handlers_sota.py`, `handlers_tx.py`,
`handlers_log.py`, un routeur mince) le rendrait beaucoup plus lisible.

**MAIS** : c'est un **gros refactor à risque** sur le cœur du serveur (le
routage doit rester identique, chaque handler doit garder son auth/verrous). À
ne PAS faire de nuit sans ton feu vert et une vérification pas-à-pas. Si tu le
veux, on le fait ensemble, par petites tranches (un domaine de handlers à la
fois, chaque tranche derrière sa PR + CI verte), pas d'un bloc.

## Recommandation

1. **Ne rien retirer** aujourd'hui : le gain (quelques dizaines de lignes) ne
   vaut pas le risque, et le code est déjà propre.
2. Si tu veux vraiment purger : parcours la **section C** et dis-moi lesquelles
   sont des restes (je les retire alors **avec leurs tests**, une PR revue par toi).
   Je recommande de **garder `RigManager`** (fonctionnalité, pas déchet).
3. Le vrai chantier d'allègement, si tu le souhaites un jour, c'est **scinder
   `logx_http.py`** — encadré, par tranches, ensemble.

*Méthode : `ruff check .` (E9,F), `vulture *.py` (confiances 60→100), recherche
exhaustive de références py+js+html par candidat. Aucune modification de code
n'a été faite — ce document est purement consultatif.*
