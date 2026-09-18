"""/#/analyse (standalone 852) : tap tremblant vs dragActivationDistance:1, tap-tap, changement de sélection,
drag lâché hors board, roque par drag du roi, prise en passant, promotion (drag ET tap), long press, multi-touch."""
import sys
sys.path.insert(0, "e2e/qa/touch")
from tlib import *

def fresh(p):
    browser, ctx, page, logs = open_mobile_t(p, standalone=True)
    install(page)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1500)
    return browser, page, logs

def play(page, moves):
    for m in moves:
        tap_move(page, m[:2], m[2:4], pause=180)

with sync_playwright() as p:
    # ---------- A. tap tremblant : à partir de combien de px un tap devient-il un drag raté ? ----------
    browser, page, logs = fresh(p)
    print("=== A. tap tremblant sur e2 (dragActivationDistance: 1) : la pièce est-elle sélectionnée après le geste ?")
    for d in [0, 1, 2, 3, 5, 8]:
        x, y = sq_center(page, "e2")
        r = gesture(page, x, y, x + d, y, steps=max(1, d), step_ms=12, hold_ms=40) if d else None
        if d == 0:
            events(page); tap_square(page, "e2"); page.wait_for_timeout(300); s = snap(page)
            print(f"   déplacement 0px (tap pur)  -> sélection={s['selected']}")
        else:
            print(f"   déplacement {d}px           -> sélection={r['after']['selected']} clone_mi-course={bool(r['mid'] and r['mid']['dragClone'])} coup_joué={r['before']['pos'] != r['after']['pos']}")
        # remise à zéro de la sélection si besoin
        if snap(page)["selected"]:
            tap_square(page, "e2"); page.wait_for_timeout(200)
    shot(page, "t07_A_tap_tremblant")

    # ---------- B. tap-tap, changement de sélection, désélection ----------
    print("=== B. tap-tap et sélection")
    tap_square(page, "e2"); page.wait_for_timeout(250); print("   tap e2 -> sélection:", snap(page)["selected"])
    tap_square(page, "d2"); page.wait_for_timeout(250); print("   tap d2 (autre pièce à moi) -> sélection:", snap(page)["selected"], "(attendu ['d2'])")
    tap_square(page, "d2"); page.wait_for_timeout(250); print("   re-tap d2 -> sélection:", snap(page)["selected"], "(attendu [])")
    tap_square(page, "e2"); page.wait_for_timeout(250); tap_square(page, "e7"); page.wait_for_timeout(250)
    print("   e2 sélectionné puis tap pièce adverse e7 (coup illégal) -> sélection:", snap(page)["selected"], "pos e2:", piece_on(page, "e2"))
    tap_move(page, "e2", "e4"); print("   tap e2 puis tap e4 -> e4:", piece_on(page, "e4"), "e2:", piece_on(page, "e2"))
    # ---------- C. drag lâché hors du board ----------
    print("=== C. drag lâché hors du board")
    x, y = sq_center(page, "d7"); r = gesture(page, x, y, x, 40); v = line("d7 lâché au-dessus du board (y=40)", r, "piece:b")
    x, y = sq_center(page, "d7"); r = gesture(page, x, y, x, 800); v = line("d7 lâché sur la barre de nav (y=800)", r, "piece:b")
    s = snap(page); print("   après : d7 =", piece_on(page, "d7"), "| hash:", s["hash"], "| clone fantôme resté:", s["dragClone"])
    shot(page, "t07_C_lache_hors_board")
    browser.close()

    # ---------- D. roque par drag du roi ----------
    browser, page, logs = fresh(p)
    print("=== D. roque par drag du roi")
    play(page, ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "f8c5"])
    r = gesture(page, *sq_center(page, "e1"), *sq_center(page, "g1")); line("roi e1 -> g1", r, "piece:wK")
    print("   g1 =", piece_on(page, "g1"), "| f1 =", piece_on(page, "f1"), "| h1 =", piece_on(page, "h1"), "(attendu wK, wR, None)")
    shot(page, "t07_D_roque"); browser.close()

    # ---------- E. prise en passant par drag ----------
    browser, page, logs = fresh(p)
    print("=== E. prise en passant par drag")
    play(page, ["e2e4", "a7a6", "e4e5", "d7d5"])
    r = gesture(page, *sq_center(page, "e5"), *sq_center(page, "d6")); line("pion e5 x d6 e.p.", r, "piece:wP")
    print("   d6 =", piece_on(page, "d6"), "| d5 =", piece_on(page, "d5"), "| e5 =", piece_on(page, "e5"), "(attendu wP, None, None)")
    shot(page, "t07_E_en_passant"); browser.close()

    # ---------- F. promotion : par drag, puis par tap ----------
    PROMO = ["h2h4", "g7g5", "h4g5", "h7h6", "g5h6", "f8g7", "h6g7", "g8f6"]
    for mode in ("drag", "tap"):
        browser, page, logs = fresh(p)
        print(f"=== F. promotion par {mode} (g7xh8)")
        play(page, PROMO)
        if mode == "drag":
            r = gesture(page, *sq_center(page, "g7"), *sq_center(page, "h8")); line("pion g7 x h8 (8e rangée)", r, "piece:wP")
        else:
            tap_move(page, "g7", "h8")
        page.wait_for_timeout(300)
        info = page.evaluate("""() => { const bs = [...document.querySelectorAll('.z-20 button')]; const ov = document.querySelector('.z-20');
          return { n: bs.length, glyphs: bs.map(b => b.textContent), sizes: bs.map(b => { const r = b.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height), Math.round(r.x), Math.round(r.y)] }),
                   overlay: ov ? (() => { const r = ov.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)] })() : null, vw: innerWidth } }""")
        print("   UI de promotion:", info)
        shot(page, f"t07_F_promotion_{mode}_ui")
        if info["n"]:
            bx = info["sizes"][3]; page.touchscreen.tap(bx[2] + bx[0] / 2, bx[3] + bx[1] / 2); page.wait_for_timeout(500)   # 4e bouton = cavalier
            print("   après tap sur le cavalier : h8 =", piece_on(page, "h8"), "(attendu wN) | UI encore visible:", snap(page)["promo"])
        shot(page, f"t07_F_promotion_{mode}_apres")
        browser.close()

    # ---------- G. long press (callout / menu contextuel / sélection de texte) ----------
    browser, page, logs = fresh(p)
    print("=== G. long press 900 ms sans bouger")
    for label, (x, y) in [("pièce e2", sq_center(page, "e2")), ("case vide e4", sq_center(page, "e4")), ("texte hors board (lignes moteur, y=75)", (120, 75))]:
        events(page); cdp = page.context.new_cdp_session(page)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y, "id": 1}]}); page.wait_for_timeout(900)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}); cdp.detach(); page.wait_for_timeout(300)
        ev = events(page); s = snap(page)
        print(f"   {label:42s} contextmenu={[e for e in ev if e.startswith('contextmenu')]} selectstart={sum(1 for e in ev if e.startswith('selectstart'))} texte_sélectionné={s['textSelection']} car. sélection_pièce={s['selected']}")
        page.touchscreen.tap(200, 700); page.wait_for_timeout(200)
    shot(page, "t07_G_long_press")
    browser.close()

    # ---------- H. multi-touch : second doigt posé pendant un drag ----------
    browser, page, logs = fresh(p)
    print("=== H. second doigt pendant un drag")
    r = gesture(page, *sq_center(page, "e2"), *sq_center(page, "e4"), extra_touch=sq_center(page, "b1")); v = line("drag e2->e4 + 2e doigt sur b1 à mi-course", r, "piece:w")
    s = snap(page); print("   après : e4 =", piece_on(page, "e4"), "e2 =", piece_on(page, "e2"), "| clone fantôme resté:", s["dragClone"], "| sélection:", s["selected"], "| nb pièces:", len(s["pos"]))
    r = gesture(page, *sq_center(page, "e7"), *sq_center(page, "e5"), extra_touch=sq_center(page, "d4")); v = line("drag e7->e5 + 2e doigt sur case vide d4", r, "piece:b")
    s = snap(page); print("   après : e5 =", piece_on(page, "e5"), "e7 =", piece_on(page, "e7"), "| clone fantôme resté:", s["dragClone"], "| nb pièces:", len(s["pos"]))
    r = gesture(page, *sq_center(page, "g1"), *sq_center(page, "f3")); line("coup suivant normal g1->f3 (le board est-il resté utilisable ?)", r, "piece:w")
    shot(page, "t07_H_multitouch")
    print("   logs:", [l for l in logs if "cancel a touchend" not in l][:3])
    browser.close()
