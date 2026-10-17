"""Gestes des cours : attendre le rendu de l’étape et chaque réponse avant de rejouer."""
import re
from contextlib import contextmanager

from playwright.sync_api import expect


def continue_btn(page):
    return page.get_by_role("button", name="Continuer", exact=True)


def solution_btn(page):
    return page.get_by_role("button", name="💡 Solution")


def wait_ready(page):
    # Une réponse peut terminer la ligne et supprimer Solution : attendre les deux issues.
    page.wait_for_function(
        """() => document.querySelector('[data-testid="line-feedback"]') &&
          [...document.querySelectorAll('button')].some((b) =>
            (b.textContent.includes('Solution') || b.textContent.trim() === 'Continuer') && !b.disabled)""",
        timeout=5000,
    )


def advance(page):
    """Le clic ne garantit pas que React a déjà remplacé l’étape précédente."""
    label = page.get_by_test_id("lesson-step")
    current, total = map(int, label.inner_text().split("/"))
    continue_btn(page).click()
    expect(label).to_have_text(f"{current + 1}/{total}", timeout=10000)


def open_lesson(page, url, lesson, step=1):
    page.goto(url)
    expect(page.locator("header h1")).to_have_text(lesson["title"], timeout=10000)
    expect(page.get_by_test_id("lesson-step")).to_have_text(f"{step}/{len(lesson['steps']) + 1}", timeout=10000)


def play_solution(page):
    wait_ready(page)
    status = page.get_by_text(re.compile(r"^(À toi : (Blancs|Noirs) · coup [0-9]+/[0-9]+|✓ Ligne terminée)$"))
    before = status.inner_text()
    solution_btn(page).click()
    # D’abord l’acceptation du clic (réponse en attente ou tour déjà changé),
    # puis la réponse adverse : chaque phase garde son budget de disponibilité.
    changed = status.filter(has_not_text=re.compile("^" + re.escape(before) + "$"))
    pending = solution_btn(page).and_(page.locator(":disabled"))
    expect(pending.or_(changed).first).to_be_visible(timeout=5000)
    # Le tour change après la réponse adverse, ou devient « Ligne terminée ».
    expect(status).not_to_have_text(before, timeout=5000)
    wait_ready(page)


def finish_line(page, max_moves=40):
    """Joue chaque tour une seule fois, jusqu’à la confirmation de fin de ligne."""
    expect(page.get_by_test_id("line-feedback")).to_be_visible(timeout=5000)
    for clicks in range(max_moves + 1):
        wait_ready(page)
        if continue_btn(page).is_enabled():
            return clicks
        if clicks == max_moves:
            raise AssertionError(f"Ligne non terminée après {max_moves} coups : {page.url}")
        play_solution(page)


def wait_piece(page, square, piece):
    """Le bouton peut être réactivé avant la fin de l’animation de react-chessboard."""
    locator = page.locator(f"[data-square='{square}'] [data-piece]")
    if piece is None:
        expect(locator).to_have_count(0, timeout=5000)
    else:
        expect(locator.first).to_have_attribute("data-piece", piece, timeout=5000)


@contextmanager
def observe_dom(page, predicate):
    """Mémoriser un état transitoire réellement rendu, sans modifier les timers de l’app."""
    observed = page.evaluate_handle("""(predicate) => {
      const matches = new Function('return (' + predicate + ')()')
      const state = { seen: false }
      const record = () => { state.seen ||= matches() }
      state.observer = new MutationObserver(record)
      state.observer.observe(document.body, { subtree: true, childList: true, attributes: true })
      record()
      return state
    }""", predicate)
    try:
        yield lambda: observed.evaluate("state => state.seen")
    finally:
        observed.evaluate("state => state.observer.disconnect()")
        observed.dispose()
