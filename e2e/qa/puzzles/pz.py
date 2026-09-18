"""Aides spécifiques puzzles : lecture du puzzle courant (props React), jeu de la solution."""
import json
import os
import sys

QA = "e2e/qa"
os.environ.setdefault("SHOTS", os.path.join(QA, "puzzles", "shots"))
sys.path.insert(0, QA)
from qa_helpers import *  # noqa: E402,F401
import chess  # noqa: E402

REPO = "."

CURRENT_PUZZLE_JS = """() => {
  const el = document.querySelector('.boardbox');
  if (!el) return null;
  const key = Object.keys(el).find(k => k.startsWith('__reactFiber$'));
  if (!key) return null;
  const stack = [el[key].child];
  let guard = 0;
  while (stack.length && guard++ < 500) {
    const n = stack.pop();
    if (!n) continue;
    if (n.memoizedProps && n.memoizedProps.puzzle) return n.memoizedProps.puzzle;
    if (n.child) stack.push(n.child);
    if (n.sibling) stack.push(n.sibling);
  }
  return null;
}"""


def current_puzzle(page):
    return page.evaluate(CURRENT_PUZZLE_JS)


def wait_puzzle(page, timeout=30000, not_id=None):
    """Attend qu'un puzzle (différent de not_id) soit monté. Retourne le dict puzzle."""
    waited = 0
    while waited < timeout:
        pz = current_puzzle(page)
        if pz and pz["id"] != not_id:
            return pz
        page.wait_for_timeout(100)
        waited += 100
    raise RuntimeError("aucun puzzle monté")


def board_placement(page):
    """Placement FEN lu dans le DOM (data-square / data-piece)."""
    pieces = page.evaluate(
        """() => Object.fromEntries([...document.querySelectorAll('[data-square]')].map(s => {
            const p = s.querySelector('[data-piece]');
            return [s.getAttribute('data-square'), p ? p.getAttribute('data-piece') : null]
        }))"""
    )
    rows = []
    for r in range(8, 0, -1):
        row, empty = "", 0
        for f in "abcdefgh":
            pc = pieces.get(f"{f}{r}")
            if not pc:
                empty += 1
            else:
                if empty:
                    row += str(empty)
                    empty = 0
                row += pc[1] if pc[0] == "w" else pc[1].lower()
        if empty:
            row += str(empty)
        rows.append(row)
    return "/".join(rows)


def expected_placement(pz, n_moves):
    b = chess.Board(pz["fen"])
    for u in pz["moves"][:n_moves]:
        b.push_uci(u)
    return b.board_fen()


def wait_placement(page, pz, n_moves, timeout=4000):
    target = expected_placement(pz, n_moves)
    waited = 0
    while waited < timeout:
        if board_placement(page) == target:
            return True
        page.wait_for_timeout(50)
        waited += 50
    return False


def orientation(page):
    """'white' si a1 est en bas à gauche, sinon 'black'."""
    a1 = page.locator("[data-square='a1']").first.bounding_box()
    h8 = page.locator("[data-square='h8']").first.bounding_box()
    return "white" if a1["y"] > h8["y"] else "black"


def play_uci(page, uci, mode="tap"):
    frm, to = uci[:2], uci[2:4]
    if mode == "tap":
        tap_move(page, frm, to)
    else:
        drag_piece(page, frm, to)
    if len(uci) == 5:
        page.wait_for_timeout(200)
        glyph = {"q": ["♕", "♛"], "r": ["♖", "♜"], "b": ["♗", "♝"], "n": ["♘", "♞"]}[uci[4]]
        btn = page.locator(".boardbox button").filter(has_text=glyph[0])
        if btn.count() == 0:
            btn = page.locator(".boardbox button").filter(has_text=glyph[1])
        btn.first.tap()
        page.wait_for_timeout(200)


def solve(page, pz, mode="tap", upto=None, on_step=None):
    """Joue la solution. upto = nombre de coups JOUEUR à jouer (None = tous)."""
    assert wait_placement(page, pz, 1), "coup d'amorce non joué"
    moves = pz["moves"]
    played = 0
    i = 1
    while i < len(moves):
        play_uci(page, moves[i], mode if not callable(mode) else mode(played))
        played += 1
        if on_step:
            on_step(played)
        if upto and played >= upto:
            return i + 1
        if i + 1 < len(moves):
            assert wait_placement(page, pz, i + 2), f"réponse adverse {i + 1} non jouée"
        i += 2
    return len(moves)


def wrong_move(pz, n_moves_played, avoid_mate=True):
    """Un coup légal FAUX (ni la solution, ni un mat) dans la position après n_moves_played coups."""
    b = chess.Board(pz["fen"])
    for u in pz["moves"][:n_moves_played]:
        b.push_uci(u)
    expected = pz["moves"][n_moves_played]
    for m in b.legal_moves:
        if m.uci() == expected or m.promotion:
            continue
        b.push(m)
        mate = b.is_checkmate()
        b.pop()
        if avoid_mate and mate:
            continue
        return m.uci()
    return None


def panel_text(page):
    return page.locator("main").inner_text()


def rating_shown(page):
    return page.evaluate(
        """() => { const e = document.querySelector('main .text-3xl'); return e ? e.innerText.trim() : null }"""
    )


def db_dump(page):
    return page.evaluate(
        """async () => {
          const open = () => new Promise((res, rej) => { const r = indexedDB.open('chess-local'); r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error) });
          const d = await open();
          const all = (name) => new Promise((res) => { if (!d.objectStoreNames.contains(name)) return res([]); const q = d.transaction(name).objectStore(name).getAll(); q.onsuccess = () => res(q.result) });
          const out = { ratings: await all('ratings'), puzzleAttempts: await all('puzzleAttempts'), rushScores: await all('rushScores') };
          d.close();
          return out;
        }"""
    )


def heap_mb(page):
    cdp = page.context.new_cdp_session(page)
    cdp.send("Performance.enable")
    cdp.send("HeapProfiler.collectGarbage")
    m = {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}
    cdp.detach()
    return round(m["JSHeapUsedSize"] / 1e6, 1), int(m.get("Nodes", 0)), int(m.get("JSEventListeners", 0))


_ALL = None


def all_puzzles():
    global _ALL
    if _ALL is None:
        with open(os.path.join(REPO, "public", "puzzles.json")) as f:
            _ALL = json.load(f)
    return _ALL


def serve_custom(page, compact_list):
    """Remplace puzzles.json par une liste réduite (format compact)."""
    body = json.dumps(compact_list)
    page.route("**/puzzles.json", lambda route: route.fulfill(status=200, content_type="application/json", body=body))
