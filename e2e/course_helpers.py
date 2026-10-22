"""Gestes des cours : attendre le rendu de l’étape et chaque réponse avant de rejouer."""
import re
from contextlib import contextmanager

from playwright.sync_api import expect


def continue_btn(page):
    return page.get_by_role("button", name="Continuer", exact=True)


def solution_btn(page):
    return page.get_by_role("button", name="💡 Solution")


def _settled(ck, page, name, wait):
    """Une attente manquée fait échouer un check nommé, avec l’étape et le message affichés."""
    try:
        wait()
        return True
    except Exception as e:  # AssertionError d’expect, TimeoutError de Playwright
        shown = _shown(page, "lesson-step") or "?"
        said = _shown(page, "line-feedback")[:80]
        reason = (str(e).strip().splitlines() or [""])[0]
        return ck.fail(name, f"({type(e).__name__} : {reason} ; étape {shown} « {said} » ; {page.url})")


def _shown(page, testid):
    try:
        return page.get_by_test_id(testid).first.inner_text(timeout=1000)
    except Exception:
        return ""


def wait_ready(ck, page):
    # Une réponse peut terminer la ligne et supprimer Solution : attendre les deux issues.
    return _settled(ck, page, "[cours] étape prête (Solution ou Continuer actif)", lambda: page.wait_for_function(
        """() => document.querySelector('[data-testid="line-feedback"]') &&
          [...document.querySelectorAll('button')].some((b) =>
            (b.textContent.includes('Solution') || b.textContent.trim() === 'Continuer') && !b.disabled)""",
        timeout=5000,
    ))


def advance(ck, page):
    """Le clic ne garantit pas que React a déjà remplacé l’étape précédente."""
    def wait():
        label = page.get_by_test_id("lesson-step")
        current, total = map(int, label.inner_text().split("/"))
        continue_btn(page).click()
        expect(label).to_have_text(f"{current + 1}/{total}", timeout=10000)
    return _settled(ck, page, "[cours] étape suivante affichée après Continuer", wait)


def open_lesson(ck, page, url, lesson, step=1):
    def wait():
        page.goto(url)
        expect(page.locator("header h1")).to_have_text(lesson["title"], timeout=10000)
        expect(page.get_by_test_id("lesson-step")).to_have_text(f"{step}/{len(lesson['steps']) + 1}", timeout=10000)
    return _settled(ck, page, f"[cours] leçon « {lesson['title']} » ouverte à l’étape {step}", wait)


def play_solution(ck, page):
    return wait_ready(ck, page) and _settled(ck, page, "[cours] réponse affichée après Solution", lambda: _solution(page)) and wait_ready(ck, page)


def _solution(page):
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


def finish_line(ck, page, max_moves=40):
    """Joue chaque tour une seule fois ; le check de l’appelant constate la fin de ligne."""
    for clicks in range(max_moves + 1):
        if not wait_ready(ck, page) or continue_btn(page).is_enabled() or clicks == max_moves:
            return clicks
        if not play_solution(ck, page):
            return clicks + 1


def wait_piece(ck, page, square, piece):
    """Le bouton peut être réactivé avant la fin de l’animation de react-chessboard."""
    locator = page.locator(f"[data-square='{square}'] [data-piece]")
    if piece is None:
        return _settled(ck, page, f"[cours] case {square} vidée", lambda: expect(locator).to_have_count(0, timeout=5000))
    return _settled(ck, page, f"[cours] {piece} rendu en {square}", lambda: expect(locator.first).to_have_attribute("data-piece", piece, timeout=5000))


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
