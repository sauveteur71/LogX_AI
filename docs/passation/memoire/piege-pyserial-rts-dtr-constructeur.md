---
name: piege-pyserial-rts-dtr-constructeur
description: "pyserial 3.5 rejette rts=/dtr= comme kwargs du constructeur Serial() (ValueError) — seulement des propriétés d'instance à poser AVANT open()"
metadata:
  type: feedback
  originSessionId: af43e861-2413-455a-8762-2f1450c1c5cc
  modified: 2026-08-03T18:00:19.609Z
---

**Règle** : `serial.Serial(device, ..., rts=False, dtr=False)` lève
`ValueError: unexpected keyword arguments` avec pyserial 3.5 (celui utilisé
dans LogX AI, `requirements.txt: pyserial>=3.5,<4`). `SerialBase.__init__`
n'accepte que `port/baudrate/bytesize/parity/stopbits/timeout/xonxoff/
rtscts/write_timeout/dsrdtr/inter_byte_timeout/exclusive` + les alias de
compat `writeTimeout`/`interCharTimeout` — tout autre kwarg (dont `rts`/
`dtr`) est refusé sans exception, peu importe la version de Windows/Linux.

**Comment forcer RTS/DTR bas SANS créer de fenêtre où ils seraient hauts** :
construire fermé, poser les propriétés, PUIS ouvrir — `_reconfigure_port()`
(appelée depuis `open()`) lit `self._rts_state`/`self._dtr_state` pour
positionner `fRtsControl`/`fDtrControl` dès la configuration matérielle du
port, donc AUCUNE impulsion haute ne se produit si l'ordre est respecté :

```python
ser = serial.Serial()
ser.port = device
ser.baudrate = baudrate
# ... autres réglages ...
ser.rts = False
ser.dtr = False
ser.open()
```

Poser `rts=`/`dtr=` en kwargs du constructeur (au lieu de ce qui précède)
casse la fonctionnalité concernée à 100% dès qu'un vrai port est ouvert —
pas un risque théorique, une exception immédiate à chaque appel.

**Pourquoi ce piège a une saveur particulière** : trouvé lors d'une revue
adversariale (workflow) AVANT fusion sur le chantier
[[chantier-cat-plug-and-play-2026-08]] — le premier correctif (kwargs au
constructeur) avait un test pytest qui passait au VERT car son double
`_FakeUnderlyingSerial.__init__(self, device, **kwargs)` acceptait
n'importe quel kwarg sans validation, masquant exactement la contrainte
réelle de pyserial. Même famille de piège que
[[piege-faux-dom-stub-et-passes-paires]] (mock trop permissif qui ne
reproduit pas le comportement de rejet de la vraie bibliothèque) — mais ici
appliqué à une lib système, pas au DOM. Un double de test pour une fonction
qui OUVRE un port série doit reproduire fidèlement la signature RÉELLE du
constructeur (aucun argument positionnel/kwarg arbitraire accepté), sinon
il ne peut jamais attraper un appel invalide côté production.

**Comment appliquer** : pour TOUT futur module qui ouvre un port pyserial
dans ce dépôt (`logx_cat.py:SerialPort`, `logx_so2r.py:PortOtrsp`,
`logx_winkeyer.py:PortWinKeyer`, ou un futur module similaire), toujours
utiliser le patron construire-fermé/poser-propriétés/ouvrir ci-dessus si
RTS/DTR doivent être contrôlés à l'ouverture — jamais de kwargs `rts=`/
`dtr=` au constructeur.
