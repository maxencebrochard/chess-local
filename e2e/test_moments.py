"""E2E « Moments critiques rejoués » (lot C2).

Deux volets :
- banc Node (src/lib/criticalMoments.ts bundlé par rolldown, exécuté sous Node) : bilans écrits à
  la main sur de vraies parties (positions calculées par python-chess), seuils de bascule et de
  coup unique, priorité coup forcé > menace > plan, filtre de couleur, maximum de 3, ordre
  chronologique, coups théoriques et coups seuls légaux écartés, textes ; détecteur de menace
  confronté à un oracle python-chess (coup nul : mat en 1, prise gagnante après échanges, échec)
  sur 300 positions réelles de puzzles lichess ;
- UI : partie chess.com de la fixture (popeye232, partie 104) ouverte par le lien profond de
  l'import, bilan réel ; section « Moments critiques » du résumé, cartes cohérentes avec
  l'échiquier, question, verdict et justification, ligne `learnSessions`, position rejouée contre
  Stockfish avec le coup du bilan, retour au résumé sans recalcul, statut « Retrouvé »,
  rechargement de `/moment-critique`, aucun Elo touché, `pickNextDomain` inchangé.

Fondée sur la fixture e2e/fixtures/chesscom.json : la partie UI est ignorée en --live.
Usage : npm run test:e2e -- --suite moments
"""
import json
import os
import re
import subprocess
import tempfile

import chess

from helpers import BASE, LIVE, Checker, desktop_context, mobile_context, overflow_x, shot

E2E_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(E2E_DIR)
ROLLDOWN = os.path.join(ROOT, "node_modules", ".bin", "rolldown")
ck = Checker("moments")
check = ck.check

DOMAIN = "critical-moment"
VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 100}
SAN_EN = re.compile(r"(?<![A-Za-z])[KQRBN][a-h1-8x]")

# ---------------------------------------------------------------------------------------- Node

NODE_JS = r"""
// engine.ts lit `location` au chargement du module (importé via review.ts) : stub avant l'import.
globalThis.location = { href: '' }
const mod = await import(process.argv[1])
let raw = ''
for await (const chunk of process.stdin) raw += chunk
const input = JSON.parse(raw)
const out = {
  cases: input.cases.map(({ review, color }) => mod.criticalMoments(review, color).map((m) => ({ ...m, text: mod.momentExplanation(m) }))),
  threats: input.fens.map((fen) => mod.threatIn(fen)),
  restore: input.restore.map(([raw, pgn]) => mod.restorableBilan(raw, pgn) !== null),
  rule: mod.ANSWER_RULE,
}
console.log(JSON.stringify(out))
"""


def bundle_module(tmp):
    path = os.path.join(tmp, "moments.mjs")
    r = subprocess.run([ROLLDOWN, "src/lib/criticalMoments.ts", "--format", "esm", "--file", path], cwd=ROOT, capture_output=True, text=True)
    if not check("[banc] bundle rolldown de criticalMoments.ts", r.returncode == 0, (r.stderr or r.stdout)[-300:]):
        return None
    return path


def run_node(bundle, payload):
    r = subprocess.run(["node", "--input-type=module", "-e", NODE_JS, "file://" + bundle], cwd=ROOT,
                       input=json.dumps(payload), capture_output=True, text=True)
    if not check("[banc] harnais Node", r.returncode == 0, r.stderr[-400:]):
        return None
    return json.loads(r.stdout)


def mk_review(sans, ann=None, start=chess.STARTING_FEN):
    """GameReview synthétique : `ann[i]` = {cls, wb, wa, ws, best (SAN)}, défaut 'best' sans chute."""
    ann = ann or {}
    board = chess.Board(start)
    moves = []
    for i, san in enumerate(sans):
        a = ann.get(i, {})
        mv = board.parse_san(san)
        if a.get("best") == "*":  # n'importe quel autre coup légal
            best = sorted(m.uci() for m in board.legal_moves if m != mv)[0]
        else:
            best = board.parse_san(a["best"]).uci() if "best" in a else mv.uci()
        wb = a.get("wb", 50.0)
        moves.append({
            "san": board.san(mv), "uci": mv.uci(), "class": a.get("cls", "best"),
            "evalAfterCp": 0, "mateAfter": None, "bestMoveUci": best,
            "winPctBefore": wb, "winPctAfter": a.get("wa", wb), "winPctSecond": a.get("ws", wb - 1),
        })
        board.push(mv)
    return {
        "moves": moves, "startFen": chess.Board(start).fen(), "startTurn": "w" if chess.Board(start).turn else "b",
        "accuracyWhite": 80, "accuracyBlack": 80, "counts": {"w": {}, "b": {}},
        "gameRatingWhite": 1500, "gameRatingBlack": 1500, "winPctSeries": [50] * (len(sans) + 1),
    }


def fen_before(sans, i, start=chess.STARTING_FEN):
    b = chess.Board(start)
    for san in sans[:i]:
        b.push_san(san)
    return b.fen()


def pgn_of(sans, start=None, white="A", black="B"):
    head = f'[White "{white}"]\n[Black "{black}"]\n'
    if start:
        head += f'[SetUp "1"]\n[FEN "{start}"]\n'
    b = chess.Board(start) if start else chess.Board()
    body = []
    for i, san in enumerate(sans):
        if b.turn:
            body.append(f"{b.fullmove_number}.")
        elif i == 0:
            body.append(f"{b.fullmove_number}...")
        body.append(san)
        b.push_san(san)
    return head + "\n" + " ".join(body) + " *"


SCHOLAR = ["e4", "e5", "Bc4", "Nc6", "Qh5", "Nf6", "Qxf7#"]
QGD = "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O Nf3 h6 Bh4 b6 cxd5 Nxd5 Bxe7 Qxe7 Nxd5 exd5 Rc1 Be6 Qa4 c5 Qa3 Rc8 Bb5 a6".split()
CENTER = ["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5"]
CHECKED = ["e4", "e5", "Bc4", "Nc6", "Bxf7+", "Kxf7"]
LONE_START = "k7/8/1K6/8/8/8/8/7R b - - 0 1"
PROMO_START = "4k3/8/8/8/8/8/p7/4K3 w - - 0 1"


# Oracle python-chess du détecteur de menace (même règle que threatIn) : roi en échec, sinon trait
# donné à l'adversaire (coup nul) : un mat en 1, sinon la prise la plus rentable après échanges,
# sinon une promotion en dame que rien ne reprend.
def see_py(board, sq):
    if board.piece_at(sq) is None:
        return 0
    caps = [m for m in board.legal_moves if m.to_square == sq]
    if not caps:
        return 0
    caps.sort(key=lambda m: VALUES[board.piece_at(m.from_square).piece_type])
    m = caps[0]
    gain = VALUES[board.piece_at(sq).piece_type]
    board.push(m)
    rest = see_py(board, sq)
    board.pop()
    return max(0, gain - rest)


def oracle_threat(fen):
    b = chess.Board(fen)
    if b.is_check():
        return ("check", None)
    me = b.turn
    b.push(chess.Move.null())
    for m in b.legal_moves:
        b.push(m)
        mate = b.is_checkmate()
        b.pop()
        if mate:
            return ("mate", None)
    best = 0
    for sq, piece in b.piece_map().items():
        if piece.color != me or piece.piece_type == chess.KING or not b.attackers(not me, sq):
            continue
        best = max(best, see_py(b, sq))
    if best >= 2:
        return ("capture", best)
    for m in list(b.legal_moves):
        if m.promotion != chess.QUEEN:
            continue
        b.push(m)
        retake = any(r.to_square == m.to_square for r in b.legal_moves)
        b.pop()
        if not retake:
            return ("promotion", None)
    return (None, None)


def puzzle_positions(n):
    with open(os.path.join(ROOT, "public", "puzzles.json"), encoding="utf-8") as f:
        puzzles = json.load(f)
    step = max(1, len(puzzles) // n)
    fens = []
    for p in puzzles[::step][:n]:
        b = chess.Board(p[1])
        b.push_uci(p[2].split()[0])
        fens.append(b.fen())
    return fens


def unit_node():
    tmp = tempfile.mkdtemp(prefix="chesslocal-moments-")
    bundle = bundle_module(tmp)
    if not bundle:
        return

    cases = {}

    def add(name, review, color):
        cases[name] = (review, color)

    # 1. Menace de mat : 3...Cf6?? laisse Dxf7#. Joueur noir.
    add("mat", mk_review(SCHOLAR, {5: {"cls": "blunder", "wb": 48, "wa": 0, "ws": 46, "best": "g6"}}), "b")
    # 2. Coup unique trouvé (3.Dh5, écart 30) côté blanc ; la gaffe noire n'est pas comptée.
    add("unique", mk_review(SCHOLAR, {4: {"wb": 60, "ws": 30}, 5: {"cls": "blunder", "wb": 48, "wa": 0, "ws": 46, "best": "g6"}}), "w")
    # 3. Plan : erreur de 15 points en position calme (8...h6 côté noir de la QGD).
    add("plan", mk_review(QGD, {11: {"cls": "mistake", "wb": 50, "wa": 35, "ws": 48, "best": "Nbd7"}}), "b")
    # 4. Menace de prise : 3.Cc3 attaque la dame d5 ; la réponse de Noir est jugée fautive.
    add("prise", mk_review(CENTER, {5: {"cls": "mistake", "wb": 45, "wa": 30, "ws": 44, "best": "Qd8"}}), "b")
    # 5. Échec : 3.Fxf7+, deux coups légaux.
    add("echec", mk_review(CHECKED, {5: {"cls": "blunder", "wb": 40, "wa": 10, "ws": 39, "best": "Ke7"}}), "b")
    # 6. Seuils de bascule : 9,9 non ; 10 oui ; avant 15 non ; après 85 non ; écart 20 non, 20,1 oui.
    add("seuils", mk_review(QGD, {
        2: {"cls": "inaccuracy", "wb": 50, "wa": 40.1, "best": "*"},  # 9,9 : non
        4: {"cls": "mistake", "wb": 50, "wa": 40, "best": "*"},       # 10 : oui
        6: {"cls": "blunder", "wb": 15, "wa": 0, "best": "*"},        # déjà perdu : non
        8: {"cls": "mistake", "wb": 99, "wa": 85, "best": "*"},       # encore gagnant : non
        10: {"wb": 60, "ws": 40},                                  # écart 20 : non
        12: {"wb": 60, "ws": 39.9},                                # écart 20,1 : oui (forcé)
    }), "w")
    # 7. Au plus 3, les plus lourds, dans l'ordre chronologique, voisins compris.
    add("max3", mk_review(QGD, {
        10: {"cls": "blunder", "wb": 55, "wa": 25, "best": "*"},  # 30
        12: {"cls": "blunder", "wb": 60, "wa": 20, "best": "*"},  # 40, voisin du précédent : gardé
        16: {"cls": "mistake", "wb": 50, "wa": 30, "best": "*"},  # 20
        20: {"cls": "blunder", "wb": 50, "wa": 25, "best": "*"},  # 25
        24: {"cls": "mistake", "wb": 50, "wa": 35, "best": "*"},  # 15
    }), "w")
    # 8. Coup théorique écarté, même avec une chute.
    add("book", mk_review(QGD, {0: {"cls": "book", "wb": 50, "wa": 20, "best": "*"}}), "w")
    # 9. Couleur inconnue : les deux camps.
    add("deux", mk_review(QGD, {6: {"cls": "blunder", "wb": 50, "wa": 20, "best": "*"}, 7: {"cls": "blunder", "wb": 60, "wa": 30, "best": "*"}}), None)
    # 10. Un seul coup légal : jamais un moment, même avec un écart de coup unique.
    add("seul", mk_review(["Kb8", "Rh8#"], {0: {"wb": 60, "ws": 30}}, start=LONE_START), "b")
    # 11. Coup forcé ET menace : la priorité va au coup forcé, la menace est citée.
    add("force_menace", mk_review(SCHOLAR, {5: {"cls": "blunder", "wb": 48, "wa": 0, "ws": 10, "best": "g6"}}), "b")
    # 12. Bilan d'avant les moments critiques (sans winPctSecond) : pas de coup forcé, rien ne casse.
    old = mk_review(QGD, {4: {"cls": "mistake", "wb": 50, "wa": 30, "best": "*"}})
    for m in old["moves"]:
        m.pop("winPctSecond")
    add("ancien", old, "w")

    # 13. Le coup joué égal au meilleur ne fait jamais une bascule (bruit de la profondeur fixe),
    #     et un autre coup ne fait jamais un « coup unique trouvé ».
    add("bruit", mk_review(QGD, {4: {"cls": "mistake", "wb": 50, "wa": 30}, 6: {"wb": 60, "ws": 30, "best": "*"}}), "w")
    # 14. Mat en 1 raté, 2e coup encore gagnant (écart 8) : coup forcé quand même.
    add("mat_rate", mk_review(SCHOLAR[:6] + ["d3"], {6: {"cls": "missedWin", "wb": 100, "wa": 50, "ws": 92, "best": "Qxf7#"}}), "w")
    # 15. Menace de promotion : le pion a2 va à dame, rien ne reprend en a1.
    add("promo", mk_review(["Ke2", "Kd7"], {0: {"cls": "blunder", "wb": 40, "wa": 20, "ws": 39, "best": "Kd1"}}, start=PROMO_START), "w")

    names = list(cases)
    fens = puzzle_positions(300)
    good_pgn = pgn_of(QGD)
    restore = [
        [{"review": cases["plan"][0], "gameKey": "pgn:x"}, good_pgn],
        [{"review": cases["plan"][0]}, pgn_of(QGD[:-1])],
        [{"review": cases["mat"][0]}, good_pgn],
        [None, good_pgn],
        [{"review": {"moves": "x"}}, good_pgn],
    ]
    out = run_node(bundle, {"cases": [{"review": r, "color": c} for r, c in cases.values()], "fens": fens, "restore": restore})
    if not out:
        return
    res = dict(zip(names, out["cases"]))

    def summary(name):
        return [(m["index"], m["answer"]) for m in res[name]]

    mat = res["mat"]
    check("[banc] menace de mat : un moment, 3...Cf6", summary("mat") == [(5, "threat")], f"({summary('mat')})")
    if mat:
        m = mat[0]
        check("[banc] menace de mat : Dxf7# détectée", m["threat"] == {"kind": "mate", "san": "Qxf7#"}, f"({m['threat']})")
        check("[banc] menace de mat : FEN avant le coup", m["fen"] == fen_before(SCHOLAR, 5), f"({m['fen']})")
        check("[banc] menace de mat : coup joué et meilleur coup", (m["playedSan"], m["bestUci"], m["bestSan"], m["found"]) == ("Nf6", "g7g6", "g6", False), f"({m['playedSan']}, {m['bestUci']}, {m['bestSan']}, {m['found']})")
        check("[banc] menace de mat : numéro de coup noir « 3... »", m["moveNo"] == "3...", f"({m['moveNo']})")
        check("[banc] menace de mat : texte avec la figurine adverse", "♕xf7#" in m["text"] and "mater" in m["text"], f"({m['text']})")
    check("[banc] coup unique trouvé : 3.Dh5 seul, forcé", summary("unique") == [(4, "forced")], f"({summary('unique')})")
    if res["unique"]:
        u = res["unique"][0]
        check("[banc] coup unique trouvé : marqué trouvé", u["found"] is True and u["drop"] == 0, f"({u['found']}, {u['drop']})")
        check("[banc] coup forcé : le texte ne nomme pas le coup à trouver", "h5" not in u["text"] and "60 %" in u["text"] and "30 %" in u["text"], f"({u['text']})")
    check("[banc] plan : erreur en position calme", summary("plan") == [(11, "plan")], f"({summary('plan')})")
    check("[banc] menace de prise : la dame d5 attaquée par Cc3", summary("prise") == [(5, "threat")], f"({summary('prise')})")
    if res["prise"]:
        t = res["prise"][0]["threat"]
        check("[banc] menace de prise : pièce, case, prise et gain", t == {"kind": "capture", "san": "Nxd5", "piece": "q", "square": "d5", "gain": 9}, f"({t})")
        check("[banc] menace de prise : texte", "la dame en d5 (♘xd5)" in res["prise"][0]["text"], f"({res['prise'][0]['text']})")
    check("[banc] échec : menace « check »", summary("echec") == [(5, "threat")] and res["echec"][0]["threat"] == {"kind": "check"}, f"({summary('echec')})")
    check("[banc] seuils : 10 points et écart 20,1 seulement", summary("seuils") == [(4, "plan"), (12, "forced")], f"({summary('seuils')})")
    check("[banc] maximum 3, les plus lourds, ordre chronologique", [m["index"] for m in res["max3"]] == [10, 12, 20], f"({[m['index'] for m in res['max3']]})")
    check("[banc] coup théorique écarté", res["book"] == [], f"({summary('book')})")
    check("[banc] couleur inconnue : les deux camps", [(m["index"], m["color"]) for m in res["deux"]] == [(6, "w"), (7, "b")], f"({[(m['index'], m['color']) for m in res['deux']]})")
    check("[banc] coup seul légal écarté", res["seul"] == [], f"({summary('seul')})")
    fm = res["force_menace"]
    check("[banc] forcé et menace : forcé prime, menace citée", summary("force_menace") == [(5, "forced")] and fm and "♕xf7#" in fm[0]["text"], f"({summary('force_menace')}, {fm[0]['text'] if fm else ''})")
    check("[banc] bilan ancien sans 2e coup : pas de coup forcé", [(m["index"], m["answer"], m["winSecond"]) for m in res["ancien"]] == [(4, "plan", None)], f"({res['ancien']})")

    check("[banc] bruit : ni bascule sur le coup de Stockfish, ni coup unique sur un autre coup", res["bruit"] == [], f"({summary('bruit')})")
    mr = res["mat_rate"]
    check("[banc] mat en 1 raté : coup forcé malgré un écart de 8", summary("mat_rate") == [(6, "forced")] and mr and mr[0]["bestMates"] and "mat en un coup" in mr[0]["text"], f"({summary('mat_rate')}, {mr[0]['text'] if mr else ''})")
    pr = res["promo"]
    check("[banc] menace de promotion", summary("promo") == [(0, "threat")] and pr and pr[0]["threat"] == {"kind": "promotion", "san": "a1=Q+", "square": "a1"}, f"({summary('promo')}, {pr[0]['threat'] if pr else ''})")
    if pr:
        check("[banc] menace de promotion : texte", "aller à dame en a1 (a1=♛+)" in pr[0]["text"], f"({pr[0]['text']})")

    texts = [m["text"] for ms in res.values() for m in ms] + [out["rule"]]
    check("[banc] aucun SAN anglais dans les textes", not [t for t in texts if SAN_EN.search(t)], f"({[t for t in texts if SAN_EN.search(t)][:2]})")
    check("[banc] aucun tiret cadratin", not [t for t in texts if "—" in t])
    check("[banc] retour au bilan : accepté seulement s'il correspond à la partie", out["restore"] == [True, False, False, False, False], f"({out['restore']})")

    # Oracle de la menace sur 300 positions de puzzles.
    mismatches = []
    kinds = {"check": 0, "mate": 0, "capture": 0, "promotion": 0, None: 0}
    for fen, got in zip(fens, out["threats"]):
        want_kind, want_gain = oracle_threat(fen)
        kinds[want_kind] += 1
        got_kind = got["kind"] if got else None
        if got_kind != want_kind or (want_kind == "capture" and got["gain"] != want_gain):
            mismatches.append((fen, want_kind, want_gain, got))
    check("[banc] menaces : oracle python-chess sur 300 positions de puzzles", not mismatches, f"({len(mismatches)} écarts, ex. {mismatches[:2]})")
    check("[banc] menaces : l'échantillon couvre échec, mat, prise et calme", all(kinds[k] >= 3 for k in ("check", "mate", "capture", None)), f"({kinds})")


# ------------------------------------------------------------------------------------------ UI

def idb(page, js):
    """Exécute `js(db)` (fonction async recevant la base Dexie ouverte nativement)."""
    return page.evaluate(
        """(src) => new Promise((resolve, reject) => {
          const req = indexedDB.open('chess-local')
          req.onerror = () => reject(req.error)
          req.onsuccess = () => { const fn = eval(src); Promise.resolve(fn(req.result)).then(resolve, reject) }
        })""",
        js,
    )


ALL_SESSIONS = """(db) => new Promise((resolve, reject) => {
  const tx = db.transaction('learnSessions', 'readonly')
  const r = tx.objectStore('learnSessions').getAll()
  r.onsuccess = () => resolve(r.result)
  r.onerror = () => reject(r.error)
})"""

ALL_RATINGS = """(db) => new Promise((resolve, reject) => {
  const tx = db.transaction('ratings', 'readonly')
  const r = tx.objectStore('ratings').getAll()
  r.onsuccess = () => resolve(r.result)
  r.onerror = () => reject(r.error)
})"""


def moment_sessions(page):
    return [s for s in idb(page, ALL_SESSIONS) if s["domain"] == DOMAIN]


def recommended_domain(page):
    """Domaine choisi par la « Séance rapide » d'Apprendre (pickNextDomain) : titre de la séance
    ouverte, sans son compteur d'items, puis séance refermée."""
    page.goto(f"{BASE}/#/apprendre")
    page.get_by_role("button", name="Séance rapide", exact=True).click()
    try:
        page.wait_for_selector("button[aria-label='Quitter la séance']", timeout=60000)
    except Exception:
        return ""
    title = page.evaluate("() => { const h = document.querySelector('header h1'); const n = h?.querySelector('span'); return h ? h.textContent.replace(n?.textContent ?? '', '').trim() : '' }")
    page.locator("button[aria-label='Quitter la séance']").click()
    return title


def open_bilan(page):
    page.goto(f"{BASE}/#/import?url=https://www.chess.com/game/live/104")
    btn = page.get_by_role("button", name=re.compile("Chercher cette partie"))
    if not ck.appears("[ui] bouton « Chercher cette partie »", page, "button:has-text('Chercher cette partie')"):
        return False
    btn.first.click()
    return ck.appears("[ui] bilan calculé (résumé affiché)", page, "button:has-text('Démarrer le bilan')", timeout=240000)


def card_facts(page):
    return page.evaluate("""() => [...document.querySelectorAll('[data-testid=critical-moment]')].map((e) => ({
      index: +e.dataset.index, fen: e.dataset.fen, best: e.dataset.best, answer: e.dataset.answer,
      gap: e.dataset.gap === '' ? null : +e.dataset.gap, threat: e.dataset.threat,
    }))""")


def ui_flow(p, browser):
    ctx = mobile_context(p, browser, ck, settings={"chesscomUsername": "popeye232"}, standalone=True)
    page = ctx.new_page()
    page.goto(f"{BASE}/#/")
    page.wait_for_timeout(800)
    ratings_before = idb(page, ALL_RATINGS)
    if not open_bilan(page):
        ctx.close()
        return

    section = page.locator("[data-testid=critical-moments]")
    if not ck.appears("[ui] section « Moments critiques » dans le résumé", page, "[data-testid=critical-moments]"):
        ctx.close()
        return
    section.scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    shot(page, "c2_moments_852")
    cards = card_facts(page)
    check("[ui] 1 à 3 moments critiques", 1 <= len(cards) <= 3, f"({len(cards)})")
    check("[ui] ordre chronologique", [c["index"] for c in cards] == sorted(c["index"] for c in cards))
    game = chess.Board()
    sans = "e4 e5 Nf3 Nc6 Bc4 Nd4 Nxe5 Qg5 Nxf7 Qxg2 Rf1 Qxe4+ Be2 Nf3#".split()
    for c in cards:
        b = chess.Board()
        for san in sans[: c["index"]]:
            b.push_san(san)
        tag = f"[ui] moment {c['index']}"
        check(f"{tag} : FEN = position avant le coup de la partie", c["fen"] == b.fen(), f"({c['fen']} vs {b.fen()})")
        check(f"{tag} : coup du joueur (Blancs, popeye232)", b.turn == chess.WHITE)
        legal = chess.Move.from_uci(c["best"]) in b.legal_moves if re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", c["best"] or "") else False
        check(f"{tag} : meilleur coup légal", legal, f"({c['best']})")
        kind, _ = oracle_threat(c["fen"])
        mates = legal and b.san(chess.Move.from_uci(c["best"])).endswith("#")
        if mates or (c["gap"] is not None and c["gap"] > 20):
            want = "forced"
        elif kind:
            want = "threat"
        else:
            want = "plan"
        check(f"{tag} : réponse attendue conforme aux faits (écart {c['gap']}, menace {kind})", c["answer"] == want and c["threat"] == (kind or ""), f"({c['answer']} / {c['threat']} vs {want} / {kind})")

    first = page.locator("[data-testid=critical-moment]").first
    target = cards[0]
    wrong = next(a for a in ("plan", "threat", "forced") if a != target["answer"])
    first.locator(f"[data-choice={wrong}]").click()
    verdict = first.locator("[data-testid=moment-verdict]")
    if ck.appears("[ui] verdict affiché après la réponse", page, "[data-testid=moment-verdict]"):
        check("[ui] mauvaise réponse : verdict « Pas tout à fait »", verdict.get_attribute("data-correct") == "0" and "Pas tout à fait" in verdict.inner_text(), f"({verdict.inner_text()[:80]!r})")
        check("[ui] justification et règle affichées", "La règle" in verdict.inner_text() and len(verdict.inner_text()) > 80)
        check("[ui] plus de boutons de choix sur cette carte", first.locator("[data-testid=moment-choice]").count() == 0)
    page.wait_for_timeout(300)
    rows = moment_sessions(page)
    check("[ui] réponse notée : une ligne question:<attendu>:<choisi>", [(r["itemId"], r["success"], r["fen"], r["ratingAfter"]) for r in rows] == [(f"question:{target['answer']}:{wrong}", 0, target["fen"], None)], f"({rows})")
    shot(page, "c2_moments_verdict_852")
    check("[ui] résumé sans débordement horizontal", not overflow_x(page))

    for previous_key in ("position", "moment"):
        previous = {
            "key": previous_key, "startFen": chess.STARTING_FEN, "player": "w",
            "label": "Partie précédente", "uci": ["e2e4", "e7e5"],
            "end": None, "assisted": False, "recorded": False,
        }
        page.evaluate("g => localStorage.setItem('chess-local-position-game-v1', JSON.stringify(g))", previous)
        first.locator("[data-testid=moment-replay]").click()
        if not ck.appears(f"[ui] autre partie {previous_key} : moment ouvert", page, "text=Objectif : trouve le bon coup"):
            ctx.close()
            return
        page.reload()
        if not ck.appears(f"[ui] autre partie {previous_key} : moment conservé avant le premier coup", page, "text=Objectif : trouve le bon coup"):
            ctx.close()
            return
        check(f"[ui] autre partie {previous_key} : sauvegarde intacte", page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-position-game-v1'))") == previous)
        page.locator("button[aria-label='Retour']").first.click()
        if not ck.appears(f"[ui] autre partie {previous_key} : retour au bilan conservé", page, "[data-testid=critical-moments]"):
            ctx.close()
            return
        check(f"[ui] autre partie {previous_key} : mêmes moments au bilan", card_facts(page) == cards)

    first.locator("[data-testid=moment-replay]").click()
    if not ck.appears("[ui] Rejouer ouvre /moment-critique", page, "text=Objectif : trouve le bon coup"):
        ctx.close()
        return
    check("[ui] URL /moment-critique", "#/moment-critique" in page.url, f"({page.url})")
    check("[ui] un seul échiquier, position du moment", page.locator("[data-board]").count() == 1)
    shot(page, "c2_moment_play_852")
    frm, to = target["best"][:2], target["best"][2:4]
    page.locator(f"[data-square='{frm}']").first.click()
    page.wait_for_timeout(250)
    page.locator(f"[data-square='{to}']").first.click()
    found = False
    for _ in range(100):
        rows = moment_sessions(page)
        if any(r["itemId"].startswith("coup:") for r in rows):
            found = True
            break
        page.wait_for_timeout(100)
    check("[ui] coup du bilan noté : ligne coup:<attendu> réussie", found and [(r["itemId"], r["success"], r["fen"]) for r in rows if r["itemId"].startswith("coup:")] == [(f"coup:{target['answer']}", 1, target["fen"])], f"({rows})")
    ck.appears("[ui] Stockfish répond", page, "[data-thinking='0']", state="attached", timeout=20000)
    page.wait_for_timeout(500)

    page.reload()
    ck.appears("[ui] rechargement : la partie du moment reprend", page, "text=Objectif : trouve le bon coup")
    moved = page.evaluate("() => JSON.parse(localStorage.getItem('chess-local-position-game-v1') || '{}').uci?.length ?? 0")
    check("[ui] rechargement : coups conservés", moved >= 1, f"({moved})")

    page.locator("button[aria-label='Retour']").first.click()
    t0 = page.evaluate("() => performance.now()")
    if ck.appears("[ui] retour : le résumé du bilan se rouvre", page, "button:has-text('Démarrer le bilan')", timeout=5000):
        dt = page.evaluate("() => performance.now()") - t0
        check("[ui] retour : bilan restauré sans recalcul (pas de progression)", page.locator("text=/Bilan en cours|\\d+ ?%/").count() == 0 or dt < 3000, f"({dt:.0f} ms)")
        check("[ui] retour : URL /analyse", "#/analyse" in page.url, f"({page.url})")
    page.locator("[data-testid=critical-moments]").scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    again = page.locator(f"[data-testid=critical-moment][data-index='{target['index']}']")
    check("[ui] retour : la réponse donnée reste affichée", again.locator("[data-testid=moment-verdict]").count() == 1)
    check("[ui] retour : statut « ✓ Retrouvé »", again.locator("[data-testid=moment-status]").inner_text().strip() == "✓ Retrouvé" if again.locator("[data-testid=moment-status]").count() else False)
    check("[ui] retour : nouvelle tentative proposée", "Rejouer encore" in again.locator("[data-testid=moment-replay]").inner_text())
    shot(page, "c2_moments_retour_852")

    check("[ui] aucun Elo modifié", idb(page, ALL_RATINGS) == ratings_before, f"({idb(page, ALL_RATINGS)})")
    # pickNextDomain : même proposition avec et sans les lignes du domaine (mesuré après le bilan,
    # qui écrit des fautes et peut lui-même changer la proposition).
    with_rows = recommended_domain(page)
    idb(page, """(db) => new Promise((resolve, reject) => {
      const tx = db.transaction('learnSessions', 'readwrite')
      const st = tx.objectStore('learnSessions')
      const r = st.getAll()
      r.onsuccess = () => { for (const s of r.result) if (s.domain === 'critical-moment') st.delete(s.id) }
      tx.oncomplete = () => resolve(true)
      tx.onerror = () => reject(tx.error)
    })""")
    without = recommended_domain(page)
    check("[ui] Apprendre propose la même séance (pickNextDomain ignore le domaine)", with_rows == without and len(without) > 3, f"({with_rows[:80]!r} / {without[:80]!r})")

    page.goto(f"{BASE}/#/")
    page.evaluate("() => localStorage.removeItem('chess-local-position-game-v1')")
    page.goto(f"{BASE}/#/moment-critique")
    ck.appears("[ui] /moment-critique sans moment : message et lien", page, "[data-testid=moment-missing]")
    ctx.close()


def layouts(p, browser):
    """Résumé en 393x660 (Safari) et 1440x900 : cartes lisibles, aucun débordement."""
    for tag, ctx in (
        ("660", mobile_context(p, browser, ck, settings={"chesscomUsername": "popeye232"})),
        ("1440", desktop_context(browser, ck, settings={"chesscomUsername": "popeye232"})),
    ):
        page = ctx.new_page()
        if open_bilan(page):
            sec = page.locator("[data-testid=critical-moments]")
            if ck.appears(f"[{tag}] section visible", page, "[data-testid=critical-moments]"):
                sec.scroll_into_view_if_needed()
                page.wait_for_timeout(400)
                check(f"[{tag}] aucun débordement horizontal", not overflow_x(page))
                boxes = page.evaluate("""() => [...document.querySelectorAll('[data-testid=critical-moment]')].map((e) => {
                  const r = e.getBoundingClientRect(); const b = e.querySelector('[data-board]').getBoundingClientRect()
                  return { w: r.width, bw: b.width, bh: b.height, inside: b.left >= r.left && b.right <= r.right }
                })""")
                check(f"[{tag}] diagrammes carrés et dans leur carte", boxes and all(abs(b["bw"] - b["bh"]) < 2 and b["inside"] and b["bw"] >= 100 for b in boxes), f"({boxes})")
                buttons = page.evaluate("""() => [...document.querySelectorAll('[data-testid=moment-choice]')].map((e) => e.getBoundingClientRect().height)""")
                check(f"[{tag}] boutons de choix d'au moins 44 px", buttons and min(buttons) >= 44, f"({buttons})")
                shot(page, f"c2_moments_{tag}")
                if tag == "1440":
                    # Bonne réponse (base neuve) : « Bien vu », ligne réussie.
                    first = page.locator("[data-testid=critical-moment]").first
                    want = first.get_attribute("data-answer")
                    first.locator(f"[data-choice={want}]").click()
                    page.wait_for_timeout(400)
                    v = first.locator("[data-testid=moment-verdict]")
                    check("[1440] bonne réponse : « Bien vu »", v.count() == 1 and v.get_attribute("data-correct") == "1" and "Bien vu" in v.inner_text())
                    rows = moment_sessions(page)
                    check("[1440] bonne réponse notée success=1", [(r["itemId"], r["success"]) for r in rows] == [(f"question:{want}:{want}", 1)], f"({rows})")
                    shot(page, "c2_moments_1440_verdict")
        ctx.close()


def ui_boundaries(browser):
    """Bilans jetables restaurés par l'interface de navigation, rendus par la vraie app."""
    cases = [
        ("seuils", QGD, {
            2: {"cls": "inaccuracy", "wb": 50, "wa": 40.1, "best": "*"},
            4: {"cls": "mistake", "wb": 50, "wa": 40, "best": "*"},
            6: {"cls": "blunder", "wb": 15, "wa": 0, "best": "*"},
            8: {"cls": "mistake", "wb": 99, "wa": 85, "best": "*"},
            10: {"wb": 60, "ws": 40},
            12: {"wb": 60, "ws": 39.9},
        }, "w", [(4, "plan"), (12, "forced")]),
        ("max3", QGD, {
            i: {"cls": "blunder", "wb": 60, "wa": 60 - drop, "best": "*"}
            for i, drop in [(10, 30), (12, 40), (16, 20), (20, 25), (24, 15)]
        }, "w", [(10, "plan"), (12, "threat"), (20, "plan")]),
        ("menace", SCHOLAR, {5: {"cls": "blunder", "wb": 48, "wa": 0, "ws": 46, "best": "g6"}}, "b", [(5, "threat")]),
        ("priorite", SCHOLAR, {5: {"cls": "blunder", "wb": 48, "wa": 0, "ws": 10, "best": "g6"}}, "b", [(5, "forced")]),
        ("mat_rate", SCHOLAR[:6] + ["d3"], {6: {"cls": "missedWin", "wb": 100, "wa": 50, "ws": 92, "best": "Qxf7#"}}, "w", [(6, "forced")]),
        ("sans_bascule", QGD, {4: {"cls": "mistake", "wb": 50, "wa": 30}, 6: {"wb": 60, "ws": 30, "best": "*"}}, "w", []),
    ]
    for name, sans, annotations, color, expected in cases:
        ctx = desktop_context(browser, ck)
        page = ctx.new_page()
        page.goto(f"{BASE}/#/")
        page.wait_for_selector("main")
        review = mk_review(sans, annotations)
        state = {"pgn": pgn_of(sans), "color": color, "bilan": {"review": review, "gameKey": None}}
        page.evaluate("state => history.replaceState({usr: state, key: 'boundary', idx: 0}, '', '#/analyse')", state)
        page.reload()
        page.wait_for_selector("[data-testid=critical-moments]")
        facts = card_facts(page)
        check(f"[ui limites] {name} : moments affichés", [(c["index"], c["answer"]) for c in facts] == expected, str(facts))
        for card in facts:
            box = page.locator(f"[data-testid=critical-moment][data-index='{card['index']}']")
            board = chess.Board(card["fen"])
            san = board.san(chess.Move.from_uci(card["best"]))
            figurines = dict(zip("KQRBN", "♔♕♖♗♘" if board.turn else "♚♛♜♝♞"))
            visible_san = "".join(figurines.get(c, c) for c in san)
            check(f"[ui limites] {name}/{card['index']} : solution masquée avant réponse", visible_san not in box.inner_text())
            box.locator(f"[data-choice={card['answer']}]").click()
            box.locator("[data-testid=moment-verdict]").wait_for()
            check(f"[ui limites] {name}/{card['index']} : solution masquée après réponse", visible_san not in box.inner_text())
        page.locator("[data-testid=critical-moments]").scroll_into_view_if_needed()
        shot(page, f"c2_boundary_{name}")
        if facts:
            page.locator("[data-testid=moment-replay]").last.click()
            page.get_by_text("Objectif : trouve le bon coup", exact=True).wait_for()
            check(f"[ui limites] {name} : solution masquée avant le premier coup", visible_san not in page.locator("main").inner_text())
        ctx.close()


def main(p):
    unit_node()
    if LIVE:
        print("[moments] partie UI fondée sur la fixture chess.com : ignorée en --live")
        return
    browser = p.chromium.launch()
    try:
        ui_flow(p, browser)
        layouts(p, browser)
        ui_boundaries(browser)
    finally:
        browser.close()


ck.run(main)
