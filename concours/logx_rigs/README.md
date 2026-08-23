# logx_rigs — catalogue des postes radioamateur + profils CAT

Amorcé le 23/08/2026 (demande F4GLD). But : une **base durable** de tous les
postes (actuels puis anciens) pour LogX AI — affichage, sélection, et pilotage
CAT natif par modèle, **en complément** de ce qui existe déjà (`logx_cat.py`
CI-V/ASCII, `logx_rig.py` Hamlib, `logx_flrig.py`, `logx_omnirig.py`,
`logx_flexradio.py`, `logx_tci.py`).

## Règle d'or — NON négociable

**Aucune commande CAT n'est écrite de mémoire.** Une trame erronée peut
déclencher un PTT, un QSY TX ou empêcher le retour RX. Chaque commande d'un
profil doit venir d'une **source citable** (manuel officiel / référence CI-V /
CAT du constructeur, ou Hamlib sous licence LGPL respectée) et porter son champ
`source`. Tant qu'un modèle n'est pas sourcé, il figure dans le catalogue en
**métadonnées seulement** (`documentation_status: "à sourcer"`) — jamais avec
des commandes devinées. Ne JAMAIS activer PTT/split/puissance sur une commande
non `verified_on_hardware`.

## Deux niveaux

### 1. `catalogue.json` — métadonnées (factuelles, sûres)
Un enregistrement par modèle. Aucune commande ici. Champs :

| champ | valeurs |
|---|---|
| `id` | identifiant `marque_modele` (ex. `icom_ic705`) |
| `manufacturer`, `model` | texte |
| `status` | `current` \| `legacy` |
| `category` | liste : `HF`, `50MHz`, `VHF`, `UHF`, `SDR`, `QRP`… |
| `protocol` | `icom_civ` \| `yaesu_cat` \| `kenwood_cat` \| `elecraft_cat` \| `flexradio_api` \| `xiegu_cat` \| `tci` \| `hamlib` |
| `transport` | liste : `usb_serial`, `tcp_network`, `civ_bus`… |
| `cat_support` | `native` \| `network_native` \| `serial_external` \| `partial` \| `none` \| `research` |
| `ft8_support` | `full` \| `partial` \| `none` \| `unknown` |
| `documentation_status` | `documented` \| `verified` \| `à sourcer` |
| `profile` | chemin du profil de commandes s'il existe, sinon absent |

### 2. `profils/<marque>/<id>.json` — commandes (sourcées uniquement)
Codes EXACTS du modèle + `source`, `verified_on_hardware`, `capabilities`.
Voir `profils/icom/ic_705.json` (seul profil sourcé à ce stade).

## Statut d'avancement (23/08/2026)
- `catalogue.json` : métadonnées des postes **actuels** (listes fournies par
  F4GLD). Anciens postes : à ajouter (couche 2).
- Profils de commandes : **IC-705 seul** (sourcé). Les autres = `à sourcer`.
- **Décision d'intégration à prendre avec F4GLD** : ce catalogue doit-il
  ALIMENTER `logx_cat.py`/`logx_configuration.js` (une seule source de vérité)
  ou rester une base de référence séparée ? Non tranché — ne pas câbler à
  l'exécution avant cette décision (éviter du code mort).
