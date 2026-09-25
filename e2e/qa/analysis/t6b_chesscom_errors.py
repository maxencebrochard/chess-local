"""Passe 6b : pseudo inexistant, hors-ligne, reprise après erreur, popeye232."""
import os, sys, time
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *

with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    reqs = []
    page.on("response", lambda r: reqs.append((r.status, r.url)) if "api.chess.com" in r.url else None)
    page.goto(f"{BASE}/#/import"); page.wait_for_timeout(1000)

    # 1. inexistant
    page.locator("input").first.fill("zz_qa_nobody_98765")
    page.get_by_role("button", name="Connecter").click()
    page.wait_for_timeout(4000)
    print("inexistant -> erreur:", page.locator("p.text-red-300").all_inner_texts(), "| API:", reqs)
    print("pseudo invalide persisté:", page.evaluate("JSON.parse(localStorage.getItem('chess-local-settings')).state.chesscomUsername"))
    print("champ lien visible malgré pseudo invalide:", page.locator("input").count() == 2, "| libellé bouton:", page.locator("main button").first.inner_text())
    shot(page, "t6b_00_unknown_user")

    # 2. popeye232 (pseudo des suites E2E)
    reqs.clear()
    page.locator("input").first.fill("popeye232")
    t0 = time.time()
    page.get_by_role("button", name="Actualiser").click()
    try:
        page.wait_for_selector("main button:has-text('vs ')", timeout=60000)
        print("popeye232 : liste chargée en", round(time.time() - t0, 1), "s, nb =", page.locator("main button:has-text('vs ')").count())
    except Exception:
        print("popeye232 : PAS DE LISTE après 60 s. erreur:", page.locator("p.text-red-300").all_inner_texts(), "texte:", page.locator("main").inner_text()[:300])
    print("API:", reqs)
    shot(page, "t6b_01_popeye")

    # 3. hors-ligne
    reqs.clear()
    ctx.set_offline(True)
    page.locator("input").first.fill("magnuscarlsen")
    page.get_by_role("button", name="Actualiser").click(); page.wait_for_timeout(2500)
    print("hors-ligne -> erreur:", page.locator("p.text-red-300").all_inner_texts(), "| liste encore affichée:", page.locator("main button:has-text('vs ')").count())
    shot(page, "t6b_02_offline")
    # retour en ligne, on retape Actualiser (même pseudo)
    ctx.set_offline(False); page.wait_for_timeout(500)
    reqs.clear()
    page.get_by_role("button", name="Actualiser").click(); page.wait_for_timeout(5000)
    print("retour en ligne + Actualiser -> requêtes:", len(reqs), "| erreur toujours affichée:", page.locator("p.text-red-300").all_inner_texts(), "| liste:", page.locator("main button:has-text('vs ')").count())
    shot(page, "t6b_03_back_online")

    # 4. pseudo avec espace interne et majuscules
    reqs.clear()
    page.locator("input").first.fill("Magnus Carlsen")
    page.get_by_role("button", name="Actualiser").click(); page.wait_for_timeout(6000)
    print("'Magnus Carlsen' -> API:", reqs[:2], "| liste:", page.locator("main button:has-text('vs ')").count(), "| erreur:", page.locator("p.text-red-300").all_inner_texts())
    # 5. hors-ligne à l'ouverture de /analyse depuis import : le tap sur une partie marche hors-ligne ?
    print("LOGS", logs)
    browser.close()
