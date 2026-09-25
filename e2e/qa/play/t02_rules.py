"""Règles en mode 2 joueurs local (déterministe) : roques, e.p., promotion, illégal, clouage, échec, pat, répétition, mat."""
from common import *

PROMO_GLYPH = {True: {"q": "♕", "r": "♖", "b": "♗", "n": "♘"}, False: {"q": "♛", "r": "♜", "b": "♝", "n": "♞"}}
counter = {"n": 0}


def do_move(page, board, san, method=None, promo_shot=None):
    mv = board.parse_san(san)
    frm, to = chess.square_name(mv.from_square), chess.square_name(mv.to_square)
    counter["n"] += 1
    method = method or ("drag" if counter["n"] % 2 else "tap")
    if method == "drag":
        drag_piece(page, frm, to)
    else:
        tap_move(page, frm, to)
    if mv.promotion:
        page.wait_for_timeout(300)
        if promo_shot:
            shot(page, promo_shot)
        letter = chess.piece_symbol(mv.promotion)
        page.locator("button", has_text=PROMO_GLYPH[board.turn][letter]).first.click()
        page.wait_for_timeout(300)
    board.push(mv)
    page.wait_for_timeout(200)
    ok = board_to_dict(board) == dom_position(page)
    print(f"   {san:8} [{method}] {'OK' if ok else 'MISMATCH'}")
    return ok


def new_local(page, tc="Illimité"):
    goto_play(page)
    setup(page, mode="local", tc=tc)
    counter["n"] = 0
    return chess.Board()


def style_of(page, square):
    return page.evaluate("""(sq) => { const e = document.querySelector(`[data-square='${sq}']`); return e ? e.getAttribute('style') : null }""", square)


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)

    # ---------- A. Roques ----------
    print("A. Roques")
    b = new_local(page)
    for san in ["e4", "e5", "Nf3", "Nc6", "Bc4", "d6"]:
        do_move(page, b, san)
    # roi sur la tour (geste chess.com) : e1 -> h1
    drag_piece(page, "e1", "h1")
    print("   roque par drag roi->tour h1 accepté ?", piece_on(page, "g1") == "wK")
    if piece_on(page, "g1") != "wK":
        do_move(page, b, "O-O", method="drag")
    else:
        b.push_san("O-O")
    print("   après O-O : g1", piece_on(page, "g1"), "f1", piece_on(page, "f1"), "h1", piece_on(page, "h1"))
    for san in ["Bg4", "d3", "Qd7", "Nc3"]:
        do_move(page, b, san)
    do_move(page, b, "O-O-O", method="tap")
    print("   après O-O-O : c8", piece_on(page, "c8"), "d8", piece_on(page, "d8"), "a8", piece_on(page, "a8"))
    shot(page, "rules_castles")
    print("   notation liste:", page.locator("main [data-current]").all_inner_texts())

    # ---------- B. Prise en passant blanche + promotion sous-promotion cavalier ----------
    print("B. e.p. + sous-promotion")
    b = new_local(page)
    for san in ["e4", "a6", "e5", "d5"]:
        do_move(page, b, san)
    tap_square(page, "e5"); page.wait_for_timeout(250)
    print("   style d6 (cible e.p.) :", style_of(page, "d6"))
    shot(page, "rules_ep_targets")
    tap_square(page, "e5"); page.wait_for_timeout(150)
    do_move(page, b, "exd6", method="drag")
    print("   d5 après e.p. :", piece_on(page, "d5"), "d6:", piece_on(page, "d6"))
    for san in ["Nc6", "dxc7", "Nf6"]:
        do_move(page, b, san)
    # promotion : ouvre l'overlay par drag, essaie d'annuler en tapant hors des boutons
    drag_piece(page, "c7", "d8")
    page.wait_for_timeout(300)
    shot(page, "rules_promo_overlay")
    n_btn = page.locator("button", has_text="♘").count()
    print("   overlay promo ouvert :", n_btn == 1, "| c7:", piece_on(page, "c7"), "d8:", piece_on(page, "d8"))
    # tap sur le fond de l'overlay (coin haut gauche du board)
    x, y = sq_center(page, "a8")
    page.touchscreen.tap(x, y); page.wait_for_timeout(300)
    print("   après tap hors boutons, overlay toujours là :", page.locator("button", has_text="♘").count() == 1)
    ob = page.locator("button", has_text="♘").first.bounding_box()
    print("   bouton promo taille:", ob)
    page.locator("button", has_text="♘").first.click(); page.wait_for_timeout(400)
    b.push_san("cxd8=N")
    print("   d8 après sous-promotion :", piece_on(page, "d8"), "| sync:", board_to_dict(b) == dom_position(page))
    print("   notation:", page.locator("main [data-current]").all_inner_texts()[-1])
    shot(page, "rules_promo_done")

    # ---------- C. e.p. noire, sous-promotion tour avec échec, sortie d'échec obligatoire ----------
    print("C. e.p. noir + promo tour + échec")
    b = new_local(page)
    for san in ["h3", "e5", "a3", "e4", "d4"]:
        do_move(page, b, san)
    do_move(page, b, "exd3", method="tap")
    print("   d4 après e.p. noir :", piece_on(page, "d4"))
    for san in ["Nf3", "dxc2", "Nd4"]:
        do_move(page, b, san)
    do_move(page, b, "cxd1=R+", method="tap", promo_shot="rules_promo_black")
    print("   d1:", piece_on(page, "d1"), "| style roi e1 (échec):", style_of(page, "e1"))
    shot(page, "rules_check")
    # coup qui ne pare pas l'échec
    n0 = ply_count(page)
    tap_move(page, "a3", "a4")
    drag_piece(page, "b2", "b4")
    print("   coups ne parant pas l'échec refusés :", ply_count(page) == n0 and board_to_dict(b) == dom_position(page))
    tap_square(page, "e1"); page.wait_for_timeout(250)
    shot(page, "rules_check_king_selected")
    tap_square(page, "e1")
    do_move(page, b, "Kxd1", method="drag")

    # ---------- D. Coups illégaux + clouage ----------
    print("D. Illégal + clouage")
    b = new_local(page)
    n0 = ply_count(page)
    tap_move(page, "e2", "e5")
    drag_piece(page, "e2", "e5")
    drag_piece(page, "b1", "b3")
    drag_piece(page, "e7", "e5")  # pièce adverse, pas au trait
    tap_move(page, "e7", "e5")
    print("   illégaux refusés :", ply_count(page) == n0 and board_to_dict(b) == dom_position(page))
    for san in ["d4", "e5", "dxe5", "d6", "exd6", "Bxd6", "Nc3", "Bb4"]:
        do_move(page, b, san)
    n0 = ply_count(page)
    tap_square(page, "c3"); page.wait_for_timeout(250)
    shot(page, "rules_pinned_selected")
    dots = page.evaluate("""() => Array.from(document.querySelectorAll('[data-square]')).filter(e => (e.getAttribute('style')||'').includes('radial-gradient')).map(e => e.getAttribute('data-square'))""")
    print("   cases cibles affichées pour Cc3 cloué :", dots)
    tap_square(page, "d5"); page.wait_for_timeout(200)
    drag_piece(page, "c3", "d5")
    print("   cavalier cloué refusé :", ply_count(page) == n0 and board_to_dict(b) == dom_position(page))

    # ---------- E. Mat du fou (modale, échec) ----------
    print("E. Mat du fou")
    b = new_local(page)
    for san in ["f3", "e5", "g4"]:
        do_move(page, b, san)
    do_move(page, b, "Qh4#", method="drag")
    page.wait_for_timeout(1200)
    print("   modale:", page.locator("div.fixed").inner_text().replace("\n", " | "))
    shot(page, "rules_mate_modal_local")
    mb = page.locator("div.fixed > div").first.bounding_box()
    print("   modale box:", mb)
    # ferme la modale par le fond
    page.touchscreen.tap(196, 40); page.wait_for_timeout(400)
    print("   modale fermée par tap fond :", page.locator("div.fixed").count() == 0)
    shot(page, "rules_mate_after_close")
    print("   boutons restants:", [t for t in page.locator("main button").all_inner_texts() if t.strip() and len(t) < 30][-6:])
    print("   bouton Bilan accessible hors modale :", page.locator("main button", has_text="Bilan").count())

    # ---------- F. Pat (Sam Loyd) ----------
    print("F. Pat")
    b = new_local(page)
    for san in ["e3", "a5", "Qh5", "Ra6", "Qxa5", "h5", "h4", "Rah6", "Qxc7", "f6", "Qxd7+", "Kf7", "Qxb7", "Qd3", "Qxb8", "Qh7", "Qxc8", "Kg6", "Qe6"]:
        do_move(page, b, san)
    page.wait_for_timeout(1200)
    print("   modale:", page.locator("div.fixed").inner_text().replace("\n", " | ") if page.locator("div.fixed").count() else "AUCUNE")
    shot(page, "rules_stalemate")

    # ---------- G. Triple répétition ----------
    print("G. Répétition")
    b = new_local(page)
    for san in ["Nf3", "Nf6", "Ng1", "Ng8", "Nf3", "Nf6", "Ng1", "Ng8"]:
        do_move(page, b, san)
    page.wait_for_timeout(1200)
    print("   modale:", page.locator("div.fixed").inner_text().replace("\n", " | ") if page.locator("div.fixed").count() else "AUCUNE")
    shot(page, "rules_threefold")

    # Archive : parties locales sauvegardées
    page.locator("div.fixed button", has_text="Nouvelle partie").click(); page.wait_for_timeout(300)
    page.locator("nav a", has_text="Archive").last.click(); page.wait_for_timeout(1000)
    shot(page, "rules_archive")
    print("Archive:", page.locator("main").inner_text()[:600].replace("\n", " | "))
    print("LOGS:", logs)
    browser.close()
