---
name: tx-human-consent
description: Règles de sécurité OBLIGATOIRES pour toute fonction d'ÉMISSION radio de LogX AI (PTT, CW keyer, DVK voix, FT8/FT4, numérique). À charger AVANT d'écrire, modifier ou proposer le moindre code qui pourrait déclencher une transmission RF. Toute émission exige une autorisation humaine explicite, interactive, tracée et temporaire — jamais automatique.
---

# Politique TX obligatoire — LogX AI

**Toute émission RF doit exiger une autorisation humaine explicite, interactive,
traçable et temporaire.** L'IA prépare, l'humain déclenche. Interdire toute
émission automatique. Ce skill s'applique à TOUT chemin qui peut activer une
émission : PTT (CAT/DTR/RTS/VOX), keyer CW, keyer vocal (DVK), séquenceur
FT8/FT4, transmission numérique.

Voir aussi, côté produit, les décisions actées de F4GLD : « écrire ≠ émettre »,
validation on-air = son geste, garde-fous obligatoires (mémoire
`feedback-autorisation-code-emission`, `projet-keyer-cw-natif`).

## Ce que l'IA PEUT faire

- Décoder et analyser les signaux reçus.
- Préparer une réponse FT8, CW, voix ou numérique.
- Proposer une fréquence, un mode, une puissance et un message TX.
- Afficher un aperçu COMPLET de l'émission prévue.
- Demander l'autorisation d'émettre.

## Ce que l'IA ne PEUT JAMAIS faire

- Activer PTT, TX, keyer CW ou DVK sans autorisation humaine valide.
- Réutiliser une ancienne autorisation après son expiration.
- Émettre après un changement de fréquence TX, mode, split, puissance,
  indicatif station ou configuration radio sans NOUVELLE validation.
- Émettre si le CAT, l'horloge UTC, la fréquence, le mode ou l'état de
  sécurité de la radio ne sont pas confirmés.
- Émettre lorsqu'un bouton **Stop TX** / arrêt d'urgence est activé.

## Ce qu'une autorisation d'émission DOIT être

- Déclenchée par une action explicite dans l'interface : bouton « Autoriser
  émission » ou « Émettre maintenant ».
- Précédée de l'affichage : fréquence TX, bande, mode, puissance, message,
  durée prévue, radio sélectionnée et méthode PTT.
- Associée à un **jeton d'autorisation unique**.
- À **expiration rapide** (ex. 30 s).
- Invalidée au premier changement de paramètre radio important.
- Journalisée en UTC avec l'identité de l'opérateur.
- Annulable à tout instant par **Stop TX**.

## Contrôle CÔTÉ BACKEND (pas seulement l'interface JS)

L'autorisation doit être vérifiée par le BACKEND avant tout PTT. Juste avant
d'émettre, RELIRE l'état CAT réel (fréquence, mode, split, puissance, connexion)
et comparer au jeton. Modèle de référence :

```python
def authorize_transmission(consent, radio_state) -> None:
    if not consent.is_valid():           # non utilisé ET non expiré
        raise PermissionError("Autorisation TX absente, utilisée ou expirée")
    if radio_state.frequency_hz != consent.frequency_hz:
        raise PermissionError("Fréquence TX modifiée")
    if radio_state.mode != consent.mode:
        raise PermissionError("Mode radio modifié")
    if radio_state.power_w != consent.power_w:
        raise PermissionError("Puissance TX modifiée")
    if radio_state.ptt_locked:
        raise PermissionError("PTT verrouillé par sécurité")
    if not radio_state.cat_connected:
        raise ConnectionError("État CAT non confirmé")
    consent.used = True
```

Le jeton (`TxConsent`) porte : token unique, indicatif opérateur, radio, fréquence
Hz, mode, puissance, message, `expires_at` (UTC), `used`. `is_valid()` = non
utilisé ET `now < expires_at`.

## FT8 (séquence unique par défaut)

- Une validation autorise **une seule séquence TX**.
- Une autorisation de SESSION limitée reste possible mais **désactivée par
  défaut** ; si activée : expiration automatique (ex. 5 min) OU nombre max de
  transmissions, interruptible immédiatement.
- **Commencer par implémenter uniquement « Émission unique ».** La session
  limitée viendra plus tard, après tests approfondis.

## Flux imposé

1. L'IA détecte un appel / prépare une réponse.
2. L'IA affiche ce qui sera transmis (aperçu complet).
3. L'humain clique « Émettre maintenant ».
4. Le backend valide l'état RÉEL de la radio.
5. Le backend crée une autorisation TX temporaire (jeton).
6. L'émission démarre seulement si l'autorisation est toujours valide.
7. L'autorisation est supprimée après la transmission.
8. L'action est ajoutée au journal d'audit.

Écran de confirmation type :

```
Autoriser l'émission ?
Radio        : IC-7300
Bande        : 20 m
Fréquence TX : 14 074 000 Hz
Mode         : USB-D / FT8
Puissance    : 20 W
Message      : F4ABC F1XYZ R-12
Durée        : 12,6 s
PTT          : CAT
[Annuler]  [Autoriser une émission]
```

## Journal d'audit (entrée non modifiable, UTC)

```json
{
  "event": "TX_AUTHORIZED_AND_EXECUTED",
  "timestamp_utc": "2026-08-25T03:49:22Z",
  "operator_callsign": "F1XYZ",
  "radio_id": "ICOM-IC7300-USB-001",
  "frequency_hz": 14074000, "mode": "FT8", "power_w": 20,
  "message": "F4ABC F1XYZ R-12", "ptt_method": "CAT",
  "consent_token": "redacted", "consent_mode": "single_transmission",
  "human_action": "UI_CONFIRM_TX"
}
```

## Bouton STOP TX (global, permanent)

Doit IMMÉDIATEMENT : annuler toute autorisation en attente ; désactiver le PTT ;
interrompre la séquence si le matériel le permet ; verrouiller toute nouvelle
émission jusqu'à une nouvelle action humaine.

## Deux niveaux d'autorisation

| Mode | Usage | Règle |
|---|---|---|
| Émission unique | Réponse FT8, CQ, message CW, test PTT | 1 confirmation humaine PAR transmission |
| Session limitée | FT8 semi-auto, contest assisté | Autorisation initiale, expiration rapide + limites strictes (PLUS TARD) |

**Priorité : n'implémenter que « Émission unique » pour commencer.**
