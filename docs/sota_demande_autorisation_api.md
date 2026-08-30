# Demande d'autorisation API SOTA — préparation

Préparé le 30/08/2026 pour F4GLD. But : débloquer les étapes 4-5 du chantier
SOTA (téléversement automatique vers sotadata + import du score officiel), qui
sont **bloquées par les CGU de l'API SOTA** tant qu'une autorisation explicite
n'est pas obtenue.

## Ce que disent les CGU officielles (sourcé)

Conditions de service de l'API SOTA — <https://api2.sota.org.uk/docs> :

- **Règle IA (celle qui nous bloque)** : *« No AI or 'Vibe-coding'… no
  AI-generated software may connect to the SOTA API without prior approval. »*
- **Groupe obligatoire** : *« Any application developer… must be a member of
  the SOTA Reflector and be a member of the 'API-consumers' group on that
  discussion board before using the API. »*
- Le développeur doit être **« a Designated Point of Contact to the SOTA
  Management Team »**.
- Usage raisonnable : blocage possible en cas de *« undue load »* / surcharge.
- Questions → formulaire de contact de la **SOTA Management Team**.

## La nuance qui nous sauve

L'interdiction vise l'IA **non relue** (« vibe-coding »), **pas** l'IA
**assistée et relue**. Précédent public sur le Reflector (fil API-consumers) :
**N4NAS** a été approuvé en déclarant *« AI-assisted development with personal
review before commit »*. LogX AI est exactement dans ce cas :

- tout le code est **relu et compris** par l'auteur (F4GLD) avant intégration ;
- développement en **TDD** avec **contre-épreuve par mutation** (chaque test
  prouvé non vacant) ;
- l'auteur est **radioamateur licencié** et **point de contact unique**.

C'est l'argument central de la demande : montrer qu'on n'est pas du
« vibe-coding », mais un développement assisté, relu et testé.

## Qui contacter / comment

- Poster dans le groupe **« API Consumers »** du Reflector :
  <https://reflector.sota.org.uk/t/api-consumers/41566>.
- Contact identifié pour les demandes d'ajout au groupe : **VK3ARR (Andrew)**.
- Alternative officielle : **formulaire de contact de la SOTA Management Team**.
- ⚠️ Organisation **bénévole, aucun délai garanti (no SLA)** — rester patient
  et courtois, ne pas relancer agressivement.

## Bonnes pratiques à afficher (prouve qu'on respecte l'infra)

- **User-Agent descriptif avec indicatif** : `LogX-AI/1.1 (F4GLD)`.
- **Spots** : privilégier le **cluster push** (`cluster.sota.org.uk:7300`)
  plutôt que le polling ; si polling nécessaire, **ETag / If-Modified-Since +
  backoff exponentiel** (jamais de martèlement).
- Demander **précisément** les accès voulus (self-spot d'expédition, lecture du
  chaser-log), pas un accès large.

---

## Message prêt à envoyer (EN — à poster sur le Reflector / envoyer à la MT)

> **Subject: API-consumers request — LogX AI logging software (F4GLD)**
>
> Hello,
>
> I would like to request membership of the API-consumers group and approval
> to use the SOTA API for my amateur-radio logging software, **LogX AI**.
>
> **About me / point of contact.** I am F4GLD, a licensed amateur radio
> operator. I will be the single Designated Point of Contact for this software
> and its API usage.
>
> **About the software.** LogX AI is a desktop logging program for radio
> amateurs (activators and chasers). SOTA support today is fully **offline**:
> it uses the public summit-list CSV for reference lookup, so it currently
> makes **no live API calls**. It already exports standard ADIF
> (MY_SIG / SIG etc.), so manual upload to sotadata is possible without the API.
>
> **On the AI policy.** I have read the Terms of Service, including the rule on
> AI-generated software. My development is **AI-assisted but fully
> human-reviewed**: I read, understand and test every change before it is
> committed (test-driven development with mutation testing to guarantee the
> tests are meaningful). This is not "vibe-coding" — I am able to understand
> and support the code, and I take responsibility for its behaviour as the
> point of contact.
>
> **What I would like to use, and how responsibly.** To reduce the manual
> workload for activators and chasers, I would like approval to:
> 1. self-spot my own SOTA expeditions, and
> 2. read my own chaser log for indicative statistics.
>
> I will identify with a descriptive User-Agent including my callsign
> (`LogX-AI/1.x (F4GLD)`), respect reasonable usage limits, use conditional
> requests (ETag / If-Modified-Since) with exponential backoff, and prefer the
> SOTA cluster for spot feeds rather than polling.
>
> I understand SOTA is volunteer-run with no SLAs, and I am in no hurry. Please
> let me know if you need any further information, or any changes to the above
> before approval.
>
> Thank you very much for the work you put into SOTA and its infrastructure.
>
> 73,
> F4GLD

---

## Checklist concrète (F4GLD)

1. [ ] Compte actif sur `reflector.sota.org.uk` (indicatif F4GLD).
2. [ ] Poster le message ci-dessus dans **« API Consumers »** (ou contacter
       **VK3ARR**, ou le formulaire de la Management Team).
3. [ ] Attendre l'ajout au groupe **API-consumers** (délai variable, bénévole).
4. [ ] Une fois approuvé : récupérer la **doc réservée au groupe** + l'éventuel
       **`client_id` OAuth**, et **me les transmettre** — c'est ce qui manque
       pour coder les étapes 4-5 (upload auto sotadata + import du score
       officiel) contre une API alors **documentée et autorisée**, au lieu de
       coder à l'aveugle contre un endpoint fermé (l'actuel `422` sur
       `api-db2.sota.org.uk` vient précisément de l'absence de doc).

## Rappel — ce qui reste faisable SANS l'API en attendant

- Info référence sommet (déjà fait, hors-ligne, 181 658 sommets).
- Mode chasseur + réf. correspondant sur le QSO (déjà fait).
- **Points de chasse « indicatifs »** locaux (en cours) — explicitement **non
  officiels**, jamais envoyés à SOTA.
- Export ADIF filtré pour **téléversement manuel** sur sotadata.org.uk (conforme
  aux CGU, aucun code API requis).
