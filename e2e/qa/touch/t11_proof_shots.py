"""Captures avant/après du constat principal : pion a2 saisi par son chiffre, standalone 852 + safe areas émulées."""
import sys
sys.path.insert(0, "e2e/qa/touch")
from tlib import *
INSETS = ".pt-safe { padding-top: 71px !important; } .pb-safe { padding-bottom: 34px !important; }"
FIX = ".boardbox { touch-action: none; } [data-square] > span, [data-square] > span > span { pointer-events: none; }"
with sync_playwright() as p:
    for tag, css in [("AVANT", INSETS), ("APRES", INSETS + FIX)]:
        browser, ctx, page, logs = open_mobile_t(p, standalone=True); install(page)
        page.goto(f"{BASE}/#/jouer"); page.wait_for_timeout(1200); page.add_style_tag(content=css)
        page.locator("main button", has_text="Noa").first.click(); page.locator("main button", has_text="Blancs").first.click()
        page.get_by_role("button", name="Jouer", exact=True).click(); page.wait_for_timeout(1500)
        page.evaluate("() => { document.querySelector('main').scrollTop = 0 }"); page.wait_for_timeout(200)
        b = sq_rect(page, "a2"); r = gesture(page, b["x"] + 5, b["y"] + 7, *sq_center(page, "a4")); v = verdict(r)
        print(f"{tag}: hit={r['startHit']} coup_joué={v['moved']} pointercancel={v['pointercancel']} main.scrollTop {r['before']['scrollers'][0]['top'] if r['before']['scrollers'] else 0} -> {r['after']['scrollers'][0]['top'] if r['after']['scrollers'] else 0} boardTop={v['boardTop']} a4={r['after']['pos'].get('a4')}")
        shot(page, f"t11_preuve_{tag}")
        browser.close()
