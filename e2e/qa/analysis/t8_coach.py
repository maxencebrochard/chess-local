"""Passe 8 : texte du coach (résumé, accords), brillant (mat de Legal), ?game inexistant, promotion."""
import os, sys, json
QA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SHOTS", os.path.join(QA, "analysis", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *

PGN = "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nd4 4. Nxe5 Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#"
LEGAL = "1. e4 e5 2. Nf3 d6 3. Bc4 Bg4 4. Nc3 g6 5. Nxe5 Bxd1 6. Bxf7+ Ke7 7. Nd5#"


def load_text(page, text):
    page.locator("main button", has_text="Options").click(); page.wait_for_timeout(300)
    page.locator("button", has_text="Importer PGN ou FEN").click(); page.wait_for_timeout(300)
    page.fill("textarea", text)
    page.locator("button", has_text="Charger").click(); page.wait_for_timeout(500)


def review(page, pgn):
    load_text(page, pgn)
    page.get_by_role("button", name="★ Bilan").click()
    page.wait_for_selector("text=Démarrer le bilan", timeout=240000); page.wait_for_timeout(300)


with sync_playwright() as p:
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.goto(f"{BASE}/#/analyse"); page.wait_for_timeout(2000)
    review(page, PGN)
    page.locator(".fixed header button").click(); page.wait_for_timeout(500)
    page.evaluate("() => {const m=document.querySelector('main'); m.scrollTop = m.scrollHeight}"); page.wait_for_timeout(300)
    print("RÉSUMÉ COACH (vue non guidée, position initiale):\n ", page.locator("main .border-l-4 p").inner_text())
    shot(page, "t8_00_coach_summary_card")

    # Mat de Legal : 5.Nxe5 est un sacrifice de dame (brillant sur chess.com)
    review(page, LEGAL)
    grids = page.evaluate("() => [...document.querySelectorAll('.fixed .grid')].map(g => g.innerText.replace(/\\n+/g,' | '))")
    print("LEGAL:", grids[1], "||", grids[2])
    page.locator("button", has_text="Démarrer le bilan").click(); page.wait_for_timeout(500)
    n = page.locator(".fixed [data-current]").count()
    for i in range(n):
        t = page.locator(".fixed .bg-white").first.inner_text().replace("\n", " | ")
        if i in (8, 9, 10, 12): print(f"  [{i}] {t}")
        if i == 8: shot(page, "t8_01_legal_nxe5")
        nxt = page.locator(".fixed button", has_text="Suivant")
        if nxt.count(): nxt.click(); page.wait_for_timeout(250)

    # Appel direct du module coach (code de l'app servi par Vite) avec un bilan fabriqué :
    out = page.evaluate("""async () => {
      const coach = await import('/src/lib/coach.ts')
      const mk = (san, uci, cls, best, extra={}) => ({san, uci, class: cls, evalAfterCp: -300, mateAfter: null, bestMoveUci: best, winPctBefore: 50, winPctAfter: 30, ...extra})
      const START='rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'
      const base = {startFen: START, startTurn: 'w', accuracyWhite: 50, accuracyBlack: 90, gameRatingWhite: 600, gameRatingBlack: 2000,
        counts: {w: {brilliant:0,great:0,best:0,excellent:0,good:0,book:2,inaccuracy:0,mistake:1,miss:0,missedWin:0,blunder:0}, b: {brilliant:0,great:0,best:0,excellent:0,good:0,book:2,inaccuracy:0,mistake:0,miss:0,missedWin:0,blunder:0}}, winPctSeries: [50,50,50,50,50,20]}
      // 1.e4 e5 2.Qh5 Nc6 3.Qxe5+?? : la dame est en prise
      const r1 = {...base, moves: [mk('e4','e2e4','book','e2e4'), mk('e5','e7e5','book','e7e5'), mk('Qh5','d1h5','good','g1f3'), mk('Nc6','b8c6','best','b8c6'), mk('Qxe5+','h5e5','mistake','g1f3')]}
      const c1 = coach.coachComments(r1, null)
      // faute au tout premier coup -> « 1e coup »
      const r2 = {...base, moves: [mk('f3','f2f3','mistake','e2e4', {winPctBefore: 53, winPctAfter: 30})]}
      return {dame: c1[4], resume1: coach.coachSummary(r2, 'w'), resume2: coach.coachSummary(r1, 'w')}
    }""")
    print("COACH dame en prise:", json.dumps(out["dame"], ensure_ascii=False))
    print("COACH résumé faute coup 1:", out["resume1"])
    print("COACH résumé r1:", out["resume2"])

    # ?game inexistant
    page.goto(f"{BASE}/#/"); page.wait_for_timeout(300)
    page.goto(f"{BASE}/#/analyse?game=99999&review=1"); page.wait_for_timeout(2000)
    print("?game=99999 -> hash:", page.evaluate("location.hash"), "| message d'erreur visible:", page.locator("text=/introuvable|inconnue|supprimée/i").count())

    # Promotion : annulation possible ?
    load_text(page, "8/P6k/8/8/8/8/8/K7 w - - 0 1")
    tap_move(page, "a7", "a8"); page.wait_for_timeout(400)
    shot(page, "t8_02_promo")
    print("sélecteur promo visible:", page.locator("button", has_text="♕").count())
    page.touchscreen.tap(30, 250); page.wait_for_timeout(400)
    print("après tap hors du sélecteur -> encore visible:", page.locator("button", has_text="♕").count(), "| Échap/annuler présent: non (voir capture)")
    page.locator("button", has_text="♘").click(); page.wait_for_timeout(500)
    print("sous-promotion cavalier:", piece_on(page, "a8"))
    print("LOGS", logs)
    browser.close()
