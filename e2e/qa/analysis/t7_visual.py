"""Passe 7 : visuel multi-viewports (393x660 Safari, paysage 852x393, desktop 1440x900)."""
import os, sys
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *

PGN = """[White "MagnusCarlsenTheGreatestOfAllTime"]
[Black "xX_LongPseudoDeLaMortQuiTue_Xx"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"""
LONG_OPENING = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7"
MODE = sys.argv[1]


def geom(page, tag):
    g = page.evaluate("""() => {
      const bb = document.querySelector('.boardbox')?.getBoundingClientRect()
      const navs = [...document.querySelectorAll('nav')].filter(n => n.offsetParent).map(n => n.getBoundingClientRect())
      const bar = [...document.querySelectorAll('main .sticky')].filter(n => n.offsetParent).map(n => n.getBoundingClientRect())[0]
      const m = document.querySelector('main')
      return {vw: innerWidth, vh: innerHeight, board: bb && {x: Math.round(bb.x), y: Math.round(bb.y), w: Math.round(bb.width), bottom: Math.round(bb.bottom)},
              nav: navs.map(n => ({x: Math.round(n.x), y: Math.round(n.y), w: Math.round(n.width), h: Math.round(n.height)})),
              actionBar: bar && {y: Math.round(bar.y), h: Math.round(bar.height)},
              mainScroll: m && {sh: m.scrollHeight, ch: m.clientHeight}, overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth}
    }""")
    print(f"[{tag}]", g)


def load_text_mobile(page, text):
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Importer PGN ou FEN").click(); page.wait_for_timeout(300)
    page.fill("textarea", text)
    page.locator("button", has_text="Charger").click(); page.wait_for_timeout(600)


with sync_playwright() as p:
    if MODE == "desktop":
        browser, ctx, page, logs = open_desktop(p)
    else:
        browser, ctx, page, logs = open_mobile(p, standalone=(MODE != "safari"))
        if MODE == "landscape":
            page.set_viewport_size({"width": 852, "height": 393})
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(2500)
    geom(page, f"{MODE} start"); shot(page, f"t7_{MODE}_00_start")

    if MODE == "desktop":
        page.locator("button", has_text="PGN").first.click(); page.wait_for_timeout(300)
        page.fill("textarea", LONG_OPENING); page.locator("button", has_text="Charger").click(); page.wait_for_timeout(2500)
        geom(page, "desktop long opening"); shot(page, "t7_desktop_01_opening")
        # EvalBar verticale + flip
        def evalbar():
            return page.evaluate("""() => {const b=[...document.querySelectorAll('main .w-6')].find(e=>e.offsetParent); if(!b) return null; const [top,bot]=b.querySelectorAll('div'); return {label:b.innerText, topH: top.style.height, topBg: top.style.background, title: b.title}}""")
        print("evalbar:", evalbar())
        page.locator("button[title=\"Retourner l'échiquier\"]").click(); page.wait_for_timeout(600)
        print("evalbar flipped:", evalbar()); shot(page, "t7_desktop_02_flipped")
        page.locator("button[title=\"Retourner l'échiquier\"]").click()
        # position mat noir pour vérifier le sens
        page.locator("button", has_text="PGN").first.click(); page.wait_for_timeout(300)
        page.fill("textarea", "1. f3 e5 2. g4"); page.locator("button", has_text="Charger").click(); page.wait_for_timeout(2500)
        print("evalbar noirs M1:", evalbar(), "| lignes:", page.locator("main .space-y-1").first.inner_text().replace("\n", " | "))
        shot(page, "t7_desktop_03_black_m1")
        page.locator("button[title=\"Retourner l'échiquier\"]").click(); page.wait_for_timeout(600)
        print("evalbar noirs M1 flipped:", evalbar()); shot(page, "t7_desktop_04_black_m1_flipped")
        # bilan desktop
        page.locator("button", has_text="PGN").first.click(); page.wait_for_timeout(300)
        page.fill("textarea", PGN); page.locator("button", has_text="Charger").click(); page.wait_for_timeout(800)
        page.locator("button", has_text="Bilan de partie").click()
        page.wait_for_selector("text=Démarrer le bilan", timeout=240000); page.wait_for_timeout(400)
        shot(page, "t7_desktop_05_summary")
        page.locator("button", has_text="Démarrer le bilan").click(); page.wait_for_timeout(600)
        for _ in range(8):
            page.locator(".fixed button", has_text="Suivant").click(); page.wait_for_timeout(200)
        shot(page, "t7_desktop_06_guided"); geom(page, "desktop guided")
        page.locator(".fixed header button").click(); page.wait_for_timeout(300)
        page.locator(".fixed header button").click(); page.wait_for_timeout(500)
        page.locator("main [data-current]:visible", has_text="xf7").first.click(); page.wait_for_timeout(1200)
        shot(page, "t7_desktop_07_review_panel"); geom(page, "desktop review panel")
        # clavier
        page.keyboard.press("ArrowLeft"); page.wait_for_timeout(300)
        print("flèche gauche clavier -> courant:", page.evaluate("() => {const e=[...document.querySelectorAll('[data-current=\"true\"]')].find(e=>e.offsetParent); return e && e.innerText}"))
    else:
        load_text_mobile(page, LONG_OPENING); page.wait_for_timeout(2000)
        geom(page, f"{MODE} long opening"); shot(page, f"t7_{MODE}_01_opening")
        page.locator("main button", has_text="Explorer").click(); page.wait_for_timeout(400)
        geom(page, f"{MODE} explorer"); shot(page, f"t7_{MODE}_02_explorer")
        page.locator("main button", has_text="Explorer").click()
        page.locator("main button", has_text="Options").click(); page.wait_for_timeout(400)
        sheet = page.locator("h2", has_text="Options").locator("xpath=..").bounding_box()
        print(f"[{MODE}] feuille options bbox:", {k: round(v) for k, v in sheet.items()})
        shot(page, f"t7_{MODE}_03_options")
        page.locator("button", has_text="Importer PGN ou FEN").click(); page.wait_for_timeout(400)
        shot(page, f"t7_{MODE}_04_import_modal")
        mb = page.locator("textarea").locator("xpath=..").bounding_box()
        print(f"[{MODE}] modale import bbox:", {k: round(v) for k, v in mb.items()})
        page.fill("textarea", PGN); page.locator("button", has_text="Charger").click(); page.wait_for_timeout(800)
        page.get_by_role("button", name="★ Bilan").click()
        page.wait_for_selector("text=Démarrer le bilan", timeout=240000); page.wait_for_timeout(400)
        shot(page, f"t7_{MODE}_05_summary")
        page.locator("button", has_text="Démarrer le bilan").click(); page.wait_for_timeout(600)
        for _ in range(8):
            page.locator(".fixed button", has_text="Suivant").click(); page.wait_for_timeout(200)
        geom(page, f"{MODE} guided"); shot(page, f"t7_{MODE}_06_guided")
        gb = page.evaluate("""() => {const b=document.querySelector('.fixed .boardbox').getBoundingClientRect(); const sc=document.querySelector('.fixed .overflow-y-auto'); const foot=[...document.querySelectorAll('.fixed .border-t')].pop().getBoundingClientRect(); return {boardTop: Math.round(b.top), boardBottom: Math.round(b.bottom), footerTop: Math.round(foot.top), scroll: {sh: sc.scrollHeight, ch: sc.clientHeight}}}""")
        print(f"[{MODE}] guidé:", gb)
        page.locator(".fixed button", has_text="Réessayer").click(); page.wait_for_timeout(500)
        gb2 = page.evaluate("""() => {const b=document.querySelector('.fixed .boardbox').getBoundingClientRect(); return {boardTop: Math.round(b.top), boardBottom: Math.round(b.bottom)}}""")
        print(f"[{MODE}] guidé retry (saut du board):", gb2)
        shot(page, f"t7_{MODE}_07_retry")
    print("LOGS", logs)
    browser.close()
