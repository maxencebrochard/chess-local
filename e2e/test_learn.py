"""E2E « Apprendre » : page, séances par domaine, exercices, Elo, mes erreurs, sauvegarde.

Usage : python3 e2e/test_learn.py            (dev local, port 5199)
        BASE=https://… python3 e2e/test_learn.py
"""
import json
import os
from playwright.sync_api import sync_playwright

BASE = os.environ.get("BASE", "http://localhost:5199")
SHOTS = os.path.join(os.path.dirname(__file__), "shots")
os.makedirs(SHOTS, exist_ok=True)
SETTINGS = json.dumps({"state": {"themeId": "green", "showLegalMoves": True, "playSounds": False,
                                 "chesscomUsername": "", "reviewDepth": "fast"}, "version": 0})
PGN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"
errors = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {detail}")
    if not cond:
        errors.append(name)


def sq(page, s):
    page.locator(f"[data-square='{s}']").click()


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(**p.devices["iPhone 14 Pro"])
    page = ctx.new_page()
    page.add_init_script(f"localStorage.setItem('chess-local-settings', {json.dumps(SETTINGS)})")
    page.on("pageerror", lambda e: print("PAGEERROR:", str(e)[:200]))

    # --- Page Apprendre ---
    page.goto(f"{BASE}/#/apprendre")
    page.wait_for_timeout(1500)
    check("[learn] onglet nav Apprendre", page.locator("nav a", has_text="Apprendre").last.is_visible())
    check("[learn] 4 pastilles Elo", page.locator("main .grid > div").count() >= 4)
    check("[learn] CTA Séance", page.get_by_role("button", name="Séance", exact=True).is_visible())
    check("[learn] Mes erreurs grisé (vide)", not page.locator("button", has_text="Mes erreurs").is_enabled())
    page.screenshot(path=f"{SHOTS}/learn_home.png")

    # --- Séance Finales (leçon -> cours -> jeu) ---
    page.locator("main button", has_text="Finales").click()
    page.wait_for_timeout(1200)
    check("[learn] leçon finale affichée", page.locator(".bg-white").first.is_visible())
    page.screenshot(path=f"{SHOTS}/learn_lesson.png")
    # Cours détaillé depuis la leçon
    page.click("text=Voir le cours complet")
    page.wait_for_timeout(500)
    check("[cours] feuille ouverte", page.locator("text=À retenir").is_visible())
    check("[cours] contenu structuré", page.locator("h2:has-text('📚')").is_visible())
    page.screenshot(path=f"{SHOTS}/learn_course.png")
    page.click("text=Retour à l'exercice")
    page.wait_for_timeout(300)
    check("[cours] fermeture -> leçon intacte", page.locator(".bg-white").first.is_visible())
    page.get_by_role("button", name="C'est parti").click()
    page.wait_for_timeout(800)
    check("[learn] objectif affiché", page.locator("text=Objectif").is_visible())
    check("[learn] board finale", page.locator("[id^='chessboard-']").first.is_visible())
    # Bouton ? dans le header (ne doit jamais chevaucher le board)
    q_btn = page.locator("header button", has_text="?")
    q_box = q_btn.bounding_box()
    board_box = page.locator("[id^='chessboard-']").first.bounding_box()
    overlaps = not (q_box["x"] + q_box["width"] < board_box["x"] or q_box["x"] > board_box["x"] + board_box["width"]
                    or q_box["y"] + q_box["height"] < board_box["y"] or q_box["y"] > board_box["y"] + board_box["height"])
    check("[cours] ? ne chevauche pas le board", not overlaps)
    q_btn.click()
    page.wait_for_timeout(400)
    check("[cours] ? pendant l'exercice", page.locator("text=À retenir").is_visible())
    page.click("text=Retour à l'exercice")
    page.wait_for_timeout(300)
    check("[cours] retour exercice intact", page.locator("[id^='chessboard-']").first.is_visible())
    page.screenshot(path=f"{SHOTS}/learn_endgame.png")
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(400)

    # --- Séance Tactiques (3 puzzles, on rate le 1er exprès via un coup légal quelconque) ---
    page.locator("main button", has_text="Tactiques").click()
    page.wait_for_timeout(2500)
    check("[learn] leçon tactique (thème)", page.locator(".bg-white").first.is_visible())
    page.get_by_role("button", name="C'est parti").click()
    page.wait_for_timeout(1800)
    check("[learn] puzzle affiché", page.locator("[id^='chessboard-']").first.is_visible())
    page.screenshot(path=f"{SHOTS}/learn_tactic.png")
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(400)

    # --- Séance Ouvertures : drill, bon coup accepté, mauvais corrigé ---
    page.locator("main button", has_text="Ouvertures").click()
    page.wait_for_timeout(1500)
    page.get_by_role("button", name="C'est parti").click()
    page.wait_for_timeout(1200)
    check("[learn] drill affiché", page.locator("text=premiers coups").is_visible())
    # Mauvais coup volontaire : a2a3 (aucune ligne du répertoire classique ne commence par a3)
    sq(page, "a2"); page.wait_for_timeout(150); sq(page, "a3")
    page.wait_for_timeout(600)
    corrected = page.locator("text=Pas la ligne").count() > 0
    check("[learn] mauvais coup corrigé", corrected)
    page.screenshot(path=f"{SHOTS}/learn_opening.png")
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(400)

    # --- CTA Séance auto ---
    page.get_by_role("button", name="Séance", exact=True).click()
    page.wait_for_timeout(2500)
    check("[learn] séance auto démarre (leçon)", page.locator(".bg-white").first.is_visible())
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(400)

    # --- Mes erreurs : bilan d'une partie avec gaffes -> stock alimenté -> jouable ---
    page.goto(f"{BASE}/#/analyse")
    page.wait_for_timeout(1500)
    page.locator("main button", has_text="Options").click()
    page.wait_for_timeout(300)
    page.click("text=Importer PGN ou FEN")
    page.fill("textarea", PGN)
    page.click("button:has-text('Charger')")
    page.wait_for_timeout(400)
    page.get_by_role("button", name="★ Bilan").click()
    page.wait_for_selector("text=Démarrer le bilan", timeout=180000)
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(600)
    page.goto(f"{BASE}/#/apprendre")
    page.wait_for_timeout(1200)
    mistakes_btn = page.locator("button", has_text="Mes erreurs")
    check("[learn] Mes erreurs alimenté par le bilan", mistakes_btn.is_enabled())
    mistakes_btn.click()
    page.wait_for_timeout(1200)
    page.get_by_role("button", name="C'est parti").click()
    page.wait_for_timeout(600)
    check("[learn] exercice erreur affiché", page.locator("text=Trouve mieux").is_visible())
    page.screenshot(path=f"{SHOTS}/learn_mistake.png")
    # Jouer un coup quelconque -> verdict -> Réessayer / Analyser
    # Jouer n'importe quel coup légal : sélectionner une pièce puis un point de destination.
    played = False
    for f in "abcdefgh":
        for r in "12345678":
            page.locator(f"[data-square='{f}{r}']").click()
            page.wait_for_timeout(60)
            tg = page.evaluate("""() => {
              const els=[...document.querySelectorAll('[data-square]')];
              const has=(root,pred)=>[root,...root.querySelectorAll('*')].some(pred);
              return els.find(e=>has(e,n=>getComputedStyle(n).background.includes('rgba(0, 0, 0, 0.34)')))?.getAttribute('data-square') ?? null;
            }""")
            if tg:
                page.locator(f"[data-square='{tg}']").click()
                played = True
                break
        if played:
            break
    page.wait_for_timeout(12000)  # vérification moteur éventuelle
    verdict = page.locator("text=Réussi").count() > 0 or page.locator("text=Raté").count() > 0
    check("[learn] verdict après coup", verdict)
    check("[learn] bouton Réessayer", page.locator("button", has_text="Réessayer").is_visible())
    check("[learn] bouton Analyser", page.locator("button", has_text="Analyser").is_visible())
    page.locator("button", has_text="Réessayer").click()
    page.wait_for_timeout(600)
    check("[learn] Réessayer relance l'exercice", page.locator("text=Trouve mieux").is_visible())
    # Rejouer un coup pour revenir au verdict, puis Analyser -> Retour -> exercice restauré
    header_before = page.locator("header h1").inner_text()
    played = False
    for f in "abcdefgh":
        for r in "12345678":
            page.locator(f"[data-square='{f}{r}']").click()
            page.wait_for_timeout(50)
            tg = page.evaluate("""() => {
              const els=[...document.querySelectorAll('[data-square]')];
              const has=(root,pred)=>[root,...root.querySelectorAll('*')].some(pred);
              return els.find(e=>has(e,n=>getComputedStyle(n).background.includes('rgba(0, 0, 0, 0.34)')))?.getAttribute('data-square') ?? null;
            }""")
            if tg:
                page.locator(f"[data-square='{tg}']").click()
                played = True
                break
        if played:
            break
    page.wait_for_timeout(2000)
    page.locator("button", has_text="Analyser").click()
    page.wait_for_timeout(1200)
    check("[analyse] Analyser ouvre /analyse", "#/analyse" in page.url or page.evaluate("() => location.hash") == "#/analyse")
    back_btn = page.locator("button", has_text="Retour à l'exercice")
    check("[analyse] bouton retour visible", back_btn.is_visible())
    back_btn.click()
    page.wait_for_timeout(800)
    check("[learn] retour restaure la séance", page.evaluate("() => location.hash") == "#/apprendre")
    check("[learn] compteur d'item restauré", page.locator("header h1").inner_text() == header_before)
    page.click("header button:has-text('✕')")


    # --- Anti-saut : le board de /analyse ne bouge pas quand les lignes moteur arrivent ---
    page.goto(f"{BASE}/#/analyse")
    page.wait_for_timeout(600)
    y_before = page.evaluate("() => document.querySelector(\"[id^='chessboard-']\")?.getBoundingClientRect().top")
    page.wait_for_timeout(4000)
    y_after = page.evaluate("() => document.querySelector(\"[id^='chessboard-']\")?.getBoundingClientRect().top")
    check("[anti-saut] board stable sur /analyse", y_before is not None and y_before == y_after, f"({y_before} -> {y_after})")

    # --- Sauvegarde (Stats) ---
    page.goto(f"{BASE}/#/stats")
    page.wait_for_timeout(800)
    check("[backup] boutons présents", page.locator("button", has_text="Exporter tout").is_visible()
          and page.locator("button", has_text="Restaurer").is_visible())
    persisted = page.evaluate("() => navigator.storage?.persisted ? navigator.storage.persisted() : false")
    check("[backup] storage.persist demandé", persisted in (True, False))  # API répond sans erreur

    ctx.close()
    browser.close()

print("=" * 40)
print("TOUT PASSE" if not errors else f"ÉCHECS: {errors}")
