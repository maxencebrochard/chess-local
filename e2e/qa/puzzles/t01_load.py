"""T01 : chargement initial /#/puzzles (standalone 393x852), état de chargement, 1er puzzle."""
import time
from pz import *

with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    t0 = time.time()
    page.goto(f"{BASE}/#/puzzles", wait_until="commit")
    # Capture très tôt : que voit-on pendant le chargement ?
    seen_loading = None
    first_text = []
    for i in range(60):
        try:
            txt = page.locator("main").inner_text(timeout=500)
        except Exception:
            txt = "<main absent>"
        if i < 8 or i % 10 == 0:
            first_text.append((round(time.time() - t0, 2), txt[:60].replace("\n", " | ")))
        if "Chargement" in txt and seen_loading is None:
            seen_loading = round(time.time() - t0, 2)
            shot(page, "t01_loading")
        if "Classement puzzles" in txt:
            break
        page.wait_for_timeout(50)
    t_ready = round(time.time() - t0, 2)
    print("chargement visible à", seen_loading, "s ; prêt à", t_ready, "s")
    for ft in first_text:
        print("  ", ft)
    pz = current_puzzle(page)
    print("puzzle:", pz)
    shot(page, "t01_before_first_move")
    place0 = board_placement(page)
    print("placement initial == fen ?", place0 == expected_placement(pz, 0))
    ok = wait_placement(page, pz, 1)
    print("coup d'amorce joué:", ok, "à", round(time.time() - t0, 2), "s")
    page.wait_for_timeout(300)
    shot(page, "t01_after_first_move")
    side = "w" if pz["fen"].split(" ")[1] == "b" else "b"
    print("joueur:", side, "orientation:", orientation(page))
    print("texte:", panel_text(page).replace("\n", " | "))
    print("rating affiché:", rating_shown(page))
    print("overflow_x:", overflow_x(page), "scroll:", scroll_state(page))
    # Positions des CTA
    for label in ["Indice", "Passer", "Puzzle Rush"]:
        b = page.locator("main button", has_text=label).first.bounding_box()
        print(label, b)
    nav = page.locator("nav").last.bounding_box()
    print("nav basse:", nav)
    print("heap:", heap_mb(page))
    print("LOGS:", logs)
    browser.close()
