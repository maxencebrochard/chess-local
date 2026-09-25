"""T08 : passe visuelle. 393x852 avec safe-areas réelles simulées, 393x660, paysage 852x393, desktop 1440x900."""
import json
from pz import *

SAFE_CSS = ".pt-safe{padding-top:calc(59px + 12px)!important}.pb-safe{padding-bottom:34px!important}"


def measure(page, tag):
    r = page.evaluate("""() => {
      const m = document.querySelector('main'); const mr = m.getBoundingClientRect();
      const navs = [...document.querySelectorAll('nav')].filter(n => n.getBoundingClientRect().height > 0);
      const btns = [...document.querySelectorAll('main button')].filter(b => !b.closest('.boardbox')).map(b => { const r = b.getBoundingClientRect(); return { t: b.innerText.replace(/\\n/g, ' ').slice(0, 22), y: Math.round(r.y), bottom: Math.round(r.bottom), w: Math.round(r.width), h: Math.round(r.height) } });
      const bb = document.querySelector('.boardbox')?.getBoundingClientRect();
      return { mainBottom: Math.round(mr.bottom), mainScroll: [m.scrollHeight, m.clientHeight], board: bb ? [Math.round(bb.x), Math.round(bb.y), Math.round(bb.width), Math.round(bb.bottom)] : null,
               hidden: btns.filter(b => b.bottom > mr.bottom).map(b => b.t), btns, overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth, vw: innerWidth, vh: innerHeight }
    }""")
    print(f"[{tag}] viewport {r['vw']}x{r['vh']} main.bottom={r['mainBottom']} scroll(h/client)={r['mainScroll']} board(x,y,w,bottom)={r['board']} overflowX={r['overflowX']}")
    print(f"[{tag}] boutons hors écran sans scroller: {r['hidden']}")
    print(f"[{tag}] boutons: {[(b['t'], b['y'], b['w'], b['h']) for b in r['btns']]}")
    return r


def puzzles_states(page, tag):
    page.goto(f"{BASE}/#/puzzles")
    page.wait_for_selector("text=Classement puzzles", timeout=30000)
    pz = wait_puzzle(page); assert wait_placement(page, pz, 1); page.wait_for_timeout(200)
    measure(page, f"{tag}/solving"); shot(page, f"t08_{tag}_solving")
    w = wrong_move(pz, 1); tap_move(page, w[:2], w[2:4]); page.wait_for_timeout(500)
    measure(page, f"{tag}/failed"); shot(page, f"t08_{tag}_failed")
    page.locator("main button", has_text="Suivant").first.evaluate("b => b.click()")
    pz2 = wait_puzzle(page, not_id=pz["id"]); solve(page, pz2); page.wait_for_timeout(500)
    measure(page, f"{tag}/solved"); shot(page, f"t08_{tag}_solved")


def rush_states(page, tag):
    page.goto(f"{BASE}/#/rush")
    page.wait_for_function("() => document.querySelectorAll('main button').length >= 3 && ![...document.querySelectorAll('main button')].some(b => b.disabled)", timeout=30000)
    measure(page, f"{tag}/rush-menu"); shot(page, f"t08_{tag}_rush_menu")
    page.locator("main button", has_text="3 minutes").first.evaluate("b => b.click()")
    pz = wait_puzzle(page); solve(page, pz); page.wait_for_timeout(900)
    measure(page, f"{tag}/rush-running"); shot(page, f"t08_{tag}_rush_running")
    page.locator("main button").filter(has_text="✕").or_(page.locator("main button").filter(has_text="Arrêter")).first.evaluate("b => b.click()")
    page.wait_for_timeout(500)
    measure(page, f"{tag}/rush-done"); shot(page, f"t08_{tag}_rush_done")


with sync_playwright() as p:
    # 1. PWA standalone avec safe-areas réelles simulées (Dynamic Island 59 px, home indicator 34 px)
    browser, ctx, page, logs = open_mobile(p, standalone=True)
    page.add_init_script(f"document.addEventListener('DOMContentLoaded', () => {{ const s = document.createElement('style'); s.textContent = {json.dumps(SAFE_CSS)}; document.head.appendChild(s) }})")
    puzzles_states(page, "safe852"); rush_states(page, "safe852")
    print("LOGS:", set(l[:100] for l in logs)); browser.close()

    # 2. Onglet Safari 393x660
    browser, ctx, page, logs = open_mobile(p, standalone=False)
    puzzles_states(page, "tab660"); rush_states(page, "tab660")
    print("LOGS:", set(l[:100] for l in logs)); browser.close()

    # 3. Paysage 852x393
    browser = p.chromium.launch(headless=True)
    opts = dict(p.devices["iPhone 14 Pro landscape"]); opts["viewport"] = {"width": 852, "height": 393}
    ctx = browser.new_context(**opts); page = ctx.new_page(); logs = []
    page.on("pageerror", lambda e: logs.append(str(e)[:200]))
    puzzles_states(page, "land"); rush_states(page, "land")
    print("LOGS:", logs); browser.close()

    # 4. Desktop 1440x900 (souris : tap_move/solve utilisent touchscreen -> contexte avec has_touch)
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, has_touch=True); page = ctx.new_page(); logs = []
    page.on("pageerror", lambda e: logs.append(str(e)[:200]))
    page.on("console", lambda m: logs.append(m.text[:120]) if m.type == "error" else None)
    puzzles_states(page, "desk"); rush_states(page, "desk")
    print("LOGS:", set(logs)); browser.close()
