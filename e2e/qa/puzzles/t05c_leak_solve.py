"""T05c : fuite quand on RÉSOUT (tap vs drag) ? noeuds DOM / listeners après GC."""
import sys
from pz import *
mode = sys.argv[1] if len(sys.argv) > 1 else "tap"
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/puzzles")
    page.wait_for_selector("text=Classement puzzles", timeout=30000)
    page.wait_for_timeout(1000)
    print(mode, "n=0", heap_mb(page))
    prev = None
    for i in range(1, 21):
        pz = wait_puzzle(page, not_id=prev)
        solve(page, pz, mode=mode)
        page.wait_for_timeout(400)
        prev = pz["id"]
        page.locator("main button", has_text="Suivant").tap()
        wait_puzzle(page, not_id=prev)
        page.wait_for_timeout(700)
        if i % 5 == 0:
            print(mode, f"n={i}", heap_mb(page), "DOM vivants:", page.evaluate("() => document.querySelectorAll('*').length"))
    page.wait_for_timeout(4000)
    print(mode, "après 4 s de repos:", heap_mb(page))
    browser.close()
