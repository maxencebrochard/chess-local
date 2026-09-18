"""Écran de configuration : mesures CTA, zones tactiles, troncatures, 852 et 660."""
from common import *

JS_BUTTONS = """() => Array.from(document.querySelectorAll('main button')).map(b => {
  const r = b.getBoundingClientRect()
  return {t: b.innerText.replace(/\\n/g,' ').slice(0,28), w: Math.round(r.width), h: Math.round(r.height), y: Math.round(r.top),
          trunc: b.scrollWidth > b.clientWidth + 1}
})"""

with sync_playwright() as p:
    for standalone in (True, False):
        tag = "852" if standalone else "660"
        browser, ctx, page, logs = open_mobile(p, standalone=standalone)
        goto_play(page)
        vp = page.viewport_size
        print(f"\n===== viewport {vp} =====")
        print("overflow_x", overflow_x(page))
        st = scroll_state(page)
        print("scroll", st)
        cta = page.get_by_role("button", name="Jouer", exact=True).bounding_box()
        nav = page.locator("nav").last.bounding_box()
        print("CTA", cta, "nav", nav)
        print("CTA bottom", cta["y"] + cta["height"], "visible zone bottom (nav top)", nav["y"])
        btns = page.evaluate(JS_BUTTONS)
        for b in btns:
            flag = " <44" if b["h"] < 44 else ""
            print(f"  {b['t']!r:32} {b['w']}x{b['h']} y={b['y']}{flag}{' TRUNC' if b['trunc'] else ''}")
        navlinks = page.evaluate("""() => Array.from(document.querySelectorAll('nav:last-of-type a')).map(a => {const r=a.getBoundingClientRect(); return [a.innerText.replace(/\\n/g,' '), Math.round(r.width), Math.round(r.height)]})""")
        print("nav links", navlinks)
        shot(page, f"setup_{tag}_top")
        # mode coach
        page.locator("main button", has_text="Entraîneur").first.click(); page.wait_for_timeout(300)
        cta = page.get_by_role("button", name="Jouer", exact=True).bounding_box()
        print("COACH CTA bottom", cta["y"] + cta["height"], "nav top", nav["y"])
        shot(page, f"setup_{tag}_coach")
        # retour bot : cadence restaurée ?
        page.locator("main button", has_text="Contre un bot").first.click(); page.wait_for_timeout(300)
        print("après coach->bot, classement:", page.locator("text=Mon classement").inner_text())
        # local
        page.locator("main button", has_text="2 joueurs").first.click(); page.wait_for_timeout(300)
        cta = page.get_by_role("button", name="Jouer", exact=True).bounding_box()
        print("LOCAL CTA bottom", cta["y"] + cta["height"], "nav top", nav["y"])
        shot(page, f"setup_{tag}_local")
        page.locator("main button", has_text="Contre un bot").first.click(); page.wait_for_timeout(200)
        # scroll en bas
        page.evaluate("() => { const m = document.querySelector('main'); m.scrollTop = m.scrollHeight }")
        page.wait_for_timeout(300)
        shot(page, f"setup_{tag}_bottom")
        # Persistance du choix : sélectionne Maximus/Noirs/3|2, change d'onglet, reviens
        page.locator("main button", has_text="Maximus").first.click()
        page.locator("main button", has_text="Noirs").first.click()
        page.locator("main button", has_text="3 | 2").first.click()
        page.locator("nav a", has_text="Archive").last.click(); page.wait_for_timeout(500)
        page.locator("nav a", has_text="Jouer").last.click(); page.wait_for_timeout(700)
        sel = page.evaluate("""() => Array.from(document.querySelectorAll('main button')).filter(b => b.className.includes('border-accent')).map(b => b.innerText.replace(/\\n/g,' '))""")
        print("sélection après aller-retour:", sel)
        print("logs", logs)
        browser.close()
