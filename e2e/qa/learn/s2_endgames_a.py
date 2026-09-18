import sys
sys.path.insert(0, 'e2e/qa/learn')
from egdrv import *

def best_chooser(page, board, n): return best(page, board)

def shuffle_queen(page, board, n):
    seq = ['e2a2', 'a2a1', 'a1a2', 'a2a1', 'a1a2', 'a2a1']
    mv = chess.Move.from_uci(seq[n]) if n < len(seq) else None
    return mv if mv and mv in board.legal_moves else None

def hang_queen(page, board, n):
    return chess.Move.from_uci('e2e4') if n == 0 else None

with sync_playwright() as p:
    for tag, eg_id, ch in [('eg_kq_shuffle', 'kq-mate', shuffle_queen), ('eg_kq_hang', 'kq-mate', hang_queen), ('eg_kq_best', 'kq-mate', best_chooser)]:
        browser, ctx, page, logs = open_mobile(p, standalone=True)
        page.add_init_script(RND_INIT)
        res = run(page, eg_id, ch, tag)
        print("   sessions:", learn_sessions(page))
        print("   LOGS:", logs)
        browser.close()
