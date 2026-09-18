"""Passe 9 : un coup exploratoire après bilan détruit-il le bilan et la suite ? Feedback de copie PGN ?"""
import os, sys
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *
PGN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"
def strip(page):
    return page.evaluate("""() => [...document.querySelectorAll('main [data-current]')].filter(e => e.offsetParent).map(e => e.innerText + (e.dataset.current === 'true' ? '*' : ''))""")
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(2000)
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Importer PGN ou FEN").click(); page.wait_for_timeout(300)
    page.fill("textarea", PGN); page.locator("button", has_text="Charger").click(); page.wait_for_timeout(500)
    page.get_by_role("button", name="★ Bilan").click()
    page.wait_for_selector("text=Démarrer le bilan", timeout=240000); page.wait_for_timeout(300)
    page.locator(".fixed header button").click(); page.wait_for_timeout(500)
    page.locator("main [data-current]:visible", has_text="xe5").first.click(); page.wait_for_timeout(600)
    print("avant:", strip(page), "| graphe présent:", page.locator("main svg.cursor-pointer").count(), "| carte précision:", page.locator("text=Précision Blancs").count())
    tap_move(page, "d7", "d6"); page.wait_for_timeout(800)
    print("après 1 coup exploratoire (…d6):", strip(page), "| graphe présent:", page.locator("main svg.cursor-pointer").count(), "| carte précision:", page.locator("text=Précision Blancs").count())
    print("confirmation/annuler proposé:", page.locator("text=/Annuler|variante|Restaurer/i").count())
    shot(page, "t9_after_exploratory_move")
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Copier le PGN").click(); page.wait_for_timeout(150)
    shot(page, "t9_after_copy")
    print("texte visible 150 ms après copie contenant 'copi':", page.evaluate("() => [...document.querySelectorAll('body *')].filter(e => e.offsetParent && e.children.length===0 && /copi/i.test(e.innerText||'')).map(e => e.innerText)"))
    print("LOGS", logs)
    browser.close()
