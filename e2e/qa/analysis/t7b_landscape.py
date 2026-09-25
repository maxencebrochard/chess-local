"""Passe 7b : paysage 852x393 (layout md) + nom d'ouverture long en standalone 393x852."""
import os, sys
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *

PGN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"
LONG_OPENING = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7"

with sync_playwright() as p:
    # --- standalone : nom d'ouverture long
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(2000)
    b0 = page.locator(".boardbox").first.bounding_box()
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Importer PGN ou FEN").click(); page.wait_for_timeout(300)
    page.fill("textarea", LONG_OPENING); page.locator("button", has_text="Charger").click(); page.wait_for_timeout(1500)
    b1 = page.locator(".boardbox").first.bounding_box()
    ban = page.locator("main .truncate.rounded.bg-surface-2").first
    print("standalone board x avant/après nom long:", b0["x"], "->", b1["x"], "| bandeau bbox:", {k: round(v) for k, v in ban.bounding_box().items()}, "| scrollWidth/clientWidth:", ban.evaluate("e => [e.scrollWidth, e.clientWidth]"))
    print("main scrollWidth/clientWidth:", page.evaluate("() => {const m=document.querySelector('main'); return [m.scrollWidth, m.clientWidth, m.scrollLeft]}"))
    shot(page, "t7b_standalone_long_opening")
    # drag horizontal possible ?
    browser.close()

    # --- paysage
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.set_viewport_size({"width": 852, "height": 393})
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(2000)
    print("paysage:", page.evaluate("""() => {const m=document.querySelector('main'); const r=(s)=>{const e=[...document.querySelectorAll(s)].find(e=>e.offsetParent); if(!e) return null; const b=e.getBoundingClientRect(); return {x:Math.round(b.x), r:Math.round(b.right), y:Math.round(b.y), b:Math.round(b.bottom)}};
      return {main:[m.scrollWidth, m.clientWidth, m.scrollHeight, m.clientHeight], overflowX: document.documentElement.scrollWidth - innerWidth, board: r('.boardbox'), panel: r('main .md\\\\:w-96')}}"""))
    btns = page.evaluate("""() => [...document.querySelectorAll('main button')].filter(e=>e.offsetParent).map(e=>{const b=e.getBoundingClientRect(); return [e.innerText.replace(/\\n/g,' ').slice(0,18), Math.round(b.x), Math.round(b.right), Math.round(b.width), Math.round(b.height)]}).filter(x => x[2] > 852 || x[3] < 40)""")
    print("boutons hors écran (right>852) ou étroits:", btns)
    page.locator("button", has_text="PGN").first.click(); page.wait_for_timeout(300)
    page.fill("textarea", PGN); page.locator("button", has_text="Charger").click(); page.wait_for_timeout(600)
    page.locator("button", has_text="Bilan").first.click()
    page.wait_for_selector("text=Démarrer le bilan", timeout=240000); page.wait_for_timeout(400)
    shot(page, "t7b_landscape_summary")
    page.locator("button", has_text="Démarrer le bilan").click(); page.wait_for_timeout(600)
    shot(page, "t7b_landscape_guided")
    print("guidé paysage:", page.evaluate("""() => {const b=document.querySelector('.fixed .boardbox').getBoundingClientRect(); const sc=document.querySelector('.fixed .overflow-y-auto'); const foot=[...document.querySelectorAll('.fixed .border-t')].pop().getBoundingClientRect(); return {boardTop: Math.round(b.top), boardBottom: Math.round(b.bottom), boardW: Math.round(b.width), footerTop: Math.round(foot.top), scroll: {sh: sc.scrollHeight, ch: sc.clientHeight}}}"""))
    print("LOGS", logs)
    browser.close()
