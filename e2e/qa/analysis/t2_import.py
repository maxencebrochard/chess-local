"""Passe 2 : import PGN / FEN collé + export."""
import os, sys, random
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *
import chess, chess.pgn


def long_pgn(plies=230, seed=7):
    rnd = random.Random(seed)
    while True:
        b = chess.Board()
        for _ in range(plies):
            ms = [m for m in b.legal_moves]
            rnd.shuffle(ms)
            ok = None
            for m in ms:
                b.push(m)
                bad = b.is_game_over(claim_draw=True)
                b.pop()
                if not bad:
                    ok = m; break
            if ok is None:
                break
            b.push(ok)
        if len(b.move_stack) == plies:
            g = chess.pgn.Game.from_board(b)
            return str(g.mainline_moves())


def strip(page):
    return page.evaluate("""() => [...document.querySelectorAll('main [data-current]')].filter(e => e.offsetParent).map(e => e.innerText + (e.dataset.current === 'true' ? '*' : ''))""")


def open_import(page):
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Importer PGN ou FEN").click(); page.wait_for_timeout(400)


def load_text(page, text, name):
    open_import(page)
    page.fill("textarea", text)
    page.locator("button", has_text="Charger").click(); page.wait_for_timeout(500)
    still_open = page.locator("textarea").count() > 0
    err = page.locator("p.text-red-400").inner_text() if page.locator("p.text-red-400").count() else ""
    print(f"[{name}] modal ouverte={still_open} erreur={err!r}")
    if still_open:
        shot(page, f"t2_{name}_err")
        page.touchscreen.tap(196, 40); page.wait_for_timeout(300)
        print(f"[{name}] fermée par tap extérieur:", page.locator("textarea").count() == 0)
    return not still_open


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(2000)

    # Modale : géométrie mobile
    open_import(page)
    box = page.locator("textarea").locator("xpath=..").bounding_box()
    print("modale import bbox:", box, "viewport 393")
    shot(page, "t2_00_modal")
    print("scroll fond pendant modale:", scroll_state(page))
    page.touchscreen.tap(196, 40); page.wait_for_timeout(300)

    # Joue 2 coups puis import vide : que devient la partie ?
    tap_move(page, "e2", "e4"); tap_move(page, "e7", "e5")
    print("avant import vide:", strip(page))
    load_text(page, "", "vide")
    print("après import vide:", strip(page))
    load_text(page, "   \n  ", "espaces")

    ok = load_text(page, "n'importe quoi", "invalide")
    ok = load_text(page, "1. e4 e5 2. Ke3", "coup_illegal")

    pgn_comments = """[Event "Test"]
[White "Alice"]
[Black "Bob"]
[Result "1-0"]

1. e4 {Meilleur par test} e5 $1 2. Nf3 (2. f4 exf4 3. Nf3) 2... Nc6 $6 3. Bb5 a6 {Morphy} 4. Ba4 Nf6 1-0"""
    ok = load_text(page, pgn_comments, "commentaires")
    print("coups:", strip(page))
    shot(page, "t2_01_comments")
    # Export PGN
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Copier le PGN").click(); page.wait_for_timeout(300)
    print("PGN exporté après import avec headers:\n", page.evaluate("navigator.clipboard.readText()"))
    print("toast/feedback copie visible ?", page.locator("text=/copi/i").count())

    # PGN avec header FEN
    pgn_fen = """[Event "Custom"]
[SetUp "1"]
[FEN "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"]

3... Nf6 4. Ng5 d5 5. exd5 Nxd5 6. Nxf7 Kxf7"""
    try:
        ok = load_text(page, pgn_fen, "pgn_fen_header")
        page.wait_for_timeout(800)
        print("coups:", strip(page), "| e4:", piece_on(page, "e4"), "c4:", piece_on(page, "c4"), "f7:", piece_on(page, "f7"))
        print("body len:", len(page.locator("body").inner_text()))
    except Exception as e:
        print("EXC pgn_fen:", str(e)[:200])
    shot(page, "t2_02_pgn_fen")
    print("LOGS après pgn fen:", logs)
    logs.clear()
    page.goto(f"{BASE}/#/"); page.wait_for_timeout(500)
    print("après crash, navigation hash vers / : body len", len(page.locator("body").inner_text()))
    page.reload(); page.wait_for_timeout(800)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(1500)

    # FEN
    ok = load_text(page, "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3", "fen_valide")
    print("fen ok, c4:", piece_on(page, "c4"), "bandeau:", page.locator("main .truncate.rounded.bg-surface-2").first.inner_text())
    tap_move(page, "g8", "f6"); page.wait_for_timeout(500)
    print("strip après coup noir depuis FEN:", strip(page))
    shot(page, "t2_03_fen_black_first")
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Copier le PGN").click(); page.wait_for_timeout(300)
    print("PGN exporté depuis FEN:\n", page.evaluate("navigator.clipboard.readText()"))
    load_text(page, "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq -", "fen_sans_compteurs")
    load_text(page, "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNX w KQkq - 0 1", "fen_invalide")
    load_text(page, "8/8/8/8/8/8/8/8 w - - 0 1", "fen_sans_rois")

    # Longue partie
    lp = long_pgn()
    print("long pgn plies:", len(lp.split()) )
    ok = load_text(page, lp, "longue")
    page.wait_for_timeout(1200)
    s = strip(page)
    print("longue: nb coups", len(s), "courant:", [x for x in s if x.endswith('*')])
    cur = page.evaluate("""() => {const s=[...document.querySelectorAll('main [data-current=\"true\"]')].find(e=>e.offsetParent); const r=s.getBoundingClientRect(); return {l:r.left,r:r.right}}""")
    print("coup courant visible dans la bande ? bbox", cur)
    shot(page, "t2_04_long")
    open(os.path.join(QA, "analysis", "long.pgn"), "w").write(lp)
    print("LOGS", logs)
    browser.close()
