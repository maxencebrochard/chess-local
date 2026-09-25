"""T04 : puzzles choisis servis un par un (route sur puzzles.json) : reprise (surlignage), promotion,
sous-promotion, mat alternatif, très long, libellé de thèmes le plus long."""
import json
import sys
import time
from pz import *

SP = json.load(open(os.path.join(os.path.dirname(__file__), "special.json")))
only = sys.argv[1:] or None


def to_dict(c):
    return {"id": c[0], "fen": c[1], "moves": c[2].split(), "rating": c[3], "themes": c[4].split()}


def yellow_squares(page):
    return page.evaluate(
        """() => [...document.querySelectorAll('[data-square]')].filter(e =>
            [e, ...e.querySelectorAll('*')].some(n => getComputedStyle(n).backgroundColor.includes('255, 255, 51'))
        ).map(e => e.getAttribute('data-square')).sort()"""
    )


def start(p, compact, standalone=True):
    browser, ctx, page, logs = open_mobile(p, standalone=standalone)
    serve_custom(page, [compact])
    page.goto(f"{BASE}/#/puzzles")
    page.wait_for_selector("text=Classement puzzles", timeout=30000)
    pz = wait_puzzle(page)
    assert pz["id"] == compact[0]
    assert wait_placement(page, pz, 1)
    page.wait_for_timeout(200)
    return browser, page, logs, pz


def status(page):
    t = panel_text(page)
    return "Résolu" if "Résolu" in t else "Raté" if "Raté" in t else "en cours"


with sync_playwright() as p:
    # ---- a. reprise sur la case du coup d'amorce : surlignage du dernier coup ----
    if not only or "recapture" in only:
        for mode in ("tap", "drag"):
            browser, page, logs, pz = start(p, SP["recapture1"])
            m = pz["moves"][1]
            print(f"[recapture/{mode}] amorce {pz['moves'][0]} -> jaunes {yellow_squares(page)} ; coup joueur {m}")
            play_uci(page, m, mode)
            page.wait_for_timeout(600)
            ys = yellow_squares(page)
            print(f"[recapture/{mode}] {status(page)} ; jaunes après coup: {ys} ; attendu: {sorted([m[:2], m[2:4]])} -> {'OK' if ys == sorted([m[:2], m[2:4]]) else 'SURLIGNAGE PERDU'}")
            shot(page, f"t04_recapture_{mode}")
            print(f"[recapture/{mode}] logs:", [l[:120] for l in logs])
            browser.close()

    # ---- b. promotion (dame) + annulation du sélecteur ----
    if not only or "promo" in only:
        browser, page, logs, pz = start(p, SP["promo"])
        print("[promo] joueur noir ? orientation:", orientation(page), pz["moves"])
        play_uci(page, pz["moves"][1])
        assert wait_placement(page, pz, 3)
        m = pz["moves"][3]
        tap_move(page, m[:2], m[2:4])
        page.wait_for_timeout(300)
        n_btn = page.locator(".boardbox button").count()
        print("[promo] sélecteur affiché, boutons:", n_btn, [page.locator(".boardbox button").nth(i).inner_text() for i in range(n_btn)])
        shot(page, "t04_promo_dialog")
        bb = page.locator(".boardbox button").first.bounding_box()
        print("[promo] taille bouton:", bb)
        # tap en dehors des boutons (coin du board) : annule ?
        board = page.locator(".boardbox").bounding_box()
        page.touchscreen.tap(board["x"] + 20, board["y"] + 20)
        page.wait_for_timeout(300)
        print("[promo] après tap hors boutons : sélecteur encore là ?", page.locator(".boardbox button").count() > 0)
        # Escape ?
        page.keyboard.press("Escape"); page.wait_for_timeout(200)
        print("[promo] après Escape : sélecteur encore là ?", page.locator(".boardbox button").count() > 0)
        page.locator(".boardbox button").filter(has_text="♛").first.tap()
        page.wait_for_timeout(600)
        print("[promo] dame ->", status(page), rating_shown(page))
        shot(page, "t04_promo_solved")
        print("[promo] logs:", [l[:120] for l in logs])
        browser.close()

        # b2. mat alternatif par promotion en tour
        browser, page, logs, pz = start(p, SP["promo"])
        play_uci(page, pz["moves"][1]); assert wait_placement(page, pz, 3)
        play_uci(page, "c2d1r"); page.wait_for_timeout(600)
        print("[altmate promo tour] ->", status(page), rating_shown(page))
        browser.close()

        # b3. promotion au drag
        browser, page, logs, pz = start(p, SP["promo"])
        play_uci(page, pz["moves"][1], "drag"); assert wait_placement(page, pz, 3)
        play_uci(page, pz["moves"][3], "drag"); page.wait_for_timeout(600)
        print("[promo drag] ->", status(page), rating_shown(page))
        browser.close()

    # ---- c. sous-promotion attendue ----
    if not only or "under" in only:
        browser, page, logs, pz = start(p, SP["underpromo"])
        print("[underpromo]", pz["moves"])
        play_uci(page, pz["moves"][1][:4] + "q"); page.wait_for_timeout(600)
        print("[underpromo] dame au lieu de cavalier ->", status(page), rating_shown(page))
        print("[underpromo] texte:", panel_text(page).split("Classement puzzles")[1].replace("\n", " | ")[:160])
        shot(page, "t04_underpromo_failed")
        page.locator("main button", has_text="Réessayer").tap(); page.wait_for_timeout(300)
        assert wait_placement(page, pz, 1)
        solve(page, pz); page.wait_for_timeout(600)
        print("[underpromo] cavalier ->", status(page))
        browser.close()

    # ---- d. mat alternatif sans promotion ----
    if not only or "altmate" in only:
        browser, page, logs, pz = start(p, SP["altmate2"])
        play_uci(page, pz["moves"][1]); assert wait_placement(page, pz, 3)
        alt = SP["altmate2_alt"][0]
        print("[altmate] attendu", pz["moves"][3], "joué", alt)
        play_uci(page, alt); page.wait_for_timeout(600)
        print("[altmate] ->", status(page), rating_shown(page))
        shot(page, "t04_altmate")
        browser.close()

    # ---- e. très long (12 demi-coups) ----
    if not only or "long" in only:
        browser, page, logs, pz = start(p, SP["verylong"])
        t0 = time.time()
        solve(page, pz); page.wait_for_timeout(600)
        print(f"[verylong] {len(pz['moves'])} demi-coups ->", status(page), rating_shown(page), f"en {time.time()-t0:.1f}s")
        shot(page, "t04_verylong_solved")
        print("[verylong] logs:", [l[:120] for l in logs])
        browser.close()

    # ---- f. libellé de thèmes le plus long ----
    if not only or "label" in only:
        for sa in (True, False):
            browser, page, logs, pz = start(p, SP["longlabel"], standalone=sa)
            solve(page, pz); page.wait_for_timeout(600)
            b = page.locator("main button", has_text="Suivant").first.bounding_box()
            print(f"[longlabel standalone={sa}] ->", status(page), "Suivant y:", b["y"], "overflow_x:", overflow_x(page), scroll_state(page))
            shot(page, f"t04_longlabel_{'852' if sa else '660'}")
            browser.close()
