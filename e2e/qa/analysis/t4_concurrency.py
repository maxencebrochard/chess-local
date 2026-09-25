"""Passe 4 : interactions pendant un bilan en cours (longue partie 230 demi-coups)."""
import os, sys, time
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *

LONG = open(os.path.join(QA, "analysis", "long.pgn")).read()
SCEN = sys.argv[1] if len(sys.argv) > 1 else "progress"


def load_text(page, text):
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Importer PGN ou FEN").click(); page.wait_for_timeout(300)
    page.fill("textarea", text)
    page.locator("button", has_text="Charger").click(); page.wait_for_timeout(500)


def nmoves(page):
    return page.evaluate("""() => [...document.querySelectorAll('main [data-current], .fixed [data-current]')].filter(e=>e.offsetParent).length""")


def cur(page):
    return page.evaluate("""() => {const e=[...document.querySelectorAll('[data-current="true"]')].find(e=>e.offsetParent); return e ? e.innerText : null}""")


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, settings={"reviewDepth": "deep"}, standalone=True)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(2000)
    load_text(page, LONG)
    page.wait_for_timeout(600)
    print("coups chargés:", nmoves(page))
    t0 = time.time()
    page.get_by_role("button", name="★ Bilan").click()
    page.wait_for_timeout(2000)

    if SCEN == "progress":
        shot(page, "t4_progress_3s")
        vis = page.evaluate("""() => [...document.querySelectorAll('body *')].filter(e => e.offsetParent && e.children.length===0 && /%|Analyse|Bilan en cours|Calcul/.test(e.innerText||'')).map(e=>e.innerText)""")
        print("indices de progression visibles (mobile):", vis)
        print("Bilan désactivé:", page.get_by_role("button", name="★ Bilan").is_disabled())
        print("Annuler présent:", page.locator("button:visible", has_text="nnuler").count())
        # navigation pendant le bilan
        for _ in range(5):
            page.locator("main button", has_text="Précédent").click(); page.wait_for_timeout(150)
        print("courant après 5x Précédent pendant bilan:", cur(page))
        shot(page, "t4_progress_nav")
        page.wait_for_selector("text=Démarrer le bilan", timeout=600000)
        print("durée bilan 230 demi-coups (s):", round(time.time() - t0, 1))
        shot(page, "t4_long_summary")
        grids = page.evaluate("() => [...document.querySelectorAll('.fixed .grid')].map(g => g.innerText.replace(/\\n+/g,' | '))")
        for g in grids: print("GRID:", g)
        # sommes
        import re
        w = b = 0
        for g in grids[1:12]:
            parts = [x.strip() for x in g.split("|")]
            w += int(parts[1]); b += int(parts[-1])
        print("somme classes blancs/noirs:", w, b, "(attendu 115/115)")
        page.locator("button", has_text="Démarrer le bilan").click(); page.wait_for_timeout(500)
        # dernier coup : auto-scroll de la bande
        last = page.locator(".fixed [data-current]").last
        page.evaluate("() => {const s=[...document.querySelectorAll('.fixed [data-current]')]; s[s.length-1].click()}")
        page.wait_for_timeout(900)
        bb = page.evaluate("""() => {const e=document.querySelector('.fixed [data-current="true"]').getBoundingClientRect(); return {l:e.left, r:e.right}}""")
        print("coup courant (dernier) bbox dans la bande:", bb)
        shot(page, "t4_long_guided_last")

    if SCEN == "variation":
        # Pendant le bilan : reculer de 100 demi-coups (via tap sur un coup ancien) et jouer un autre coup
        page.evaluate("() => {const s=[...document.querySelectorAll('main [data-current]')].filter(e=>e.offsetParent); s[9].click()}")
        page.wait_for_timeout(500)
        print("courant:", cur(page), "nb:", nmoves(page))
        # jouer un coup légal quelconque différent : on tente plusieurs coups de pions
        before = nmoves(page)
        for frm, to in (("a2", "a3"), ("h2", "h3"), ("a7", "a6"), ("h7", "h6"), ("a2", "a4"), ("h7", "h5")):
            try:
                tap_move(page, frm, to)
            except Exception:
                continue
            if nmoves(page) != before:
                print("variante jouée:", frm, to); break
        print("nb coups après variante pendant bilan:", nmoves(page))
        shot(page, "t4_variation_during_review")
        page.wait_for_selector("text=Démarrer le bilan", timeout=600000)
        print("bilan terminé en", round(time.time() - t0, 1), "s ; LOGS:", logs)
        shot(page, "t4_variation_summary")
        g = page.locator(".fixed svg.cursor-pointer").bounding_box()
        page.touchscreen.tap(g["x"] + g["width"] * 0.9, g["y"] + g["height"] / 2)
        page.wait_for_timeout(1000)
        print("après tap graphe 90% : body len", len(page.locator("body").inner_text()), "LOGS:", logs)
        shot(page, "t4_variation_after_graph_tap")

    if SCEN == "leave":
        page.locator("nav a", has_text="Archive").last.click(); page.wait_for_timeout(1500)
        print("hash:", page.evaluate("location.hash"), "LOGS:", logs)
        page.locator("nav a", has_text="Analyse").last.click(); page.wait_for_timeout(2500)
        print("retour analyse : nb coups", nmoves(page), "| lignes:", page.evaluate("() => [...document.querySelectorAll('main p.truncate')].map(p => p.innerText)"))
        shot(page, "t4_leave_back")
        # le moteur répond-il encore ?
        tap_move(page, "e2", "e4"); page.wait_for_timeout(2500)
        print("lignes après e4:", page.evaluate("() => [...document.querySelectorAll('main p.truncate')].map(p => p.innerText)"))
        print("LOGS:", logs)

    if SCEN == "reimport":
        # importer une autre partie pendant le bilan
        load_text(page, "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#")
        print("nb coups après réimport pendant bilan:", nmoves(page), "Bilan désactivé:", page.get_by_role("button", name="★ Bilan").is_disabled())
        page.wait_for_selector("text=Démarrer le bilan", timeout=600000)
        print("bilan terminé en", round(time.time() - t0, 1), "s")
        grids = page.evaluate("() => [...document.querySelectorAll('.fixed .grid')].map(g => g.innerText.replace(/\\n+/g,' | '))")
        print("GRID théorique:", [g for g in grids if g.startswith("Théorique")], "précision:", grids[0])
        shot(page, "t4_reimport_summary")
        page.locator("button", has_text="Démarrer le bilan").click(); page.wait_for_timeout(600)
        print("guidé: nb coups bande", nmoves(page), "bulle:", page.locator(".fixed .bg-white").first.inner_text().replace("\n", " | "))
        shot(page, "t4_reimport_guided")
        print("LOGS:", logs)
    browser.close()
