"""Contre-vérification indépendante de TOUCH-1 par le coordinateur : pion a2 saisi par son chiffre de coordonnée."""
from qa_helpers import *

FIX = """
.boardbox { touch-action: none; }
.boardbox [data-square] > span, .boardbox [data-square] > span > span { pointer-events: none; }
"""

def run(p, label, fix, height):
    browser, ctx, page, logs = open_mobile(p)
    page.set_viewport_size({"width": 393, "height": height})
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1500)
    if fix:
        page.add_style_tag(content=FIX)
    box = page.locator("[data-square='a2']").first.bounding_box()
    x1, y1 = box["x"] + 4, box["y"] + 8           # coin haut-gauche : le petit "2"
    hit = page.evaluate("([x,y]) => { const e = document.elementFromPoint(x,y); return e.tagName + (e.getAttribute('data-piece') ? ':'+e.getAttribute('data-piece') : '') + ' txt=' + JSON.stringify((e.textContent||'').slice(0,3)) }", [x1, y1])
    x2, y2 = sq_center(page, "a4")
    before = scroll_state(page)
    touch_drag(page, x1, y1, x2, y2)
    after = scroll_state(page)
    print(f"[{label} h={height}] élément touché: {hit} | a2={piece_on(page,'a2')} a4={piece_on(page,'a4')} | main.scrollTop {before['mainScrollTop']} -> {after['mainScrollTop']} (scrollable={before['mainScrollable']})")
    # témoin : même pion saisi par son CENTRE
    browser.close()

with sync_playwright() as p:
    for h in (560, 660):
        run(p, "SANS correctif", False, h)
        run(p, "AVEC correctif", True, h)
