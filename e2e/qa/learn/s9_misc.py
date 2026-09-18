"""Divers : finale à objectif nulle RATÉE, saut de layout « Je vérifie… », taille du board par domaine, cibles tactiles."""
import sys, json
sys.path.insert(0, 'e2e/qa/learn')
from egdrv import *
from s3_tactics_lib import verdict_text
PGN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"

def flee(page, board, n):
    pawns = list(board.pieces(chess.PAWN, chess.BLACK))
    tgt = pawns[0] if pawns else board.king(chess.BLACK)
    ms = sorted(board.legal_moves, key=lambda m: -chess.square_distance(m.to_square, tgt))
    return ms[0] if ms else None

def board_box(page):
    return page.evaluate("() => { const b=document.querySelector(\"[id^='chessboard-']\").getBoundingClientRect(); return {x:b.x, y:b.y, w:b.width} }")

with sync_playwright() as p:
    # 1) objectif nulle raté
    browser, ctx, page, logs = open_mobile(p, standalone=True); page.add_init_script(RND_INIT)
    run(page, 'kp-defense-front', flee, 'eg_draw_fail', elo=1400)
    browser.close()

    # 2) taille/position du board par domaine + cibles tactiles
    browser, ctx, page, logs = open_mobile(p, standalone=True); page.add_init_script(RND_INIT)
    for label in ("Finales", "Tactiques", "Stratégie", "Ouvertures"):
        page.goto(f"{BASE}/#/"); page.wait_for_timeout(300); page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(900)
        set_rnd(page, 0.3); start_domain(page, label); go_play(page); page.wait_for_timeout(700)
        print(f" board {label}:", board_box(page))
        page.locator("header button", has_text="✕").first.tap(); page.wait_for_timeout(300)
    # feuille : taille du ✕
    set_rnd(page, 0.3); start_domain(page, "Finales")
    page.locator("text=Voir le cours complet").tap(); page.wait_for_timeout(400)
    print(" cibles: ✕ feuille", page.locator("div.fixed.inset-0.z-50 header button").bounding_box(), "| 'Voir le cours complet'", None)
    page.locator("div.fixed.inset-0.z-50 header button").tap(); page.wait_for_timeout(200)
    print(" cible 'Voir le cours complet':", page.locator("text=Voir le cours complet").bounding_box())
    print(" aria: ", page.evaluate("() => [...document.querySelectorAll('div.fixed.inset-0.z-40 header button')].map(b => ({txt:b.innerText, aria:b.getAttribute('aria-label'), title:b.title}))"))
    browser.close()

    # 3) saut de layout « Je vérifie… »
    browser, ctx, page, logs = open_mobile(p, standalone=True); page.add_init_script(RND_INIT)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1500)
    page.locator("main button", has_text="Options").tap(); page.wait_for_timeout(300)
    page.locator("text=Importer PGN ou FEN").tap(); page.wait_for_timeout(200)
    page.fill("textarea", PGN); page.locator("button:has-text('Charger')").tap(); page.wait_for_timeout(500)
    page.get_by_role("button", name="★ Bilan").tap(); page.wait_for_selector("text=Démarrer le bilan", timeout=240000)
    page.locator("header button:has-text('✕')").first.tap(); page.wait_for_timeout(500)
    page.goto(f"{BASE}/#/apprendre"); page.wait_for_timeout(1000)
    page.locator("button", has_text="Mes erreurs").tap(); page.wait_for_selector("text=C'est parti"); go_play(page)
    m0 = get_session(page)['session']['items'][0]['mistake']
    page.evaluate("""() => { window.__samples = []; const tick = () => { const b = document.querySelector("[id^='chessboard-']"); window.__samples.push([Math.round(performance.now()), b ? Math.round(b.getBoundingClientRect().top) : null, document.body.innerText.includes('Je vérifie')]); if (window.__samples.length < 900) requestAnimationFrame(tick) }; tick() }""")
    board = chess.Board(m0['fenBefore'])
    alts = [m for m in board.legal_moves if m.uci() != m0['bestUci'] and not (board.push(m), board.is_checkmate(), board.pop())[1]]
    play_my_move(page, board, alts[0], 'tap')
    for _ in range(100):
        if verdict_text(page): break
        page.wait_for_timeout(200)
    s = page.evaluate("() => window.__samples")
    tops = sorted({x[1] for x in s}); ver = [x for x in s if x[2]]
    print(" 'Je vérifie' : tops du board observés =", tops, "| frames avec le texte:", len(ver), "| durée:", (ver[-1][0] - ver[0][0]) if ver else 0, "ms | top pendant vérif:", sorted({x[1] for x in ver}))
    print(" verdict:", verdict_text(page))
    print("LOGS:", [l[:140] for l in logs][:3])
    browser.close()
