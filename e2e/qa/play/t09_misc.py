"""Divers : perte de surbrillance après désélection, a11y, modale en 375 px, dérive pendule sous charge CPU."""
import time
from common import *


def bg_of(page, sq):
    return page.evaluate("""(sq) => { const e = document.querySelector(`[data-square='${sq}']`); return getComputedStyle(e).backgroundColor + ' | ' + getComputedStyle(e).backgroundImage.slice(0, 40) }""", sq)


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    # ---------- H : surbrillance du dernier coup perdue après sélection/désélection ----------
    goto_play(page)
    setup(page, mode="local", tc="Illimité")
    tap_move(page, "e2", "e4"); tap_move(page, "d7", "d5")
    print("H d5 avant sélection :", bg_of(page, "d5"))
    shot(page, "hl_before")
    tap_square(page, "e4"); page.wait_for_timeout(250)
    print("H d5 pendant sélection de e4 (cible de capture) :", bg_of(page, "d5"))
    shot(page, "hl_selected")
    tap_square(page, "e4"); page.wait_for_timeout(250)
    print("H d5 après désélection :", bg_of(page, "d5"), " | d7 :", bg_of(page, "d7"))
    shot(page, "hl_after_deselect")
    print("H logs:", logs)

    # ---------- A : a11y ----------
    a11y = page.evaluate("""() => Array.from(document.querySelectorAll('main button')).filter(b => ['⏮','◀','▶','⏭'].includes(b.innerText.trim())).map(b => [b.innerText.trim(), b.getAttribute('aria-label'), b.title])""")
    print("A boutons de navigation (texte, aria-label, title):", a11y)
    page.locator("button", has_text="Abandonner").click(); page.wait_for_selector("div.fixed"); page.wait_for_timeout(300)
    modal = page.evaluate("""() => { const m = document.querySelector('div.fixed'); return {role: m.getAttribute('role'), ariaModal: m.getAttribute('aria-modal'), innerRole: m.firstElementChild.getAttribute('role'), activeInModal: m.contains(document.activeElement)} }""")
    print("A modale:", modal)
    page.keyboard.press("Escape"); page.wait_for_timeout(200)
    print("A Échap ferme la modale ?", page.locator("div.fixed").count() == 0)
    browser.close()

    # ---------- S : iPhone SE / mini 375 px ----------
    browser = p.chromium.launch(headless=True)
    opts = dict(p.devices["iPhone 14 Pro"]); opts["viewport"] = {"width": 375, "height": 667}
    ctx = browser.new_context(**opts); page = ctx.new_page()
    goto_play(page)
    setup(page, mode="bot", bot="Noa", color="Blancs", tc="10 min")
    page.locator("button", has_text="Abandonner").click(); page.wait_for_selector("div.fixed"); page.wait_for_timeout(400)
    mb = page.locator("div.fixed > div").first.bounding_box()
    print("S modale en 375 px :", mb, "-> déborde ?", mb["x"] < 0 or mb["x"] + mb["width"] > 375)
    shot(page, "modal_375")
    browser.close()

    # ---------- C : dérive de la pendule sous charge CPU ----------
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    goto_play(page)
    cdp = ctx.new_cdp_session(page)
    page.locator("main button", has_text="Noa").first.click()
    page.locator("main button", has_text="3 min").first.click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_selector("[data-square='e2']")
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 6})
    t0 = time.time(); c0 = clock_texts(page)
    # charge : bouge la souris / sélectionne des pièces pendant 20 s (rerenders)
    while time.time() - t0 < 20:
        tap_square(page, "e2"); page.wait_for_timeout(150)
        tap_square(page, "e2"); page.wait_for_timeout(150)
    c1 = clock_texts(page); wall = time.time() - t0
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    print(f"C CPU x6 pendant {wall:.1f}s de temps mur : pendule {c0} -> {c1}")
    browser.close()
