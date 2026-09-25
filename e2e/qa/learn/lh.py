"""Helpers spécifiques à la QA Apprendre."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("SHOTS", os.path.join(HERE, "shots"))
sys.path.insert(0, os.path.dirname(HERE))
from qa_helpers import *  # noqa

REPO = "."
COURSES = json.load(open(f"{REPO}/src/data/courses.json"))
ENDGAMES = json.load(open(f"{REPO}/src/data/endgames.json"))
STRATEGY = json.load(open(f"{REPO}/src/data/strategy.json"))

RND_INIT = "window.__rndQ = []; const __origRnd = Math.random; Math.random = () => (window.__rndQ && window.__rndQ.length) ? window.__rndQ.shift() : __origRnd();"


def set_rnd(page, *xs):
    """File de valeurs servies par Math.random (puis retour au vrai hasard)."""
    page.evaluate("(xs) => { window.__rndQ = xs }", list(xs))


def get_session(page):
    raw = page.evaluate("() => sessionStorage.getItem('learn-session-v1')")
    return json.loads(raw) if raw else None


def db_eval(page, body):
    """body : expression JS utilisant `db` (Dexie), retourne une promesse."""
    return page.evaluate("async () => { const m = await import('/src/lib/db.ts'); const db = m.db; return await (%s) }" % body)


def ratings(page):
    rows = db_eval(page, "db.ratings.toArray()")
    return {r["key"]: r for r in rows}


def set_rating(page, key, value, games=0):
    db_eval(page, "db.ratings.put({key: %s, value: %d, games: %d})" % (json.dumps(key), value, games))


def learn_sessions(page):
    return db_eval(page, "db.learnSessions.toArray()")


def expected_course_id(item):
    k = item["kind"]
    if k == "endgame":
        return item["endgame"]["id"]
    if k == "tactic":
        return item["theme"]
    if k == "strategy":
        for t in item["card"]["themes"]:
            if t in COURSES:
                return t
        return item["card"]["id"]
    if k == "opening":
        return "opening-principles"
    return None


def start_domain(page, label, wait=1500):
    page.locator("main button", has_text=label).first.tap()
    page.wait_for_selector("text=C'est parti", timeout=30000)
    page.wait_for_timeout(300)


def go_play(page):
    page.get_by_role("button", name="C'est parti").tap()
    page.wait_for_selector("[id^='chessboard-']", timeout=15000)
    page.wait_for_timeout(500)


def board_fen_pieces(page):
    """Dictionnaire case -> pièce du PREMIER board (exercice)."""
    return page.evaluate(
        """() => {
          const out = {}
          const board = document.querySelector("[id^='chessboard-']")
          if (!board) return out
          board.querySelectorAll('[data-square]').forEach(sq => {
            const p = sq.querySelector('[data-piece]')
            if (p) out[sq.getAttribute('data-square')] = p.getAttribute('data-piece')
          })
          return out
        }"""
    )


def session_scroller_top(page):
    return page.evaluate("() => { const e = document.querySelector('div.fixed.inset-0.z-40'); return e ? e.scrollTop : null }")


def box(page, sel):
    return page.locator(sel).first.bounding_box()
