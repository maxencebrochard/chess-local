"""E2E V4 : mode entraîneur, analyse mobile chess.com, accueil gamifié, puzzles flamme.

Usage : python3 e2e/test_v4.py            (dev local, port 5199)
        BASE=https://… python3 e2e/test_v4.py
"""
import json
import os
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:5199")
SHOTS = os.path.join(os.path.dirname(__file__), "shots")
os.makedirs(SHOTS, exist_ok=True)
SETTINGS = json.dumps({"state": {"themeId": "green", "showLegalMoves": True, "playSounds": False,
                                 "chesscomUsername": "", "reviewDepth": "fast"}, "version": 0})
errors = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        errors.append(name)


def sq(page, s):
    page.locator(f"[data-square='{s}']").click()


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # ---------- MODE ENTRAÎNEUR (desktop) ----------
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.add_init_script(f"localStorage.setItem('chess-local-settings', {json.dumps(SETTINGS)})")
    page.on("pageerror", lambda e: print("PAGEERROR:", str(e)[:150]))
    page.goto(f"{BASE}/#/jouer")
    page.wait_for_timeout(1200)
    page.click("button:has-text('Entraîneur')")
    page.wait_for_timeout(300)
    check("[coach] note explicative", page.locator("text=évalue chaque coup").is_visible())
    check("[coach] cadences masquées", page.locator("text=Cadence").count() == 0)
    page.locator("main button", has_text="Noa").first.click()
    page.locator("main button", has_text="Blancs").first.click()
    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_timeout(1000)
    check("[coach] éval bar visible", page.locator("main .bg-neutral-800").first.is_visible())
    check("[coach] bulle d'accueil", len(page.locator(".bg-white").first.inner_text()) > 10)
    check("[coach] pas de pendule", page.locator("main .font-mono.text-xl").count() == 0)
    bubble0 = page.locator(".bg-white").first.inner_text()
    sq(page, "e2"); page.wait_for_timeout(200); sq(page, "e4")
    page.wait_for_timeout(6000)  # éval + réponse bot + éval
    bubble1 = page.locator(".bg-white").first.inner_text()
    check("[coach] bulle commente", bubble1 != bubble0, f"({bubble1[:50]}…)")
    n0 = page.locator("main [data-current]").count()
    check("[coach] deux demi-coups joués", n0 >= 2, f"({n0})")
    page.click("button:has-text('Indication')")
    page.wait_for_timeout(4000)
    check("[coach] badge non classée après Indication", page.locator("text=non classée").is_visible())
    page.click("button:has-text('Annuler')")
    page.wait_for_timeout(1500)
    n1 = page.locator("main [data-current]").count()
    check("[coach] Annuler retire 2 demi-coups", n1 == n0 - 2, f"({n0} -> {n1})")
    page.screenshot(path=f"{SHOTS}/v4_coach.png")
    page.click("button:has-text('Abandonner')")
    page.wait_for_timeout(1200)
    body = page.locator("div.fixed").inner_text()
    check("[coach] fin non classée (pas de delta)", "Classement :" not in body and "non classée" in body, f"({body[:60]}…)")
    ctx.close()

    # ---------- ANALYSE MOBILE ----------
    ctx = browser.new_context(**p.devices["iPhone 14 Pro"], permissions=["clipboard-read", "clipboard-write"])
    page = ctx.new_page()
    page.add_init_script(f"localStorage.setItem('chess-local-settings', {json.dumps(SETTINGS)})")
    page.on("pageerror", lambda e: print("PAGEERROR:", str(e)[:150]))
    page.goto(f"{BASE}/#/analyse")
    page.wait_for_timeout(3000)
    check("[analyse-m] HEvalBar en haut", page.locator("main .bg-neutral-800").first.is_visible())
    check("[analyse-m] lignes compactes", "(" in page.locator("main").inner_text()[:400])
    check("[analyse-m] bandeau Position de départ", page.locator("text=Position de départ").is_visible())
    check("[analyse-m] barre d'actions bas", page.locator("main button", has_text="Explorer").is_visible())
    check("[analyse-m] explorer caché par défaut", not page.locator("text=Explorer d'ouvertures").first.is_visible())
    page.locator("main button", has_text="Explorer").click()
    page.wait_for_timeout(300)
    check("[analyse-m] explorer s'ouvre", page.locator("text=Explorer d'ouvertures").is_visible())
    page.locator("main button:has-text('e4')").last.click()
    page.wait_for_timeout(600)
    check("[analyse-m] bandeau ouverture nommée",
          not page.locator("text=Position de départ").first.is_visible() if page.locator("text=Position de départ").count() else True)
    page.locator("main button", has_text="Précédent").click()
    page.wait_for_timeout(300)
    check("[analyse-m] Précédent", page.locator("main [data-current='true']").count() == 0)
    page.locator("main button", has_text="Suivant").click()
    page.wait_for_timeout(300)
    check("[analyse-m] Suivant", page.locator("main [data-current='true']").count() >= 1)
    page.locator("main button", has_text="Options").click()
    page.wait_for_timeout(300)
    check("[analyse-m] feuille Options", page.locator("text=Copier le PGN").is_visible())
    page.click("text=Copier le PGN")
    page.wait_for_timeout(300)
    clip = page.evaluate("() => navigator.clipboard.readText()")
    check("[analyse-m] Copier PGN via Options", "e4" in clip)
    page.screenshot(path=f"{SHOTS}/v4_analyse_mobile.png")

    # ---------- ACCUEIL ----------
    page.locator("nav a", has_text="Accueil").last.click()
    page.wait_for_timeout(600)
    check("[accueil] carte Problèmes", page.locator("text=Résolvez !").is_visible())
    check("[accueil] cartes stats", page.locator("main a", has_text="Blitz").count() == 1)
    page.screenshot(path=f"{SHOTS}/v4_home.png")
    page.click("text=Résolvez !")
    page.wait_for_timeout(800)
    check("[accueil] Résolvez → puzzles", "puzzles" in page.url)
    page.locator("nav a", has_text="Accueil").last.click()
    page.wait_for_timeout(500)
    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_timeout(600)
    check("[accueil] CTA Jouer → jouer", "jouer" in page.url)

    # ---------- PUZZLES : flamme ----------
    page.locator("nav a", has_text="Puzzles").last.click()
    page.wait_for_selector("text=Classement puzzles", timeout=20000)
    check("[puzzles] flamme visible", page.locator("text=🔥").is_visible())
    page.screenshot(path=f"{SHOTS}/v4_puzzles.png")
    ctx.close()
    browser.close()

print("=" * 40)
print("TOUT PASSE" if not errors else f"ÉCHECS: {errors}")
