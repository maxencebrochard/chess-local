"""Ouvertures, archive VIDE : lignes de repli, textes, mauvais coup, 1 faute vs 2 fautes, Elo."""
import sys, json
sys.path.insert(0, 'e2e/qa/learn')
from egdrv import *
from s3_tactics_lib import verdict_text

def drill_header(page):
    return page.evaluate("""() => { const e=[...document.querySelectorAll('div.truncate')][0]; if(!e) return null; return {text:e.innerText, truncated: e.scrollWidth > e.clientWidth, sw:e.scrollWidth, cw:e.clientWidth} }""")

def msg(page):
    return page.evaluate("() => document.querySelector('p.min-h-\\\\[34px\\\\]')?.innerText ?? null")

def play_line(page, line, depth, color, wrong_plies=()):
    board = chess.Board()
    for i in range(depth):
        mv = chess.Move.from_uci(line[i])
        mine = (board.turn == chess.WHITE) == (color == 'w')
        if mine:
            if i in wrong_plies:
                bad = [m for m in board.legal_moves if m != mv][3]
                print(f"     faute exprès au demi-coup {i}: {board.san(bad)} au lieu de {board.san(mv)}")
                tap_move(page, chess.square_name(bad.from_square), chess.square_name(bad.to_square)); page.wait_for_timeout(500)
                print("     message:", msg(page), "| pièce revenue:", board_fen_pieces(page) == bmap(board))
                shot(page, f"s4_wrong_{i}_{line[1]}")
            play_my_move(page, board, mv, 'tap' if i % 4 == 0 else 'drag')
        else:
            board.push(mv)
        for _ in range(40):
            if board_fen_pieces(page) == bmap(board): break
            page.wait_for_timeout(100)
    page.wait_for_timeout(900)

with sync_playwright() as p:
    for idx, wrong in [(2, (2,)), (4, (0, 2)), (5, ()), (0, ())]:
        browser, ctx, page, logs = open_mobile(p, standalone=True)
        page.add_init_script(RND_INIT)
        page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1200)
        set_rnd(page, (idx + 0.5) / 6)
        start_domain(page, 'Ouvertures')
        it = get_session(page)['session']['items'][0]
        print(f"\n=== idx={idx} {it['line']['name']} eco={it['line']['eco']} color={it['line']['playerColor']} depth={it['depth']} diff={it['difficulty']} uci={it['line']['uci']}")
        print(" leçon:", page.locator('.bg-white').first.inner_text().replace('\n', ' | '))
        shot(page, f"s4_lesson_{idx}")
        go_play(page)
        print(" header drill:", drill_header(page))
        shot(page, f"s4_play_{idx}")
        play_line(page, it['line']['uci'], it['depth'], it['line']['playerColor'], wrong)
        print(" verdict:", verdict_text(page), "| elo:", ratings(page).get('learn-opening'))
        shot(page, f"s4_end_{idx}")
        print(" LOGS:", [l[:120] for l in logs])
        browser.close()
