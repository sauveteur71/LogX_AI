---
name: reference-protocoles-cat-proprietaires
description: "Sources et détails techniques (ports, formats de trame) pour OmniRig, FlexRadio SmartSDR, PowerGenius XL, Icom CI-V/réseau, ACOM — recherche du 06/08/2026 en vue d'intégration dans LogX AI"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 96260619-9237-4cd4-9f10-a5311a0f4a94
  modified: 2026-08-06T15:48:24.835Z
---

Recherche approfondie faite le 06/08/2026 (demande explicite « maximum de doc, fouille pour ne rien louper ») avant tout début d'implémentation CAT/ampli propriétaire supplémentaire dans LogX AI. Contexte : [logx_amp.py](concours/logx_amp.py) a déjà `TcpAmpPort`/`UdpAmpPort` génériques + `KpaAmp`/`IcomAmp`/`SpeAmp` ; `logx_cat.py` existe pour le CAT radio.

## OmniRig (VE3NEA)
- Spec complète et texte du format `.ini` rig : http://www.dxatlas.com/omnirig/inistru.txt (3 sections INIT/STATUS/pmXxx, `Command=`, `ReplyLength=`/`ReplyEnd=`, `Validate=`, `Value=`/`ValueN=`/`FlagN=`, formats vfText/vfBinL/B/vfBcdLU/LS/BU/BS/vfYaesu).
- Dépôt : https://github.com/VE3NEA/OmniRig — interface COM `IOmniRigX` dans `OmniRig.ridl`.
- Binding Python (pywin32) communautaire : https://github.com/4Z1KD/omnipyrig

## FlexRadio SmartSDR — API réseau complète, bien documentée
Doc officielle exhaustive (79 pages) : https://github.com/flexradio/smartsdr-api-docs/wiki
- Commande : TCP port **4992**, trame `C[D]<seq>|<commande><term>` → `R<seq>|<code_hexa>|<message>`, async `S<handle>|<message>`.
- Streaming (FFT/S-mètre/IQ) : UDP port **4991**, encapsulation VITA-49.
- Discovery : paquet VITA-49 (Stream ID 0x800, Class ID 0x534CFFFF) sur port 4991, payload `model=%s serial=%s version=%s name=%s callsign=%s ip=%u.%u.%u.%u port=%u`.
- FlexLib (.NET) doc : https://www.flexradio.com/flexlib/annotated.html — exemples waveform : https://github.com/n5ac/smartsdr-dsp

## PowerGenius XL (4O3A) — protocole Ethernet complet, PIÈGE localisation
Le dépôt GitHub officiel référencé (`github.com/4o3a/genius-api-docs`) est quasi vide (juste un titre + logo) — **la vraie doc complète est ailleurs**, dans le MÊME wiki que SmartSDR : https://github.com/flexradio/smartsdr-api-docs/wiki/PowerGenius-Ethernet-API
- Commande : TCP port **9008**. Discovery : UDP port **9008**, broadcast sous-réseau local, regex `^(?<model>\S+)\s+ip=...\s+v=...\s+serial=...\s+nickname=...$`.
- Trame : `C<seq>|<commande>\r` (terminateur 0x0D) → `R<seq>|<code_hexa>|<message>` ; async `S<0>|<message>`.
- Prologue connexion : `V<a.b.c> [ AUTH]` (AUTH requis en WAN). Max 10 connexions TCP + 10 UDP.
- Commandes : `amplifier create`, `meter create` (FWD/RL/DRV/ID/TEMP), `interlock create/disable`, `catradio read/set`, `flexradio read/set`, `status`, `setup read`, `ifconf`, `ping`, `save`.
- Confirme les « 7 dialectes CAT » : band-data via TCP Flex appairé, CAT/CI-V série, BCD, ou Pin2Band.

## Icom — CI-V série documenté, réseau/RS-BA1 fermé
- CI-V série : trame `FE FE <dest> <ctrl> <cmd> [sous-cmd] [data BCD] FD`. Manuel générique historique 1993 (structure toujours valide) : https://www.cryptomuseum.com/ref/protocol/civ/files/CIV_manual_1993_v3.pdf — guides CAT par modèle chez icomamerica/icomeurope/icomfrance.
- **RS-BA1 / réseau (IC-705, IC-7610, IC-905...) : Icom ne publie AUCUNE spec réseau officielle.** Entièrement reverse-engineered par la communauté, confirmé par deux implémentations indépendantes convergentes :
  - Ports : UDP **50001** (contrôle), UDP **50002** (CI-V encapsulé), UDP **50003** (audio).
  - wfview (C++, GPLv3, la référence de facto) : https://github.com/wf-group/wfview
  - kappanhang (Go, HA2NON) : https://github.com/nonoo/kappanhang — voir `pkt7.go` pour la structure des paquets.
  - Kenwood réseau (TS-890S, comparaison) : TCP 60000 contrôle + UDP 60001 audio — protocole différent.
  - Pour intégrer le remote Icom sans repasser par RS-BA1 propriétaire : uniquement possible en s'appuyant sur le code source wfview/kappanhang, aucune doc texte n'existe.

## ACOM — confirmé : aucune source, ni officielle ni communautaire, ne documente le protocole octet par octet
Déjà noté dans [logx_amp.py:28](concours/logx_amp.py:28) comme « non documenté officiellement » — recherche du 06/08/2026 confirme et étend : les deux logiciels tiers existants (ACOM-Controller de SM7IUN, https://github.com/bjornekelund/ACOM-Controller ; ACOM Director Classic de M0YOM) ne publient pas non plus les octets de commande dans leur code/doc visible. Seul indice technique public : DTR/RTS ne sont pas de vraies lignes de handshake (réservées au power-on distant), le port RS-232 « n'est pas un vrai RS-232 » selon M0YOM. Pour intégrer ACOM il faudrait du reverse engineering matériel (sniffer le port série pendant qu'un de ces deux logiciels pilote l'ampli) ou contact direct ACOM.

## Tableau récap
| Protocole | Doc officielle | Ports connus | Prêt à coder |
|---|---|---|---|
| OmniRig | oui | — (COM local) | oui |
| FlexRadio SmartSDR | oui | TCP 4992 / UDP 4991 | oui |
| PowerGenius XL | oui (mal indexée) | TCP+UDP 9008 | oui |
| Icom CI-V série | oui | — (série) | oui |
| Icom réseau/RS-BA1 | non, reverse-engineered | UDP 50001/50002/50003 | via code wfview/kappanhang |
| ACOM | non, aucune source | inconnu | non sans reverse engineering |

**Recommandation d'ordre d'implémentation** : FlexRadio et PowerGenius XL en premier (doc complète, style proche de `TcpAmpPort`/`KpaAmp` existant), puis Icom réseau si besoin remote (via wfview), OmniRig si besoin de multiplexer un port CAT, ACOM en dernier / à part (nécessite reverse engineering).
