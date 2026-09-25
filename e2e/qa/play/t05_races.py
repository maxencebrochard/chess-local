"""Courses : abandon pendant la réflexion du bot, nouvelle partie immédiate, navigation en pleine partie, abandon au coup 0."""
import time
from common import *

IDB = """() => new Promise(res => { const r = indexedDB.open('chess-local'); r.onsuccess = () => { const db = r.result; const tx = db.transaction(['ratings','games']); const out = {}; tx.objectStore('ratings').getAll().onsuccess = e => out.ratings = e.target.result; tx.objectStore('games').getAll().onsuccess = e => out.games = e.target.result.map(g => [g.id, g.result, g.termination, g.playerRatingAfter, g.pgn.split('\\n').pop()]); tx.oncomplete = () => res(out) } })"""

with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)

    # ---------- R1 : abandon pendant que Maximus réfléchit ----------
    for attempt in (1, 2):
        goto_play(page)
        setup(page, mode="bot", bot="Maximus", color="Blancs", tc="Illimité")
        tap_move(page, "e2", "e4", pause=80)
        page.locator("button", has_text="Abandonner").click()
        t0 = time.time()
        page.wait_for_selector("div.fixed", timeout=5000)
        n_at_modal = ply_count(page)
        page.wait_for_timeout(3500)
        n_after = ply_count(page)
        print(f"R1#{attempt} demi-coups à l'ouverture de la modale: {n_at_modal} ; 3,5 s après: {n_after} ; coups: {page.locator('main [data-current]').all_inner_texts()}")
        shot(page, f"race_resign_botmove_{attempt}")
    print("   IDB:", page.evaluate(IDB))

    # ---------- R2 : abandon puis nouvelle partie immédiate avec les noirs ----------
    for attempt in (1, 2):
        goto_play(page)
        setup(page, mode="bot", bot="Maximus", color="Blancs", tc="Illimité")
        tap_move(page, "e2", "e4", pause=80)
        t0 = time.time()
        page.locator("button", has_text="Abandonner").click()
        page.locator("div.fixed button", has_text="Nouvelle partie").click()
        page.locator("main button", has_text="Noirs").first.click()
        page.get_by_role("button", name="Jouer", exact=True).click()
        t_start = time.time() - t0
        page.wait_for_selector("[data-square='e2']")
        w = wait_ply(page, 1, timeout=12000)
        print(f"R2#{attempt} nouvelle partie lancée {t_start:.2f}s après l'abandon ; premier coup du bot: {'après %d ms' % w if w is not None else 'JAMAIS (12 s)'}")
        shot(page, f"race_newgame_black_{attempt}")
        print("   position DOM == départ ?", dom_position(page) == board_to_dict(chess.Board()))

    # ---------- R3 : navigation en pleine partie ----------
    goto_play(page)
    setup(page, mode="bot", bot="Noa", color="Blancs", tc="10 min")
    tap_move(page, "e2", "e4"); wait_ply(page, 2); page.wait_for_timeout(300)
    tap_move(page, "d2", "d4"); wait_ply(page, 4); page.wait_for_timeout(300)
    games_before = len(page.evaluate(IDB)["games"])
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
    page.locator("nav a", has_text="Archive").last.click(); page.wait_for_timeout(800)
    page.locator("nav a", has_text="Jouer").last.click(); page.wait_for_timeout(1000)
    shot(page, "race_nav_back")
    print("R3 après aller-retour : écran setup ?", page.locator("text=Adversaire").count() == 1, "| board présent ?", page.locator("[data-square='e2']").count() > 0,
          "| dialogues:", dialogs, "| parties en base avant/après:", games_before, len(page.evaluate(IDB)["games"]))

    # ---------- R4 : abandon au coup 0 ----------
    goto_play(page)
    setup(page, mode="bot", bot="Noa", color="Blancs", tc="10 min")
    page.locator("button", has_text="Abandonner").click()
    page.wait_for_selector("div.fixed")
    page.wait_for_timeout(500)
    print("R4 abandon sans coup:", page.locator("div.fixed").inner_text().replace("\n", " | "))
    shot(page, "race_resign_move0")

    # ---------- R5 : navigation dans l'historique pendant la partie ----------
    goto_play(page)
    setup(page, mode="bot", bot="Noa", color="Blancs", tc="Illimité")
    tap_move(page, "e2", "e4"); wait_ply(page, 2); page.wait_for_timeout(300)
    tap_move(page, "d2", "d4"); wait_ply(page, 4); page.wait_for_timeout(300)
    page.locator("main button", has_text="⏮").click(); page.wait_for_timeout(300)
    print("R5 ⏮ : e4 joué affiché ?", piece_on(page, "e4"), "(⏮ devrait montrer la position initiale)")
    shot(page, "hist_first")
    n0 = ply_count(page)
    tap_move(page, "g1", "f3")
    print("   coup tenté en consultation d'historique : accepté ?", ply_count(page) != n0)
    page.locator("main button", has_text="⏭").click(); page.wait_for_timeout(300)
    nb = page.evaluate("""() => Array.from(document.querySelectorAll('main button')).filter(b => ['⏮','◀','▶','⏭'].includes(b.innerText.trim())).map(b => Math.round(b.getBoundingClientRect().height))""")
    print("   hauteur boutons de navigation:", nb)
    ab = page.locator("button", has_text="Abandonner").bounding_box()
    print("   bouton Abandonner:", ab)

    # ---------- R6 : double tap rapide ----------
    x, y = sq_center(page, "g1")
    page.touchscreen.tap(x, y); page.touchscreen.tap(x, y); page.wait_for_timeout(150)
    tap_square(page, "f3"); page.wait_for_timeout(300)
    print("R6 double tap sur g1 puis f3 : coup joué ?", piece_on(page, "f3"))
    print("LOGS:", logs)
    browser.close()
