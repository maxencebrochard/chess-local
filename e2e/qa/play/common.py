"""Socle commun des scripts QA de la page Jouer."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("SHOTS", os.path.join(HERE, "shots"))
sys.path.insert(0, os.path.dirname(HERE))
from qa_helpers import *  # noqa: E402,F401,F403
import chess  # noqa: E402


def goto_play(page):
    page.goto(f"{BASE}/#/jouer")
    page.reload()
    page.wait_for_selector("text=Cadence", timeout=15000)
    page.wait_for_timeout(400)


def setup(page, mode="bot", bot="Noa", color="Blancs", tc="Illimité"):
    """Configure l'écran de setup et lance la partie."""
    label = {"bot": "Contre un bot", "coach": "Entraîneur", "local": "2 joueurs"}[mode]
    page.locator("main button", has_text=label).first.click()
    page.wait_for_timeout(150)
    if mode != "local":
        page.locator("main button", has_text=bot).first.click()
        page.locator("main button", has_text=color).first.click()
    if mode != "coach":
        page.locator("main button", has_text=tc).first.click()
    page.wait_for_timeout(150)
    page.get_by_role("button", name="Jouer", exact=True).click()
    page.wait_for_selector("[data-square='e2']", timeout=15000)
    page.wait_for_timeout(500)


def ply_count(page):
    return page.locator("main [data-current]").count()


def wait_ply(page, n, timeout=20000):
    """Attend que n demi-coups soient affichés. Retourne le temps d'attente en ms, ou None."""
    waited = 0
    while waited < timeout:
        if ply_count(page) >= n:
            return waited
        page.wait_for_timeout(100)
        waited += 100
    return None


def dom_position(page):
    """{square: 'wP'...} lu dans le DOM."""
    return page.evaluate(
        """() => {
          const out = {}
          document.querySelectorAll('[data-square]').forEach(sq => {
            const p = sq.querySelector('[data-piece]')
            if (p) out[sq.getAttribute('data-square')] = p.getAttribute('data-piece')
          })
          return out
        }"""
    )


def board_to_dict(board):
    out = {}
    for sq, pc in board.piece_map().items():
        out[chess.square_name(sq)] = ("w" if pc.color else "b") + pc.symbol().upper()
    return out


def sync_bot_move(page, board):
    """Trouve le coup légal qui amène `board` à la position du DOM, le pousse, le retourne."""
    dom = dom_position(page)
    for mv in list(board.legal_moves):
        board.push(mv)
        if board_to_dict(board) == dom:
            return mv
        board.pop()
    return None


def clock_texts(page):
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('main .font-mono.text-xl')).map(e => e.textContent)"""
    )


def rect(page, selector_or_locator):
    loc = page.locator(selector_or_locator) if isinstance(selector_or_locator, str) else selector_or_locator
    return loc.first.bounding_box()
