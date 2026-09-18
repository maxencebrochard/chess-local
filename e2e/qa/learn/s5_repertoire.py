"""Archive NON vide : 2 vraies parties courtes contre Noa (Blancs puis Noirs), puis drill d'ouvertures."""
import sys, json
sys.path.insert(0, 'e2e/qa/learn')
from egdrv import *
from s3_tactics_lib import verdict_text

def play_game(page, color, my_moves_fn, n_moves):
    page.goto(f"{BASE}/#/"); page.wait_for_timeout(500)
    page.goto(f"{BASE}/#/jouer"); page.wait_for_timeout(600)
    page.reload(); page.wait_for_timeout(1200)
    page.locator("button", has_text="Noa").first.tap(); page.wait_for_timeout(150)
    page.locator("button", has_text="Blancs" if color == 'w' else "Noirs").first.tap(); page.wait_for_timeout(150)
    page.get_by_role("button", name="Jouer", exact=True).tap()
    page.wait_for_selector("[id^='chessboard-']", timeout=15000); page.wait_for_timeout(800)
    board = chess.Board()
    def sync_bot():
        kind, mv, dt = wait_bot(page, board, timeout_s=30)
        return kind
    if color == 'b':
        print("   bot ouvre:", sync_bot(), board.peek().uci() if board.move_stack else None)
    for n in range(n_moves):
        mv = my_moves_fn(board, n)
        if mv is None or mv not in board.legal_moves:
            mv = native_best(board, 8) or list(board.legal_moves)[0]
        san = board.san(mv)
        play_my_move(page, board, mv, 'tap' if n % 2 == 0 else 'drag')
        k = sync_bot()
        print(f"   {n+1}. {san} -> bot {board.peek().uci() if k == 'move' else k}")
        if board.is_game_over() or k != 'move': break
    page.locator("button", has_text="Abandonner").first.tap(); page.wait_for_timeout(1200)
    shot(page, f"s5_game_{color}_over")
    return board

def white_moves(board, n):
    return [chess.Move.from_uci(u) for u in ('e2e4', 'g1f3', 'f1c4', 'd2d3', 'e1g1')][n] if n < 5 else None

def black_moves(board, n):
    # répond e5 / Cc6 / Cf6 autant que possible
    for u in ('e7e5', 'b8c6', 'g8f6', 'f8c5', 'd7d6'):
        mv = chess.Move.from_uci(u)
        if mv in board.legal_moves: return mv
    return None

with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.add_init_script(RND_INIT)
    print("== partie 1 (Blancs)"); b1 = play_game(page, 'w', white_moves, 5)
    print("== partie 2 (Noirs)"); b2 = play_game(page, 'b', black_moves, 5)
    games = db_eval(page, "db.games.toArray()")
    for g in games: print("  game:", g['mode'], g['playerColor'], g['result'], g['termination'], '|', g['pgn'].split('\n')[-1][:120])
    lines = page.evaluate("async () => { const m = await import('/src/lib/repertoire.ts'); return await m.buildDrillLines() }")
    print("== buildDrillLines:")
    for l in lines: print("  ", l['eco'], l['name'], l['playerColor'], 'joué', l['timesPlayed'], 'perdu', l['losses'], len(l['uci']), 'demi-coups')
    # seed complémentaire : 2 parties connues (perdues) pour tester le tri et le drill côté noir
    db_eval(page, """db.games.bulkAdd([
      {date: Date.now(), mode:'bot', botId:'noa', playerColor:'b', timeControl:'10+0', timeClass:'rapid', pgn:'1. e4 c6 2. d4 d5 3. Nc3 dxe4 4. Nxe4 Bf5 5. Ng3 Bg6', result:'1-0', termination:'par abandon'},
      {date: Date.now(), mode:'bot', botId:'noa', playerColor:'b', timeControl:'10+0', timeClass:'rapid', pgn:'1. e4 c6 2. d4 d5 3. Nc3 dxe4 4. Nxe4 Bf5 5. Ng3 Bg6 6. h4 h6', result:'1-0', termination:'par abandon'}
    ])""")
    lines = page.evaluate("async () => { const m = await import('/src/lib/repertoire.ts'); return await m.buildDrillLines() }")
    print("== buildDrillLines après seed Caro-Kann (2 défaites, Noirs):")
    for l in lines: print("  ", l['eco'], l['name'], l['playerColor'], 'joué', l['timesPlayed'], 'perdu', l['losses'], len(l['uci']), 'demi-coups')
    # drill de la 1re ligne (la plus perdue)
    page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1200)
    set_rnd(page, 0.01)
    start_domain(page, 'Ouvertures')
    it = get_session(page)['session']['items'][0]
    print("== drill:", it['line']['name'], it['line']['playerColor'], 'depth', it['depth'], it['line']['uci'])
    print(" leçon:", page.locator('.bg-white').first.inner_text().replace('\n', ' | '))
    shot(page, "s5_drill_lesson")
    go_play(page); page.wait_for_timeout(900)
    shot(page, "s5_drill_play")
    print(" orientation noire ? a8 en bas-droite:", page.evaluate("() => { const a=document.querySelector(\"[data-square='a8']\").getBoundingClientRect(); const h=document.querySelector(\"[data-square='h1']\").getBoundingClientRect(); return a.y > h.y }"))
    # joue la ligne
    board = chess.Board(); line = it['line']['uci']; color = it['line']['playerColor']
    for i in range(it['depth']):
        mv = chess.Move.from_uci(line[i])
        if (board.turn == chess.WHITE) == (color == 'w'):
            play_my_move(page, board, mv, 'drag' if i % 4 == 1 else 'tap')
        else:
            board.push(mv)
        for _ in range(50):
            if board_fen_pieces(page) == bmap(board): break
            page.wait_for_timeout(100)
    page.wait_for_timeout(900)
    print(" verdict:", verdict_text(page), ratings(page).get('learn-opening'))
    shot(page, "s5_drill_end")
    print("LOGS:", [l[:160] for l in logs])
    browser.close()
