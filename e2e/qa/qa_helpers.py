"""Helpers QA mobile partagés par les subagents de test (Playwright Python, Chromium émulé iPhone).

Usage type :

    import sys; sys.path.insert(0, "<dossier qa>")
    from qa_helpers import *
    with sync_playwright() as p:
        browser, ctx, page, logs = open_mobile(p)
        page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1200)
        before = scroll_state(page)
        drag_piece(page, "e2", "e4")          # vrai drag TACTILE (CDP), pas souris
        after = scroll_state(page)
        shot(page, "analyse_after_drag")       # -> <SHOTS>/analyse_after_drag.png, à relire avec l'outil Read
        browser.close()
"""
import json
import os

from playwright.sync_api import sync_playwright  # noqa: F401  (ré-exporté)

BASE = os.environ.get("BASE", "http://localhost:5199")
QA_DIR = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.environ.get("SHOTS", os.path.join(QA_DIR, "shots"))
os.makedirs(SHOTS, exist_ok=True)

DEFAULT_SETTINGS = {
    "themeId": "green",
    "showLegalMoves": True,
    "playSounds": False,
    "chesscomUsername": "",
    "reviewDepth": "fast",
}


def open_mobile(p, settings=None, device="iPhone 14 Pro", headless=True, standalone=False):
    """Chromium émulé iPhone (DPR 3, hasTouch, UA iOS). Retourne (browser, ctx, page, logs).

    standalone=False : viewport 393x660, celui d'un onglet Safari (barres du navigateur déduites).
    standalone=True  : viewport 393x852, celui de la PWA installée (plein écran). C'est la cible
                       principale de l'app. Attention : env(safe-area-inset-*) vaut 0 en émulation.
    """
    browser = p.chromium.launch(headless=headless)
    opts = dict(p.devices[device])
    if standalone:
        opts["viewport"] = {"width": 393, "height": 852}
    ctx = browser.new_context(**opts)
    page = ctx.new_page()
    state = {"state": {**DEFAULT_SETTINGS, **(settings or {})}, "version": 0}
    page.add_init_script(
        "if (!localStorage.getItem('chess-local-settings')) "
        f"localStorage.setItem('chess-local-settings', {json.dumps(json.dumps(state))})"
    )
    logs = []
    page.on("pageerror", lambda e: logs.append(f"PAGEERROR: {str(e)[:300]}"))
    page.on("console", lambda m: logs.append(f"CONSOLE.{m.type}: {m.text[:300]}") if m.type in ("error", "warning") else None)
    return browser, ctx, page, logs


def open_desktop(p, settings=None, width=1440, height=900):
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": width, "height": height})
    page = ctx.new_page()
    state = {"state": {**DEFAULT_SETTINGS, **(settings or {})}, "version": 0}
    page.add_init_script(
        "if (!localStorage.getItem('chess-local-settings')) "
        f"localStorage.setItem('chess-local-settings', {json.dumps(json.dumps(state))})"
    )
    logs = []
    page.on("pageerror", lambda e: logs.append(f"PAGEERROR: {str(e)[:300]}"))
    page.on("console", lambda m: logs.append(f"CONSOLE.{m.type}: {m.text[:300]}") if m.type in ("error", "warning") else None)
    return browser, ctx, page, logs


def shot(page, name, full_page=False):
    path = os.path.join(SHOTS, f"{name}.png")
    page.screenshot(path=path, full_page=full_page)
    return path


def sq_center(page, square):
    """Centre (x, y) en px CSS de la case (ex 'e2'), quelle que soit l'orientation du board."""
    box = page.locator(f"[data-square='{square}']").first.bounding_box()
    if not box:
        raise RuntimeError(f"case {square} introuvable")
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def tap_square(page, square):
    x, y = sq_center(page, square)
    page.touchscreen.tap(x, y)


def tap_move(page, frm, to, pause=250):
    """Coup en deux taps (tap pièce puis tap destination)."""
    tap_square(page, frm)
    page.wait_for_timeout(pause)
    tap_square(page, to)
    page.wait_for_timeout(pause)


def touch_drag(page, x1, y1, x2, y2, steps=14, step_ms=16, hold_ms=60):
    """Drag TACTILE réel via CDP Input.dispatchTouchEvent : passe par le pipeline de gestes du
    navigateur, donc un défaut de `touch-action` fait scroller la page comme sur un vrai téléphone."""
    cdp = page.context.new_cdp_session(page)
    pt = lambda x, y: [{"x": round(x, 1), "y": round(y, 1), "id": 1, "radiusX": 8, "radiusY": 8, "force": 1}]
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pt(x1, y1)})
    page.wait_for_timeout(hold_ms)
    for i in range(1, steps + 1):
        x = x1 + (x2 - x1) * i / steps
        y = y1 + (y2 - y1) * i / steps
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": pt(x, y)})
        page.wait_for_timeout(step_ms)
    page.wait_for_timeout(hold_ms)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()
    page.wait_for_timeout(250)


def drag_piece(page, frm, to, **kw):
    x1, y1 = sq_center(page, frm)
    x2, y2 = sq_center(page, to)
    touch_drag(page, x1, y1, x2, y2, **kw)


def scroll_state(page):
    """État à comparer avant/après un geste : scroll fenêtre, scroll du <main>, route, historique."""
    return page.evaluate(
        """() => {
          const m = document.querySelector('main')
          return {
            windowScrollY: Math.round(window.scrollY),
            mainScrollTop: m ? Math.round(m.scrollTop) : null,
            mainScrollable: m ? m.scrollHeight > m.clientHeight : null,
            mainScrollHeight: m ? m.scrollHeight : null,
            mainClientHeight: m ? m.clientHeight : null,
            hash: location.hash,
            historyLength: history.length,
          }
        }"""
    )


def piece_on(page, square):
    """Code pièce ('wP', 'bK', ...) sur la case, ou None. Lit l'attribut data-piece de react-chessboard."""
    return page.evaluate(
        """(sq) => {
          const el = document.querySelector(`[data-square='${sq}'] [data-piece]`)
          return el ? el.getAttribute('data-piece') : null
        }""",
        square,
    )


def overflow_x(page):
    """Débordement horizontal de la page (doit être 0 sur mobile)."""
    return page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
