# IA-1 — Contrôle & validation du log — Plan d'implémentation

> **Pour agents exécutants :** SOUS-COMPÉTENCE REQUISE : superpowers:subagent-driven-development
> (recommandé) ou superpowers:executing-plans pour exécuter tâche par tâche.

**Goal :** ajouter au validateur déterministe existant des contrôles de
cohérence indépendants de l'activité (freq↔bande, date/heure, RST↔mode,
références d'activation) + un résumé pré-vol informatif avant export/LoTW.

**Architecture :** un module pur nouveau `concours/logx_controles.py`
(fonctions `(qso[, now]) -> (level, code, msg)|None` + agrégateur
`controles_coherence`), appelé dans la boucle existante de
`logx_validator.validate_log`. Aucune UI refondue : les findings sortent au
format déjà consommé par `logx_verif_panel.js`.

**Tech Stack :** Python 3 (stdlib) ; tables du dépôt `logx_scoring._band_from_freq`,
`logx_activation.validate_ref`/`PROGRAM_SPECS`, `logx_utils.utcnow` ; pytest + ruff.

**Spec :** `docs/superpowers/specs/2026-08-24-ia-controle-log-design.md`

## Global Constraints

- **Français** (messages de findings + UI), vocabulaire radioamateur.
- **Format de finding EXACT** de `validate_log` : les fonctions rendent
  `(level, code, msg)` ; c'est `_f(findings, level, code, msg, q, i)` qui bâtit
  `{level, code, msg, call, band, at, id}`. Ne jamais dupliquer ce montage.
- **Niveaux** : `erreur` | `attention` | `info` (mêmes chaînes qu'aujourd'hui).
- **Fonctions PURES** : `maintenant_utc`/dates injectés, jamais `datetime.now()`
  en dur (rejouabilité des tests).
- **Jamais bloquant** : aucun contrôle n'annule un export/upload (masquer ≠
  bloquer). Le pré-vol INFORME seulement.
- **Indépendant de l'activité** : les nouveaux contrôles s'exécutent pour CHAQUE
  QSO, sans garde `contest_id` ni `simple_mode`.
- **Valeurs de domaine sourcées**, jamais inventées : bandes via
  `logx_scoring._band_from_freq` ; formats de réf via `logx_activation` ; modes à
  rapport dB via la famille WSJT-X (SNR en dB — WSJT-X User Guide, § Reporting).
- **Contre-épreuve par mutation** après chaque tâche (témoin vert → remettre le
  défaut → le test rougit → restaurer → md5).
- **CRLF** : `logx_validator.py`/`logx_qsl.py` sont en CRLF (piège de mutation
  scriptée, cf. sous-chantier B). Fichiers de test en LF, `newline=''` à l'écriture.

---

### Task 1 : `logx_controles.py` — cohérence fréquence/bande et date/heure

**Files:**
- Create: `concours/logx_controles.py`
- Test: `concours/tests/test_controles_coherence.py`

**Interfaces:**
- Produces : `controle_freq_bande(q) -> (level, code, msg) | None`,
  `controle_date_future(q, maintenant_utc) -> ... | None`,
  `controle_heure_fin(q) -> ... | None`. `maintenant_utc` est un `str` `YYYYMMDD`.

- [ ] **Step 1 : test d'abord**

```python
# concours/tests/test_controles_coherence.py
import os, sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE); os.chdir(BASE)
import logx_controles as ctrl


def test_freq_bande_incoherente_signale():
    r = ctrl.controle_freq_bande({'freq': '7.150', 'band': '14'})
    assert r is not None and r[0] == 'attention' and r[1] == 'freq_bande_incoherente'


def test_freq_bande_coherente_ok():
    assert ctrl.controle_freq_bande({'freq': '14.075', 'band': '14'}) is None


def test_freq_absente_ou_inconnue_silencieux():
    assert ctrl.controle_freq_bande({'band': '14'}) is None
    assert ctrl.controle_freq_bande({'freq': 'zzz', 'band': '14'}) is None


def test_date_future_signale():
    r = ctrl.controle_date_future({'date': '20260825'}, '20260824')
    assert r is not None and r[1] == 'date_future'


def test_date_passee_ou_jour_ok():
    assert ctrl.controle_date_future({'date': '20260824'}, '20260824') is None
    assert ctrl.controle_date_future({'date': '20200101'}, '20260824') is None


def test_heure_fin_avant_debut_signale():
    r = ctrl.controle_heure_fin({'date': '20260824', 'time': '1215', 'time_off': '1200'})
    assert r is not None and r[0] == 'info' and r[1] == 'heure_fin_avant_debut'


def test_heure_fin_normale_ok():
    assert ctrl.controle_heure_fin({'date': '20260824', 'time': '1215', 'time_off': '1230'}) is None
    assert ctrl.controle_heure_fin({'date': '20260824', 'time': '1215'}) is None  # pas de time_off
```

- [ ] **Step 2 : lancer, vérifier l'échec** — `pytest tests/test_controles_coherence.py -q` → ImportError (module absent).

- [ ] **Step 3 : implémentation minimale**

```python
# concours/logx_controles.py
# -*- coding: utf-8 -*-
"""IA-1 — contrôles de cohérence DÉTERMINISTES, indépendants de l'activité.

Chaque fonction reçoit un QSO (dict interne du log) et rend soit
(level, code, msg) — un finding au format attendu par logx_validator._f — soit
None si tout va bien ou si le cas est trop ambigu pour trancher sans faux
positif. Fonctions PURES : aucune I/O, aucune horloge en dur (la date du jour
est injectée). Valeurs de domaine tirées des tables déjà sourcées du dépôt.
"""
import re

from logx_scoring import _band_from_freq   # '14.075'/'14075' -> bande interne '14'


def controle_freq_bande(q):
    """Fréquence loguée incohérente avec la bande loguée. Silencieux si freq
    absente ou hors de toute bande connue (on ne signale pas l'indécidable)."""
    freq = str(q.get('freq', '') or '').strip()
    if not freq:
        return None
    bande_calc = _band_from_freq(freq)
    bande_log = str(q.get('band', '') or '').strip()
    if bande_calc and bande_log and bande_calc != bande_log:
        return ('attention', 'freq_bande_incoherente',
                f"Fréquence {freq} MHz incohérente avec la bande {bande_log} "
                f"(attendu {bande_calc})")
    return None


def controle_date_future(q, maintenant_utc):
    """Date de QSO postérieure au jour UTC courant (`maintenant_utc` = 'YYYYMMDD')."""
    date = re.sub(r'\D', '', str(q.get('date', '') or ''))
    if len(date) == 8 and date > str(maintenant_utc):
        return ('attention', 'date_future',
                f"Date {date} postérieure à aujourd'hui ({maintenant_utc})")
    return None


def controle_heure_fin(q):
    """Heure de fin (time_off) antérieure à l'heure de début (time), même date.
    Niveau info : un QSO chevauchant minuit UTC produit légitimement ce cas —
    rare, faible enjeu, non alarmant. Compare HHMM numériquement."""
    t_on = re.sub(r'\D', '', str(q.get('time', '') or ''))[:4]
    t_off = re.sub(r'\D', '', str(q.get('time_off', '') or ''))[:4]
    if len(t_on) == 4 and len(t_off) == 4 and int(t_off) < int(t_on):
        return ('info', 'heure_fin_avant_debut',
                f"Heure de fin {t_off} avant l'heure de début {t_on}")
    return None
```

- [ ] **Step 4 : lancer, vérifier le succès** — `pytest tests/test_controles_coherence.py -q` → tous verts.

- [ ] **Step 5 : contre-épreuve mutation** — remplacer `bande_calc != bande_log`
  par `False` dans `controle_freq_bande` → `test_freq_bande_incoherente_signale`
  ROUGIT ; restaurer ; `md5sum` inchangé.

- [ ] **Step 6 : ruff + commit**

```bash
python -m ruff check --select E9,F concours/logx_controles.py concours/tests/test_controles_coherence.py
git add concours/logx_controles.py concours/tests/test_controles_coherence.py
git commit -m "IA-1 lot 1 : controles coherence freq/bande + date/heure (fonctions pures)"
```

---

### Task 2 : RST↔mode et références d'activation

**Files:**
- Modify: `concours/logx_controles.py`
- Test: `concours/tests/test_controles_coherence.py` (ajouts)

**Interfaces:**
- Produces : `controle_rst_mode(q) -> (level, code, msg) | None`,
  `controle_activation_ref(q) -> list[(level, code, msg)]` (0, 1 ou 2 findings),
  et l'agrégateur `controles_coherence(q, maintenant_utc) -> list[(level, code, msg)]`.

- [ ] **Step 1 : test d'abord**

```python
def test_rst_59_sur_ft8_signale():
    r = ctrl.controle_rst_mode({'mode': 'FT8', 'rst_sent': '599', 'rst_rcvd': '-12'})
    assert r is not None and r[1] == 'rst_incoherent_mode'


def test_rst_db_sur_ft8_ok():
    assert ctrl.controle_rst_mode({'mode': 'FT8', 'rst_sent': '-08', 'rst_rcvd': '-12'}) is None


def test_rst_599_sur_cw_ok():
    assert ctrl.controle_rst_mode({'mode': 'CW', 'rst_sent': '599', 'rst_rcvd': '599'}) is None


def test_activation_sans_ref_signale():
    rs = ctrl.controle_activation_ref({'my_sig': 'SOTA', 'my_sig_info': ''})
    assert any(c == 'activation_sans_ref' for _, c, _ in rs)


def test_activation_ref_mal_formee_signale():
    rs = ctrl.controle_activation_ref({'my_sig': 'SOTA', 'my_sig_info': 'PAS-BON'})
    assert any(c == 'ref_format_invalide' for _, c, _ in rs)


def test_activation_ref_valide_ok():
    rs = ctrl.controle_activation_ref({'my_sig': 'SOTA', 'my_sig_info': 'F/AB-123'})
    assert rs == []


def test_aggregateur_reunit_les_findings():
    q = {'freq': '7.0', 'band': '14', 'mode': 'FT8', 'rst_sent': '599',
         'rst_rcvd': '599', 'date': '20260824'}
    codes = {c for _, c, _ in ctrl.controles_coherence(q, '20260824')}
    assert 'freq_bande_incoherente' in codes and 'rst_incoherent_mode' in codes
```

- [ ] **Step 2 : lancer, vérifier l'échec** — les nouveaux tests échouent (fonctions absentes).

- [ ] **Step 3 : implémentation**

```python
from logx_activation import PROGRAM_SPECS, validate_ref

# Modes WSJT-X à rapport de signal en dB (SNR), PAS en RST : un « 59 »/« 599 »
# y trahit un RST par défaut oublié. Source : WSJT-X User Guide (§ Reporting,
# le rapport échangé est le S/N en dB). Liste volontairement restreinte aux
# modes que LogX manipule / qu'un import peut porter.
_MODES_RAPPORT_DB = {'FT8', 'FT4', 'FT2', 'JT65', 'JT9', 'JT4', 'FST4',
                     'FST4W', 'Q65', 'MSK144', 'JS8', 'WSPR'}
_RST_STYLE_RE = re.compile(r'^\d{2,3}$')   # 2-3 chiffres nus : allure RST (59/599)


def controle_rst_mode(q):
    """RST de style 59/599 sur un mode à rapport dB (FT8…) : probable défaut
    oublié. Conservateur : ne signale que ce cas net, jamais l'inverse."""
    mode = str(q.get('mode', '') or '').upper().strip()
    if mode not in _MODES_RAPPORT_DB:
        return None
    for champ in ('rst_sent', 'rst_rcvd'):
        val = str(q.get(champ, '') or '').strip()
        if val and _RST_STYLE_RE.match(val):
            return ('info', 'rst_incoherent_mode',
                    f"RST {val} en {mode} : ce mode se rapporte en dB (ex. -12), "
                    f"pas en 59/599")
    return None


def controle_activation_ref(q):
    """Références d'activation : programme déclaré sans référence, ou référence
    au mauvais format. Côté station (my_sig) = attention ; côté correspondant
    (sig) = info (on subit la réf de l'autre). Réutilise PROGRAM_SPECS."""
    out = []
    for prog_key, info_key, niveau, prefixe in (
            ('my_sig', 'my_sig_info', 'attention', 'Ma référence'),
            ('sig', 'sig_info', 'info', 'Référence correspondant')):
        prog = str(q.get(prog_key, '') or '').upper().strip()
        ref = str(q.get(info_key, '') or '').strip()
        if not prog or prog not in PROGRAM_SPECS:
            continue
        if not ref:
            out.append((niveau, 'activation_sans_ref',
                        f"{prefixe} : programme {prog} déclaré sans référence"))
        elif not validate_ref(prog, ref):
            out.append((niveau, 'ref_format_invalide',
                        f"{prefixe} {prog} « {ref} » : format invalide"))
    return out


def controles_coherence(q, maintenant_utc):
    """Tous les findings de cohérence pour un QSO (liste de (level, code, msg))."""
    res = []
    for f in (controle_freq_bande(q), controle_date_future(q, maintenant_utc),
              controle_heure_fin(q), controle_rst_mode(q)):
        if f:
            res.append(f)
    res.extend(controle_activation_ref(q))
    return res
```

- [ ] **Step 4 : lancer, vérifier le succès.**

- [ ] **Step 5 : contre-épreuve mutation** — dans `controle_rst_mode`, remplacer
  `if val and _RST_STYLE_RE.match(val)` par `if False` → `test_rst_59_sur_ft8_signale`
  ROUGIT ; restaurer ; md5. Idem : vider `_MODES_RAPPORT_DB` ne doit PAS être le
  seul filet (le test le prouve).

- [ ] **Step 6 : ruff + commit** (`IA-1 lot 2 : RST/mode + references d'activation`).

---

### Task 3 : brancher les contrôles dans `validate_log`

**Files:**
- Modify: `concours/logx_validator.py` (import + appel dans la boucle `for i, q`)
- Test: `concours/tests/test_validate_coherence_integration.py`

**Interfaces:**
- Consumes : `logx_controles.controles_coherence(q, maintenant_utc)`,
  `logx_utils.utcnow`. Chaque `(level, code, msg)` est passé à
  `_f(findings, level, code, msg, q, i)`.

- [ ] **Step 1 : test d'abord** — un carnet HORS concours (mode simple) reçoit
  les findings de cohérence ; un log REF garde ses findings concours.

```python
# concours/tests/test_validate_coherence_integration.py
import os, sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE); os.chdir(BASE)
import logx_validator as v


def test_coherence_active_meme_en_mode_simple():
    # mode simple, aucun concours : les contrôles concours sont muets, mais la
    # cohérence freq/bande doit sortir quand même.
    log = [{'call': 'F4ABC', 'band': '14', 'freq': '7.150', 'mode': 'SSB',
            'date': '20200101', 'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59'}]
    res = v.validate_log(log, contest_id='', cfg={'usage_mode': 'simple'})
    codes = {f['code'] for f in res['findings']}
    assert 'freq_bande_incoherente' in codes


def test_findings_concours_inchanges_sur_log_ref():
    # doublon REF (même call+band) toujours détecté : la greffe cohérence ne
    # casse pas l'existant.
    log = [{'call': 'F4ABC', 'band': '14', 'mode': 'SSB', 'date': '20260101',
            'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59'},
           {'call': 'F4ABC', 'band': '14', 'mode': 'SSB', 'date': '20260101',
            'time': '1205', 'rst_sent': '59', 'rst_rcvd': '59'}]
    res = v.validate_log(log, contest_id='REF_CDF_HF_SSB', cfg={})
    assert any(f['code'] == 'doublon' for f in res['findings'])
```

- [ ] **Step 2 : lancer, vérifier l'échec** — `freq_bande_incoherente` absent
  (contrôle pas encore branché) ; le 2e test passe déjà (garde-fou anti-régression).

- [ ] **Step 3 : implémentation** — dans `logx_validator.py`, au début de la
  boucle (après le `continue` du call vide), ajouter :

```python
        # IA-1 : contrôles de cohérence indépendants de l'activité (freq/bande,
        # date/heure, RST/mode, réf d'activation) — s'appliquent à TOUT QSO,
        # même hors concours et en mode simple.
        for level, code, msg in _controles_coherence(q, _AUJOURDHUI_UTC()):
            _f(findings, level, code, msg, q, i)
```

  avec en tête de fichier :

```python
from logx_controles import controles_coherence as _controles_coherence
from logx_utils import utcnow


def _AUJOURDHUI_UTC():
    """Jour UTC 'YYYYMMDD' pour controle_date_future (injecté, pas d'horloge en
    dur dans les fonctions pures)."""
    return utcnow().strftime('%Y%m%d')
```

  (`utcnow()` VÉRIFIÉ : rend un `datetime` NAÏF UTC — `.strftime('%Y%m%d')` OK.)

- [ ] **Step 4 : lancer, vérifier le succès** (les deux tests verts).

- [ ] **Step 5 : contre-épreuve mutation** — commenter l'appel
  `_f(findings, level, code, msg, q, i)` de la greffe → le 1er test ROUGIT, le 2e
  reste vert ; restaurer ; md5.

- [ ] **Step 6 : non-régression + ruff + commit** — `pytest tests/test_validator*.py
  tests/test_controles_coherence.py tests/test_validate_coherence_integration.py -q`
  puis la SUITE COMPLÈTE avant de clore. Commit `IA-1 lot 3 : brancher la
  coherence dans validate_log`.

---

### Task 4 : résumé pré-vol informatif avant export / LoTW

**Files:**
- Modify: `concours/logx_validator.py` (fonction `resume_controle`)
- Modify: `concours/logx_qsl.py` (`upload_lotw` joint le résumé à sa réponse)
- Test: `concours/tests/test_resume_controle.py`

**Interfaces:**
- Produces : `resume_controle(qsos, contest_id='', cfg=None) -> {erreurs, attentions, infos, ok}`.
- `upload_lotw` : sa valeur de retour gagne une clé `controle` = ce résumé ;
  son comportement d'upload est INCHANGÉ (jamais bloquant).

- [ ] **Step 1 : test d'abord**

```python
# concours/tests/test_resume_controle.py
import os, sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE); os.chdir(BASE)
import logx_validator as v


def test_resume_compte_par_niveau():
    log = [{'call': 'F4ABC', 'band': '14', 'freq': '7.0', 'mode': 'SSB',
            'date': '20260101', 'time': '1200', 'rst_sent': '59', 'rst_rcvd': '59'}]
    r = v.resume_controle(log, '', {})
    assert set(r) >= {'erreurs', 'attentions', 'infos', 'ok'}
    assert r['attentions'] >= 1        # freq/bande incohérente
    assert r['ok'] is (r['erreurs'] == 0)
```

- [ ] **Step 2 : lancer, vérifier l'échec** (fonction absente).

- [ ] **Step 3 : implémentation** — `resume_controle` réutilise `validate_log` :

```python
def resume_controle(qsos, contest_id='', cfg=None):
    """Résumé compact des contrôles pour le PRÉ-VOL avant export/LoTW.
    INFORMATIF — ne bloque rien (masquer != bloquer). S'appuie sur validate_log."""
    res = validate_log(qsos, contest_id, cfg)
    c = res['counts']
    return {'erreurs': c.get('erreur', 0), 'attentions': c.get('attention', 0),
            'infos': c.get('info', 0), 'ok': c.get('erreur', 0) == 0}
```

- [ ] **Step 4 : lancer, vérifier le succès.**

- [ ] **Step 5 : câblage upload_lotw (informatif)** — test d'abord : `upload_lotw`
  renvoie une clé `controle` ET tente toujours l'upload même sur log en erreur.

```python
# test : monkeypatch _run_tqsl/_find_tqsl_binary pour ne rien lancer, vérifier
# que le retour contient 'controle' et que l'upload n'est PAS annulé par un
# finding erreur. (AST-check possible en complément : upload_lotw n'a AUCUN
# return anticipé conditionné par resume_controle.)
```

  Implémentation : dans `upload_lotw`, après avoir constitué la liste `qsos` à
  uploader, calculer `controle = resume_controle(qsos, cfg.get('contest',''), cfg)`
  et l'AJOUTER au dict de retour, sans jamais l'utiliser comme condition d'arrêt.

- [ ] **Step 6 : contre-épreuve mutation** — transformer le câblage en garde
  bloquante (`if not controle['ok']: return {...}`) → le test « upload tenté même
  en erreur » ROUGIT (prouve la non-blocance) ; restaurer ; md5.

- [ ] **Step 7 : SUITE COMPLÈTE + ruff + commit** — `IA-1 lot 4 : resume pre-vol
  informatif (jamais bloquant) sur upload LoTW`.

---

## Auto-revue du plan

- **Couverture spec** : freq/bande (T1), date/heure (T1), RST/mode (T2),
  réf d'activation (T2), branchement activité-agnostique (T3), pré-vol
  export/LoTW (T4). Le contrôle « mode hors énum » est explicitement hors scope
  v1 (spec §3.1) ; la doublon-détection existe déjà (non re-couverte).
- **Cohérence de types** : `controle_*` rendent `(level, code, msg)|None` ;
  `controle_activation_ref` rend une LISTE ; `controles_coherence` aplatit tout
  en liste ; `validate_log` déballe via `_f`. `resume_controle` rend un dict de
  compteurs. Cohérent de bout en bout.
- **Points vérifiés** : `logx_utils.utcnow()` rend un `datetime` naïf UTC (OK
  pour `.strftime`). **À confirmer à l'exécution** : que `_band_from_freq`
  accepte la valeur de `q['freq']` telle qu'écrite par l'export (MHz).
