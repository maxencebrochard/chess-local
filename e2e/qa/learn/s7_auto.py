"""Séance auto : ordre des domaines, abandon, écran de fin, aller-retour Analyser sur une finale (état du board)."""
import sys, json
sys.path.insert(0, 'e2e/qa/learn')
from egdrv import *
from s3_tactics_lib import verdict_text

def start_auto(page):
    page.get_by_role("button", name="Séance", exact=True).tap()
    page.wait_for_selector("text=C'est parti", timeout=30000); page.wait_for_timeout(300)
    return get_session(page)['session']

def fail_fast(page, sess):
    """Rate chaque item le plus vite possible, retourne quand l'écran de fin est affiché."""
    for k, it in enumerate(sess['items']):
        go_play(page); page.wait_for_timeout(700)
        if it['kind'] == 'endgame':
            board = chess.Board(it['endgame']['fen'])
            # donne la pièce ou joue n'importe quoi jusqu'au verdict
            for n in range(40):
                if verdict_text(page): break
                mv = list(board.legal_moves)[0]
                play_my_move(page, board, mv, 'tap')
                wait_bot(page, board, timeout_s=15)
        elif it['kind'] in ('tactic', 'strategy'):
            pz = it['puzzle']; board = chess.Board(pz['fen']); board.push(chess.Move.from_uci(pz['moves'][0]))
            for _ in range(40):
                if board_fen_pieces(page) == bmap(board): break
                page.wait_for_timeout(100)
            good = chess.Move.from_uci(pz['moves'][1])
            bad = [m for m in board.legal_moves if m != good and not m.promotion and not (board.push(m), board.is_checkmate(), board.pop())[1]][0]
            play_my_move(page, board, bad, 'tap'); page.wait_for_timeout(600)
        elif it['kind'] == 'opening':
            board = chess.Board(); line = it['line']['uci']
            if it['line']['playerColor'] == 'b':
                board.push(chess.Move.from_uci(line[0])); page.wait_for_timeout(900)
            exp = chess.Move.from_uci(line[len(board.move_stack)])
            bads = [m for m in board.legal_moves if m != exp][:2]
            for b in bads:
                tap_move(page, chess.square_name(b.from_square), chess.square_name(b.to_square)); page.wait_for_timeout(400)
            # puis dérouler la ligne
            for i in range(len(board.move_stack), it['depth']):
                mv = chess.Move.from_uci(line[i])
                if (board.turn == chess.WHITE) == (it['line']['playerColor'] == 'w'):
                    play_my_move(page, board, mv, 'tap')
                else:
                    board.push(mv)
                for _ in range(50):
                    if board_fen_pieces(page) == bmap(board): break
                    page.wait_for_timeout(100)
            page.wait_for_timeout(900)
        for _ in range(60):
            if verdict_text(page): break
            page.wait_for_timeout(250)
        print(f"     item {k+1}/{len(sess['items'])} {it['kind']}: {verdict_text(page)}")
        page.locator("button", has_text="Suivant").tap(); page.wait_for_timeout(600)

with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.add_init_script(RND_INIT)
    page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1200)
    # Finales à 800, Tactiques à 1500 : « le plus faible » serait Finales/Ouvertures/Stratégie, jamais Tactiques
    set_rating(page, 'learn-tactic', 1500, 5); set_rating(page, 'learn-endgame', 600, 5)
    page.reload(); page.wait_for_timeout(1200)
    order = []
    for n in range(5):
        set_rnd(page, 0.2)
        sess = start_auto(page)
        order.append(sess['domain'])
        print(f"== séance auto {n+1}: domaine={sess['domain']} items={len(sess['items'])} header={page.locator('header h1').inner_text()!r}")
        if n == 0:
            # abandon en cours : ✕ en phase jeu, sans confirmation ?
            go_play(page); page.wait_for_timeout(500)
            page.locator("header button", has_text="✕").first.tap(); page.wait_for_timeout(500)
            print("   abandon: accueil?", page.get_by_role("button", name="Séance", exact=True).count(), "| sessions en base:", len(learn_sessions(page)), "| stored:", get_session(page))
            set_rnd(page, 0.2)
            sess = start_auto(page)
            print("   relance après abandon: domaine=", sess['domain'])
        fail_fast(page, sess)
        print("   fin:", page.locator("h1").first.inner_text(), "|", page.locator("p.text-neutral-400").first.inner_text().replace('\n', ' '))
        if n == 0: shot(page, "s7_end_zero")
        page.locator("button", has_text="Terminer").tap(); page.wait_for_timeout(600)
    print("ORDRE:", order)
    print("ratings:", {k: v['value'] for k, v in ratings(page).items()})
    # --- aller-retour Analyser sur une finale en phase success : état du board ?
    page.goto(f"{BASE}/#/"); page.wait_for_timeout(300)
    eg = open_endgame(page, 'kq-mate', elo=800)
    go_play(page); page.wait_for_timeout(800)
    board = chess.Board(eg['fen'])
    for u in ('e2a2', 'a2a1', 'a1a2'):
        play_my_move(page, board, chess.Move.from_uci(u), 'tap'); wait_bot(page, board)
    page.wait_for_timeout(1200)
    before = board_fen_pieces(page); print("finale avant Analyser:", verdict_text(page), before)
    page.locator("button", has_text="Analyser").tap(); page.wait_for_timeout(1500)
    shot(page, "s7_eg_analyse")
    print(" /analyse label:", page.locator("main").inner_text()[:160].replace('\n', ' | '))
    page.locator("button", has_text="Retour à l'exercice").tap(); page.wait_for_timeout(1500)
    after = board_fen_pieces(page)
    print(" après retour:", verdict_text(page), after, "| board identique:", before == after, "| eval:", eval_label(page))
    shot(page, "s7_eg_back")
    print("LOGS:", [l[:200] for l in logs])
    browser.close()
