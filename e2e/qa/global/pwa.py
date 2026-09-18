"""PWA sur le build servi (BASE=http://localhost:5198) : SW, précache, puis HORS LIGNE sur chaque route."""
import json
import os
import sys

QA = "e2e/qa"
os.environ.setdefault("SHOTS", f"{QA}/global/shots")
os.environ["BASE"] = "http://localhost:5198"
sys.path.insert(0, QA)
from qa_helpers import *  # noqa

fails = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        fails.append(name)


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True, settings={"playSounds": True})
    net = []
    page.on("requestfailed", lambda r: net.append(f"REQFAILED {r.url[:110]} {r.failure}"))
    page.on("response", lambda r: net.append(f"HTTP{r.status} {r.url[:110]}") if r.status >= 400 else None)
    page.goto(f"{BASE}/")
    page.wait_for_timeout(1500)
    head = page.evaluate("""() => ({ manifest: document.querySelector('link[rel=manifest]')?.href, apple: document.querySelector('link[rel=apple-touch-icon]')?.href,
        viewport: document.querySelector('meta[name=viewport]')?.content, capable: document.querySelector('meta[name=apple-mobile-web-app-capable]')?.content,
        statusBar: document.querySelector('meta[name=apple-mobile-web-app-status-bar-style]')?.content, title: document.querySelector('meta[name=apple-mobile-web-app-title]')?.content,
        startup: document.querySelectorAll('link[rel=apple-touch-startup-image]').length })""")
    print("head:", json.dumps(head, ensure_ascii=False))
    t0 = page.evaluate("performance.now()")
    sw = page.evaluate("""async () => { const reg = await navigator.serviceWorker.ready; return { scope: reg.scope, state: reg.active && reg.active.state, script: reg.active && reg.active.scriptURL } }""")
    print("SW:", sw)
    check("SW enregistré et actif", sw["state"] in ("activated", "activating"))
    # attend le précache complet
    for _ in range(60):
        info = page.evaluate("""async () => { const names = await caches.keys(); const out = {}; for (const n of names) { const c = await caches.open(n); out[n] = (await c.keys()).map(r => new URL(r.url).pathname) } return out }""")
        total = sum(len(v) for v in info.values())
        if total >= 21:
            break
        page.wait_for_timeout(1000)
    print("caches:", {k: len(v) for k, v in info.items()})
    allurls = [u for v in info.values() for u in v]
    for must in ["stockfish-18-lite-single.wasm", "stockfish-18-lite-single.js", "puzzles.json", "Move.mp3", "Capture.mp3", "GenericNotify.mp3", "Confirmation.mp3", "Error.mp3", "LowTime.mp3", "pwa-192.png", "apple-touch-icon.png", "index.html", "manifest.webmanifest"]:
        check(f"précache: {must}", any(must in u for u in allurls))
    est = page.evaluate("navigator.storage.estimate().then(e => ({usageMB: +(e.usage/1e6).toFixed(1), quotaMB: Math.round(e.quota/1e6)}))")
    print("storage estimate:", est, "| persisted:", page.evaluate("navigator.storage.persisted()"))
    print("réseau (en ligne):", net)

    # ---------- HORS LIGNE ----------
    ctx.set_offline(True)
    net.clear(); logs.clear()
    page.reload()
    page.wait_for_timeout(2000)
    txt = page.locator("main").inner_text() if page.locator("main").count() else ""
    check("offline: l'app démarre après reload", "Jouer" in txt and "Problèmes" in txt)
    shot(page, "offline_home")
    for route in ["/jouer", "/puzzles", "/rush", "/apprendre", "/analyse", "/archive", "/stats", "/import"]:
        page.goto(f"{BASE}/#{route}")
        page.wait_for_timeout(1500)
        page.reload()
        page.wait_for_timeout(1800)
        n = len(page.locator("main").inner_text().strip()) if page.locator("main").count() else 0
        check(f"offline: deep link + reload {route}", n > 30, f"(texte={n})")
    print("réseau offline (routes):", net[:10]); net.clear()

    # puzzles offline
    page.goto(f"{BASE}/#/puzzles")
    try:
        page.wait_for_selector("[data-square='a1']", timeout=30000)
        ok = True
    except Exception:
        ok = False
    check("offline: puzzles.json se charge (board affiché)", ok)
    shot(page, "offline_puzzles")

    # moteur offline : analyse
    page.goto(f"{BASE}/#/analyse")
    ok = False
    for _ in range(40):
        page.wait_for_timeout(1000)
        t = page.locator("main").inner_text()
        if "+0," in t or "-0," in t or "prof." in t:
            ok = True
            break
    check("offline: Stockfish évalue dans Analyse", ok)
    shot(page, "offline_analyse")

    # moteur offline : le bot joue
    page.goto(f"{BASE}/#/jouer")
    page.wait_for_timeout(1200)
    page.locator("main button", has_text="Blancs").first.tap()
    page.get_by_role("button", name="Jouer", exact=True).tap()
    page.wait_for_timeout(1500)
    tap_move(page, "e2", "e4")
    ok = False
    for _ in range(30):
        page.wait_for_timeout(1000)
        if page.locator("main [data-current]").count() >= 2:
            ok = True
            break
    check("offline: le bot répond", ok, f"(demi-coups={page.locator('main [data-current]').count()})")
    shot(page, "offline_jouer")

    # sons offline
    snd = page.evaluate("""async () => { const out = {}; for (const f of ['Move','Capture','GenericNotify','Confirmation','Error','LowTime']) { try { const r = await fetch(`./sounds/${f}.mp3`); out[f] = r.ok ? (await r.arrayBuffer()).byteLength : 'HTTP' + r.status } catch (e) { out[f] = 'ERR ' + e.message } } return out }""")
    print("sons offline:", snd)
    check("offline: sons servis par le cache", all(isinstance(v, int) and v > 500 for v in snd.values()))
    print("réseau offline (moteur/puzzles/sons):", net[:10], "| logs:", logs[:10]); net.clear(); logs.clear()

    # import chess.com offline
    page.goto(f"{BASE}/#/import")
    page.wait_for_timeout(1000)
    page.locator("main input").first.fill("hikaru")
    page.locator("main button", has_text="Connecter").tap()
    page.wait_for_timeout(2500)
    err = page.locator("main p.bg-red-900\\/40")
    msg = err.first.inner_text() if err.count() else "(aucun message)"
    print("import offline:", repr(msg), "| navigator.onLine =", page.evaluate("navigator.onLine"))
    check("offline: import -> message propre en français", "connexion" in msg.lower())
    shot(page, "offline_import")
    # deep link du raccourci iOS, hors ligne
    page.goto(f"{BASE}/#/import?url=https%3A%2F%2Fwww.chess.com%2Fgame%2Flive%2F123456789")
    page.reload()
    page.wait_for_timeout(3000)
    body = page.locator("main").inner_text()
    dl = page.locator("main p.bg-surface-2")
    dlmsg = dl.first.inner_text() if dl.count() else "(aucun)"
    print("deep link offline, statut:", repr(dlmsg))
    check("offline: deep link ?url= -> message propre (sans nom d'erreur technique ni URL brute)", "TypeError" not in dlmsg and "https://" not in dlmsg, dlmsg[:120])
    shot(page, "offline_import_deeplink")
    print("logs console offline:", logs[:8])

    # __BUILD__ visible ailleurs que /import ?
    ctx.set_offline(False)
    found = {}
    for route in ["/", "/stats", "/import"]:
        page.goto(f"{BASE}/#{route}")
        page.wait_for_timeout(900)
        found[route] = "build 20" in page.locator("body").inner_text()
    print("horodatage build visible:", found)
    browser.close()

print("\nFAILS:", fails)
