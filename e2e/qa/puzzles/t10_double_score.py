"""T10 : puzzles classés, 3 coups faux très rapides : l'Elo n'est-il débité qu'une fois ?"""
from pz import *
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/puzzles")
    page.wait_for_selector("text=Classement puzzles", timeout=30000)
    pz = wait_puzzle(page); assert wait_placement(page, pz, 1); page.wait_for_timeout(200)
    w = wrong_move(pz, 1)
    x1, y1 = sq_center(page, w[:2]); x2, y2 = sq_center(page, w[2:4])
    for _ in range(3):
        page.touchscreen.tap(x1, y1); page.touchscreen.tap(x2, y2)
    page.wait_for_timeout(800)
    d = db_dump(page)
    print("rating affiché:", rating_shown(page), "| DB:", d["ratings"], "| tentatives:", [(a["puzzleId"], a["success"], a["ratingAfter"]) for a in d["puzzleAttempts"]])
    browser.close()
