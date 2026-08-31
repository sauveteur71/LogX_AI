# État des données XOTA (validation de format ≠ base de sites)

Note technique honnête (F4GLD, 31/08/2026) : **valider le FORMAT d'une référence
n'est PAS la même chose que disposer d'une BASE de sites** (nom, commune,
coordonnées, statut officiel). LogX AI le distingue explicitement.

## Trois niveaux de données

| Niveau | Ce que LogX sait faire | Exemple |
|---|---|---|
| `format_only` | Vérifier la **syntaxe** de la référence, l'enregistrer, saisie manuelle du nom/lieu | DFCF, DMF |
| `unverified` | idem, + format **provisoire** à reconfirmer sur la source officielle | DMF |
| `full` (base de sites) | Recherche par réf. **et par nom**, nom officiel, coordonnées, statut, source | POTA, SOTA |

**Une référence syntaxiquement valide n'est pas nécessairement une référence
officiellement attribuée ou active.**

## Statut par programme

| Programme | Fonction actuelle dans LogX | Statut |
|---|---|---|
| **POTA** | Base des parcs (~50 000) + recherche + export + upload guidé | ✅ Opérationnel |
| **SOTA** | Base des sommets (181 658) + recherche + points indicatifs + export | ✅ Opérationnel |
| **WWFF** | Dans le moteur (`PROGRAM_SPECS`), **base à relier** (répertoire `wwff_directory.csv` existe) | 🟠 À intégrer |
| **IOTA** | Dans le moteur, base des groupes d'îles à relier | 🟠 À intégrer |
| **DFCF** | **Validation de format** + saisie manuelle (pas de base de châteaux) | 🟡 Format seulement |
| **DMF** | **Validation de format PROVISOIRE** + saisie manuelle | 🟡 À reconfirmer |
| **PARC Community** | Références et règles non documentées techniquement | ⚪ Expérimental |

## DMF — format provisoire

Le format `DMF01.001` est retenu à titre **provisoire** : la source officielle
`dmf.r-e-f.org` était **indisponible (HTTP 503)** lors de l'implémentation. Le
validateur est donc **tolérant** (séparateur `.` ou `-`, espace/tiret optionnel,
Corse 2A/2B) : il **ne rejette pas** une référence réelle qui ne suivrait pas
exactement ce format. **Statut : à reconfirmer** quand le site officiel revient.

## DFCF — validation de format uniquement

La validation **syntaxique** est disponible (réf. `DFCF-01001`, sourcée
`dfcf.fr/reglement.html`). **Aucune base de données** de forts/châteaux n'est
intégrée : le nom, la commune, le département et la position doivent être
**saisis à la main**. Le rayon (1000 m depuis le 01/01/2026) et les modes
(CW/SSB) du règlement ne sont pas modélisés comme règles bloquantes.
**Statut : format_only.**

## Import futur des bases DFCF/DMF (chantier data séparé)

À traiter comme un projet indépendant : identifier la source officielle →
télécharger/demander la liste (CSV/XLSX/PDF/HTML) → normaliser les références
(en conservant la **saisie brute**, sans altérer un numéro réel) → dédupliquer →
géocoder si autorisé → **conserver l'URL et la date de la source** → publier une
version interne. Un **manifeste** (`source_url`, `retrieved_at`, `source_status`,
`records_imported`, `validation_status`) accompagne chaque import.

## Formulation utilisateur

> Les références POTA et SOTA peuvent être **recherchées** dans leurs bases de
> sites. Pour **DFCF et DMF**, LogX AI assure une **validation syntaxique** et un
> enregistrement **manuel** de la référence, mais ne dispose **pas encore** d'un
> catalogue intégré des forts, châteaux et moulins. Le format **DMF** utilisé est
> **provisoire** et doit être reconfirmé auprès de la source officielle.
