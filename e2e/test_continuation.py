"""E2E « Aller plus loin » (F3) : après un puzzle d'Apprendre (tactique ou stratégie), reprendre
la position contre Stockfish ou voir la suite du moteur, sans rien changer au score.

`puzzles.json` est remplacé par une fixture (route Playwright, service worker bloqué pour que la
route s'applique aussi au build de prod) : deux puzzles déterministes portant tous les thèmes.

Usage : npm run test:e2e -- --suite continuation
"""
import json

from helpers import SHOTS, BASE, Checker, desktop_context, mobile_context, overflow_x

ck = Checker("continuation")
check = ck.check

# A : finale, fourchette de cavalier (amorce ...Ke8, puis Nc7+ Kd7 Nxa8). Fin non terminale.
PUZZLE_A = ["F3A", "r4k2/5p1p/6p1/3N4/8/6P1/P4PKP/8 b - - 0 1", "f8e8 d5c7 e8d7 c7a8"]
# B : mat en 1 (amorce ...Nc3, puis Ra8#). Fin terminale : rien à prolonger.
PUZZLE_B = ["F3B", "6k1/5ppp/8/8/4n3/8/5PPP/R5K1 b - - 0 1", "e4c3 a1a8"]
# Tous les thèmes tactiques (src/lib/themes.ts) et stratégiques (src/data/strategy.json) : quelle
# que soit la carte ou le thème tiré par buildSession, le seul puzzle de la fixture est choisi.
THEMES = (
    "fork pin skewer discoveredAttack mateIn1 mateIn2 mateIn3 backRankMate hangingPiece sacrifice "
    "deflection attraction promotion trappedPiece intermezzo defensiveMove rookEndgame pawnEndgame "
    "zugzwang exposedKing discoveredCheck advancedPawn kingsideAttack quietMove"
)

DIALOG = "[data-continuation]"
MAIN_BOARD = "[id^='chessboard-']"


def fixture(ctx, puzzle):
    body = json.dumps([[puzzle[0], puzzle[1], puzzle[2], 1000, THEMES]])
    ctx.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))


def board_root(page, in_dialog):
    """Racine de l'échiquier visé : celui du calque, ou celui de l'exercice (le premier du DOM)."""
    return page.locator(f"{DIALOG} {MAIN_BOARD}").first if in_dialog else page.locator(MAIN_BOARD).first


def piece(page, square, in_dialog=False):
    el = board_root(page, in_dialog).locator(f"[data-square='{square}'] [data-piece]")
    return el.first.get_attribute("data-piece") if el.count() else None


def tap(page, square, in_dialog=False):
    box = board_root(page, in_dialog).locator(f"[data-square='{square}']").first.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    if page.viewport_size["width"] > 800:  # contexte desktop : souris, pas d'écran tactile
        page.mouse.click(x, y)
    else:
        page.touchscreen.tap(x, y)


def move(page, frm, to, in_dialog=False):
    tap(page, frm, in_dialog)
    page.wait_for_timeout(200)
    tap(page, to, in_dialog)
    page.wait_for_timeout(250)


def wait_until(page, predicate, timeout=30000):
    waited = 0
    while waited < timeout:
        if predicate():
            return True
        page.wait_for_timeout(200)
        waited += 200
    return predicate()


def strip_sans(page):
    return page.locator(f"{DIALOG} [data-current]").all_inner_texts()


def strip_count(page):
    return page.locator(f"{DIALOG} [data-current]").count()


def idb_score(page, key):
    """(Elo du domaine, nombre de tentatives enregistrées) lus directement dans IndexedDB."""
    return page.evaluate(
        """(key) => new Promise((resolve, reject) => {
          const req = indexedDB.open('chess-local')
          req.onerror = () => reject(req.error)
          req.onsuccess = () => {
            const db = req.result
            const tx = db.transaction(['ratings', 'learnSessions'], 'readonly')
            const r = tx.objectStore('ratings').get(key)
            const n = tx.objectStore('learnSessions').count()
            tx.oncomplete = () => { db.close(); resolve([r.result ? r.result.value : null, n.result]) }
            tx.onerror = () => reject(tx.error)
          }
        })""",
        key,
    )


def start_domain(page, label):
    page.goto(f"{BASE}/#/apprendre")
    page.wait_for_timeout(1200)
    page.locator("main button", has_text=label).click()
    ck.appears(f"[{label}] leçon affichée", page, "button:has-text(\"C'est parti\")", timeout=20000)
    page.get_by_role("button", name="C'est parti").click()


def board_fits(page, scope_selector, name):
    vh = page.viewport_size["height"]
    box = page.locator(f"{scope_selector} {MAIN_BOARD}").first.bounding_box()
    check(f"{name} : échiquier entier à l'écran", box is not None and box["y"] >= 0 and box["y"] + box["height"] <= vh + 1, f"({box})")
    check(f"{name} : aucun débordement horizontal", overflow_x(page) == 0)


def suite(p):
    browser = p.chromium.launch(headless=True)

    # ===== iPhone 14 Pro standalone, puzzle A =====
    ctx = mobile_context(p, browser, ck, standalone=True, service_workers="block")
    fixture(ctx, PUZZLE_A)
    page = ctx.new_page()

    # --- Tactique A réussie ---
    start_domain(page, "Tactiques")
    check("[fixture] puzzle A chargé (cavalier d5, roi f8)", wait_until(page, lambda: piece(page, "d5") == "wN", 5000)
          and piece(page, "a8") == "bR")
    check("[tactique] amorce jouée (...Ke8)", wait_until(page, lambda: piece(page, "e8") == "bK", 5000))
    move(page, "d5", "c7")
    check("[tactique] réponse ...Kd7", wait_until(page, lambda: piece(page, "d7") == "bK", 5000))
    move(page, "c7", "a8")
    ck.appears("[tactique] verdict Réussi", page, "text=Réussi", timeout=5000)
    page.wait_for_timeout(500)
    score_before = idb_score(page, "learn-tactic")
    check("[score] tentative tactique enregistrée", score_before[1] == 1, f"({score_before})")
    play_btn = page.get_by_role("button", name="Jouer contre le moteur")
    check("[aller plus loin] bouton Jouer contre le moteur visible", play_btn.count() == 1 and play_btn.is_visible())
    check("[aller plus loin] bouton Voir la suite visible", page.get_by_role("button", name="Voir la suite").count() == 1)
    page.screenshot(path=f"{SHOTS}/continuation_verdict.png")

    # --- Jouer contre le moteur depuis la fin de la solution ---
    play_btn.click()
    ck.appears("[jouer] calque Contre Stockfish ouvert", page, DIALOG, timeout=5000)
    check("[jouer] position de départ = fin de la solution (cavalier en a8)", piece(page, "a8", True) == "wN"
          and piece(page, "d7", True) == "bK")
    check("[jouer] le moteur, au trait, joue le premier", wait_until(page, lambda: strip_count(page) >= 1, 30000))
    ck.appears("[jouer] à toi de jouer", page, f"{DIALOG} >> text=À toi de jouer", timeout=30000)
    check("[jouer] éval affichée", page.locator(f"{DIALOG} .bg-neutral-800 span").first.inner_text().strip() not in ("", "0,00"),
          f"({page.locator(f'{DIALOG} .bg-neutral-800 span').first.inner_text()})")
    board_fits(page, DIALOG, "[jouer 393x852]")
    page.screenshot(path=f"{SHOTS}/continuation_play_mobile.png")
    move(page, "a2", "a3", True)
    check("[jouer] coup du joueur accepté", piece(page, "a3", True) == "wP")
    check("[jouer] le moteur répond", wait_until(page, lambda: strip_count(page) >= 3, 30000), f"({strip_count(page)} coups)")
    ck.appears("[jouer] de nouveau à toi", page, f"{DIALOG} >> text=À toi de jouer", timeout=30000)
    page.locator(f"{DIALOG} button", has_text="Annuler").click()
    page.wait_for_timeout(400)
    check("[jouer] Annuler reprend le coup et la réponse", strip_count(page) == 1 and piece(page, "a2", True) == "wP",
          f"({strip_count(page)} coups)")
    page.locator(f"{DIALOG} button", has_text="Abandonner").click()
    ck.appears("[jouer] résultat après abandon", page, f"{DIALOG} >> text=Tu as abandonné", timeout=3000)
    page.screenshot(path=f"{SHOTS}/continuation_resign.png")
    heights = [page.locator(f"{DIALOG} button", has_text=t).first.bounding_box()["height"] for t in ("Rejouer", "Retour à l'exercice")]
    check("[jouer] boutons de fin sur une seule ligne", all(h < 48 for h in heights), f"({heights})")
    page.locator(f"{DIALOG} button", has_text="Rejouer").click()
    page.wait_for_timeout(300)
    check("[jouer] Rejouer repart de la fin de la solution", piece(page, "a8", True) == "wN")
    check("[jouer] le moteur rejoue le premier", wait_until(page, lambda: strip_count(page) >= 1, 30000))
    page.locator(f"{DIALOG} header button", has_text="Exercice").click()
    page.wait_for_timeout(400)
    check("[retour] calque fermé", page.locator(DIALOG).count() == 0)
    check("[retour] verdict intact", page.locator("text=Réussi").first.is_visible())
    check("[score] Elo et tentatives inchangés après le prolongement", idb_score(page, "learn-tactic") == score_before,
          f"({score_before} -> {idb_score(page, 'learn-tactic')})")

    # --- Analyser depuis le calque, puis retour à la séance ---
    page.get_by_role("button", name="Jouer contre le moteur").click()
    ck.appears("[analyser] moteur a joué", page, f"{DIALOG} >> text=À toi de jouer", timeout=30000)
    move(page, "a2", "a3", True)
    check("[analyser] réponse du moteur", wait_until(page, lambda: strip_count(page) >= 3, 30000))
    ck.appears("[analyser] à toi", page, f"{DIALOG} >> text=À toi de jouer", timeout=30000)
    played = strip_sans(page)
    page.locator(f"{DIALOG} button", has_text="Analyser").click()
    check("[analyser] /analyse ouvert", wait_until(page, lambda: page.evaluate("() => location.hash").startswith("#/analyse"), 5000))
    ck.appears("[analyser] bouton retour", page, "button:has-text(\"Retour à l'exercice\")", timeout=5000)
    check("[analyser] coups de la suite chargés (pion a3, cavalier a8)",
          wait_until(page, lambda: piece(page, "a3") == "wP" and piece(page, "a8") == "wN", 5000))
    page.locator("button", has_text="Retour à l'exercice").click()
    check("[analyser] séance restaurée", wait_until(page, lambda: page.evaluate("() => location.hash") == "#/apprendre", 5000))
    ck.appears("[analyser] le calque se rouvre sur la même partie", page, DIALOG, timeout=5000)
    check("[analyser] coups de la partie restaurés à l'identique", strip_sans(page) == played, f"({played} -> {strip_sans(page)})")
    check("[analyser] à toi de jouer après restauration", page.locator(f"{DIALOG} >> text=À toi de jouer").count() > 0)
    page.locator(f"{DIALOG} header button", has_text="Exercice").click()
    page.wait_for_timeout(400)
    check("[analyser] verdict Réussi intact", page.locator("text=Réussi").first.is_visible())
    check("[analyser] Aller plus loin encore proposé après restauration",
          page.get_by_role("button", name="Jouer contre le moteur").count() == 1)
    check("[score] toujours inchangé après l'aller-retour", idb_score(page, "learn-tactic") == score_before)
    page.click("header button:has-text('✕')")
    page.wait_for_timeout(400)

    # --- Stratégie A ratée : voir le plan ---
    start_domain(page, "Stratégie")
    check("[stratégie] amorce jouée", wait_until(page, lambda: piece(page, "e8") == "bK", 5000))
    strat_before = idb_score(page, "learn-strategy")
    move(page, "a2", "a3")
    ck.appears("[stratégie] verdict Raté", page, "text=Raté", timeout=5000)
    page.wait_for_timeout(500)
    strat_after_fail = idb_score(page, "learn-strategy")
    # Raté restauré : l'index d'avancement survit à l'aller-retour vers l'analyseur.
    page.locator("button", has_text="Analyser").click()
    ck.appears("[stratégie] analyseur ouvert", page, "button:has-text(\"Retour à l'exercice\")", timeout=5000)
    page.locator("button", has_text="Retour à l'exercice").click()
    ck.appears("[stratégie] verdict Raté restauré", page, "text=Raté", timeout=5000)
    check("[score] l'échec est compté une fois", strat_after_fail[1] == strat_before[1] + 1, f"({strat_before} -> {strat_after_fail})")
    plan_btn = page.get_by_role("button", name="Voir le plan")
    check("[plan] bouton Voir le plan visible", plan_btn.count() == 1 and plan_btn.is_visible())
    plan_btn.click()
    ck.appears("[plan] calque ouvert", page, DIALOG, timeout=5000)
    check("[plan] ligne du moteur d'au moins 4 demi-coups", wait_until(page, lambda: strip_count(page) >= 4, 30000),
          f"({strip_count(page)})")
    page.locator(f"{DIALOG} button[aria-label='Début']").click()
    page.wait_for_timeout(300)
    check("[plan] départ = position où l'exercice s'est arrêté (cavalier d5, roi e8)",
          piece(page, "d5", True) == "wN" and piece(page, "e8", True) == "bK" and piece(page, "a2", True) == "wP")
    page.locator(f"{DIALOG} button[aria-label='Coup suivant']").click()
    page.wait_for_timeout(300)
    check("[plan] Coup suivant fait avancer la position", piece(page, "d5", True) != "wN" or piece(page, "e8", True) != "bK"
          or piece(page, "a2", True) != "wP")
    board_fits(page, DIALOG, "[plan 393x852]")
    page.screenshot(path=f"{SHOTS}/continuation_plan_mobile.png")
    page.locator(f"{DIALOG} button", has_text="Jouer à partir d'ici").click()
    ck.appears("[plan] passe en mode jouer", page, f"{DIALOG} button:has-text('Abandonner')", timeout=5000)
    page.locator(f"{DIALOG} header button", has_text="Exercice").click()
    page.wait_for_timeout(400)
    check("[score] stratégie inchangée après le plan", idb_score(page, "learn-strategy") == strat_after_fail)
    ctx.close()

    # ===== iPhone onglet Safari 393x660, puzzle B (mat en 1) =====
    ctx = mobile_context(p, browser, ck, service_workers="block")
    fixture(ctx, PUZZLE_B)
    page = ctx.new_page()
    start_domain(page, "Tactiques")
    check("[mat] amorce ...Nc3", wait_until(page, lambda: piece(page, "c3") == "bN", 5000))
    move(page, "h2", "h3")
    ck.appears("[mat] verdict Raté", page, "text=Raté", timeout=5000)
    page.wait_for_timeout(300)
    check("[mat 393x660] verdict : aucun débordement horizontal", overflow_x(page) == 0)
    page.screenshot(path=f"{SHOTS}/continuation_verdict_660.png")
    page.get_by_role("button", name="Jouer contre le moteur").click()
    ck.appears("[mat] calque ouvert à la position du mat en 1", page, f"{DIALOG} >> text=À toi de jouer", timeout=30000)
    check("[mat] départ = avant le coup faux (pion h2, tour a1)", piece(page, "h2", True) == "wP" and piece(page, "a1", True) == "wR")
    board_fits(page, DIALOG, "[jouer 393x660]")
    page.screenshot(path=f"{SHOTS}/continuation_play_660.png")
    move(page, "a1", "a8", True)
    ck.appears("[mat] Échec et mat détecté", page, f"{DIALOG} >> text=Échec et mat", timeout=5000)
    page.screenshot(path=f"{SHOTS}/continuation_mate.png")
    page.locator(f"{DIALOG} button", has_text="Retour à l'exercice").click()
    page.wait_for_timeout(400)
    page.locator("button", has_text="Réessayer").click()
    check("[mat] réessai : amorce rejouée", wait_until(page, lambda: piece(page, "c3") == "bN", 5000))
    move(page, "a1", "a8")
    ck.appears("[mat] réessai réussi", page, "text=Réussi", timeout=5000)
    page.wait_for_timeout(300)
    check("[mat] position déjà matée : rien à prolonger", page.get_by_role("button", name="Jouer contre le moteur").count() == 0)
    ctx.close()

    # ===== Desktop 1440x900, puzzle A =====
    ctx = desktop_context(browser, ck, service_workers="block")
    fixture(ctx, PUZZLE_A)
    page = ctx.new_page()
    start_domain(page, "Tactiques")
    wait_until(page, lambda: piece(page, "e8") == "bK", 5000)
    move(page, "d5", "c7")
    wait_until(page, lambda: piece(page, "d7") == "bK", 5000)
    move(page, "c7", "a8")
    ck.appears("[desktop] verdict Réussi", page, "text=Réussi", timeout=5000)
    page.get_by_role("button", name="Voir la suite").click()
    check("[desktop] plan calculé", wait_until(page, lambda: strip_count(page) >= 2, 30000))
    check("[desktop] Jouer à partir d'ici actif une fois le plan calculé",
          page.locator(f"{DIALOG} button", has_text="Jouer à partir d'ici").is_enabled())
    board_fits(page, DIALOG, "[plan 1440x900]")
    page.screenshot(path=f"{SHOTS}/continuation_plan_desktop.png")
    page.keyboard.press("Escape")
    check("[desktop] Échap ferme le calque", wait_until(page, lambda: page.locator(DIALOG).count() == 0, 2000))
    ctx.close()

    browser.close()


ck.run(suite)
