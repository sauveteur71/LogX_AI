# RAPPORT DE RELECTURE — RadioContest AI v3.0
**Date :** 18 juin 2026  
**Fichiers analysés :** radiocontest.html · logbook.html · configuration.html · serveur.py · config.json · calldb.json

---

## 🔴 BUGS CRITIQUES (bloquants)

### 1. logbook.html — FICHIER TRONQUÉ (JavaScript incomplet)
Le fichier se termine brutalement à la ligne 1147 au milieu de la déclaration `async function refreshCluste` sans fermeture de fonction, sans `</script>`, sans `</body>`, sans `</html>`.

**Fonctions MANQUANTES qui ne sont jamais définies :**
- `refreshCluster()` — rafraîchissement du cache cluster
- `lookupCall(call)` — lookup dans calldb.json
- `lookupCluster(call)` — lookup dans le cache cluster
- `applyCallData(dbData, clusterData)` — auto-remplissage du locator
- `showCompassInline()` / `hideCompassInline()` — boussole inline
- `searchCalls(query)` — recherche autocomplétion
- `showAC(results, query)` / `hideAC()` — affichage autocomplete

**Conséquence :** l'appel à `lookupCall()` dans `onCallInput()` lève une ReferenceError silencieuse. L'autocomplétion est totalement non-fonctionnelle. Le fichier est parsé par le navigateur grâce à la tolérance HTML5 mais avec un état JavaScript dégradé.

**Correction :** restaurer la fin du fichier depuis le ZIP de backup (`RadioContest_F6KQJ_2026_STABLE_v3.0.zip`).

---

### 2. radiocontest.html — Grille de carte hardcodée, ignore BOUNDS
Dans `initMap()` (ligne 445-446), la grille SVG est dessinée avec des constantes fixes :
```javascript
for(let lon=-12;lon<=42;lon+=4)...
for(let lat=32;lat<=70;lat+=4)...
```
Ces valeurs ne changent PAS quand `switchMapMode()` bascule en mode monde. La grille reste Europe même quand la carte affiche le monde entier.

**Correction :** remplacer par `BOUNDS.lonMin/Max` et `BOUNDS.latMin/Max` avec `BOUNDS.gridLon/gridLat`.

---

### 3. radiocontest.html — Bouton mapModeBtn inexistant
Dans `switchMapMode()`, le code fait :
```javascript
const btn = document.getElementById('mapModeBtn');
if(btn) btn.textContent = ...
```
Cet élément n'existe nulle part dans le HTML. Il n'y a aucun bouton pour changer de mode carte manuellement. Le switch automatique fonctionne mais l'opérateur ne peut pas forcer la vue Europe/Monde.

**Correction :** ajouter un bouton dans le header avec `id="mapModeBtn"`.

---

### 4. logbook.html — CONTEST_END_UTC hardcodé
```javascript
const CONTEST_END_UTC = new Date('2026-07-06T14:00:00Z');
```
Ce countdown ne change jamais, quel que soit le concours sélectionné. Pour le National THF (mars), l'IARU VHF (septembre), etc., le compte à rebours sera faux.

**Correction :** lire la date de fin depuis `localStorage('radiocontest_config')` → `contest.end_date + end_utc`.

---

### 5. logbook.html — Export EDI avec infos personnelles hardcodées
L'export EDI encode en dur :
```javascript
`PClub=F6KQJ`,
`RName=Olivier PARRIAUX`,
`RCall=F4GLD`,
`RAdr1=Chaspinhac`,
`RPoCo=43700`,
`RCity=Chaspinhac`,
`MOpe1=F4GLD`,
```
Ces valeurs ne viennent PAS de la configuration. Si une autre station utilise le logiciel (ou si F6KQJ change de QTH), le fichier EDI sera incorrect et rejeté par le bureau des contests.

**Correction :** lire ces champs depuis `localStorage('radiocontest_config')` et/ou le modal setup.

---

### 6. logbook.html — Synchronisation offline→online manquante
Quand le serveur est inaccessible, les QSO sont sauvegardés dans `qsoLog` (mémoire locale) mais jamais renvoyés au serveur quand la connexion revient. Un refresh de page perd tous les QSO hors-ligne.

**Correction :** stocker les QSO hors-ligne dans `localStorage` et synchroniser au prochain `fetchLog()` réussi.

---

## 🟠 BUGS MINEURS

### 7. configuration.html — saveConfig() n'inclut pas la clé API
Le bouton "💾 SAUVEGARDER CONFIG" appelle `saveConfig()` qui ne sauvegarde PAS `api_key`. La clé n'est sauvegardée que dans `launchApp()` → `localStorage.setItem('radiocontest_apikey', key)`. Un utilisateur qui sauvegarde sans lancer perd sa clé au reload.

### 8. configuration.html — Version affichée incorrecte
Le header affiche `v2.0.0` mais le serveur se nomme `RadioContest AI - Serveur principal v3.0`.

### 9. radiocontest.html — conversationHistory limité à 16 messages
```javascript
if(conversationHistory.length>16) conversationHistory=conversationHistory.slice(-16);
```
Pendant une session de 24h de concours, l'IA perd tout le contexte passé la 8e interaction. L'agent oublie les recommandations précédentes, les stations déjà contactées, etc.
**Recommandation :** 30-40 messages, ou résumé automatique périodique du contexte.

### 10. logbook.html — Export EDI : format de ligne QSO approximatif
La spec EDI REG1TEST attend :
`YYYYMMDD;HHMM;Indicatif;ModeCode;RSTenv;N°env;RSTrecu;N°recu;Echange;Locator;Points`

Le code envoie le mode en texte (`SSB`) dans un champ ultérieur comme commentaire. Le code mode numérique (1=SSB, 2=CW, 6=FM) est calculé mais placé au mauvais endroit dans certains cas. Vérifier avec un validateur EDI officiel avant soumission.

### 11. serveur.py — save_log_to_disk() sans verrou
```python
def save_log_to_disk():
    with open('shared_log.json', 'w', ...) as f:
        json.dump(shared_log, f, ...)
```
`shared_log` est partagé entre threads mais la sauvegarde ne prend pas `log_lock`. Race condition possible si deux opérateurs enregistrent simultanément.

**Correction :**
```python
def save_log_to_disk():
    with log_lock:
        data = list(shared_log)
    with open('shared_log.json', 'w', ...) as f:
        json.dump(data, f, ...)
```

---

## 🟡 PROBLÈMES DE LISIBILITÉ — JOUR / NUIT

### Problème central : thème 100% sombre, illisible en plein soleil
Le logiciel n'a qu'un seul thème (dark). Lors d'une activation terrain en journée (Rallye Points Hauts = juillet, en plein air), l'écran sombre sur fond noir est **illisible en plein soleil**.

### Solution recommandée : Toggle jour/nuit persistant

Ajouter un bouton ☀️/🌙 dans chaque header qui bascule les CSS variables :

```css
/* Mode JOUR */
body.day-mode {
  --bg: #F0F2F8;
  --bg2: #FFFFFF;
  --bg3: #E8EAFF;
  --border: #C0C8E8;
  --text: #0A0C20;
  --muted: #6070A0;
  --accent: #E05000;      /* orange plus sombre */
  --accent2: #0060B0;     /* bleu plus sombre */
  --green: #007840;
  --red: #CC0030;
  --yellow: #8C6A00;
}
```

**Éléments à adapter en mode jour :**
- Table du logbook : fond blanc, bordures gris clair
- Bulles de chat : fond blanc avec bordure bleue
- Carte SVG : fond `#E8EFF8` au lieu de `#07080F`, pays en `#D0D8E8`
- Formulaire de saisie : fond blanc, labels sombres
- Boutons : orange plein sur blanc

**Ajout du bouton dans chaque page :**
```html
<button id="themeToggle" onclick="toggleTheme()" 
  style="font-size:18px;background:none;border:none;cursor:pointer">☀️</button>
```
```javascript
function toggleTheme() {
  const day = document.body.classList.toggle('day-mode');
  localStorage.setItem('theme', day ? 'day' : 'night');
  document.getElementById('themeToggle').textContent = day ? '🌙' : '☀️';
}
// Au chargement :
if(localStorage.getItem('theme') === 'day') document.body.classList.add('day-mode');
```

---

## 🔵 AMÉLIORATIONS PERFORMANCE

### A. Raccourcis clavier dans le logbook (PRIORITÉ HAUTE pour terrain)
L'efficacité de saisie en concours dépend des raccourcis :

| Touche | Action |
|--------|--------|
| `Tab` | Indicatif → RST envoyé → N° envoyé → RST reçu → N° reçu → Locator → Enregistrer |
| `Enter` (sur locator) | Enregistrer le QSO ✅ |
| `F9` | Enregistrer le QSO (n'importe où dans le formulaire) |
| `Escape` | Fermer le modal d'édition |
| `Ctrl+Z` | Annuler le dernier QSO |
| `Ctrl+F` | Focus sur le champ de recherche |

**Implémentation :**
```javascript
document.addEventListener('keydown', e => {
  if(e.key === 'F9') { e.preventDefault(); submitQSO(); }
  if(e.ctrlKey && e.key === 'z') undoLastQSO();
});
```

### B. Augmenter la taille de police sur la page principale
Le tableau logbook utilise `font-size: 15px` pour les données principales, ce qui est bien. Mais les labels (`9px`) et les en-têtes de colonne (`11px`) sont illisibles à distance ou sous soleil.

**Recommandation :**
- Labels/en-têtes : minimum `11px` → `13px`
- Valeurs du tableau : `15px` → `17px` 
- Indicatifs : `18px` → `20px`

### C. Validation du locator en temps réel
Le champ locator accepte n'importe quelle saisie. Ajouter :
```javascript
function validateLocator(loc) {
  return /^[A-R]{2}\d{2}[A-X]{2}$/i.test(loc);
}
// Dans onLocatorInput() :
if(loc.length === 6 && !validateLocator(loc)) {
  document.getElementById('inputLocator').classList.add('error');
  return;
}
```

### D. Backup automatique du log
Ajouter une sauvegarde localStorage automatique toutes les 5 minutes :
```javascript
setInterval(() => {
  localStorage.setItem('logbook_backup', JSON.stringify(qsoLog));
  localStorage.setItem('logbook_backup_time', new Date().toISOString());
}, 5 * 60 * 1000);
```
Et afficher en pied de page : `Dernier backup : 14:32 UTC`

### E. Graphique QSO/heure
Ajouter un mini-graphique (canvas ou SVG) dans le score banner montrant la progression par heure. Critique pour gérer son rythme pendant 24h.

---

## 🟢 AMÉLIORATIONS FONCTIONNELLES

### F. Export Cabrillo pour CQ WW / ARRL DX
Actuellement seuls EDI, ADIF et CSV sont disponibles. Les concours HF (CQ WW, ARRL DX) exigent le format Cabrillo. Ajouter `exportCabrillo()`.

Exemple d'en-tête Cabrillo minimal :
```
START-OF-LOG: 3.0
CALLSIGN: F6KQJ
CONTEST: CQ-WW-SSB
CATEGORY-OPERATOR: SINGLE-OP
CATEGORY-POWER: LOW
CATEGORY-MODE: SSB
CLAIMED-SCORE: 12345
CLUB: GCEBP43
NAME: Olivier PARRIAUX
QSO: 14225 PH 2026-10-24 1432 F6KQJ 59 14 G3XYZ 59 14
END-OF-LOG:
```

### G. Indicateur de temps écoulé depuis le début du concours
Compléter le countdown avec un temps écoulé :
```
⏱ ÉCOULÉ: 06:45:22 | RESTANT: 17:14:38
```

### H. Bouton de refresh manuel des clusters
Sur le terrain, l'opérateur veut parfois forcer un refresh immédiat des spots sans attendre le timer automatique. Ajouter un bouton `🔄 REFRESH` dans le chat ou la carte.

### I. Affichage de l'opérateur dans le logbook : noms complets
Actuellement les boutons affichent `OP1`, `OP2`, etc. Les charger depuis `config.json` :
```
F4GLD (Olivier) | F1OMQ (Didier) | F1HAW (Jean) | ...
```

### J. Lier la configuration logbook à localStorage
Le modal setup du logbook demande l'indicatif et le locator à chaque ouverture, même si la config est déjà sauvegardée. Préremplir depuis `localStorage('radiocontest_config')`.

### K. Confirmation visuelle d'enregistrement QSO
Après `submitQSO()` réussi, afficher un flash vert sur la première ligne du tableau (c'est fait avec `new-entry`) mais aussi un son court (bip) optionnel configurable pour confirmer sans regarder l'écran :
```javascript
if(cfg.audio_confirm) {
  const ctx = new AudioContext();
  const osc = ctx.createOscillator();
  osc.frequency.value = 880;
  osc.connect(ctx.destination);
  osc.start(); osc.stop(ctx.currentTime + 0.08);
}
```

---

## 📋 RÉCAPITULATIF PRIORITÉS

| # | Problème | Impact | Effort | Priorité |
|---|----------|--------|--------|----------|
| 1 | logbook.html tronqué (fonctions manquantes) | 🔴 Critique | Faible (restaurer backup) | **P0** |
| 2 | Mode jour (lisibilité terrain) | 🔴 Critique | Moyen | **P1** |
| 3 | CONTEST_END_UTC hardcodé | 🟠 Moyen | Faible | **P2** |
| 4 | Export EDI champs personnels hardcodés | 🟠 Moyen | Faible | **P2** |
| 5 | Raccourcis clavier logbook | 🟡 Confort | Faible | **P2** |
| 6 | Grille carte non mise à jour au switch | 🟡 Confort | Faible | **P3** |
| 7 | Bouton mapModeBtn manquant | 🟡 Confort | Faible | **P3** |
| 8 | saveConfig sans api_key | 🟡 Confort | Très faible | **P3** |
| 9 | Race condition save_log_to_disk | 🟠 Moyen | Très faible | **P3** |
| 10 | Sync offline→online | 🟠 Moyen | Moyen | **P3** |
| 11 | Raccourcis clavier / F9 | 🟡 Confort | Faible | **P4** |
| 12 | Taille police labels | 🟡 Confort | Très faible | **P4** |
| 13 | Export Cabrillo | 🟡 Utile | Moyen | **P4** |
| 14 | Backup localStorage automatique | 🟡 Utile | Faible | **P4** |
| 15 | Graphique QSO/heure | 🟢 Nice | Moyen | **P5** |
| 16 | Bip de confirmation QSO | 🟢 Nice | Faible | **P5** |

---

## 🔧 ACTIONS IMMÉDIATES RECOMMANDÉES

1. **MAINTENANT** : Vérifier dans le ZIP `RadioContest_F6KQJ_2026_STABLE_v3.0.zip` si `logbook.html` est complet, et restaurer la version complète.

2. **AVANT LE RALLYE (5 juillet)** : Implémenter le toggle jour/nuit. Tester l'interface en plein soleil avec un écran de laptop réel.

3. **AVANT LE RALLYE** : Corriger l'export EDI pour lire les champs personnels depuis la config.

4. **AVANT LE RALLYE** : Ajouter F9 pour enregistrer un QSO (raccourci le plus critique en opération).

5. **AVANT LE RALLYE** : Corriger le CONTEST_END_UTC pour le lire depuis config.

---

*Rapport généré par analyse statique complète du code source — RadioContest AI v3.0 — F6KQJ Chaspinhac*
