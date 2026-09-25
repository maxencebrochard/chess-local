"""Maximus 4 coups, seuil humain de la course R2, Nouvelle partie x5, paysage, desktop."""
import time
from common import *

with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)

    # ---------- M1 : Maximus, 4 coups ----------
    goto_play(page)
    setup(page, mode="bot", bot="Maximus", color="Blancs", tc="5 min")
    b = chess.Board()
    for i, san in enumerate(["e4", "Nf3", "Bc4", "d3"]):
        mv = b.parse_san(san) if b.is_legal(b.parse_san(san)) else next(iter(b.legal_moves))
        t0 = time.time()
        (drag_piece if i % 2 == 0 else tap_move)(page, chess.square_name(mv.from_square), chess.square_name(mv.to_square))
        b.push(mv)
        t1 = time.time()
        w = wait_ply(page, len(b.move_stack) + 1, timeout=30000)
        page.wait_for_timeout(250)
        bm = sync_bot_move(page, b)
        print(f"M1 {san} -> Maximus {bm} en {time.time()-t1:.2f}s (w={w})")
        if bm is None:
            shot(page, f"maximus_sync_fail_{i}"); break
    shot(page, "maximus_4moves")
    print("M1 pendules:", clock_texts(page))

    # ---------- M2 : seuil humain de la course « abandon puis nouvelle partie noire » ----------
    for pace in (400, 700):
        goto_play(page)
        setup(page, mode="bot", bot="Maximus", color="Blancs", tc="Illimité")
        tap_move(page, "e2", "e4", pause=80)
        t0 = time.time()
        page.wait_for_timeout(pace)
        page.locator("button", has_text="Abandonner").click()
        page.wait_for_timeout(pace)
        page.locator("div.fixed button", has_text="Nouvelle partie").click()
        page.wait_for_timeout(pace)
        page.locator("main button", has_text="Noirs").first.click()
        page.wait_for_timeout(pace)
        page.get_by_role("button", name="Jouer", exact=True).click()
        t_start = time.time() - t0
        w = wait_ply(page, 1, timeout=12000)
        print(f"M2 rythme {pace} ms/tap : partie relancée {t_start:.2f}s après e4 ; premier coup du bot: {'après %d ms' % w if w is not None else 'JAMAIS (12 s) -> partie bloquée'}")
        if w is None:
            shot(page, f"race_stuck_pace_{pace}")

    # ---------- M3 : Nouvelle partie x5 ----------
    goto_play(page)
    times = []
    for i in range(5):
        setup(page, mode="bot", bot="Maximus", color="Blancs", tc="Illimité") if i == 0 else None
        if i > 0:
            page.get_by_role("button", name="Jouer", exact=True).click()
            page.wait_for_selector("[data-square='e2']"); page.wait_for_timeout(300)
        tap_move(page, "e2", "e4", pause=100)
        t1 = time.time()
        w = wait_ply(page, 2, timeout=30000)
        times.append(round(time.time() - t1, 2))
        page.wait_for_timeout(300)
        page.locator("button", has_text="Abandonner").click()
        page.wait_for_selector("div.fixed")
        page.locator("div.fixed button", has_text="Nouvelle partie").click()
        page.wait_for_timeout(300)
        page.locator("main button", has_text="Blancs").first.click()
    print("M3 temps de réponse de Maximus sur 5 parties enchaînées:", times)
    print("LOGS mobile:", logs)
    browser.close()

    # ---------- L : paysage 852x393 ----------
    browser = p.chromium.launch(headless=True)
    opts = dict(p.devices["iPhone 14 Pro"]); opts["viewport"] = {"width": 852, "height": 393}
    ctx = browser.new_context(**opts); page = ctx.new_page()
    logs2 = []
    page.on("pageerror", lambda e: logs2.append(str(e)[:200]))
    goto_play(page)
    shot(page, "landscape_setup")
    setup(page, mode="bot", bot="Noa", color="Blancs", tc="10 min")
    tap_move(page, "e2", "e4"); wait_ply(page, 2); page.wait_for_timeout(400)
    shot(page, "landscape_game")
    bb = page.locator(".boardbox").bounding_box()
    print("L paysage boardbox:", bb, "viewport 852x393 ; main scroll:", scroll_state(page))
    clocks = page.evaluate("""() => Array.from(document.querySelectorAll('main .font-mono.text-xl')).map(e => {const r=e.getBoundingClientRect(); return [e.textContent, Math.round(r.top), Math.round(r.bottom)]})""")
    print("L pendules (top,bottom):", clocks)
    ab = page.locator("button", has_text="Abandonner").bounding_box()
    print("L bouton Abandonner:", ab)
    # coach paysage
    goto_play(page)
    setup(page, mode="coach", bot="Noa", color="Blancs")
    page.wait_for_timeout(500)
    shot(page, "landscape_coach")
    print("L coach boardbox:", page.locator(".boardbox").bounding_box())
    print("LOGS paysage:", logs2)
    browser.close()

    # ---------- D : desktop 1440x900 ----------
    browser, ctx, page, logs3 = open_desktop(p)
    goto_play(page)
    shot(page, "desktop_setup")
    setup(page, mode="bot", bot="Noa", color="Blancs", tc="3 | 2")
    page.locator("[data-square='e2']").click(); page.wait_for_timeout(200)
    shot(page, "desktop_selected")
    page.locator("[data-square='e4']").click()
    wait_ply(page, 2); page.wait_for_timeout(500)
    shot(page, "desktop_game")
    page.locator("button", has_text="Abandonner").click(); page.wait_for_selector("div.fixed"); page.wait_for_timeout(400)
    shot(page, "desktop_modal")
    print("D boardbox:", page.locator(".boardbox").bounding_box())
    print("LOGS desktop:", logs3)
    browser.close()
