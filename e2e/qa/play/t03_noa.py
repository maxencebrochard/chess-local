"""Partie complète contre Noa (400) jusqu'au mat, 10 min, puis Archive et Stats dans le même contexte."""
import time
import chess.engine
from common import *

COLOR = sys.argv[1] if len(sys.argv) > 1 else "Blancs"   # Blancs | Noirs
TC = sys.argv[2] if len(sys.argv) > 2 else "10 min"
TAG = "noa_w" if COLOR == "Blancs" else "noa_b"
PROMO_GLYPH = {True: {"q": "♕", "r": "♖", "b": "♗", "n": "♘"}, False: {"q": "♛", "r": "♜", "b": "♝", "n": "♞"}}


def highlighted(page):
    return page.evaluate("""() => Array.from(document.querySelectorAll('[data-square]')).filter(e => {
        const own = e.cloneNode(true); own.querySelectorAll('svg').forEach(s => s.remove());
        return own.outerHTML.includes('255, 255, 51')
    }).map(e => e.getAttribute('data-square')).sort()""")


def active_clock(page):
    return page.evaluate("""() => Array.from(document.querySelectorAll('main .font-mono.text-xl')).map(e => [e.textContent, e.className.includes('bg-neutral-100') || e.className.includes('bg-red-900')])""")


sf = chess.engine.SimpleEngine.popen_uci("/usr/local/bin/stockfish")
with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    goto_play(page)
    setup(page, mode="bot", bot="Noa", color=COLOR, tc=TC)
    me = chess.WHITE if COLOR == "Blancs" else chess.BLACK
    board = chess.Board()
    shot(page, f"{TAG}_start")
    print("noms:", page.locator("main span.font-semibold").all_inner_texts())
    print("pendules au départ:", active_clock(page))
    print("orientation: a1 en bas à gauche ?", sq_center(page, "a1"), "h8:", sq_center(page, "h8"))
    delays = []
    n = 0
    if me == chess.BLACK:
        t0 = time.time()
        w = wait_ply(page, 1)
        page.wait_for_timeout(300)
        mv = sync_bot_move(page, board)
        print(f"   premier coup du bot: {mv} après {time.time()-t0:.2f}s")
        page.wait_for_timeout(200)
        shot(page, f"{TAG}_bot_first_move")
        print("   surbrillance:", highlighted(page))
    while not board.is_game_over() and n < 120:
        res = sf.play(board, chess.engine.Limit(time=0.15))
        mv = res.move
        frm, to = chess.square_name(mv.from_square), chess.square_name(mv.to_square)
        n += 1
        method = "drag" if n % 2 else "tap"
        if method == "drag":
            drag_piece(page, frm, to)
        else:
            tap_move(page, frm, to)
        if mv.promotion:
            page.wait_for_timeout(250)
            shot(page, f"{TAG}_promo_{n}")
            page.locator("button", has_text=PROMO_GLYPH[board.turn][chess.piece_symbol(mv.promotion)]).first.click()
            page.wait_for_timeout(250)
        san = board.san(mv)
        board.push(mv)
        t_after = time.time()
        page.wait_for_timeout(120)
        ok = board_to_dict(board) == dom_position(page)
        if not ok:
            # peut-être que le bot a déjà répondu
            bm = sync_bot_move(page, board)
            print(f"   {n}. {san} [{method}] DOM différent ; coup bot déjà joué ? {bm}")
            if bm is None:
                shot(page, f"{TAG}_mismatch_{n}")
                print("   !!! désynchronisation, arrêt"); break
            continue
        if board.is_game_over():
            print(f"   {n}. {san} [{method}] -> fin ({board.result()})")
            break
        if n == 3:
            # jouer pendant que le bot réfléchit : tente un second coup immédiatement
            before = ply_count(page)
            mv2 = next(iter(board.copy().legal_moves), None)
            # tente de bouger un de mes pions (pas au trait)
            my_pawn = next((chess.square_name(s) for s in board.pieces(chess.PAWN, me)), None)
            if my_pawn:
                tap_square(page, my_pawn)
                page.wait_for_timeout(80)
                sel = highlighted(page)
                print("   tap sur ma pièce pendant réflexion du bot, surbrillances:", sel)
        clk = active_clock(page)
        target_ply = len(board.move_stack) + 1
        w = wait_ply(page, target_ply, timeout=25000)
        dt = time.time() - t_after
        if w is None:
            print(f"   {n}. {san}: BOT NE RÉPOND PAS (25 s)"); shot(page, f"{TAG}_bot_stuck_{n}"); break
        page.wait_for_timeout(150)
        bm = sync_bot_move(page, board)
        delays.append(dt)
        hl = highlighted(page)
        exp = sorted([chess.square_name(bm.from_square), chess.square_name(bm.to_square)]) if bm else None
        flag = "" if (bm and all(s in hl for s in exp)) else f" SURBRILLANCE?? {hl} vs {exp}"
        print(f"   {n}. {san} [{method}] bot: {bm} ({dt:.2f}s) pendules pendant réflexion bot: {clk}{flag}")
        if bm is None:
            shot(page, f"{TAG}_sync_fail_{n}"); break
        if board.is_check():
            shot(page, f"{TAG}_incheck_{n}")
        if n in (2, 6):
            shot(page, f"{TAG}_move_{n}")
    sf.quit()
    print("délais bot: min %.2f max %.2f moy %.2f" % (min(delays), max(delays), sum(delays) / len(delays)) if delays else "aucun délai")
    page.wait_for_timeout(1500)
    shot(page, f"{TAG}_gameover_modal")
    if page.locator("div.fixed").count():
        print("MODALE:", page.locator("div.fixed").inner_text().replace("\n", " | "))
        print("modale boutons:", page.locator("div.fixed button").all_inner_texts())
    else:
        print("PAS DE MODALE")
    print("pendules fin:", active_clock(page))
    page.wait_for_timeout(1500)
    print("pendules 1,5 s plus tard (doivent être figées):", active_clock(page))
    # Archive + Stats même contexte
    if page.locator("div.fixed").count():
        page.touchscreen.tap(196, 30); page.wait_for_timeout(400)
    shot(page, f"{TAG}_after_modal_closed")
    page.locator("nav a", has_text="Archive").last.click(); page.wait_for_timeout(1200)
    shot(page, f"{TAG}_archive")
    print("ARCHIVE:", page.locator("main").inner_text()[:500].replace("\n", " | "))
    page.locator("nav a", has_text="Stats").last.click(); page.wait_for_timeout(1200)
    shot(page, f"{TAG}_stats")
    print("STATS:", page.locator("main").inner_text()[:700].replace("\n", " | "))
    rat = page.evaluate("""() => new Promise(res => { const r = indexedDB.open('chess-local'); r.onsuccess = () => { const db = r.result; const tx = db.transaction(['ratings','games']); const out = {}; tx.objectStore('ratings').getAll().onsuccess = e => out.ratings = e.target.result; tx.objectStore('games').getAll().onsuccess = e => out.games = e.target.result.map(g => [g.id, g.result, g.termination, g.playerRatingAfter, g.timeClass]); tx.oncomplete = () => res(out) } })""")
    print("IDB:", rat)
    print("LOGS:", logs)
    browser.close()
