"""Écran de partie en 393x660 (onglet Safari) : ce qui tient à l'écran, modale."""
import time
from common import *
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=False)
    goto_play(page)
    setup(page, mode="bot", bot="Noa", color="Blancs", tc="10 min")
    t0 = time.time()
    tap_move(page, "e2", "e4", pause=100)
    w = wait_ply(page, 2)
    print("premier coup du bot (moteur à froid) :", round(time.time() - t0, 2), "s")
    page.wait_for_timeout(400)
    shot(page, "game_660")
    nav = page.locator("nav").last.bounding_box()
    for name, loc in [("board", ".boardbox"), ("pendule bas", "main .font-mono.text-xl >> nth=1"), ("ouverture", "main .rounded.bg-surface-2.px-3"), ("⏮", "main button:has-text('⏮')"), ("Abandonner", "button:has-text('Abandonner')")]:
        bb = page.locator(loc).first.bounding_box()
        print(f"  {name:12} y={bb['y']:.0f}..{bb['y']+bb['height']:.0f}  (zone visible jusqu'à {nav['y']:.0f}) {'HORS ÉCRAN' if bb['y']+bb['height'] > nav['y'] else ''}")
    print("scroll:", scroll_state(page))
    page.evaluate("() => { const m = document.querySelector('main'); m.scrollTop = m.scrollHeight }"); page.wait_for_timeout(300)
    shot(page, "game_660_scrolled")
    page.locator("button", has_text="Abandonner").click(); page.wait_for_selector("div.fixed"); page.wait_for_timeout(400)
    shot(page, "modal_660")
    print("LOGS", logs)
    browser.close()
