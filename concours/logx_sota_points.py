"""Points de chasse SOTA « indicatifs » (non officiels) — calcul purement local.

Rien n'est jamais envoyé à SOTA : ces totaux servent à donner à l'opérateur un
ordre de grandeur de ses chasses, PAS un score officiel (le score officiel ne
peut venir que de sotadata.org.uk après téléversement du log).

Règles SOURCÉES sur les « SOTA General Rules v1.20 » (PDF officiel, lu le
30/08/2026) :

- **Valeur d'un sommet (règle 3.11)** : 1/2/4/6/8/10 points selon six paliers
  d'altitude. Portée par le champ `points` de la base des sommets
  (`logx_sota.get_summit`).
- **Chasse (règle 3.8 §3)** : « only one QSO with a given Summit on any one day
  (defined as 00:00 to 23:59 UTC) counts for points » → un sommet compte UNE
  fois par jour UTC. Le même sommet un autre jour recompte.
- **S2S (règle 3.8 §7)** : un opérateur lui-même sur un sommet peut réclamer les
  points de chasse des sommets contactés pendant son expédition → un QSO est
  « S2S » quand MON sommet ET celui du correspondant sont renseignés (les deux
  en SOTA). Même dédoublonnage 1×/sommet/jour UTC. Le S2S est un SOUS-ENSEMBLE
  de la chasse (s2s ≤ chasse toujours).
- **Aucun bonus saisonnier** en chasse ni en S2S (règle 3.11.1 : le bonus
  d'hiver est réservé aux expéditions/portable) → aucune logique de bonus ici.

Le QSO stocke la référence du correspondant en `sig` (programme, ex. « SOTA »)
+ `sig_info` (code sommet, ex. « G/LD-001 »), mon propre sommet en `my_sig` /
`my_sig_info`, et la date en `date` au format 'YYYYMMDD' UTC (cf. nowDateUTC()).
"""


def _annee_de(date):
    """'YYYYMMDD' -> 'YYYY', ou '' si la date est absente/mal formée."""
    d = (date or '').strip()
    return d[:4] if len(d) >= 4 and d[:4].isdigit() else ''


def points_chasse(log, lookup, year=None):
    """Somme des points de chasse SOTA indicatifs sur un carnet.

    Args:
        log: itérable de QSO (dicts). Champs lus : `sig`/`sig_info` (réf. du
            correspondant), `my_sig`/`my_sig_info` (mon sommet en portable),
            `date` ('YYYYMMDD' UTC).
        lookup: callable `code -> dict` (avec clé `points`) ou `None` si le
            sommet est inconnu de la base (typiquement `logx_sota.get_summit`).
        year: si fourni (int ou str), ne compte que les QSO de cette année UTC ;
            sinon compte tout le carnet.

    Returns:
        dict {'chasse': int, 's2s': int, 'sommets': int, 's2s_sommets': int}.
        Dédoublonnage : un sommet compte une seule fois par jour UTC (règle
        3.8 §3). `s2s` est le sous-ensemble où mon propre sommet SOTA est aussi
        renseigné (règle 3.8 §7).
    """
    yr = str(year) if year not in (None, '') else None
    vus = {}       # (code, date UTC) -> points  — chasse (idempotent par jour)
    vus_s2s = {}   # (code, date UTC) -> points  — S2S (sous-ensemble)
    for q in log:
        if not isinstance(q, dict):
            continue
        if (q.get('sig') or '').strip().upper() != 'SOTA':
            continue
        code = (q.get('sig_info') or '').strip().upper()
        if not code:
            continue
        date = (q.get('date') or '').strip()
        if yr is not None and _annee_de(date) != yr:
            continue
        sommet = lookup(code)
        if not sommet:
            continue
        try:
            pts = int(sommet.get('points') or 0)
        except (TypeError, ValueError):
            pts = 0
        if pts <= 0:
            continue
        cle = (code, date)
        vus[cle] = pts  # même sommet, même jour UTC -> une seule entrée
        if (q.get('my_sig') or '').strip().upper() == 'SOTA' \
                and (q.get('my_sig_info') or '').strip():
            vus_s2s[cle] = pts
    return {
        'chasse': sum(vus.values()),
        's2s': sum(vus_s2s.values()),
        'sommets': len(vus),
        's2s_sommets': len(vus_s2s),
    }


def totaux(log, lookup, annee_courante):
    """Enveloppe pour l'endpoint : totaux de l'année courante ET cumul.

    `annee_courante` est injectée (jamais lue de l'horloge ici) pour rester
    testable — l'appelant passe l'année UTC du moment.
    """
    an = points_chasse(log, lookup, year=annee_courante)
    tout = points_chasse(log, lookup, year=None)
    return {
        'year': int(annee_courante),
        'chasse_year': an['chasse'], 's2s_year': an['s2s'],
        'sommets_year': an['sommets'], 's2s_sommets_year': an['s2s_sommets'],
        'chasse_all': tout['chasse'], 's2s_all': tout['s2s'],
        'sommets_all': tout['sommets'], 's2s_sommets_all': tout['s2s_sommets'],
    }
