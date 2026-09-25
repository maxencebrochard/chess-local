"""(a) effet d'un retour arrière (= ce que fait le swipe-back iOS) pendant une partie : la partie survit-elle ?
(b) faisabilité : si la navigation par onglets REMPLACE l'entrée d'historique, history.length reste-t-il constant ?"""
import sys
sys.path.insert(0, "e2e/qa/touch")
from tlib import *

with sync_playwright() as p:
    print("=== (a) history.back() pendant une partie (standalone 852)")
    browser, ctx, page, logs = open_mobile_t(p, standalone=True); install(page)
    page.goto(f"{BASE}/#/"); page.wait_for_timeout(800)
    page.locator("nav a", has_text="Jouer").last.click(); page.wait_for_timeout(800)
    page.locator("main button", has_text="Noa").first.click(); page.locator("main button", has_text="Blancs").first.click()
    page.get_by_role("button", name="Jouer", exact=True).click(); page.wait_for_timeout(1500)
    r = gesture(page, *sq_center(page, "e2"), *sq_center(page, "e4")); page.wait_for_timeout(3000)
    before = snap(page); print("   partie en cours : e4 =", piece_on(page, "e4"), "| hash", before["hash"], "| history.length", before["historyLength"], "| nb pièces déplacées vs départ:", sum(1 for k in ("e2",) if k not in before["pos"]))
    page.evaluate("history.back()"); page.wait_for_timeout(1200)
    mid = snap(page); print("   après history.back() : hash", mid["hash"], "| board présent:", mid["boardTop"] is not None)
    shot(page, "t10_a_apres_back")
    page.evaluate("history.forward()"); page.wait_for_timeout(1500)
    after = snap(page)
    print("   après history.forward() (retour sur /jouer) : hash", after["hash"], "| board présent:", after["boardTop"] is not None, "| e4 =", piece_on(page, "e4") if after["boardTop"] is not None else None, "| écran de configuration affiché:", page.locator("text=Adversaire").count() > 0)
    shot(page, "t10_a_apres_forward")
    browser.close()

    print("=== (b) émulation 'onglets en replace' : pushState redirigé vers replaceState")
    browser, ctx, page, logs = open_mobile_t(p, standalone=True); install(page)
    page.add_init_script("history.pushState = history.replaceState.bind(history)")
    page.goto(f"{BASE}/#/"); page.wait_for_timeout(800); h0 = page.evaluate("history.length"); seen = []
    for label, expect in [("Jouer", "#/jouer"), ("Puzzles", "#/puzzles"), ("Analyse", "#/analyse"), ("Stats", "#/stats"), ("Apprendre", "#/apprendre")]:
        page.locator("nav a", has_text=label).last.click(); page.wait_for_timeout(500); seen.append((page.evaluate("location.hash") == expect))
    print(f"   history.length : {h0} -> {page.evaluate('history.length')} après 5 taps d'onglets | toutes les routes atteintes: {all(seen)}")
    browser.close()
