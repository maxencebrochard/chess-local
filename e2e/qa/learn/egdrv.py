"""Pilote de finale : joue de vrais coups (tap / drag tactile) et suit la partie avec python-chess."""
import sys, json, time
sys.path.insert(0, 'e2e/qa/learn')
from lh import *
import chess, chess.engine

EG_IDS = [e['id'] for e in ENDGAMES]

def pool_for(elo):
    close = [e for e in ENDGAMES if abs(e['difficulty'] - elo) <= 300]
    return close or ENDGAMES

def rnd_for(eg_id, elo):
    pool = pool_for(elo)
    ids = [e['id'] for e in pool]
    i = ids.index(eg_id)
    return (i + 0.5) / len(ids)

def bmap(board):
    out = {}
    for sq, pc in board.piece_map().items():
        out[chess.square_name(sq)] = ('w' if pc.color else 'b') + pc.symbol().upper()
    return out

def verdict(page):
    if page.locator("text=✓ Réussi").count(): return 'success'
    if page.locator("text=✗ Raté").count(): return 'fail'
    return None

def eval_label(page):
    return page.evaluate("() => document.querySelector('.h-7.w-full span')?.innerText ?? null")

def native_best(board, depth=14):
    try:
        eng = chess.engine.SimpleEngine.popen_uci('/usr/local/bin/stockfish')
        r = eng.play(board, chess.engine.Limit(depth=depth))
        eng.quit()
        return r.move
    except Exception:
        return None

def page_best(page, fen):
    """Second Engine WASM dans la page (repli quand le Stockfish natif plante)."""
    uci = page.evaluate("""async (fen) => {
      const m = await import('/src/lib/engine.ts')
      window.__qaEngine ??= new m.Engine()
      const r = await window.__qaEngine.search({ fen, depth: 14, multipv: 1 })
      return r.bestMove
    }""", fen)
    return chess.Move.from_uci(uci)

def best(page, board):
    return native_best(board) or page_best(page, board.fen())

def play_my_move(page, board, move, how='tap'):
    frm, to = chess.square_name(move.from_square), chess.square_name(move.to_square)
    if how == 'drag':
        drag_piece(page, frm, to)
    else:
        tap_move(page, frm, to, pause=180)
    if move.promotion:
        page.wait_for_timeout(200)
        idx = {chess.QUEEN: 0, chess.ROOK: 1, chess.BISHOP: 2, chess.KNIGHT: 3}[move.promotion]
        page.locator("div.absolute.inset-0.z-20 button").nth(idx).tap()
    board.push(move)

def wait_bot(page, board, timeout_s=25):
    """Attend la réponse du bot ; retourne ('move', move) | ('verdict', v) | ('timeout', None)."""
    t0 = time.time()
    target_before = bmap(board)
    while time.time() - t0 < timeout_s:
        v = verdict(page)
        dom = board_fen_pieces(page)
        if dom != target_before:
            for mv in board.legal_moves:
                board.push(mv)
                same = bmap(board) == dom
                board.pop()
                if same:
                    board.push(mv)
                    return ('move', mv, time.time() - t0)
        if v:
            # le verdict peut tomber pendant l'animation du coup du bot : on relit le DOM une fois
            page.wait_for_timeout(450)
            dom = board_fen_pieces(page)
            for mv in board.legal_moves:
                board.push(mv)
                same = bmap(board) == dom
                board.pop()
                if same:
                    board.push(mv)
                    return ('move', mv, time.time() - t0)
            return ('verdict', v, time.time() - t0)
        page.wait_for_timeout(120)
    return ('timeout', None, timeout_s)

def open_endgame(page, eg_id, elo=None):
    page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1000)
    if elo is not None:
        set_rating(page, 'learn-endgame', elo, 0)
        page.reload(); page.wait_for_timeout(1200)
    cur = (ratings(page).get('learn-endgame') or {'value': 800})['value']
    set_rnd(page, rnd_for(eg_id, cur))
    start_domain(page, 'Finales')
    item = get_session(page)['session']['items'][0]
    assert item['endgame']['id'] == eg_id, item['endgame']['id']
    return item['endgame']

def run(page, eg_id, chooser, tag, elo=None, max_moves=80, how_cycle=('tap', 'drag')):
    eg = open_endgame(page, eg_id, elo)
    r0 = ratings(page).get('learn-endgame')
    go_play(page)
    page.wait_for_timeout(800)
    board = chess.Board(eg['fen'])
    print(f"--- [{tag}] {eg_id} obj={eg['objective']} side={eg['side']} elo_avant={r0} eval_init={eval_label(page)}")
    shot(page, f"{tag}_start")
    log = []
    v = None
    for n in range(max_moves):
        mv = chooser(page, board, n)
        if mv is None: break
        san = board.san(mv)
        play_my_move(page, board, mv, how_cycle[n % len(how_cycle)])
        page.wait_for_timeout(150)
        if bmap(board) != board_fen_pieces(page):
            page.wait_for_timeout(500)
            if bmap(board) != board_fen_pieces(page):
                print(f"   !! coup {san} non appliqué au DOM (verdict={verdict(page)})")
        kind, val, dt = wait_bot(page, board) if not board.is_game_over() else ('over', None, 0)
        if kind == 'over':
            page.wait_for_timeout(1500)
        ev = eval_label(page)
        v = verdict(page)
        rep = board.peek().uci() if kind == 'move' else kind
        log.append((n + 1, san, rep, ev, v))
        print(f"   {n+1:2}. {san:8} bot={rep:8} dt={dt:.1f}s eval={ev} verdict={v} over={board.is_game_over()} plies={len(board.move_stack)}")
        if v: break
        if kind == 'timeout': break
    page.wait_for_timeout(1500)
    v = verdict(page)
    r1 = ratings(page).get('learn-endgame')
    delta_ui = page.evaluate("() => { const s=[...document.querySelectorAll('span')].find(e=>/^\\([+-]\\d+\\)$/.test(e.innerText.trim())); return s? s.innerText : null }")
    print(f"   => verdict={v} mat={board.is_checkmate()} pat={board.is_stalemate()} insuff={board.is_insufficient_material()} rep3={board.can_claim_threefold_repetition()} elo {r0} -> {r1} delta_ui={delta_ui} fen={board.fen()}")
    shot(page, f"{tag}_end")
    return dict(verdict=v, board=board, r0=r0, r1=r1, log=log, delta_ui=delta_ui)
