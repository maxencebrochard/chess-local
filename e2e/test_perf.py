"""E2E performance : budgets chiffrés du build de prod sur iPhone, CPU ralenti 4x.

Suite « prod uniquement » (comme `pwa`) : les tailles se lisent dans le build du lancement
(`E2E_DIST`), et des temps mesurés sur le serveur de dev (modules non groupés, transformés à la
volée) ne diraient rien de la PWA installée.

Ce qui est mesuré, et pourquoi :
- JS initial (script d'entrée + `modulepreload` d'`index.html`), brut et gzip : ce que l'iPhone
  télécharge, parse et exécute avant le premier affichage.
- précache : chaque fichier du build (hors service worker lui-même et couche native `assets/native-*`
  de l'app iOS) figure dans le manifeste de `sw.js`. Avec des routes paresseuses, une chunk oubliée (nouvelle extension hors `globPatterns`,
  fichier au-delà du plafond de 25 Mo que Workbox écarte en silence) ne casse que hors ligne,
  sur une seule page.
- accueil, à froid (service worker bloqué, latence 4G émulée : la cascade de chunks se paie en
  allers-retours) et à chaud (servi par le service worker, cas réel d'une PWA installée) : temps
  jusqu'au premier contenu (`main h1`), jusqu'à l'accueil complet (`[data-review-ready]`, compteur
  de révision compris), puis TTI = fin de la dernière long task avant 1 s de calme. Médiane de 3.
- Puzzles (à chaud, vrai chargement de document) : temps jusqu'au premier puzzle, qui comprend
  les 16 Mo de puzzles.json, et plus longue long task (parsing).
- mémoire : tas JS (CDP `Runtime.getHeapUsage`, après un GC) après l'accueil, Puzzles, Analyse.
- Analyse : long tasks pendant cinq glissés tactiles, analyse live en cours, puis pendant 5 s
  d'analyse live.
- montée de version : un build A installé, un build B (chunks renommées) déployé à sa place ; la
  page encore ouverte sur A ouvre une route jamais chargée : l'app recharge sur B, sans erreur.
- chunk introuvable (sans service worker) : un rechargement puis la page, ou, si elle reste
  introuvable, un seul rechargement puis l'écran de secours.

Bruit : le CPU ralenti est vérifié dans chaque page mesurée (boucle de calibration), et les budgets
de temps sont multipliés par la charge de la machine (boucle libre comparée à sa valeur de
référence sur un Mac au repos), sans jamais descendre sous le budget nominal. Les budgets d'octets
et de précache, déterministes, n'ont aucune marge de ce type.
Les temps viennent de V8 sur Mac : ils comparent des versions entre elles, ils ne prédisent pas
JavaScriptCore sur iPhone.
Le détail des mesures va dans `e2e/shots/perf-metrics.json` (ou `PERF_OUT`).

Usage : npm run test:e2e -- --suite perf
"""
import glob
import gzip
import hashlib
import json
import os
import re
import shutil
import statistics
import tempfile

from helpers import BASE, SHOTS, Checker, StaticServer, drag_piece, mobile_context, piece_on
from run import free_port

THROTTLE = 4  # CPU ralenti 4x : ordre de grandeur d'un iPhone milieu de gamme face à un Mac M
RUNS = 3
FREE_SPIN_REF_MS = 25  # boucle de calibration non ralentie, Mac au repos (voir `calibrate`)
# Latence 4G des mesures à froid (CDP Network.emulateNetworkConditions), sans plafond de débit :
# le serveur local ne compresse pas, un débit plafonné ferait payer 4 fois trop d'octets.
NET_4G = {"offline": False, "latency": 150, "downloadThroughput": -1, "uploadThroughput": -1}

# Budgets, mesurés le 16 octobre 2026 (Mac M, machine chargée par d'autres suites) : environ 1,5x la
# mesure après découpage pour les temps, 15 à 20 % de marge pour les octets. Les budgets d'octets
# échouent sur le build d'avant découpage ou dès qu'une page lourde revient dans l'accueil ; ceux de
# temps attrapent une régression franche (un parsing ou un rendu bloquant de plus).
#   JS initial : 378 Ko gzip avant, 110 après.     JS de l'accueil : 1 540 Ko avant, 899 après.
#   Accueil à froid : 681 ms avant, 925 après (compteur de révision chargé après le premier
#   affichage : contenu 635 -> 522 ms).             Accueil à chaud : 411 ms avant, 333 après.
#   Premier puzzle : 853 ms avant, 1 088 après (page paresseuse). Glissé : aucune long task.
# Remesuré le 23 octobre 2026, après rebase sur toutes les features (parcours, séance, défense...) :
#   JS initial : 468 Ko gzip avant, 117 après.     JS de l'accueil : 1 905 Ko avant, 987,5 après
#   (compteur de révision et progression du parcours en deux imports après le premier affichage ;
#   la progression ne charge plus les cours : computePath ne lit que learningPath.json, et
#   check-learning-path.mjs résout chaque leçon d'étape dans son cours avec lessonRef).
#   Accueil à froid : complet 707 ms avant, 1 050 à 1 100 après (médianes ; contenu 658 -> 665 ms).
#   L'écart est la cascade du compteur de révision : sa chunk et ses dépendances (kingAttack avec
#   openings.json, 541 Ko, openingTrainer, chess.js...) ne partent qu'au montage de l'accueil, vers
#   530 ms, puis coûtent au moins un aller-retour de 150 ms et leur évaluation. Revenir à 707 ms
#   demanderait de les précharger dans index.html, donc de les compter dans le JS initial
#   (budget de 130 Ko gzip, contre 117 aujourd'hui) : le gain du découpage serait perdu.
#   Le TTI vaut au moins l'accueil complet : son budget borne aussi ce dernier.
#   Accueil à chaud : complet 416 ms avant, 365 à 403 après (contenu 380 -> 203 à 244 ms).
#   Premier puzzle : 1 030 ms avant, 964 après ; tas de la page Puzzles 55,8 -> 28,9 Mo.
BUDGET = {
    "initial_js_gzip_kb": 130,
    "home_js_kb": 1050,
    "home_cold_tti_ms": 1400,
    "home_warm_tti_ms": 600,
    "puzzles_warm_ready_ms": 1500,
    "drag_max_longtask_ms": 100,
}

# Pages de l'app ouvertes directement, chacune avec un sélecteur que seule elle affiche.
ROUTES = [
    ("", "[data-review-ready]"), ("jouer", "main :text('Adversaire')"), ("puzzles", "text=Trouve le meilleur coup"),
    ("rush", "main :text('Survie')"), ("apprendre", "main :text('Séance')"),
    ("ouvertures", "main :text(\"Entraîneur d'ouvertures\")"), ("apprendre/finales", "main :text('Cours de finales')"),
    ("apprendre/roque", "main :text('Démolir le roque')"), ("mats", "main :text('Mats éclair')"),
    ("revision", "main h1"), ("attaques-manquees", "main :text('Mes attaques manquées')"),
    ("analyse", "main :text('Options')"), ("analyse/jouer", "main :text('Aucune position à jouer')"),
    ("finales", "main :text(\"Finales jusqu'au bout\")"), ("attaque", "main :text(\"Entraîneur d'attaque\")"),
    ("archive", "main :text('Archive')"), ("stats", "main :text('Statistiques')"), ("insights", "main :text('Insights')"),
    ("reglages", "main :text('Profondeur du bilan de partie')"), ("donnees", "main :text('Dernier export')"),
    ("import", "main :text('Importer depuis')"), ("repertoire", "main :text('Mon répertoire')"),
    ("apprendre/bases", "main :text('Les bases')"), ("apprendre/parcours", "main :text(\"Parcours d'apprentissage\")"),
    ("apprendre/structures", "main :text('Structures de pions')"), ("structures", "main :text('Mes structures de pions')"),
    ("apprendre/defense", "main :text(\"Tenir sous l'attaque\")"), ("defenses-ratees", "main :text('Mes défenses ratées')"),
    ("moment-critique", "main :text('Aucun moment critique')"), ("finales/chrono", "main :text('Finales au chrono')"),
    ("defense", "main :text('Entraîneur de défense')"), ("visualisation", "main :text('Calcul et visualisation')"),
    ("convertir", "main :text(\"Convertir l'avantage\")"), ("seance", "main :text('Séance du jour')"),
]
# Score d'une ligne moteur de l'analyse mobile : seul Stockfish le produit.
ENGINE_LINE = "main [data-engine-line]:visible [data-engine-score]:text-matches('^[+-]?(\\\\d+,\\\\d\\\\d|M\\\\d+)$')"
DRAGS = [("e2", "e4", "wP"), ("e7", "e5", "bP"), ("g1", "f3", "wN"), ("b8", "c6", "bN"), ("f1", "c4", "wB")]

# Long tasks, posées avant tout script de la page. Tampon des ressources agrandi : au-delà de
# 250 entrées (pièces, sons), le compte des scripts serait faux sans le dire.
OBSERVE = """(() => {
  window.__lt = []
  try { performance.setResourceTimingBufferSize(5000) } catch {}
  try {
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) window.__lt.push([e.startTime, e.duration])
    }).observe({ type: 'longtask', buffered: true })
  } catch {}
})()"""
SPIN = "() => { const t = performance.now(); let x = 0; for (let i = 0; i < 3e7; i++) x += i % 7; return performance.now() - t + (x < 0) }"

ck = Checker("perf")
check = ck.check
metrics = {}
calib = {"free_ms": None, "load": 1.0}


def kb(n):
    return round(n / 1024, 1)


def gz(data):
    return len(gzip.compress(data, 9))


def budget(name):
    """Budget de temps ajusté à la charge de la machine (jamais sous le budget nominal)."""
    return round(BUDGET[name] * calib["load"])


# --- Build ------------------------------------------------------------------------------------


def initial_assets(dist):
    """Script d'entrée et modulepreload d'index.html : ce qui part avant le premier rendu."""
    html = open(os.path.join(dist, "index.html"), encoding="utf-8").read()
    js = re.findall(r'<script[^>]+type="module"[^>]+src="\./([^"]+)"', html)
    js += re.findall(r'<link[^>]+rel="modulepreload"[^>]+href="\./([^"]+)"', html)
    return js


def precache_manifest(dist):
    return set(re.findall(r'url:"([^"]+)"', open(os.path.join(dist, "sw.js"), encoding="utf-8").read()))


def build_checks(dist):
    js = initial_assets(dist)
    check("[build] index.html référence un script d'entrée", bool(js), f"({js})")
    raw = sum(os.path.getsize(os.path.join(dist, f)) for f in js)
    zipped = sum(gz(open(os.path.join(dist, f), "rb").read()) for f in js)
    chunks = sorted(glob.glob(os.path.join(dist, "assets", "*.js")))
    total_js = sum(os.path.getsize(f) for f in chunks)
    largest = max(chunks, key=os.path.getsize) if chunks else ""
    metrics["build"] = {
        "initial_js_files": js, "initial_js_kb": kb(raw), "initial_js_gzip_kb": kb(zipped),
        "chunks": len(chunks), "all_js_kb": kb(total_js), "all_js_gzip_kb": kb(sum(gz(open(f, "rb").read()) for f in chunks)),
        "largest_chunk": os.path.basename(largest), "largest_chunk_kb": kb(os.path.getsize(largest)) if largest else 0,
    }
    print(f"[mesure] JS initial {kb(raw)} Ko ({kb(zipped)} Ko gzip) en {len(js)} fichier(s) ; {len(chunks)} chunks, {kb(total_js)} Ko de JS au total", flush=True)
    check(f"[budget] JS initial <= {BUDGET['initial_js_gzip_kb']} Ko gzip", kb(zipped) <= BUDGET["initial_js_gzip_kb"], f"({kb(zipped)} Ko)")

    # Précache : tout fichier du build, sauf le service worker et son runtime, doit être dans le
    # manifeste. Liste d'exclusions explicite plutôt qu'une copie de globPatterns : une nouvelle
    # extension oubliée dans vite.config.ts doit faire échouer ce check.
    manifest = precache_manifest(dist)
    check("[précache] manifeste lisible dans sw.js", len(manifest) > 20, f"({len(manifest)} entrées)")
    missing = []
    for path in glob.glob(os.path.join(dist, "**", "*"), recursive=True):
        rel = os.path.relpath(path, dist)
        name = os.path.basename(rel)
        # Textes de licence (.txt, .md) : documentation du dépôt public, jamais lue par l'app.
        # `assets/native-*` : couche native de l'app iOS (@capacitor/*, pilote haptique), exclue du
        # précache par `globIgnores` de vite.config.ts, que la PWA ne télécharge jamais (suite `ios_app`).
        native = rel.startswith(os.path.join("assets", "native-"))
        if os.path.isdir(path) or native or name == "sw.js" or name.startswith("workbox-") or name.endswith((".txt", ".md")):
            continue
        if rel not in manifest:
            missing.append(rel)
    check("[précache] chaque fichier du build (chunks paresseuses comprises) est précaché", not missing, f"({missing[:6]})")


# --- Navigateur -------------------------------------------------------------------------------


def calibrate(p, browser):
    """Charge de la machine (boucle libre) et ralentissement réel (même boucle sous x4)."""
    ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
    page = ctx.new_page()
    page.goto(f"{BASE}/#/import")
    page.wait_for_timeout(1000)
    free = statistics.median(page.evaluate(SPIN) for _ in range(5))
    calib["free_ms"] = free
    calib["load"] = max(1.0, free / FREE_SPIN_REF_MS)
    metrics["calibration"] = {"free_spin_ms": round(free, 1), "load": round(calib["load"], 2)}
    print(f"[mesure] boucle de calibration libre : {free:.1f} ms (référence {FREE_SPIN_REF_MS} ms) : budgets de temps x{calib['load']:.2f}", flush=True)
    ctx.close()


def throttled(ctx, init=None):
    page = ctx.new_page()
    if init:
        page.add_init_script(init)
    cdp = ctx.new_cdp_session(page)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": THROTTLE})
    return page, cdp


def check_throttled(page, label):
    """Le ralentissement doit avoir survécu à la navigation de la page mesurée."""
    ratio = page.evaluate(SPIN) / max(calib["free_ms"], 0.1)
    check(f"[méthode] {label} : CPU réellement ralenti (x{THROTTLE} demandé)", ratio > THROTTLE * 0.6, f"(x{ratio:.1f})")


def ready_at(page, selector, timeout=60000):
    """`performance.now()` (depuis le début de la navigation) au premier frame où `selector` est visible."""
    try:
        h = page.wait_for_function(
            """(sel) => {
              const el = document.querySelector(sel)
              return el && el.getClientRects().length ? performance.now() : 0
            }""",
            arg=selector, polling="raf", timeout=timeout,
        )
        return round(h.json_value())
    except Exception as e:
        ck.fail(f"[mesure] {selector} n'apparaît pas", f"({type(e).__name__})")
        return None


def text_ready_at(page, text, timeout=60000):
    try:
        h = page.wait_for_function(
            "(t) => document.querySelector('main')?.innerText.includes(t) ? performance.now() : 0",
            arg=text, polling="raf", timeout=timeout,
        )
        return round(h.json_value())
    except Exception as e:
        ck.fail(f"[mesure] « {text} » n'apparaît pas", f"({type(e).__name__})")
        return None


def long_tasks(page, since=0):
    return [(s, d) for s, d in page.evaluate("() => window.__lt ?? []") if s + d >= since]


def longest(tasks):
    return round(max([d for _, d in tasks] or [0]))


def tti(page, ready, quiet_ms=1000, cap_ms=30000):
    """Fin de la dernière long task avant `quiet_ms` de calme après `ready` (TTI à la Lighthouse,
    fenêtre réduite)."""
    while True:
        now = page.evaluate("() => performance.now()")
        last = max([ready] + [s + d for s, d in long_tasks(page)])
        if now - last >= quiet_ms or now > cap_ms:
            return round(last)
        page.wait_for_timeout(200)


def script_kb(page):
    return kb(page.evaluate(
        """() => performance.getEntriesByType('resource')
          .filter((e) => new URL(e.name).pathname.endsWith('.js'))
          .reduce((n, e) => n + e.decodedBodySize, 0)"""
    ))


def heap_mb(cdp):
    cdp.send("HeapProfiler.collectGarbage")
    return round(cdp.send("Runtime.getHeapUsage")["usedSize"] / 1e6, 1)


def median_of(runs, keys):
    return {k: statistics.median(r[k] for r in runs) for k in keys}


def measure_home(page, cdp):
    page.goto(f"{BASE}/#/", wait_until="commit")
    first = ready_at(page, "main h1")
    ready = ready_at(page, "[data-review-ready]")
    if first is None or ready is None:
        return None
    return {"first": first, "ready": ready, "tti": tti(page, ready), "js_kb": script_kb(page), "heap_mb": heap_mb(cdp),
            "longest_task": longest(long_tasks(page))}


def home_cold(p, browser):
    runs = []
    for i in range(RUNS):
        ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
        ctx.add_init_script(OBSERVE)
        page, cdp = throttled(ctx)
        cdp.send("Network.enable")
        cdp.send("Network.emulateNetworkConditions", NET_4G)
        r = measure_home(page, cdp)
        if r is None:
            ctx.close()
            return
        if i == 0:
            check_throttled(page, "accueil à froid")
        runs.append(r)
        ctx.close()
    m = median_of(runs, runs[0].keys())
    metrics["home_cold"] = {**m, "runs": runs}
    print(f"[mesure] accueil à froid (latence 4G) : contenu {m['first']} ms, complet {m['ready']} ms, TTI {m['tti']} ms, JS {m['js_kb']} Ko, tas {m['heap_mb']} Mo, plus longue tâche {m['longest_task']} ms", flush=True)
    check(f"[budget] JS chargé par l'accueil <= {BUDGET['home_js_kb']} Ko", m["js_kb"] <= BUDGET["home_js_kb"], f"({m['js_kb']} Ko)")
    check(f"[budget] accueil interactif à froid <= {budget('home_cold_tti_ms')} ms (CPU x{THROTTLE}, latence 4G)", m["tti"] <= budget("home_cold_tti_ms"), f"(médiane {m['tti']} ms)")


def wait_precache(page):
    for _ in range(90):
        done = page.evaluate(
            """async () => {
              const paths = []
              for (const n of await caches.keys()) for (const r of await (await caches.open(n)).keys()) paths.push(r.url)
              // Workbox suffixe les fichiers non hachés de `?__WB_REVISION__=` : comparer les chemins.
              const names = paths.map((u) => new URL(u).pathname)
              return names.some((n) => n.endsWith('/puzzles.json')) && names.some((n) => n.endsWith('.wasm')) && !!navigator.serviceWorker.controller
            }"""
        )
        if done:
            return True
        page.wait_for_timeout(1000)
    return False


def warm(p, browser):
    ctx = mobile_context(p, browser, ck, standalone=True)
    ctx.add_init_script(OBSERVE)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/")
    page.evaluate("() => navigator.serviceWorker.ready")
    ok = wait_precache(page)
    page.close()
    if not check("[chaud] service worker installé, précache complet", ok):
        ctx.close()
        return
    runs = []
    for i in range(RUNS):
        page, cdp = throttled(ctx)
        r = measure_home(page, cdp)
        if r is None:
            break
        r["controlled"] = page.evaluate("() => !!navigator.serviceWorker.controller")
        if i == 0:
            check_throttled(page, "accueil à chaud")
        runs.append(r)
        page.close()
    if len(runs) == RUNS:
        check("[chaud] l'accueil est servi par le service worker", all(r["controlled"] for r in runs))
        m = median_of(runs, ("first", "ready", "tti", "heap_mb", "longest_task"))
        metrics["home_warm"] = {**m, "runs": runs}
        print(f"[mesure] accueil à chaud : contenu {m['first']} ms, complet {m['ready']} ms, TTI {m['tti']} ms, tas {m['heap_mb']} Mo, plus longue tâche {m['longest_task']} ms", flush=True)
        check(f"[budget] accueil interactif à chaud <= {budget('home_warm_tti_ms')} ms (CPU x{THROTTLE})", m["tti"] <= budget("home_warm_tti_ms"), f"(médiane {m['tti']} ms)")

    # Puzzles : vrai chargement de document, sans séance gardée (premier puzzle tiré parmi 120 000).
    runs = []
    for i in range(RUNS):
        page, cdp = throttled(ctx, init="try { localStorage.removeItem('chess-local-puzzle-session') } catch {}")
        page.goto(f"{BASE}/#/puzzles", wait_until="commit")
        ready = text_ready_at(page, "Trouve le meilleur coup")
        if ready is None:
            break
        tasks = long_tasks(page)
        runs.append({"ready": ready, "longest_task": longest(tasks), "longtasks_total": round(sum(d for _, d in tasks)), "heap_mb": heap_mb(cdp)})
        if i == 0:
            check_throttled(page, "Puzzles")
        page.close()
    if len(runs) == RUNS:
        m = median_of(runs, runs[0].keys())
        metrics["puzzles_warm"] = {**m, "runs": runs}
        print(f"[mesure] Puzzles à chaud : premier puzzle {m['ready']} ms, plus longue tâche {m['longest_task']} ms, long tasks {m['longtasks_total']} ms, tas {m['heap_mb']} Mo", flush=True)
        check(f"[budget] premier puzzle à chaud <= {budget('puzzles_warm_ready_ms')} ms (CPU x{THROTTLE})", m["ready"] <= budget("puzzles_warm_ready_ms"), f"(médiane {m['ready']} ms)")

    analysis(ctx)
    ctx.close()


def analysis(ctx):
    page, cdp = throttled(ctx)
    page.goto(f"{BASE}/#/analyse")
    if not ck.appears("[analyse] analyse live en cours", page, ENGINE_LINE, timeout=60000):
        page.close()
        return
    check_throttled(page, "Analyse")
    drags = []
    for frm, to, piece in DRAGS:
        # Le moteur pousse ses lignes sur la position courante pendant le glissé.
        ck.appears(f"[analyse] lignes moteur avant {frm}-{to}", page, ENGINE_LINE, timeout=60000)
        page.evaluate("() => { window.__frames = 0; const tick = () => { window.__frames++; window.__raf = requestAnimationFrame(tick) }; tick() }")
        t0 = page.evaluate("() => performance.now()")
        drag_piece(page, frm, to)
        t1 = page.evaluate("() => { cancelAnimationFrame(window.__raf); return performance.now() }")
        frames = page.evaluate("() => window.__frames")
        check(f"[analyse] le glissé a joué {frm}-{to}", piece_on(page, to) == piece, f"({piece_on(page, to)})")
        tasks = [(s, d) for s, d in long_tasks(page, t0) if s <= t1]
        drags.append({"ms": round(t1 - t0), "fps": round(frames / ((t1 - t0) / 1000), 1), "longtasks": len(tasks), "max_longtask": longest(tasks)})
    # Analyse live de la dernière position, sans interaction.
    t2 = page.evaluate("() => performance.now()")
    page.wait_for_timeout(5000)
    live = long_tasks(page, t2)
    a = {
        "drag_fps": statistics.median(d["fps"] for d in drags), "drag_max_longtask": statistics.median(d["max_longtask"] for d in drags),
        "drag_worst_longtask": max(d["max_longtask"] for d in drags), "drags": drags,
        "live_5s_longtasks": len(live), "live_5s_longtask_ms": round(sum(d for _, d in live)), "live_max_longtask": longest(live),
        "heap_mb": heap_mb(cdp),
    }
    metrics["analysis"] = a
    print(f"[mesure] glissés sur Analyse : {a['drag_fps']} images/s, plus longue tâche par glissé {a['drag_max_longtask']} ms (pire {a['drag_worst_longtask']} ms) ; analyse live 5 s : {a['live_5s_longtasks']} long tasks, {a['live_5s_longtask_ms']} ms (max {a['live_max_longtask']} ms) ; tas {a['heap_mb']} Mo", flush=True)
    check(f"[budget] plus longue tâche d'un glissé <= {budget('drag_max_longtask_ms')} ms (médiane de {len(DRAGS)}, CPU x{THROTTLE})",
          a["drag_max_longtask"] <= budget("drag_max_longtask_ms"), f"({a['drag_max_longtask']} ms)")
    page.close()


def per_route(p, browser):
    """JS chargé à l'ouverture directe de chaque page (sans CPU ralenti : seul le volume compte)."""
    ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
    ctx.add_init_script(OBSERVE)
    out = {}
    for route, selector in ROUTES:
        page = ctx.new_page()
        page.goto(f"{BASE}/#/{route}")
        if ck.appears(f"[route] /#/{route} s'affiche", page, selector, timeout=45000):
            page.wait_for_timeout(500)
            out[route or "/"] = script_kb(page)
        page.close()
    ctx.close()
    metrics["route_js_kb"] = out
    print("[mesure] JS par page (Ko) : " + ", ".join(f"{r} {v}" for r, v in out.items()), flush=True)
    if "/" in out and "analyse" in out and "jouer" in out:
        check("[découpage] l'accueil charge moins de JS qu'Analyse et Jouer", out["/"] < out["analyse"] and out["/"] < out["jouer"],
              f"(accueil {out['/']} Ko, analyse {out['analyse']} Ko, jouer {out['jouer']} Ko)")


# --- Montée de version et chunks introuvables -------------------------------------------------


def renamed_build(src, dest):
    """Copie du build comme après un déploiement qui modifie l'entrée : la chunk d'entrée change
    de nom, et toute chunk qui en référence une renommée change de nom à son tour (son contenu a
    changé, donc son hash aussi : le précache ne re-télécharge jamais une URL hachée connue).
    Retourne {ancien nom: nouveau nom}, ou None si le build n'a pas la forme attendue."""
    shutil.copytree(src, dest)
    assets = os.path.join(dest, "assets")
    names = sorted(n for n in os.listdir(assets) if n.endswith(".js"))
    entry = os.path.basename(initial_assets(src)[0])
    if entry not in names or not any(n.startswith("Analysis-") for n in names):
        return None
    texts = {n: open(os.path.join(assets, n), encoding="utf-8").read() for n in names}
    renames = {entry: entry.replace(".js", "B.js")}
    while True:
        more = {n: n.replace(".js", "B.js") for n in names if n not in renames and any(old in texts[n] for old in renames)}
        if not more:
            break
        renames.update(more)
    for path in glob.glob(os.path.join(dest, "**", "*"), recursive=True):
        if os.path.isdir(path) or not path.endswith((".js", ".html")):
            continue
        text = open(path, encoding="utf-8").read()
        for old, new in renames.items():
            text = text.replace(old, new)
        open(path, "w", encoding="utf-8").write(text)
    for old, new in renames.items():
        os.rename(os.path.join(assets, old), os.path.join(assets, new))
    # index.html a changé : sa révision dans le manifeste aussi (c'est ce qui le fait re-télécharger).
    sw_path = os.path.join(dest, "sw.js")
    md5 = hashlib.md5(open(os.path.join(dest, "index.html"), "rb").read()).hexdigest()
    sw, n = re.subn(r'\{url:"index\.html",revision:"[^"]+"\}', f'{{url:"index.html",revision:"{md5}"}}', open(sw_path, encoding="utf-8").read())
    open(sw_path, "w", encoding="utf-8").write(sw)
    analysis_renamed = any(k.startswith("Analysis-") for k in renames)
    return renames if n == 1 and analysis_renamed else None


def open_analysis(page):
    """Navigation interne vers Analyse (HashRouter, sans rechargement du document) : depuis le
    lot 2, Analyse n'a plus d'onglet, et un changement de hash fait le même chemin qu'un lien."""
    page.evaluate("() => { location.hash = '#/analyse' }")


def new_deploy(p, browser, dist):
    """Build A installé, build B déployé à sa place, page encore ouverte sur A : une route jamais
    ouverte demande une chunk que le nouveau service worker a purgée."""
    work = tempfile.mkdtemp(prefix="perf-deploy-")
    port = free_port()
    server = StaticServer(dist, port)
    server.start()
    try:
        renames = renamed_build(dist, os.path.join(work, "B"))
        if not check("[déploiement] build B préparé (chunks renommées, manifeste à jour)", bool(renames)):
            return
        ctx = mobile_context(p, browser, ck, standalone=True)
        page = ctx.new_page()
        loads = []
        page.on("load", lambda: loads.append(1))
        asked = []
        page.on("request", lambda r: asked.append(r.url.rsplit("/", 1)[-1]) if "/assets/Analysis-" in r.url else None)
        page.goto(f"{server.base}/#/")
        page.evaluate("() => navigator.serviceWorker.ready")
        if not check("[déploiement] build A installé (précache complet, page contrôlée)", wait_precache(page)):
            ctx.close()
            return
        ck.appears("[déploiement] accueil du build A affiché", page, "[data-review-ready]")
        server.stop()
        server = StaticServer(os.path.join(work, "B"), port)
        server.start()
        changed = page.evaluate(
            """async () => {
              const changed = new Promise((r) => navigator.serviceWorker.addEventListener('controllerchange', () => r(true), { once: true }))
              await (await navigator.serviceWorker.getRegistration()).update()
              return Promise.race([changed, new Promise((r) => setTimeout(() => r(false), 60000))])
            }"""
        )
        if not check("[déploiement] le service worker du build B a pris la main", changed):
            ctx.close()
            return
        before = len(loads)
        open_analysis(page)
        ck.appears("[déploiement] Analyse s'affiche après la mise à jour", page, "main :text('Options')", timeout=30000)
        new_name = renames[next(k for k in renames if k.startswith("Analysis-"))]
        # Aucune requête vers l'ancienne chunk : le rechargement a précédé l'import, il n'a pas
        # rattrapé un échec (le filet `reloadOnce` seul passerait par une requête en 404).
        check("[déploiement] un seul rechargement, avant toute requête de l'ancienne chunk", len(loads) - before == 1 and asked and all(a == new_name for a in asked),
              f"({len(loads) - before} rechargement(s), chunks d'Analyse demandées {asked})")
        ctx.close()
    finally:
        server.stop()
        shutil.rmtree(work, ignore_errors=True)


def open_analysis(page):
    """Navigation interne vers Analyse, sans rechargement : Analyse n'a plus d'onglet (lot 2 de la
    refonte, elle vit sous Plus) ; changer le hash est exactement ce que fait un lien du HashRouter."""
    page.evaluate("() => { location.hash = '#/analyse' }")


def missing_chunk(p, browser):
    """Chunk de route introuvable, sans service worker (déploiement pendant une visite) : un
    rechargement, puis la page. Toujours introuvable : un seul rechargement, puis l'écran de
    secours, jamais de boucle."""
    for always in (False, True):
        label = "chunk toujours introuvable" if always else "chunk introuvable une fois"
        ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
        failed = []

        def handle(route):
            if always or not failed:
                failed.append(route.request.url)
                route.fulfill(status=404, body="")
            else:
                route.continue_()

        ctx.route("**/assets/Analysis-*.js", handle)
        page = ctx.new_page()
        loads = []
        page.on("load", lambda: loads.append(1))
        page.goto(f"{BASE}/#/")
        ck.appears(f"[{label}] accueil affiché", page, "[data-review-ready]")
        if always:
            with ck.expect_pageerror(("dynamically imported module", "Importing a module script failed")):
                open_analysis(page)
                ck.appears(f"[{label}] écran de secours affiché", page, "main [role='alert']", timeout=20000)
            page.wait_for_timeout(1500)
            check(f"[{label}] un seul rechargement automatique", len(loads) == 2 and len(failed) == 2, f"({len(loads)} chargements, {len(failed)} échecs)")
        else:
            open_analysis(page)
            ck.appears(f"[{label}] Analyse s'affiche après rechargement", page, "main :text('Options')", timeout=20000)
            check(f"[{label}] la chunk a échoué une fois, puis l'app a rechargé une fois", len(failed) == 1 and len(loads) == 2, f"({len(failed)} échecs, {len(loads)} chargements)")
            key = page.evaluate("() => sessionStorage.getItem('chess-local-chunk-reload')")
            check(f"[{label}] la garde de rechargement est levée après succès", key is None, f"({key})")
        ctx.close()


def write_metrics():
    path = os.environ.get("PERF_OUT", os.path.join(SHOTS, "perf-metrics.json"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"[mesure] détail : {path}", flush=True)


def suite(p):
    dist = os.environ.get("E2E_DIST")
    if not dist:
        ck.fail("[perf] E2E_DIST absent : lance cette suite par `npm run test:e2e -- --suite perf`")
        return
    build_checks(dist)
    browser = p.chromium.launch(headless=True)
    try:
        calibrate(p, browser)
        home_cold(p, browser)
        warm(p, browser)
        per_route(p, browser)
        new_deploy(p, browser, dist)
        missing_chunk(p, browser)
    finally:
        write_metrics()
        browser.close()


ck.run(suite)
