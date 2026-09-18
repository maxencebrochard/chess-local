"""T05e : même scénario select_only, mais coordonnées via evaluate (aucun ElementHandle Playwright sur les cases)."""
from pz import *
def center(page, sq):
    return page.evaluate("""(sq) => { const r = document.querySelector(`[data-square='${sq}']`).getBoundingClientRect(); return [r.x + r.width/2, r.y + r.height/2] }""", sq)
with sync_playwright() as p:
    for scen in ("select_tap_nohandle", "select_mouse_nohandle", "no_touch_but_handle"):
        browser, ctx, page, logs = open_mobile(p, standalone=True)
        page.goto(f"{BASE}/#/puzzles")
        page.wait_for_selector("text=Classement puzzles", timeout=30000)
        page.wait_for_timeout(1000)
        n0 = heap_mb(page)
        pz = wait_puzzle(page)
        for i in range(8):
            wait_placement(page, pz, 1)
            sq = pz["moves"][1][:2]
            if scen == "select_tap_nohandle":
                x, y = center(page, sq); page.touchscreen.tap(x, y)
            elif scen == "select_mouse_nohandle":
                x, y = center(page, sq); page.mouse.click(x, y)
            else:
                page.locator(f"[data-square='{sq}']").first.bounding_box()  # handle Playwright, aucun toucher
            page.wait_for_timeout(200)
            sel = page.evaluate("() => [...document.querySelectorAll('[data-square] *')].some(n => getComputedStyle(n).backgroundColor.includes('255, 255, 51, 0.5'))")
            page.locator("main button", has_text="Passer").tap()
            pz = wait_puzzle(page, not_id=pz["id"]); page.wait_for_timeout(700)
        n1 = heap_mb(page)
        print(f"{scen:24s} sélection visible: {sel}  noeuds {n0[1]} -> {n1[1]}  (+{(n1[1]-n0[1])/8:.0f}/puzzle)")
        browser.close()
