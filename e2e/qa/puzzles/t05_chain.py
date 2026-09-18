"""T05 : enchaîne 10 puzzles (7 réussis, 3 ratés), dérive Elo, répétitions, latence « Suivant », heap,
persistance après rechargement, « Passer » sans pénalité. Puis chargement à froid avec CPU x4."""
import time
from pz import *

with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/puzzles")
    page.wait_for_selector("text=Classement puzzles", timeout=30000)
    print("heap initial:", heap_mb(page))
    seen, rows = [], []
    prev = None
    pattern = [1, 1, 1, 0, 1, 1, 0, 1, 1, 1]  # 1 = réussi
    for i, ok in enumerate(pattern):
        t0 = time.time()
        pz = wait_puzzle(page, not_id=prev)
        assert wait_placement(page, pz, 1)
        r_before = int(rating_shown(page).split("+")[0].split("-")[0]) if i == 0 else r_after
        if ok:
            solve(page, pz, mode="tap" if i % 2 == 0 else "drag")
        else:
            w = wrong_move(pz, 1)
            tap_move(page, w[:2], w[2:4])
        page.wait_for_timeout(450)
        shown = rating_shown(page)
        streak = page.evaluate("() => document.querySelector('main .text-orange-400')?.innerText")
        import re
        r_after = int(re.match(r"\d+", shown).group(0))
        rows.append((pz["id"], pz["rating"], ok, r_before, shown, streak))
        seen.append(pz["id"])
        print(f"#{i+1} {pz['id']} ({pz['rating']}, {len(pz['moves'])} coups) {'OK ' if ok else 'KO '} Elo {r_before} -> {shown}  série {streak}  écart puzzle-Elo {pz['rating'] - r_before:+d}")
        prev = pz["id"]
        t1 = time.time()
        page.locator("main button", has_text="Suivant").tap()
        nxt = wait_puzzle(page, not_id=prev)
        lat = time.time() - t1
        if i in (0, 9):
            print(f"   latence Suivant -> nouveau puzzle monté: {lat*1000:.0f} ms")
    print("répétitions:", len(seen) - len(set(seen)))
    print("heap après 10 puzzles:", heap_mb(page))
    shot(page, "t05_after_10")
    d = db_dump(page)
    print("DB rating:", d["ratings"], "tentatives:", len(d["puzzleAttempts"]))

    # Passer : pénalité ? tentative enregistrée ?
    r0 = rating_shown(page)
    cur = wait_puzzle(page)
    for _ in range(5):
        page.locator("main button", has_text="Passer").tap()
        cur = wait_puzzle(page, not_id=cur["id"])
    d2 = db_dump(page)
    print("après 5 « Passer » : rating", r0, "->", rating_shown(page), "| tentatives:", len(d2["puzzleAttempts"]))

    # Rechargement
    streak_before = page.evaluate("() => document.querySelector('main .text-orange-400')?.innerText")
    page.reload()
    page.wait_for_selector("text=Classement puzzles", timeout=30000)
    page.wait_for_timeout(800)
    streak_after = page.evaluate("() => document.querySelector('main .text-orange-400')?.innerText")
    print("après reload : rating", rating_shown(page), "| série avant/après:", streak_before, "->", streak_after)
    shot(page, "t05_after_reload")

    # Navigation interne (onglet Accueil puis retour) : série ?
    page.locator("nav a", has_text="Accueil").last.tap(); page.wait_for_timeout(500)
    shot(page, "t05_home")
    print("accueil:", page.locator("main").inner_text().replace("\n", " | ")[:300])
    page.locator("nav a", has_text="Puzzles").last.tap()
    page.wait_for_selector("text=Classement puzzles", timeout=30000)
    print("LOGS:", set(l[:100] for l in logs))
    browser.close()

    # ---- chargement à froid, CPU x4 (approximation d'un vieil iPhone) ----
    for rate in (1, 4, 6):
        browser, ctx, page, logs = open_mobile(p, standalone=True)
        cdp = ctx.new_cdp_session(page)
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": rate})
        t0 = time.time()
        page.goto(f"{BASE}/#/puzzles", wait_until="commit")
        page.wait_for_selector("text=Classement puzzles", timeout=60000)
        print(f"CPU x{rate} : puzzle affiché après {time.time()-t0:.2f} s")
        # Rush : boutons désactivés combien de temps ?
        browser.close()
