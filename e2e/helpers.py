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
import re
from contextlib import contextmanager
import signal
import subprocess
import sys
import traceback

from playwright.sync_api import sync_playwright

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(E2E_DIR)
FIXTURES = os.path.join(E2E_DIR, "fixtures")
SHOTS = os.environ.get("SHOTS", os.path.join(E2E_DIR, "shots"))
os.makedirs(SHOTS, exist_ok=True)

# E2E_LIVE=1 : l'API chess.com réelle remplace la fixture (jamais dans le gate : réseau = flaky).
LIVE = os.environ.get("E2E_LIVE") == "1"

# Bouton du domaine Finales (et pas la carte « Cours de finales »).
FINALES = re.compile(r"^\W*Finales$")

DEFAULT_SETTINGS = {
    "themeId": "green",
    "pieceSet": "atelier",
    "showLegalMoves": True,
    "premoves": True,
    "showAttackers": False,
    "playSounds": False,
    "soundVolume": 1,
    "chesscomUsername": "",
    "reviewDepth": "fast",
    "playMode": "bot",
    "playBotId": "nina",
    "playColor": "w",
    "playTcLabel": "10 min",
}


# Rend déterministes les courses avec une recherche moteur (abandon pendant la réflexion du bot,
# vérification de Réessayer abandonnée) : tant que `__heldUci` est un tableau, les `bestmove` des
# workers Stockfish sont retenus au lieu d'être livrés à l'app (écouteur posé dans le constructeur,
# donc avant `onmessage`). `__releaseUci()` les livre ensuite tels quels : la réponse du moteur
# arrive alors réellement après l'action de la suite (fin de partie, Quitter), et le moteur peut se
# libérer. À poser en init script, et à armer (`__heldUci = []`) juste avant la recherche visée.
HOLD_BESTMOVE = """(() => {
  const Native = window.Worker
  window.__heldUci = null
  window.Worker = class extends Native {
    constructor(...args) {
      super(...args)
      this.addEventListener('message', (e) => {
        if (window.__heldUci && typeof e.data === 'string' && e.data.startsWith('bestmove')) {
          e.stopImmediatePropagation()
          window.__heldUci.push([this, e.data])
        }
      })
    }
  }
  window.__releaseUci = () => {
    const held = window.__heldUci ?? []
    window.__heldUci = null
    for (const [w, data] of held) w.dispatchEvent(new MessageEvent('message', { data }))
    return held.length
  }
})()"""


# Espion Web Audio, à poser en init script dans un contexte dont les sons sont allumés. Chromium
# headless joue l'audio sans geste ; iOS non. Le script émule donc la politique de WebKit sur
# `AudioContext` :
# - un contexte créé hors geste naît `suspended`, `resume()` n'aboutit que pendant un geste (fin
#   de toucher : touchend ou pointerup, click, keydown ; pas pointerdown ni touchstart, comme iOS) ;
# - `__background(mode)` simule un passage en arrière-plan (visibilitychange hidden puis visible) :
#   `interrupted` met les contextes dans cet état sans retour possible, `zombie` les laisse
#   `running` mais muets (les deux cas observés sur iPhone).
# Chaque `AudioBufferSourceNode.start()` est journalisé dans `window.__sounds` avec le fichier joué
# (suivi fetch -> ArrayBuffer -> AudioBuffer) et s'il est AUDIBLE : contexte `running` et pas
# zombie. Un `start()` sur un contexte suspendu ou interrompu est exactement le « pas de son » de
# la PWA : il ne compte pas. `window.__gain` garde le dernier volume posé.
WEBKIT_AUDIO = r"""(() => {
  const Native = window.AudioContext
  if (!Native || window.__sounds) return
  window.__sounds = []
  let inGesture = false
  for (const t of ['touchend', 'pointerup', 'click', 'keydown']) {
    window.addEventListener(t, (e) => {
      if (!e.isTrusted) return
      inGesture = true
      setTimeout(() => { inGesture = false }, 0)
    }, true)
  }
  const emu = new WeakMap()
  const zombies = new WeakSet()
  const all = []
  window.__audioRunning = () => all.some((c) => emu.get(c) === 'running' && !zombies.has(c))
  class WebKitLike extends Native {
    constructor(...a) {
      super(...a)
      emu.set(this, inGesture ? 'running' : 'suspended')
      all.push(this)
    }
    get state() { return emu.get(this) ?? super.state }
    resume() {
      if (emu.get(this) === 'suspended' && inGesture) emu.set(this, 'running')
      return super.resume().catch(() => {})
    }
    suspend() {
      if (emu.get(this) === 'running') emu.set(this, 'suspended')
      return super.suspend()
    }
    close() {
      emu.set(this, 'closed')
      return super.close()
    }
  }
  window.AudioContext = WebKitLike
  let vis = 'visible'
  Object.defineProperty(document, 'visibilityState', { get: () => vis, configurable: true })
  Object.defineProperty(document, 'hidden', { get: () => vis === 'hidden', configurable: true })
  window.__background = (mode) => {
    vis = 'hidden'
    document.dispatchEvent(new Event('visibilitychange'))
    for (const c of all) {
      if (emu.get(c) === 'closed') continue
      if (mode === 'zombie') zombies.add(c)
      else emu.set(c, 'interrupted')
    }
    vis = 'visible'
    document.dispatchEvent(new Event('visibilitychange'))
  }
  // Fichier d'origine de chaque AudioBuffer.
  const abUrl = new WeakMap()
  window.__decoded = new Set()
  const bufUrl = new WeakMap()
  const origAb = Response.prototype.arrayBuffer
  Response.prototype.arrayBuffer = async function () {
    const ab = await origAb.call(this)
    abUrl.set(ab, this.url)
    return ab
  }
  const origDecode = BaseAudioContext.prototype.decodeAudioData
  BaseAudioContext.prototype.decodeAudioData = function (ab, ...rest) {
    const url = abUrl.get(ab)
    const p = origDecode.call(this, ab, ...rest)
    if (p && p.then) p.then((buf) => { if (url) { bufUrl.set(buf, url); window.__decoded.add(url.split('/').pop()) } }, () => {})
    return p
  }
  // Volume : dernière valeur posée sur un gain.
  window.__gain = null
  const origSet = AudioParam.prototype.setValueAtTime
  AudioParam.prototype.setValueAtTime = function (v, ...rest) {
    window.__gain = v
    return origSet.call(this, v, ...rest)
  }
  const origStart = AudioBufferSourceNode.prototype.start
  AudioBufferSourceNode.prototype.start = function (...a) {
    const url = this.buffer ? bufUrl.get(this.buffer) : undefined
    const name = url ? url.split('/').pop().replace(/\.mp3.*$/, '') : '(muet)'
    const st = this.context.state
    const scheduledMs = Math.max(0, (a[0] ?? this.context.currentTime) - this.context.currentTime) * 1000
    const at = performance.now() + scheduledMs
    // Événement en cours de diffusion (microtâches comprises) : null si le son part d'une tâche
    // ultérieure (setTimeout, requestAnimationFrame, fin d'animation, réponse réseau).
    const ev = window.event
    window.__sounds.push({ name, at, state: st, audible: st === 'running' && !zombies.has(this.context),
      scheduledMs, event: ev ? ev.type : null, trusted: ev ? ev.isTrusted : null, eventAt: ev ? ev.timeStamp : null })
    return origStart.apply(this, a)
  }
})()"""


# Fichiers de public/sounds : `sounds.ts` les précharge tous au démarrage, sans attendre de geste.
SOUND_FILES = sorted(f for f in os.listdir(os.path.join(os.path.dirname(E2E_DIR), "public", "sounds")) if f.endswith(".mp3"))

# Fin d'un geste pour iOS et l'espion : un son « immédiat » part pendant leur diffusion.
GESTURE_EVENTS = ("pointerup", "mouseup", "touchend", "click", "keydown")


def wait_sounds_ready(page, timeout=15000):
    """Attend que l'espion `WEBKIT_AUDIO` ait vu décoder tous les sons et qu'un contexte tourne.
    Avant, un son demandé attend son fetch et son décodage : il part en retard sans régression.
    Remplace une attente fixe, trop courte sous charge et trop longue sinon."""
    try:
        page.wait_for_function(
            "(n) => window.__decoded && window.__decoded.size >= n && window.__audioRunning()",
            arg=len(SOUND_FILES), timeout=timeout, polling=50)
        return True
    except Exception:
        return False


def immediate_sound(entries, name, budget_ms=250):
    """(ok, détail) : un seul son, `name`, audible, démarré PENDANT la diffusion de l'événement de
    fin de geste qui joue le coup (même tâche, microtâches comprises), et au plus `budget_ms` après
    l'horodatage navigateur de cet événement.

    Le critère principal ne dépend pas de la charge : un son repoussé à une tâche ultérieure
    (setTimeout, requestAnimationFrame, fin d'animation) n'a plus d'événement en cours et échoue même
    s'il part 5 ms plus tard. Le budget en temps n'est qu'un filet contre un long travail synchrone
    ajouté avant le son, assez large pour le travail légitime d'une machine chargée.
    Une programmation future de 80 ms ou plus échoue indépendamment de ce budget."""
    sounds = [e for e in entries if e["name"] != "(muet)"]
    detail = f"({fmt_sounds(sounds)}, {[(e.get('event'), e.get('trusted'), None if e.get('eventAt') is None else round(e['at'] - e['eventAt'], 1)) for e in sounds]})"
    if len(sounds) != 1:
        return False, detail
    e = sounds[0]
    ok = (e["name"] == name and e["audible"] and e.get("event") in GESTURE_EVENTS and e.get("trusted")
          and e.get("scheduledMs", float("inf")) < 80
          and e.get("eventAt") is not None and 0 <= e["at"] - e["eventAt"] < budget_ms)
    return ok, detail


def sound_log(page):
    """Entrées de l'espion `WEBKIT_AUDIO` ({name, state, audible}), dans l'ordre des `start()`."""
    return page.evaluate("() => window.__sounds ?? []")


def sounds_heard(page, start, settle=400):
    """Sons joués depuis l'index `start`, sans le tampon muet de déverrouillage."""
    page.wait_for_timeout(settle)
    return [e for e in sound_log(page)[start:] if e["name"] != "(muet)"]


def fmt_sounds(entries):
    return "[" + ", ".join(f"{e['name']}{'' if e['audible'] else ' (MUET:' + e['state'] + ')'}" for e in entries) + "]"


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
    return json.dumps({"state": {**DEFAULT_SETTINGS, **(overrides or {})}, "version": 2})


class Checker:
    """Bilan d'une suite. Tout ce qui est anormal est un échec : check faux, exception non
    rattrapée de la page (`pageerror`), requête chess.com non prévue, exception de la suite."""

    def __init__(self, suite):
        self.suite = suite
        self.passed = 0
        self.failures = []
        self._expected = []  # attentes actives de `expect_pageerror` (pile)

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

    def appears(self, name, page, selector, timeout=30000, state="visible"):
        """Check « l'élément finit par apparaître » : un échec propre plutôt qu'une exception
        qui interrompt la suite. `state="attached"` se contente de la présence dans le DOM."""
        try:
            page.wait_for_selector(selector, timeout=timeout, state=state)
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
        page.on("pageerror", self._on_pageerror)
        # Charge reproductible, opt-in : ralentir le rendu sans rallonger les assertions.
        rate = float(os.environ.get("E2E_CPU_RATE", "1"))
        if rate != 1:
            page.context.new_cdp_session(page).send("Emulation.setCPUThrottlingRate", {"rate": rate})
            print(f"[charge] CPU ralenti x{rate:g}", flush=True)

    def _on_pageerror(self, e):
        msg = str(e)
        for exp in reversed(self._expected):
            if any(p in msg for p in exp["patterns"]):
                exp["seen"].append(msg)
                # Simple trace : le check est celui de la sortie du bloc (« survenu »), qui peut échouer.
                print(f"[info] pageerror attendu ({msg[:120]})", flush=True)
                return
        self.fail("[pageerror] exception non rattrapée dans la page", f"({msg[:300]})")

    @contextmanager
    def expect_pageerror(self, pattern):
        """Pendant le bloc, un `pageerror` dont le message contient `pattern` (ou l'une des chaînes
        d'un tuple : un message React diffère entre dev et prod minifiée) est attendu (crash
        provoqué par la suite) ; à la sortie, échec si aucun n'est survenu. Hors bloc, rien ne
        change : tout `pageerror` reste un échec."""
        patterns = (pattern,) if isinstance(pattern, str) else tuple(pattern)
        pattern = " | ".join(patterns)
        exp = {"patterns": patterns, "seen": []}
        self._expected.append(exp)
        try:
            yield exp
        finally:
            self._expected.remove(exp)
            seen = len(exp["seen"]) >= 1
            self.check(f"[pageerror attendu] {pattern} survenu", seen, "" if seen else "(aucun pageerror correspondant)")

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


def wait_js(page, expr, timeout=30000, arg=None):
    """Vrai dès que l'expression JS est vraie, faux après `timeout` ms : remplace un délai fixe
    suivi d'un constat (trop court sous charge, trop long sinon). Le check reste à l'appelant."""
    try:
        page.wait_for_function(expr, arg=arg, timeout=timeout, polling=100)
        return True
    except Exception:
        return False


PLIES_AT_LEAST = "(n) => document.querySelectorAll('main [data-current]').length >= n"


# Alerte « Qu'est-ce qu'il menace ? » (src/lib/threat.ts), hors réglages Zustand : coupée par
# défaut dans les contextes de test, sinon une question imprévue (l'entraîneur l'active par défaut)
# bloquerait les coups des suites de Jouer. `threat_prefs=None` garde le défaut de l'app.
THREAT_PREFS_KEY = "chess-local-threat-check"
THREAT_OFF = {"bot": False, "coach": False}


def new_context(browser, ck, settings=None, threat_prefs=THREAT_OFF, **options):
    """Contexte surveillé par `ck`, réglages pré-remplis, chess.com simulé (sauf E2E_LIVE=1)."""
    ctx = browser.new_context(**options)
    ck.watch(ctx)
    # Le script s'exécute aussi sur about:blank, dont l'origine opaque interdit localStorage :
    # sans try/catch, chaque contexte commencerait par un faux `pageerror`.
    ctx.add_init_script(
        "try { if (!localStorage.getItem('chess-local-settings')) "
        f"localStorage.setItem('chess-local-settings', {json.dumps(settings_json(settings))}) }} catch {{}}"
    )
    if threat_prefs is not None:
        # Une fois par onglet (marqueur de session) : une réinitialisation suivie d'un rechargement
        # doit pouvoir constater la clé effacée.
        ctx.add_init_script(
            "try { if (!sessionStorage.getItem('e2e-threat-seeded')) { sessionStorage.setItem('e2e-threat-seeded', '1'); "
            f"if (!localStorage.getItem('{THREAT_PREFS_KEY}')) localStorage.setItem('{THREAT_PREFS_KEY}', {json.dumps(json.dumps(threat_prefs))}) }} }} catch {{}}"
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
    target = page.locator(f"[data-square='{square}']").first
    # Un changement de puzzle peut remplacer le DOM avant sa première mise en page.
    # Attendre les mêmes garanties qu'un vrai tap avant de figer les coordonnées du drag.
    target.tap(trial=True)
    box = target.bounding_box()
    if not box:
        raise RuntimeError(f"case {square} introuvable")
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def tap_square(page, square):
    # Le locator attend une case visible et stable et se résout à nouveau si React la remplace.
    page.locator(f"[data-square='{square}']").first.tap()


def tap_move(page, frm, to, pause=250):
    """Coup en deux taps (pièce puis destination)."""
    tap_square(page, frm)
    page.wait_for_timeout(pause)
    tap_square(page, to)
    page.wait_for_timeout(pause)


def touch_drag(page, x1, y1, x2, y2, steps=14, step_ms=16, hold_ms=60, during=None, on_step=None, after_release=None):
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
        if on_step:
            on_step(i, x, y)
    page.wait_for_timeout(hold_ms)
    if during:
        during(x2, y2)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    if after_release:
        after_release()
    cdp.detach()
    page.wait_for_timeout(250)


def drag_piece(page, frm, to, start=None, **kw):
    """Saisie au centre, ou en un point précis de la pièce (bords, coordonnées)."""
    x1, y1 = start if start is not None else sq_center(page, frm)
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
    """Débordement horizontal de body, des calques fixes et des scrollers verticaux.
    Les bandes volontairement défilables horizontalement sont exclues.
    html seul ne mesure plus le contenu lorsque body est fixé.
    """
    return page.evaluate(
        """() => {
          const over = (e) => e.scrollWidth - e.clientWidth
          let max = over(document.body)
          for (const e of document.querySelectorAll('body *')) {
            const cs = getComputedStyle(e)
            if (e.classList.contains('overflow-x-auto')) continue
            if (cs.position === 'fixed' || ['auto', 'scroll'].includes(cs.overflowY)) {
              max = Math.max(max, over(e))
            }
          }
          return max
        }"""
    )


class Solver:
    """Le Stockfish du repo (node_modules, build lite mono-thread, celui de l'app) lancé sous
    Node, en UCI : un joueur simulé qui joue vraiment, quelle que soit la défense de l'app, et
    un juge des seuils d'évaluation de l'app (`score`, même build et même `movetime` qu'elle)."""

    def __init__(self):
        self.proc = subprocess.Popen(
            ["node", "node_modules/stockfish/bin/stockfish-18-lite-single.js"],
            cwd=ROOT_DIR, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        self._send("uci")
        self._until("uciok")

    def _send(self, cmd):
        self.proc.stdin.write(cmd + "\n")
        self.proc.stdin.flush()

    def _until(self, prefix, on_line=None):
        while True:
            line = self.proc.stdout.readline()
            if not line:
                raise RuntimeError("Stockfish (Node) s'est arrêté")
            if on_line:
                on_line(line)
            if line.startswith(prefix):
                return line.strip()

    def best(self, fen, depth=14):
        self._send(f"position fen {fen}")
        self._send(f"go depth {depth}")
        return self._until("bestmove").split()[1]

    def score(self, fen, movetime=150):
        """Dernier score (cp, mate) de la recherche, du point de vue du trait, comme `Engine.search`."""
        last = {"cp": None, "mate": None}

        # Même lecture que `parseInfo` de src/lib/engine.ts : dernière ligne `info ... pv`.
        def read(line):
            if not line.startswith("info ") or " pv " not in line or " depth " not in line:
                return
            cp = re.search(r"\bscore cp (-?\d+)", line)
            mate = re.search(r"\bscore mate (-?\d+)", line)
            last.update(cp=int(cp.group(1)) if cp else None, mate=int(mate.group(1)) if mate else None)

        self._send(f"position fen {fen}")
        self._send(f"go movetime {movetime}")
        self._until("bestmove", read)
        return last

    def close(self):
        try:
            self._send("quit")
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()
