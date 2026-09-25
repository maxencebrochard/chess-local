import sys
sys.path.insert(0, 'e2e/qa/learn')
from egdrv import *

def best_chooser(page, board, n): return best(page, board)

def shuffle_rook(page, board, n):
    """Tour qui se promène loin du roi noir, sans aucun progrès, en évitant la répétition."""
    rook = list(board.pieces(chess.ROOK, chess.WHITE))
    if not rook: return None
    bk = board.king(chess.BLACK)
    cands = []
    for mv in board.legal_moves:
        if mv.from_square != rook[0]: continue
        if chess.square_distance(mv.to_square, bk) <= 2: continue
        board.push(mv)
        bad = board.is_repetition(2) or board.is_stalemate() or board.is_checkmate()
        board.pop()
        if not bad: cands.append(mv)
    # reste sur les rangées 1-2 / colonnes a-b pour ne rien « couper »
    cands.sort(key=lambda m: (chess.square_rank(m.to_square), chess.square_file(m.to_square), (m.to_square * 7 + n * 3) % 5))
    return cands[n % min(3, len(cands))] if cands else None

def draw_corner(page, board, n):
    # pion tour : le roi reste dans le coin
    for u in ('h8g8', 'g8h8', 'g8f8', 'f8g8'):
        mv = chess.Move.from_uci(u)
        if mv in board.legal_moves:
            return mv
    return next(iter(board.legal_moves), None)

SCEN = [
    ('eg_kr_shuffle', 'kr-mate', shuffle_rook, None),
    ('eg_kpopp_best', 'kp-opposition-1', best_chooser, None),
    ('eg_corner_draw', 'rook-pawn-corner', draw_corner, 1200),
    ('eg_kpfront_best', 'kp-king-front', best_chooser, None),
]
only = sys.argv[1:] 
with sync_playwright() as p:
    for tag, eg_id, ch, elo in SCEN:
        if only and tag not in only: continue
        browser, ctx, page, logs = open_mobile(p, standalone=True)
        page.add_init_script(RND_INIT)
        try:
            res = run(page, eg_id, ch, tag, elo=elo)
        except Exception as ex:
            print("   EXC", repr(ex)[:300]); shot(page, f"{tag}_exc")
        print("   LOGS:", logs)
        browser.close()
