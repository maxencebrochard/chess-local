"""Socle partagé des suites E2E (Playwright Python, Chromium).

Trois rôles :
- `Checker` : compte les checks, les `pageerror` et les exceptions, et sort en code non nul
  au moindre échec. Une suite qui imprime « TOUT PASSE » avec un code 0 alors qu'elle a des
  `[FAIL]` ne protège de rien.
- contextes navigateur : iPhone 14 Pro tactile (cible principale de l'app) et desktop,
  réglages pré-remplis, API chess.com simulée.
- gestes : vrai drag TACTILE via CDP, lecture de l'échiquier, état de scroll.

Lancement normal : `npm run test:e2e` (voir e2e/run.py), qui démarre son propre serveur et
fournit BASE. Lancer une suite à la main exige BASE :
    BASE=http://localhost:5173 python3 e2e/test_learn.py
"""
import json
import os
import signal
import sys
import traceback

from playwright.sync_api import sync_playwright

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(E2E_DIR, "fixtures")
SHOTS = os.environ.get("SHOTS", os.path.join(E2E_DIR, "shots"))
os.makedirs(SHOTS, exist_ok=True)

# E2E_LIVE=1 : l'API chess.com réelle remplace la fixture (jamais dans le gate : réseau = flaky).
LIVE = os.environ.get("E2E_LIVE") == "1"

DEFAULT_SETTINGS = {
    "themeId": "green",
    "showLegalMoves": True,
    "playSounds": False,
    "chesscomUsername": "",
    "reviewDepth": "fast",
}


def base_url():
    """URL de l'app testée. Pas de valeur par défaut : un port codé en dur a déjà fait tester
    un serveur mort, puis un serveur fantôme. C'est e2e/run.py qui démarre le serveur."""
    base = os.environ.get("BASE", "").rstrip("/")
    if not base:
        sys.exit("BASE manquant. Lance `npm run test:e2e`, ou fournis BASE=http://hôte:port.")
    return base


BASE = base_url()


def settings_json(overrides=None):
    """Réglages au format Zustand persist (`{state, version}`), tels que l'app les relit."""
    return json.dumps({"state": {**DEFAULT_SETTINGS, **(overrides or {})}, "version": 0})


class Checker:
    """Bilan d'une suite. Tout ce qui est anormal est un échec : check faux, exception non
    rattrapée de la page (`pageerror`), requête chess.com non prévue, exception de la suite."""

    def __init__(self, suite):
        self.suite = suite
        self.passed = 0
        self.failures = []

    def check(self, name, cond, detail=""):
        ok = bool(cond)
        print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}".rstrip(), flush=True)
        if ok:
            self.passed += 1
        else:
            self.failures.append(name)
        return ok

    def fail(self, name, detail=""):
        return self.check(name, False, detail)

    def appears(self, name, page, selector, timeout=30000):
        """Check « l'élément finit par apparaître » : un échec propre plutôt qu'une exception
        qui interrompt la suite."""
        try:
            page.wait_for_selector(selector, timeout=timeout)
            return self.check(name, True)
        except Exception as e:  # TimeoutError de Playwright
            return self.check(name, False, f"({type(e).__name__} après {timeout} ms : {selector})")

    def watch(self, ctx):
        """À appeler juste après la création du contexte, AVANT new_page() : couvre toutes les
        pages du contexte, popups comprises, du premier chargement jusqu'à la fermeture."""
        ctx.on("page", self._watch_page)
        for page in ctx.pages:
            self._watch_page(page)
        return ctx

    def _watch_page(self, page):
        page.on("pageerror", lambda e: self.fail("[pageerror] exception non rattrapée dans la page", f"({str(e)[:300]})"))

    def run(self, body):
        """Exécute `body(p)` puis sort. Le navigateur est toujours fermé (sortie du `with`),
        et une exception de la suite donne un échec nommé, pas une pile brute sans bilan."""
        def interrupt(signum, _frame):
            raise KeyboardInterrupt(signal.Signals(signum).name)

        # SIGTERM et SIGHUP comme Ctrl+C : les `finally` de la suite (navigateur, serveur propre à
        # la suite) doivent s'exécuter quand le lanceur l'arrête.
        for sig in (signal.SIGTERM, signal.SIGHUP):
            signal.signal(sig, interrupt)
        try:
            with sync_playwright() as p:
                body(p)
        except KeyboardInterrupt:
            self.fail("[suite] interrompue")
        except BaseException as e:
            if isinstance(e, SystemExit):
                raise
            traceback.print_exc()
            self.fail("[suite] exception, la suite s'est arrêtée avant la fin", f"({type(e).__name__}: {str(e)[:200]})")
        self.finish()

    def finish(self):
        print("=" * 50)
        if self.failures:
            print(f"ÉCHECS ({self.suite}) : {len(self.failures)} sur {self.passed + len(self.failures)}")
            for name in self.failures:
                print(f"  - {name}")
            sys.exit(1)
        if self.passed == 0:
            print(f"AUCUN CHECK EXÉCUTÉ ({self.suite}) : une suite vide ne prouve rien.")
            sys.exit(1)
        print(f"TOUT PASSE ({self.suite}) : {self.passed} checks")
        sys.exit(0)


def new_context(browser, ck, settings=None, **options):
    """Contexte surveillé par `ck`, réglages pré-remplis, chess.com simulé (sauf E2E_LIVE=1)."""
    ctx = browser.new_context(**options)
    ck.watch(ctx)
    # Le script s'exécute aussi sur about:blank, dont l'origine opaque interdit localStorage :
    # sans try/catch, chaque contexte commencerait par un faux `pageerror`.
    ctx.add_init_script(
        "try { if (!localStorage.getItem('chess-local-settings')) "
        f"localStorage.setItem('chess-local-settings', {json.dumps(settings_json(settings))}) }} catch {{}}"
    )
    mock_chesscom(ctx, ck)
    return ctx


def mobile_context(p, browser, ck, settings=None, standalone=False, **options):
    """iPhone 14 Pro émulé (DPR 3, tactile, UA iOS).

    standalone=False : 393x660, un onglet Safari (barres du navigateur déduites).
    standalone=True  : 393x852, la PWA installée en plein écran, cible principale de l'app.
    Attention : `env(safe-area-inset-*)` vaut 0 en émulation. Sur un vrai iPhone 14 Pro en
    standalone, 59 px en haut et 34 px en bas réduisent la hauteur utile.
    """
    opts = dict(p.devices["iPhone 14 Pro"])
    if standalone:
        opts["viewport"] = {"width": 393, "height": 852}
    opts.update(options)
    return new_context(browser, ck, settings, **opts)


def desktop_context(browser, ck, settings=None, width=1440, height=900, **options):
    return new_context(browser, ck, settings, viewport={"width": width, "height": height}, **options)


def mock_chesscom(ctx, ck):
    """Simule api.chess.com depuis e2e/fixtures/chesscom.json. Toute URL non prévue est un
    échec : sinon un changement d'appel réseau passerait inaperçu, et le gate dépendrait
    d'internet."""
    if LIVE:
        return
    with open(os.path.join(FIXTURES, "chesscom.json"), encoding="utf-8") as f:
        routes = json.load(f)["routes"]

    def handle(route):
        url = route.request.url.split("?")[0].rstrip("/")
        entry = routes.get(url)
        if entry is None:
            ck.fail("[réseau] appel chess.com non prévu par la fixture", f"({url})")
            route.abort()
            return
        route.fulfill(
            status=entry.get("status", 200),
            content_type="application/json",
            headers={"access-control-allow-origin": "*"},
            body=json.dumps(entry.get("body", {})),
        )

    ctx.route("https://api.chess.com/**", handle)


def shot(page, name, full_page=False):
    os.makedirs(SHOTS, exist_ok=True)
    path = os.path.join(SHOTS, f"{name}.png")
    page.screenshot(path=path, full_page=full_page)
    return path


def click_square(page, square):
    page.locator(f"[data-square='{square}']").click()


def sq_center(page, square):
    """Centre (x, y) en px CSS de la case, quelle que soit l'orientation du board."""
    box = page.locator(f"[data-square='{square}']").first.bounding_box()
    if not box:
        raise RuntimeError(f"case {square} introuvable")
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def tap_square(page, square):
    x, y = sq_center(page, square)
    page.touchscreen.tap(x, y)


def tap_move(page, frm, to, pause=250):
    """Coup en deux taps (pièce puis destination)."""
    tap_square(page, frm)
    page.wait_for_timeout(pause)
    tap_square(page, to)
    page.wait_for_timeout(pause)


def touch_drag(page, x1, y1, x2, y2, steps=14, step_ms=16, hold_ms=60):
    """Drag TACTILE réel via CDP `Input.dispatchTouchEvent`. Il passe par le pipeline de gestes
    du navigateur : un défaut de `touch-action` fait défiler la page comme sur un téléphone,
    ce qu'un drag souris de Playwright ne montre jamais."""
    cdp = page.context.new_cdp_session(page)

    def point(x, y):
        return [{"x": round(x, 1), "y": round(y, 1), "id": 1, "radiusX": 8, "radiusY": 8, "force": 1}]

    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": point(x1, y1)})
    page.wait_for_timeout(hold_ms)
    for i in range(1, steps + 1):
        x = x1 + (x2 - x1) * i / steps
        y = y1 + (y2 - y1) * i / steps
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": point(x, y)})
        page.wait_for_timeout(step_ms)
    page.wait_for_timeout(hold_ms)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()
    page.wait_for_timeout(250)


def drag_piece(page, frm, to, **kw):
    x1, y1 = sq_center(page, frm)
    x2, y2 = sq_center(page, to)
    touch_drag(page, x1, y1, x2, y2, **kw)


def piece_on(page, square):
    """Code pièce ('wP', 'bK', ...) sur la case, ou None (attribut data-piece de react-chessboard)."""
    return page.evaluate(
        """(sq) => {
          const el = document.querySelector(`[data-square='${sq}'] [data-piece]`)
          return el ? el.getAttribute('data-piece') : null
        }""",
        square,
    )


def scroll_state(page):
    """À comparer avant/après un geste. Le conteneur scrollable de l'app est `<main>`, pas la fenêtre."""
    return page.evaluate(
        """() => {
          const m = document.querySelector('main')
          return {
            windowScrollY: Math.round(window.scrollY),
            mainScrollTop: m ? Math.round(m.scrollTop) : null,
            mainScrollable: m ? m.scrollHeight > m.clientHeight : null,
            hash: location.hash,
            historyLength: history.length,
          }
        }"""
    )


def overflow_x(page):
    """Débordement horizontal de la page : doit valoir 0 sur mobile."""
    return page.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
