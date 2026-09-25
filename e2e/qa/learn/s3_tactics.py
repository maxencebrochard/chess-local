"""Tactiques : 3 puzzles (tap, drag, raté exprès), Elo Dexie, Réessayer (double comptage ? delta périmé ?), board après Raté."""
import sys, json
sys.path.insert(0, 'e2e/qa/learn')
from egdrv import *

def verdict_text(page):
    return page.evaluate("() => { const b=[...document.querySelectorAll('div.flex.items-center.gap-2.px-3.py-2')][0]; return b ? b.innerText.replace(/\\n/g,' | ') : null }")

def verdict_geom(page):
    return page.evaluate("""() => {
      const bar=[...document.querySelectorAll('div.flex.items-center.gap-2.px-3.py-2')][0]; if(!bar) return null
      const v=bar.querySelector('span'); const r=v.getBoundingClientRect(); const br=bar.getBoundingClientRect()
      const next=[...bar.querySelectorAll('button')].pop().getBoundingClientRect()
      return {verdictH: r.height, verdictW: r.width, lineH: parseFloat(getComputedStyle(v).lineHeight), barRight: br.right, nextRight: next.right, vw: innerWidth, barBottom: br.bottom, vh: innerHeight,
              btns:[...bar.querySelectorAll('button')].map(b=>{const q=b.getBoundingClientRect(); return [b.innerText.replace(/\\n/g,' '), Math.round(q.width), Math.round(q.height)]})}
    }""")

def solve(page, puzzle, how='tap', wrong_at=None):
    """Joue la solution. wrong_at = index (dans moves) où jouer exprès un mauvais coup légal."""
    board = chess.Board(puzzle['fen'])
    moves = puzzle['moves']
    board.push(chess.Move.from_uci(moves[0]))
    # attendre le coup d'amorce
    for _ in range(40):
        if board_fen_pieces(page) == bmap(board): break
        page.wait_for_timeout(100)
    i = 1
    while i < len(moves):
        mv = chess.Move.from_uci(moves[i])
        if wrong_at == i:
            alts = [m for m in board.legal_moves if m != mv and not board.gives_check(m) and not m.promotion]
            bad = alts[0]
            print(f"     coup FAUX exprès: {board.san(bad)} (attendu {board.san(mv)})")
            play_my_move(page, board, bad, how); board.pop()
            page.wait_for_timeout(700)
            return 'wrong-played'
        play_my_move(page, board, mv, how)
        page.wait_for_timeout(250)
        i += 1
        if i < len(moves):
            board.push(chess.Move.from_uci(moves[i])); i += 1
            for _ in range(40):
                if board_fen_pieces(page) == bmap(board): break
                page.wait_for_timeout(100)
    page.wait_for_timeout(600)
    return 'solved'

with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.add_init_script(RND_INIT)
    page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1200)
    set_rnd(page, 0.01)  # thème fork
    start_domain(page, 'Tactiques')
    sess = get_session(page)['session']
    print("thème:", sess['items'][0]['theme'], [ (i['puzzle']['id'], i['puzzle']['rating'], len(i['puzzle']['moves'])) for i in sess['items']])
    print("puzzles distincts:", len({i['puzzle']['id'] for i in sess['items']}))
    shot(page, "s3_tactic_lesson")
    # --- item 1 : tap, réussi
    go_play(page)
    print(" item1:", solve(page, sess['items'][0]['puzzle'], 'tap'), "| verdict:", verdict_text(page), "| elo:", ratings(page).get('learn-tactic'))
    print("  geom:", verdict_geom(page)); shot(page, "s3_item1_success")
    # Réessayer après succès -> rejouer -> pas de re-score
    page.locator("button", has_text="Réessayer").tap(); page.wait_for_timeout(400)
    print("  après Réessayer: verdict visible?", verdict_text(page), "| leçon?", page.get_by_role('button', name="C'est parti").count())
    print("  re-solve:", solve(page, sess['items'][0]['puzzle'], 'drag'), "| verdict:", verdict_text(page), "| elo:", ratings(page).get('learn-tactic'), "| nb sessions:", len(learn_sessions(page)))
    page.locator("button", has_text="Suivant").tap(); page.wait_for_timeout(500)
    # --- item 2 : raté exprès puis Réessayer réussi -> delta périmé ?
    print(" item2 phase leçon?", page.get_by_role('button', name="C'est parti").count(), "| header:", page.locator('header h1').inner_text().replace('\n',' '))
    shot(page, "s3_item2_lesson")
    go_play(page)
    print(" item2:", solve(page, sess['items'][1]['puzzle'], 'tap', wrong_at=1), "| verdict:", verdict_text(page), "| elo:", ratings(page).get('learn-tactic'))
    shot(page, "s3_item2_fail")
    # le board reste-t-il jouable après Raté ?
    b = chess.Board(sess['items'][1]['puzzle']['fen']); b.push(chess.Move.from_uci(sess['items'][1]['puzzle']['moves'][0]))
    good = chess.Move.from_uci(sess['items'][1]['puzzle']['moves'][1])
    tap_move(page, chess.square_name(good.from_square), chess.square_name(good.to_square)); page.wait_for_timeout(500)
    b.push(good)
    print("  board jouable après Raté ? (bon coup accepté):", board_fen_pieces(page) == bmap(b), "| verdict:", verdict_text(page))
    shot(page, "s3_item2_fail_then_move")
    page.locator("button", has_text="Réessayer").tap(); page.wait_for_timeout(400)
    print("  re-solve:", solve(page, sess['items'][1]['puzzle'], 'tap'), "| verdict:", verdict_text(page), "| elo:", ratings(page).get('learn-tactic'), "| nb sessions:", len(learn_sessions(page)))
    shot(page, "s3_item2_retry_success")
    page.locator("button", has_text="Suivant").tap(); page.wait_for_timeout(500)
    # --- item 3 : drag, réussi
    go_play(page)
    print(" item3:", solve(page, sess['items'][2]['puzzle'], 'drag'), "| verdict:", verdict_text(page), "| elo:", ratings(page).get('learn-tactic'))
    page.locator("button", has_text="Suivant").tap(); page.wait_for_timeout(700)
    print(" FIN:", page.locator("h1").first.inner_text(), "|", page.locator("p.text-neutral-400").first.inner_text())
    shot(page, "s3_end_screen")
    print(" sessions:", [(s['itemId'], s['success'], s['ratingAfter']) for s in learn_sessions(page)])
    print("LOGS:", logs)
    browser.close()
