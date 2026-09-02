# Audit CAT + FT8 approfondi — LogX AI

Campagne dediee (checklist WSJT-X/Hamlib 4.7.2), 23/08/2026. Lecture seule, chaque constat verifie adversarialement. 48 constats. Detail brut : tasks/ws5s9gnev.output.

> [RADIO] = touche l emission : corrige+teste OK, essai sur l air = manip supervisee F4GLD. Aucune adresse CI-V / code mode / seuil ecrit de memoire : sourcer le manuel officiel.

## [HAUTE/bug [RADIO]] logx_cat.py:685 — _civ_set_frame accepte toute trame radio->E0 comme accusé : faux 'echec' sur bus CI-V partagé (WSJT-X + LogX = cas FT8 standard)
- **Defaut** : Le predicat accept= de _civ_set_frame (_matches) ne vérifie QUE les adresses (TO=E0, FROM=self.addr). Il n'exige PAS que la trame soit un accusé FB/FA. La boucle relit de _transceive ne saute donc que les trames MAL adressées, pas les trames BIEN adressées d'un AUTRE échange. Sur un bus CI-V partagé (splitter CI-V ou USB CI-V partagé WSJT-X+LogX, montage FT8 courant), tous les contrôleurs utilisent E0 (le code l'affirme lui-même, lignes 540-548). La réponse de WSJT-X à SON get_freq (FE FE E0 <ad
- **Effort** : 30 min

## [HAUTE/backlog [RADIO]] logx_cat.py:1077 — Split FT8 non implémenté : ni Rig split, ni Fake It, ni séparation cadran/audio (RF = freq_cadran + freq_audio)
- **Defaut** : Aucune méthode d'émission de split n'existe dans CivRadio ni AsciiRadio (grep : aucun set_split, aucun envoi 0x0F Icom, aucun FT0/FT1/FT2/FT3 Yaesu). Or c'est un pré-requis FT8 de la checklist : décaler le VFO d'émission pour garder l'audio dans la zone propre du filtre SSB (Fake It), et gérer le split Rig. La donnée est préparée (self.split_style calculé L.1077, table SPLIT_STYLE L.833-838, styles ft01/ft23/fr_ft documentés L.821-823) mais AUCUN code ne l'utilise pour émettre — le commentaire L
- **Effort** : 1 jour

## [HAUTE/bug [RADIO]] logx_rig.py:180 — set_freq() ignore le RPRT de la commande de mode : un mode refuse par la radio est rapporte comme succes
- **Defaut** : Quand un mode est fourni, set_freq() envoie 'M {mode} 0' mais NE verifie PAS la reponse RPRT (contrairement a la commande 'F' juste au-dessus, qui passe par _rprt_ok). La fonction retourne {'ok': True} des que le QSY a reussi, meme si le changement de mode a echoue (mode inconnu de la radio, capacite absente, ex. PKTUSB/USB-DATA non supporte sous ce nom, RPRT != 0). L'appelant (logx_http.py:6101, chemin QSY/FT8 via payload 'mode') croit alors la radio en USB-DATA alors qu'elle est restee dans l'
- **Effort** : 15 min

## [HAUTE/bug [RADIO]] logx_omnirig.py:294 — Aucune normalisation de mode : les modes du carnet (FT8/FT4/PSK/SSB/RTTY) ne sont jamais mappes
- **Defaut** : set_freq (l.294) et set_mode (l.309) mappent le mode directement via MODE_TO_PARAM.get(str(mode).strip().upper()) dont les seules cles sont 8 tokens NIVEAU RADIO ('CW','CW-R','USB','LSB','DATA','DATA-R','AM','FM'). Le module n'importe/n'appelle jamais normaliser_mode() (logx_cat.py:1027), la fonction que TOUS les autres chemins de mode utilisent pour traduire le vocabulaire du carnet. Or le vocabulaire reel du carnet est defini en logx_cat.py:1006-1010 : MODES_NUMERIQUES={'FT8','FT4','PSK',...},
- **Effort** : 1h

## [HAUTE/bug [RADIO]] logx_omnirig.py:295 — set_freq avale silencieusement un mode non reconnu et retourne ok:True (incoherent avec set_mode)
- **Defaut** : Dans set_freq, l.293-297 : if mode: param = MODE_TO_PARAM.get(...); if param is not None: rig.Mode = param ; puis return {'ok': True}. Si un mode est fourni mais non mappe (param None), le mode est saute EN SILENCE et la fonction retourne quand meme {'ok': True}. L'appelant croit le mode applique. C'est incoherent avec set_mode (l.309-312) qui, pour EXACTEMENT le meme token non mappe, retourne une erreur explicite. Combine au finding precedent : un QSY vers FT8/SSB/RTTY laisse la radio dans son 
- **Effort** : 20 min

## [MOYENNE/backlog [RADIO]] logx_cat.py:1018 — HYPOTHESE A VERIFIER : Kenwood/Elecraft en FT8 restent en USB simple, pas de sous-mode DATA -> routage audio arrière peut-etre inactif
- **Defaut** : MODE_NUMERIQUE_PAR_MARQUE = {'yaesu': 'DATA-USB'} (L.1018) ne couvre QUE Yaesu. Pour kenwood/elecraft, normaliser_mode (L.1044-1045) renvoie 'USB' pour tout mode numérique (FT8/FT4/PSK), donc AsciiRadio.set_mode envoie MD<code USB> — la radio est mise en USB phonie, jamais dans son sous-mode DATA/PKT. Checklist item 2 : le mode DATA route l'audio par l'entrée arrière (USB/DATA) et coupe compresseur/EQ micro ; en USB simple, sur les postes où le chemin audio arrière est lié au mode DATA, l'audio 
- **Effort** : 2h

## [MOYENNE/backlog [RADIO]] logx_cat.py:1308 — Aucun handshake matériel (RTS/CTS, DTR/RTS) configurable : SerialPort force rts=dtr=False et laisse rtscts/dsrdtr/xonxoff aux valeurs par défaut de pyserial
- **Defaut** : Le constructeur SerialPort n'accepte que device/baudrate/timeout (ligne 1280) et pose explicitement bytesize/parity/stopbits/rts/dtr (1305-1309) mais JAMAIS rtscts, dsrdtr ni xonxoff. pyserial les laisse donc à False. Un poste dont le CAT exige un handshake matériel restera muet, et l'opérateur ne dispose d'aucun champ CONFIG pour l'activer. C'est exactement le point 4 de la checklist WSJT-X/Hamlib. De plus rts=False est posé en dur : sur un port où RTS sert au handshake CAT (et non au PTT), mai
- **Effort** : 2-3h

## [MOYENNE/bug [RADIO]] logx_flrig.py:96 — set_freq masque un succes partiel : la frequence est reglee mais si set_mode echoue, l'appelant recoit ok:False
- **Defaut** : Dans set_freq, set_frequency() puis set_mode() sont executes sequentiellement dans le meme try. Si set_frequency reussit (radio deja QSY) mais que set_mode leve (mode invalide, fault XML-RPC, capacite absente), l'exception est capturee et la fonction retourne {'ok': False}. L'appelant croit que rien n'a eu lieu alors que le VFO a bougé — etat radio et etat rapporte divergent.
- **Effort** : 20 min

## [MOYENNE/amelioration] logx_flrig.py:88 — Toutes les exceptions sont etiquetees 'flrig injoignable', y compris les Fault XML-RPC qui ne sont pas des problemes de connectivite
- **Defaut** : Les trois handlers (get_state, set_freq, set_ptt) formattent n'importe quelle Exception en 'flrig injoignable ({e})'. Un Fault XML-RPC (mode refuse, commande non supportee par la radio, valeur hors plage) ou un ValueError de parsing seront presentes a l'utilisateur comme une panne reseau, masquant le vrai probleme (capacite absente / mode inexistant). Recoupe le point 8 de la checklist : l'absence de capacite n'est pas distinguee d'une injoignabilite.
- **Effort** : 30 min

## [MOYENNE/bug [RADIO]] logx_flexradio.py:330 — set_ptt renvoie ok=True sans confirmer que la radio a reellement engage l'emission (code d'erreur R avale)
- **Defaut** : FlexClient.set_ptt() envoie 'xmit 1' en fire-and-forget et le module set_ptt() renvoie {'ok': True} des que send_line() a reussi. Or le protocole SmartSDR repond 'R<seq>|<code_hexa>|<message>' a chaque commande (code != 0 = echec : TX inhibe, interlock, pas de slice TX, PTT deny). _handle_line() ignore explicitement les lignes 'R'. Consequence : si la radio REFUSE le xmit, l'echec est invisible cote appelant — le voice keyer / la sequence FT8 croit emettre alors que la radio est restee en recept
- **Effort** : 1h (lire la reponse R correlee au seq de xmit avec un petit timeout, ou a defaut confirmer via l'etat interlock pousse dans get_state()['ptt'])

## [MOYENNE/bug] logx_flexradio.py:305 — Les slices retires ne sont jamais purges du cache — get_state peut servir une frequence perimee
- **Defaut** : _handle_slice_status() n'ajoute/met a jour que des cles dans state['freq_hz'] et state['mode'] ; aucune entree n'est jamais supprimee ni invalidee. Quand un slice est ferme cote SmartSDR (l'API pousse une notification de retrait / in_use=0), le module continue de detenir sa derniere frequence. get_state() a un repli qui prend 'le premier slice connu' quand le slice '0' est absent : ce repli peut donc retourner la frequence d'un slice qui n'existe plus, avec ok=True cote module.
- **Effort** : 2h (parser le champ d'etat in_use/retrait et supprimer l'entree correspondante)

## [MOYENNE/bug] logx_tci.py:681 — La reconnexion transparente ne ré-arme jamais le flux IQ : le panadapter TCI meurt silencieusement après toute coupure
- **Defaut** : Quand le fil de lecture meurt (ExpertSDR3 relancé, réseau tombé, idle timeout), _ensure_connected() détecte reader.is_alive()==False, ferme l'ancien client et recrée un TciClient NEUF. Ce nouveau client n'a jamais reçu IQ_SAMPLERATE/DDS/IQ_START : son _iq_buffer reste vide. Les fréquences/mode se ré-alimentent seuls (protocole push), mais le flux IQ est un état CLIENT-initié qui n'est ré-émis nulle part après reconnexion.
- **Effort** : 1-2 h

## [MOYENNE/amelioration] logx_ft8.html:1042 — Le mode CAT (rigMode) est interrogé mais jamais exploité : aucune détection/alerte si la radio n'est pas en mode données (checklist USB-DATA)
- **Defaut** : Variable morte doublée d'un manquement de la checklist : le mode remonté par le CAT est disponible mais aucun contrôle ne prévient l'opérateur que sa radio est en USB au lieu d'USB-DATA/PKTUSB. C'est précisément le cas où « tout semble normal côté logiciel » mais où le signal part dégradé. L'information nécessaire est déjà en main (rigMode), il ne manque que la comparaison + l'avis.
- **Effort** : 1-2 h

## [MOYENNE/bug [RADIO]] logx_ft8.html:3199 — Le decalage VFO (Fake It) est commande APRES le PTT et valide sur r.ok HTTP, pas sur un mouvement reel du poste
- **Defaut** : Dans envoyerMessage(), pttOn(true) engage l'emission (ligne 3098) PUIS le QSY de decalage est envoye (3196-3199). La radio est donc deja en emission (keyed) au moment du changement de VFO. Le succes est juge sur `if(r.ok){ decalage = d; }` — r.ok est le statut HTTP de /rig/qsy (commande acceptee par le serveur/hamlib), PAS une confirmation que le VFO a physiquement bouge. Beaucoup de postes ignorent un changement de frequence tant qu'ils sont keyes ; dans ce cas decalage est quand meme pose, et 
- **Effort** : 1 jour

## [MOYENNE/bug [RADIO]] logx_ft8.html:3067 — La garde 'creneau manque' apres l'attente ne protege que le chemin sequenceur, jamais le chemin manuel
- **Defaut** : Apres l'await du creneau (3052), la revalidation du timing (`Math.abs(Date.now()-prochain)>500` -> emission abandonnee) est gatee sur `creneauImpose > 0`, donc ne s'execute QUE pour le sequenceur. Idem pour le pre-controle `prochain <= now` (3037). Le chemin MANUEL (envoyerMessage() sans creneauImpose, appele par le bouton Envoyer et le double-clic) ne verifie jamais qu'il s'est reveille a l'heure : apres l'attente il ne teste que generationTx/txArmed (3084). Si le timer se reveille tard (thread
- **Effort** : 30 min

## [MOYENNE/backlog [RADIO]] logx_ft8.html:3084 — Aucune garde de synchro UTC avant d'autoriser l'emission FT8, alors que l'infra de mesure d'horloge existe
- **Defaut** : Checklist point 6 : FT8 ne doit pas emettre si l'horloge derive de plus de ~1 s. Le code DISPOSE de tout le necessaire cote reception (mesurerHorloge(), medianeDt(), majAlerteHorloge, seuils HORLOGE_SAINE_S/DT_ALERTE_S) mais envoyerMessage() ne consulte AUCUN de ces elements avant d'emettre. Les seules gardes avant modulation sont generationTx et txArmed (3084 et 3172). Une horloge PC fausse fait donc partir des trames hors du creneau des correspondants sans le moindre avertissement au moment de
- **Effort** : 1 jour

## [MOYENNE/backlog [RADIO]] logx_ft8.html:2433 — Le mode CAT (rigMode) est lu mais jamais verifie : rien ne garantit USB-DATA/PKTUSB avant d'emettre en FT8
- **Defaut** : Checklist point 2 : le logiciel devrait s'assurer d'un mode data (USB-D/DATA-U/PKTUSB) qui route l'audio USB arriere, pas d'un simple USB. La page LIT le mode courant du poste (rigMode, affecte ligne 1042 depuis /rig) mais ne l'utilise nulle part — rigMode n'est reference qu'en 1012/1042/1047, l'affichage 1044 se sert de la bande, jamais du mode. appliquerProtectionPuissance() pousse bien la PUISSANCE vers le poste (2444) mais ni ne regle ni ne verifie le mode. Un operateur reste en USB phonie (
- **Effort** : 1h

## [MOYENNE/bug] logx_hardware_cat.js:399 — La cle anti-repetition des alertes 'besoin LoTW' ignore la bande/mode, contredisant sa propre semantique documentee
- **Defaut** : Le commentaire l.396-397 decrit l'alerte comme 'entite deja travaillee mais pas confirmee LoTW sur cette bande/mode' — donc pertinente par bande/mode. Mais la cle de deduplication est `m.call + '|lotw'`, sans bande ni mode. Le Set _wsjtxAlerted persiste toute la session : une station signalee 'besoin LoTW' sur une bande ne re-declenchera jamais l'alerte quand on la recroise sur une AUTRE bande ou l'on en a aussi besoin. La branche 'missing' (l.382-383) assume ce comportement par indicatif volont
- **Effort** : 10 min

## [MOYENNE/backlog [RADIO]] logx_hardware_cat.js:508 — Aucune garde de derive d'horloge UTC cote client avant d'armer une emission FT8 automatique (Wait-and-Pounce niveau 3/4)
- **Defaut** : Le fichier CALCULE/AFFICHE la derive d'horloge (horlogeHtml, l.309-323) et avertit qu'au-dela du seuil les appels FT8 ne sont plus decodes, mais armerPounce() n'utilise jamais cette information : le niveau 4 (station qui emet seule, l.469-470) ne demande qu'une confirmation de duree (l.508) et le niveau 3 aucune, sans jamais consulter d.horloge/l'etat de synchro avant d'autoriser une emission automatique. Un poste hors NTP avec horloge derivee emettrait donc en FT8 sans etre decode. La garde peu
- **Effort** : 1 jour

## [MOYENNE/bug] logx_reglages_poste.js:277 — TS-590SG « Niveau d'entrée audio » : valeur Menu No. 71 non soutenue par sa citation (qui est la ligne TS-590S / Menu 64)
- **Defaut** : La ligne affirme « Menu No. 71 » pour le TS-590SG, mais la citation attachée parle du TS-590S et de « Menu No.64 ». La citation ne contient ni « 71 » ni « 590SG » : elle est identique mot pour mot à celle de l'entrée TS-590S (lignes 316/319-320). Le fichier viole ici sa propre RÈGLE DE CONSTITUTION (« chaque ligne porte sa SOURCE et une CITATION vérifiable ») et l'audit ne peut pas confirmer que « Menu No. 71 » soit le bon numéro de menu. Comme le préambule le dit lui-même, un chemin de menu fau
- **Effort** : 15 min

## [BASSE/amelioration [RADIO]] logx_cat.py:347 — civ_is_ok() confond le refus explicite (FA/NG) et l'absence de reponse
- **Defaut** : civ_is_ok() ne renvoie True que pour FB FD (ack positif). FA FD (NG = commande recue mais refusee / parametre non supporte) et une trame absente/malformee tombent tous dans le meme False. Le seul appelant SET (_civ_set_frame -> _civ_set) traduit ce False par le message unique 'Radio CI-V : pas d'accuse de reception (FB)'. C'est exactement le point 8 de la checklist (gerer l'absence de capacite) : le code ne plante pas et ne suppose pas le succes, mais il ne sait pas distinguer 'la radio a refuse
- **Effort** : 1h

## [BASSE/amelioration [RADIO]] logx_cat.py:296 — civ_encode_freq() tronque/desaligne silencieusement si la frequence depasse la capacite de nb_octets
- **Defaut** : civ_encode_freq construit le BCD via rjust(digits,'0') puis decoupe sur range(0, digits, 2). rjust ne tronque jamais : si str(int(freq_hz)) est PLUS LONG que `digits`, la boucle ne lit que les `digits` PREMIERS caracteres (chiffres de poids fort) et jette les chiffres de poids faible en queue, sans erreur. Le resultat est une trame de frequence fausse envoyee au poste sans aucun signal. Aucun garde-fou ne verifie que la valeur tient dans nb_octets.
- **Effort** : 15 min

## [BASSE/amelioration [RADIO]] logx_cat.py:278 — Justification incoherente du seuil 6 octets IC-905 (5,85 GHz ne depasse PAS 9 999 999 999)
- **Defaut** : Le commentaire du seuil affirme qu'au-dela de 5,85 GHz la frequence 'depasse ce qu'un BCD 5 octets peut representer (9 999 999 999 Hz)'. C'est arithmetiquement faux : 5 850 000 000 < 9 999 999 999. Un BCD 5 octets (10 chiffres) represente jusqu'a ~10 GHz, donc la bascule a 5,85 GHz n'est PAS justifiee par une limite de representation. La vraie raison (comportement firmware IC-905 sur les modules SHF, cf. Hamlib RIG_IS_IC905) n'est pas sourcable depuis le depot. Risque concret : un mainteneur cro
- **Effort** : 30 min

## [BASSE/backlog [RADIO]] logx_cat.py:250 — Adresse controleur CI-V (0xE0) codee en dur, non configurable par instance
- **Defaut** : CIV_CTRL_ADDR est fige a 0xE0 et injecte dans toutes les trames emises (civ_build_frame) et exige a la reception (_matches, _on_frame). L'adresse RADIO est bien configurable (dict CIV_ADDRESSES + champ modele editable, checklist 3 OK), mais l'adresse CONTROLEUR ne l'est pas. Or les propres commentaires du module (lignes 540-548) reconnaissent que sur un bus CI-V partage (LogX + WSJT-X + N1MM via separateur) tous utilisent 0xE0, ce qui rend TO/FROM indistinguables. Rendre l'adresse controleur con
- **Effort** : 2-3h

## [BASSE/amelioration] logx_cat.py:833 — SPLIT_STYLE / self.split_style : donnée morte (calculée, jamais lue)
- **Defaut** : La table SPLIT_STYLE (L.833-838) et l'attribut self.split_style (L.1077) constituent du code mort : calculés à chaque instanciation d'AsciiRadio mais jamais consommés (aucune commande split émise, cf. constat backlog). Dette technique : une table de correspondance modèle->style maintenue et corrigée (le commentaire L.824-832 documente un 'DÉFAUT DE DONNÉE CORRIGÉ' sur le FT-991) alors que rien ne l'exerce — donc jamais testable de bout en bout et susceptible de re-diverger silencieusement d'ici 
- **Effort** : 10 min

## [BASSE/bug [RADIO]] logx_cat.py:641 — HYPOTHESE A VERIFIER : CI-V 1A 06 (flag DATA) envoyé avec un seul octet de donnée, sans octet de filtre
- **Defaut** : set_mode Icom envoie la sous-commande 1A 06 avec UN SEUL octet de donnée (data mode 00/01). Le format Icom de réglage du data mode inclut généralement un second octet (largeur de filtre, ex. 1A 06 01 01), et Hamlib (icom.c, cité en commentaire L.629) envoie data mode + filtre ensemble. Certains postes peuvent rejeter ou mal interpréter un 1A 06 tronqué à un octet en SET. Comme c'est du fire-and-forget (read_reply=False, L.641-642), un rejet serait totalement silencieux — le flag DATA ne s'armera
- **Effort** : 1h

## [BASSE/backlog [RADIO]] logx_cat.py:2160 — Aucun split (Rig split ni Fake It) émis par le CAT natif : point 1 de la checklist FT8 non traité
- **Defaut** : L'unique opération de fréquence exposée est set_freq(cfg, freq_hz, mode=None) (2160), qui appelle driver.set_freq(freq_hz) sur un seul VFO (2169). Il n'existe aucune fonction set_split au niveau module ni aucune méthode driver émettant une commande split : SPLIT_STYLE (défini en 833-838) est calculé dans self.split_style (1077) mais n'est utilisé par AUCUN chemin d'émission. Le mode « Rig split » du FT8 (VFO TX distinct pour garder l'audio en 1500-2000 Hz) est donc impossible en natif. Le décala
- **Effort** : 1-2 jours

## [BASSE/amelioration] logx_cat.py:1673 — Repli d'adresse CI-V 0x94 codé en dur et dupliqué : un modèle Icom absent de CIV_ADDRESSES (ou vide) prend silencieusement l'adresse de l'IC-7300
- **Defaut** : civ_addr = _parse_civ_addr(...) or CIV_ADDRESSES.get(model, 0x94) (1673), répliqué à l'identique dans test_connection (2377). Deux problèmes : (a) le défaut 0x94 (adresse usine IC-7300 d'après CIV_ADDRESSES ligne 262) est renvoyé pour tout modèle Icom/Xiegu non listé ou champ model vide — la radio répond alors « muette » sans indice que la cause est une adresse par défaut inadaptée ; (b) l'opérateur GET « or » traite une adresse manuelle valide 0x00 (saisie « 00 ») comme absente et bascule sur l
- **Effort** : 30 min

## [BASSE/bug [RADIO]] logx_rig.py:128 — Course sur le cache _sockets : le thread worker orphelin (timeout DNS) mute _sockets sans detenir _lock
- **Defaut** : _do() (execute dans l'executor) appelle _get_socket()/_drop_socket() qui mutent le dict partage _sockets, mais _do() ne detient JAMAIS _lock lui-meme : la serialisation repose uniquement sur le fait que le thread APPELANT tient _lock pendant fut.result(). Sur le chemin _cf.TimeoutError (resolution DNS bloquee, cas explicitement documente lignes 129-135), l'appelant fait 'raise' et libere _lock alors que le thread _do() orphelin continue de tourner. Un _command() suivant acquiert _lock et soumet 
- **Effort** : 1h

## [BASSE/amelioration] logx_rig.py:107 — Garde de completude fragile : 'cmd[0] in "Ff mM"' contient une espace parasite et duplique la logique de _complete
- **Defaut** : La condition 'cmd[0] in 'Ff mM'' teste l'appartenance a une chaine qui contient une ESPACE : une commande commencant par ' ' matcherait aussi. Inoffensif aujourd'hui (aucune commande ne commence par espace) mais c'est un ensemble de lettres exprime par accident comme une sous-chaine, fragile a toute evolution. De plus la meme boucle decode buf en ASCII dans la condition while ET dans le if interne ET _complete() le redecode integralement a chaque recv (O(n^2) sur la taille de reponse, negligeabl
- **Effort** : 30 min

## [BASSE/backlog [RADIO]] logx_flrig.py:98 — Le mode est transmis verbatim a set_mode sans gestion USB-DATA/PKTUSB : rien ne garantit le routage audio arriere pour FT8
- **Defaut** : set_freq passe `str(mode)` tel quel a rig.set_mode. Point 2 de la checklist : FT8 exige un mode data (USB-D/DATA-U/PKTUSB, ou USB-D1/D2 chez Icom) qui route l'audio USB arriere, pas 'USB' seul. Ce backend ne connait pas la distinction et se repose entierement sur le nom de mode fourni par l'appelant. HYPOTHESE A VERIFIER : le mappage correct peut etre fait en amont ; ici on ne peut que constater l'absence de toute normalisation/validation du mode data.
- **Effort** : 2h

## [BASSE/amelioration] logx_flrig.py:58 — Un ServerProxy (et sa connexion TCP) est recree a chaque appel : montage/demontage TCP a chaque poll
- **Defaut** : _proxy() construit un ServerProxy neuf a chaque get_state/set_freq/set_ptt ; il est jete a la sortie du bloc `with`, donc la connexion HTTP mise en cache par le Transport meurt avec lui. Chaque poll (get_state, potentiellement toutes les 1-3 s selon le point 9 de la checklist) ouvre puis ferme une connexion TCP au lieu de reutiliser un proxy persistant. Fonctionnellement correct mais inefficace et generateur de churn de sockets.
- **Effort** : 30 min

## [BASSE/amelioration [RADIO]] logx_omnirig.py:233 — Timeout trompeur sous concurrence : un 2e appel qui fait la queue derriere un appel lent signale a tort 'OmniRig ne repond pas'
- **Defaut** : _com_call partage un executor a 1 seul worker (l.131/212) et borne l'appel par fut.result(timeout=TIMEOUT_S + 2) = 5 s (l.233). Ce delai court a partir de la SOUMISSION, pas du debut d'execution. Deux appels HTTP concurrents (p.ex. un get_state en polling et un set_ptt du voicekeyer) se serialisent : le 2e attend que le 1er finisse PUIS s'execute. Si le 1er prend ~4 s (legitime mais lent), le 2e depasse 5 s de file+exec alors que son propre appel COM serait rapide, et renvoie 'OmniRig ne repond 
- **Effort** : 1h

## [BASSE/amelioration [RADIO]] logx_omnirig.py:196 — Absence d'interrogation de capacite : une commande non supportee par le rig est rapportee 'OmniRig injoignable'
- **Defaut** : Checklist #8. set_mode/set_freq/set_ptt supposent que l'ecriture de propriete (rig.Mode, rig.Freq, rig.Tx) reussit. Si le rig ou la config OmniRig ne supporte pas la commande (mode data absent, PTT CAT non gere), l'appel COM leve une exception attrapee par le catch generique l.195-196 qui renvoie {'ok': False, 'error': f'OmniRig injoignable ({e})'}. Le message est faux : OmniRig EST joignable (Status a deja ete lu a ST_ONLINE juste avant), c'est la commande qui n'est pas disponible. Aucun pre-co
- **Effort** : 1h

## [BASSE/backlog [RADIO]] logx_omnirig.py:292 — Aucun support Split / Fake It pour FT8 alors que FreqA/FreqB sont exposes par IRigX
- **Defaut** : Checklist #1. get_state ne lit que rig.Freq (l.269), set_freq n'ecrit que rig.Freq (l.292) ; aucune bascule split, aucune gestion FreqA/FreqB. Le split FT8 (Rig-split OU Fake It : decaler le VFO cadran pour garder l'audio dans la zone propre du filtre SSB) ne peut pas etre pilote par ce backend. A noter honnetement : le split n'est cable dans AUCUN backend a ce jour (logx_cat.py:829-832 dit que SPLIT_STYLE est calcule mais qu'aucune methode ne l'utilise pour emettre une commande split) — c'est d
- **Effort** : 1 jour

## [BASSE/amelioration] logx_flexradio.py:382 — reader.is_alive() ne prouve pas la liaison vivante : cache perime servi jusqu'a ~30 s avec ok=True (pas d'horodatage de fraicheur)
- **Defaut** : _ensure_connected() considere la connexion saine tant que le thread de lecture est is_alive(). Or sur une coupure reseau demi-ouverte (pas de FIN/RST), recv() ne leve qu'apres READ_IDLE_TIMEOUT_S=30 s : pendant cette fenetre le thread reste vivant, is_alive()=True, et get_state() renvoie ok=True avec la derniere frequence en cache (potentiellement fausse). Le commentaire affirme que cette verification evite de servir 'indefiniment' un cache mort — c'est vrai a la borne pres (30 s), mais aucun ho
- **Effort** : 2-3h (horodater chaque MAJ de freq/interlock et exposer un age max dans get_state, ou envoyer un ping periodique 'ping' documente)

## [BASSE/bug [RADIO]] logx_icomremote.py:103 — Adresse CI-V en hex NU tout-chiffres silencieusement lue en decimal (0x94/0x98 faux)
- **Defaut** : _parse_civ_addr tente int(s, 0) AVANT le repli int(s, 16). Toute chaine ne contenant que des chiffres est donc acceptee comme DECIMAL et n'atteint jamais le repli hex. Les adresses CI-V ecrites en hex nu (sans prefixe 0x, comme dans les manuels Icom) qui sont tout-chiffres sont mal converties : '94' -> 94 (au lieu de 0x94=148, IC-7300), '98' -> 98 (au lieu de 0x98=152, IC-7610). Incoherence directe avec les adresses contenant une lettre, elles correctement lues en hex : 'A4' -> 164 (0xA4, IC-705
- **Effort** : 15 min

## [BASSE/backlog] logx_icomremote.py:143 — Checklist CAT/FT8 (split, USB-DATA, garde UTC, handshake, port PTT, capacites, poll) inauditable ici : hors perimetre de ce module
- **Defaut** : La consigne du domaine demande de verifier 10 points CAT/FT8 (split Rig+Fake It et separation cadran/audio, mode USB-DATA/PKTUSB, handshake RTS/DTR pyserial pose avant open(), separation port CAT/PTT, garde de derive UTC ~1 s, longueur trame Yaesu, interrogation des capacites, intervalle de poll, exclusivite du port CAT). AUCUN de ces points n'est traitable dans ce fichier : le module est un stub desactive par conception (get_state/set_freq/set_ptt/test_connection renvoient tous {'ok': False} sa
- **Effort** : n/a (redirection d'audit vers logx_cat/logx_rig/logx_flrig/logx_tci)

## [BASSE/bug] logx_tci.py:529 — HYPOTHESE A VERIFIER : les noms de commande s-mètre écoutés ('rx_sensors'/'rx_channel_sensors') ne correspondent peut-être pas à la commande TCI réelle — smeter_dbm resterait à None
- **Defaut** : _handle_line ne met à jour smeter_dbm que sur les lignes nommées 'rx_sensors' ou 'rx_channel_sensors'. Si le serveur TCI émet le niveau via un autre nom de commande, smeter_dbm reste None en permanence et get_state renvoie toujours smeter_dbm:None. Impossible de sourcer le nom exact de la commande depuis le dépôt.
- **Effort** : 30 min (observation d'un flux réel)

## [BASSE/backlog] logx_tci.py:708 — L'état PTT est suivi en interne mais jamais exposé par get_state(cfg) — la couche client ne peut pas connaître l'état émission via TCI
- **Defaut** : _handle_line maintient self.state['ptt'] (L.528) et TciClient.get_state le renvoie (L.546), mais la fonction module get_state(cfg) (L.708-710) n'inclut PAS 'ptt' dans son dict de sortie. Toute UI qui voudrait afficher l'état TX réel (retour de trx push du serveur, ou PTT déclenché par un autre logiciel partageant le SDR) n'y a pas accès, contrairement à freq/mode/smeter.
- **Effort** : 15 min

## [BASSE/amelioration] logx_ft8.html:1318 — Commentaire périmé : affirme que le décalage de VFO (Fake It) n'est pas fait, alors qu'il est implémenté et appelé à l'émission
- **Defaut** : Incohérence documentaire : la preuve de conception (le pavé « PROPRETÉ DU SIGNAL ÉMIS ») dit que le VFO n'est pas décalé, ce qui est faux depuis l'ajout de decalageVfoHz/#ft8DecalageVfo. Un mainteneur qui lit ce commentaire pour décider d'ajouter le Fake It le ré-implémenterait ou casserait le comportement existant en croyant partir de zéro.
- **Effort** : 5 min

## [BASSE/backlog [RADIO]] logx_ft8.html:1342 — Un seul mode de split implémenté (Fake It) ; le mode « Rig » split de la référence WSJT-X est absent
- **Defaut** : Par rapport à la checklist point 1 (gérer le split Rig ET Fake It), seul Fake It existe. Certains opérateurs/postes préfèrent le split Rig matériel (moins de commutations du VFO principal, pas de QSY du cadran). C'est une piste de complétude à arbitrer, pas un défaut de correction — Fake It atteint le même objectif acoustique.
- **Effort** : 1 jour

## [BASSE/backlog [RADIO]] logx_ft8.html:1567 — La détection de dérive d'horloge est purement consultative : rien ne bloque/confirme une émission FT8 quand l'horloge est mesurée fausse
- **Defaut** : Checklist point 6 : il n'existe pas de garde de synchro UTC avant d'autoriser une émission ; la connaissance existe (médiane DT, mesure SNTP) mais n'est pas branchée sur le chemin d'émission. À arbitrer : WSJT-X non plus ne bloque pas durement l'émission sur dérive d'horloge (parité de référence) — d'où le classement backlog/confiance basse. Une confirmation optionnelle « ton horloge est décalée de X s, émettre quand même ? » resterait dans l'esprit du produit (panne muette évitée).
- **Effort** : 2 h

## [BASSE/amelioration [RADIO]] logx_ft8.html:2736 — stopEmission() appelle annulerEmissionsProgrammees() deux fois, lancant jusqu'a trois relacherPtt() concurrents dont deux non attendus
- **Defaut** : stopEmission() invoque annulerEmissionsProgrammees() en 2729 ET en 2736 (appels identiques, vraisemblablement un artefact de fusion). Chaque appel fait couperAudioTx() puis, si pttDemande, `relacherPtt(6)` NON attendu (2573). Ajoutes au couperAudioTx()/relacherPtt(6) awaited de 2744-2745, cela peut declencher jusqu'a 3 boucles de reessai PTT-OFF simultanees se disputant le meme drapeau pttDemande et bombardant /rig/ptt. Fonctionnellement ca finit par relacher, mais c'est de la dette : duplicatio
- **Effort** : 10 min

## [BASSE/backlog] logx_hardware_cat.js:144 — Table de plan de bande codee en dur dans le client (bornes freq->bande), potentiellement dupliquee avec le serveur
- **Defaut** : syncBandModeFromRig() embarque une table freq->bande interne codee en dur (bornes 'larges pour segments contest'). Ce sont des valeurs de domaine (limites de bandes) inscrites cote client, alors que la normalisation CAT (modes) est explicitement decrite comme un reflet de tables serveur (logx_cat.py). Le mapping bande n'a pas de source citee dans ce fichier et duplique vraisemblablement une notion de plan de bande existant ailleurs — a mutualiser/sourcer pour eviter la derive entre client et ser
- **Effort** : 1 jour

## [BASSE/amelioration] logx_reglages_poste.js:116 — Valeurs de « Défaut d'usine » affirmées mais absentes de leurs citations (défaut systémique de sourçage)
- **Defaut** : De nombreuses lignes annoncent une valeur d'usine précise (« défaut 50 % », « Défaut d'usine : ACC », « défaut 4 ») que la citation attachée ne mentionne pas — la citation ne donne souvent que la description générique ou la plage. Le préambule affirme pourtant que chaque ligne est « vérifiable » par sa citation. Ce sont des VALEUR A SOURCER selon la règle d'audit 4.
- **Effort** : 1h

## [BASSE/backlog] logx_reglages_poste.js:37 — Socle universel FT8 : rien sur le split / Fake It (décalage VFO pour garder l'audio dans la zone propre du filtre SSB)
- **Defaut** : Le socle universel couvre mode, niveau, filtre, AGC, puissance (checklist WSJT-X partielle) mais n'aborde ni le split (Rig/Fake It) ni le principe RF_reelle = freq_cadran + freq_audio qui maintient l'audio ~1500-2000 Hz hors des flancs du filtre SSB. Pour l'audience débutante revendiquée (l.3-6), l'absence de cette consigne peut conduire à émettre avec l'audio en bord de bande passante (distorsion/splatter).
- **Effort** : 1 jour

## [BASSE/amelioration] logx_ft8_dsp.js:659 — Incoherence d'API : ft8DecodeAudio ne rend pas snrDb alors que ft8DecodeAudioAll le rend
- **Defaut** : ft8DecodeAudioAll (l.702-706) retourne des objets avec snrDb (report reel envoye sur l'air, dont le commentaire l.695-701 souligne l'importance). ft8DecodeAudio (l.659-661) retourne le meme genre d'objet (text, freqHz, syncScore, startSample) mais SANS snrDb, alors que ft8EstimerSnr est disponible et prend exactement (samples, startSample, baseFreqHz, sampleRate) deja calcules ici. Deux formes de resultat divergentes pour deux fonctions soeurs : piege pour tout code qui basculerait de l'une a l'
- **Effort** : 15 min (ajouter snrDb a ft8DecodeAudio pour aligner les deux formes)
