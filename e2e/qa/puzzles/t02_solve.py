"""T02 : solution correcte (tap puis drag), coup faux (1er coup, puis 2e coup joueur), réessayer, analyser + retour."""
from pz import *


def boxes(page):
    out = {}
    bb = page.locator(".boardbox").first.bounding_box()
    out["board"] = (round(bb["y"]), round(bb["height"]))
    for label in ["Indice", "Passer", "Suivant", "Réessayer", "Analyser", "Puzzle Rush"]:
        loc = page.locator("main button", has_text=label)
        if loc.count():
            b = loc.first.bounding_box()
            out[label] = (round(b["y"]), round(b["height"]))
    return out


def skip_until(page, cond, max_skips=40):
    pz = wait_puzzle(page)
    n = 0
    while not cond(pz) and n < max_skips:
        page.locator("main button", has_text="Passer").tap()
        pz = wait_puzzle(page, not_id=pz["id"])
        n += 1
    return pz, n


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/puzzles")
    page.wait_for_selector("text=Classement puzzles", timeout=30000)

    # --- A. multi-coups, tap-tap ---
    pz, n = skip_until(page, lambda z: len(z["moves"]) >= 4)
    print("A puzzle", pz["id"], pz["rating"], pz["moves"], "skips:", n, "rating après skips:", rating_shown(page))
    wait_placement(page, pz, 1)
    b0 = boxes(page)
    print("A boxes solving:", b0)

    def after_step(k):
        if k == 1:
            page.wait_for_timeout(150)
            print("A texte après 1er coup:", panel_text(page).split("Classement puzzles")[1].replace("\n", " | ")[:120])
            print("A boxes mid:", boxes(page))
            shot(page, "t02_A_mid_feedback")

    solve(page, pz, mode="tap", on_step=after_step)
    page.wait_for_timeout(500)
    print("A texte fin:", panel_text(page).split("8 |")[-1].replace("\n", " | ")[-260:])
    print("A boxes solved:", boxes(page), "scroll:", scroll_state(page))
    shot(page, "t02_A_solved")
    print("A rating:", rating_shown(page))
    # Le board est-il encore interactif après résolution ?
    # --- B. drag tactile ---
    page.locator("main button", has_text="Suivant").tap()
    pz2 = wait_puzzle(page, not_id=pz["id"])
    print("B puzzle", pz2["id"], pz2["rating"], pz2["moves"], pz2["themes"])
    solve(page, pz2, mode="drag")
    page.wait_for_timeout(500)
    print("B rating:", rating_shown(page), "| résolu:", "Résolu" in panel_text(page))
    shot(page, "t02_B_solved_drag")

    # --- C. coup faux au 1er coup ---
    page.locator("main button", has_text="Suivant").tap()
    pz3 = wait_puzzle(page, not_id=pz2["id"])
    wait_placement(page, pz3, 1)
    w = wrong_move(pz3, 1)
    print("C puzzle", pz3["id"], pz3["rating"], pz3["moves"], "coup faux:", w)
    tap_square(page, w[:2]); page.wait_for_timeout(250)
    tap_square(page, w[2:4])
    page.wait_for_timeout(60)
    shot(page, "t02_C_wrong_t60ms")
    print("C placement 60ms après coup faux == position avant ?", board_placement(page) == expected_placement(pz3, 1))
    page.wait_for_timeout(500)
    shot(page, "t02_C_failed")
    txt = panel_text(page)
    print("C texte:", txt.split("Classement puzzles")[1].replace("\n", " | ")[:220])
    print("C rating:", rating_shown(page), "boxes:", boxes(page), "scroll:", scroll_state(page))
    # Le board reste-t-il jouable après l'échec, sans Réessayer ?
    play_uci(page, pz3["moves"][1])
    page.wait_for_timeout(700)
    print("C après échec, bon coup joué sans Réessayer -> placement avancé ?",
          board_placement(page) != expected_placement(pz3, 1))
    print("C texte:", panel_text(page).split("Classement puzzles")[1].replace("\n", " | ")[:220])
    shot(page, "t02_C_play_after_fail")

    # --- D. coup faux au 2e coup joueur ---
    page.locator("main button").filter(has_text="Suivant").or_(page.locator("main button").filter(has_text="Passer")).first.tap()
    pz4 = wait_puzzle(page, not_id=pz3["id"])
    pz4, n = skip_until(page, lambda z: len(z["moves"]) >= 4 and z["moves"][1][:4] != z["moves"][3][:4])
    wait_placement(page, pz4, 1)
    r_before = rating_shown(page)
    play_uci(page, pz4["moves"][1])
    assert wait_placement(page, pz4, 3)
    w = wrong_move(pz4, 3)
    print("D puzzle", pz4["id"], pz4["moves"], "coup faux au pas 3:", w, "attendu:", pz4["moves"][3])
    tap_move(page, w[:2], w[2:4])
    page.wait_for_timeout(500)
    txt = panel_text(page)
    print("D texte:", txt.split("Classement puzzles")[1].replace("\n", " | ")[:220])
    print("D rating avant/après:", r_before, rating_shown(page))
    shot(page, "t02_D_failed_step3")

    # --- E. Réessayer puis résoudre : pas de variation ---
    page.locator("main button", has_text="Réessayer").tap()
    page.wait_for_timeout(300)
    r_retry = rating_shown(page)
    shot(page, "t02_E_retry_start")
    solve(page, pz4, mode="tap")
    page.wait_for_timeout(500)
    print("E rating pendant retry:", r_retry, "après résolution en retry:", rating_shown(page))
    print("E texte:", panel_text(page).split("Classement puzzles")[1].replace("\n", " | ")[:220])
    shot(page, "t02_E_retry_solved")

    # --- F. Analyser + retour ---
    # D'abord on se fait une série de 1 pour voir si elle survit au retour.
    page.locator("main button", has_text="Suivant").tap()
    pz5 = wait_puzzle(page, not_id=pz4["id"])
    solve(page, pz5, mode="tap")
    page.wait_for_timeout(500)
    print("F avant analyse : puzzle", pz5["id"], "texte:", panel_text(page).split("Classement puzzles")[1].replace("\n", " | ")[:120])
    shot(page, "t02_F_before_analyse")
    page.locator("main button", has_text="Analyser").tap()
    page.wait_for_timeout(3500)
    print("F url:", page.url)
    print("F analyse placement == position clé (après amorce) ?", board_placement(page) == expected_placement(pz5, 1),
          "orientation:", orientation(page))
    shot(page, "t02_F_analyse")
    print("F analyse texte:", panel_text(page).replace("\n", " | ")[:400])
    back = page.locator("main button", has_text="Retour").or_(page.locator("main button", has_text="←"))
    print("F boutons retour:", back.count(), [back.nth(i).inner_text() for i in range(back.count())])
    if back.count():
        back.first.tap()
        page.wait_for_timeout(1500)
        print("F url après retour:", page.url)
        pz6 = wait_puzzle(page)
        print("F puzzle après retour:", pz6["id"], "(avant:", pz5["id"], ")")
        print("F texte après retour:", panel_text(page).split("Classement puzzles")[1].replace("\n", " | ")[:120])
        shot(page, "t02_F_after_return")
    print("DB:", {k: (v if k != "puzzleAttempts" else [(a["puzzleId"], a["success"], a["ratingAfter"]) for a in v]) for k, v in db_dump(page).items()})
    print("LOGS:", logs)
    browser.close()
