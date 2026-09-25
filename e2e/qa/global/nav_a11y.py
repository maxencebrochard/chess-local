"""Navigation, cibles tactiles, contrastes, focus clavier, aria, bouton retour, rechargement."""
import json
import os
import sys

QA = "e2e/qa"
os.environ.setdefault("SHOTS", f"{QA}/global/shots")
sys.path.insert(0, QA)
from qa_helpers import *  # noqa

ROUTES = ["/", "/jouer", "/puzzles", "/rush", "/apprendre", "/analyse", "/archive", "/stats", "/import"]

JS_TARGETS = """() => {
  const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' }
  const els = [...document.querySelectorAll('a, button, input:not([type=file]), summary, select, textarea')].filter(vis)
  return els.map(e => { const r = e.getBoundingClientRect(); return {
    tag: e.tagName, text: (e.innerText || e.placeholder || '').trim().replace(/\\s+/g, ' ').slice(0, 40), w: Math.round(r.width), h: Math.round(r.height),
    inNav: !!e.closest('nav'), aria: e.getAttribute('aria-label'), title: e.getAttribute('title'), role: e.getAttribute('role'),
    ariaPressed: e.getAttribute('aria-pressed'), ariaChecked: e.getAttribute('aria-checked') } })
}"""

JS_CONTRAST = """() => {
  const cv = document.createElement('canvas'); cv.width = cv.height = 1
  const cx = cv.getContext('2d', { willReadFrequently: true })
  const rgb = (css) => { cx.clearRect(0,0,1,1); cx.fillStyle = '#000'; cx.fillStyle = css; cx.fillRect(0,0,1,1); const d = cx.getImageData(0,0,1,1).data; return [d[0], d[1], d[2]] }
  const lum = ([r,g,b]) => { const f = (c) => { c /= 255; return c <= 0.03928 ? c/12.92 : ((c+0.055)/1.055) ** 2.4 }; return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b) }
  const ratio = (a, b) => { const la = lum(a), lb = lum(b); return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05) }
  const probe = document.createElement('span'); document.body.appendChild(probe)
  const out = {}
  const bgs = { surface: '#262421', 'surface-2': '#312e2b', 'surface-3': '#3c3936' }
  for (const cls of ['text-neutral-300', 'text-neutral-400', 'text-neutral-500', 'text-neutral-600', 'text-accent', 'text-red-400']) {
    probe.className = cls
    const css = getComputedStyle(probe).color
    const c = rgb(css)
    out[cls] = { css, rgb: c }
    for (const [n, bg] of Object.entries(bgs)) out[cls][n] = +ratio(c, rgb(bg)).toFixed(2)
  }
  // blanc sur accent (CTA), accent sur accent/20 sur surface-2
  out['white-on-accent'] = +ratio([255,255,255], rgb('#81b64c')).toFixed(2)
  probe.remove()
  return out
}"""

with sync_playwright() as p:
    # ---------- MOBILE ----------
    for w, h in [(393, 852), (320, 568)]:
        browser, ctx, page, logs = open_mobile(p, standalone=True)
        page.set_viewport_size({"width": w, "height": h})
        page.goto(f"{BASE}/#/")
        page.wait_for_timeout(1200)
        tabs = page.evaluate(
            """() => [...document.querySelectorAll('nav')].filter(n => n.getBoundingClientRect().height > 0).flatMap(n => [...n.querySelectorAll('a')]).map(a => {
              const r = a.getBoundingClientRect(); const cs = getComputedStyle(a)
              const range = document.createRange(); range.selectNodeContents(a); const tr = range.getBoundingClientRect()
              return { label: a.textContent.trim(), w: +r.width.toFixed(1), h: +r.height.toFixed(1), fontSize: cs.fontSize, textW: +tr.width.toFixed(1), overflow: +(tr.width - r.width).toFixed(1) } })"""
        )
        navh = page.evaluate("() => [...document.querySelectorAll('nav')].filter(n => n.getBoundingClientRect().height > 0).map(n => n.getBoundingClientRect().height)")
        print(f"\n== TABS {w}x{h} navHeight={navh}")
        for t in tabs:
            print("  ", t)
        if w == 393:
            print("\n== CONTRASTES")
            print(json.dumps(page.evaluate(JS_CONTRAST), indent=1))
            print("\n== CIBLES < 44px et boutons sans nom accessible (393x852)")
            for route in ROUTES:
                page.goto(f"{BASE}/#{route}")
                page.wait_for_timeout(1300)
                els = page.evaluate(JS_TARGETS)
                small = [e for e in els if not e["inNav"] and (e["h"] < 44 or e["w"] < 44)]
                import re
                noname = [e for e in els if not e["aria"] and not re.search(r"[A-Za-zÀ-ÿ0-9]{2,}", e["text"])]
                print(f"  {route}: {len(els)} interactifs, {len(small)} sous 44px (hors nav)")
                for e in small[:14]:
                    print(f"      small {e['tag']} '{e['text']}' {e['w']}x{e['h']}")
                for e in noname[:12]:
                    print(f"      NONAME {e['tag']} text='{e['text']}' title={e['title']} role={e['role']} pressed={e['ariaPressed']} checked={e['ariaChecked']} {e['w']}x{e['h']}")
        browser.close()

    # ---------- BOUTON RETOUR + RELOAD (mobile standalone) ----------
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    print("\n== RELOAD sur chaque route")
    for route in ROUTES:
        page.goto(f"{BASE}/#{route}")
        page.wait_for_timeout(1000)
        page.reload()
        page.wait_for_timeout(1300)
        st = page.evaluate("() => ({hash: location.hash, txt: document.querySelector('main').innerText.trim().length})")
        print("  ", route, st, "OK" if st["hash"] == f"#{route}" and st["txt"] > 0 else "KO")
    print("\n== BACK : chaîne accueil > tuile Rush > back ; accueil > import > back ; chaîne d'onglets")
    page.goto(f"{BASE}/#/")
    page.wait_for_timeout(1000)
    page.locator("main a", has_text="Puzzle Rush").tap()
    page.wait_for_timeout(800)
    print("   après tuile Rush:", page.evaluate("location.hash"), "| liens de retour dans main:", page.locator("main a, main button", has_text="Retour").count() + page.locator("main a, main button", has_text="←").count() + page.locator("main a, main button", has_text="‹").count())
    shot(page, "nav_rush_no_back")
    page.go_back(); page.wait_for_timeout(700)
    print("   back ->", page.evaluate("location.hash"))
    page.locator("main a", has_text="chess.com").tap()
    page.wait_for_timeout(800)
    print("   après tuile chess.com:", page.evaluate("location.hash"), "| retour dans main:", page.locator("main a, main button", has_text="Retour").count())
    page.go_back(); page.wait_for_timeout(700)
    print("   back ->", page.evaluate("location.hash"))
    chain = ["Jouer", "Puzzles", "Apprendre", "Analyse", "Archive", "Stats"]
    for label in chain:
        page.locator("nav a", has_text=label).last.tap()
        page.wait_for_timeout(900)
    hashes = [page.evaluate("location.hash")]
    for _ in range(len(chain)):
        page.go_back(); page.wait_for_timeout(900)
        hashes.append(page.evaluate("location.hash") + ("" if page.evaluate("document.querySelector('main').innerText.trim().length") > 0 else " (VIDE)"))
    print("   chaîne back:", hashes)
    # re-tap sur l'onglet actif : pollue-t-il l'historique ?
    page.goto(f"{BASE}/#/stats"); page.wait_for_timeout(800)
    h0 = page.evaluate("history.length")
    for _ in range(3):
        page.locator("nav a", has_text="Stats").last.tap(); page.wait_for_timeout(300)
    print("   history.length avant/après 3 re-taps sur l'onglet actif:", h0, page.evaluate("history.length"))
    # scroll conservé entre onglets ?
    page.evaluate("document.querySelector('main').scrollTop = 300"); page.wait_for_timeout(200)
    page.locator("nav a", has_text="Archive").last.tap(); page.wait_for_timeout(700)
    print("   scrollTop de main après stats(300) -> archive:", page.evaluate("document.querySelector('main').scrollTop"))
    page.locator("nav a", has_text="Stats").last.tap(); page.wait_for_timeout(700)
    print("   scrollTop de main au retour sur stats:", page.evaluate("document.querySelector('main').scrollTop"))
    print("   logs:", logs)
    browser.close()

    # ---------- PAYSAGE : h1 de l'accueil coupé ? ----------
    browser = p.chromium.launch(headless=True)
    opts = dict(p.devices["iPhone 14 Pro"]); opts["viewport"] = {"width": 852, "height": 393}
    ctx = browser.new_context(**opts); page = ctx.new_page()
    page.goto(f"{BASE}/#/"); page.wait_for_timeout(1200)
    print("\n== PAYSAGE 852x393 accueil:", page.evaluate("""() => { const m = document.querySelector('main'); const h = document.querySelector('main h1').getBoundingClientRect(); const b = [...document.querySelectorAll('main button')].pop().getBoundingClientRect();
      m.scrollTop = 0; return { h1Top: Math.round(h.top), h1Bottom: Math.round(h.bottom), mainTop: Math.round(m.getBoundingClientRect().top), scrollTopMin: m.scrollTop, jouerBottom: Math.round(b.bottom), vh: innerHeight, scrollMax: m.scrollHeight - m.clientHeight } }"""))
    browser.close()

    # ---------- DESKTOP : focus clavier ----------
    browser, ctx, page, logs = open_desktop(p)
    for route in ["/", "/stats", "/import"]:
        page.goto(f"{BASE}/#{route}")
        page.wait_for_timeout(1200)
        print(f"\n== TAB ORDER {route}")
        page.mouse.click(700, 5)
        for i in range(22 if route == "/stats" else 14):
            page.keyboard.press("Tab")
            info = page.evaluate(
                """() => { const e = document.activeElement; if (!e || e === document.body) return null; const cs = getComputedStyle(e);
                  return { tag: e.tagName, text: (e.innerText || e.placeholder || e.title || '').trim().replace(/\\s+/g,' ').slice(0, 30), outline: cs.outlineStyle + ' ' + cs.outlineWidth + ' ' + cs.outlineColor, shadow: cs.boxShadow.slice(0, 40), focusVisible: e.matches(':focus-visible') } }"""
            )
            print("  ", i + 1, info)
        if route == "/stats":
            shot(page, "focus_stats_desktop")
        if route == "/import":
            page.locator("input").first.focus()
            page.wait_for_timeout(200)
            shot(page, "focus_import_input_desktop")
    browser.close()
