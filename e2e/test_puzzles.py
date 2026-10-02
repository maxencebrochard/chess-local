"""E2E « Puzzles » : Puzzles classés et Puzzle Rush (lot l9-puzzles).

Ce qui est vérifié : une vie par puzzle en Rush (rafale de coups faux, coup faux puis bon coup),
UNE ligne `rushScores` par run (prod et StrictMode), record égalé sans « Nouveau record », chrono
en temps réel, score enregistré quand on quitte un run, solution affichée après un échec au
2e coup (SAN en figurines, promotion comprise), coup faux montré en rouge puis échiquier
verrouillé, série et puzzle courant conservés (rechargement, aller-retour analyse), « Passer »
payant, et `puzzles.json` en échec de chargement (état d'erreur, « Réessayer », aucune pageerror).
Les coups faux sont joués au tap (rafales) et au drag tactile réel (échec au 2e coup).

La base de 120 000 puzzles est remplacée par une liste réduite servie par `ctx.route` : les
scénarios deviennent déterministes et rapides. Le puzzle affiché est reconnu par le placement des
pièces lu dans le DOM, jamais par les internes React. Le service worker est bloqué : en prod, le
précache Workbox servirait le vrai fichier et contournerait la route.

Usage : npm run test:e2e -- --suite puzzles
        npm run test:e2e:dev -- --suite puzzles      (StrictMode : effets et updaters doublés)
"""
import json
import re
import sys

try:
    import chess
except ImportError:
    sys.exit("python-chess manquant : pip install -r e2e/requirements.txt")

from helpers import BASE, Checker, drag_piece, mobile_context, shot, sq_center, tap_move, tap_square

ck = Checker("puzzles")
check = ck.check

# Format compact de public/puzzles.json : [id, fen, moves, rating, themes], moves[0] est le coup
# adverse d'amorce joué automatiquement, puis alternance joueur / adversaire.
# Trois puzzles à 4 demi-coups, classés 700 à 900 : dans la bande d'un Elo de départ à 800.
FOUR_PLY = [
    ["007mr", "5k2/p2r3p/1p4pP/3r1q2/3Rp3/2P5/PP3PQ1/K3R3 w - - 0 33", "d4e4 d5d1 e1d1 d7d1", 739, "backRankMate endgame mate mateIn2 short"],
    ["00NAM", "r5k1/pp3ppp/8/3p4/3P4/4R2P/q1P1QPPK/8 b - - 1 21", "a2c4 e3e8 a8e8 e2e8", 715, "endgame mate mateIn2 short"],
    ["00eCY", "8/6p1/5p1p/R5kP/2b3P1/1r3PK1/8/8 b - - 4 61", "c4d5 a5d5 f6f5 d5f5", 774, "endgame hangingPiece mate mateIn2 short"],
]
# Douze puzzles à 2 demi-coups pour le Rush (résolus en un coup).
RUSH = [
    ["004yJ", "r4rk1/1bp2ppp/p1q1pn2/2P5/8/3B1N2/P1P1QPPP/R4RK1 w - - 0 16", "f3e5 c6g2", 737, "mate mateIn1 oneMove"],
    ["005Ep", "5kr1/ppR3p1/3R3p/8/1r1n4/8/1P3PPP/2K5 b - - 4 31", "d4b5 d6d8", 794, "mate mateIn1 oneMove"],
    ["009fH", "rn2kb1r/pp2pppp/2p2n2/8/3q2b1/1Q6/PPP2PPP/RNB1KBNR w KQkq - 0 7", "b3b7 d4d1", 769, "mate mateIn1 oneMove"],
    ["00A9Q", "2rq1rk1/1p3p1p/p1pn2p1/P2p4/1P1PnP2/3NP3/5PBP/R1Q3RK w - - 2 22", "d3c5 e4f2", 727, "mate mateIn1 oneMove"],
    ["00CYP", "3rk2r/p1p2pp1/1p6/2pQ1b2/2Pn1P2/8/PP1P1KBq/R1B1R3 b - - 3 25", "e8f8 d5d8", 776, "mate mateIn1 oneMove"],
    ["00Elq", "rn3q1r/4pk1p/2pp1np1/p5Q1/1p1PPNP1/5P2/PPP5/R4KNR b - - 0 17", "h7h6 g5g6", 791, "mate mateIn1 oneMove"],
    ["00Hfa", "6k1/5ppp/5Bq1/8/p3R3/P6P/2r2QB1/R5K1 b - - 0 29", "c2f2 e4e8", 741, "mate mateIn1 oneMove"],
    ["00KgR", "5r1k/1pq3p1/2p2P1p/3pPQ2/1p1P4/7P/1rB4K/5R2 b - - 1 35", "f8f6 f5h7", 782, "mate mateIn1 oneMove"],
    ["00ad3", "2kr3r/ppp2p2/2nb1n1p/4q1p1/Q7/N1P1B3/PP2NPPP/R4RK1 w - - 2 13", "a3c4 e5h2", 718, "mate mateIn1 oneMove"],
    ["00jUu", "8/5ppk/p1Q4p/2R4P/1q2P3/5P2/1P4P1/1K1n4 w - - 2 45", "c5c1 b4b2", 703, "mate mateIn1 oneMove"],
    ["00luA", "r2q1rk1/1b3pp1/p3p3/3n2b1/1pnN1P2/3Q4/PPP1NB2/1K1R1B1R b - - 2 20", "d5f4 d3h7", 745, "mate mateIn1 oneMove"],
    ["00mLm", "4Q1nk/p5bp/3P2p1/4p3/4Pq2/1B5P/6P1/7K b - - 2 35", "g7h6 e8g8", 770, "mate mateIn1 oneMove"],
]
# Un puzzle dont la solution est une promotion (exd8=Q#), pour le texte de la solution.
PROMO = [
    ["0LaM6", "2rR3k/1p2P1pP/6B1/4n3/8/8/7P/7K b - - 2 37", "c8d8 e7d8q", 799, "advancedPawn mate mateIn1 oneMove promotion"],
]

FIGURINES = {"w": {"K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘"}, "b": {"K": "♚", "Q": "♛", "R": "♜", "B": "♝", "N": "♞"}}

DB_JS = """async () => {
  const open = () => new Promise((res, rej) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) })
  const d = await open()
  const all = (name) => new Promise((res) => { if (!d.objectStoreNames.contains(name)) return res([]); const q = d.transaction(name).objectStore(name).getAll(); q.onsuccess = () => res(q.result) })
  const out = { ratings: await all('ratings'), puzzleAttempts: await all('puzzleAttempts'), rushScores: await all('rushScores') }
  d.close()
  return out
}"""

PLACEMENT_JS = """() => {
  const rows = []
  for (let r = 8; r >= 1; r--) {
    let row = '', empty = 0
    for (const f of 'abcdefgh') {
      const el = document.querySelector(`[data-square='${f}${r}'] [data-piece]`)
      const pc = el ? el.getAttribute('data-piece') : null
      if (!pc) { empty++; continue }
      if (empty) { row += empty; empty = 0 }
      row += pc[0] === 'w' ? pc[1] : pc[1].toLowerCase()
    }
    if (empty) row += empty
    rows.push(row)
  }
  return rows.join('/')
}"""


# ---------- contexte, route, lecture de l'app ----------

def open_page(p, browser, puzzles, standalone=True):
    """Contexte iPhone surveillé, `puzzles.json` remplacé par `puzzles`. Retourne (ctx, page, net) :
    `net["fail"] = True` fait échouer les chargements suivants (panne réseau simulée)."""
    ctx = mobile_context(p, browser, ck, standalone=standalone, service_workers="block")
    net = {"fail": False}
    body = json.dumps(puzzles)

    def handle(route):
        if net["fail"]:
            route.abort()
        else:
            route.fulfill(status=200, content_type="application/json", body=body)

    ctx.route("**/puzzles.json", handle)
    return ctx, ctx.new_page(), net


def db_dump(page):
    """Lecture directe d'IndexedDB (ratings, puzzleAttempts, rushScores), par ordre de clé."""
    return page.evaluate(DB_JS)


def puzzle_rating(page):
    return next((r["value"] for r in db_dump(page)["ratings"] if r["key"] == "puzzle"), None)


def wait_rush_scores(page, n, timeout=4000):
    """Sonde `rushScores` jusqu'à compter n lignes (l'écriture est asynchrone). Retourne les scores."""
    waited = 0
    while True:
        scores = [r["score"] for r in db_dump(page)["rushScores"]]
        if len(scores) >= n or waited >= timeout:
            return scores
        page.wait_for_timeout(200)
        waited += 200


def placement(page):
    """Placement FEN (sans trait ni droits) lu dans le DOM de react-chessboard."""
    return page.evaluate(PLACEMENT_JS)


def board_after(pz, n):
    """Position après les n premiers demi-coups de la solution."""
    b = chess.Board(pz[1])
    for u in pz[2].split()[:n]:
        b.push_uci(u)
    return b


def player_color(pz):
    return "b" if pz[1].split(" ")[1] == "w" else "w"


def figurine(san, color):
    return "".join(FIGURINES[color].get(c, c) for c in san)


def wait_placement(page, target, timeout=4000):
    waited = 0
    while waited < timeout:
        if placement(page) == target:
            return True
        page.wait_for_timeout(50)
        waited += 50
    return False


def wait_puzzle(page, served, not_id=None, timeout=15000):
    """Attend qu'un puzzle de `served` (autre que `not_id`) soit affiché AVEC son amorce jouée.
    Retourne le puzzle (tuple compact), ou None : le check appelant échoue proprement."""
    targets = {board_after(pz, 1).board_fen(): pz for pz in served if pz[0] != not_id}
    waited = 0
    while waited < timeout:
        pz = targets.get(placement(page))
        if pz:
            return pz
        page.wait_for_timeout(100)
        waited += 100
    return None


def wrong_move(pz, n_played):
    """Un coup légal FAUX après n_played demi-coups : ni la solution, ni un mat (accepté par
    l'app comme solution alternative), ni une promotion (sélecteur à part)."""
    b = board_after(pz, n_played)
    expected = pz[2].split()[n_played]
    for m in b.legal_moves:
        if m.uci() == expected or m.promotion:
            continue
        b.push(m)
        mate = b.is_checkmate()
        b.pop()
        if not mate:
            return m.uci()
    raise RuntimeError(f"aucun coup faux disponible pour {pz[0]}")


def solve(page, pz):
    """Joue toute la solution au tap, en attendant chaque réponse adverse. False si l'app ne suit pas."""
    moves = pz[2].split()
    for i in range(1, len(moves), 2):
        tap_move(page, moves[i][:2], moves[i][2:4], pause=150)
        if i + 1 < len(moves) and not wait_placement(page, board_after(pz, i + 2).board_fen()):
            return False
    return True


def quick_taps(page, *ucis, gap=40):
    """Coups enchaînés le plus vite possible (taps espacés de `gap` ms), sans attendre l'app."""
    for uci in ucis:
        x1, y1 = sq_center(page, uci[:2])
        x2, y2 = sq_center(page, uci[2:4])
        page.touchscreen.tap(x1, y1)
        page.wait_for_timeout(gap)
        page.touchscreen.tap(x2, y2)
        page.wait_for_timeout(gap)


def square_is_red(page, square):
    """La case (ou un de ses descendants, où react-chessboard pose squareStyles) est teintée en rouge."""
    return page.evaluate(
        """(sq) => {
          const root = document.querySelector(`[data-square='${sq}']`)
          if (!root) return false
          return [root, ...root.querySelectorAll('*')].some((n) => /rgba?\\(239, 68, 68/.test(getComputedStyle(n).backgroundColor))
        }""",
        square,
    )


def watch_red(page, square):
    """Guette à chaque frame la case teintée en rouge ; `window.__redSeen` passe à true dès qu'elle l'est."""
    page.evaluate(
        """(sq) => {
          window.__redSeen = false
          const tick = () => {
            const root = document.querySelector(`[data-square='${sq}']`)
            if (root && [root, ...root.querySelectorAll('*')].some((n) => /rgba?\\(239, 68, 68/.test(getComputedStyle(n).backgroundColor))) {
              window.__redSeen = true
              return
            }
            requestAnimationFrame(tick)
          }
          requestAnimationFrame(tick)
        }""",
        square,
    )


def main_text(page):
    return page.locator("main").inner_text()


def rating_shown(page):
    m = re.match(r"\s*(\d+)", page.locator("main .text-3xl").first.inner_text())
    return int(m.group(1)) if m else None


def streak_shown(page):
    txt = page.locator("main .text-orange-400").first.inner_text().strip()
    return int(txt) if txt.isdigit() else None


def rush_state(page):
    """(score, vies perdues) lus à l'écran pendant un run ; (None, None) hors run."""
    m = re.search(r"(\d+)\s*\n\s*résolus", main_text(page))
    strikes = page.evaluate("() => document.querySelectorAll('main .text-red-500').length")
    return (int(m.group(1)) if m else None, strikes if m else None)


def clock_seconds(page):
    loc = page.locator("main .font-mono").first
    m = re.match(r"(\d+):(\d+)", loc.inner_text()) if loc.count() else None
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def btn_class(page, label):
    return page.locator("main button", has_text=label).first.get_attribute("class") or ""


def tap_button(name, page, label, timeout=5000):
    """Tape un bouton de `main` s'il apparaît. Sinon un échec nommé, jamais une exception qui
    interrompt la suite avant le bilan."""
    if not ck.appears(name, page, f"main button:has-text('{label}')", timeout=timeout):
        return False
    page.locator("main button", has_text=label).first.tap()
    return True


# ---------- Puzzle Rush ----------

def rush_run(page, n_ok, tag):
    """Résout n_ok puzzles puis rate trois fois (un coup faux par puzzle). Retourne le dernier puzzle."""
    prev = None
    for i in range(n_ok):
        pz = wait_puzzle(page, RUSH, not_id=prev)
        if not check(f"[rush:{tag}] puzzle à résoudre n°{i + 1} affiché", pz is not None):
            return None
        check(f"[rush:{tag}] solution n°{i + 1} acceptée", solve(page, pz))
        prev = pz[0]
    for k in range(3):
        pz = wait_puzzle(page, RUSH, not_id=prev)
        if not check(f"[rush:{tag}] puzzle à rater n°{k + 1} affiché", pz is not None):
            return None
        tap_move(page, *split_uci(wrong_move(pz, 1)), pause=120)
        prev = pz[0]
    return prev


def split_uci(uci):
    return uci[:2], uci[2:4]


def rush_suite(p, browser):
    ctx, page, _ = open_page(p, browser, RUSH)
    page.goto(f"{BASE}/#/rush")
    if not ck.appears("[rush] menu prêt (puzzles chargés)", page, "main button:not([disabled]):has-text('Survie')", timeout=30000):
        ctx.close()
        return
    page.locator("main button", has_text="Survie").tap()

    # PUZ-1 : trois coups faux en rafale sur le même puzzle = UNE vie.
    pz = wait_puzzle(page, RUSH)
    if check("[rush] premier puzzle affiché", pz is not None):
        w = wrong_move(pz, 1)
        # La rafale puis une capture d'écran peuvent à elles seules dépasser le flash de 600 ms :
        # le rouge est guetté dans la page pendant la rafale, sans la ralentir.
        watch_red(page, w[2:4])
        quick_taps(page, w, w, w)
        page.wait_for_timeout(60)
        check("[rush] coup faux montré en rouge (PUZ-6)", page.evaluate("() => window.__redSeen === true"))
        shot(page, "rush_wrong_flash_852")
        page.wait_for_timeout(500)
        score, strikes = rush_state(page)
        check("[rush] 3 coups faux en rafale = 1 vie perdue, 0 point (PUZ-1)", (score, strikes) == (0, 1), f"(score {score}, vies perdues {strikes})")

    # PUZ-1 : coup faux puis bon coup dans la foulée = vie perdue, PAS de point.
    pz2 = wait_puzzle(page, RUSH, not_id=pz[0] if pz else None)
    if check("[rush] puzzle suivant après l'erreur", pz2 is not None):
        quick_taps(page, wrong_move(pz2, 1), pz2[2].split()[1])
        page.wait_for_timeout(900)
        score, strikes = rush_state(page)
        check("[rush] coup faux puis bon coup = pas de point (PUZ-1)", (score, strikes) == (0, 2), f"(score {score}, vies perdues {strikes})")

    # Un puzzle résolu = un point, puis 3e erreur = fin du run.
    pz3 = wait_puzzle(page, RUSH, not_id=pz2[0] if pz2 else None)
    if check("[rush] troisième puzzle", pz3 is not None):
        check("[rush] solution acceptée", solve(page, pz3))
        page.wait_for_timeout(250)
        shot(page, "rush_running_852")
        score, strikes = rush_state(page)
        check("[rush] puzzle résolu = 1 point", (score, strikes) == (1, 2), f"(score {score}, vies perdues {strikes})")
    pz4 = wait_puzzle(page, RUSH, not_id=pz3[0] if pz3 else None)
    if check("[rush] quatrième puzzle", pz4 is not None):
        tap_move(page, *split_uci(wrong_move(pz4, 1)), pause=120)
    if not ck.appears("[rush] écran de fin après la 3e erreur", page, "main button:has-text('Rejouer')", timeout=6000):
        ctx.close()
        return
    page.wait_for_timeout(400)
    check("[rush] premier run à 1 = nouveau record", page.locator("text=Nouveau record").count() == 1)
    rows = db_dump(page)["rushScores"]
    check("[rush] UNE ligne rushScores pour le run (PUZ-14)", len(rows) == 1 and rows[0]["score"] == 1 and rows[0]["mode"] == "survival",
          f"({[(r['mode'], r['score']) for r in rows]})")
    shot(page, "rush_done_852")

    # PUZ-11 : même score au run suivant = record égalé, pas « Nouveau record ».
    page.locator("main button", has_text="Rejouer").tap()
    rush_run(page, 1, "run2")
    if not ck.appears("[rush] fin du 2e run", page, "main button:has-text('Rejouer')", timeout=6000):
        ctx.close()
        return
    page.wait_for_timeout(400)
    check("[rush] record égalé = « Terminé », pas « Nouveau record » (PUZ-11)",
          page.locator("text=Nouveau record").count() == 0 and page.locator("main h1", has_text="Terminé").count() == 1)
    rows = db_dump(page)["rushScores"]
    check("[rush] deux runs = deux lignes", [r["score"] for r in rows] == [1, 1], f"({[r['score'] for r in rows]})")

    # PUZ-12 : quitter en plein run par la nav basse enregistre le score.
    page.locator("main button", has_text="Rejouer").tap()
    pz = wait_puzzle(page, RUSH)
    if check("[rush] 3e run démarré", pz is not None):
        check("[rush] un point avant de quitter", solve(page, pz))
        page.wait_for_timeout(300)
    nav = page.locator("nav a", has_text="Accueil").last
    if check("[rush] onglet Accueil présent", nav.count() == 1):
        nav.tap()
    scores = wait_rush_scores(page, 3)
    check("[rush] quitter en plein run enregistre le score (PUZ-12)", scores == [1, 1, 1], f"({scores})")
    ctx.close()


def rush_clock_suite(p, browser):
    """PUZ-10 : le chrono suit l'heure réelle. `fast_forward` saute 60 s en ne tirant les timers
    qu'une fois : un compteur de ticks ne perd qu'une seconde, une échéance en perd 60."""
    ctx, page, _ = open_page(p, browser, RUSH)
    page.clock.install()
    page.goto(f"{BASE}/#/rush")
    if not ck.appears("[rush:chrono] menu prêt", page, "main button:not([disabled]):has-text('3 minutes')", timeout=30000):
        ctx.close()
        return
    page.locator("main button", has_text="3 minutes").tap()
    ck.appears("[rush:chrono] chrono affiché", page, "main .font-mono", timeout=5000)
    page.wait_for_timeout(1500)
    before = clock_seconds(page)
    page.clock.fast_forward(60_000)
    page.wait_for_timeout(700)
    after = clock_seconds(page)
    check("[rush:chrono] 60 s sautées = chrono avancé d'au moins 50 s (PUZ-10)",
          before is not None and after is not None and before - after >= 50, f"({before} s -> {after} s)")
    ctx.close()


# ---------- Puzzles classés ----------

def puzzles_suite(p, browser):
    ctx, page, _ = open_page(p, browser, FOUR_PLY)
    page.goto(f"{BASE}/#/puzzles")
    ck.appears("[puzzles] page chargée", page, "text=Classement puzzles", timeout=30000)
    pz = wait_puzzle(page, FOUR_PLY)
    if not check("[puzzles] puzzle servi affiché, amorce jouée", pz is not None):
        ctx.close()
        return
    shot(page, "puzzles_solving_852")
    check("[puzzles] « Passer » n'est pas le bouton vert (PUZ-5)", "bg-accent" not in btn_class(page, "Passer"))

    # Résolution complète : série 1, Elo en hausse, une tentative réussie.
    check("[puzzles] solution acceptée", solve(page, pz))
    ck.appears("[puzzles] panneau Résolu", page, "text=Résolu", timeout=5000)
    page.wait_for_timeout(500)
    check("[puzzles] « Suivant » est le bouton vert", "bg-accent" in btn_class(page, "Suivant"))
    check("[puzzles] série à 1", streak_shown(page) == 1, f"({streak_shown(page)})")
    r_solved = rating_shown(page)
    check("[puzzles] Elo en hausse", r_solved is not None and r_solved > 800, f"({r_solved})")
    d = db_dump(page)
    check("[puzzles] une tentative réussie en base", [(a["puzzleId"], a["success"]) for a in d["puzzleAttempts"]] == [(pz[0], True)])
    shot(page, "puzzles_solved_852")

    # PUZ-3 : rechargement : série et puzzle courant conservés.
    page.reload()
    ck.appears("[puzzles] page rechargée", page, "text=Classement puzzles", timeout=30000)
    page.wait_for_timeout(800)
    check("[puzzles] série conservée après rechargement (PUZ-3)", streak_shown(page) == 1, f"({streak_shown(page)})")
    check("[puzzles] puzzle courant conservé après rechargement (PUZ-3)",
          page.locator("text=Résolu").count() == 1 and wait_puzzle(page, [pz], timeout=3000) is not None)

    # PUZ-3 : aller-retour vers l'analyseur.
    if tap_button("[puzzles] bouton Analyser après résolution", page, "Analyser avec Stockfish") and ck.appears(
        "[analyse] ouverte depuis le puzzle, bouton retour", page, "button:has-text('Retour')", timeout=30000
    ):
        page.locator("button", has_text="Retour").first.tap()
    ck.appears("[puzzles] retour sur la page", page, "text=Classement puzzles", timeout=10000)
    page.wait_for_timeout(800)
    check("[puzzles] série conservée au retour d'analyse (PUZ-3)", streak_shown(page) == 1, f"({streak_shown(page)})")
    check("[puzzles] même puzzle au retour d'analyse (PUZ-3)",
          page.locator("text=Résolu").count() == 1 and wait_puzzle(page, [pz], timeout=3000) is not None)

    # PUZ-2 et PUZ-6 : bon 1er coup, coup faux au 2e (en DRAG tactile : le drop d'un coup faux est
    # désormais accepté par react-chessboard) : solution correcte, coup faux montré, verrou.
    tap_button("[puzzles] bouton Suivant", page, "Suivant")
    pz2 = wait_puzzle(page, FOUR_PLY, not_id=pz[0])
    if not check("[puzzles] « Suivant » tire un autre puzzle", pz2 is not None):
        ctx.close()
        return
    moves = pz2[2].split()
    tap_move(page, *split_uci(moves[1]), pause=150)
    check("[puzzles] réponse adverse jouée", wait_placement(page, board_after(pz2, 3).board_fen()))
    page.wait_for_timeout(300)
    w = wrong_move(pz2, 3)
    drag_piece(page, *split_uci(w))
    b = board_after(pz2, 3)
    b.push_uci(w)
    check("[puzzles] coup faux laissé sur l'échiquier pendant le flash (PUZ-6)", placement(page) == b.board_fen())
    check("[puzzles] case du coup faux en rouge (PUZ-6)", square_is_red(page, w[2:4]))
    shot(page, "puzzles_wrong_flash_852")
    page.wait_for_timeout(800)
    check("[puzzles] position revenue après le flash", placement(page) == board_after(pz2, 3).board_fen())
    check("[puzzles] panneau Raté", page.locator("text=Raté").count() == 1)
    expected = figurine(board_after(pz2, 3).san(chess.Move.from_uci(moves[3])), player_color(pz2))
    check("[puzzles] « Le bon coup était » = coup attendu au 2e coup, en figurines (PUZ-2)",
          f"Le bon coup était {expected}" in main_text(page), f"(attendu « {expected} »)")
    shot(page, "puzzles_failed_852")
    tap_move(page, *split_uci(moves[3]), pause=150)
    page.wait_for_timeout(400)
    check("[puzzles] échiquier verrouillé après l'échec (PUZ-1/PUZ-17)",
          placement(page) == board_after(pz2, 3).board_fen() and page.locator("text=Résolu").count() == 0)
    check("[puzzles] série remise à 0", streak_shown(page) == 0, f"({streak_shown(page)})")
    n_attempts = len(db_dump(page)["puzzleAttempts"])
    check("[puzzles] l'échec est noté une fois", n_attempts == 2)

    # Réessayer puis Passer : le puzzle est déjà noté, pas de seconde tentative.
    tap_button("[puzzles] bouton Réessayer", page, "Réessayer")
    ck.appears("[puzzles] Réessayer relance", page, "text=Trouve le meilleur coup", timeout=5000)
    tap_button("[puzzles] bouton Passer après Réessayer", page, "Passer")
    page.wait_for_timeout(1200)
    check("[puzzles] Passer après un échec déjà noté n'écrit rien", len(db_dump(page)["puzzleAttempts"]) == n_attempts)

    # PUZ-5 : « Passer » d'emblée = échec : Elo en baisse, tentative ratée écrite.
    pz3 = wait_puzzle(page, FOUR_PLY, not_id=pz2[0])
    if check("[puzzles] troisième puzzle (le seul non tenté)", pz3 is not None and pz3[0] != pz[0]):
        r_before = puzzle_rating(page)
        tap_button("[puzzles] bouton Passer sur un puzzle neuf", page, "Passer")
        page.wait_for_timeout(1200)
        d = db_dump(page)
        last = d["puzzleAttempts"][-1] if d["puzzleAttempts"] else {}
        check("[puzzles] Passer écrit une tentative ratée (PUZ-5)",
              len(d["puzzleAttempts"]) == n_attempts + 1 and last.get("puzzleId") == pz3[0] and last.get("success") is False)
        r_after = puzzle_rating(page)
        check("[puzzles] Passer baisse l'Elo (PUZ-5)", r_after is not None and r_before is not None and r_after < r_before, f"({r_before} -> {r_after})")
    ctx.close()


def double_skip_suite(p, browser):
    """Double tap sur « Passer » : un seul puzzle passé et noté, un seul nouveau tirage. Sans garde,
    le 2e tap tirait aussitôt P2, puis la fin du 1er le remplaçait par P3 sans l'avoir noté."""
    ctx, page, _ = open_page(p, browser, RUSH)
    page.goto(f"{BASE}/#/puzzles")
    ck.appears("[double Passer] page chargée", page, "text=Classement puzzles", timeout=30000)
    pz = wait_puzzle(page, RUSH)
    if not check("[double Passer] puzzle affiché", pz is not None) or not ck.appears(
        "[double Passer] bouton Passer", page, "main button:has-text('Passer')"
    ):
        ctx.close()
        return
    # Avant et après l'amorce : chaque placement observé est rattaché à son puzzle.
    ids = {board_after(z, n).board_fen(): z[0] for z in RUSH for n in (0, 1)}
    # Les deux taps dans la même tâche : le 2e arrive forcément pendant que le 1er attend l'écriture
    # de l'Elo. Deux taps tactiles espacés de quelques ms laissent parfois le 1er finir, et le 2e
    # passe alors légitimement le puzzle suivant.
    page.locator("main button", has_text="Passer").first.evaluate("(b) => { b.click(); b.click() }")
    seen = [pz[0]]
    for _ in range(50):
        cur = ids.get(placement(page))
        if cur and cur != seen[-1]:
            seen.append(cur)
        page.wait_for_timeout(50)
    check("[double Passer] un seul nouveau puzzle tiré", len(seen) == 2, f"(puzzles vus : {seen})")
    attempts = [(a["puzzleId"], a["success"]) for a in db_dump(page)["puzzleAttempts"]]
    check("[double Passer] une seule tentative ratée, sur le puzzle passé", attempts == [(pz[0], False)], f"({attempts})")
    shot(page, "puzzles_double_skip_852")
    ctx.close()


def promo_suite(p, browser):
    """Solution avec promotion (PUZ-2), en 393x660 (onglet Safari) pour les captures."""
    ctx, page, _ = open_page(p, browser, PROMO, standalone=False)
    page.goto(f"{BASE}/#/puzzles")
    ck.appears("[promo] page chargée", page, "text=Classement puzzles", timeout=30000)
    pz = wait_puzzle(page, PROMO)
    if check("[promo] puzzle affiché", pz is not None):
        shot(page, "puzzles_solving_660")
        tap_move(page, *split_uci(wrong_move(pz, 1)), pause=150)
        ck.appears("[promo] panneau Raté", page, "text=Raté", timeout=5000)
        page.wait_for_timeout(800)
        expected = figurine(board_after(pz, 1).san(chess.Move.from_uci(pz[2].split()[1])), player_color(pz))
        check("[promo] solution affichée avec la pièce de promotion (PUZ-2)", f"Le bon coup était {expected}" in main_text(page), f"(attendu « {expected} »)")
        shot(page, "puzzles_failed_660")
    ctx.close()


# ---------- puzzles.json en échec ----------

def error_suite(p, browser):
    ctx, page, net = open_page(p, browser, FOUR_PLY)
    net["fail"] = True
    page.goto(f"{BASE}/#/puzzles")
    ck.appears("[erreur] /puzzles : état d'erreur affiché", page, "text=Impossible de charger les puzzles", timeout=10000)
    shot(page, "puzzles_error_852")
    net["fail"] = False
    tap_button("[erreur] /puzzles : bouton Réessayer", page, "Réessayer")
    ck.appears("[erreur] /puzzles : Réessayer charge la page", page, "text=Classement puzzles", timeout=15000)
    ctx.close()

    ctx, page, net = open_page(p, browser, RUSH)
    net["fail"] = True
    page.goto(f"{BASE}/#/rush")
    ck.appears("[erreur] /rush : état d'erreur affiché", page, "text=Impossible de charger les puzzles", timeout=10000)
    net["fail"] = False
    tap_button("[erreur] /rush : bouton Réessayer", page, "Réessayer")
    ck.appears("[erreur] /rush : Réessayer active les modes", page, "main button:not([disabled]):has-text('Survie')", timeout=15000)
    ctx.close()


def suite(p):
    browser = p.chromium.launch(headless=True)
    try:
        rush_suite(p, browser)
        rush_clock_suite(p, browser)
        puzzles_suite(p, browser)
        double_skip_suite(p, browser)
        promo_suite(p, browser)
        error_suite(p, browser)
    finally:
        browser.close()


ck.run(suite)
