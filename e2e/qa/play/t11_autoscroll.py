"""Auto-scroll de <main> provoqué par la liste de coups (scrollIntoView) quand l'écran de partie dépasse la hauteur utile."""
from common import *
with sync_playwright() as p:
    for h, label in ((660, "onglet Safari"), (759, "standalone iPhone 14 Pro avec safe areas simulées (852-59-34)"), (852, "standalone émulé sans safe areas")):
        browser = p.chromium.launch(headless=True)
        opts = dict(p.devices["iPhone 14 Pro"]); opts["viewport"] = {"width": 393, "height": h}
        ctx = browser.new_context(**opts); page = ctx.new_page()
        goto_play(page)
        setup(page, mode="bot", bot="Noa", color="Blancs", tc="10 min")
        s0 = scroll_state(page)
        top0 = page.locator(".boardbox").bounding_box()["y"]
        page.evaluate("""() => { window.__sc = []; const m = document.querySelector('main'); m.addEventListener('scroll', () => window.__sc.push([Math.round(performance.now()), m.scrollTop])) }""")
        tap_move(page, "e2", "e4", pause=120)
        page.wait_for_timeout(150)
        s1 = scroll_state(page)
        wait_ply(page, 2); page.wait_for_timeout(500)
        s2 = scroll_state(page)
        top2 = page.locator(".boardbox").bounding_box()["y"]
        print(f"[393x{h}] {label}")
        print(f"   main scrollHeight/clientHeight: {s0['mainScrollHeight']}/{s0['mainClientHeight']} ; scrollTop avant={s0['mainScrollTop']} après mon coup={s1['mainScrollTop']} après coup du bot={s2['mainScrollTop']}")
        print(f"   haut du board: {top0:.0f} -> {top2:.0f} px ; événements scroll: {page.evaluate('() => window.__sc.length')}")
        shot(page, f"autoscroll_{h}")
        browser.close()
