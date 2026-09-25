"""T06 : Puzzle Rush, mode Survie : difficulté croissante, 3 erreurs, double erreur < 400 ms, record, égalité de record,
quitter en plein rush, doublons rushScores (StrictMode)."""
import re
from pz import *


def rush_state(page):
    t = page.locator("main").inner_text()
    strikes = page.evaluate("() => document.querySelectorAll('main .text-red-500').length")
    m = re.search(r"(\d+)\s*\n\s*résolus", t)
    return {"score": int(m.group(1)) if m else None, "strikes": strikes}


def fast_wrong(page, pz, n_played=1, second=None):
    """Coup faux le plus rapide possible (taps espacés de 40 ms)."""
    w = wrong_move(pz, n_played)
    tap_square(page, w[:2]); page.wait_for_timeout(40); tap_square(page, w[2:4])
    return w


def play_run(page, n_ok, tag, shots=False):
    """Résout n_ok puzzles puis rate 3 fois. Retourne la liste (score, rating du puzzle)."""
    ratings = []
    prev = None
    for i in range(n_ok):
        pz = wait_puzzle(page, not_id=prev)
        ratings.append((i, pz["rating"], len(pz["moves"])))
        solve(page, pz, mode="tap" if i % 2 == 0 else "drag")
        prev = pz["id"]
        if shots and i == 1:
            page.wait_for_timeout(100)
            shot(page, f"t06_{tag}_running")
    for k in range(3):
        pz = wait_puzzle(page, not_id=prev)
        assert wait_placement(page, pz, 1)
        w = wrong_move(pz, 1)
        tap_move(page, w[:2], w[2:4], pause=120)
        page.wait_for_timeout(150)
        if shots and k == 0:
            shot(page, f"t06_{tag}_after_wrong_150ms")
        st = rush_state(page) if k < 2 else None
        print(f"   erreur {k+1}: état {st}")
        prev = pz["id"]
    page.wait_for_timeout(900)
    return ratings


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/rush")
    page.wait_for_timeout(300)
    dis = page.locator("main button", has_text="Survie").is_disabled()
    print("menu à 300 ms : boutons désactivés ?", dis)
    page.wait_for_function("() => ![...document.querySelectorAll('main button')].some(b => b.disabled)", timeout=30000)
    shot(page, "t06_menu")
    print("menu:", page.locator("main").inner_text().replace("\n", " | "))

    # --- run 1 : 6 réussis puis 3 erreurs ---
    page.locator("main button", has_text="Survie").tap()
    page.wait_for_timeout(200)
    print("survie : horloge affichée ?", page.locator("main .font-mono").count() > 0)
    ratings = play_run(page, 6, "survie", shots=True)
    print("run1 ratings par score:", ratings)
    txt = page.locator("main").inner_text().replace("\n", " | ")
    print("run1 écran fin:", txt)
    shot(page, "t06_done_run1")
    print("run1 DB rushScores:", db_dump(page)["rushScores"])

    # --- run 2 : même score (égalité) ---
    page.locator("main button", has_text="Rejouer").tap()
    play_run(page, 6, "survie2")
    txt = page.locator("main").inner_text().replace("\n", " | ")
    print("run2 (égalité, 6) écran fin:", txt)
    shot(page, "t06_done_run2_tie")

    # --- run 3 : score inférieur ---
    page.locator("main button", has_text="Rejouer").tap()
    play_run(page, 2, "survie3")
    print("run3 (2) écran fin:", page.locator("main").inner_text().replace("\n", " | "))
    shot(page, "t06_done_run3_lower")
    page.locator("main button", has_text="Menu").tap(); page.wait_for_timeout(400)
    print("menu records:", page.locator("main").inner_text().replace("\n", " | ")[-120:])
    shot(page, "t06_menu_records")

    # --- double erreur en < 400 ms sur le même puzzle ---
    page.locator("main button", has_text="Survie").tap()
    pz = wait_puzzle(page); assert wait_placement(page, pz, 1)
    w = wrong_move(pz, 1)
    for _ in range(3):
        tap_square(page, w[:2]); page.wait_for_timeout(30); tap_square(page, w[2:4]); page.wait_for_timeout(30)
    page.wait_for_timeout(120)
    print("3 coups faux rapides sur LE MÊME puzzle ->", rush_state(page), "| texte:", page.locator("main").inner_text().replace("\n", " | ")[-80:])
    page.wait_for_timeout(1200)
    print("   1,2 s plus tard:", page.locator("main").inner_text().replace("\n", " | ")[-100:])
    shot(page, "t06_triple_strike")
    if page.locator("main button", has_text="Menu").count():
        page.locator("main button", has_text="Menu").tap(); page.wait_for_timeout(300)
    else:
        page.locator("main button", has_text="✕").tap(); page.wait_for_timeout(400)
        page.locator("main button", has_text="Menu").tap(); page.wait_for_timeout(300)

    # --- erreur puis bon coup dans la fenêtre de 400 ms (puzzle en 1 coup) ---
    page.locator("main button", has_text="Survie").tap()
    pz = wait_puzzle(page); assert wait_placement(page, pz, 1)
    tries = 0
    while len(pz["moves"]) != 2 and tries < 15:
        solve(page, pz); pz = wait_puzzle(page, not_id=pz["id"]); assert wait_placement(page, pz, 1); tries += 1
    before = rush_state(page)
    w = wrong_move(pz, 1)
    tap_square(page, w[:2]); page.wait_for_timeout(30); tap_square(page, w[2:4]); page.wait_for_timeout(30)
    g = pz["moves"][1]
    tap_square(page, g[:2]); page.wait_for_timeout(30); tap_square(page, g[2:4])
    page.wait_for_timeout(250)
    print("erreur puis bon coup < 400 ms : avant", before, "après", rush_state(page))

    # --- quitter en plein rush via la nav basse ---
    n_before = len(db_dump(page)["rushScores"])
    page.locator("nav a", has_text="Accueil").last.tap(); page.wait_for_timeout(500)
    page.go_back(); page.wait_for_timeout(800)
    print("retour sur /rush après navigation :", page.locator("main").inner_text().replace("\n", " | ")[:80])
    print("   scores enregistrés avant/après abandon par navigation:", n_before, len(db_dump(page)["rushScores"]))
    print("DB rushScores:", [(s["mode"], s["score"]) for s in db_dump(page)["rushScores"]])
    print("LOGS:", set(l[:140] for l in logs))
    browser.close()
