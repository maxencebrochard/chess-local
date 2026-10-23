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
import http.server
import json
import os
import re
import threading
from contextlib import contextmanager
import signal
import subprocess
import sys
import traceback

from playwright.sync_api import sync_playwright

from run import HOST, SUBPATH

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(E2E_DIR)
FIXTURES = os.path.join(E2E_DIR, "fixtures")
SHOTS = os.environ.get("SHOTS", os.path.join(E2E_DIR, "shots"))
os.makedirs(SHOTS, exist_ok=True)

# E2E_LIVE=1 : l'API chess.com réelle remplace la fixture (jamais dans le gate : réseau = flaky).
LIVE = os.environ.get("E2E_LIVE") == "1"

# Bouton du domaine Finales (et pas la carte « Cours de finales »).
FINALES = re.compile(r"^\W*Finales$")

# Hub d'Apprendre (lot 5 du plan UX) : les séances par domaine se lancent depuis leur groupe
# d'Entraînement (carte `[data-session=<domaine>]`), Mes erreurs depuis Réviser mes parties. La
# séance s'ouvre ensuite sur `#/apprendre`, comme avant : seules ces entrées ont changé.
SESSION_GROUP = {"tactic": "tactique", "endgame": "finales", "opening": "ouvertures", "strategy": "strategie"}


def open_learn_session(page, domain, tap=False):
    """Ouvre le groupe du domaine et lance sa séance (`tap=True` : geste tactile)."""
    page.goto(f"{BASE}/#/apprendre/entrainement/{SESSION_GROUP[domain]}")
    card = page.locator(f"main [data-session={domain}]")
    card.wait_for(state="visible", timeout=20000)
    card.tap() if tap else card.click()


def open_mistakes_session(page):
    """Réviser mes parties, puis Mes erreurs (attend que le compte active la carte)."""
    page.goto(f"{BASE}/#/apprendre/mes-parties")
    page.wait_for_selector("[data-testid=mistakes-card]:not([disabled])", timeout=20000)
    page.locator("[data-testid=mistakes-card]").click()


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
  // Début réel de la diffusion de chaque fin de geste : premier écouteur du chemin (fenêtre, phase de
  // capture, posé avant tout script de l'app). L'écart avec `timeStamp` (création de l'événement)
  // est l'attente dans la file du thread principal, qui dépend de la charge et non du code du geste.
  const dispatchAt = new WeakMap()
  for (const t of ['pointerup', 'mouseup', 'touchend', 'click', 'keydown']) {
    window.addEventListener(t, (e) => { dispatchAt.set(e, performance.now()) }, true)
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
      scheduledMs, event: ev ? ev.type : null, trusted: ev ? ev.isTrusted : null, eventAt: ev ? ev.timeStamp : null,
      dispatchAt: ev ? dispatchAt.get(ev) ?? null : null })
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
    le début de cette diffusion.

    Le critère principal ne dépend pas de la charge : un son repoussé à une tâche ultérieure
    (setTimeout, requestAnimationFrame, fin d'animation) n'a plus d'événement en cours et échoue même
    s'il part 5 ms plus tard. Le budget borne le travail synchrone du geste avant le son (un rendu
    React forcé, un calcul ajouté) : il se compte depuis le premier écouteur de l'événement, pas
    depuis sa création (`timeStamp`), car l'attente dans la file du thread principal avant la
    diffusion ne dépend que de la charge de la machine (117,6 ms relevés sous un gate parallèle, pour
    un travail du geste de quelques ms ; voir docs/f14-feeling.md). Il est en temps CPU de la page :
    multiplié par E2E_CPU_RATE, qui ralentit d'autant ce travail. Une programmation future de 80 ms
    ou plus échoue indépendamment."""
    sounds = [e for e in entries if e["name"] != "(muet)"]
    def timing(e):
        if e.get("eventAt") is None or e.get("dispatchAt") is None:
            return None
        return f"file {e['dispatchAt'] - e['eventAt']:.1f} ms, geste {e['at'] - e['dispatchAt']:.1f} ms"
    detail = f"({fmt_sounds(sounds)}, {[(e.get('event'), e.get('trusted'), timing(e)) for e in sounds]})"
    if len(sounds) != 1:
        return False, detail
    e = sounds[0]
    budget = budget_ms * float(os.environ.get("E2E_CPU_RATE", "1"))
    ok = (e["name"] == name and e["audible"] and e.get("event") in GESTURE_EVENTS and e.get("trusted")
          and e.get("scheduledMs", float("inf")) < 80
          and e.get("dispatchAt") is not None and 0 <= e["at"] - e["dispatchAt"] < budget)
    return ok, detail


# Runtime natif de l'app iOS simulé au plus près du contrat de la native-bridge de Capacitor
# (node_modules/@capacitor/ios/Capacitor/Capacitor/assets/native-bridge.js et JSExport.swift) :
# `webkit.messageHandlers.bridge`, `Capacitor.isNativePlatform`, en-têtes de plugin et
# `nativePromise`, que @capacitor/core appelle pour toute méthode déclarée. Les appels au plugin
# Haptics sont journalisés dans `window.__haptics` au lieu de partir vers Swift.
CAPACITOR_IOS = r"""(() => {
  if (window.__haptics) return
  window.__haptics = []
  window.webkit = { messageHandlers: { bridge: { postMessage() {} } } }
  const methods = ['impact', 'notification', 'vibrate', 'selectionStart', 'selectionChanged', 'selectionEnd']
    .map((name) => ({ name, rtype: 'promise' }))
  window.Capacitor = {
    isNativePlatform: () => true,
    getPlatform: () => 'ios',
    PluginHeaders: [{ name: 'Haptics', methods }],
    nativePromise: (plugin, method, options) => {
      window.__haptics.push({ plugin, method, options: options ?? null, at: performance.now() })
      return Promise.resolve()
    },
    nativeCallback: () => '',
  }
})()"""


def haptic_log(page):
    """Appels haptiques natifs depuis le début de la page, en « méthode:style » (impact:LIGHT,
    notification:ERROR, selectionChanged...). None hors runtime natif simulé."""
    return page.evaluate("""() => window.__haptics ? window.__haptics.map((h) =>
      h.method + (h.options?.style ? ':' + h.options.style : h.options?.type ? ':' + h.options.type : '')) : null""")


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
    un juge des seuils d'évaluation de l'app (`score`, même build et même recherche à nœuds fixes
    qu'elle)."""

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

    def score(self, fen, nodes):
        """Dernier score (cp, mate) d'une recherche à `nodes` nœuds, table de hachage vidée, du point
        de vue du trait, comme `Engine.search({ nodes, newGame: true })` : indépendant de la charge."""
        last = {"cp": None, "mate": None}

        # Même lecture que `parseInfo` de src/lib/engine.ts : dernière ligne `info ... pv`.
        def read(line):
            if not line.startswith("info ") or " pv " not in line or " depth " not in line:
                return
            cp = re.search(r"\bscore cp (-?\d+)", line)
            mate = re.search(r"\bscore mate (-?\d+)", line)
            last.update(cp=int(cp.group(1)) if cp else None, mate=int(mate.group(1)) if mate else None)

        self._send("ucinewgame")
        self._send(f"position fen {fen}")
        self._send(f"go nodes {nodes}")
        self._until("bestmove", read)
        return last

    def close(self):
        try:
            self._send("quit")
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


# ---------------------------------------------------------------------------
# Serveur statique sur un port imposé, sous /chess-local/ comme GitHub Pages : deux builds
# servis l'un après l'autre sur le MÊME port (même origine, donc même service worker et même
# IndexedDB), pour les suites de montée de version (`upgrade`, `perf`).
# ---------------------------------------------------------------------------
class SubpathHandler(http.server.SimpleHTTPRequestHandler):
    """Sert `directory` sous SUBPATH uniquement (comme GitHub Pages), en HTTP/1.0 : pas de
    keep-alive, donc l'arrêt ne laisse aucune connexion pendante entre les deux builds."""

    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".wasm": "application/wasm",
        ".webmanifest": "application/manifest+json",
        ".json": "application/json",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".mp3": "audio/mpeg",
    }

    def translate_path(self, path):
        path = path.split("?", 1)[0].split("#", 1)[0]
        if not path.startswith(SUBPATH):
            return os.path.join(self.directory, "__hors_du_sous_chemin__")
        full = os.path.normpath(os.path.join(self.directory, path[len(SUBPATH):]))
        if not full.startswith(os.path.normpath(self.directory)):
            return os.path.join(self.directory, "__hors_du_dossier__")
        return os.path.join(full, "index.html") if os.path.isdir(full) else full

    def end_headers(self):
        # Aucun cache HTTP : le second build a des fichiers de même chemin (sw.js, engine, sons)
        # et le navigateur ne doit jamais en garder un corps périmé. Le précache du service
        # worker, lui, n'est pas concerné : c'est justement lui qu'on teste.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *_args):
        pass

    def log_error(self, fmt, *args):
        # Journal des seules erreurs (connexion coupée, corps tronqué) : `log_message` muet les
        # avalait aussi, et un « Cache.put() encountered a network error » du précache ne
        # permettait pas de savoir si le serveur avait coupé le corps ou si le client avait abandonné.
        print(f"[serveur {self.directory[-40:]}] {fmt % args}", flush=True)

    # Mutation `truncate-old-precache` : fichier dont le corps est coupé à mi-chemin, comme le
    # « Cache.put() encountered a network error » vu sous charge, mais à chaque fois.
    truncate = None

    def copyfile(self, source, outputfile):
        if self.truncate and self.path.split("?", 1)[0].endswith(self.truncate):
            outputfile.write(source.read(os.fstat(source.fileno()).st_size // 2))
            self.close_connection = True
            return
        super().copyfile(source, outputfile)

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError) as e:
            self.log_error("corps interrompu (%s) pendant %s", type(e).__name__, getattr(self, "path", "?"))
            self.close_connection = True


class StaticServer:
    def __init__(self, directory, port, truncate=None):
        self.directory = directory
        self.port = port
        self.truncate = truncate
        self.srv = None

    @property
    def base(self):
        return f"http://{HOST}:{self.port}{SUBPATH.rstrip('/')}"

    def start(self):
        directory, truncate = self.directory, self.truncate
        # Le port est celui de l'origine du profil (IndexedDB et service worker y sont attachés) :
        # s'il n'est pas disponible, on échoue, on n'en choisit jamais un autre.
        self.srv = http.server.ThreadingHTTPServer((HOST, self.port), lambda *a, **k: type("H", (SubpathHandler,), {"truncate": truncate})(*a, directory=directory, **k))
        self.srv.daemon_threads = True
        self.srv.block_on_close = False  # ne pas attendre un gros fetch en cours (puzzles.json) pour rendre le port
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def stop(self):
        if self.srv is None:
            return
        self.srv.shutdown()
        self.srv.server_close()
        self.srv = None

