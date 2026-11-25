# -*- coding: utf-8 -*-
"""Tout POST du navigateur vers le serveur doit porter Content-Type JSON.

Le serveur refuse en 415 tout POST sans `Content-Type: application/json`
(garde CSRF, logx_http.py do_POST) — seul /qsl_scan/upload (multipart) est
exempté. Audit du 25/11/2026 : /calldb/enrich_from_log et /lan/firewall/open
étaient appelés sans cet en-tête, donc échouaient TOUJOURS, en silence
(/moon/track/start|stop trouvé par ce même test).
"""
import glob
import os
import re

CONCOURS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _sans_commentaires_js(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'(?m)(^|[^:\'"\\])//.*$', r'\1', s)


def _appel(s, i):
    """Texte de l'appel fetch( ... ) qui commence en i (parenthèses équilibrées)."""
    prof = 0
    for k in range(i, len(s)):
        if s[k] == '(':
            prof += 1
        elif s[k] == ')':
            prof -= 1
            if prof == 0:
                return s[i:k + 1]
    return s[i:]


def _posts_sans_json():
    fautifs = []
    for f in sorted(glob.glob(os.path.join(CONCOURS, '*.js')) + glob.glob(os.path.join(CONCOURS, '*.html'))):
        s = _sans_commentaires_js(open(f, encoding='utf-8').read())
        for m in re.finditer(r'\bfetch\(', s):
            appel = _appel(s, m.start() + len('fetch'))
            if not re.search(r"method\s*:\s*['\"]POST['\"]", appel):
                continue
            if '/qsl_scan/upload' in appel:
                continue
            # en-tête littéral, ou objet d'en-têtes nommé (vérifié ailleurs)
            if 'application/json' in appel or re.search(r'headers\s*:\s*[A-Za-z_$]', appel):
                continue
            fautifs.append('%s:%d %s' % (os.path.basename(f), s.count('\n', 0, m.start()) + 1,
                                         appel[:80].replace('\n', ' ')))
    return fautifs


def test_tout_post_porte_l_entete_json():
    assert _posts_sans_json() == []
