"""T05b : fuite ? 60 x « Passer », mesure heap / noeuds DOM / listeners tous les 15."""
import time
from pz import *
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/puzzles")
    page.wait_for_selector("text=Classement puzzles", timeout=30000)
    page.wait_for_timeout(1000)
    print("n=0", heap_mb(page), "DOM vivants:", page.evaluate("() => document.querySelectorAll('*').length"))
    cur = wait_puzzle(page)
    lat = []
    for i in range(1, 61):
        t = time.time()
        page.locator("main button", has_text="Passer").tap()
        cur = wait_puzzle(page, not_id=cur["id"])
        lat.append(time.time() - t)
        page.wait_for_timeout(700)  # laisse jouer le coup d'amorce
        if i % 15 == 0:
            print(f"n={i}", heap_mb(page), "DOM vivants:", page.evaluate("() => document.querySelectorAll('*').length"),
                  f"latence moy. {1000*sum(lat[-15:])/15:.0f} ms")
    page.wait_for_timeout(3000)
    print("après 3 s de repos:", heap_mb(page))
    print("LOGS:", set(l[:100] for l in logs))
    browser.close()
