"""Enveloppe locale de qa_helpers (que je ne modifie pas : module partagé).

Le serveur dev 5199 était injoignable au moment des tests et la consigne interdit d'en lancer un.
Repli SANS serveur ni port : les requêtes vers BASE sont servies depuis le build `dist/` du repo
(lecture seule) par interception Playwright. Si le serveur répond, on l'utilise tel quel.
Le mode réellement utilisé est imprimé en tête de chaque script (MODE=dev-server | dist-intercept).
"""
import os
import sys
import urllib.request
from urllib.parse import urlparse

QA = "e2e/qa"
sys.path.insert(0, QA)
from qa_helpers import *  # noqa: F401,F403,E402
import qa_helpers as _h  # noqa: E402

DIST = "dist"
BLOCK = ("sw.js", "registerSW.js")  # pas de service worker : évite le précache de 25 Mo


def server_up():
    try:
        with urllib.request.urlopen(_h.BASE + "/", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


MODE = "dev-server" if server_up() else "dist-intercept"
print(f"MODE={MODE} BASE={_h.BASE}")


def _handler(route):
    path = urlparse(route.request.url).path.lstrip("/") or "index.html"
    name = os.path.basename(path)
    if name in BLOCK or name.startswith("workbox-"):
        return route.fulfill(status=404, body="")
    full = os.path.normpath(os.path.join(DIST, path))
    if not full.startswith(DIST) or not os.path.isfile(full):
        return route.fulfill(status=404, body="")
    route.fulfill(path=full)


def open_mobile_t(p, standalone=False, settings=None, width=None, height=None):
    """open_mobile + repli dist. width/height : viewport forcé (ex 393x560)."""
    browser, ctx, page, logs = _h.open_mobile(p, settings=settings, standalone=standalone)
    if MODE == "dist-intercept":
        ctx.route(_h.BASE + "/**", _handler)
    if width and height:
        page.set_viewport_size({"width": width, "height": height})
    return browser, ctx, page, logs
