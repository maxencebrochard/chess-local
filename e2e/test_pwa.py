"""E2E PWA : le build servi sous un sous-chemin (comme GitHub Pages) s'installe et tourne hors ligne.

Suite « prod uniquement » : sans service worker ni manifest, le serveur de dev ne dit rien de
tout ça. `npm run build` qui passe ne prouve ni les chemins relatifs, ni le précache.

Usage : npm run test:e2e -- --suite pwa
"""
import os
from urllib.parse import urlparse

from helpers import BASE, Checker, mobile_context
from run import Server, port_is_listening

# (route, texte que seule cette page affiche) : la coquille de l'app s'affiche aussi sur une
# route inconnue, donc « la nav est visible » ne prouverait pas que la page a chargé.
ROUTES = [("", "Problèmes"), ("jouer", "Adversaire"), ("puzzles", "Classement puzzles"), ("rush", "Survie"),
          ("apprendre", "Séance"), ("analyse", "Options"), ("archive", "Archive"), ("stats", "Statistiques"),
          ("import", "Importer depuis")]
SUBPATH = urlparse(BASE).path.rstrip("/") + "/"  # "/chess-local/"
PRECACHED = ["engine/stockfish-18-lite-single.wasm", "engine/stockfish-18-lite-single.js", "puzzles.json",
             "sounds/Move.mp3", "index.html"]
# Ligne moteur de l'analyse mobile, par exemple « (+0,32) e4 e5 Cf3 ». Seul Stockfish la produit :
# la barre d'éval, elle, affiche « 0,00 » par défaut, moteur en panne compris.
ENGINE_LINE = "main p:text-matches('^\\\\([+-]?(\\\\d+,\\\\d\\\\d|M\\\\d+)\\\\) \\\\S')"
ck = Checker("pwa")
check = ck.check


def cached_paths(page):
    return page.evaluate(
        """async () => {
          const paths = []
          for (const name of await caches.keys()) for (const req of await (await caches.open(name)).keys()) paths.push(new URL(req.url).pathname)
          return paths
        }"""
    )


def wait_precache(page, subpath):
    """Attend que le service worker soit actif et que les gros assets soient en cache, SOUS le
    sous-chemin. Retourne (service worker, chemins en cache)."""
    sw = page.evaluate(
        """async () => {
          const reg = await Promise.race([navigator.serviceWorker.ready, new Promise((r) => setTimeout(() => r(null), 60000))])
          return reg ? { scope: reg.scope, active: !!reg.active } : null
        }"""
    )
    paths = []
    for _ in range(60):
        paths = cached_paths(page)
        if all(f"{subpath}{n}" in paths for n in PRECACHED):
            break
        page.wait_for_timeout(1000)
    return sw, paths


def online_phase(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()

    # Toute réponse en erreur ou hors du sous-chemin trahit un chemin absolu (`/engine/...`) :
    # invisible en dev et en preview à la racine, fatal sur GitHub Pages.
    bad = []
    origin = f"{urlparse(BASE).scheme}://{urlparse(BASE).netloc}"

    def on_response(res):
        if not res.url.startswith(origin):
            return
        path = urlparse(res.url).path
        if res.status >= 400 or not path.startswith(SUBPATH):
            bad.append(f"{res.status} {path}")

    page.on("response", on_response)

    for route, marker in ROUTES:
        page.goto(f"{BASE}/#/{route}")
        ck.appears(f"[sous-chemin] /#/{route} affiche sa page", page, f"main :text('{marker}')", timeout=15000)
    page.goto(f"{BASE}/#/analyse")
    ck.appears("[sous-chemin] Stockfish analyse (ligne moteur affichée)", page, ENGINE_LINE, timeout=45000)
    check("[sous-chemin] aucune réponse en erreur ni hors du sous-chemin", not bad, f"({bad[:5]})")

    manifest = page.evaluate(
        """async () => {
          const link = document.querySelector('link[rel="manifest"]')
          if (!link) return null
          const res = await fetch(link.href)
          const json = await res.json()
          const icons = await Promise.all(json.icons.map(async (i) => (await fetch(new URL(i.src, link.href))).status))
          return { status: res.status, display: json.display, start_url: json.start_url, scope: json.scope, icons }
        }"""
    )
    check("[manifest] présent et lisible", bool(manifest) and manifest["status"] == 200, f"({manifest})")
    if manifest:
        check("[manifest] display standalone", manifest["display"] == "standalone")
        check("[manifest] start_url et scope relatifs", manifest["start_url"] == "." and manifest["scope"] == ".", f"({manifest['start_url']}, {manifest['scope']})")
        check("[manifest] toutes les icônes se chargent", manifest["icons"] and all(s == 200 for s in manifest["icons"]), f"({manifest['icons']})")

    sw, paths = wait_precache(page, SUBPATH)
    check("[sw] service worker actif", bool(sw) and sw["active"], f"({sw})")
    check("[sw] portée = le sous-chemin", bool(sw) and urlparse(sw["scope"]).path == SUBPATH, f"({sw and sw['scope']})")
    for n in PRECACHED:
        check(f"[sw] précaché sous le sous-chemin : {n}", f"{SUBPATH}{n}" in paths, f"({len(paths)} entrées)")
    ctx.close()


def offline_phase(p, browser):
    """Vrai hors-ligne : la PWA est installée depuis un serveur à nous, puis ce serveur est TUÉ.
    `ctx.set_offline(True)` ne suffit pas : il coupe le réseau de la page mais pas celui du
    service worker, qui retomberait sur le réseau pour toute entrée absente du cache."""
    # own_group=False : ce serveur reste dans le groupe de process de la suite, donc le lanceur
    # l'emporte avec elle s'il doit la tuer. Sinon il survivrait en serveur fantôme.
    own = Server("prod", os.environ["E2E_DIST"], own_group=False)
    own.start()
    try:
        ctx = mobile_context(p, browser, ck, standalone=True)
        page = ctx.new_page()
        page.goto(f"{own.base}/#/")
        sw, paths = wait_precache(page, SUBPATH)
        check("[hors ligne] installation terminée avant coupure", bool(sw) and sw["active"] and all(f"{SUBPATH}{n}" in paths for n in PRECACHED))
        port = own.port
        own.stop(check_port=False)  # le contrôle du port est le check qui suit, pas une exception
        check("[hors ligne] le serveur est réellement arrêté", not port_is_listening(port), f"(port {port})")

        page.reload()
        ck.appears("[hors ligne] l'app redémarre sans serveur", page, "main :text('Problèmes')", timeout=20000)
        page.goto(f"{own.base}/#/puzzles")
        ck.appears("[hors ligne] les 120 000 puzzles se chargent", page, "text=Trouve le meilleur coup", timeout=45000)
        check("[hors ligne] un échiquier de puzzle est affiché", page.locator("[data-square='e4']").count() == 1)
        page.goto(f"{own.base}/#/analyse")
        ck.appears("[hors ligne] Stockfish analyse (ligne moteur affichée)", page, ENGINE_LINE, timeout=45000)
        ctx.close()
    finally:
        own.stop(check_port=False)


def suite(p):
    if not os.environ.get("E2E_DIST"):
        # Suite lancée à la main : seul e2e/run.py sait où se trouve le build de ce lancement.
        ck.fail("[pwa] E2E_DIST absent : lance cette suite par `npm run test:e2e -- --suite pwa`")
        return
    browser = p.chromium.launch(headless=True)
    online_phase(p, browser)
    offline_phase(p, browser)
    browser.close()


ck.run(suite)
