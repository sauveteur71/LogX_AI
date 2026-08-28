# -*- coding: utf-8 -*-
"""Provenance par champ : d'où vient chaque donnée enrichie d'un indicatif.

Pour la confiance (« FAIT »), on montre la SOURCE de chaque valeur. v1, à partir
de l'indicatif SEUL et hors-ligne :
  - Pays / Continent / Zone CQ / Zone ITU -> cty.dat (base DXCC locale) ;
  - Distance / Azimut -> calculés (position de référence cty.dat + votre QTH).

Fonction pure et déterministe (aucun réseau) ; le locator/nom via callbook
pourront s'ajouter plus tard (source = fournisseur callbook). Lecture seule.
"""


def provenance(call, cfg=None):
    """[{champ, valeur, source}] pour l'indicatif `call`. Vide si inconnu."""
    import logx_dxcc as dxcc
    from logx_utils import locator_to_latlon, haversine, bearing

    call = str(call or '').strip()
    rows = []
    if not call:
        return rows
    info = dxcc.lookup(call)
    if not info:
        return rows

    if info.get('country'):
        rows.append({'champ': 'Pays', 'valeur': info['country'], 'source': 'cty.dat'})
    if info.get('continent'):
        rows.append({'champ': 'Continent', 'valeur': str(info['continent']), 'source': 'cty.dat'})
    if info.get('cq_zone') is not None:
        rows.append({'champ': 'Zone CQ', 'valeur': str(info['cq_zone']), 'source': 'cty.dat'})
    if info.get('itu_zone') is not None:
        rows.append({'champ': 'Zone ITU', 'valeur': str(info['itu_zone']), 'source': 'cty.dat'})

    my_loc = str((cfg or {}).get('locator') or '').strip()
    if info.get('lat') is not None and info.get('lon') is not None and my_loc:
        mll = locator_to_latlon(my_loc)
        if mll and mll[0] is not None:
            d = haversine(mll[0], mll[1], info['lat'], info['lon'])
            az = bearing(mll[0], mll[1], info['lat'], info['lon'])
            rows.append({'champ': 'Distance', 'valeur': '%d km' % round(d), 'source': 'calculé (cty.dat)'})
            rows.append({'champ': 'Azimut', 'valeur': '%d°' % round(az), 'source': 'calculé (cty.dat)'})
    return rows
