"""TOUCH-8 : après 'Précédent', quels glyphes le voile de promotion propose-t-il ? (lecture DOM, pas interprétation de capture)"""
import sys
sys.path.insert(0, "e2e/qa/touch")
from tlib import *
G = "() => [...document.querySelectorAll('.absolute.inset-0.z-20 button')].map(b => b.textContent + ' U+' + b.textContent.codePointAt(0).toString(16).toUpperCase())"
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile_t(p, standalone=True); install(page)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1500)
    for m in ["h2h4", "g7g5", "h4g5", "h7h6", "g5h6", "f8g7", "h6g7", "g8f6"]:
        tap_move(page, m[:2], m[2:], pause=180)
    tap_move(page, "g7", "h8"); page.wait_for_timeout(300)
    print("glyphes à l'ouverture (pion BLANC, trait aux blancs) :", page.evaluate(G), "(blancs = U+2655..2658, noirs = U+265B..265E)")
    page.locator("main button", has_text="Précédent").click(); page.wait_for_timeout(400)
    print("glyphes après 'Précédent' (trait aux noirs)        :", page.evaluate(G))
    browser.close()
