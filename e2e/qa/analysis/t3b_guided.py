"""Passe 3b : graphe cliquable, vue non guidée après bilan, flèches, Réessayer."""
import os, sys
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *

PGN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"


def load_text(page, text):
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Importer PGN ou FEN").click(); page.wait_for_timeout(300)
    page.fill("textarea", text)
    page.locator("button", has_text="Charger").click(); page.wait_for_timeout(500)


def cur(page, scope=""):
    return page.evaluate("""(scope) => {const e=[...document.querySelectorAll(scope + ' [data-current="true"]')].find(e=>e.offsetParent); return e ? e.innerText : null}""", scope)


def bubble(page):
    return page.locator(".fixed .bg-white").first.inner_text().replace("\n", " | ")


def arrows(page):
    return page.evaluate("""() => [...document.querySelectorAll('.boardbox svg [marker-end], .boardbox svg line, .boardbox svg path')].filter(e => e.offsetParent !== undefined).map(e => (e.getAttribute('stroke')||e.getAttribute('fill')||'')).filter(Boolean)""")


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(2000)
    load_text(page, PGN)
    page.get_by_role("button", name="★ Bilan").click()
    page.wait_for_selector("text=Démarrer le bilan", timeout=240000)
    page.wait_for_timeout(300)

    # Tap sur le graphe à ~64 % (≈ demi-coup 9 = Nxf7 idx 8)
    g = page.locator(".fixed svg.cursor-pointer").bounding_box()
    for ratio in (0.0, 9 / 14, 1.0):
        page.touchscreen.tap(g["x"] + g["width"] * ratio + (1 if ratio == 0 else -1 if ratio == 1 else 0), g["y"] + g["height"] / 2)
        page.wait_for_timeout(500)
        guided = page.locator(".fixed button", has_text="Réessayer").count() > 0
        print(f"tap graphe ratio={ratio:.2f} -> guidé={guided} coup courant={cur(page, '.fixed')!r} bulle={bubble(page) if guided else ''}")
        if ratio == 0.0:
            shot(page, "t3b_00_graph_tap_start")
        if guided:
            page.locator(".fixed header button").click(); page.wait_for_timeout(300)

    # Fermer le résumé -> vue analyse avec bilan
    page.locator(".fixed header button").click(); page.wait_for_timeout(600)
    print("après ✕ : hash", page.evaluate("location.hash"), "courant", cur(page, "main"), scroll_state(page))
    shot(page, "t3b_01_after_close")
    page.evaluate("() => {const m=document.querySelector('main'); m.scrollTop = m.scrollHeight}"); page.wait_for_timeout(300)
    shot(page, "t3b_02_after_close_scrolled")
    page.evaluate("() => {const m=document.querySelector('main'); m.scrollTop = 0}")

    # tap sur le coup Nxf7 dans la bande
    page.locator("main [data-current]:visible", has_text="xf7").first.click(); page.wait_for_timeout(1500)
    print("courant:", cur(page, "main"), "flèches:", arrows(page))
    shot(page, "t3b_03_blunder_nonguided")
    page.evaluate("() => {const m=document.querySelector('main'); m.scrollTop = m.scrollHeight}"); page.wait_for_timeout(300)
    shot(page, "t3b_04_blunder_nonguided_scrolled")
    print("carte coach:", page.locator("main .border-l-4").inner_text().replace("\n", " | "))
    # graphe non guidé : tap
    g2 = page.locator("main svg.cursor-pointer").bounding_box()
    page.touchscreen.tap(g2["x"] + g2["width"] * 0.5, g2["y"] + g2["height"] / 2); page.wait_for_timeout(500)
    print("tap graphe non guidé 50% -> courant", cur(page, "main"))
    # Moment clé
    page.locator("main button", has_text="Moment clé →").click(); page.wait_for_timeout(400)
    print("moment clé → :", cur(page, "main"))
    page.locator("main button", has_text="← Moment clé").click(); page.wait_for_timeout(400)
    print("← moment clé :", cur(page, "main"))
    page.locator("main [data-current]:visible", has_text="xf7").first.click(); page.wait_for_timeout(500)
    # Réessayer depuis la carte
    page.locator("main button", has_text="Réessayer").click(); page.wait_for_timeout(600)
    print("retry bulle:", bubble(page))
    shot(page, "t3b_05_retry_start")
    # mauvais coup : a2a3
    tap_move(page, "a2", "a3"); page.wait_for_timeout(300)
    print("après a3 (immédiat):", bubble(page))
    page.wait_for_timeout(4000)
    print("après a3 (+4s):", bubble(page), "| a3:", piece_on(page, "a3"), "a2:", piece_on(page, "a2"))
    shot(page, "t3b_06_retry_failed")
    # Solution
    page.locator(".fixed button", has_text="Solution").click(); page.wait_for_timeout(300)
    print("solution:", bubble(page))
    shot(page, "t3b_07_retry_solution")
    # bon coup par drag : Bc4xf7+
    drag_piece(page, "c4", "f7"); page.wait_for_timeout(800)
    print("après Bxf7+:", bubble(page), "| f7:", piece_on(page, "f7"), "c4:", piece_on(page, "c4"))
    shot(page, "t3b_08_retry_found")
    page.locator(".fixed button", has_text="Continuer").click(); page.wait_for_timeout(400)
    print("après Continuer:", bubble(page), "courant", cur(page, ".fixed"))
    # Meilleur : flèche
    page.locator(".fixed button", has_text="Meilleur").click(); page.wait_for_timeout(400)
    print("flèches Meilleur:", arrows(page))
    shot(page, "t3b_09_best_arrow")
    # Afficher : lignes
    page.locator(".fixed button", has_text="Afficher").click(); page.wait_for_timeout(2500)
    shot(page, "t3b_10_lines")
    brd = page.locator(".fixed .boardbox").bounding_box()
    print("board y avec lignes:", brd["y"])
    # retry alternatif : un coup correct mais pas le meilleur ? d2-d3 n'est pas bon. Essayons O-O (e1g1)
    page.locator(".fixed button", has_text="Réessayer").click(); page.wait_for_timeout(400)
    tap_move(page, "e1", "g1"); page.wait_for_timeout(4000)
    print("retry O-O:", bubble(page))
    # quitter le mode par la flèche retour pendant retry
    page.locator(".fixed header button").click(); page.wait_for_timeout(400)
    print("retour résumé pendant retry ok:", page.locator("text=Démarrer le bilan").count() == 1)
    print("LOGS", logs)
    browser.close()
