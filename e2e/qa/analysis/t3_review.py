"""Passe 3 : bilan complet sur la partie à fautes (mobile standalone)."""
import os, sys, time, json
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *

PGN = sys.argv[1] if len(sys.argv) > 1 else "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"
TAG = sys.argv[2] if len(sys.argv) > 2 else "t3"


def load_text(page, text):
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Importer PGN ou FEN").click(); page.wait_for_timeout(300)
    page.fill("textarea", text)
    page.locator("button", has_text="Charger").click(); page.wait_for_timeout(500)


def summary_data(page):
    return page.evaluate("""() => {
      const rows = [...document.querySelectorAll('.fixed .grid')].map(g => g.innerText.replace(/\\n+/g,' | '))
      return rows
    }""")


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(2000)
    load_text(page, PGN)
    page.wait_for_timeout(800)
    shot(page, f"{TAG}_00_loaded")
    t0 = time.time()
    page.get_by_role("button", name="★ Bilan").click()
    page.wait_for_timeout(700)
    shot(page, f"{TAG}_01_progress")
    print("texte visible pendant le bilan (main):", page.locator("main").inner_text()[:300].replace("\n", " | "))
    print("% visible ?", page.evaluate("() => [...document.querySelectorAll('main *')].filter(e => e.offsetParent && /Analyse…|\\d+\\s?%/.test(e.innerText||'') && e.children.length===0).map(e=>e.innerText)"))
    print("bouton annuler ?", page.locator("button:visible", has_text="Annuler").count())
    page.wait_for_selector("text=Démarrer le bilan", timeout=240000)
    print("durée bilan s:", round(time.time() - t0, 1))
    page.wait_for_timeout(400)
    shot(page, f"{TAG}_02_summary")
    for r in summary_data(page):
        print("GRID:", r)
    print("quip:", page.locator(".fixed .bg-white").first.inner_text())
    sc = page.evaluate("() => {const s=document.querySelector('.fixed .overflow-y-auto'); return {sh:s.scrollHeight, ch:s.clientHeight}}")
    print("résumé scroll:", sc)
    page.evaluate("() => {const s=document.querySelector('.fixed .overflow-y-auto'); s.scrollTop = s.scrollHeight}")
    page.wait_for_timeout(300)
    shot(page, f"{TAG}_03_summary_bottom")
    page.evaluate("() => {const s=document.querySelector('.fixed .overflow-y-auto'); s.scrollTop = 0}")

    # Démarrer -> guidé
    page.locator("button", has_text="Démarrer le bilan").click(); page.wait_for_timeout(600)
    shot(page, f"{TAG}_04_guided_first")
    n = page.locator(".fixed [data-current]").count()
    print("nb coups bande:", n)
    allc = []
    heights = []
    for i in range(n):
        bubble = page.locator(".fixed .bg-white").first
        txt = bubble.inner_text().replace("\n", " | ")
        bb = bubble.bounding_box(); brd = page.locator(".fixed .boardbox").bounding_box()
        heights.append((round(bb["height"]), round(brd["y"])))
        ev = page.locator(".fixed .bg-neutral-800").first.inner_text()
        allc.append(txt)
        print(f"  [{i}] eval={ev!r} bulle={txt}")
        if i in (3, 6, 7, 8, 13):
            shot(page, f"{TAG}_05_guided_{i}")
        nxt = page.locator(".fixed button", has_text="Suivant")
        if nxt.count():
            nxt.click(); page.wait_for_timeout(350)
    print("hauteur bulle / y board par coup:", heights)
    bad = [c for c in allc if any(k in c for k in ("undefined", "NaN", "null"))]
    print("textes suspects:", bad)
    import re
    raw = [c for c in allc if re.search(r"\b[KQRBN][a-h]?x?[a-h][1-8]", c)]
    print("SAN anglais brut dans bulles:", raw)
    print("bouton final:", page.locator(".fixed button").last.inner_text())
    shot(page, f"{TAG}_06_guided_last")
    print("LOGS", logs)
    json.dump(allc, open(os.path.join(QA, "analysis", f"{TAG}_comments.json"), "w"), ensure_ascii=False, indent=1)
    browser.close()
