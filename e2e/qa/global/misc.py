"""Captures de preuve + mesures de cohérence visuelle (h1, paddings, rayons) + responsive en partie."""
import json
import os
import sys
from collections import Counter

QA = "e2e/qa"
os.environ.setdefault("SHOTS", f"{QA}/global/shots")
sys.path.insert(0, QA)
sys.path.insert(0, f"{QA}/global")
from qa_helpers import *  # noqa
from seed import seed

ROUTES = ["/", "/jouer", "/puzzles", "/rush", "/apprendre", "/analyse", "/archive", "/stats", "/import"]

with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/stats"); page.wait_for_timeout(1100)
    seed(page); page.reload(); page.wait_for_timeout(1000)
    # 1. message d'erreur de restauration (vert + anglais)
    page.locator("input[type=file]").set_input_files(f"{QA}/global/backup_files/texte.json")
    page.wait_for_timeout(700)
    page.evaluate("document.querySelector('main').scrollTop = 99999"); page.wait_for_timeout(300)
    shot(page, "restore_error_green_english")
    m = page.locator("main p.text-xs.text-accent").first
    print("msg erreur:", m.inner_text(), "| couleur:", m.evaluate("e => getComputedStyle(e).color"))
    # 2. succès : « Recharge la page » en PWA standalone
    page.locator("input[type=file]").set_input_files(f"{QA}/global/backup_files/export.json")
    page.wait_for_timeout(900)
    page.evaluate("document.querySelector('main').scrollTop = 99999"); page.wait_for_timeout(300)
    shot(page, "restore_success_recharge")

    # 3. cohérence : h1, padding conteneur, rayons, tailles de police des boutons, par route
    print("\n== COHÉRENCE PAR ROUTE (393x852, données peuplées)")
    for route in ROUTES:
        page.goto(f"{BASE}/#{route}"); page.wait_for_timeout(1300)
        info = page.evaluate("""() => {
          const main = document.querySelector('main'); const h1 = main.querySelector('h1'); const c = main.firstElementChild
          const cs = (e) => getComputedStyle(e)
          const radii = {}; const btnFonts = {}
          for (const e of main.querySelectorAll('button, a, div, details, input')) { const r = cs(e).borderTopLeftRadius; const bg = cs(e).backgroundColor; if (r !== '0px' && bg !== 'rgba(0, 0, 0, 0)' && e.getBoundingClientRect().width > 40) radii[r] = (radii[r] || 0) + 1 }
          for (const e of main.querySelectorAll('button')) { const k = cs(e).fontSize + '/' + cs(e).fontWeight; btnFonts[k] = (btnFonts[k] || 0) + 1 }
          return { h1: h1 ? { text: h1.innerText.slice(0, 30), size: cs(h1).fontSize, weight: cs(h1).fontWeight, left: Math.round(h1.getBoundingClientRect().left), top: Math.round(h1.getBoundingClientRect().top) } : null,
                   pad: c ? cs(c).paddingLeft + ' / top ' + cs(c).paddingTop : null, firstLeft: c && c.firstElementChild ? Math.round(c.firstElementChild.getBoundingClientRect().left) : null, radii, btnFonts }
        }""")
        print(f"  {route}: {json.dumps(info, ensure_ascii=False)}")
    # 4. libellé de cadence dans Jouer
    page.goto(f"{BASE}/#/jouer"); page.wait_for_timeout(1200)
    t = page.locator("main").inner_text()
    idx = t.find("Mon classement")
    print("\nJouer:", repr(t[idx: idx + 40]))
    browser.close()

    # 5. responsive EN PARTIE : tablette portrait + paysage téléphone
    for name, w, h in [("tab820x1180", 820, 1180), ("land852x393", 852, 393)]:
        browser = p.chromium.launch(headless=True)
        opts = dict(p.devices["iPhone 14 Pro"]); opts["viewport"] = {"width": w, "height": h}
        c = browser.new_context(**opts); pg = c.new_page()
        pg.add_init_script("if (!localStorage.getItem('chess-local-settings')) localStorage.setItem('chess-local-settings', " + json.dumps(json.dumps({"state": DEFAULT_SETTINGS, "version": 0})) + ")")
        pg.goto(f"{BASE}/#/jouer"); pg.wait_for_timeout(1200)
        pg.get_by_role("button", name="Jouer", exact=True).click(); pg.wait_for_timeout(1500)
        m = pg.evaluate("""() => { const m = document.querySelector('main'); const a8 = document.querySelector("[data-square='a8']").getBoundingClientRect(); const h1 = document.querySelector("[data-square='h1']").getBoundingClientRect();
          return { mainOvx: m.scrollWidth - m.clientWidth, mainLeft: Math.round(m.getBoundingClientRect().left), boardLeft: Math.round(Math.min(a8.left, h1.left)), boardRight: Math.round(Math.max(a8.right, h1.right)), boardTop: Math.round(Math.min(a8.top, h1.top)), boardBottom: Math.round(Math.max(a8.bottom, h1.bottom)), vw: innerWidth, vh: innerHeight, sq: Math.round(a8.width) } }""")
        print(f"\n{name} /jouer en partie:", m)
        pg.screenshot(path=os.path.join(SHOTS, f"ingame_{name}_jouer.png"))
        pg.goto(f"{BASE}/#/analyse"); pg.wait_for_timeout(1500)
        m = pg.evaluate("""() => { const m = document.querySelector('main'); const a8 = document.querySelector("[data-square='a8']").getBoundingClientRect(); const h1 = document.querySelector("[data-square='h1']").getBoundingClientRect();
          return { mainOvx: m.scrollWidth - m.clientWidth, mainLeft: Math.round(m.getBoundingClientRect().left), boardLeft: Math.round(Math.min(a8.left, h1.left)), boardRight: Math.round(Math.max(a8.right, h1.right)), vw: innerWidth, sq: Math.round(a8.width), scrollLeftMax: m.scrollWidth - m.clientWidth } }""")
        print(f"{name} /analyse:", m)
        browser.close()

    # 6. zoom barre d'onglets 320
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.set_viewport_size({"width": 320, "height": 568})
    page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1200)
    page.screenshot(path=os.path.join(SHOTS, "tabbar_320_zoom.png"), clip={"x": 0, "y": 568 - 56, "width": 320, "height": 56})
    page.set_viewport_size({"width": 393, "height": 852})
    page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1000)
    page.screenshot(path=os.path.join(SHOTS, "tabbar_393_zoom.png"), clip={"x": 0, "y": 852 - 56, "width": 393, "height": 56})
    browser.close()
