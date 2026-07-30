# -*- coding: utf-8 -*-
"""Wait-and-Pounce : décider s'il faut appeler une station entendue.

LES QUATRE NIVEAUX, demandés par l'utilisateur, chacun activable séparément :

  1 SIGNALER   son + couleur quand un décodage vaut le coup. Déjà en place.
  2 ARMER      un clic prépare la réponse dans WSJT-X ; l'opérateur émet.
  3 APPELER    le logiciel déclenche l'appel dès qu'un décodage correspond
               aux règles. Quelqu'un est devant la radio.
  4 SANS PERSONNE  le niveau 3 qui continue de tourner sans surveillance.
               L'utilisateur l'a précisé : « tout automatique veut dire
               personne devant la radio ».

CE MODULE NE PARLE À PERSONNE. Il ne connaît ni socket, ni HTTP, ni WSJT-X :
il reçoit un décodage et un état, et rend une décision motivée. Tout ce qui
émet vit dans logx_wsjtx.repondre_a(). Cette séparation n'est pas cosmétique —
elle permet de tester l'intégralité du raisonnement, y compris les cas qui
feraient émettre, sans qu'un seul octet ne parte sur l'air.

CE QUE LOGX SAIT ET QUE WAIT-AND-POUNCE IGNORE. L'utilitaire de F5UKW raisonne
sur « déjà contacté ou non ». LogX sait POURQUOI une station compte : nouveau
multiplicateur pour le concours en cours, carré jamais travaillé, entité non
confirmée LoTW sur CE créneau bande × mode précis, le tout contre un carnet à
vie. C'est une sélection nettement plus fine, et elle existe déjà.

LES GARDE-FOUS NE SONT PAS DE LA PRUDENCE DÉCORATIVE. Une station qui émet
sans personne devant elle peut le faire pendant des heures, appeler cent fois
la même station sourde, ou continuer après la fin du concours. Chacun des
verrous ci-dessous répond à une de ces façons de mal finir :

  • DURÉE MAXIMALE, obligatoire au niveau 4. Une session s'arrête toute seule.
  • UN SEUL APPEL EN VOL. WSJT-X mène un QSO à la fois : ré-armer à chaque
    décodage le ferait sauter de station en station sans en finir aucune.
  • PAS DEUX FOIS LA MÊME STATION. Si elle n'a pas répondu en trois cycles,
    insister ne sert à rien et encombre la fréquence.
  • PLAFOND D'APPELS. Filet de sécurité contre une boucle involontaire.
  • JOURNAL DE TOUT CE QUI EST PARTI. Sans surveillance, c'est la seule façon
    de savoir après coup ce que la station a fait en votre nom.
"""
import time

NIVEAU_SIGNALER = 1
NIVEAU_ARMER = 2
NIVEAU_APPELER = 3
NIVEAU_SANS_PERSONNE = 4

# Durée par défaut d'une session sans surveillance. Volontairement courte : on
# la prolonge d'un clic, alors qu'on ne récupère pas une heure d'émission qu'on
# n'a pas vue passer.
DUREE_DEFAUT_MIN = 30
DUREE_MAX_MIN = 480          # 8 h : au-delà, c'est une station automatique

# Trois cycles FT8 sans réponse : la station ne nous entend pas, ou elle est
# occupée ailleurs. Insister n'apporte rien et occupe la fréquence.
CYCLES_AVANT_ABANDON = 3
DUREE_CYCLE_S = 15

# Filet contre l'emballement. En FT8 un QSO prend au mieux une minute : plus de
# 30 appels par quart d'heure signale un défaut, pas un bon week-end.
PLAFOND_APPELS = 30
FENETRE_PLAFOND_S = 900

MOTIFS = {
    'nouveau_pays': 'entité jamais travaillée',
    'besoin_lotw': 'entité non confirmée LoTW sur ce créneau',
    'carre_neuf': 'carré jamais travaillé',
    'nouveau_mult': 'nouveau multiplicateur',
}

DEFAUTS = {
    'niveau': NIVEAU_SIGNALER,
    'criteres': ['nouveau_pays', 'besoin_lotw'],
    'bandes': [],            # [] = toutes
    'modes': [],             # [] = tous
    'exclus': [],            # indicatifs à ne jamais appeler
    'duree_min': DUREE_DEFAUT_MIN,
}


def reglages_valides(brut):
    """Normalise ce qui vient de la configuration.

    Un réglage illisible dégrade vers le niveau 1 — SIGNALER. Le doute ne doit
    jamais profiter à l'émission : c'est l'inverse de la règle appliquée aux
    filtres de spots, où le doute profite à l'affichage. Dans les deux cas on
    dégrade vers l'inoffensif.
    """
    r = dict(DEFAUTS)
    r['criteres'] = list(DEFAUTS['criteres'])
    if not isinstance(brut, dict):
        return r
    try:
        n = int(brut.get('niveau', NIVEAU_SIGNALER))
    except (TypeError, ValueError):
        n = NIVEAU_SIGNALER
    r['niveau'] = n if n in (1, 2, 3, 4) else NIVEAU_SIGNALER
    for cle in ('bandes', 'modes', 'exclus'):
        v = brut.get(cle)
        if isinstance(v, str):
            v = v.replace(';', ',').split(',')
        r[cle] = [str(x).strip().upper() for x in v if str(x).strip()] \
            if isinstance(v, (list, tuple)) else []
    crit = brut.get('criteres')
    if isinstance(crit, (list, tuple)):
        propres = [str(c).strip() for c in crit if str(c).strip() in MOTIFS]
        r['criteres'] = propres
    try:
        d = int(brut.get('duree_min', DUREE_DEFAUT_MIN))
    except (TypeError, ValueError):
        d = DUREE_DEFAUT_MIN
    r['duree_min'] = max(1, min(DUREE_MAX_MIN, d))
    return r


class Session:
    """L'état d'une session d'appel automatique. Une seule à la fois.

    Rien ne démarre sans un `armer()` explicite : au rechargement du serveur,
    une session en cours ne survit pas. C'est voulu — une station qui se
    remettrait à émettre toute seule après un redémarrage inopiné est
    exactement ce qu'il ne faut pas.
    """

    def __init__(self, horloge=time.time):
        self._horloge = horloge
        self.reinitialiser()

    def reinitialiser(self):
        self.active = False
        self.niveau = NIVEAU_SIGNALER
        self.reglages = reglages_valides({})
        self.expire_a = 0.0
        self.appel_en_cours = ''
        self.appel_depuis = 0.0
        self.appeles = {}          # indicatif -> nombre d'appels
        self.journal = []          # tout ce qui est parti, dans l'ordre
        self.motif_arret = ''

    # ── Armer / désarmer ────────────────────────────────────────────────────
    def armer(self, reglages):
        r = reglages_valides(reglages)
        if r['niveau'] < NIVEAU_APPELER:
            return {'ok': False,
                    'error': "Les niveaux 1 et 2 n'ont rien a armer : "
                             "ils n'emettent jamais d'eux-memes"}
        if not r['criteres']:
            # Sans critère, « appelle ce qui est intéressant » voudrait dire
            # « appelle tout le monde ». On refuse plutôt que de deviner.
            return {'ok': False,
                    'error': 'Aucun critere coche : le logiciel appellerait tout le monde'}
        maintenant = self._horloge()
        self.active = True
        self.niveau = r['niveau']
        self.reglages = r
        self.expire_a = maintenant + r['duree_min'] * 60
        self.appel_en_cours = ''
        self.appeles = {}
        self.journal = []
        self.motif_arret = ''
        return {'ok': True, 'niveau': self.niveau,
                'expire_dans_s': int(self.expire_a - maintenant)}

    def desarmer(self, motif='arret manuel'):
        etait = self.active
        self.active = False
        self.appel_en_cours = ''
        self.motif_arret = motif
        return {'ok': True, 'etait_active': etait, 'motif': motif}

    def expiree(self):
        return self.active and self._horloge() >= self.expire_a

    def restant_s(self):
        return max(0, int(self.expire_a - self._horloge())) if self.active else 0

    # ── La décision ─────────────────────────────────────────────────────────
    def decider(self, decodage, interet):
        """Faut-il appeler cette station ?

        `decodage` : {'call', 'band', 'mode', 'last_seen'...}
        `interet`  : {'nouveau_pays': bool, 'besoin_lotw': bool, ...} — ce que
                     LogX sait de cette station, calculé par l'appelant.

        Retourne {'appeler': bool, 'motif': str}. Le motif est TOUJOURS
        renseigné, y compris sur un refus : sans surveillance, c'est la seule
        trace de pourquoi la station n'a pas appelé un DX qu'on attendait.
        """
        call = str((decodage or {}).get('call') or '').upper().strip()
        if not self.active:
            return {'appeler': False, 'motif': 'session inactive'}
        if self.expiree():
            self.desarmer('duree ecoulee')
            return {'appeler': False, 'motif': 'duree ecoulee'}
        if not call:
            return {'appeler': False, 'motif': 'indicatif vide'}
        r = self.reglages
        if call in r['exclus']:
            return {'appeler': False, 'motif': 'indicatif exclu'}
        bande = str(decodage.get('band') or '').upper()
        if r['bandes'] and bande not in r['bandes']:
            return {'appeler': False, 'motif': 'bande %s hors selection' % bande}
        mode = str(decodage.get('mode') or '').upper()
        if r['modes'] and mode not in r['modes']:
            return {'appeler': False, 'motif': 'mode %s hors selection' % mode}

        # Un seul appel en vol. WSJT-X mène UN QSO à la fois : ré-armer à
        # chaque décodage le ferait sauter de station en station sans en
        # terminer aucune, et l'opérateur retrouverait dix QSO à moitié faits.
        if self.appel_en_cours and self.appel_en_cours != call:
            attente = self._horloge() - self.appel_depuis
            if attente < CYCLES_AVANT_ABANDON * DUREE_CYCLE_S:
                return {'appeler': False,
                        'motif': 'appel de %s en cours' % self.appel_en_cours}
            # Le QSO en cours n'aboutit pas : on libère et on continue.
            self.appel_en_cours = ''

        if self.appeles.get(call, 0) >= CYCLES_AVANT_ABANDON:
            return {'appeler': False,
                    'motif': '%s appele %d fois sans reponse' % (call, self.appeles[call])}

        if len(self.journal) >= PLAFOND_APPELS:
            recents = [j for j in self.journal
                       if self._horloge() - j['t'] < FENETRE_PLAFOND_S]
            if len(recents) >= PLAFOND_APPELS:
                self.desarmer('plafond d appels atteint')
                return {'appeler': False, 'motif': 'plafond d appels atteint'}

        retenus = [c for c in r['criteres'] if (interet or {}).get(c)]
        if not retenus:
            return {'appeler': False, 'motif': 'aucun critere satisfait'}
        return {'appeler': True, 'motif': MOTIFS[retenus[0]],
                'criteres': retenus}

    def noter_appel(self, call, motif=''):
        """Enregistre un appel RÉELLEMENT parti. À n'appeler qu'après l'envoi :
        journaliser un appel qui a échoué fausserait le plafond et l'historique
        que l'opérateur relira."""
        c = str(call or '').upper().strip()
        maintenant = self._horloge()
        self.appel_en_cours = c
        self.appel_depuis = maintenant
        self.appeles[c] = self.appeles.get(c, 0) + 1
        self.journal.append({'t': maintenant, 'call': c, 'motif': motif,
                             'essai': self.appeles[c]})
        return self.journal[-1]

    def noter_qso(self, call):
        """Un QSO a abouti : la station n'est plus « en cours » et ne sera plus
        rappelée, quel que soit son intérêt."""
        c = str(call or '').upper().strip()
        if self.appel_en_cours == c:
            self.appel_en_cours = ''
        self.appeles[c] = CYCLES_AVANT_ABANDON      # ne plus jamais rappeler

    def etat(self):
        return {
            'active': self.active,
            'niveau': self.niveau,
            'sans_personne': self.active and self.niveau == NIVEAU_SANS_PERSONNE,
            'restant_s': self.restant_s(),
            'appel_en_cours': self.appel_en_cours,
            'appels': len(self.journal),
            'motif_arret': self.motif_arret,
            'journal': self.journal[-20:],
            'reglages': self.reglages,
        }


# Session unique du processus. Non persistée : un redémarrage la perd, et c'est
# la propriété qu'on veut (voir le commentaire de la classe).
session = Session()
