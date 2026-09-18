from common import *
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=False)
    goto_play(page)
    setup(page, mode="coach", bot="Noa", color="Blancs")
    tap_move(page, "e2", "e4"); wait_ply(page, 2); page.wait_for_timeout(1500)
    strip = page.locator("main [data-current]").first.bounding_box()
    bar = page.locator("main .border-t").first.bounding_box()
    board = page.locator(".boardbox").bounding_box()
    inner = page.evaluate("() => { const e = document.querySelector('main .overflow-y-auto'); return {sh: e.scrollHeight, ch: e.clientHeight, st: e.scrollTop} }")
    print("coach 660 : board bas =", board["y"] + board["height"], "| bouton de coup y =", strip["y"], "..", strip["y"] + strip["height"], "| barre d'actions haut =", bar["y"], "| zone interne:", inner)
    shot(page, "coach_660_strip")
    browser.close()
