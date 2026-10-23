"""E2E « Cours de finales » (Apprendre) : données vérifiées, sommaire, leçons jouables coup par
coup, refus exacts, promotion, progression persistante et idempotente, lien vers l'exercice,
rotation des domaines, mise en page 393x852, 393x660 et 1440x900.

Usage : npm run test:e2e -- --suite endgame_course
"""
import json
import re
import os
import subprocess

from course_helpers import advance, continue_btn, finish_line, observe_dom, open_lesson, wait_piece, wait_ready, wait_rows
from helpers import BASE, Checker, desktop_context, mobile_context, overflow_x, piece_on, shot, tap_move, tap_square

ck = Checker("endgame_course")
check = ck.check
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(ROOT, "src", "data", "endgameCourse.json"), encoding="utf-8") as f:
    COURSE = json.load(f)
LESSONS = [lid for ch in COURSE["chapters"] for lid in ch["lessons"]]
N = len(LESSONS)

# Lignes `learnSessions` du domaine `course`, lues directement dans IndexedDB.
COURSE_ROWS = """() => new Promise((resolve) => {
  const req = indexedDB.open('chess-local')
  req.onsuccess = () => {
    const tx = req.result.transaction('learnSessions', 'readonly')
    const all = tx.objectStore('learnSessions').getAll()
    all.onsuccess = () => { resolve(all.result.filter((r) => r.domain === 'course').map((r) => r.itemId)); req.result.close() }
  }
})"""

# Une séance Finales ancienne puis 30 leçons terminées plus récentes : la rotation des domaines doit
# ignorer les leçons, sinon la séance Finales sort de sa fenêtre de 30 lignes.
SEED_ROTATION = """() => new Promise((resolve) => {
  const req = indexedDB.open('chess-local')
  req.onsuccess = () => {
    const tx = req.result.transaction('learnSessions', 'readwrite')
    const store = tx.objectStore('learnSessions')
    store.clear()
    store.add({ date: 1000, domain: 'endgame', itemId: 'kq-mate', success: 1, ratingAfter: 800 })
    for (let i = 0; i < 30; i++) store.add({ date: 2000 + i, domain: 'course', itemId: 'finales:x' + i, success: 1, ratingAfter: null })
    tx.oncomplete = () => { req.result.close(); resolve(true) }
  }
})"""


def step_label(page):
    return page.locator("[data-testid='lesson-step']").inner_text()


def feedback(page):
    return page.locator("[data-testid='line-feedback']").inner_text()


def in_viewport(page, locator):
    box = locator.bounding_box()
    vp = page.viewport_size
    return box is not None and box["y"] >= 0 and box["y"] + box["height"] <= vp["height"] + 0.5 and box["x"] >= 0 and box["x"] + box["width"] <= vp["width"] + 0.5


def suite(p):
    # ---------- Données : contrôle hors ligne (structure, légalité, textes, tampon des tables) ----------
    res = subprocess.run(["node", "scripts/check-endgame-course.mjs"], cwd=ROOT, capture_output=True, text=True)
    check("[données] check-endgame-course.mjs passe", res.returncode == 0, f"({(res.stdout + res.stderr).strip()[-300:]})")
    check("[données] 14 leçons au moins, 5 chapitres", N >= 14 and len(COURSE["chapters"]) == 5, f"({N} leçons)")

    browser = p.chromium.launch(headless=True)
    ctx = mobile_context(p, browser, ck, standalone=True)
    page = ctx.new_page()

    # ---------- Entrée depuis Apprendre (Toutes les leçons) ----------
    page.goto(f"{BASE}/#/apprendre/lecons")
    ck.appears("[entrée] carte Cours de finales", page, "button:has-text('Cours de finales')")
    check("[entrée] progression 0/N", page.locator("[data-testid='course-card-progress']").inner_text() == f"0/{N} leçons")
    shot(page, "course_learn_home")
    page.locator("button", has_text="Cours de finales").click()
    ck.appears("[sommaire] titre", page, "h1:has-text('Cours de finales')")
    check("[sommaire] URL", page.url.endswith("#/apprendre/finales"), f"({page.url})")
    check("[sommaire] 5 chapitres", page.locator("main section h2").count() == 5)
    check("[sommaire] toutes les leçons listées", page.locator("[data-lesson]").count() == N)
    check("[sommaire] onglet Apprendre allumé", page.locator("nav a[aria-current]", has_text="Apprendre").count() >= 1)
    check("[sommaire] progression 0/N", page.locator("[data-testid='course-progress']").inner_text() == f"0/{N}")
    shot(page, "course_index", full_page=True)

    # ---------- Leçon « deux tours » : diagramme, ligne, refus, indice, réponse adverse ----------
    page.locator("[data-lesson='mat-deux-tours']").click()
    ck.appears("[leçon] étape 1/3", page, "[data-testid='lesson-step']:has-text('1/3')")
    # Plein écran : ce qui est peint en bas de l'écran est le pied de la leçon, pas la nav de l'app.
    check("[leçon] plein écran : nav recouverte", page.evaluate("() => !document.elementFromPoint(196, 840).closest('nav')"))
    check("[leçon] diagramme et explication", page.locator("[id^='chessboard-']").first.is_visible() and "escalier" in page.locator(".bg-white").first.inner_text().lower())
    check("[leçon] flèches du diagramme", page.locator("[id^='chessboard-'] marker[id*='arrowhead']").count() == 2)
    check("[leçon] Précédent grisé à la 1re étape", not page.get_by_role("button", name="← Précédent").is_enabled())
    shot(page, "course_diagram")
    advance(ck, page)
    ck.appears("[ligne] étape 2/3", page, "[data-testid='lesson-step']:has-text('2/3')")
    check("[ligne] URL porte l'étape", "etape=2" in page.url, f"({page.url})")
    check("[ligne] Continuer grisé tant que la ligne n'est pas jouée", not continue_btn(page).is_enabled())
    # Coup qui gagne aussi mais n'est pas celui de la méthode : refusé avec le bon message.
    tap_move(page, "a1", "a2")
    page.wait_for_timeout(150)
    check("[ligne] coup gagnant non attendu : « gagne aussi »", "gagne aussi" in feedback(page), f"({feedback(page)})")
    wait_ready(ck, page)
    wait_piece(ck, page, "a1", "wR")
    wait_piece(ck, page, "a2", None)
    check("[ligne] coup refusé repris", piece_on(page, "a1") == "wR" and piece_on(page, "a2") is None)
    check("[ligne] pas d'indice après un seul essai", page.locator("[id^='chessboard-'] marker[id*='arrowhead']").count() == 0)
    tap_move(page, "e1", "d2")
    wait_ready(ck, page)
    check("[ligne] indice au 2e essai (flèche)", page.locator("[id^='chessboard-'] marker[id*='arrowhead']").count() == 1)
    tap_move(page, "a1", "a4")
    check("[ligne] bon coup accepté et commenté", "4e rangée" in feedback(page), f"({feedback(page)})")
    wait_ready(ck, page)
    wait_piece(ck, page, "d5", "bK")
    check("[ligne] réponse adverse jouée (Rd5)", piece_on(page, "d5") == "bK")
    check("[ligne] réponse annoncée dans la bulle", "répondent" in page.locator(".bg-white").first.inner_text())
    shot(page, "course_line")

    # Analyser en pleine ligne (leçon non notée) : la position atteinte part dans l'analyseur, et
    # « Retour à la leçon » rend la même étape au même coup.
    status = page.get_by_text(re.compile(r"^À toi : (Blancs|Noirs) · coup [0-9]+/[0-9]+$")).inner_text()
    page.get_by_role("button", name="Analyser").click()
    if ck.appears("[ligne:analyse] « Retour à la leçon » dans l'analyseur", page, "button:has-text('Retour à la leçon')", timeout=10000):
        wait_piece(ck, page, "d5", "bK")
        check("[ligne:analyse] position atteinte transmise", piece_on(page, "a4") == "wR" and piece_on(page, "d5") == "bK")
        page.get_by_role("button", name="Retour à la leçon").click()
        if ck.appears("[ligne:analyse] retour à l'étape 2/3", page, "[data-testid='lesson-step']:has-text('2/3')", timeout=10000):
            wait_piece(ck, page, "a4", "wR")
            check("[ligne:analyse] même coup de la ligne", piece_on(page, "a4") == "wR" and piece_on(page, "d5") == "bK"
                  and page.get_by_text(status, exact=True).count() == 1, f"({status})")
            # Le coup restauré ne vaut qu'une fois : quitter l'étape puis y revenir recommence la ligne.
            page.get_by_role("button", name="← Précédent").click()
            ck.appears("[ligne:analyse] Précédent → étape 1/3", page, "[data-testid='lesson-step']:has-text('1/3')")
            advance(ck, page)
            if ck.appears("[ligne:analyse] Continuer → étape 2/3", page, "[data-testid='lesson-step']:has-text('2/3')"):
                wait_piece(ck, page, "a1", "wR")
                check("[ligne:analyse] étape revisitée : ligne repartie du début",
                      piece_on(page, "a1") == "wR" and piece_on(page, "a4") is None and piece_on(page, "e5") == "bK"
                      and page.get_by_text(re.compile(r"^À toi : (Blancs|Noirs) · coup 1/[0-9]+$")).count() == 1)

    # Rafraîchissement en cours de leçon : on reste à l'étape 2 (ligne recommencée).
    page.reload()
    ck.appears("[refresh] reste à l'étape 2/3", page, "[data-testid='lesson-step']:has-text('2/3')")
    check("[refresh] ligne repartie de la position initiale", piece_on(page, "a1") == "wR" and piece_on(page, "e5") == "bK")

    # Précédent pendant la pause de la réponse adverse : aucune réponse jouée hors de son étape.
    page.clock.install()
    page.clock.pause_at(page.evaluate("Date.now() + 100"))
    tap_move(page, "a1", "a4", pause=120)
    check("[pause] réponse encore en attente", not page.get_by_role("button", name="💡 Solution").is_enabled() and piece_on(page, "e5") == "bK")
    page.get_by_role("button", name="← Précédent").click()
    ck.appears("[pause] diagramme rendu", page, "[data-testid='lesson-step']:text-is('1/3')")
    check("[pause] Précédent ramène au diagramme", step_label(page) == "1/3")
    advance(ck, page)
    page.clock.run_for(1100)  # Dépasser la date du callback annulé dans la nouvelle étape.
    page.clock.resume()
    check("[pause] la ligne repart de zéro", piece_on(page, "a1") == "wR" and piece_on(page, "a4") is None and piece_on(page, "e5") == "bK")

    clicks = finish_line(ck, page)
    check("[ligne] jouée jusqu'au mat par Solution", continue_btn(page).is_enabled(), f"({clicks} clics)")
    check("[ligne] message de fin", "escalier" in feedback(page).lower(), f"({feedback(page)})")
    check("[ligne] Rejouer proposé", page.get_by_role("button", name="↺ Rejouer").is_visible())
    shot(page, "course_line_done")
    advance(ck, page)
    ck.appears("[bilan] À retenir", page, "text=À retenir")
    check("[bilan] S'entraîner proposé", page.get_by_role("button", name="S'entraîner : Mat des deux tours").is_visible())
    check("[bilan] Leçon suivante proposée", page.get_by_role("button", name="Leçon suivante").is_visible())
    shot(page, "course_summary")
    wait_rows(ck, page, COURSE_ROWS, "[progrès] ligne learnSessions course écrite")
    check("[progrès] une ligne learnSessions course", page.evaluate(COURSE_ROWS) == ["finales:mat-deux-tours"], f"({page.evaluate(COURSE_ROWS)})")
    # Revoir le bilan ne compte pas deux fois.
    page.goto(f"{BASE}/#/apprendre/finales/mat-deux-tours?etape=3")
    ck.appears("[progrès] bilan rouvert", page, "text=À retenir")
    wait_rows(ck, page, COURSE_ROWS, "[progrès] ligne learnSessions course relue")
    page.wait_for_timeout(400)  # Conserver la fenêtre de détection d’une écriture en double.
    check("[progrès] idempotent", len(page.evaluate(COURSE_ROWS)) == 1, f"({page.evaluate(COURSE_ROWS)})")

    # ---------- S'entraîner : exercice lié, puis retour au cours ----------
    page.get_by_role("button", name="S'entraîner : Mat des deux tours").click()
    ck.appears("[exercice] séance Finales ouverte sur l'exercice lié", page, ".bg-white:has-text('Mat des deux tours')")
    check("[exercice] Voir la leçon proposé", page.locator("button", has_text="Voir la leçon").is_visible())
    # Aller-retour vers la leçon : la séance (et son retour au cours) est restaurée.
    page.locator("button", has_text="Voir la leçon").click()
    ck.appears("[exercice] Voir la leçon ouvre la leçon", page, "[data-testid='lesson-step']:has-text('1/3')")
    page.click("header button[aria-label='Fermer la leçon']")
    ck.appears("[exercice] ✕ de la leçon rend la séance", page, ".bg-white:has-text('Mat des deux tours')")
    check("[exercice] séance restaurée, pas l'accueil", page.get_by_role("button", name="C'est parti").is_visible())
    # Leçon finie depuis la séance : chaque sortie du bilan rend la séance. « Retour à la séance »
    # remplace « S'entraîner », qui en démarrerait une autre.
    for exit_label in ("Retour à la séance", "Sommaire", "Leçon suivante"):
        page.locator("button", has_text="Voir la leçon").click()
        ck.appears(f"[séance → {exit_label}] leçon ouverte", page, "[data-testid='lesson-step']:has-text('1/3')")
        advance(ck, page)
        ck.appears(f"[séance → {exit_label}] ligne", page, "[data-testid='lesson-step']:has-text('2/3')")
        finish_line(ck, page)
        advance(ck, page)
        ck.appears(f"[séance → {exit_label}] bilan", page, "text=À retenir")
        check(f"[séance → {exit_label}] pas de S'entraîner au bilan", page.locator("button", has_text="S'entraîner").count() == 0)
        page.get_by_role("button", name=exit_label).click()
        if exit_label == "Sommaire":
            ck.appears("[séance → Sommaire] sommaire", page, "h1:has-text('Cours de finales')")
            page.get_by_role("button", name="Retour à Apprendre", exact=True).click()
        elif exit_label == "Leçon suivante":
            ck.appears("[séance → Leçon suivante] leçon suivante", page, "[data-testid='lesson-step']:has-text('1/')")
            page.click("header button[aria-label='Fermer la leçon']")
        ck.appears(f"[séance → {exit_label}] séance rendue", page, ".bg-white:has-text('Mat des deux tours')")
        check(f"[séance → {exit_label}] séance restaurée, pas l'accueil", page.get_by_role("button", name="C'est parti").is_visible())
    # Diagramme analysé depuis une leçon ouverte par la séance : le retour rend l'étape, et ✕ rend
    # toujours la séance (l'origine survit à l'aller-retour).
    page.locator("button", has_text="Voir la leçon").click()
    ck.appears("[séance → analyse] leçon ouverte", page, "[data-testid='lesson-step']:has-text('1/3')")
    page.get_by_role("button", name="Analyser").click()
    if ck.appears("[séance → analyse] « Retour à la leçon »", page, "button:has-text('Retour à la leçon')", timeout=10000):
        wait_piece(ck, page, "a4", "wR")
        check("[séance → analyse] position du diagramme transmise", piece_on(page, "a4") == "wR" and piece_on(page, "b1") == "wR" and piece_on(page, "e5") == "bK")
        page.get_by_role("button", name="Retour à la leçon").click()
        ck.appears("[séance → analyse] retour au diagramme 1/3", page, "[data-testid='lesson-step']:has-text('1/3')", timeout=10000)
        page.click("header button[aria-label='Fermer la leçon']")
        ck.appears("[séance → analyse] ✕ rend la séance", page, ".bg-white:has-text('Mat des deux tours')")
        check("[séance → analyse] séance restaurée, pas l'accueil", page.get_by_role("button", name="C'est parti").is_visible())
    page.get_by_role("button", name="C'est parti").click()
    ck.appears("[exercice] échiquier de l'exercice", page, "text=Objectif")
    check("[exercice] position de rr-mate", piece_on(page, "a1") == "wR" and piece_on(page, "b1") == "wR")
    page.click("header button:has-text('✕')")
    ck.appears("[exercice] ✕ ramène au bilan de la leçon", page, "text=À retenir")
    check("[exercice] URL du bilan", "finales/mat-deux-tours" in page.url, f"({page.url})")

    # ---------- Sommaire et accueil : progression persistante ----------
    page.get_by_role("button", name="Sommaire").click()
    ck.appears("[progrès] sommaire 1/N", page, f"[data-testid='course-progress']:has-text('1/{N}')")
    check("[progrès] coche sur la leçon", "✓" in page.locator("[data-lesson='mat-deux-tours']").inner_text())
    page.reload()
    ck.appears("[progrès] persiste après rechargement", page, f"[data-testid='course-progress']:has-text('1/{N}')")
    page.goto(f"{BASE}/#/apprendre/lecons")
    ck.appears("[progrès] carte de Toutes les leçons 1/N", page, f"[data-testid='course-card-progress']:has-text('1/{N} leçons')")

    # ---------- Carré du pion : coup qui lâche le gain, promotion avec la mauvaise pièce ----------
    page.goto(f"{BASE}/#/apprendre/finales/carre-du-pion?etape=3")
    ck.appears("[carré] ligne ouverte (Noirs en bas)", page, "[data-testid='lesson-step']:has-text('3/4')")
    red = "() => [...document.querySelectorAll(\"[data-square='c7'] div\")].some((e) => getComputedStyle(e).backgroundColor.includes('235, 97, 80'))"
    with observe_dom(page, red) as red_seen:
        tap_move(page, "b8", "c7", pause=120)
        check("[carré] coup perdant : gain lâché", "échapper le gain" in feedback(page), f"({feedback(page)})")
        check("[carré] case du coup refusé en rouge", red_seen())
    wait_ready(ck, page)
    wait_piece(ck, page, "b8", "bK")
    check("[carré] roi reposé en b8", piece_on(page, "b8") == "bK")
    tap_move(page, "f4", "f3")
    check("[carré] seul coup gagnant salué", "Seul coup" in feedback(page), f"({feedback(page)})")
    wait_ready(ck, page)
    wait_piece(ck, page, "f3", "bP")
    tap_move(page, "f3", "f2")
    wait_ready(ck, page)
    wait_piece(ck, page, "f2", "bP")
    tap_square(page, "f2")
    page.wait_for_timeout(200)
    tap_square(page, "f1")
    page.wait_for_timeout(300)
    page.get_by_role("button", name="Tour", exact=True).click()  # sous-promotion en tour : gagne aussi
    page.wait_for_timeout(150)
    check("[carré] sous-promotion en tour : « gagne aussi »", "gagne aussi" in feedback(page), f"({feedback(page)})")
    wait_ready(ck, page)
    wait_piece(ck, page, "f2", "bP")
    tap_square(page, "f2")
    page.wait_for_timeout(200)
    tap_square(page, "f1")
    page.wait_for_timeout(300)
    page.get_by_role("button", name="Dame", exact=True).click()
    wait_ready(ck, page)
    wait_piece(ck, page, "f1", "bQ")
    check("[carré] promotion en dame : ligne terminée", continue_btn(page).is_enabled() and piece_on(page, "f1") == "bQ")
    shot(page, "course_square")

    # ---------- Id inconnu ----------
    page.goto(f"{BASE}/#/apprendre/finales/inconnue")
    ck.appears("[id inconnu] retour au sommaire", page, "h1:has-text('Cours de finales')")

    # ---------- Toutes les leçons se jouent jusqu'au bilan ----------
    for lid in LESSONS:
        open_lesson(ck, page, f"{BASE}/#/apprendre/finales/{lid}", COURSE["lessons"][lid])
        steps = COURSE["lessons"][lid]["steps"]
        ok = True
        for i, s in enumerate(steps):
            if s["kind"] == "line":
                finish_line(ck, page)
                ok = ok and continue_btn(page).is_enabled()
            advance(ck, page)
        ok = ok and page.locator("text=À retenir").is_visible()
        check(f"[toutes] {lid} jouée jusqu'au bilan", ok)
    page.goto(f"{BASE}/#/apprendre/finales")
    ck.appears("[toutes] sommaire N/N", page, f"[data-testid='course-progress']:has-text('{N}/{N}')")

    # ---------- Rotation des domaines : les leçons ne comptent pas ----------
    page.evaluate(SEED_ROTATION)
    page.goto(f"{BASE}/#/apprendre")
    page.wait_for_timeout(800)
    page.get_by_role("button", name="Séance rapide", exact=True).click()
    page.wait_for_timeout(2500)
    title = page.locator("header h1").first.inner_text()
    check("[rotation] Séance ne repropose pas Finales (lignes course ignorées)", "Finales" not in title, f"({title})")
    ctx.close()

    # ---------- 393x660 (onglet Safari) : échiquier et bouton dans l'écran ----------
    ctx = mobile_context(p, browser, ck)
    page = ctx.new_page()
    for lid, etape, name in [("lucena", 2, "line"), ("mat-dame", 1, "diagram"), ("dame-contre-pion", 2, "line_long")]:
        page.goto(f"{BASE}/#/apprendre/finales/{lid}?etape={etape}")
        page.wait_for_selector("[id^='chessboard-']", timeout=10000)
        page.wait_for_timeout(500)
        board = page.locator("[id^='chessboard-']").first
        check(f"[660] {lid} : échiquier entier à l'écran", in_viewport(page, board), f"({board.bounding_box()})")
        check(f"[660] {lid} : Continuer à l'écran", in_viewport(page, continue_btn(page)))
        check(f"[660] {lid} : bulle visible", page.locator(".bg-white").first.is_visible())
        check(f"[660] {lid} : pas de défilement horizontal", overflow_x(page) == 0, f"({overflow_x(page)} px)")
        shot(page, f"course_660_{name}")
    ctx.close()

    # ---------- 1440x900 ----------
    ctx = desktop_context(browser, ck)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/apprendre/finales")
    page.wait_for_selector("[data-lesson]", timeout=10000)
    shot(page, "course_desktop_index")
    page.goto(f"{BASE}/#/apprendre/finales/philidor?etape=2")
    page.wait_for_selector("[id^='chessboard-']", timeout=10000)
    page.wait_for_timeout(400)
    check("[desktop] Philidor : Noirs en bas", piece_on(page, "d8") == "bK" and page.locator("[data-square='d8']").bounding_box()["y"] > page.locator("[data-square='d1']").bounding_box()["y"])
    check("[desktop] Continuer à l'écran", in_viewport(page, continue_btn(page)))
    shot(page, "course_desktop_line")
    ctx.close()
    browser.close()


ck.run(suite)
