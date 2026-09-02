# Concours « à barème flou » — sources de règlement (F4GLD, 31/08/2026)

Les 10 concours de `AMBIGUS_CONNUS` (`tests/test_concours_sans_definition.py`)
rendent `[]` volontairement : leur barème est une **plage ou un mot**, pas des
bandes précises. F4GLD a retrouvé les règlements officiels ci-dessous. Ce
document est la **base sourcée** pour écrire de vraies définitions conformes à
`contest_schema.json` — **sans rien inventer** (règle du dépôt : source citable
ou `VALEUR À SOURCER`).

Index général REF : <https://concours.r-e-f.org/reglements/> ·
Calendrier : <https://concours.r-e-f.org/calendrier/calendrier.php>
Règles communes HF/THF : voir l'index REF (s'appliquent sauf disposition
contraire du règlement particulier).

## Rappels de schéma (ce qu'une définition DOIT respecter)

- **Requis** : `name, organizer, date_rule, bands, modes, exchange, scoring, log_format`.
- **`bands`** = liste de clés MHz **internes** : `'144','432','1296','2320','3400','5760','10368','24048','47088'`… (PAS `'70CM'`).
  Correspondance : 70cm=432 · 23cm=1296 · 13cm=2320 · 9cm=3400 · 6cm=5760 ·
  3cm=10368 · 6mm=24048 · 4mm=47088 · 80m=3.5 · 40m=7 · 20m=14 · 15m=21 · 10m=28.
- **`date_rule`** (grammaire `logx_rules.py:DATE_RULE_PATTERN`) :
  `permanent` | `{first|second|third|fourth|last}_{saturday|sunday}_{mois}[_HHh]`
  | `{…}_full_weekend_{mois}[_HHh]`. **Pas de « _and_ »** (une seule instance par
  définition — une édition mars ET décembre = DEUX définitions).
- **`log_format`** ∈ `{EDI, CABRILLO, ADIF, ''}` — « IARU REG1TEST » n'existe PAS
  dans l'enum : les concours REF THF utilisent **`EDI`**. `CABRILLO` exige aussi `cabrillo_name`.
- **`scoring.type`** ∈ `{km, km_x_locators, km_x_large_locator_squares,
  zone_country_per_band, …, dept_dxcc, summit_points, park_points, wwa_sprint}`,
  OU un bloc **`bricks`** (prédicats/multiplicateurs validés contre `logx_scoring.py`).

## Statut par concours

| ID | Règlement (sourcé F4GLD) | Prêt à écrire ? | Ce qui bloque encore |
|---|---|---|---|
| `UFT_RENCONTRES` | [Rencontres UFT](https://www.uft.net/activites-et-concours/rencontres-uft/) | Presque | **date_rule non sourcée** ; scoring `dept`→mapper (`dept_dxcc` ?) |
| `REF_NAT_TVA` | [reg_nattva 20260516](https://concours.r-e-f.org/reglements/actuels/reg_nattva_fr_20260516.pdf) | Non | scoring **`tva`** absent du schéma/moteur ; bandes SHF exactes à confirmer |
| `REF_NAT_TVA_DEC` | (même règlement, édition décembre) | Non | idem + `date_rule` de l'édition décembre |
| `REF_IARU_TVA` | [reg IARU TVA](https://concours.r-e-f.org/reglements/) | Non | scoring `tva` ; `date_rule` = `second_saturday_june_12h` (OK) ; bandes SHF |
| `REF_CDF_TVA` | [reg CDF TVA](https://concours.r-e-f.org/reglements/) | Non | scoring `tva` ; `date_rule` = `second_saturday_september_14h` (OK) ; bandes SHF |
| `REF_CHALLENGE_THF` | [reg Challenge THF](https://concours.r-e-f.org/reglements/) | Non | scoring « stations/mois × coefficients » **≠ km×loc** — modèle propre à créer ; `date_rule`=`permanent` |
| `REF_IARU_UHF` | [reg IARU UHF/SHF](https://concours.r-e-f.org/reglements/) | Le plus proche | bandes SHF exactes à confirmer sur PDF (repo=8 bandes, exemple F4GLD=6) ; `date_rule`=`first_saturday_october_14h` (OK) ; scoring `km_x_locators` (OK) |
| `REF_F8TD` | **introuvable** — [article F5KEE](https://www.f5kee.fr/technique/le-trophee-f8td-arrive-le-30-aout-rendez-vous-sur-les-micro-ondes/) | Non | `source_incomplete` : garder tel quel jusqu'au règlement officiel |
| `F9NL` | **introuvable** — [calendrier](https://concours.r-e-f.org/calendrier/calendrier.php) (3ᵉ w-e sept., 05:00-10:00 UTC) | Non | `rules_not_found` : garder tel quel |
| `CUSTOM` | — | — | **volontairement vide** (l'opérateur choisit tout) |

## Faits sourcés utiles (pour l'écriture future)

**National TVA** (reg_nattva 20260516) : bandes 432 MHz et au-delà ;
70 cm = 2 pts/km, 23 cm = 4 pts/km, > 23 cm = 10 pts/km (bilatéral) ; échange
radio = report + n° QSO + locator ; échange vidéo = code secret 4 chiffres
différent par bande ; Section 1 = émission/réception, Section 2 = réception seule.

**IARU R1 TVA** : 2ᵉ samedi de juin 12:00→dimanche 18:00 UTC ; 70 cm/23 cm/13 cm/
9 cm/6 cm(?)/1.2 cm ; point à point ; numérotation par bande ; km (moitié en
réception seule).

**CDF TVA** : 2ᵉ samedi de septembre 14:00→dimanche 18:00 UTC ; 432+ ; sections
1/2 comme National TVA.

**Challenge THF** : toute l'année, calcul **trimestriel** ; toutes bandes ≥ 144 MHz ;
une station 1×/mois/bande ; points = nouvelles stations/mois/bande ;
multiplicateurs = départements + grands carrés/bande ; coefficients
144=1, 432=3, 1296=5, ≥2320=10. **Modèle de score spécifique** (pas km×loc).

**IARU UHF/SHF** : 1ᵉʳ samedi d'octobre 14:00→dimanche 14:00 UTC ; 432 MHz et
au-delà (liste exacte à reprendre du PDF).

**Rencontres UFT** : CW ; 80 m (3.520-3.560), 40 m (7.013-7.035), 20 m
(14.030-14.060), 15 m (21.030-21.060), 10 m (28.030-28.060) ; échange membre
RST/n° UFT, non-membre RST/NM ; QSO 1×/bande ; log **Cabrillo** ; délai 15 j ;
catégories assisté/non-assisté, OP/radio-club/QRP/SWL/non-membre.

**Trophée F8TD** (NON officiel, article F5KEE) : 30 août, 04:00-13:00 UTC ;
1296 MHz→47 GHz ; RST + n° + locator ; numérotation par bande ; score km ;
log IARU REG1TEST par bande ; dépôt 1ᵉʳ mercredi suivant. **À NE PAS intégrer
comme définition officielle sans PDF/page REF.**

## Trois chantiers pour finir (pas de la « conversion », du travail de sources)

1. **Moteur de score TVA** (petit chantier) : ajouter un `type` ou des `bricks`
   « pts × relais TVA » à `logx_scoring.py` + l'enum du schéma → débloque les 4 TVA.
2. **Confirmer sur PDF** : les bandes SHF exactes (IARU UHF, IARU/CDF/Nat TVA) et
   les `date_rule` manquants (UFT, édition décembre du National TVA).
3. **Modèle Challenge THF** (stations/mois × mults × coefficients) : score propre.

Ensuite seulement : écrire chaque définition, la valider (`python logx_validate.py`),
et la retirer de `AMBIGUS_CONNUS`. F9NL et F8TD restent `rules_not_found` /
`source_incomplete` jusqu'à un règlement attribuable à l'organisateur.
